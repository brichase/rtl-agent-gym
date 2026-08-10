"""Public episode driver for single-shot and tool-using RTL agents."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any

from env.grade import _versions, grade, load_task
from env.runner import EpisodeState

from .backends import BackendResult
from .backends.anthropic_backend import AnthropicBackend
from .backends.codex_backend import CodexBackend
from .backends.mock_backend import MockBackend
from .pricing import calculate_cost
from .prompts import Prompt, build_prompt, prompt_hash


RESULT_FIELDS = (
    "task",
    "model_id",
    "condition",
    "trial",
    "compile_ok",
    "visible_pass",
    "hidden_pass",
    "oracle_pass",
    "sanity_ok",
    "area_norm",
    "depth_norm",
    "reward",
    "turns",
    "tool_calls",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_ms_per_call",
    "cache_hits",
    "protocol_ok",
    "protocol_violations",
    "first_failure_stage",
    "tool_versions",
    "prompt_hash",
    "timestamp",
)


def _safe_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    return cleaned.strip("._") or "episode"


def _empty_row(
    task_name: str,
    model_id: str,
    condition: str,
    trial: int,
    tools_dir: str | None,
) -> dict[str, Any]:
    return {
        "task": task_name,
        "model_id": model_id,
        "condition": condition,
        "trial": trial,
        "compile_ok": False,
        "visible_pass": False,
        "hidden_pass": False,
        "oracle_pass": False,
        "sanity_ok": False,
        "area_norm": None,
        "depth_norm": None,
        "reward": 0.0,
        "turns": 0,
        "tool_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost_usd": None,
        "latency_ms_per_call": [],
        "cache_hits": 0,
        "protocol_ok": True,
        "protocol_violations": [],
        "first_failure_stage": "no_submission",
        "tool_versions": _versions(tools_dir),
        "prompt_hash": None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "error": None,
    }


class _Transcript:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.stream = path.open("w", encoding="utf-8")

    @staticmethod
    def _default(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, Path):
            return str(value)
        return repr(value)

    def write(self, event: dict[str, Any]) -> None:
        record = {"timestamp": time.time(), **event}
        self.stream.write(
            json.dumps(record, ensure_ascii=False, sort_keys=True, default=self._default) + "\n"
        )
        self.stream.flush()

    def close(self) -> None:
        self.stream.close()


_VERILOG_BLOCK = re.compile(
    r"```(?:verilog|systemverilog)\s*\n(?P<rtl>.*?)```", re.IGNORECASE | re.DOTALL
)


def _final_verilog(text: str) -> str | None:
    matches = list(_VERILOG_BLOCK.finditer(text))
    if not matches:
        return None
    rtl = matches[-1].group("rtl").strip()
    return rtl + "\n" if rtl else None


def _backend(model_id: str) -> Any:
    if model_id == "mock":
        return MockBackend()
    if model_id.startswith("claude-"):
        return AnthropicBackend(model_id)
    if model_id.startswith("gpt-"):
        return CodexBackend(model_id)
    raise ValueError(f"unsupported model_id: {model_id}")


def _apply_grading(row: dict[str, Any], graded: dict[str, Any]) -> None:
    for field in (
        "compile_ok",
        "visible_pass",
        "hidden_pass",
        "oracle_pass",
        "sanity_ok",
        "area_norm",
        "depth_norm",
        "reward",
        "first_failure_stage",
        "tool_versions",
    ):
        row[field] = graded.get(field)


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
_FAILURE_RANK = {stage: rank for rank, stage in enumerate(FAILURE_STAGE_ORDER[1:])}


def _first_failure_stage(
    *,
    submitted: bool,
    graded: dict[str, Any] | None,
    backend_result: BackendResult,
) -> str:
    candidates: list[str] = []
    if not submitted:
        candidates.append("no_submission")
    if graded is not None:
        stage = graded.get("first_failure_stage")
        if stage in _FAILURE_RANK:
            candidates.append(str(stage))
    if getattr(backend_result, "tool_argument_errors", []):
        candidates.append("tool_argument")
    if getattr(backend_result, "tool_execution_errors", []):
        candidates.append("tool_execution")
    if getattr(backend_result, "protocol_violations", []):
        candidates.append("protocol_violation")
    return min(candidates, key=_FAILURE_RANK.__getitem__) if candidates else "none"


def run_episode(
    task_dir: Path,
    model_id: str,
    condition: str,
    trial: int,
    out_dir: Path,
    max_turns: int = 10,
) -> dict[str, Any]:
    """Run and grade one episode, converting all episode failures into a row."""
    task_dir = Path(task_dir).resolve()
    out_dir = Path(out_dir).resolve()
    tools_dir = os.environ.get("RTL_GYM_TOOLS")
    try:
        task_name = load_task(task_dir).name
    except Exception:
        task_name = task_dir.name
    row = _empty_row(task_name, model_id, condition, trial, tools_dir)
    stem = "_".join(
        (_safe_component(task_name), _safe_component(model_id), _safe_component(condition), str(trial))
    )
    transcript_path = out_dir / "transcripts" / f"{stem}.jsonl"
    episode_dir = out_dir / "episodes" / stem
    transcript: _Transcript | None = None
    state: EpisodeState | None = None
    backend_result = BackendResult()
    graded: dict[str, Any] | None = None

    try:
        if condition not in {"single_shot", "agentic"}:
            raise ValueError(f"unknown condition: {condition}")
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        episode_dir.mkdir(parents=True, exist_ok=True)
        for stale_name in ("submission.v", "mcp_state.json", "mcp_state.tmp", "tool_log.jsonl"):
            stale = episode_dir / stale_name
            if stale.is_file():
                stale.unlink()
        cache_dir = episode_dir / "cache"
        if cache_dir.is_dir():
            for cached_result in cache_dir.glob("*.json"):
                cached_result.unlink()
        transcript = _Transcript(transcript_path)
        prompt: Prompt = build_prompt(task_dir, condition)
        row["prompt_hash"] = prompt_hash(prompt)
        transcript.write(
            {
                "type": "prompt",
                "system": prompt.system,
                "user": prompt.user,
                "rendered": prompt.rendered,
                "prompt_hash": row["prompt_hash"],
            }
        )

        state = EpisodeState.load(task_dir, workdir=episode_dir, seed=trial)
        tools = state.make_tools()
        backend = _backend(model_id)
        if isinstance(backend, CodexBackend):
            backend_result = backend.run(
                prompt,
                condition,
                task_dir,
                tools,
                transcript.write,
                max_turns,
                episode_dir=episode_dir,
                state=state,
            )
        else:
            backend_result = backend.run(
                prompt, condition, task_dir, tools, transcript.write, max_turns
            )

        if condition == "single_shot" and not state.submitted:
            rtl = _final_verilog(backend_result.final_text)
            if rtl is None:
                backend_result.error = backend_result.error or (
                    "single-shot response contained no parsable Verilog code block"
                )
            else:
                state.record_submission(rtl)
                transcript.write({"type": "parsed_submission", "rtl": rtl})
        elif condition == "agentic" and not state.submitted:
            backend_result.error = backend_result.error or "episode ended without submit"

        row.update(
            {
                "turns": backend_result.turns,
                "tool_calls": backend_result.tool_calls,
                "tokens_in": backend_result.tokens_in,
                "tokens_out": backend_result.tokens_out,
                "latency_ms_per_call": (
                    backend_result.call_latencies_ms
                    + backend_result.tool_latencies_ms
                    + list(state.latency.latency_ms_per_call)
                ),
                "cache_hits": backend_result.cache_hits + state.latency.cache_hits,
                "protocol_ok": not getattr(backend_result, "protocol_violations", []),
                "protocol_violations": list(
                    getattr(backend_result, "protocol_violations", [])
                ),
                "cost_usd": calculate_cost(
                    model_id, backend_result.tokens_in, backend_result.tokens_out
                ),
                "error": backend_result.error,
            }
        )
        if state.submitted and state.submission_path is not None:
            try:
                graded = grade(
                    task_dir,
                    state.submission_path,
                    seed=trial,
                    tools=tools_dir,
                )
                _apply_grading(row, graded)
                transcript.write({"type": "grade", "result": graded})
            except Exception as error:
                row["error"] = row["error"] or f"grading failed: {type(error).__name__}: {error}"
                transcript.write({"type": "grade_error", "error": row["error"]})
    except Exception as error:
        row["error"] = f"{type(error).__name__}: {error}"
        if transcript is None:
            transcript = _Transcript(transcript_path)
        transcript.write({"type": "episode_error", "error": row["error"]})
    finally:
        if transcript is not None:
            transcript.close()
    row["first_failure_stage"] = _first_failure_stage(
        submitted=bool(state and state.submitted),
        graded=graded,
        backend_result=backend_result,
    )
    return row
