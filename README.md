# rtl-agent-gym

**An adversarially hardened benchmark for RTL-generation agents: 6 verified tasks, a red-teamed functional grader, synthesis-cost proxy rewards, and a single-shot vs. tool-loop ablation.**

The claim this project makes, in the exact words it can defend: *adversarially hardened functional grading with synthesis-cost proxy rewards.* Not "PPA," not "ungameable." Those are earned by the red-team results below or not claimed at all.

---

## What it is and why

An agent that writes Verilog is only as trustworthy as the thing that grades it. Most "LLM writes RTL" demos grade with a handful of visible test vectors — which a model can satisfy by memorizing the vectors, emitting constants, or exploiting a lenient checker. `rtl-agent-gym` inverts the usual emphasis: the effort goes into the *grader* and the *experiment*, not task breadth.

Concretely it provides:

- **6 tasks** spanning distinct hardware failure modes (combinational, sequential, stateful buffering, fairness, protocol timing, handshake protocol).
- **Staged functional grading** run in a sandbox: compile → visible tests → hidden tests → randomized transaction-sequence oracle vs. a reference design → sanity checks.
- **A red-team suite** of hand-written adversarial submissions that attack the grader itself, each with an expected verdict, run by `make smoke-test`.
- **Synthesis-cost proxy rewards** from Yosys (cell area + logic depth), so a functionally-correct-but-bloated design scores below a tight one.
- **A single-shot vs. agentic ablation** across two pinned models, isolating what the *tool-loop environment* contributes over raw model knowledge.

Built with Claude Code as an orchestrated campaign (Claude conducting, OpenAI Codex CLI workers implementing). The design decisions — reward shaping, hidden-test and oracle review, red-team attack ideas, the evaluation-integrity fixes, and this write-up — are the human/conductor contribution.

---

## Quickstart

```bash
# 1. Toolchain: OSS CAD Suite (iverilog + yosys), pinned. Point RTL_GYM_TOOLS at its bin/.
export RTL_GYM_TOOLS=/path/to/oss-cad-suite/bin

# 2. Python env at ./venv (the Makefile's default PYTHON; override with PYTHON=...).
#    stdlib + pyyaml is enough for grading:
uv venv venv && uv pip install -p ./venv/bin/python pyyaml
#    or, without uv: python3 -m venv venv && ./venv/bin/pip install pyyaml

# 3. Run the full grader + red-team suite on references and adversarial submissions.
#    NO API KEY REQUIRED — this grades known-good and known-broken designs only.
make smoke-test
```

`make smoke-test` grades every task's reference (expected reward ≥ 0.95), every planted broken variant (expected to land on a specific ladder rung), and every red-team submission (expected to be blocked at a specific gate). It prints a table and exits non-zero on any mismatch. This is the reproducibility anchor: it needs no model, no network, and no key.

Toolchain pinned for the reported numbers: **Icarus Verilog 14.0 (devel, s20260301)**, **Yosys 0.68+40**.

---

## Architecture

```
env/       runner, tools (run_sim/run_synth/submit), grade (staged ladder), sandbox, latency+cache
tasks/     6 tasks: task.yaml, spec.md, interface.v, tb_visible.v, tb_hidden.v, oracle.py, ref/, broken/
redteam/   7 adversarial submissions + expected verdicts
agent/     tool-use episode loop; Anthropic + Codex-CLI backends; stdio MCP tool server
eval/      sweep runner + markdown report generator
results/   full/ (results.jsonl + report), evidence/, hacks/
```

Agent tools (the only interface a model under test gets): `run_sim(rtl)` compiles and runs the *visible* testbench; `run_synth(rtl)` returns Yosys cell area + logic depth; `submit(rtl)` ends the episode. All calls are timed and content-hash cached.

---

## Task set

| # | Task | Failure mode it probes |
|---|------|------------------------|
| 1 | Parameterized barrel shifter | combinational / parameterization |
| 2 | Gray-code counter | simple sequential, reset behavior |
| 3 | Round-robin arbiter (4 req) | sequential fairness over time |
| 4 | Sync FIFO w/ full+empty flags | stateful buffering, pointer wraparound, simultaneous rd+wr |
| 5 | UART transmitter (8N1) | protocol timing, bit ordering, idle/stop |
| 6 | AXI-Lite register file (4 regs) | handshake protocol, channel independence |

Each task's `spec.md` is written so an expert could implement to it and pass the hidden tests — every hidden check traces to a spec sentence, no gotchas. The graded conventions (FIFO simultaneous-op semantics, arbiter reset priority, UART bit-phase, AXI same-edge read ordering and SLVERR) are pinned in each spec and ratified as the contract.

Parameterization is enforced, not assumed: the FIFO is tested at a non-power-of-two `DEPTH=5`/`WIDTH=4` in addition to the default, and the barrel shifter at `WIDTH=5` with rotate distances that distinguish true `mod WIDTH` from the common low-bits shortcut. (A FIFO that ignored `DEPTH` and hardcoded 8 entries previously scored 0.97; it now scores ≤ 0.2.)

---

## Grading

**Sandbox** (`env/sandbox.py`) — proportionate to the threat model (a model doing a task, not a hostile user). Each step runs in a fresh temp dir containing only the files that step needs; per-step wall-clock timeout (default 30 s, process-group kill on expiry); stdout capped at 64 KiB; the reference module and file are renamed per run so a submission cannot name or hierarchically reference them.

**Staged, gated ladder** (`env/grade.py`):

```
compile fails                          → R = 0
compiles, visible tests fail           → R = 0.1
visible passes, hidden tests fail      → R = 0.2
hidden passes, oracle/sanity fails     → R = 0.2  (flagged for transcript review)
all gates pass                         → R = 0.7 + 0.3 * cost_score
```

**Oracle (anti-hardcoding).** Every task except the combinational one is graded by randomized *transaction sequences* — reset phases, bursts, idle gaps, boundary events — driven identically into the agent RTL and the reference, compared cycle-by-cycle (or, for AXI-Lite, at the transaction level, so legal handshake-stall timing differences don't cause false mismatches). Comparisons use `!==`/`===` so X/Z never counts as a match.

**Sanity checks**, framed as defenses motivated by observed attacks: synthesized cell count above a per-task floor (catches constant-output stubs); no `initial`-block output forcing; no hierarchical references or `` `include ``/`$readmem` in a submission.

**Synthesis-cost proxy** (not "PPA"):

```
area_norm  = agent_cells / ref_cells
depth_norm = agent_depth / ref_depth
cost_score = clamp(2 − (area_norm + depth_norm)/2, 0, 1)
```

Reference parity = 1.0 exactly; beating the reference earns nothing extra (capped); 2× worse on the average of area and depth = 0. Depth is included from day one on purpose: an area-only reward invites slow, serialized logic. Both `area_norm` and `depth_norm` are reported raw in every results row so the proxy is auditable.

---

## Red-team results: attacking our own grader

Before evaluating any agent, we adversarially evaluated the *evaluator*. Seven hand-written submissions (`redteam/`) each target a specific grader weakness, with an expected verdict checked by `make smoke-test`. **Finding a weakness is the good outcome.**

| # | Attack | Blocked by | Reward | Weakness? |
|---|--------|-----------|--------|-----------|
| 1 | Constant outputs tuned to the visible tests | visible testbench | 0.1 | no |
| 2 | Hardcoded lookup of the visible stimulus | hidden testbench | 0.2 | no |
| 3 | Hierarchical reference into TB/reference scope | compile (standalone elaboration) | 0.0 | no |
| 4 | `` `include ``/`$readmem` of grader files | sandbox isolation → visible | 0.1 | no |
| 5 | Zero-time infinite loop (hangs the simulator) | wall-clock timeout (suite did not hang) | 0.1 | no |
| 6 | Massive `$display` flood | **see below** | 0.2 | **found → mitigated** |
| 7 | X/Z output vs. an X-optimistic checker | strict `!==` comparison | 0.1 | no |

**The one real finding (attack 6).** A functionally-wrong design that prints `TB_ALL_PASS` and then floods > 64 KiB of text can forge the visible *and* hidden string-match gates, because the sandbox's output cap truncates away the genuine `TB_FAIL` lines. It was caught only by the value-based differential oracle (which compares trace values, not strings, and cannot be flooded), capping its reward at 0.2 flagged — **no attack reached ≥ 0.7.** The finding exposed that the string-match gates were the trustworthy-looking-but-weak layer and the oracle was the real backstop.

**Mitigation:** truncated testbench output now auto-fails the visible/hidden gates (no legitimate run approaches 64 KiB). After the fix, attack 6 fails both string gates directly (`visible_pass=False, hidden_pass=False`) while the reward stays 0.2 flagged. Before/after is preserved in `redteam/06_output_flood/`.

Summary: **7 attempted grader exploits, 6 blocked at their intended gate, 1 exposed a real weakness — now mitigated.**

---

## Evaluation-integrity: closing a reference-data leak

A separate integrity review found that the agent episodes originally launched with the working directory set to the repository root under a read-only sandbox — so a model under test could *read the reference RTL, hidden testbenches, and oracle directly*, and transcripts confirmed it happened. Any agentic-vs-single-shot comparison from that configuration is invalid and is not cited here.

Fix: the agent now runs in an isolated, empty per-episode directory **with the shell tool disabled entirely** — it can call only `run_sim`, `run_synth`, and `submit`, and has no mechanism to read any file. A live canary preflight (`make leakage-check`) plants a secret in the answer area and confirms it never reaches the agent; a `protocol_ok` field flags any episode that attempts an unapproved action. All reported numbers below come from this isolated configuration.

---

## Evaluation

Two pinned models — **`gpt-5.6-luna` (max reasoning)** and **`gpt-5.6-sol` (high reasoning)** — × 6 tasks × 5 trials × 2 conditions (single-shot: one generation, no tools; agentic: tool loop, `max_turns` 10). Counts are reported alongside rates; differences from 5 trials are phrased as observations, not significance claims.

120 episodes, **zero infrastructure errors**, all under the isolated (shell-disabled) backend. Full tables: [`results/full/report.md`](results/full/report.md).

**Both models solve almost everything functionally** — pass@5 is 6/6 tasks for both, in both conditions. So the interesting signal is *not* pass/fail; it is **design quality via the synthesis-cost proxy**, and it is exactly where the tool loop earns its keep.

Pass rates (episodes solved, reward ≥ 0.7):

| Model | Single-shot | Agentic |
|---|---|---|
| `gpt-5.6-luna@max` | 30/30 | 30/30 |
| `gpt-5.6-sol@high` | 29/30 | 30/30 |

The single functional miss: `gpt-5.6-sol@high`, single-shot, `axi_lite_regs`, 1 of 5 trials — see Findings.

**Where the environment adds value — synthesis cost (area_norm / depth_norm, lower is tighter; 1.0 = reference parity):**

| Task | Model | Single-shot area / depth | Agentic area / depth |
|---|---|---|---|
| uart_tx | luna | 1.48 / 0.87 | **0.64 / 0.55** |
| uart_tx | sol | 1.18 / 1.00 | **0.41 / 0.24** |
| sync_fifo | luna | 1.17 / **1.86** | 1.01 / **1.06** |

On the tasks with real implementation freedom (UART, FIFO), the agentic condition — able to call `run_synth` and see cell area and logic depth before submitting — produced dramatically tighter designs than single-shot. On the constrained tasks (Gray counter, arbiter, barrel shifter) both conditions sit at reference parity, as expected: there is nothing to improve.

The token/cost columns disclose the confound — agentic spends ~10× the input tokens (e.g. UART luna: 12.7k single-shot → 146k agentic). The claim is deliberately modest: the environment improves *design quality on tasks that admit it*, at a token cost the tables make visible. No budget-matched condition is claimed.

---

## Findings

**1. The tool loop rescues the hardest task — a real AXI-Lite protocol bug.** The only functional failure in 120 episodes was `gpt-5.6-sol@high`, single-shot, `axi_lite_regs`, trial 1: the design compiled but failed the visible testbench with `TB_FAIL: basic write response valid=0` — it never asserted `BVALID` to complete the write-response (B-channel) handshake, the classic AXI-Lite subordinate mistake. The other four single-shot trials passed, and **all five agentic trials passed** — with `run_sim` feedback, the model saw the failing handshake and fixed it. `first_failure_stage` attribution pinned this to `visible_sim` automatically. This is the ablation's thesis in one data point: on a protocol task, the environment converts a plausible-but-wrong one-shot into a correct design.

**2. Depth pressure is real, and area-only reward would have missed it.** `gpt-5.6-luna@max` single-shot on `sync_fifo` produced a functionally-correct design with `depth_norm = 1.86` — serialized logic, nearly twice the reference's critical-path depth. The agentic run, seeing `run_synth` output, brought it to `1.06`. This is the concrete justification for including logic depth in the cost proxy from day one: an area-only reward would have scored the serialized design well and created exactly the wrong optimization pressure.

**3. Agents beat a non-minimal reference when given synthesis visibility.** On UART, agentic designs reached `area_norm` 0.41–0.64 — i.e. *smaller* than the reference — while still passing all hidden tests and the oracle. Two honest readings: the models are genuinely good at compact UART logic when they can measure it, and the hand-written reference is not minimal. The cost proxy is relative, so "better than reference" caps at reward 1.0; the raw norms in every row keep this visible rather than hidden.

**Reward hacking: a clean null result.** Across all 120 episodes, **zero** tripped the oracle/sanity flag (the signature of passing tests without correct behavior). The models did not game the grader. The one demonstrated reward hack in the project came from red-teaming the grader itself (the output-flood attack), preserved verbatim in [`results/hacks/`](results/hacks/). "The models didn't cheat, and here is the exploit that proves the grader would have caught them if they had" is the honest version of the reward-hacking story.

**Protocol tracking works.** One agentic episode was flagged `protocol_ok=False` for calling a built-in Codex introspection tool (`list_mcp_resources`) — benign, not a file read, and the episode was correct anyway. The flag firing on a harmless deviation is evidence the isolation instrumentation is live, not that anything leaked.

---

## Limitations

- **5 trials** per cell: enough to report counts and observe direction, not to make significance claims.
- **Zero-delay simulation**: no timing/CDC checks; async FIFO deliberately excluded because zero-delay sim can't exercise it.
- **Synthesis-cost proxy, not PPA**: Yosys generic `stat` cell count and logic depth, no real library, no place-and-route.
- **Proportionate sandbox**: temp-dir isolation, timeouts, output caps, and a shell-disabled agent — not a general-purpose security jail. The red-team suite empirically tests whether it's enough for the threat model (a model doing a task).
- **Not budget-matched**: the agentic condition is allowed to spend more; the cost columns disclose it rather than controlling for it.
- **Not a sealed benchmark**: the hidden testbenches, oracles and reference designs are in this repo, so the tasks are not held out and may enter future training data.

## Next steps

Real EDA (OpenROAD/commercial synthesis + PnR for true PPA rewards), timing-annotated simulation to admit CDC tasks, more tasks once each grades cleanly, and using the environment as an RL reward signal rather than an eval harness.

## Reproducing

`make smoke-test` reproduces the entire grader + red-team verification from a fresh clone
(new venv, existing OSS CAD Suite via `RTL_GYM_TOOLS`) with no API key — verified at
36/36. The agent evaluation additionally needs a configured OpenAI Codex CLI login; run
`make leakage-check` first to confirm the isolation before trusting any agentic numbers.

## Build records

`docs/campaign-hq/` and `CLAUDE.md` are the working records of the agent-orchestrated build (plans, worker briefs, learnings), kept for transparency about how the project was made.

## License

MIT — see [LICENSE](LICENSE).
