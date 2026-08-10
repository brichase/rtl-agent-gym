# Task: parameterization coverage — barrel_shifter + sync_fifo

## Why
A review found the parameterization claims are not enforced. VERIFIED: a sync_fifo that
ignores its DEPTH parameter and hardcodes 8 entries scores reward 0.97 (all gates pass),
because every test and oracle uses DEPTH=8. The barrel_shifter's WIDTH=5 cases may not
fully distinguish correct `distance % WIDTH` rotation from the low-3-bits shortcut. Close
both holes by adding coverage at NON-default, NON-power-of-two parameters. This does not
change any task's semantics — only adds tests that enforce the existing spec.

## Environment
Branch `campaign/param-coverage`, worktree `/data/projects/rtl-agent-gym/.worktrees/param-coverage`, base fc207c8.
Tools: /data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin. Python: /data/projects/rtl-agent-gym/venv/bin/python.

## Owned files
`tasks/barrel_shifter/**`, `tasks/sync_fifo/**` ONLY. Do NOT touch other tasks, env/,
agent/, eval/, redteam/.

## Work items
1. **sync_fifo DEPTH enforcement.** Add a second DUT instantiation in tb_hidden.v at a
   NON-power-of-two DEPTH (use DEPTH=5) and non-default WIDTH (use WIDTH=4), exercising:
   fill to full, overflow-write ignored, simultaneous rd+wr at full, wraparound past 2×
   DEPTH, drain to empty, underflow-read ignored — the same corner battery the DEPTH=8
   instance gets, driven by the same inline golden model generalized to the parameter.
   ALSO extend oracle.py so at least one of its seeds drives a DEPTH=5/WIDTH=4 instance
   (parameter passed via the generated TB), so the differential oracle also varies DEPTH.
   After your change, a FIFO that hardcodes 8 entries / 3-bit pointers MUST fail (verify
   with the exploit below). Add a `broken/hardcoded_depth.v` variant (ignores DEPTH,
   hardcodes 8) with expected.yaml max_reward 0.2, proving the coverage works.
2. **barrel_shifter WIDTH enforcement.** In tb_hidden.v (and oracle vectors) add WIDTH=5
   cases that distinguish `distance % 5` from `shift_amt[2:0]`: rotate-left and rotate-
   right by 8 and by 9 at WIDTH=5 (8%5=3, 9%5=4, but 8&7=0, 9&7=1 → different results),
   and logical shifts with distance ≥5 (must yield 0, but low-3-bits would not). Add a
   `broken/low3bits.v` variant (uses only shift_amt[2:0]) with expected.yaml max_reward
   0.2, proving the new coverage catches it.

## Verification (report it)
For BOTH tasks: ref passes tb_visible + tb_hidden; oracle ref-vs-ref passes seeds 1–3
(including the new parameter instance) and with a mangled ref copy; every broken variant
(including your two new ones) dies at its expected rung. Then from repo root
`RTL_GYM_TOOLS=... make smoke-test` green (34 existing + your 2 new broken cases = 36).
CRUCIAL regression proof, include in report:
- sync_fifo hardcoded-8 design → now reward ≤0.2 (was 0.97). Test with a design that
  hardcodes `reg [7:0] mem[0:7]; reg[2:0] head,tail; count==8`.
- barrel low-3-bits design → now reward ≤0.2.

## Constraints
No subagents, no network. Verilog-2005, timescale 1ns/1ps. Cannot commit; intended message:
`campaign/param-coverage: enforce DEPTH/WIDTH parameterization in fifo + barrel hidden TBs and oracles`.
Final report: standard JSON shape; put the two regression rewards (before→after) in
live_smoke.observed.
