"""Episode-scoped, cached agent tools."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from .grade import compile_rtl, load_task, run_testbench, synthesize_rtl

if TYPE_CHECKING:
    from .runner import EpisodeState


class Tools:
    """The three functions exposed to a model-driving loop."""

    def __init__(self, state: "EpisodeState") -> None:
        self.state = state
        self.task = load_task(state.task_dir)

    def run_sim(self, rtl: str) -> dict[str, Any]:
        def invoke() -> dict[str, Any]:
            compiled = compile_rtl(self.task, rtl)
            if not compiled["ok"]:
                return {
                    "compile_ok": False,
                    "stdout": compiled["stdout"],
                    "passed": False,
                }
            simulated = run_testbench(
                self.task, rtl, self.task.path / "tb_visible.v"
            )
            return {
                # The dedicated compile gate above succeeded; a later simulator
                # timeout must not erase that fact.
                "compile_ok": True,
                "stdout": simulated["stdout"],
                "passed": simulated["passed"],
            }

        return self.state.latency.call("run_sim", rtl, invoke)

    def run_synth(self, rtl: str) -> dict[str, Any]:
        def invoke() -> dict[str, Any]:
            synthesized = synthesize_rtl(self.task, rtl)
            return {
                "ok": synthesized["ok"],
                "cells": synthesized["cells"],
                "depth": synthesized["depth"],
                "stdout": synthesized["stdout"],
            }

        return self.state.latency.call("run_synth", rtl, invoke)

    def submit(self, rtl: str) -> dict[str, Any]:
        if not self.state.submitted:
            self.state.record_submission(rtl)
        elif self.state.submission_path is None or self.state.submission_path.read_text(
            encoding="utf-8"
        ) != rtl:
            raise RuntimeError("episode already has a different final submission")

        def invoke() -> dict[str, Any]:
            return {"accepted": True}

        return self.state.latency.call("submit", rtl, invoke)
