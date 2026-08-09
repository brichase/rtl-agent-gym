# Task: agent/ — episode driver with Anthropic + Codex backends

## Goal
Build `agent/loop.py`, `agent/prompts.py`, `agent/mcp_server.py`: the model-driving
side of rtl-agent-gym. Implements the episode API in `docs/CONTRACTS.md` (§agent/
episode API) exactly — `eval/` is being built against it by a sibling worker right now.

## Read first (worktree root)
`docs/CONTRACTS.md` (episode API, tools.py signatures, results schema, TB protocol),
`rtl-agent-gym-weekend-plan-v2.md` §2 §6, `env/tools.py` + `env/runner.py` (built, on
main — use them, don't reimplement grading/sim).

## Environment
- Branch `campaign/agent-loop`, worktree `/data/projects/rtl-agent-gym/.worktrees/agent-loop`, base `0c7c31a`.
- venv: `/data/projects/rtl-agent-gym/venv/bin/python` (anthropic 0.121.0, pyyaml).
- Tools dir (for env/ calls): RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin
- NO ANTHROPIC_API_KEY exists. All your tests must run keyless. Codex CLI 0.147 is
  installed and logged in (ChatGPT plan) — you may run AT MOST 2 tiny live
  `codex exec` sanity calls total (model default, prompt "reply OK"-scale); the full
  live pilot is the conductor's job, not yours.

## Owned files
`agent/__init__.py`, `agent/loop.py`, `agent/prompts.py`, `agent/mcp_server.py`,
`agent/backends/` (anthropic_backend.py, codex_backend.py, mock_backend.py),
`agent/tests/` (unittest, keyless).

## Excluded
`env/**`, `tasks/**`, `eval/**`, `redteam/**`, `Makefile`, `README.md`, `docs/campaign-hq/**`

## Design decisions (binding)
- prompts.py: system+user prompt built from task spec.md + interface.v + tool-use
  instructions. Identical task content across backends and conditions; agentic adds only
  the tool protocol section; single_shot adds "output final Verilog in one ```verilog
  block". Deterministic; expose `prompt_hash()` (sha256 of the rendered prompt) for the
  results row.
- AnthropicBackend: `anthropic` SDK tool-use loop, tools run_sim/run_synth/submit mapped
  to env/tools.py; max_turns cap; temperature default; records tokens_in/out from usage,
  per-call latency; cost_usd from a PRICING dict in agent/pricing.py (leave rates None
  with TODO if you cannot verify current claude-opus-5 pricing — do NOT invent numbers;
  null cost is acceptable and the conductor fills rates later).
- CodexBackend: spawns `codex exec --json -s read-only` with
  `-c mcp_servers.rtlgym.command=/data/projects/rtl-agent-gym/venv/bin/python`
  `-c 'mcp_servers.rtlgym.args=["-m","agent.mcp_server"]'` and env vars
  (RTL_GYM_TASK_DIR, RTL_GYM_EPISODE_DIR, RTL_GYM_TOOLS, RTL_GYM_MAX_TOOL_CALLS)
  passed via `-c mcp_servers.rtlgym.env.<K>=<V>`. Model + effort via
  `-m <model> -c model_reasoning_effort=<effort>`. Parse the JSON event stream for
  messages, tool calls, usage tokens. Verify the exact config syntax against
  `codex exec --help` / codex docs on this machine; record what works in your report.
  Episode ends when the model calls submit (MCP server writes submission.v +
  state file the backend polls after codex exec exits) or codex exec terminates.
  Wall-clock cap per episode (default 15 min) → kill process group, error row.
- mcp_server.py: minimal MCP stdio server (implement the protocol by hand, stdlib only —
  handshake initialize/initialized, tools/list, tools/call; JSON-RPC over stdin/stdout).
  Serves run_sim/run_synth/submit for ONE episode configured via env vars. Tool-call
  budget: after RTL_GYM_MAX_TOOL_CALLS, run_sim/run_synth return "budget exhausted —
  submit now". Log every call with args+result+latency to RTL_GYM_EPISODE_DIR/tool_log.jsonl.
- MockBackend: scripted sequence from a fixture file (list of fake model actions:
  tool calls + final submit). Used by tests to exercise the full episode path
  including real env grading of the toy_adder fixture, keyless.
- run_episode(): per CONTRACTS.md. Grades via env.grade after submit; writes transcript
  JSONL + returns full results row (all schema fields; tool_versions from env;
  condition, prompt_hash, timestamp included). Single-shot with no parsable code block →
  compile_fail row, not an exception.

## Verification (goes in report)
```
cd /data/projects/rtl-agent-gym/.worktrees/agent-loop && RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin /data/projects/rtl-agent-gym/venv/bin/python -m unittest discover -s agent/tests -v
```
Tests must cover: mock agentic episode on env/fixtures/toy_adder ends with reward 1.0
row (mock submits ref source) and correct turns/tool_calls counts; mock single-shot with
broken RTL yields the right rung; MCP server speaks the protocol over a pipe (spawn it,
do initialize + tools/list + a run_sim tools/call on toy_adder, assert result JSON);
budget exhaustion message after N calls; transcript file written and parseable.

## Live smoke (report observed output)
MCP server standalone against toy_adder (the tools/call sequence above) + ONE live
`codex exec` sanity call confirming your MCP config syntax loads the server
(model default, ask it to call run_sim once on the provided stub and reply with the
result status only). If the live call is impossible, mark live_smoke.passed=false with
the blocker — do not fake it.

## Constraints
No subagents. Keyless Anthropic path (unit-test request construction with a stubbed
client, never a real call). You cannot commit; intended message:
`campaign/agent-loop: episode driver, Anthropic+Codex backends, MCP tool server`.

## Final report: same JSON shape as before (status, branch, commit:"", files_changed,
verify_cmd, verify_result{passed,output_tail}, live_smoke{cmd,expected,observed,passed},
blockers).
