# rtl-agent-gym — Module Contracts

Authoritative interface spec between `env/`, `tasks/`, `redteam/`, `agent/`, and `eval/`.
Workers build to this; deviations require conductor sign-off. The design rationale lives
in `rtl-agent-gym-weekend-plan-v2.md` (§2–§5) — read it first.

## Toolchain

Absolute path (gitignored, already installed):
`/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin` — provides `iverilog`, `vvp`, `yosys`.
All code resolves tools via env var `RTL_GYM_TOOLS` falling back to that path. Never assume
tools are on PATH. Record versions (`iverilog -V | head -1`, `yosys --version`) into results rows.

Python: 3.11+ stdlib + `pyyaml`; `anthropic` only inside `agent/`. venv at `./venv`.

## Directory layout per task

```
tasks/<name>/
  task.yaml        # metadata, see schema below
  spec.md          # the prompt-facing spec the agent sees
  interface.v      # module stub with ports only (agent fills body)
  tb_visible.v     # 3–5 basic cases; agent-facing feedback loop
  tb_hidden.v      # corner cases; never shown to agent
  oracle.py        # randomized transaction-sequence differential check
  ref/ref.v        # reference implementation
  broken/          # grader-validation variants, each with expected rung
    stub.v  off_by_one.v  wrong_reset.v
    expected.yaml  # {stub: {max_reward: 0.1}, off_by_one: {...}, ...}
```

## task.yaml schema

```yaml
name: gray_counter          # == directory name
top_module: gray_counter    # module the agent must implement (matches interface.v)
kind: sequential            # combinational | sequential
compare_mode: cycle         # cycle | transaction  (oracle comparison granularity)
clock: clk                  # omit for combinational
reset: {signal: rst_n, active: low, sync: true}   # omit for combinational
area_floor_cells: 8         # sanity: synthesized cell count must be >= this
sim_timeout_s: 30
oracle_runs: 3              # distinct seeds per grading
```

## Testbench protocol (visible and hidden)

- Self-contained iverilog-compatible Verilog-2005. Instantiates `top_module` by name.
- On each failing check: `$display("TB_FAIL: <short reason>")`.
- At end, if zero failures: `$display("TB_ALL_PASS")`. Always `$finish`.
- grade.py verdict: pass ⇔ stdout contains `TB_ALL_PASS` and no `TB_FAIL`.
- TBs must not read files, use hierarchical refs into the DUT, or depend on X-optimism:
  compare with `!==` / `===` so X/Z never counts as a match.

## oracle.py CLI contract

```
python3 oracle.py --rtl <agent.v> --ref <ref.v> --seed <int> --workdir <dir> [--tools <bindir>]
```
- Generates a randomized transaction sequence (reset phases, bursts, idle gaps, boundary
  events per task), drives agent RTL and reference identically, compares per compare_mode.
- The reference module name MUST be discovered by parsing the first `module <name>` in
  the `--ref` file — never assumed equal to task.yaml `top_module`. grade.py hands the
  oracle a mangled copy (`ref_<8hex>.v`, module renamed) so submissions can't name it.
  The agent RTL keeps the task's top_module name.
- Exit 0 = match, 1 = mismatch, 2 = infrastructure error.
- Last stdout line: JSON `{"pass": bool, "seed": N, "checked": <n_cycles_or_txns>, "first_mismatch": <str|null>}`.
- Combinational task #1 may use random vectors; all others use sequences.
- May use a small Python golden model instead of ref.v where noted in task.yaml.

## grade.py CLI + ladder

```
python3 -m env.grade --task <name> --rtl <file.v> --json-out <path>
```
Gated ladder (plan §4): compile fail→0 · visible fail→0.1 · hidden fail→0.2 ·
oracle/sanity fail→0.2 + `flagged: true` · all pass→ 0.7 + 0.3*cost_score.

`cost_score = clamp(2 − (area_norm + depth_norm)/2, 0, 1)`;
`area_norm = agent_cells / ref_cells`, `depth_norm = agent_depth / ref_depth`.
Area = total cell count from `yosys 'synth; stat'`; depth = longest topological path from
`yosys 'synth; ltp -noff'`. Identical flow for agent and ref, computed fresh both sides.

Sanity checks: cell count ≥ area_floor_cells; reject `initial` blocks driving outputs in
the submission (regex + AST-lite check is fine); reject hierarchical references and
`` `include ``/`$readmem` in submissions.

Output JSON: `{task, compile_ok, visible_pass, hidden_pass, oracle_pass, sanity_ok,
area_cells, ref_cells, area_norm, depth, ref_depth, depth_norm, cost_score, reward,
flagged, fail_reason, stage_logs: {...truncated stdout per stage...}}`.

## sandbox.py

Every compile/sim/synth runs in a fresh temp dir containing only the files that step
needs. Per-step wall-clock timeout (task.yaml `sim_timeout_s`, default 30), kill process
group on expiry. Stdout/stderr captured, truncated at 64 KiB with a `[truncated]` marker.
Reference file/module name mangled per run (`ref_<8hex>.v`, module renamed to match) so
submissions can't name it. No network use by graded code.

## env/tools.py (agent-facing)

- `run_sim(rtl: str) -> {compile_ok, stdout, passed}` — compile + tb_visible only.
- `run_synth(rtl: str) -> {ok, cells, depth, stdout}` — yosys stat + ltp.
- `submit(rtl: str) -> {accepted: true}` — records final submission, ends episode.
All routed through `latency.py`: wall-clock ms per call + SHA-256(content)→result cache.

## redteam layout

```
redteam/<attack_name>/
  submission.v     # or submission template + note which task it targets
  expected.yaml    # {task: <name>, expect: {max_reward: 0.2, flagged: true|false, ...}}
```
`make smoke-test` runs: every task's ref (expect reward ≥ 0.95), every broken/ variant
(expect its rung), every redteam submission (expect its verdict) — zero API calls,
non-zero exit on any mismatch, summary table to stdout.

## Results row (eval phase, one JSONL line per episode)

`task, model_id, condition(single_shot|agentic), trial, compile_ok, visible_pass,
hidden_pass, oracle_pass, sanity_ok, area_norm, depth_norm, reward, turns, tool_calls,
tokens_in, tokens_out, cost_usd, latency_ms_per_call, cache_hits, tool_versions,
prompt_hash, timestamp`

## Conventions

- Python: stdlib + pyyaml only outside `agent/`; type hints; no framework; small modules.
- Verilog: 2005 subset iverilog accepts; `timescale 1ns/1ps`; active task convention
  documented per task in spec.md.
- Every module importable and runnable standalone (`python3 -m env.grade ...`).
- Determinism: all randomness seeded; seeds recorded in outputs.
