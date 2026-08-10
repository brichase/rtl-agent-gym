"""Codex CLI backend using an episode-local stdio MCP server."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
from typing import Any

from . import BackendResult
from ..prompts import Prompt


TranscriptWriter = Callable[[dict[str, Any]], None]
PYTHON = "/data/projects/rtl-agent-gym/venv/bin/python"
APPROVED_TOOLS = frozenset({"run_sim", "run_synth", "submit"})
ACTION_ITEM_TYPES = frozenset(
    {
        "command_execution",
        "dynamic_tool_call",
        "file_change",
        "file_read",
        "image_view",
        "web_search",
    }
)


@dataclass
class CodexBackendResult(BackendResult):
    protocol_violations: list[str] = field(default_factory=list)
    tool_argument_errors: list[str] = field(default_factory=list)
    tool_execution_errors: list[str] = field(default_factory=list)


def _toml_string(value: str) -> str:
    return json.dumps(value)


class CodexBackend:
    def __init__(
        self,
        model_id: str,
        *,
        effort: str | None = None,
        wall_timeout_s: float | None = None,
        codex_command: str = "codex",
        codex_home: Path | None = None,
    ) -> None:
        self.model_id = model_id
        self.effort = effort or os.environ.get("RTL_GYM_CODEX_EFFORT", "max")
        self.wall_timeout_s = wall_timeout_s or float(
            os.environ.get("RTL_GYM_EPISODE_TIMEOUT_S", "900")
        )
        self.codex_command = codex_command
        self.codex_home = codex_home
        self.repo_root = Path(__file__).resolve().parents[2]

    def command(
        self,
        prompt: Prompt,
        condition: str,
        task_dir: Path,
        episode_dir: Path,
        max_tool_calls: int,
    ) -> list[str]:
        command = [
            self.codex_command,
            "exec",
            "--json",
            "--ephemeral",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "-c",
            f"model_reasoning_effort={_toml_string(self.effort)}",
        ]
        if self.model_id:
            command[7:7] = ["-m", self.model_id]
        if condition == "agentic":
            tools_dir = os.environ.get(
                "RTL_GYM_TOOLS",
                "/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin",
            )
            configs = (
                # codex exec auto-cancels MCP approval elicitations (exec/src/lib.rs,
                # rust-v0.147.0); per-server approve mode is the only unattended path.
                ("mcp_servers.rtlgym.default_tools_approval_mode", "approve"),
                ("mcp_servers.rtlgym.command", PYTHON),
                ("mcp_servers.rtlgym.args", '["-m","agent.mcp_server"]'),
                ("mcp_servers.rtlgym.env.RTL_GYM_TASK_DIR", str(task_dir.resolve())),
                ("mcp_servers.rtlgym.env.RTL_GYM_EPISODE_DIR", str(episode_dir.resolve())),
                ("mcp_servers.rtlgym.env.RTL_GYM_TOOLS", tools_dir),
                ("mcp_servers.rtlgym.env.RTL_GYM_MAX_TOOL_CALLS", str(max_tool_calls)),
                ("mcp_servers.rtlgym.env.PYTHONPATH", str(self.repo_root)),
            )
            for key, value in configs:
                command.extend(["-c", f"{key}={value if key.endswith('.args') else _toml_string(value)}"])
        command.append(prompt.rendered)
        return command

    @staticmethod
    def _short(value: Any, limit: int = 120) -> str:
        rendered = " ".join(str(value).split())
        return rendered if len(rendered) <= limit else rendered[: limit - 3] + "..."

    @classmethod
    def _inspect_item(
        cls,
        item: dict[str, Any],
        result: CodexBackendResult,
        seen_actions: set[str],
        seen_tool_errors: set[str],
    ) -> None:
        """Classify Codex JSONL actions without treating them as episode failures."""
        item_type = str(item.get("type", ""))
        identity = str(item.get("id", f"{item_type}:{len(seen_actions)}"))

        if item_type == "mcp_tool_call":
            server = item.get("server", item.get("server_name"))
            tool = str(item.get("tool", item.get("name", "")))
            if server != "rtlgym" or tool not in APPROVED_TOOLS:
                action_key = f"mcp:{identity}"
                if action_key not in seen_actions:
                    seen_actions.add(action_key)
                    result.protocol_violations.append(
                        f"unapproved MCP tool: {server or '<unknown>'}/{tool or '<unknown>'}"
                    )
                return

            arguments = item.get("arguments")
            argument_key = f"argument:{identity}"
            if (
                not isinstance(arguments, dict)
                or not isinstance(arguments.get("rtl"), str)
            ) and argument_key not in seen_tool_errors:
                seen_tool_errors.add(argument_key)
                result.tool_argument_errors.append(f"{tool}: invalid rtl argument")

            if item.get("status") not in {"completed", "failed"}:
                return
            execution_error = item.get("error")
            payload = item.get("result")
            if isinstance(payload, dict):
                structured = payload.get("structured_content", payload.get("structuredContent"))
                if payload.get("isError") is True or payload.get("is_error") is True:
                    execution_error = execution_error or "tool returned isError"
                if isinstance(structured, dict) and "error" in structured:
                    execution_error = execution_error or structured["error"]
            execution_key = f"execution:{identity}"
            if execution_error and execution_key not in seen_tool_errors:
                seen_tool_errors.add(execution_key)
                result.tool_execution_errors.append(
                    f"{tool}: {cls._short(execution_error)}"
                )
            return

        is_action = item_type in ACTION_ITEM_TYPES or (
            item_type.endswith("_tool_call") and item_type != "mcp_tool_call"
        )
        action_key = f"action:{identity}"
        if not is_action or action_key in seen_actions:
            return
        seen_actions.add(action_key)
        detail = item.get("command", item.get("path", item.get("name", "")))
        suffix = f": {cls._short(detail)}" if detail else ""
        result.protocol_violations.append(f"{item_type}{suffix}")

    @staticmethod
    def _message_text(event: dict[str, Any]) -> str | None:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            return None
        text = item.get("text", item.get("content"))
        if isinstance(text, str):
            return text
        if isinstance(text, list):
            parts = [
                str(block.get("text", ""))
                for block in text
                if isinstance(block, dict) and block.get("type") in {"text", "output_text"}
            ]
            return "\n".join(parts)
        return None

    @staticmethod
    def _load_mcp_metrics(
        episode_dir: Path,
        result: BackendResult,
        transcript: TranscriptWriter,
    ) -> None:
        state_path = episode_dir / "mcp_state.json"
        if state_path.is_file():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                result.tool_calls = int(state.get("tool_calls", result.tool_calls))
            except (OSError, ValueError, TypeError):
                pass
        log_path = episode_dir / "tool_log.jsonl"
        if not log_path.is_file():
            return
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            transcript({"type": "mcp_tool_log", "backend": "codex", "entry": item})
            latency = item.get("latency_ms")
            if isinstance(latency, (int, float)):
                result.tool_latencies_ms.append(float(latency))
            payload = item.get("result")
            if isinstance(payload, dict) and payload.get("cache_hit") is True:
                result.cache_hits += 1

    def run(
        self,
        prompt: Prompt,
        condition: str,
        task_dir: Path,
        tools: Any,
        transcript: TranscriptWriter,
        max_turns: int,
        *,
        episode_dir: Path,
        state: Any,
    ) -> BackendResult:
        del tools
        result = CodexBackendResult()
        command = self.command(prompt, condition, task_dir, episode_dir, max_turns)
        agent_cwd = episode_dir / "agent_cwd"
        if agent_cwd.exists():
            shutil.rmtree(agent_cwd)
        agent_cwd.mkdir(parents=True)
        transcript(
            {
                "type": "process_start",
                "backend": "codex",
                "argv": command[:-1] + ["<prompt>"],
                "cwd": str(agent_cwd),
            }
        )
        started = time.monotonic()
        process_env = os.environ.copy()
        if self.codex_home is not None:
            process_env["CODEX_HOME"] = str(self.codex_home.resolve())
        try:
            process = subprocess.Popen(
                command,
                cwd=agent_cwd,
                env=process_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
            try:
                stdout, stderr = process.communicate(timeout=self.wall_timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                stdout, stderr = process.communicate()
                result.error = f"codex episode timed out after {self.wall_timeout_s:g}s"
        except Exception as error:
            result.error = f"{type(error).__name__}: {error}"
            transcript({"type": "process_error", "backend": "codex", "error": result.error})
            return result

        result.call_latencies_ms.append(round((time.monotonic() - started) * 1000, 3))
        last_usage: tuple[int, int] | None = None
        mcp_call_ids: set[str] = set()
        seen_actions: set[str] = set()
        seen_tool_errors: set[str] = set()
        for raw_line in stdout.splitlines():
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                transcript({"type": "codex_stdout", "raw": raw_line})
                continue
            transcript({"type": "codex_event", "event": event})
            if event.get("type") == "turn.completed":
                result.turns += 1
                usage = event.get("usage", {})
                if isinstance(usage, dict):
                    last_usage = (
                        int(usage.get("input_tokens", 0) or 0),
                        int(usage.get("output_tokens", 0) or 0),
                    )
            elif event.get("type") == "turn.failed" and result.error is None:
                failure = event.get("error", {})
                message = failure.get("message") if isinstance(failure, dict) else failure
                result.error = f"codex turn failed: {message}"
            item = event.get("item")
            if isinstance(item, dict):
                self._inspect_item(item, result, seen_actions, seen_tool_errors)
                if item.get("type") == "mcp_tool_call":
                    server = item.get("server", item.get("server_name"))
                    tool = item.get("tool", item.get("name"))
                    if server == "rtlgym" and tool in APPROVED_TOOLS:
                        identity = str(item.get("id", len(mcp_call_ids)))
                        mcp_call_ids.add(identity)
            text = self._message_text(event)
            if text is not None:
                result.final_text = text
        if last_usage is not None:
            result.tokens_in, result.tokens_out = last_usage
        result.tool_calls = len(mcp_call_ids)
        if result.turns == 0 and stdout:
            result.turns = 1
        if stderr:
            transcript({"type": "codex_stderr", "text": stderr})
        if process.returncode != 0 and result.error is None:
            detail = stderr.strip().splitlines()[-1] if stderr.strip() else "no stderr"
            result.error = f"codex exec exited {process.returncode}: {detail}"

        self._load_mcp_metrics(episode_dir, result, transcript)
        submission_path = episode_dir / "submission.v"
        if submission_path.is_file() and not state.submitted:
            try:
                state.record_submission(submission_path.read_text(encoding="utf-8"))
            except Exception as error:
                result.error = result.error or f"failed to import MCP submission: {error}"
        return result
