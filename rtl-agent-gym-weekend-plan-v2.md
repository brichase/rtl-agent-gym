# Weekend Project: `rtl-agent-gym` — Plan v2

**A small, adversarially hardened RTL-agent benchmark: 6 verified tasks, a red-teamed grader, synthesis-cost proxy rewards, and a single-shot vs. tool-loop ablation.**

Supersedes v1. Center of gravity moved from task breadth to grader trustworthiness and experimental hygiene — the things a Code RL reviewer actually scrutinizes. This doc is the spec to hand to Claude Code; §3–§7 build directly.

**Claim discipline (use these words, not stronger ones):** "adversarially hardened functional grading with synthesis-cost proxy rewards." Not "PPA," not "ungameable" — those claims get earned by the red-team results or not made.

---

## 1. Scope: in / out

**In:** 6 airtight tasks · sandbox-lite grading · task-specific transaction oracles · red-team suite for the grader · area+depth cost proxy · 2 pinned models × 5 trials · single-shot vs. agentic ablation · token/cost logging · no-API-key smoke test · findings write-up.

**Out (do not build, even if ahead of schedule):** RL training, OpenROAD, UI, async FIFO (zero-delay sim can't exercise CDC — it would look rigorous while proving little), more than 6 tasks, budget-matched ablation conditions, UVM-grade scoreboards/coverage, general-purpose sandbox security. Finish early → deepen the analysis, never widen scope.

---

## 2. Architecture

```
rtl-agent-gym/
├── README.md, Makefile          # make smoke-test runs full grading on refs + red-team suite, no API key
├── env/
│   ├── runner.py                # one episode: task in, transcript + metrics row out
│   ├── tools.py                 # run_sim / run_synth / submit (subprocess, via latency.py)
│   ├── grade.py                 # staged gates + oracle + sanity checks (see §4)
│   ├── sandbox.py               # temp-dir isolation, timeouts, output caps (see §4)
│   └── latency.py               # wall-clock per call + SHA-256 content-hash cache
├── agent/loop.py, prompts.py    # Anthropic tool-use loop; also runs single-shot condition
├── tasks/<name>/                # task.yaml, spec.md, interface.v, tb_visible.v,
│                                #   tb_hidden.v, oracle.py, ref/ref.v
├── redteam/                     # hand-written adversarial submissions + expected verdicts
├── eval/run_eval.py, report.py  # sweep → results.jsonl → markdown tables
└── results/                     # jsonl, transcripts/, hacks/
```

**Toolchain:** OSS CAD Suite (iverilog, yosys; macOS arm64 build), Python 3.11+, `anthropic` SDK. Nothing else.

**Agent tools:** `run_sim(rtl)` (compile + visible TB, returns errors/failures — the feedback loop), `run_synth(rtl)` (yosys `stat`: cell area + logic depth), `submit(rtl)`. All calls timed and cached in `latency.py`; report latency percentiles and cache hit rate.

**Results schema (one JSONL row per episode)** — dimensions separate, scalar computed on top:
`task, model_id, condition(single_shot|agentic), trial, compile_ok, visible_pass, hidden_pass, oracle_pass, sanity_ok, area_norm, depth_norm, reward, turns, tool_calls, tokens_in, tokens_out, cost_usd, latency_ms_per_call, cache_hits, tool_versions, prompt_hash, timestamp`

---

## 3. Task set — exactly 6, spanning distinct failure modes

| # | Task | Failure mode it probes |
|---|------|------------------------|
| 1 | Parameterized barrel shifter | combinational / parameterization |
| 2 | Gray-code counter | simple sequential, reset behavior |
| 3 | Round-robin arbiter (4 req) | sequential fairness over time |
| 4 | Sync FIFO w/ full+empty flags | stateful buffering, pointer wraparound, simultaneous rd+wr |
| 5 | UART transmitter | protocol timing, bit ordering, idle/stop behavior |
| 6 | AXI-Lite register file (4 regs) | handshake protocol, channel independence (the hard one) |

Per task: `spec.md`, `interface.v` stub, `tb_visible.v` (3–5 basic cases), `tb_hidden.v` (corners: reset, back-to-back, wraparound, boundary), `oracle.py` + stimulus generator, `ref/ref.v`. Claude Code drafts all of it; **you personally review every hidden TB and oracle — your DV judgment is the quality bar, and a buggy hidden test poisons every downstream number.** Add a 7th/8th task only after all 6 grade cleanly, and only if trivially verifiable.

---

## 4. Grading spec (the part reviewers scrutinize)

**Sandbox-lite (`sandbox.py`)** — proportionate to the threat model (a model doing a task, not a hostile user): grade in a fresh temp dir containing only the agent RTL + the files that grading step needs; wall-clock timeout per sim (default 30 s — accidental infinite loops are common); cap stdout/file output; mangle the reference module/file name per run so hierarchical references and includes can't find it. No process jails, no memory limits — the red-team suite (§5) empirically tests whether this is enough.

**Staged, gated ladder (`grade.py`):**

```
compile fails                          → R = 0
compiles, visible TB fails             → R = 0.1
visible passes, hidden TB fails        → R = 0.2
hidden passes, oracle/sanity fails     → R = 0.2  (flag for transcript review — likely a hack)
all gates pass                         → R = 0.7 + 0.3 * cost_score
```

**Oracle (anti-hardcoding), task-specific:** randomized **transaction sequences** (not vectors) — reset phases, bursts, idle gaps, boundary events — driven identically into agent RTL and reference (or a small Python golden model), compared cycle-by-cycle or at transaction level per `task.yaml`. Combinational task #1 may use random vectors; everything else gets sequences. Small golden models, not UVM scoreboards.

**Sanity checks — framed in the README as "defenses motivated by observed attacks," never as making the reward ungameable:** synthesized cell count above per-task floor (catches constant-output stubs); no `initial`-block output forcing; no references outside the module's own scope.

**Synthesis-cost proxy (not "PPA"):** `area_norm = agent_area / ref_area`, `depth_norm = agent_depth / ref_depth` (yosys stat; both reported raw in every row). Scalar: `cost_score = clamp(2 − (area_norm + depth_norm)/2, 0, 1)` — **reference parity = 1.0 exactly**, better-than-ref earns nothing extra (cap), 2× worse = 0. Include depth from day one: area-only reward invites slow serialized logic — say so in the README, and check the data for whether depth pressure actually appears.

---

## 5. Red-team the grader (the memorable section)

Before running any agent evals, hand-write ~7 adversarial submissions in `redteam/`, each with an expected verdict, run by `make smoke-test`:

1. Constant outputs tuned to pass weak visible tests
2. Hardcoded lookup of the visible TB's exact stimulus
3. Hierarchical reference into TB/reference scope
4. `` `include ``/`$readmem` attempt to read grader files
5. Zero-time infinite loop (hangs the simulator)
6. Massive `$display` output flood
7. X/Z output exploitation (does the checker treat X as match?)

README section: *"Red-team results: N attempted grader exploits, X blocked initially, Y exposed weaknesses, all mitigated."* Finding weaknesses is the good outcome — "before evaluating agents, I adversarially evaluated the evaluator" is the strongest line in the project.

---

## 6. Evaluation plan

- **2 pinned model IDs** (one small, one strong tier) × **6 tasks × 5 independent trials** (call them trials, not seeds) × **2 conditions**: single-shot (one generation, no tools) vs. agentic (tool loop, `max_turns` 8–10). Single-shot is cheap; run it on all 6 tasks. ≈ 120 graded episodes + agent turns — roughly $15–50.
- Report **counts** (e.g., 4/5) alongside rates; pass@1 and pass@5; mean turns; raw area/depth on solved tasks; tokens and cost per episode. No significance claims from 5 trials — phrase differences as observations.
- **Headline result:** the single-shot → agentic delta per model. That demonstrates the *environment* adds value, not just model knowledge. Token/cost columns disclose the confound (agentic spends more); one success-vs-cost scatter is sufficient rigor — no budget-matched conditions.
- Every episode that trips the oracle/sanity flag or shows gaming behavior → transcript saved to `results/hacks/` verbatim. One clean reward-hack example leads the findings.

---

## 7. Plan of action — the weekend

**Friday eve (2 h) — de-risk + grader skeleton.** Install OSS CAD Suite; verify iverilog/yosys; 5-line SDK call works. Hand-run one manual episode (tiny adder: ref, TB, sim, `yosys stat`). **Milestone: grading pipeline runs standalone on a known-good and a known-broken design and returns the right rungs of the ladder.**

**Sat AM (3–4 h) — core + 3 tasks, grade the grader.** Claude Code builds `env/` + tasks 1, 2, 4 (combinational, simple sequential, stateful). For each: ref scores 1.0; a stub, an off-by-one, and a wrong-reset variant land on the correct rungs. **Milestone: `make smoke-test` green with zero API calls.**

**Sat PM (3–4 h) — agent loop + baseline + pilot.** Build `agent/loop.py` with full metrics logging from the first run (retrofitting logging is how weekends die). Single-shot condition is the same code with `max_turns=1` and no tools. **Milestone: 3-task × 2-condition × 1-trial pilot on the small model; inspect transcripts; confirm the metric discriminates.**

**Sun AM (3 h) — remaining 3 tasks + red team.** Add tasks 3, 5, 6 (you review hidden TBs/oracles). Write the 7 red-team submissions; run them; fix what breaks; record before/after verdicts. Add depth metric + caching if not already in. **Milestone: full unattended eval of one model completes.**

**Sun PM (3–4 h) — main eval + findings.** Launch the full sweep; write the README *yourself* while it runs: what/why mapped to the posting, quickstart + smoke test, grading and reward-design rationale, red-team results table, eval results, **findings** (2–3 real failure analyses, any hack transcript, whether area/depth pressure shows up), limitations, "next steps with production EDA tools and real RL." **Milestone: README with real numbers.**

**Sun eve (1 h) — ship.** Fresh-clone reproducibility check (`make smoke-test` on a clean machine/venv), MIT license, pin repo, resume bullet to me.

**Fallback order (cut top-first):** task 6 (AXI-Lite) → 5 trials down to 3 → task 5 (UART). **Never cut:** two models, two conditions, the red-team suite, the write-up hours. Four bulletproof tasks under two models and two conditions with a red-teamed grader beats six tasks under one condition.

---

## 8. Deliverables checklist

- [ ] Public repo, MIT, pinned; `make smoke-test` passes with no API key
- [ ] README: red-team results table, eval tables with counts, 2–3 failure analyses, cost/latency stats
- [ ] Saved transcripts: at least one feedback-driven fix; any reward-hack verbatim in `results/hacks/`
- [ ] Versions pinned in every results row (model IDs, tool versions, prompt hash)
- [ ] Resume bullet + link

**Draft resume bullet (v2):**
> Built *rtl-agent-gym* (open source): an agentic RTL-generation benchmark with adversarially hardened grading — hidden testbenches, randomized transaction-sequence oracles vs. reference designs (Icarus Verilog), and synthesis-cost proxy rewards (Yosys area + logic depth). Red-teamed the grader with hand-built exploit submissions before trusting it; evaluated two Claude models (5 trials/task) with a single-shot vs. tool-loop ablation isolating the environment's contribution.

**Build-with-Claude-Code note:** feature it, don't hide it. Yours unmistakably: the reward design decisions, hidden TB/oracle review, red-team attack ideas, and the findings write-up.
