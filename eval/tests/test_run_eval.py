from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from eval import run_eval


class RunEvalTest(unittest.TestCase):
    def test_sweep_persists_every_row_and_resume_skips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dirs = []
            for name in ("task_a", "task_b"):
                task_dir = root / name
                task_dir.mkdir()
                (task_dir / "task.yaml").write_text(f"name: {name}\n", encoding="utf-8")
                task_dirs.append(task_dir)
            output = root / "results"
            calls: list[dict[str, object]] = []

            def fake_run_episode(
                *,
                task_dir: Path,
                model_id: str,
                condition: str,
                trial: int,
                out_dir: Path,
                max_turns: int,
                max_effort: str | None = None,
            ) -> dict[str, object]:
                calls.append(
                    {
                        "task": task_dir.name,
                        "model": model_id,
                        "condition": condition,
                        "trial": trial,
                        "out_dir": out_dir,
                        "max_turns": max_turns,
                        "max_effort": max_effort,
                    }
                )
                row: dict[str, object] = {
                    "task": task_dir.name,
                    "model_id": model_id,
                    "condition": condition,
                    "trial": trial,
                    "reward": 0.8 if trial % 2 == 0 else 0.2,
                    "turns": trial + 1,
                    "tool_calls": trial,
                }
                if task_dir.name == "task_b" and condition == "agentic" and trial == 1:
                    row["error"] = "deterministic episode error"
                return row

            args = [
                "--tasks",
                ",".join(str(path) for path in task_dirs),
                "--models",
                "mock,gpt-5.6-luna@max",
                "--conditions",
                "single_shot,agentic",
                "--trials",
                "3",
                "--max-turns",
                "8",
                "--out",
                str(output),
            ]
            self.assertEqual(run_eval.main(args, run_episode_fn=fake_run_episode), 0)

            results_path = output / "results.jsonl"
            lines = results_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 24)
            rows = [json.loads(line) for line in lines]
            keys = {
                (row["task"], row["model_id"], row["condition"], row["trial"])
                for row in rows
            }
            self.assertEqual(len(keys), 24)
            self.assertTrue(all(line.startswith("{") and line.endswith("}") for line in lines))
            self.assertEqual(
                sum(row.get("error") == "deterministic episode error" for row in rows),
                2,
            )

            effort_calls = [call for call in calls if call["model"] == "gpt-5.6-luna"]
            self.assertEqual(len(effort_calls), 12)
            self.assertTrue(all(call["max_effort"] == "max" for call in effort_calls))
            self.assertTrue(
                all(row["model_id"] == "gpt-5.6-luna@max" for row in rows if "gpt" in row["model_id"])
            )

            self.assertEqual(
                run_eval.main([*args, "--resume"], run_episode_fn=fake_run_episode),
                0,
            )
            self.assertEqual(len(calls), 24)
            self.assertEqual(len(results_path.read_text(encoding="utf-8").splitlines()), 24)

    def test_episode_exception_is_written_as_error_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            task_dir = root / "task"
            task_dir.mkdir()

            def failing_episode(**_: object) -> dict[str, object]:
                raise RuntimeError("backend unavailable")

            rows = run_eval.run_sweep(
                tasks=[run_eval.TaskSpec(task_dir, "task")],
                models=[run_eval.ModelSpec("mock", "mock")],
                conditions=["agentic"],
                trials=1,
                out_dir=root / "out",
                max_turns=10,
                resume=False,
                run_episode=failing_episode,
            )
            self.assertEqual(len(rows), 1)
            self.assertIn("RuntimeError: backend unavailable", rows[0]["error"])
            persisted = json.loads((root / "out" / "results.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(persisted["trial"], 0)


if __name__ == "__main__":
    unittest.main()

