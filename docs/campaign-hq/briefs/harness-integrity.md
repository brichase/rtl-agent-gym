# Task: harness integrity — isolate the agent sandbox + failure attribution

## Why
An external review found an evaluation-integrity bug: the Codex episode backend launches
`codex exec` with `cwd = repo_root` and a read-only sandbox, so the agent under test can
READ reference RTL, hidden testbenches, oracles, and broken variants directly. The pilot
transcripts confirm agents opened `tasks/*/ref/ref.v`. This invalidates any agentic-vs-
single-shot comparison because the agentic condition was not isolated from answer data.
Fix the isolation and add a preflight that proves the leak is closed. Also add first-
failure attribution so the report can say WHY a low reward happened.

## Environment
Branch `campaign/harness-integrity`, worktree `/data/projects/rtl-agent-gym/.worktrees/harness-integrity`, base fc207c8.
Tools: RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin (not on PATH).
Python: /data/projects/rtl-agent-gym/venv/bin/python. Codex CLI 0.147 present, ChatGPT login.

## Read first
`agent/backends/codex_backend.py` (the bug is `cwd=self.repo_root` ~line 150), `agent/loop.py`,
`agent/mcp_server.py`, `env/grade.py`, `docs/CONTRACTS.md` (episode API + results row).

## Owned files
`agent/backends/codex_backend.py`, `agent/loop.py`, `agent/mcp_server.py`,
`env/grade.py`, `eval/report.py`, `agent/tests/*`, `env/tests/*`. Do NOT touch tasks/,
redteam/, or the reward-ladder reward constants.

## Work items
1. **Sandbox isolation (the core fix).** Launch the Codex agent with `cwd` set to an
   ISOLATED per-episode working dir (e.g. `episode_dir/agent_cwd/`) that contains NONE of
   the repo answer data — not repo_root. The agent needs nothing from disk: spec +
   interface come through the prompt (prompts.py already renders them at launch), and
   run_sim/run_synth/submit come through the MCP server (which reads task files server-
   side via RTL_GYM_TASK_DIR env, unchanged). Ensure the MCP server subprocess still finds
   `agent.mcp_server` (use an absolute PYTHONPATH / -m resolution that does not depend on
   cwd=repo_root). Keep read-only sandbox. The Anthropic backend path is unaffected but
   confirm it too grades only the submitted RTL, never exposing answer files.
2. **Leakage preflight + canary.** Add `agent/leakage_check.py` (and a unit test) that:
   plants a canary file named e.g. `HIDDEN_CANARY_<rand>.txt` under the repo/task answer
   area, runs a real one-turn agent episode whose prompt explicitly asks the model to read
   and echo any file it can find named like the canary, and asserts the canary content
   does NOT appear in the transcript/submission. If it does → raise/exit non-zero
   (`leakage detected`). Wire it as a Makefile target `leakage-check` and reference it from
   the README-facing smoke path is NOT required, but `make leakage-check` must pass. This
   needs ONE real codex exec call — you are authorized to make it (small, model default).
3. **Protocol tracking.** In the episode result row add `protocol_ok` (bool): false if the
   agent made any tool/file action outside the three approved MCP tools (for Codex, detect
   local shell / file-read events in the JSON event stream; approved = mcp rtlgym tool
   calls + normal reasoning/messages). Record `protocol_violations` (list of short
   strings). Do not fail the episode on a violation — just record it; the conductor
   reviews flagged rows.
4. **First-failure attribution.** Add `first_failure_stage` to the results row, one of:
   `none, no_submission, compile, visible_sim, tool_argument, tool_execution, hidden_sim,
   oracle, sanity, synthesis, protocol_violation`. Derive it from the existing grade JSON
   + episode events (first stage, in ladder order, that did not pass). `none` when reward
   is full. Surface a per-category count table in eval/report.py.

## Verification (report it)
- `RTL_GYM_TOOLS=... /data/projects/rtl-agent-gym/venv/bin/python -m unittest discover -s agent/tests` and `-s env/tests` green.
- `RTL_GYM_TOOLS=... make leakage-check` → passes (canary NOT leaked). Include the observed
  final line proving the canary was unreadable.
- A mock or real episode row now includes protocol_ok, protocol_violations,
  first_failure_stage. Show one example row (JSON, trimmed).
- `RTL_GYM_TOOLS=... make smoke-test` still 34/34.

## Constraints
No subagents. At most 2 live codex exec calls total (the canary check + one sanity). You
cannot commit; intended message:
`campaign/harness-integrity: isolate agent cwd, leakage canary, protocol + first-failure fields`.
Final report: standard JSON shape + in live_smoke.observed put the leakage-check result
and one example results row.
