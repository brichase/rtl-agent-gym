"""Backend result types shared by the episode driver."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BackendResult:
    final_text: str = ""
    turns: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    call_latencies_ms: list[float] = field(default_factory=list)
    tool_latencies_ms: list[float] = field(default_factory=list)
    cache_hits: int = 0
    error: str | None = None
