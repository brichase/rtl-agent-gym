"""Run a sequential task/model/condition/trial evaluation sweep."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence, TextIO

import yaml


RunEpisode = Callable[..., dict[str, Any]]
CONDITIONS = ("single_shot", "agentic")


@dataclass(frozen=True)
class TaskSpec:
    """A task directory and the stable name stored in results rows."""

    path: Path
    name: str


@dataclass(frozen=True)
class ModelSpec:
    """The requested model label plus the backend ID and optional effort."""

    requested_id: str
    backend_id: str
    max_effort: str | None = None


def _comma_list(value: str, option: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise ValueError(f"{option} must contain at least one value")
    if len(set(items)) != len(items):
        raise ValueError(f"{option} contains duplicate values")
    return items


def _task_name(task_dir: Path) -> str:
    metadata_path = task_dir / "task.yaml"
    if metadata_path.is_file():
        try:
            metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ValueError(f"cannot read {metadata_path}: {exc}") from exc
        if isinstance(metadata, dict) and isinstance(metadata.get("name"), str):
            name = metadata["name"].strip()
            if name:
                return name
    return task_dir.name


def resolve_tasks(value: str, *, root: Path = Path("tasks")) -> list[TaskSpec]:
    """Resolve CLI task names or paths without changing their sweep order."""

    requested = _comma_list(value, "--tasks")
    if "all" in requested:
        if requested != ["all"]:
            raise ValueError("--tasks all cannot be combined with other tasks")
        if not root.is_dir():
            raise ValueError(f"task root does not exist: {root}")
        paths = sorted(
            (path for path in root.iterdir() if (path / "task.yaml").is_file()),
            key=lambda path: path.name,
        )
        if not paths:
            raise ValueError(f"no task.yaml files found under {root}")
    else:
        paths = []
        for item in requested:
            direct = Path(item)
            path = direct if direct.is_dir() else root / item
            if not path.is_dir():
                raise ValueError(f"task directory does not exist: {item}")
            paths.append(path)

    tasks = [TaskSpec(path=path.resolve(), name=_task_name(path)) for path in paths]
    names = [task.name for task in tasks]
    if len(set(names)) != len(names):
        raise ValueError("resolved tasks contain duplicate task names")
    return tasks


def parse_models(value: str) -> list[ModelSpec]:
    """Parse model IDs, including Codex ``model@effort`` labels."""

    models: list[ModelSpec] = []
    for requested in _comma_list(value, "--models"):
        backend_id = requested
        max_effort: str | None = None
        if requested.startswith("gpt-") and "@" in requested:
            backend_id, separator, max_effort = requested.rpartition("@")
            if not separator or not backend_id or not max_effort:
                raise ValueError(f"invalid model effort syntax: {requested}")
        models.append(ModelSpec(requested, backend_id, max_effort))
    return models


def _result_key(row: dict[str, Any]) -> tuple[str, str, str, int] | None:
    try:
        return (
            str(row["task"]),
            str(row["model_id"]),
            str(row["condition"]),
            int(row["trial"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_completed(path: Path) -> set[tuple[str, str, str, int]]:
    """Load completed sweep coordinates from an existing JSONL file."""

    completed: set[tuple[str, str, str, int]] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {path} line {line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"expected object in {path} line {line_number}")
            key = _result_key(row)
            if key is None:
                raise ValueError(f"missing sweep dimensions in {path} line {line_number}")
            completed.add(key)
    return completed


def _supports_max_effort(run_episode: RunEpisode) -> bool:
    try:
        parameters = inspect.signature(run_episode).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        parameter.name == "max_effort"
        or parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    )


def _error_row(
    task: TaskSpec, model: ModelSpec, condition: str, trial: int, exc: BaseException
) -> dict[str, Any]:
    return {
        "task": task.name,
        "model_id": model.requested_id,
        "condition": condition,
        "trial": trial,
        "error": f"{type(exc).__name__}: {exc}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _is_solved(row: dict[str, Any]) -> bool:
    reward = row.get("reward")
    return isinstance(reward, (int, float)) and not isinstance(reward, bool) and reward >= 0.7


def run_sweep(
    *,
    tasks: Sequence[TaskSpec],
    models: Sequence[ModelSpec],
    conditions: Sequence[str],
    trials: int,
    out_dir: Path,
    max_turns: int,
    resume: bool,
    run_episode: RunEpisode,
    progress_stream: TextIO = sys.stdout,
) -> list[dict[str, Any]]:
    """Run episodes sequentially and append every result before continuing."""

    if trials < 1:
        raise ValueError("--trials must be at least 1")
    if max_turns < 1:
        raise ValueError("--max-turns must be at least 1")
    invalid_conditions = [condition for condition in conditions if condition not in CONDITIONS]
    if invalid_conditions:
        raise ValueError(f"unsupported conditions: {', '.join(invalid_conditions)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"
    completed = load_completed(results_path) if resume else set()
    total = len(tasks) * len(models) * len(conditions) * trials
    supports_effort = _supports_max_effort(run_episode)
    rows: list[dict[str, Any]] = []
    passed = errors = skipped = run_count = 0

    with results_path.open("a", encoding="utf-8") as handle:
        ordinal = 0
        for task in tasks:
            for model in models:
                for condition in conditions:
                    for trial in range(trials):
                        ordinal += 1
                        key = (task.name, model.requested_id, condition, trial)
                        label = f"{task.name} {model.requested_id} {condition} trial={trial}"
                        if key in completed:
                            skipped += 1
                            print(
                                f"[{ordinal}/{total}] SKIP {label} | "
                                f"run={run_count} pass={passed} errors={errors} skipped={skipped}",
                                file=progress_stream,
                                flush=True,
                            )
                            continue

                        kwargs: dict[str, Any] = {
                            "task_dir": task.path,
                            "model_id": model.backend_id,
                            "condition": condition,
                            "trial": trial,
                            "out_dir": out_dir,
                            "max_turns": max_turns,
                        }
                        if model.max_effort is not None and supports_effort:
                            kwargs["max_effort"] = model.max_effort
                        try:
                            row = run_episode(**kwargs)
                            if not isinstance(row, dict):
                                raise TypeError("run_episode must return a dict")
                            row = dict(row)
                            row.update(
                                task=task.name,
                                model_id=model.requested_id,
                                condition=condition,
                                trial=trial,
                            )
                        except Exception as exc:  # An episode failure must not abort a sweep.
                            row = _error_row(task, model, condition, trial, exc)

                        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                        rows.append(row)
                        run_count += 1
                        passed += int(_is_solved(row))
                        errors += int(bool(row.get("error")))
                        print(
                            f"[{ordinal}/{total}] DONE {label} reward={row.get('reward', 'n/a')} | "
                            f"run={run_count} pass={passed} errors={errors} skipped={skipped}",
                            file=progress_stream,
                            flush=True,
                        )
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", required=True, help="comma-separated task names/paths, or all")
    parser.add_argument("--models", required=True, help="comma-separated model IDs")
    parser.add_argument(
        "--conditions",
        required=True,
        help="comma-separated conditions: single_shot,agentic",
    )
    parser.add_argument("--trials", required=True, type=int)
    parser.add_argument("--out", type=Path, default=Path("results"))
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, run_episode_fn: RunEpisode | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tasks = resolve_tasks(args.tasks)
        models = parse_models(args.models)
        conditions = _comma_list(args.conditions, "--conditions")
        if run_episode_fn is None:
            from agent.loop import run_episode as run_episode_fn  # Late by contract.

        run_sweep(
            tasks=tasks,
            models=models,
            conditions=conditions,
            trials=args.trials,
            out_dir=args.out,
            max_turns=args.max_turns,
            resume=args.resume,
            run_episode=run_episode_fn,
        )
    except (ImportError, OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
