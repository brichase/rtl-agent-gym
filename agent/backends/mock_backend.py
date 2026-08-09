"""Scripted keyless backend used by integration tests."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
from pathlib import Path
from typing import Any

from . import BackendResult
from ..prompts import Prompt


TranscriptWriter = Callable[[dict[str, Any]], None]


class MockBackend:
    def __init__(self, fixture_path: str | Path | None = None) -> None:
        configured = fixture_path or os.environ.get("RTL_GYM_MOCK_FIXTURE")
        if configured is None:
            raise ValueError("mock backend requires RTL_GYM_MOCK_FIXTURE")
        self.fixture_path = Path(configured).resolve()

    def _actions(self, condition: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        metadata: dict[str, Any] = {}
        if isinstance(payload, dict):
            metadata = payload
            payload = payload.get(condition, payload.get("actions"))
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise ValueError(f"mock fixture must contain a list of actions: {self.fixture_path}")
        return payload, metadata

    @staticmethod
    def _rtl(action: dict[str, Any], task_dir: Path) -> str:
        if "rtl" in action:
            return str(action["rtl"])
        if "rtl_file" in action:
            path = Path(str(action["rtl_file"]))
            if not path.is_absolute():
                path = task_dir / path
            return path.read_text(encoding="utf-8")
        arguments = action.get("arguments", {})
        if isinstance(arguments, dict) and "rtl" in arguments:
            return str(arguments["rtl"])
        raise ValueError("mock tool action requires rtl or rtl_file")

    def run(
        self,
        prompt: Prompt,
        condition: str,
        task_dir: Path,
        tools: Any,
        transcript: TranscriptWriter,
        max_turns: int,
    ) -> BackendResult:
        del prompt
        result = BackendResult()
        actions, metadata = self._actions(condition)
        result.tokens_in = int(metadata.get("tokens_in", 0))
        result.tokens_out = int(metadata.get("tokens_out", 0))
        for action in actions[: (1 if condition == "single_shot" else max_turns)]:
            result.turns += 1
            action_type = action.get("type")
            transcript({"type": "mock_action", "action": action})
            if action_type in {"message", "final"}:
                if "verilog_file" in action:
                    source_path = Path(str(action["verilog_file"]))
                    if not source_path.is_absolute():
                        source_path = task_dir / source_path
                    source = source_path.read_text(encoding="utf-8")
                    result.final_text = f"```verilog\n{source.rstrip()}\n```"
                else:
                    result.final_text = str(action.get("content", action.get("text", "")))
            elif action_type == "tool_call":
                if condition != "agentic":
                    result.error = "single-shot mock attempted a tool call"
                    break
                name = str(action.get("name"))
                if name not in {"run_sim", "run_synth", "submit"}:
                    result.error = f"unknown mock tool: {name}"
                    break
                rtl = self._rtl(action, task_dir)
                result.tool_calls += 1
                try:
                    tool_result = getattr(tools, name)(rtl)
                    transcript(
                        {
                            "type": "tool_result",
                            "name": name,
                            "arguments": {"rtl": rtl},
                            "result": tool_result,
                        }
                    )
                except Exception as error:  # exercise backend failure rows without raising
                    result.error = f"{type(error).__name__}: {error}"
                    transcript({"type": "tool_error", "name": name, "error": result.error})
                    break
                if name == "submit":
                    break
            else:
                result.error = f"unknown mock action type: {action_type}"
                break
        return result
