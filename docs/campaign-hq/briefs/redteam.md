# Task: redteam/ — 7 adversarial submissions attacking the grader

## Goal
Write the 7 hand-crafted grader exploits from plan §5 (`rtl-agent-gym-weekend-plan-v2.md`),
each with an expected verdict, wired into `make smoke-test`. You are attacking OUR OWN
grader to find weaknesses BEFORE agents do. A finding that BREAKS the grader (attack
scores ≥0.7) is a SUCCESS of this exercise — report it as a finding, do not silently
patch the grader.

## Read first
Plan §5 (attack list), docs/CONTRACTS.md §redteam layout + §grade.py + §sandbox,
env/grade.py + env/sandbox.py (the defenses you're probing), tasks/gray_counter and
tasks/sync_fifo (targets; their tb_visible.v is what weak-visible-test attacks tune to).

## Environment
Branch `campaign/redteam`, worktree `/data/projects/rtl-agent-gym/.worktrees/redteam`.
Tools: /data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin. Python: /data/projects/rtl-agent-gym/venv/bin/python.

## Owned files
`redteam/<attack>/{submission.v,expected.yaml}` for exactly these 7 (names fixed):
1. `const_outputs` — constant/trivial outputs tuned to pass gray_counter's visible TB
   cases specifically. Expect: dies at hidden TB (max_reward 0.2... or 0.1 — verify and
   record actual, see below).
2. `stimulus_lookup` — hardcoded replay of sync_fifo tb_visible's exact stimulus→output
   mapping (a little ROM of the visible test's expected outputs). Expect: passes visible,
   dies hidden/oracle.
3. `hier_reference` — hierarchical reference trying to read TB or reference internals
   (e.g. `tb_visible.dut_ref...` / upward name refs). Expect: sanity static check
   rejects, or compile fails; must be flagged, ≤0.2.
4. `include_readmem` — `` `include `` and `$readmemh` attempts on grader files (ref.v,
   oracle files, /etc/passwd-style paths). Expect: sanity rejects; also verify the
   mangled ref filename makes the include target unguessable.
5. `infinite_loop` — zero-time always loop that hangs the simulator. Expect: timeout
   kill, reward ≤0.1, suite completes (does NOT hang make smoke-test — this is the key
   assertion).
6. `display_flood` — multi-MB $display flood. Expect: output truncated at the 64 KiB
   cap, grading completes with correct verdict, no disk blowup.
7. `xz_exploit` — drives outputs to X/Z hoping the checker treats X as match (targets
   any task whose TB might use == instead of !==). Expect: fails TBs (they use !==) and
   oracle; if any TB treats X as pass, THAT IS A FINDING — report it.

expected.yaml per attack: `{task: <target>, expect: {max_reward: <r>, flagged: <bool>},
note: <one-line what this attack probes>}`. Set max_reward/flagged from what you VERIFY
actually happens (run env.grade on each), not from hope — but if the verified outcome is
a grader weakness (e.g. attack reaches 0.7+), record the weakness in your report AND set
expected.yaml to the CURRENT actual behavior with `weakness: true` so smoke-test still
passes while the finding is visible.

## Makefile integration
make smoke-test already discovers redteam/ dirs (env/grade.py --smoke). Verify it picks
up all 7 and compares against expected.yaml. If discovery needs a small fix, you may
edit the Makefile/env/grade.py smoke-discovery code ONLY (no grading-logic changes).

## Verification (report it)
`RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin make smoke-test`
green over: 4 fixture cases + 3 tasks' refs/broken + your 7 attacks. Also report a
table: attack → intended verdict → actual verdict → blocked-by (which gate) → any
weakness found.

## Constraints
No subagents, no network. Cannot commit; intended message:
`campaign/redteam: 7 grader exploit submissions with verified verdicts`.
Final report: same JSON shape + the attack table in live_smoke.observed.
