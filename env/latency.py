"""Timing and content-addressed caching for episode tool calls."""

from __future__ import annotations

from collections.abc import Callable
import copy
import hashlib
import json
from pathlib import Path
import time
from typing import Any


class LatencyCache:
    """Route calls through an in-memory and optional episode-local disk cache."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir
        self._memory: dict[tuple[str, str], dict[str, Any]] = {}
        self.latency_ms_per_call: list[float] = []
        self.cache_hits = 0
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _disk_path(self, operation: str, digest: str) -> Path | None:
        if self.cache_dir is None:
            return None
        safe_operation = "".join(c for c in operation if c.isalnum() or c in "-_")
        return self.cache_dir / f"{safe_operation}-{digest}.json"

    def call(
        self,
        operation: str,
        content: str,
        function: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        started = time.monotonic()
        digest = self.content_hash(content)
        key = (operation, digest)
        cached = self._memory.get(key)
        disk_path = self._disk_path(operation, digest)
        if cached is None and disk_path is not None and disk_path.is_file():
            try:
                loaded = json.loads(disk_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    cached = loaded
                    self._memory[key] = loaded
            except (OSError, json.JSONDecodeError):
                cached = None

        cache_hit = cached is not None
        if cache_hit:
            self.cache_hits += 1
            result = copy.deepcopy(cached)
        else:
            result = function()
            self._memory[key] = copy.deepcopy(result)
            if disk_path is not None:
                disk_path.write_text(
                    json.dumps(result, sort_keys=True, separators=(",", ":")),
                    encoding="utf-8",
                )

        elapsed_ms = (time.monotonic() - started) * 1000.0
        self.latency_ms_per_call.append(elapsed_ms)
        result["latency_ms"] = round(elapsed_ms, 3)
        result["cache_hit"] = cache_hit
        result["content_sha256"] = digest
        return result
