"""Anthropic Messages API backend with native tool-use looping."""

from __future__ import annotations

from collections.abc import Callable
import json
import os
import time
from typing import Any

from . import BackendResult
from ..pricing import calculate_cost
from ..prompts import Prompt


TranscriptWriter = Callable[[dict[str, Any]], None]

TOOL_DEFINITIONS = [
    {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {"rtl": {"type": "string", "description": "Complete Verilog source"}},
            "required": ["rtl"],
            "additionalProperties": False,
        },
    }
    for name, description in (
        ("run_sim", "Compile the RTL and run the visible testbench."),
        ("run_synth", "Synthesize the RTL and report cells and logic depth."),
        ("submit", "Record the final RTL and end the episode."),
    )
]


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped
    result: dict[str, Any] = {}
    for field in ("type", "text", "id", "name", "input"):
        if hasattr(value, field):
            result[field] = getattr(value, field)
    return result


def _usage(response: Any, name: str) -> int:
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        return int(usage.get(name, 0) or 0)
    return int(getattr(usage, name, 0) or 0)


class AnthropicBackend:
    def __init__(
        self,
        model_id: str,
        *,
        client: Any | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.model_id = model_id
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client = client
        self.max_tokens = max_tokens or int(os.environ.get("RTL_GYM_MAX_TOKENS", "4096"))

    def run(
        self,
        prompt: Prompt,
        condition: str,
        task_dir: Any,
        tools: Any,
        transcript: TranscriptWriter,
        max_turns: int,
    ) -> BackendResult:
        del task_dir
        result = BackendResult()
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt.user}]
        limit = 1 if condition == "single_shot" else max_turns

        for _ in range(limit):
            request: dict[str, Any] = {
                "model": self.model_id,
                "max_tokens": self.max_tokens,
                "system": prompt.system,
                "messages": messages,
            }
            if condition == "agentic":
                request["tools"] = TOOL_DEFINITIONS
            transcript({"type": "model_request", "backend": "anthropic", "request": request})
            started = time.monotonic()
            try:
                response = self.client.messages.create(**request)
            except Exception as error:
                result.error = f"{type(error).__name__}: {error}"
                transcript({"type": "model_error", "backend": "anthropic", "error": result.error})
                break
            result.call_latencies_ms.append(round((time.monotonic() - started) * 1000, 3))
            result.turns += 1
            result.tokens_in += _usage(response, "input_tokens")
            result.tokens_out += _usage(response, "output_tokens")
            blocks = [_as_dict(block) for block in getattr(response, "content", [])]
            transcript({"type": "model_response", "backend": "anthropic", "content": blocks})
            messages.append({"role": "assistant", "content": blocks})

            text_parts = [str(block.get("text", "")) for block in blocks if block.get("type") == "text"]
            if text_parts:
                result.final_text = "\n".join(text_parts)
            tool_uses = [block for block in blocks if block.get("type") == "tool_use"]
            if condition == "single_shot" or not tool_uses:
                break

            tool_results: list[dict[str, Any]] = []
            submitted = False
            for block in tool_uses:
                name = str(block.get("name", ""))
                arguments = block.get("input", {})
                result.tool_calls += 1
                transcript(
                    {
                        "type": "tool_call",
                        "backend": "anthropic",
                        "id": block.get("id"),
                        "name": name,
                        "arguments": arguments,
                    }
                )
                is_error = False
                try:
                    if name not in {"run_sim", "run_synth", "submit"}:
                        raise ValueError(f"unknown tool: {name}")
                    if not isinstance(arguments, dict) or not isinstance(arguments.get("rtl"), str):
                        raise ValueError("tool input requires string field 'rtl'")
                    payload: Any = getattr(tools, name)(arguments["rtl"])
                except Exception as error:
                    is_error = True
                    payload = {"error": f"{type(error).__name__}: {error}"}
                transcript(
                    {
                        "type": "tool_result",
                        "backend": "anthropic",
                        "id": block.get("id"),
                        "name": name,
                        "result": payload,
                        "is_error": is_error,
                    }
                )
                tool_result: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": block.get("id"),
                    "content": json.dumps(payload, sort_keys=True),
                }
                if is_error:
                    tool_result["is_error"] = True
                tool_results.append(tool_result)
                if name == "submit" and not is_error:
                    submitted = True
                    break
            if submitted:
                break
            messages.append({"role": "user", "content": tool_results})

        return result

    @staticmethod
    def cost_usd(model_id: str, tokens_in: int, tokens_out: int) -> float | None:
        return calculate_cost(model_id, tokens_in, tokens_out)
