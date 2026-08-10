from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent.backends.anthropic_backend import AnthropicBackend
from agent.backends.codex_backend import CodexBackend, CodexBackendResult, PYTHON
from agent.loop import RESULT_FIELDS, _first_failure_stage, run_episode
from agent.prompts import AGENTIC_PROTOCOL, SINGLE_SHOT_PROTOCOL, build_prompt, prompt_hash
from env.runner import EpisodeState
from eval.report import render_report


ROOT = Path(__file__).resolve().parents[2]
TASK = ROOT / "env" / "fixtures" / "toy_adder"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TOOLS = "/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin"


class EpisodeTests(unittest.TestCase):
    def run_mock(self, condition: str, fixture: str = "mock_episode.json") -> tuple[dict, Path]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        out_dir = Path(temporary.name)
        with patch.dict(
            os.environ,
            {"RTL_GYM_MOCK_FIXTURE": str(FIXTURES / fixture), "RTL_GYM_TOOLS": TOOLS},
        ):
            row = run_episode(TASK, "mock", condition, 0, out_dir)
        return row, out_dir

    def test_mock_agentic_ref_scores_one_and_counts_actions(self) -> None:
        row, out_dir = self.run_mock("agentic")
        self.assertEqual(1.0, row["reward"])
        self.assertEqual(3, row["turns"])
        self.assertEqual(3, row["tool_calls"])
        self.assertEqual(11, row["tokens_in"])
        self.assertEqual(7, row["tokens_out"])
        self.assertTrue(row["protocol_ok"])
        self.assertEqual([], row["protocol_violations"])
        self.assertEqual("none", row["first_failure_stage"])
        self.assertIsNone(row["error"])
        self.assertTrue(all(field in row for field in RESULT_FIELDS))
        transcript = out_dir / "transcripts" / "toy_adder_mock_agentic_0.jsonl"
        records = [json.loads(line) for line in transcript.read_text().splitlines()]
        self.assertTrue(records)
        self.assertTrue(any(record["type"] == "grade" for record in records))
        self.assertEqual(1, sum(record["type"] == "prompt" for record in records))

    def test_mock_single_shot_broken_rtl_lands_on_hidden_fail_rung(self) -> None:
        row, _ = self.run_mock("single_shot")
        self.assertTrue(row["compile_ok"])
        self.assertTrue(row["visible_pass"])
        self.assertFalse(row["hidden_pass"])
        self.assertEqual(0.2, row["reward"])
        self.assertEqual("hidden_sim", row["first_failure_stage"])
        self.assertEqual(1, row["turns"])
        self.assertEqual(0, row["tool_calls"])

    def test_single_shot_without_code_block_is_compile_fail_row(self) -> None:
        row, _ = self.run_mock("single_shot", "mock_no_block.json")
        self.assertFalse(row["compile_ok"])
        self.assertEqual(0.0, row["reward"])
        self.assertEqual("no_submission", row["first_failure_stage"])
        self.assertIn("no parsable Verilog", row["error"])


class PromptTests(unittest.TestCase):
    def test_prompts_are_deterministic_and_change_only_protocol_suffix(self) -> None:
        agentic = build_prompt(TASK, "agentic")
        single = build_prompt(TASK, "single_shot")
        self.assertEqual(agentic.system, single.system)
        self.assertEqual(
            agentic.user[: -len(AGENTIC_PROTOCOL)],
            single.user[: -len(SINGLE_SHOT_PROTOCOL)],
        )
        self.assertEqual(prompt_hash(agentic), prompt_hash(build_prompt(TASK, "agentic")))
        self.assertEqual(prompt_hash(agentic), prompt_hash(TASK, "agentic"))
        self.assertEqual(64, len(prompt_hash(agentic)))


class ReportAttributionTests(unittest.TestCase):
    def test_report_counts_first_failure_categories(self) -> None:
        rows = [
            {
                "task": "task",
                "model_id": "mock",
                "condition": "agentic",
                "trial": trial,
                "reward": 1.0 if stage == "none" else 0.2,
                "first_failure_stage": stage,
            }
            for trial, stage in enumerate(("none", "hidden_sim", "hidden_sim"))
        ]
        markdown = render_report(
            rows,
            input_path=Path("results/results.jsonl"),
            output_path=Path("results/report.md"),
        )
        self.assertIn("## First-failure attribution", markdown)
        self.assertIn("| none | 1 | 33.3% |", markdown)
        self.assertIn("| hidden_sim | 2 | 66.7% |", markdown)


class FakeMessages:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.requests: list[dict] = []

    def create(self, **request: object) -> object:
        self.requests.append(request)
        return self.responses.pop(0)


class AnthropicTests(unittest.TestCase):
    def test_keyless_stub_receives_single_shot_request_without_tools(self) -> None:
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="```verilog\nmodule x; endmodule\n```")],
            usage=SimpleNamespace(input_tokens=5, output_tokens=3),
        )
        messages = FakeMessages([response])
        client = SimpleNamespace(messages=messages)
        backend = AnthropicBackend("claude-opus-5", client=client)
        events: list[dict] = []
        result = backend.run(
            build_prompt(TASK, "single_shot"),
            "single_shot",
            TASK,
            None,
            events.append,
            10,
        )
        self.assertEqual(1, result.turns)
        self.assertEqual((5, 3), (result.tokens_in, result.tokens_out))
        self.assertNotIn("tools", messages.requests[0])
        self.assertNotIn("temperature", messages.requests[0])
        self.assertEqual("claude-opus-5", messages.requests[0]["model"])

    def test_keyless_stub_executes_submit_tool(self) -> None:
        rtl = (TASK / "ref" / "ref.v").read_text()
        response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use", id="tool-1", name="submit", input={"rtl": rtl}
                )
            ],
            usage=SimpleNamespace(input_tokens=8, output_tokens=4),
        )
        messages = FakeMessages([response])
        client = SimpleNamespace(messages=messages)
        with tempfile.TemporaryDirectory() as temporary:
            state = EpisodeState.load(TASK, workdir=temporary)
            result = AnthropicBackend("claude-opus-5", client=client).run(
                build_prompt(TASK, "agentic"),
                "agentic",
                TASK,
                state.make_tools(),
                lambda event: None,
                3,
            )
            self.assertTrue(state.submitted)
        self.assertEqual(1, result.turns)
        self.assertEqual(1, result.tool_calls)
        self.assertIn("tools", messages.requests[0])


class CodexCommandTests(unittest.TestCase):
    def test_agentic_command_has_pinned_mcp_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"RTL_GYM_TOOLS": TOOLS}
        ):
            command = CodexBackend("gpt-test", effort="high").command(
                build_prompt(TASK, "agentic"),
                "agentic",
                TASK,
                Path(temporary),
                6,
            )
        joined = " ".join(command)
        self.assertIn("exec --json --ephemeral -s read-only", joined)
        self.assertIn("-m gpt-test", joined)
        self.assertIn('model_reasoning_effort="high"', joined)
        self.assertIn(f'mcp_servers.rtlgym.command="{PYTHON}"', joined)
        self.assertIn('mcp_servers.rtlgym.args=["-m","agent.mcp_server"]', joined)
        self.assertIn('mcp_servers.rtlgym.env.RTL_GYM_MAX_TOOL_CALLS="6"', joined)
        self.assertIn(f'mcp_servers.rtlgym.env.PYTHONPATH="{ROOT}"', joined)

    def test_run_launches_from_empty_episode_local_cwd(self) -> None:
        captured: dict[str, object] = {}

        class FakeProcess:
            pid = 12345
            returncode = 0

            def communicate(self, timeout: float | None = None) -> tuple[str, str]:
                del timeout
                return ('{"type":"turn.completed","usage":{}}\n', "")

        def fake_popen(command: list[str], **kwargs: object) -> FakeProcess:
            captured["command"] = command
            captured.update(kwargs)
            return FakeProcess()

        with tempfile.TemporaryDirectory() as temporary:
            episode_dir = Path(temporary) / "episode"
            episode_dir.mkdir()
            (episode_dir / "agent_cwd").mkdir()
            (episode_dir / "agent_cwd" / "stale.txt").write_text("stale")
            state = EpisodeState.load(TASK, workdir=episode_dir)
            with patch("agent.backends.codex_backend.subprocess.Popen", fake_popen):
                CodexBackend("gpt-test", effort="low").run(
                    build_prompt(TASK, "single_shot"),
                    "single_shot",
                    TASK,
                    None,
                    lambda event: None,
                    1,
                    episode_dir=episode_dir,
                    state=state,
                )
            agent_cwd = episode_dir / "agent_cwd"
            self.assertEqual(agent_cwd, captured["cwd"])
            self.assertEqual([], list(agent_cwd.iterdir()))
            self.assertNotEqual(ROOT, captured["cwd"])

    def test_protocol_classifier_flags_shell_once_and_accepts_rtlgym(self) -> None:
        result = CodexBackendResult()
        seen_actions: set[str] = set()
        seen_errors: set[str] = set()
        shell = {
            "id": "shell-1",
            "type": "command_execution",
            "command": "sed -n '1p' hidden.v",
        }
        CodexBackend._inspect_item(shell, result, seen_actions, seen_errors)
        CodexBackend._inspect_item(shell, result, seen_actions, seen_errors)
        CodexBackend._inspect_item(
            {
                "id": "tool-1",
                "type": "mcp_tool_call",
                "server": "rtlgym",
                "tool": "run_sim",
                "arguments": {"rtl": "module x; endmodule"},
                "status": "completed",
                "result": {"structured_content": {"passed": True}},
            },
            result,
            seen_actions,
            seen_errors,
        )
        self.assertEqual(1, len(result.protocol_violations))
        self.assertIn("command_execution", result.protocol_violations[0])
        self.assertFalse(result.tool_argument_errors)
        self.assertFalse(result.tool_execution_errors)

    def test_first_failure_uses_declared_ladder_order(self) -> None:
        result = CodexBackendResult(
            protocol_violations=["command_execution"],
            tool_argument_errors=["run_sim: invalid rtl argument"],
        )
        self.assertEqual(
            "tool_argument",
            _first_failure_stage(
                submitted=True,
                graded={"first_failure_stage": "hidden_sim"},
                backend_result=result,
            ),
        )


class MCPServerTests(unittest.TestCase):
    @contextmanager
    def server(self, max_calls: int = 10):
        temporary = tempfile.TemporaryDirectory()
        env = os.environ.copy()
        env.update(
            {
                "RTL_GYM_TASK_DIR": str(TASK),
                "RTL_GYM_EPISODE_DIR": temporary.name,
                "RTL_GYM_TOOLS": TOOLS,
                "RTL_GYM_MAX_TOOL_CALLS": str(max_calls),
                "PYTHONPATH": str(ROOT),
            }
        )
        process = subprocess.Popen(
            [PYTHON, "-m", "agent.mcp_server"],
            cwd=temporary.name,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            yield process, Path(temporary.name)
        finally:
            if process.stdin:
                process.stdin.close()
            process.wait(timeout=10)
            stderr = process.stderr.read() if process.stderr else ""
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
            if process.returncode != 0:
                self.fail(stderr or "MCP server failed")
            temporary.cleanup()

    def rpc(self, process: subprocess.Popen, request: dict) -> dict:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    def initialize(self, process: subprocess.Popen) -> None:
        initialized = self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
            },
        )
        self.assertEqual("rtlgym", initialized["result"]["serverInfo"]["name"])
        assert process.stdin is not None
        process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        process.stdin.flush()

    def call_sim(self, process: subprocess.Popen, request_id: int) -> dict:
        rtl = (TASK / "ref" / "ref.v").read_text()
        return self.rpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "run_sim", "arguments": {"rtl": rtl}},
            },
        )

    def test_protocol_lists_tools_and_runs_visible_sim(self) -> None:
        with self.server() as (process, episode_dir):
            self.initialize(process)
            listed = self.rpc(
                process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            )
            self.assertEqual(
                {"run_sim", "run_synth", "submit"},
                {tool["name"] for tool in listed["result"]["tools"]},
            )
            called = self.call_sim(process, 3)
            payload = json.loads(called["result"]["content"][0]["text"])
            self.assertTrue(payload["compile_ok"])
            self.assertTrue(payload["passed"])
            rtl = (TASK / "ref" / "ref.v").read_text()
            submitted = self.rpc(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {"name": "submit", "arguments": {"rtl": rtl}},
                },
            )
            accepted = json.loads(submitted["result"]["content"][0]["text"])
            self.assertTrue(accepted["accepted"])
            self.assertEqual(rtl, (episode_dir / "submission.v").read_text())
            logs = [json.loads(line) for line in (episode_dir / "tool_log.jsonl").read_text().splitlines()]
            self.assertEqual("run_sim", logs[0]["name"])

    def test_budget_exhaustion_after_n_calls(self) -> None:
        with self.server(max_calls=1) as (process, episode_dir):
            self.initialize(process)
            first = self.call_sim(process, 2)
            self.assertTrue(json.loads(first["result"]["content"][0]["text"])["passed"])
            second = self.call_sim(process, 3)
            self.assertEqual(
                "budget exhausted — submit now", second["result"]["content"][0]["text"]
            )
            state = json.loads((episode_dir / "mcp_state.json").read_text())
            self.assertEqual(2, state["tool_calls"])


if __name__ == "__main__":
    unittest.main()
