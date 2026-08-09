"""Deterministic prompt construction shared by every backend."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path


SYSTEM_PROMPT = """You are an expert RTL design engineer. Implement the requested module in synthesizable Verilog-2005. Follow the specification and module interface exactly. Do not modify the port list or top-module name."""

AGENTIC_PROTOCOL = """

## Tool protocol

Use `run_sim` to compile and run the visible testbench, `run_synth` to inspect synthesis cost, and `submit` exactly once with your final complete Verilog source. Tool arguments must contain the full RTL in the `rtl` field. The episode ends when you call `submit`; do not merely print the final RTL.
"""

SINGLE_SHOT_PROTOCOL = """

## Output protocol

Output the final complete Verilog in one ```verilog code block. Do not use tools.
"""


@dataclass(frozen=True)
class Prompt:
    """The system/user pair plus its canonical rendering."""

    system: str
    user: str

    @property
    def rendered(self) -> str:
        return f"<system>\n{self.system}\n</system>\n<user>\n{self.user}\n</user>\n"


def build_prompt(task_dir: str | Path, condition: str) -> Prompt:
    """Build a stable prompt from prompt-facing task files only."""
    if condition not in {"single_shot", "agentic"}:
        raise ValueError(f"unknown condition: {condition}")
    task_path = Path(task_dir)
    spec = (task_path / "spec.md").read_text(encoding="utf-8").rstrip()
    interface = (task_path / "interface.v").read_text(encoding="utf-8").rstrip()
    task_content = (
        "## Task specification\n\n"
        f"{spec}\n\n"
        "## Required interface\n\n"
        "```verilog\n"
        f"{interface}\n"
        "```"
    )
    suffix = AGENTIC_PROTOCOL if condition == "agentic" else SINGLE_SHOT_PROTOCOL
    return Prompt(system=SYSTEM_PROMPT, user=task_content + suffix)


def prompt_hash(prompt: Prompt | str | Path, condition: str | None = None) -> str:
    """Return SHA-256 for a prompt, rendered string, or task/condition pair."""
    if condition is not None:
        rendered = build_prompt(Path(prompt), condition).rendered
    else:
        rendered = prompt.rendered if isinstance(prompt, Prompt) else str(prompt)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
