# Task: AXI-Lite oracle robustness + same-edge coverage

## Why
A review found the AXI-Lite evaluator is over-constrained on timing in a way that could
reject LEGAL implementations, and under-covered on the spec's hardest guarantee. Two fixes,
both preserving the AXI4-Lite spec (do NOT change spec.md semantics, only the
evaluator/tests):

1. The spec says the subordinate MAY apply backpressure, and AW/W are INDEPENDENT channels.
   But the hidden TB requires AWREADY/WREADY high on the first offered edge, and the oracle
   compares AW-vs-W handshake ORDER. A legal design that accepts W before AW (or stalls
   ready a cycle) while the reference does the opposite could be wrongly rejected.
2. The spec's same-edge read/write ordering (read accepted on the edge a register changes
   observes the OLD value; a later read observes NEW) is stated but not directly exercised.

## Environment
Branch `campaign/axi-oracle`, worktree `/data/projects/rtl-agent-gym/.worktrees/axi-oracle`, base fc207c8.
Tools: /data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin. Python: /data/projects/rtl-agent-gym/venv/bin/python.

## Owned files
`tasks/axi_lite_regs/**` ONLY. Do NOT touch other tasks or the harness.

## Work items
1. **Relax the oracle to semantic comparison.** Rework oracle.py so it:
   - Drives both agent and (mangled) reference with the SAME randomized transactions but
     tolerates each side's own backpressure: wait for READY with a BOUNDED timeout
     (e.g. 64 cycles) rather than assuming immediate READY; hold VALID + payload stable
     while waiting (and check the DUT does too).
   - Compares SEMANTIC OUTCOMES only: the multiset/sequence of B responses, R data+resp
     per read, and final readback of all four registers — NOT the relative cycle or the
     AW-vs-W handshake order. Two designs that differ only in stall timing or AW/W
     acceptance order but produce identical register/response results must BOTH pass.
   - Keep checking protocol stability: VALID must not drop and payload must not change
     while awaiting READY (that is still a real bug to catch).
2. **Hidden TB coverage.** In tb_hidden.v add:
   - Same-edge read-old: register = OLD; issue AW+W (new value) and AR (same register) so
     they transact on the same edge; assert R returns OLD; a subsequent read returns NEW.
   - Backpressure/order equivalence is an ORACLE concern (item 1); but ALSO add a hidden
     case where the master delays BREADY/RREADY several cycles and the DUT must hold the
     response stable — verifying cross-direction independence (a read answered while a B
     is stalled). Optionally add "write while an R response is stalled."
   Every added check must trace to a spec.md sentence (spec.md already states same-edge
   read-old at ~line 27, backpressure/hold-stable, and read/B independence).

## Verification (report it)
- ref passes tb_visible + tb_hidden; oracle ref-vs-ref passes seeds 1–3 and with a mangled
  ref copy; broken variants still die at expected rungs; off_by_one still caught.
- POSITIVE control: write a SECOND legal reference that accepts W-before-AW and stalls
  each READY by one cycle (semantically identical). The relaxed oracle must PASS it
  (rtl=that design, ref=ref/ref.v). Include this pass in the report — it proves you fixed
  the over-constraint, not just loosened everything.
- NEGATIVE control: a design that returns NEW value on same-edge read must still FAIL
  (the coverage you added). Include it.
- `RTL_GYM_TOOLS=... make smoke-test` still green for axi_lite_regs.

## Constraints
No subagents, no network. Cannot commit; intended message:
`campaign/axi-oracle: semantic (stall-tolerant) oracle + same-edge/backpressure hidden coverage`.
Final report: standard JSON shape; put the positive+negative control results in
live_smoke.observed.
