# Campaign Learnings

## Standing rules
- System python3.14 lacks ensurepip; `python3 -m venv` fails. Use `uv venv` + `uv pip install -p ./venv/bin/python ...`.
- Toolchain never on PATH: every command needs RTL_GYM_TOOLS or absolute `/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin`.
- Eval model IDs pinned: claude-opus-5, gpt-5.6-luna (effort=max). Probe cost ≈ nothing; `codex exec --json` returns usage tokens per turn.

## Log
<!-- newest first: date | task | worker | outcome | lesson -->
- 2026-08-09 | kickoff | conductor | ok | codex:rescue plugin rejected as eval backend (one-shot forwarder, no MCP tool control); raw `codex exec` chosen. Companion jobs keyed to worktree cwd — record jobId+cwd+logFile.
