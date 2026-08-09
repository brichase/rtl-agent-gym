# Review batch 2 — hidden TBs + oracles for tasks 3, 5, 6

Same bar as batch 1. All three passed automated checks (refs 1.000, every broken variant
on its predicted rung, oracles catch off-by-ones, smoke 34/34 green). Conductor reviewed
independently — no bugs found; judgment calls flagged ⚑. ~15 min.

The three tasks that probe *protocol* behavior, where "functionally correct" has the most
room for legitimate disagreement — so your DV eye matters most here.

---

## 3. rr_arbiter — `tasks/rr_arbiter/` (fairness over time)

**Spec**: 4 req → 4 one-hot grant, **registered** (grant appears the edge after sampling).
Round-robin: remembered position = last granted index; search starts immediately after it.
Idle cycle → no grant, position unchanged (priority resumes where it left off). Sync
active-low reset initializes remembered position to **3**, so requester 0 is first
priority after reset.

**Hidden TB** (86 lines): 4+ full rotations with all lines contending (fairness),
single-requester monopoly, back-to-back handoff, request deassertion between grants,
reset mid-rotation.

⚑ **The one real design decision**: reset sets remembered-position = 3 (→ 0 first). That's
a defensible convention but *is* a convention — an implementer could reasonably pick
"position = 0 → requester 1 first." It's pinned unambiguously in spec.md:20-22, so it's
spec-traceable, not a gotcha. Confirm you're happy with that specific choice (it's the
kind of thing where the ref and hidden TB must agree, and they do).

⚑ Registered (not combinational) grant is a real fork too — spec.md:6-8 pins it. A
combinational-grant arbiter is also a valid design in the abstract; we grade registered.
Confirm.

## 5. uart_tx — `tasks/uart_tx/` (protocol timing)

**Spec**: 8N1, CLKS_PER_BIT param (default 16, ≥2). Idle high; tx_start while idle
captures tx_data, drops start bit, asserts tx_busy; **LSB-first** data[0]→data[7]; high
stop bit; each bit held exactly CLKS_PER_BIT rising-edge intervals; tx_start ignored
while busy; sync active-low reset → line high, busy low.

**Hidden TB** (136 lines): bit-level sampling at every CLKS_PER_BIT boundary, asymmetric
byte (LSB-order proof), back-to-back frames, tx_start pulse mid-frame ignored, reset
mid-frame, **CLKS_PER_BIT=4** second instantiation (catches hardcoded-16 timing).

⚑ Timing definition (spec.md:12-16): "the acceptance edge begins the first start-bit
interval; the serial output first advances to data bit 0 exactly CLKS_PER_BIT rising
edges later." This is the precise phase contract — everything hangs on it. It's internally
consistent and the ref matches, but it's the sentence most worth your eyes: is this the
bit-phase convention you'd grade against? (Alternative conventions shift everything by one
interval; ref + hidden TB + oracle are mutually consistent under this one.)

## 6. axi_lite_regs — `tasks/axi_lite_regs/` (handshake protocol — the hard one)

**Spec** (34 lines, the densest): AXI4-Lite subordinate, 4×32-bit regs at 0x0/4/8/C.
Independent AW/W (accept either first, execute write only when both landed), WSTRB
byte-wise, B response held to handshake, AR→R with data+resp held to handshake, reads
independent of B channel, SLVERR on any other/unaligned/upper-bits address, sync reset
clears regs + discards half-transactions + drops valids.

**Hidden TB** (with inline reference model): AW-before-W, W-before-AW, simultaneous +
earliest-legal back-to-back write, **read-after-write while B pending**, WSTRB partial
writes preserve unselected bytes, invalid+unaligned → SLVERR + no modify, reset between
edges (valids unchanged until edge), reset discarding a pending W half.

⚑ **The subtle correctness call** (spec.md:27-29): "A read accepted on the same edge that
changes a register observes the register's value from *before* that edge; a read on a
later edge, including while the B response is pending, observes the new value." This is the
read/write ordering semantics — the single hardest thing to get right in an AXI-Lite
subordinate and the exact reason this task is task 6. The ref and hidden TB implement
read-old-on-same-edge. Confirm this is the ordering you want to grade (it's the standard
"register updates are visible next cycle" semantics; the alternative — read sees the new
value same-edge — is generally wrong for a registered design, but worth your explicit OK).

⚑ SLVERR (not DECERR) chosen for bad addresses (spec.md:19-21). Both appear in real
AXI-Lite; spec pins SLVERR. Confirm.

**Oracle**: transaction-level comparison (compare_mode: transaction) with independent
per-channel 0–3 cycle delays on both directions vs the mangled ref — this is the one task
where cycle-by-cycle would be too rigid (legal handshake stalls vary the timing), so it
compares the ordered (addr, data, resp) transaction stream instead. Confirm you're happy
with transaction-level rather than cycle-level grading here.

---

## Questions for you

1. rr_arbiter: OK to grade **registered grant** + **reset→position 3** as the required
   convention?
2. uart_tx: is the bit-phase timing contract (spec.md:12-16) the one you'd grade?
3. axi_lite_regs: OK with **read-old-value-on-same-edge** ordering and **SLVERR** for bad
   addresses?
4. axi_lite_regs: transaction-level oracle comparison acceptable (vs cycle-level)?
5. Anything to add to hidden coverage before eval numbers?

Reply "batch 2 approved" or with per-task fixes. Files:
`tasks/{rr_arbiter,uart_tx,axi_lite_regs}/{spec.md,tb_hidden.v,oracle.py}`
