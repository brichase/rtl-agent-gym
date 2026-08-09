"""Minimal one-episode MCP stdio server for Codex RTL tools.

The transport is newline-delimited JSON-RPC 2.0.  Protocol output is written only
to stdout; diagnostics, if any, go to stderr.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from env.runner import EpisodeState


TOOL_DESCRIPTIONS = {
    "run_sim": "Compile the supplied RTL and run the visible testbench.",
    "run_synth": "Synthesize the supplied RTL and report cells and logic depth.",
    "submit": "Record the supplied RTL as final and end the episode.",
}


class EpisodeMCPServer:
    def __init__(self) -> None:
        task_dir = Path(self._required_env("RTL_GYM_TASK_DIR")).resolve()
        self.episode_dir = Path(self._required_env("RTL_GYM_EPISODE_DIR")).resolve()
        self.episode_dir.mkdir(parents=True, exist_ok=True)
        self.max_tool_calls = int(os.environ.get("RTL_GYM_MAX_TOOL_CALLS", "10"))
        if self.max_tool_calls < 0:
            raise ValueError("RTL_GYM_MAX_TOOL_CALLS must be nonnegative")
        self.state = EpisodeState.load(task_dir, workdir=self.episode_dir)
        self.tools = self.state.make_tools()
        self.tool_calls = 0
        self.state_path = self.episode_dir / "mcp_state.json"
        self.log_path = self.episode_dir / "tool_log.jsonl"
        self._write_state()

    @staticmethod
    def _required_env(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"missing required environment variable {name}")
        return value

    def _write_state(self) -> None:
        payload = {
            "tool_calls": self.tool_calls,
            "max_tool_calls": self.max_tool_calls,
            "submitted": self.state.submitted,
            "submission_path": str(self.state.submission_path) if self.state.submission_path else None,
        }
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.state_path)

    def _log_call(
        self,
        name: str,
        arguments: dict[str, Any],
        result: Any,
        latency_ms: float,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "call_index": self.tool_calls,
            "name": name,
            "arguments": arguments,
            "result": result,
            "latency_ms": round(latency_ms, 3),
        }
        with self.log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")

    @staticmethod
    def tool_list() -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "rtl": {"type": "string", "description": "Complete Verilog source"}
                    },
                    "required": ["rtl"],
                    "additionalProperties": False,
                },
            }
            for name, description in TOOL_DESCRIPTIONS.items()
        ]

    def call_tool(self, name: str, arguments: Any) -> dict[str, Any]:
        if name not in TOOL_DESCRIPTIONS:
            raise ValueError(f"unknown tool: {name}")
        if not isinstance(arguments, dict) or not isinstance(arguments.get("rtl"), str):
            raise ValueError("tool arguments require string field 'rtl'")
        self.tool_calls += 1
        started = time.monotonic()
        if name in {"run_sim", "run_synth"} and self.tool_calls > self.max_tool_calls:
            payload: Any = "budget exhausted — submit now"
        else:
            try:
                payload = getattr(self.tools, name)(arguments["rtl"])
            except Exception as error:
                payload = {"error": f"{type(error).__name__}: {error}"}
        latency_ms = (time.monotonic() - started) * 1000
        self._log_call(name, arguments, payload, latency_ms)
        self._write_state()
        text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)
        response: dict[str, Any] = {
            "content": [{"type": "text", "text": text}],
            "isError": isinstance(payload, dict) and "error" in payload,
        }
        if isinstance(payload, dict):
            response["structuredContent"] = payload
        return response

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any] | None:
        request_id = request.get("id")
        method = request.get("method")
        if method == "notifications/initialized" or request_id is None:
            return None
        if method == "initialize":
            params = request.get("params", {})
            requested = params.get("protocolVersion") if isinstance(params, dict) else None
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": requested or "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "rtlgym", "version": "1.0.0"},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self.tool_list()},
            }
        if method == "tools/call":
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise ValueError("tools/call params must be an object")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": self.call_tool(str(params.get("name", "")), params.get("arguments", {})),
            }
        raise ValueError(f"method not found: {method}")


def _error_response(request_id: Any, error: Exception) -> dict[str, Any]:
    code = -32601 if str(error).startswith("method not found") else -32602
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": str(error)},
    }


def main() -> int:
    try:
        server = EpisodeMCPServer()
    except Exception as error:
        print(f"rtlgym MCP startup failed: {error}", file=sys.stderr, flush=True)
        return 1
    for line in sys.stdin:
        request_id: Any = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            request_id = request.get("id")
            response = server.dispatch(request)
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            response = _error_response(request_id, error)
        except Exception as error:  # keep one malformed/tool failure from killing the server
            response = _error_response(request_id, error)
        if response is not None:
            print(json.dumps(response, separators=(",", ":"), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
