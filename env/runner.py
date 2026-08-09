"""Episode state plumbing; model-driving code intentionally lives elsewhere."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import tempfile
from typing import Any

import yaml

from .latency import LatencyCache


@dataclass
class EpisodeState:
    task_dir: Path
    workdir: Path
    task: dict[str, Any]
    seed: int = 0
    submitted: bool = False
    submission_path: Path | None = None
    latency: LatencyCache = field(init=False)

    def __post_init__(self) -> None:
        self.task_dir = self.task_dir.resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.latency = LatencyCache(self.workdir / "cache")

    @classmethod
    def load(
        cls,
        task_dir: str | Path,
        *,
        workdir: str | Path | None = None,
        seed: int = 0,
    ) -> "EpisodeState":
        task_path = Path(task_dir).resolve()
        metadata_path = task_path / "task.yaml"
        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid task metadata: {metadata_path}")
        episode_dir = (
            Path(workdir).resolve()
            if workdir is not None
            else Path(tempfile.mkdtemp(prefix=f"rtl-gym-{metadata.get('name', 'task')}-"))
        )
        return cls(task_path, episode_dir, metadata, seed=seed)

    def record_submission(self, rtl: str) -> Path:
        if self.submitted:
            raise RuntimeError("episode already has a final submission")
        path = self.workdir / "submission.v"
        path.write_text(rtl, encoding="utf-8")
        self.submission_path = path
        self.submitted = True
        return path

    def make_tools(self) -> "Tools":
        from .tools import Tools

        return Tools(self)


class Runner:
    """Clean seam consumed by the later agent loop."""

    def __init__(self, state: EpisodeState) -> None:
        self.state = state
        self.tools = state.make_tools()
