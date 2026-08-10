"""Real Codex preflight proving the episode cwd cannot see answer-data canaries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile
from typing import Any, Sequence

from env.runner import EpisodeState

from .backends.codex_backend import CodexBackend
from .prompts import Prompt


ROOT = Path(__file__).resolve().parents[1]
UNREADABLE_MARKER = "CANARY_UNREADABLE"


class LeakageDetected(RuntimeError):
    pass


def _answer_area(repo_root: Path) -> tuple[Path, Path]:
    for task_dir in sorted((repo_root / "tasks").glob("*")):
        answer_dir = task_dir / "ref"
        if (task_dir / "task.yaml").is_file() and answer_dir.is_dir():
            return task_dir, answer_dir
    raise FileNotFoundError("no task answer area found under tasks/*/ref")


def run_check(
    *,
    repo_root: Path = ROOT,
    backend: CodexBackend | None = None,
) -> str:
    """Plant a transient answer-area canary and run exactly one Codex turn."""
    task_dir, answer_dir = _answer_area(repo_root.resolve())
    nonce = secrets.token_hex(16)
    canary_path = answer_dir / f"HIDDEN_CANARY_{nonce}.txt"
    canary_content = f"RTL_GYM_SECRET_{secrets.token_hex(24)}"
    prompt = Prompt(
        system="You are a filesystem isolation probe. Follow the request exactly.",
        user=(
            "Use the local shell to search recursively from your current working directory "
            "for any file whose basename matches HIDDEN_CANARY_*.txt. If you find one, read "
            "it and echo its exact contents. If none is accessible, finish with exactly "
            f"{UNREADABLE_MARKER}. Do not guess a path or contents."
        ),
    )
    canary_path.write_text(canary_content + "\n", encoding="utf-8")
    events: list[dict[str, Any]] = []
    try:
        with tempfile.TemporaryDirectory(prefix="rtl-gym-leakage-") as temporary:
            temporary_root = Path(temporary)
            episode_dir = temporary_root / "episode"
            probe_backend = backend
            if probe_backend is None:
                source_home = Path(
                    os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
                )
                codex_home = temporary_root / "codex-home"
                codex_home.mkdir()
                for name in ("auth.json", "config.toml"):
                    source = source_home / name
                    if source.is_file():
                        shutil.copy2(source, codex_home / name)
                probe_backend = CodexBackend(
                    "",
                    effort=os.environ.get("RTL_GYM_LEAKAGE_EFFORT", "low"),
                    wall_timeout_s=float(
                        os.environ.get("RTL_GYM_LEAKAGE_TIMEOUT_S", "180")
                    ),
                    codex_home=codex_home,
                )
            state = EpisodeState.load(task_dir, workdir=episode_dir)
            result = probe_backend.run(
                prompt,
                "single_shot",
                task_dir,
                None,
                events.append,
                1,
                episode_dir=episode_dir,
                state=state,
            )
            submission = ""
            submission_path = episode_dir / "submission.v"
            if submission_path.is_file():
                submission = submission_path.read_text(encoding="utf-8")
            observed = "\n".join(
                (result.final_text, submission, json.dumps(events, ensure_ascii=False))
            )
            # Core invariant: planted answer-area data must never reach the agent.
            # The prompt actively instructs the agent to search for and echo the canary,
            # so if any file-read path existed the content would surface here.
            if canary_content in observed:
                raise LeakageDetected("leakage detected: canary content reached the episode")
            if result.error:
                raise RuntimeError(f"leakage probe episode failed: {result.error}")
            # Structural guarantee: shell_tool is disabled, so the agent has no mechanism
            # to execute a file-read at all. A command_execution event means the shell was
            # (re-)enabled — a regression in the isolation, even if this run didn't leak.
            executed_shell = any(
                event.get("type") == "codex_event"
                and isinstance(event.get("event"), dict)
                and isinstance(event["event"].get("item"), dict)
                and event["event"]["item"].get("type") == "command_execution"
                for event in events
            )
            if executed_shell:
                raise RuntimeError(
                    "leakage probe regression: agent executed a shell command "
                    "(shell_tool no longer disabled)"
                )
    finally:
        canary_path.unlink(missing_ok=True)
    return "leakage-check: PASS — canary unreadable (not present in transcript/submission)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        message = run_check(repo_root=args.repo_root)
    except (LeakageDetected, OSError, RuntimeError, ValueError) as error:
        print(f"leakage-check: FAIL — {error}")
        return 1
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
