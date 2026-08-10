"""Generate Markdown summary tables from evaluation JSONL results."""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Sequence


SOLVED_REWARD = 0.7
CONDITION_ORDER = {"single_shot": 0, "agentic": 1}
FAILURE_STAGE_ORDER = (
    "none",
    "no_submission",
    "compile",
    "visible_sim",
    "tool_argument",
    "tool_execution",
    "hidden_sim",
    "oracle",
    "sanity",
    "synthesis",
    "protocol_violation",
)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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
            missing = [key for key in ("task", "model_id", "condition", "trial") if key not in row]
            if missing:
                raise ValueError(
                    f"missing {', '.join(missing)} in {path} line {line_number}"
                )
            rows.append(row)
    if not rows:
        raise ValueError(f"no results rows found in {path}")
    return rows


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _values(rows: Iterable[dict[str, Any]], field: str) -> list[float]:
    values = (_number(row.get(field)) for row in rows)
    return [value for value in values if value is not None]


def _mean(rows: Iterable[dict[str, Any]], field: str) -> float | None:
    values = _values(rows, field)
    return fmean(values) if values else None


def _solved(row: dict[str, Any]) -> bool:
    reward = _number(row.get("reward"))
    return reward is not None and reward >= SOLVED_REWARD


def _rate(count: int, total: int) -> str:
    return f"{100.0 * count / total:.1f}%" if total else "—"


def _count_rate(count: int, total: int) -> str:
    return f"{count}/{total} ({_rate(count, total)})"


def _fmt(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(headers: Sequence[str], body: Iterable[Sequence[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(_escape(cell) for cell in row) + " |" for row in body)
    return lines


def _condition_key(condition: str) -> tuple[int, str]:
    return CONDITION_ORDER.get(condition, len(CONDITION_ORDER)), condition


def _transcript_pointer(row: dict[str, Any], report_path: Path) -> str:
    explicit = row.get("transcript_path") or row.get("transcript")
    if explicit:
        target = Path(str(explicit))
        if target.is_absolute():
            try:
                target = Path(os.path.relpath(target, report_path.parent))
            except ValueError:
                pass
    else:
        transcript_model = str(row["model_id"])
        if transcript_model.startswith("gpt-") and "@" in transcript_model:
            # run_eval passes the base ID to run_episode, which names the transcript.
            transcript_model = transcript_model.rpartition("@")[0]
        filename = "_".join(
            (
                str(row["task"]),
                transcript_model,
                str(row["condition"]),
                str(row["trial"]),
            )
        ) + ".jsonl"
        target = Path("transcripts") / filename
    label = f"trial {row['trial']}"
    return f"[{label}]({target.as_posix().replace(' ', '%20')})"


def _group_rows(
    rows: Iterable[dict[str, Any]], fields: Sequence[str]
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row[field]) for field in fields)].append(row)
    return grouped


def _detail_table(
    rows: list[dict[str, Any]], report_path: Path
) -> tuple[list[str], dict[tuple[str, str, str], list[dict[str, Any]]]]:
    grouped = _group_rows(rows, ("task", "model_id", "condition"))
    has_cost = bool(_values(rows, "cost_usd"))
    headers = [
        "Task",
        "Model",
        "Condition",
        "Passes",
        "Pass rate",
        "Pass@1",
        "Pass@5",
        "Mean reward",
        "Mean turns",
        "Mean tool calls",
        "Mean tokens in",
        "Mean tokens out",
    ]
    if has_cost:
        headers.append("Mean cost (USD)")
    headers.extend(["Mean area norm (solved)", "Mean depth norm (solved)", "Flagged"])

    body: list[list[str]] = []
    ordered_keys = sorted(grouped, key=lambda key: (key[0], key[1], _condition_key(key[2])))
    for task, model, condition in ordered_keys:
        group = sorted(grouped[(task, model, condition)], key=lambda row: int(row["trial"]))
        solved = [row for row in group if _solved(row)]
        count, total = len(solved), len(group)
        flagged = [row for row in group if row.get("flagged") is True]
        flagged_cell = str(len(flagged))
        if flagged:
            flagged_cell += " (" + ", ".join(
                _transcript_pointer(row, report_path) for row in flagged
            ) + ")"
        detail = [
            task,
            model,
            condition,
            f"{count}/{total}",
            _rate(count, total),
            _count_rate(count, total),
            _count_rate(int(bool(solved)), 1),
            _fmt(_mean(group, "reward")),
            _fmt(_mean(group, "turns"), 2),
            _fmt(_mean(group, "tool_calls"), 2),
            _fmt(_mean(group, "tokens_in"), 1),
            _fmt(_mean(group, "tokens_out"), 1),
        ]
        if has_cost:
            detail.append(_fmt(_mean(group, "cost_usd"), 4))
        detail.extend(
            [
                _fmt(_mean(solved, "area_norm")),
                _fmt(_mean(solved, "depth_norm")),
                flagged_cell,
            ]
        )
        body.append(detail)
    return _table(headers, body), grouped


def _headline_table(rows: list[dict[str, Any]]) -> list[str]:
    by_model_condition = _group_rows(rows, ("model_id", "condition"))
    models = sorted({str(row["model_id"]) for row in rows})
    body: list[list[str]] = []
    for model in models:
        single = by_model_condition.get((model, "single_shot"), [])
        agentic = by_model_condition.get((model, "agentic"), [])

        def episode_cell(group: list[dict[str, Any]]) -> str:
            return _count_rate(sum(_solved(row) for row in group), len(group)) if group else "—"

        def task_cell(group: list[dict[str, Any]]) -> tuple[str, float | None]:
            if not group:
                return "—", None
            task_groups = _group_rows(group, ("task",))
            solved_tasks = sum(any(_solved(row) for row in task_rows) for task_rows in task_groups.values())
            total_tasks = len(task_groups)
            return _count_rate(solved_tasks, total_tasks), solved_tasks / total_tasks

        single_count = sum(_solved(row) for row in single)
        agentic_count = sum(_solved(row) for row in agentic)
        single_rate = single_count / len(single) if single else None
        agentic_rate = agentic_count / len(agentic) if agentic else None
        single_tasks, single_task_rate = task_cell(single)
        agentic_tasks, agentic_task_rate = task_cell(agentic)
        reward_single, reward_agentic = _mean(single, "reward"), _mean(agentic, "reward")
        body.append(
            [
                model,
                episode_cell(single),
                episode_cell(agentic),
                "—"
                if single_rate is None or agentic_rate is None
                else f"{100.0 * (agentic_rate - single_rate):+.1f} pp",
                single_tasks,
                agentic_tasks,
                "—"
                if single_task_rate is None or agentic_task_rate is None
                else f"{100.0 * (agentic_task_rate - single_task_rate):+.1f} pp",
                "—"
                if reward_single is None or reward_agentic is None
                else f"{reward_agentic - reward_single:+.3f}",
            ]
        )
    return _table(
        [
            "Model",
            "Single-shot episode passes",
            "Agentic episode passes",
            "Delta pass rate",
            "Single-shot task pass@5",
            "Agentic task pass@5",
            "Delta task pass@5",
            "Delta mean reward",
        ],
        body,
    )


def _latencies(row: dict[str, Any]) -> list[float]:
    value = row.get("latency_ms_per_call")
    if isinstance(value, (list, tuple)):
        values = (_number(item) for item in value)
        return [item for item in values if item is not None]
    number = _number(value)
    return [] if number is None else [number]


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _cache_counts(row: dict[str, Any]) -> tuple[float, float]:
    hits_value = row.get("cache_hits")
    if isinstance(hits_value, (list, tuple)):
        hits = float(sum(bool(item) for item in hits_value))
        return hits, float(len(hits_value))
    hits = _number(hits_value)
    if hits is None:
        return 0.0, 0.0
    for field in ("cache_lookups", "cache_requests"):
        queries = _number(row.get(field))
        if queries is not None:
            return hits, queries
    latency_count = len(_latencies(row))
    if isinstance(row.get("latency_ms_per_call"), (list, tuple)) and latency_count:
        return hits, float(latency_count)
    tool_calls = _number(row.get("tool_calls"))
    return hits, tool_calls or 0.0


def _latency_table(rows: list[dict[str, Any]]) -> list[str] | None:
    if not any(
        _latencies(row) or row.get("cache_hits") is not None
        for row in rows
    ):
        return None
    grouped = _group_rows(rows, ("model_id", "condition"))
    body: list[list[str]] = []
    for model, condition in sorted(grouped, key=lambda key: (key[0], _condition_key(key[1]))):
        group = grouped[(model, condition)]
        latencies = [latency for row in group for latency in _latencies(row)]
        hits, queries = (sum(values) for values in zip(*(_cache_counts(row) for row in group)))
        cache = "—" if not queries else _count_rate(int(hits), int(queries))
        body.append(
            [
                model,
                condition,
                len(latencies),
                _fmt(_percentile(latencies, 0.50), 1),
                _fmt(_percentile(latencies, 0.95), 1),
                cache,
            ]
        )
    return _table(
        ["Model", "Condition", "Timed calls", "Latency p50 (ms)", "Latency p95 (ms)", "Cache hits"],
        body,
    )


def _failure_table(rows: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        stage = row.get("first_failure_stage")
        counts[str(stage) if stage else "unknown"] += 1
    ordered = [stage for stage in FAILURE_STAGE_ORDER if counts[stage]]
    ordered.extend(sorted(stage for stage in counts if stage not in FAILURE_STAGE_ORDER))
    return _table(
        ["First failure stage", "Episodes", "Share"],
        ([stage, counts[stage], _rate(counts[stage], len(rows))] for stage in ordered),
    )


def render_report(rows: list[dict[str, Any]], *, input_path: Path, output_path: Path) -> str:
    detail, _ = _detail_table(rows, output_path)
    lines = [
        "# Evaluation report",
        "",
        f"Source: `{input_path.as_posix()}` ({len(rows)} episodes). Solved means reward >= {SOLVED_REWARD}.",
        "Pass@1 is the empirical solved-episode fraction; pass@5 records whether any trial in the group solved.",
        "",
        "## Single-shot to agentic headline",
        "",
        *_headline_table(rows),
        "",
        "## Results by task, model, and condition",
        "",
        *detail,
        "",
        "## First-failure attribution",
        "",
        *_failure_table(rows),
    ]
    latency = _latency_table(rows)
    if latency is not None:
        lines.extend(["", "## Tool latency and cache", "", *latency])
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="input_path", type=Path, default=Path("results/results.jsonl"))
    parser.add_argument("--out", dest="output_path", type=Path, default=Path("results/report.md"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rows = load_rows(args.input_path)
        report = render_report(rows, input_path=args.input_path, output_path=args.output_path)
        args.output_path.parent.mkdir(parents=True, exist_ok=True)
        args.output_path.write_text(report, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"wrote {args.output_path} ({len(rows)} episodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
