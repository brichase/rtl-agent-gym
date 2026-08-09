# Task: benchmark tasks batch 2 — rr_arbiter, uart_tx, axi_lite_regs

Same contract and quality bar as batch 1 (tasks/barrel_shifter etc., now on main, are
your worked examples — match their structure, TB protocol, oracle CLI, broken/ layout,
and the module-name-discovery rule in docs/CONTRACTS.md §oracle exactly).

## Environment
Branch `campaign/tasks-batch2`, worktree `/data/projects/rtl-agent-gym/.worktrees/tasks-batch2`.
Tools: /data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin (not on PATH).
Python: /data/projects/rtl-agent-gym/venv/bin/python. Verilog-2005, `timescale 1ns/1ps`.

## Owned files
`tasks/rr_arbiter/**`, `tasks/uart_tx/**`, `tasks/axi_lite_regs/**` — each the full
layout: task.yaml, spec.md, interface.v, tb_visible.v, tb_hidden.v, oracle.py, ref/ref.v,
broken/{stub,off_by_one,wrong_reset}.v + expected.yaml.
Excluded: everything else (env/, agent/, eval/, existing tasks/, Makefile, redteam/, docs/).

## Design requirements (plan §3 failure modes)
- **rr_arbiter** (fairness over time): 4 req lines, 4 one-hot grant lines, sync
  active-low reset. Round-robin: priority rotates to the requester after the last grant.
  Spec must pin: behavior with no requests (no grant), grant timing (combinational vs
  registered — pick registered, one grant max per cycle), rotation rule after idle
  cycles. Hidden TB: all-requesters-contending fairness over 4+ full rotations,
  single-requester monopoly, back-to-back handoff, reset mid-rotation, request
  deassertion between grants. Oracle: random request patterns incl. bursts and idle,
  cycle-compare grants vs ref.
- **uart_tx** (protocol timing): 8N1 serial transmitter, CLKS_PER_BIT parameter
  (default 16). Ports: clk, rst_n, tx_start, tx_data[7:0], tx_serial, tx_busy. Spec pins:
  idle high, start bit low, LSB-first data, stop bit high, busy asserted during frame,
  tx_start ignored while busy, exact bit timing in clocks. Hidden TB: bit-level timing
  check at every CLKS_PER_BIT boundary, LSB order (asymmetric byte like 8'h5A),
  back-to-back frames, start pulse mid-frame ignored, reset mid-frame returns line high +
  busy low, CLKS_PER_BIT=4 second instantiation. Oracle: random bytes with random gaps,
  sample tx_serial every clock, cycle-compare vs ref.
- **axi_lite_regs** (handshake protocol, the hard one): AXI4-Lite subordinate, four
  32-bit R/W registers at word addresses 0x0,0x4,0x8,0xC. Channels: AW, W, B, AR, R with
  standard valid/ready. Spec pins: independent AW/W arrival order (write executes when
  both have landed), B response after write, R data+response, OKAY resp everywhere,
  reads of the 4 registers, DECERR or reserved-address behavior (pick: addresses beyond
  0xC return SLVERR on B/R — spec it), reset deasserts all valids, WSTRB honored
  byte-wise. Hidden TB: AW-before-W, W-before-AW, simultaneous, back-to-back writes,
  read-after-write same cycle as B, delayed ready on B/R (master stalls), WSTRB partial
  writes, SLVERR path, reset mid-transaction. Oracle: randomized transaction sequences
  with independent per-channel delays (0–3 cycles) on both directions, compare at
  transaction level (addr, data, resp order per channel) vs ref; note compare_mode:
  transaction in task.yaml.
- Every hidden-TB check traces to a spec.md sentence. No gotchas. Broken variants:
  stub fails visible; off_by_one passes visible, dies hidden/oracle (e.g. arbiter that
  never rotates past requester 2, uart_tx MSB-first, axi write executing on AW alone);
  wrong_reset dies hidden.

## Verification (report it)
Batch-1's sweep pattern: per task — ref passes tb_visible + tb_hidden; broken variants
die exactly per expected.yaml; oracle ref-vs-ref passes seeds 1–3 AND with a mangled
ref copy (module renamed ref_deadbeef); oracle catches off_by_one; yosys synth succeeds
on every ref. THEN from worktree root: `RTL_GYM_TOOLS=... make smoke-test` must be green
for your three tasks (grade.py ladder: refs ≥0.95, broken variants at their rungs).

## Constraints
No subagents, no network. Cannot commit; intended message:
`campaign/tasks-batch2: rr_arbiter, uart_tx, axi_lite_regs with hidden TBs + oracles`.
Final report: same JSON shape as batch 1 (status, branch, files_changed, verify_cmd,
verify_result{passed,output_tail}, live_smoke{...}, blockers).
