# Campaign Learnings

## Standing rules
- System python3.14 lacks ensurepip; `python3 -m venv` fails. Use `uv venv` + `uv pip install -p ./venv/bin/python ...`.
- Toolchain never on PATH: every command needs RTL_GYM_TOOLS or absolute `/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin`.
- Eval model IDs pinned: claude-opus-5, gpt-5.6-luna (effort=max). Probe cost ≈ nothing; `codex exec --json` returns usage tokens per turn.

## Log
<!-- newest first: date | task | worker | outcome | lesson -->
- 2026-08-09 | codex MCP eval backend | conductor+scout | fixed | `codex exec` auto-cancels ALL MCP tool approvals ("user cancelled MCP tool call"); approval_policy/never and feature flags don't help. Required: `-c 'mcp_servers.<id>.default_tools_approval_mode="approve"'`. Found via web-search scout reading codex-rs source. Also: `--search` is a root-command flag in 0.147, not an exec flag.
- 2026-08-09 | wave-1 integration | conductor | contract gap found | Two workers built to CONTRACTS.md but it under-specified how oracles learn the (mangled) ref module name. Refs graded 0.2 on integrated main; both workers' own verifications were green because neither exercised the cross-boundary path. Lesson: for any producer/consumer file contract, the contract doc must pin name-discovery rules, and integration smoke on merged main is non-negotiable before calling a wave done.
- 2026-08-09 | kickoff | conductor | ok | codex:rescue plugin rejected as eval backend (one-shot forwarder, no MCP tool control); raw `codex exec` chosen. Companion jobs keyed to worktree cwd — record jobId+cwd+logFile.
