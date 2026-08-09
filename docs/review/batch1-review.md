# Review batch 1 — hidden TBs + oracles for tasks 1, 2, 4

Your DV judgment is the quality bar (plan §3): a buggy hidden TB poisons every
downstream number. Everything below has passed automated checks (refs 1.0, broken
variants on predicted rungs, oracle differentials catch off-by-ones on 3 seeds);
what automation can't decide is whether the *checks themselves* test the right thing.
~15 min: skim each TB with the notes below, answer the questions at the end.

Conductor's independent review found no bugs; flags worth your eyes are marked ⚑.

---

## 1. barrel_shifter — `tasks/barrel_shifter/`

**Spec**: WIDTH-parameterized (default 8); `shift_amt` is WIDTH bits, full unsigned
value semantics; modes 00=LSL, 01=LSR (vacated bits zero, distance ≥ WIDTH → all
zeros), 10=ROL, 11=ROR (distance mod WIDTH).

**Hidden TB** (`tb_hidden.v`, 94 lines): two DUTs — WIDTH=8 and **WIDTH=5**
(non-power-of-2, so `amt % WIDTH` ≠ truncating to log2 bits — kills the common
`shift_amt[2:0]` shortcut). Corners: distance 0 (all modes), WIDTH−1, ≥ WIDTH
(shift→0 vs rotate→mod), all-ones/all-zeros, distance 9 rotates on WIDTH=8.

⚑ Check: are you happy that shift semantics for `shift_amt` up to 255 (full 8-bit
value, not just 0..8) are pinned enough by the "≥ WIDTH → zeros" rule?

**Oracle**: 3-seeded random vectors incl. boundary distances; generates a TB
instantiating agent + (mangled) ref side by side, compares combinationally.

## 2. gray_counter — `tasks/gray_counter/`

**Spec**: internal binary count increments mod 2^N each rising edge with rst_n high;
`gray = bin ^ (bin>>1)`. Synchronous active-low reset, priority over increment,
"changing rst_n between rising edges must not change state."

**Hidden TB** (`tb_hidden.v`, 106 lines): dual instantiation N=4 **and N=3**;
full 16-step wrap with the single-bit-change property asserted on *every* transition
(power-of-two check on `delta`); mid-count reset; **synchronous-reset timing probe** —
asserts rst_n between edges and verifies output doesn't move until the next posedge
(kills async-reset implementations); restart-at-1 after release.

⚑ The TB requires gray==0001 exactly one edge after reset release (spec: increment on
every rising edge with rst_n high — so 0→1). Confirm you're happy this is traceable,
not a gotcha.

**Oracle**: randomized sequences of count-runs (3–18), reset pulses (1–3 cycles),
short resumed runs, ~4-cycle idle segments; cycle-compare vs mangled ref.

## 3. sync_fifo — `tasks/sync_fifo/`

**Spec** (31 lines — the most semantics-dense): DEPTH=8/WIDTH=8; sync active-low
reset → empty=1, full=0, **data_out=0**; write-while-full ignored *unless*
simultaneous read (slot frees); read-while-empty ignored, data_out holds; registered
data_out updated only on successful read; simultaneous rd+wr mid-fill keeps occupancy.

**Hidden TB** (`tb_hidden.v`, 145 lines): inline golden model (head/tail/count) with
`check_model` asserting full, empty, and data_out after every transaction. Corners:
overflow write at full; **rd+wr at full** (accepted both — the subtle one); underflow
read; **rd+wr at empty** (write accepted, read ignored); mid-fill rd+wr; 2×DEPTH+5
wrap traffic; synchronous-reset timing probe (same technique as gray).

⚑ `data_out` must reset to zero and be fully X-free from the first cycle — stricter
than some real-world FIFOs (which leave data_out floating until first read). It IS
spec'd explicitly. Confirm you want that strictness (it forces agents to actually
read the spec; it's also the kind of detail a weak agent fails on).

⚑ Acceptance semantics are "state immediately before the edge" (flags-based, not
next-state) — spec'd at line 12. This is the standard choice; confirm.

**Oracle**: 18–35-op random bursts of (wr,rd,data) incl. deliberate boundary pushes,
reset pulses between bursts, idle gaps; cycle-compare vs mangled ref.

---

## Questions for you

1. Any hidden-TB check you'd call a gotcha rather than spec-traceable? (Plan rule:
   "every hidden-TB check must trace to a spec.md sentence.")
2. Are the sync_fifo simultaneous-op semantics the ones you want to grade against
   (esp. rd+wr at full accepted)?
3. Is 3 oracle seeds per grading enough, or do you want 5 for the FIFO?
4. Anything you want *added* to hidden coverage before eval numbers get generated?

Reply with fixes or "batch 1 approved" (any caveats noted). Files:
`tasks/{barrel_shifter,gray_counter,sync_fifo}/{spec.md,tb_hidden.v,oracle.py}`
