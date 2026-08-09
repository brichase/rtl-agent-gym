# Task: benchmark tasks batch 1 — barrel_shifter, gray_counter, sync_fifo

## Goal
Author three complete benchmark tasks under `tasks/`: parameterized barrel shifter
(combinational), Gray-code counter (simple sequential + reset), synchronous FIFO with
full/empty flags (stateful, pointer wraparound, simultaneous rd+wr). Each task fully
follows the layout and protocols in `docs/CONTRACTS.md`. These are graded artifacts:
hidden-TB and oracle quality is the product.

## Read first (in your worktree root)
1. `docs/CONTRACTS.md` — binding: task layout, task.yaml schema, TB protocol
   (TB_FAIL/TB_ALL_PASS, `!==` comparisons, no hierarchical refs, no file I/O),
   oracle.py CLI contract, broken/ layout.
2. `rtl-agent-gym-weekend-plan-v2.md` §3, §4 — what failure mode each task probes.

## Environment
- Branch: `campaign/tasks-batch1`, worktree: `/data/projects/rtl-agent-gym/.worktrees/tasks-batch1`, base commit `f2b810e`.
- Tools: `/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin` (iverilog, vvp, yosys) — NOT on PATH, use absolute paths or set PATH yourself in your shell.
- Python for oracles: `/data/projects/rtl-agent-gym/venv/bin/python` (3.14, pyyaml). Oracles are stdlib+pyyaml only and must NOT import from `env/` (it may not exist yet).

## Owned files (create)
`tasks/barrel_shifter/**`, `tasks/gray_counter/**`, `tasks/sync_fifo/**`, each exactly:
`task.yaml, spec.md, interface.v, tb_visible.v, tb_hidden.v, oracle.py, ref/ref.v,
broken/stub.v, broken/off_by_one.v, broken/wrong_reset.v (sequential tasks only),
broken/expected.yaml`

## Excluded (sibling workers own these — do not create or modify)
`env/**`, `redteam/**`, `agent/**`, `eval/**`, `Makefile`, `README.md`, `docs/campaign-hq/**`

## Design requirements
- **barrel_shifter**: parameterized WIDTH (default 8) and shift-amount port; modes: logical
  left/right + rotate (define precisely in spec.md). task.yaml: kind=combinational,
  compare_mode=cycle; the oracle drives random vectors (the contract allows vectors for
  the one combinational task) including boundary shift amounts. Hidden TB corners: shift
  by 0, by WIDTH-1, all-ones/all-zeros patterns, every mode.
- **gray_counter**: N-bit (default 4) Gray-code counter, synchronous active-low reset per
  task.yaml. Hidden TB corners: reset mid-count, wraparound (full cycle back to 0),
  single-bit-change property checked across every transition.
- **sync_fifo**: DEPTH=8, WIDTH=8, full/empty flags, no data loss/dup. Hidden TB corners:
  reset, fill to full + overflow-write attempt, drain to empty + underflow-read attempt,
  pointer wraparound (>2× depth traffic), simultaneous read+write at full, at empty, and
  mid-fill. Spec.md must state the exact semantics you test (e.g. write-while-full is
  ignored, read-while-empty is ignored, simultaneous rd+wr while full/empty behavior).
- Specs must be unambiguous enough that an expert could implement to them and pass the
  hidden TB — every hidden-TB check must trace to a spec.md sentence. No trick gotchas.
- Oracles: gray_counter and sync_fifo use randomized transaction sequences (reset phases,
  bursts, idle gaps, boundary events) against ref.v (or a small Python golden model —
  note it in task.yaml with `golden: python`), compared per compare_mode. Seeded,
  reproducible, ~3 distinct seeds meaningful. Barrel shifter: random vectors incl.
  boundary shift amounts.
- broken/ variants: stub.v = compiles, constant/trivially wrong outputs (should die at
  visible or hidden TB); off_by_one.v = subtle (wrong flag threshold, wrong shift edge,
  wrong wrap point — should pass visible TB but die at hidden TB or oracle); wrong_reset.v
  = wrong polarity/async-vs-sync (sequential tasks; must die at hidden TB or oracle).
  expected.yaml per CONTRACTS.md: for each variant the max rung it may reach
  (`{stub: {max_reward: 0.1}, off_by_one: {max_reward: 0.2}, wrong_reset: {max_reward: 0.2}}`
  — tighten per task to what you verify actually happens).

## Verification (run from worktree root; goes in your report)
For every task, using TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin:
1. `$TOOLS/iverilog -g2005 -o /tmp/t.vvp ref/ref.v tb_visible.v && $TOOLS/vvp /tmp/t.vvp` → prints TB_ALL_PASS, no TB_FAIL.
2. Same with tb_hidden.v → TB_ALL_PASS.
3. Every broken variant against tb_visible + tb_hidden → dies exactly where expected.yaml says (stub fails visible; off_by_one passes visible but fails hidden/oracle; wrong_reset fails hidden).
4. `oracle.py --rtl ref/ref.v --ref ref/ref.v --seed 1..3 --workdir /tmp/o` → pass;
   `oracle.py --rtl broken/off_by_one.v --ref ref/ref.v --seed 1..3` → fail (mismatch reported).
5. `$TOOLS/yosys -QT -p 'read_verilog ref/ref.v; synth; stat'` succeeds for every ref.
Write a small throwaway script for this sweep and include its summary output in the report. A broken variant that does not die where predicted is a bug in your task — fix the TB/oracle or the variant until behavior matches expected.yaml.

## Live smoke
The verification sweep IS the live smoke; report cmd + expected + observed summary
(per-task table: ref-visible/ref-hidden/broken-behavior/oracle-differential all ✓).

## Constraints
- Do not spawn subagents. No network. `timescale 1ns/1ps` everywhere. Verilog-2005 only.
- You cannot commit (`.git` read-only). Report intended commit message:
  `campaign/tasks-batch1: barrel_shifter, gray_counter, sync_fifo with hidden TBs + oracles`.

## Final report (print last, JSON)
{"status": "done|partial|blocked", "branch": "campaign/tasks-batch1", "commit": "",
 "files_changed": [...], "verify_cmd": "...", "verify_result": {"passed": bool,
 "output_tail": "..."}, "live_smoke": {"cmd": "...", "expected": "...", "observed":
 "per-task summary table", "passed": bool}, "blockers": [...]}
