# Campaign: rtl-agent-gym
Goal: Build the adversarially hardened RTL-agent benchmark per `rtl-agent-gym-weekend-plan-v2.md` — 6 verified tasks, red-teamed grader, synthesis-cost proxy rewards, single-shot vs tool-loop ablation across claude-opus-5 and gpt-5.6-luna(max).
Status: phase 1 of 6: core build (wave 1 dispatched)

Spec: `rtl-agent-gym-weekend-plan-v2.md` (root). Interface contracts: `docs/CONTRACTS.md`.
Scope discipline: plan §1 "Out" list is binding. Finish early → deepen analysis, never widen.

## Eval configuration (user-decided 2026-08-09)
- Models: `claude-opus-5` (Anthropic API) × `gpt-5.6-luna` with `model_reasoning_effort="max"` (Codex CLI backend — verified working).
- Codex backend: raw `codex exec --json` + local MCP server exposing run_sim/run_synth/submit. NOT the codex:rescue plugin (it's a one-shot forwarder; no custom tools, no per-episode control).
- ANTHROPIC_API_KEY: not set; user exports it when eval phases start. Everything through phase 4 must run API-free.
- User reviews hidden TBs + oracles in two batches: after tasks {1,2,4}, after tasks {3,5,6}. Conductor preps a review doc per batch (TB intent, corner list, oracle logic).

## Phases

### Phase 1: core build (wave 1)
- [ ] env/ core: sandbox, latency, tools, grade, runner + Makefile + smoke-test harness — worker: codex — verify: `make smoke-test` scaffolding runs on tiny adder fixture
- [ ] tasks 1,2,4 (barrel shifter, gray counter, sync FIFO) + broken/ variants — worker: codex — verify: refs compile+pass own TBs via raw iverilog
- [ ] venv with pyyaml + anthropic — worker: conductor (tiny unblocker)

### Phase 2: integrate + grade-the-grader
- [ ] Merge wave 1; `make smoke-test`: refs → ≥0.95, broken variants → correct rungs — worker: conductor + codex fixes
- [ ] USER REVIEW batch 1: hidden TBs + oracles for tasks 1,2,4
- Milestone: smoke test green, zero API calls (plan Sat-AM milestone)

### Phase 3: agent loop + pilot
- [ ] agent/loop.py + prompts.py: Anthropic tool-use backend, full metrics logging from first run — worker: codex
- [ ] Codex backend: MCP server (tools over stdio) + `codex exec` episode driver — worker: codex
- [ ] eval/run_eval.py + report.py sweep scaffolding — worker: codex
- [ ] Pilot: 3 tasks × 2 conditions × 1 trial on gpt-5.6-luna (no Anthropic key needed); inspect transcripts, confirm metric discriminates — worker: conductor
- Milestone: pilot transcripts reviewed (plan Sat-PM milestone)

### Phase 4: remaining tasks + red team
- [ ] Tasks 3,5,6 (round-robin arbiter, UART tx, AXI-Lite regfile) + broken/ variants — worker: codex
- [ ] redteam/: 7 adversarial submissions + expected verdicts (attack list = plan §5) — worker: codex, attack ideas reviewed by conductor
- [ ] USER REVIEW batch 2: hidden TBs + oracles for tasks 3,5,6
- [ ] Fix what red team breaks; record before/after verdicts for README table
- Milestone: full smoke-test green over 6 tasks + 7 attacks; unattended single-model eval completes

### Phase 5: main eval + findings
- [ ] Needs ANTHROPIC_API_KEY from user
- [ ] Full sweep: 2 models × 6 tasks × 5 trials × 2 conditions (~120 episodes)
- [ ] README written by conductor+user: red-team table, eval tables with counts, 2–3 failure analyses, hack transcripts to results/hacks/, limitations
- Milestone: README with real numbers (plan Sun-PM milestone)

### Phase 6: ship
- [ ] Fresh-clone reproducibility: clean venv, `make smoke-test` — worker: codex in clean worktree
- [ ] MIT license, pin repo, resume bullet
- Fallback order if time collapses (plan §7): cut task 6 → 5 trials→3 → task 5. Never cut: two models, two conditions, red team, write-up.

## Fleet (active dispatches)

| Task | Worker | Branch | Worktree | Session | Dispatched | Status |
|---|---|---|---|---|---|---|

## Verified environment (kickoff preflight 2026-08-09)
- OSS CAD Suite 2026-08-09 (linux-x64) at `toolchain/oss-cad-suite/` (gitignored, 2.5G): iverilog 14.0-devel s20260301, Yosys 0.68+40. Adder smoke: sim PASS, stat 20 cells.
- Codex CLI 0.147.0, ChatGPT login, default model gpt-5.6-sol effort=high (workers inherit this).
- Python 3.14.4 system; venv pending. 12 cores, 53G RAM.
