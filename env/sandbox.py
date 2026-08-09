"""Small, dependency-free subprocess sandbox used by the grader.

This is deliberately sandbox-lite: it isolates files, bounds wall-clock time, and
bounds captured output.  It is not a process jail and must not be presented as one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import threading
import time


DEFAULT_TOOLS = Path("/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin")
OUTPUT_LIMIT = 64 * 1024
TRUNCATION_MARKER = b"\n[truncated]\n"


@dataclass(frozen=True)
class SandboxResult:
    returncode: int
    stdout: str
    timed_out: bool
    elapsed_ms: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def tools_dir(override: str | Path | None = None) -> Path:
    """Resolve the pinned OSS CAD Suite binaries without consulting PATH."""
    value = override or os.environ.get("RTL_GYM_TOOLS")
    return Path(value) if value else DEFAULT_TOOLS


def tool_path(name: str, override: str | Path | None = None) -> str:
    path = tools_dir(override) / name
    if not path.is_file():
        raise FileNotFoundError(f"required tool not found: {path}")
    return str(path)


def _safe_destination(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if root.resolve() not in candidate.parents:
        raise ValueError(f"staged path escapes sandbox: {relative}")
    return candidate


def _stage_files(root: Path, files: Mapping[str, str | bytes | Path]) -> None:
    for relative, source in files.items():
        destination = _safe_destination(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, Path):
            shutil.copyfile(source, destination)
        elif isinstance(source, bytes):
            destination.write_bytes(source)
        else:
            destination.write_text(source, encoding="utf-8")


def _run_one(
    command: Sequence[str],
    cwd: Path,
    timeout_s: float,
    environment: Mapping[str, str] | None,
) -> tuple[int, bytes, bool]:
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=dict(environment) if environment is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    captured = bytearray()
    truncated = False

    def drain() -> None:
        nonlocal truncated
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(8192)
            if not chunk:
                return
            remaining = OUTPUT_LIMIT - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    timed_out = False
    try:
        process.wait(timeout=max(timeout_s, 0.001))
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    reader.join(timeout=2.0)
    if process.stdout is not None:
        process.stdout.close()
    if truncated:
        if len(captured) + len(TRUNCATION_MARKER) > OUTPUT_LIMIT:
            del captured[OUTPUT_LIMIT - len(TRUNCATION_MARKER) :]
        captured.extend(TRUNCATION_MARKER)
    return process.returncode, bytes(captured), timed_out


def run_commands(
    commands: Sequence[Sequence[str]],
    files: Mapping[str, str | bytes | Path],
    *,
    timeout_s: float = 30.0,
    environment: Mapping[str, str] | None = None,
) -> SandboxResult:
    """Run commands sequentially in one fresh directory with one time budget."""
    started = time.monotonic()
    combined = bytearray()
    returncode = 0
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="rtl-gym-") as temporary:
        root = Path(temporary)
        _stage_files(root, files)
        for command in commands:
            remaining = timeout_s - (time.monotonic() - started)
            if remaining <= 0:
                returncode, timed_out = -signal.SIGKILL, True
                break
            returncode, output, command_timed_out = _run_one(
                command, root, remaining, environment
            )
            available = OUTPUT_LIMIT - len(combined)
            if available > 0:
                combined.extend(output[:available])
            if len(output) > available and not combined.endswith(TRUNCATION_MARKER):
                if len(combined) + len(TRUNCATION_MARKER) > OUTPUT_LIMIT:
                    del combined[OUTPUT_LIMIT - len(TRUNCATION_MARKER) :]
                combined.extend(TRUNCATION_MARKER)
            timed_out = timed_out or command_timed_out
            if returncode != 0 or timed_out:
                break
    if timed_out:
        timeout_note = b"\n[TIMEOUT]\n"
        available = OUTPUT_LIMIT - len(combined)
        combined.extend(timeout_note[:available])
    return SandboxResult(
        returncode=returncode,
        stdout=combined.decode("utf-8", errors="replace"),
        timed_out=timed_out,
        elapsed_ms=(time.monotonic() - started) * 1000.0,
    )


def run_command(
    command: Sequence[str],
    files: Mapping[str, str | bytes | Path],
    *,
    timeout_s: float = 30.0,
    environment: Mapping[str, str] | None = None,
) -> SandboxResult:
    return run_commands([command], files, timeout_s=timeout_s, environment=environment)
