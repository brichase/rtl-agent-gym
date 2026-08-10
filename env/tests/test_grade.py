from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

from env import sandbox
from env.grade import grade, load_task, run_testbench, static_sanity
from env.runner import EpisodeState


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "toy_adder"
ROOT = Path(__file__).resolve().parents[2]


class GradeLadderTests(unittest.TestCase):
    def test_reference_reaches_full_reward(self) -> None:
        result = grade(FIXTURE, FIXTURE / "ref" / "ref.v", seed=11)
        self.assertGreaterEqual(result["reward"], 0.95)
        for gate in ("compile_ok", "visible_pass", "hidden_pass", "oracle_pass", "sanity_ok"):
            self.assertTrue(result[gate], gate)
        self.assertEqual(result["area_norm"], 1.0)
        self.assertEqual(result["depth_norm"], 1.0)
        self.assertEqual(result["first_failure_stage"], "none")

    def test_stub_stops_at_visible_gate(self) -> None:
        result = grade(FIXTURE, FIXTURE / "broken" / "stub.v")
        self.assertEqual(result["reward"], 0.1)
        self.assertTrue(result["compile_ok"])
        self.assertFalse(result["visible_pass"])
        self.assertFalse(result["flagged"])
        self.assertEqual(result["first_failure_stage"], "visible_sim")

    def test_off_by_one_stops_at_hidden_gate(self) -> None:
        result = grade(FIXTURE, FIXTURE / "broken" / "off_by_one.v")
        self.assertEqual(result["reward"], 0.2)
        self.assertTrue(result["visible_pass"])
        self.assertFalse(result["hidden_pass"])
        self.assertFalse(result["flagged"])
        self.assertEqual(result["first_failure_stage"], "hidden_sim")

    def test_zero_time_loop_is_killed(self) -> None:
        result = grade(FIXTURE, FIXTURE / "broken" / "infinite_loop.v")
        self.assertLessEqual(result["reward"], 0.1)
        self.assertIn("timeout", result["fail_reason"])
        self.assertIn("[TIMEOUT]", result["stage_logs"].get("visible", ""))

    def test_initial_output_drive_is_rejected_without_false_positive(self) -> None:
        bad = "module add4(input a, output reg sum); initial sum = 1; endmodule"
        harmless = (
            'module add4(input a, output sum); initial $display("sum.ready"); '
            "assign sum = a; endmodule"
        )
        self.assertFalse(static_sanity(bad)[0])
        self.assertTrue(static_sanity(harmless)[0])

    def test_episode_tools_cache_and_record_submission(self) -> None:
        rtl = (FIXTURE / "ref" / "ref.v").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temporary:
            state = EpisodeState.load(FIXTURE, workdir=temporary, seed=7)
            episode_tools = state.make_tools()
            first = episode_tools.run_sim(rtl)
            second = episode_tools.run_sim(rtl)
            submitted = episode_tools.submit(rtl)
            self.assertTrue(first["passed"])
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(first["content_sha256"], second["content_sha256"])
            self.assertTrue(submitted["accepted"])
            self.assertEqual(state.submission_path.read_text(encoding="utf-8"), rtl)

    def test_sandbox_caps_output(self) -> None:
        result = sandbox.run_command(
            [sys.executable, "-c", "print('x' * 70000)"], {}, timeout_s=2
        )
        self.assertTrue(result.ok)
        self.assertLessEqual(len(result.stdout.encode("utf-8")), sandbox.OUTPUT_LIMIT)
        self.assertIn("[truncated]", result.stdout)
        self.assertTrue(result.truncated)

    def test_output_flood_fails_truncated_tb_gates(self) -> None:
        flood = ROOT / "redteam" / "06_output_flood" / "submission.v"
        result = grade(ROOT / "tasks" / "gray_counter", flood)
        self.assertFalse(result["visible_pass"])
        self.assertFalse(result["hidden_pass"])
        self.assertFalse(result["oracle_pass"])
        self.assertLessEqual(result["reward"], 0.2)
        self.assertTrue(result["flagged"])
        self.assertIn("visible testbench output truncated", result["fail_reason"])
        self.assertIn("hidden testbench output truncated", result["fail_reason"])

        reference = FIXTURE / "ref" / "ref.v"
        rtl = reference.read_text(encoding="utf-8")
        normal = grade(FIXTURE, reference)
        self.assertGreaterEqual(normal["reward"], 0.95)
        task = load_task(FIXTURE)
        for testbench in (FIXTURE / "tb_visible.v", FIXTURE / "tb_hidden.v"):
            self.assertFalse(run_testbench(task, rtl, testbench)["truncated"])


if __name__ == "__main__":
    unittest.main()
