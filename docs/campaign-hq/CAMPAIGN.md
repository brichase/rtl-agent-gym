# Campaign: rtl-agent-gym
Goal: Build the adversarially hardened RTL-agent benchmark per `rtl-agent-gym-weekend-plan-v2.md` — 6 verified tasks, red-teamed grader, synthesis-cost proxy rewards, single-shot vs tool-loop ablation across claude-opus-5 and gpt-5.6-luna(max).
Status: phase 4++ COMPLETE. Wave 4 (external-review fixes) merged: LEAK CLOSED (agent cwd isolated, canary leakage-check passes), DEPTH/WIDTH parameterization enforced (hardcoded-8 fifo 0.97→0.2), AXI oracle stall-tolerant + same-edge coverage, first_failure_stage + protocol_ok fields added. Smoke 36/36, unit tests green. User RATIFIED all 4 semantic conventions. Models: gpt-5.6-luna@max + gpt-5.6-sol@high (both Codex; NO Anthropic key needed). Pilot re-running with isolated backend (old pilot numbers contaminated by leak — do not cite). Next: full eval on user go.

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

## OVERNIGHT RUN — COMPLETE (2026-08-10, before 06:00)
Full eval finished: 120/120 episodes, 0 infra errors. luna 60/60 pass; sol 59/60 (one AXI single-shot miss, tool loop fixed 5/5). Report: results/full/report.md. README numbers + 3 findings filled, hacks/ has the flood example, evidence transcripts saved. Final smoke 36/36, unit tests OK, leakage-check PASS, fresh-clone repro PASS, MIT license. 44 commits. Token spend 8.6M in / 399k out (Codex plan). Deliverables checklist essentially complete; repo is ship-ready pending user's go to publish.
Key finding: environment value is in synthesis-cost quality, not pass/fail (both models pass@5 6/6). UART agentic area 0.41-0.64x single-shot; FIFO depth 1.86->1.06. Depth pressure confirmed. Zero model reward-hacks.

## OVERNIGHT RUN (user asleep until ~06:00, 2026-08-10) — authorized "keep working"
Guardrails honored: no remote (none exists), no destructive ops, everything self-verified before commit, additive only.
- Full eval LAUNCHED: gpt-5.6-luna@max + gpt-5.6-sol@high, 6 tasks × 5 trials × 2 conditions = 60 episodes/model, parallel detached, --resume, monitored. Results → results/full/{luna,sol}/. All on Codex plan (no Anthropic key).
- Isolated backend (shell disabled) — all overnight numbers are leak-free. Pilot re-run confirmed FIFO agentic 0.999 with protocol_ok=True.
- Overnight deliverables in progress: README (drafted, numbers pending sweep), LICENSE (done), report tables (on sweep completion), failure analysis + hacks/, fresh-clone repro check.
- Morning report will be four buckets: merged+verified / awaiting-field-test / blocked / one decision needed first.

## Fleet (active dispatches)

| Task | Worker | Branch | Worktree | Session | Dispatched | Status |
|---|---|---|---|---|---|---|
| env-core | codex companion (gpt-5.6-sol high) | campaign/env-core | .worktrees/env-core | task-msm1ytx5-w1x4oz | 2026-08-09 | done, verified, merged (11 min) |
| tasks-batch1 | codex companion (gpt-5.6-sol high) | campaign/tasks-batch1 | .worktrees/tasks-batch1 | task-msm1ytzw-j1hkac | 2026-08-09 | done, verified, merged (11 min) |
| oracle-fix (module-name discovery) | codex companion resume | campaign/tasks-batch1 | .worktrees/tasks-batch1 | task-msm2j3qh-d1ezxx | 2026-08-09 | done, merged; smoke 15/15 |
| agent-loop | codex companion (gpt-5.6-sol high) | campaign/agent-loop | .worktrees/agent-loop | task-msm2orkv-c9cqr6 | 2026-08-09 | running (~30 min expected) |
| eval-harness | codex companion (gpt-5.6-sol high) | campaign/eval-harness | .worktrees/eval-harness | task-msm2ornb-jfmsr3 | 2026-08-09 | done, verified, merged |
| tasks-batch2 | codex companion (gpt-5.6-sol high) | campaign/tasks-batch2 | (removed) | task-msm3xvbq-wv31up | 2026-08-09 | done, verified, merged; worktree cleaned |
| redteam | Claude general-purpose (rerouted from Codex — content filter) | campaign/redteam | (removed) | agent a4b338020185cf808 | 2026-08-09 | done, verified, merged; FINDING: flood weakness |
| harden-flood | codex companion (gpt-5.6-sol high) | campaign/harden-flood | (removed) | task-msm4g812-ngnma1 | 2026-08-09 | done, verified, merged; smoke 34/34 |
| harness-integrity (LEAK FIX) | codex companion | campaign/harness-integrity | .worktrees/harness-integrity | task-msmljm61-h1ktws | 2026-08-09 | running (watch for content-filter refusal → reroute Claude) |
| param-coverage | codex companion | campaign/param-coverage | .worktrees/param-coverage | task-msmljm8m-cufl01 | 2026-08-09 | running |
| axi-oracle | codex companion | campaign/axi-oracle | .worktrees/axi-oracle | task-msmljmbi-sc0507 | 2026-08-09 | running |

## Wave 4 origin: external agent review (2026-08-09)
Findings verified by conductor: (1) LEAK — codex_backend cwd=repo_root + read-only sandbox lets agent read ref.v/hidden/oracle; pilot transcripts confirm. Agentic pilot numbers CONTAMINATED, must re-run after fix. (2) FIFO DEPTH hole — hardcoded-8 fifo scores 0.97 (verified). (3) barrel low-3-bits: conductor could NOT reproduce reward 1.0 (got 0.2); fixing coverage anyway. (4) AXI oracle over-constrains AW/W order + immediate-ready. Semantic conventions (D2/D5/D6/D7) endorsed by reviewer; awaiting user's single bundled ratification.

## Verified environment (kickoff preflight 2026-08-09)
- OSS CAD Suite 2026-08-09 (linux-x64) at `toolchain/oss-cad-suite/` (gitignored, 2.5G): iverilog 14.0-devel s20260301, Yosys 0.68+40. Adder smoke: sim PASS, stat 20 cells.
- Codex CLI 0.147.0, ChatGPT login, default model gpt-5.6-sol effort=high (workers inherit this).
- Python 3.14.4 system; venv pending. 12 cores, 53G RAM.
