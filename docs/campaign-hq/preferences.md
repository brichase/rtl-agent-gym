# Worker Routing Preferences
<!-- Precedence: user's live instruction > this file > skill defaults.
     Update this file whenever the user states a preference. -->

## Kickoff preflight (2026-08-09)
- codex-cli 0.147.0, ChatGPT-plan login OK. Companion runtime: `~/.claude/plugins/cache/openai-codex/codex/1.0.5/scripts/codex-companion.mjs`
- Codex config default: model gpt-5.6-sol, reasoning high — workers inherit; don't override without user request
- Toolchain: `toolchain/oss-cad-suite/bin` (absolute: /data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin)
- Verification command: `make smoke-test` (once it exists); per-worker commands in briefs
- Permission envelope: companion tasks run with --write (`.git` read-only → conductor commits); no ANTHROPIC_API_KEY until user exports it

## User decisions (2026-08-09)
- Eval models: claude-opus-5 + gpt-5.6-luna at model_reasoning_effort=max (user said "codex luna max")
- Eval Codex backend: raw `codex exec` + MCP tools server — NOT codex:rescue plugin (conductor evaluated both; plugin is a one-shot forwarder)
- Hidden TB/oracle review: user reviews in two batches ({1,2,4}, then {3,5,6}); conductor preps review docs
- API key: user exports when eval phase starts; build phases stay API-free
- Conductor: Fable when available, otherwise Claude Opus at high effort
- UI/UX, design, integration judgment: Claude Opus, high effort
- Implementation, tests, research, mechanical refactors: Codex CLI when available
- Codex unavailable: Claude worker agents use the same briefs and report schema
- Model/effort overrides: user's live request wins; record requested worker, model, and reasoning level before dispatch
- Check-in cadence: phase boundaries and plan-changing surprises
- Permission envelope: record Codex sandbox/network/approval policy and Claude worker edit permissions at kickoff
