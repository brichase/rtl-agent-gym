from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from agent.backends import BackendResult
from agent.leakage_check import UNREADABLE_MARKER, run_check


class ProbeBackend:
    """Compliant backend: shell_tool is disabled, so it executes no command and the
    canary never surfaces."""

    emit_shell = False

    def run(
        self,
        prompt: object,
        condition: str,
        task_dir: Path,
        tools: object,
        transcript: object,
        max_turns: int,
        *,
        episode_dir: Path,
        state: object,
    ) -> BackendResult:
        del prompt, condition, tools, max_turns, state
        canaries = list((task_dir / "ref").glob("HIDDEN_CANARY_*.txt"))
        if len(canaries) != 1:
            raise AssertionError("preflight did not plant exactly one canary")
        agent_cwd = episode_dir / "agent_cwd"
        agent_cwd.mkdir(parents=True)
        if list(agent_cwd.iterdir()):
            raise AssertionError("agent cwd was not empty")
        if self.emit_shell:
            transcript(
                {
                    "type": "codex_event",
                    "event": {
                        "type": "item.completed",
                        "item": {"id": "probe", "type": "command_execution"},
                    },
                }
            )
        return BackendResult(
            final_text=f"No shell available; nothing to read. {UNREADABLE_MARKER}",
            turns=1,
        )


class ShellRegressionBackend(ProbeBackend):
    """Simulates a regression where shell_tool got re-enabled."""

    emit_shell = True


class LeakageCheckTests(unittest.TestCase):
    def test_canary_is_not_exposed_and_is_always_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "tasks" / "probe"
            (task_dir / "ref").mkdir(parents=True)
            (task_dir / "task.yaml").write_text(
                "name: probe\ntop_module: probe\n", encoding="utf-8"
            )
            message = run_check(repo_root=root, backend=ProbeBackend())
            self.assertIn("canary unreadable", message)
            self.assertEqual([], list((task_dir / "ref").glob("HIDDEN_CANARY_*.txt")))

    def test_shell_execution_is_flagged_as_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "tasks" / "probe"
            (task_dir / "ref").mkdir(parents=True)
            (task_dir / "task.yaml").write_text(
                "name: probe\ntop_module: probe\n", encoding="utf-8"
            )
            with self.assertRaises(RuntimeError):
                run_check(repo_root=root, backend=ShellRegressionBackend())
            # canary is still cleaned up even on the failure path
            self.assertEqual([], list((task_dir / "ref").glob("HIDDEN_CANARY_*.txt")))


if __name__ == "__main__":
    unittest.main()
