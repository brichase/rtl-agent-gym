from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval import report


class ReportTest(unittest.TestCase):
    def _rows(self) -> list[dict[str, object]]:
        rewards = {
            ("small", "task_a", "single_shot"): [0.8, 0.2, 0.7],
            ("small", "task_a", "agentic"): [0.8, 0.9, 0.95],
            ("small", "task_b", "single_shot"): [0.2, 0.2, 0.2],
            ("small", "task_b", "agentic"): [0.2, 0.8, 0.2],
            ("large", "task_a", "single_shot"): [0.7, 0.8, 0.9],
            ("large", "task_a", "agentic"): [0.9, 0.9, 0.9],
            ("large", "task_b", "single_shot"): [0.2, 0.7, 0.2],
            ("large", "task_b", "agentic"): [0.8, 0.8, 0.8],
        }
        rows: list[dict[str, object]] = []
        for (model, task, condition), group_rewards in rewards.items():
            for trial, reward in enumerate(group_rewards):
                rows.append(
                    {
                        "task": task,
                        "model_id": model,
                        "condition": condition,
                        "trial": trial,
                        "reward": reward,
                        "turns": 1 if condition == "single_shot" else 3 + trial,
                        "tool_calls": 0 if condition == "single_shot" else 2,
                        "tokens_in": 100 + trial,
                        "tokens_out": 50 + trial,
                        "cost_usd": 0.01 * (trial + 1),
                        "area_norm": 1.0 - 0.1 * trial,
                        "depth_norm": 1.1 - 0.1 * trial,
                        "flagged": model == "small"
                        and task == "task_a"
                        and condition == "single_shot"
                        and trial == 1,
                        "latency_ms_per_call": [10.0 + trial, 20.0 + trial],
                        "cache_hits": trial % 2,
                    }
                )
        return rows

    def test_report_contains_exact_counts_deltas_and_pointers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_path = root / "results.jsonl"
            output_path = root / "report.md"
            input_path.write_text(
                "".join(json.dumps(row) + "\n" for row in self._rows()),
                encoding="utf-8",
            )

            self.assertEqual(
                report.main(["--in", str(input_path), "--out", str(output_path)]),
                0,
            )
            markdown = output_path.read_text(encoding="utf-8")

            self.assertIn(
                "| small | 2/6 (33.3%) | 4/6 (66.7%) | +33.3 pp | 1/2 (50.0%) | 2/2 (100.0%) | +50.0 pp | +0.258 |",
                markdown,
            )
            self.assertIn(
                "| task_a | small | single_shot | 2/3 | 66.7% | 2/3 (66.7%) | 1/1 (100.0%) | 0.567 | 1.00 | 0.00 | 101.0 | 51.0 | 0.0200 | 0.900 | 1.000 | 1 ([trial 1](transcripts/task_a_small_single_shot_1.jsonl)) |",
                markdown,
            )
            self.assertIn(
                "| task_b | small | single_shot | 0/3 | 0.0% | 0/3 (0.0%) | 0/1 (0.0%) |",
                markdown,
            )
            self.assertIn("## Tool latency and cache", markdown)
            self.assertIn("| small | agentic | 12 | 16.0 | 22.0 | 2/12 (16.7%) |", markdown)


if __name__ == "__main__":
    unittest.main()
