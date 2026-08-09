# Task: env/ core — sandboxed grading pipeline + Makefile smoke harness

## Goal
Build the grading engine of rtl-agent-gym: `env/sandbox.py`, `env/latency.py`,
`env/tools.py`, `env/grade.py`, `env/runner.py` (stub OK, see below), plus `Makefile`
with a `smoke-test` target, per the authoritative specs. Success = the grading ladder
runs standalone on a known-good and known-broken design and returns the correct rungs,
with zero network/API use.

## Read first (in your worktree root)
1. `docs/CONTRACTS.md` — binding interface contract (task.yaml schema, TB protocol,
   oracle CLI, grade.py CLI + ladder + JSON output, sandbox rules, redteam layout).
2. `rtl-agent-gym-weekend-plan-v2.md` §2, §4 — design rationale. §1 "Out" list is
   binding: no process jails, no memory limits, no UVM, no extra scope.

## Environment
- Branch: `campaign/env-core`, worktree: `/data/projects/rtl-agent-gym/.worktrees/env-core`, base commit `f2b810e`.
- Tools: `/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin` (iverilog, vvp, yosys).
  Resolve via env var `RTL_GYM_TOOLS` with that absolute path as fallback. NOT on PATH.
- Python: 3.14 at `/data/projects/rtl-agent-gym/venv/bin/python` (has pyyaml). Code must
  be stdlib+pyyaml only. Type hints, small modules, no frameworks.

## Owned files (create)
- `env/__init__.py`, `env/sandbox.py`, `env/latency.py`, `env/tools.py`, `env/grade.py`, `env/runner.py`
- `env/fixtures/toy_adder/` — a complete miniature task following the CONTRACTS.md task
  layout (task.yaml, spec.md, interface.v, tb_visible.v, tb_hidden.v, oracle.py, ref/ref.v,
  broken/{stub.v,off_by_one.v}, broken/expected.yaml). 4-bit adder. This is your test
  fixture; real tasks are built by a sibling worker and must not be referenced.
- `env/tests/test_grade.py` — stdlib `unittest`: ref lands reward ≥ 0.95; stub lands 0.1
  or 0.2 with correct gate flags; off_by_one lands its expected rung; a design with an
  infinite loop (`always #0`- or `while(1)`-style zero-time loop, include such a fixture
  file) is killed by the timeout and graded 0/0.1 without hanging the suite.
- `Makefile` — targets: `smoke-test` (discovers every dir under `tasks/` and `redteam/`
  if present — tolerate their absence now — plus `env/fixtures/`, grades refs/broken/
  redteam expectations, prints a summary table, exits non-zero on any mismatch),
  `test` (unittest discovery), `clean`.

## Excluded (sibling workers own these — do not create or modify)
- `tasks/**`, `redteam/**`, `agent/**`, `eval/**`, `README.md`, `docs/campaign-hq/**`

## Implementation notes
- grade.py stages each gate through sandbox.py: fresh temp dir per step, only that step's
  files copied in, per-step timeout (task.yaml `sim_timeout_s`, default 30 s) with process-
  group kill, stdout truncated at 64 KiB.
- Reference mangling: when the oracle stage needs ref.v alongside the submission, copy it
  as `ref_<8 random hex>.v` and rewrite the module name to match; the submission must not
  be able to name the ref module or file.
- Sanity stage per CONTRACTS.md: cell floor via yosys stat, reject `initial` blocks
  driving DUT outputs, hierarchical references (`top.tb.x` style), `` `include `` and
  `$readmem*` in submissions. Static checks: regex over the comment-stripped source is fine.
- Area/depth: run the exact same yosys flow (`synth; stat` and `synth; ltp -noff`) on
  agent and ref; parse cell count and longest-path depth. Cache ref results per task
  within a grade call, but do not persist stale ref numbers across runs.
- latency.py: wall-clock ms per tool call + SHA-256(content)->result cache (in-memory +
  optional on-disk under the episode workdir). tools.py routes run_sim/run_synth/submit
  through it, per CONTRACTS.md signatures.
- runner.py: implement the episode-state plumbing only as far as tools.py needs
  (task loading, workdir, submission recording). The model-driving loop belongs to a
  later `agent/` worker — leave a clean seam, do not build agent code.
- Determinism: seed everything; record seeds in outputs.

## Verification (run from worktree root; this exact command goes in your report)
```
cd /data/projects/rtl-agent-gym/.worktrees/env-core && RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin /data/projects/rtl-agent-gym/venv/bin/python -m unittest discover -s env/tests -v && RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin make smoke-test
```

## Live smoke (include observed output in report)
```
RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin /data/projects/rtl-agent-gym/venv/bin/python -m env.grade --task env/fixtures/toy_adder --rtl env/fixtures/toy_adder/ref/ref.v --json-out /tmp/toy_adder_ref.json
```
Expected: JSON with all gates true, reward ≥ 0.95 (self-vs-self ⇒ area_norm = depth_norm = 1.0 ⇒ reward 1.0). Then the same command with `broken/stub.v` → reward ≤ 0.2 with `flagged` or failed gate. Report both observed JSONs (truncate stage_logs).

## Constraints
- Do not spawn subagents. Do not touch `.git` config or attempt push. No network calls.
- You cannot commit (`.git` is read-only in your sandbox). Instead, report the intended
  commit message: `campaign/env-core: grading pipeline + sandbox + smoke harness`.

## Final report (print as the last thing you output, JSON matching this shape)
{"status": "done|partial|blocked", "branch": "campaign/env-core", "commit": "",
 "files_changed": [...], "verify_cmd": "...", "verify_result": {"passed": bool,
 "output_tail": "last ~20 lines"}, "live_smoke": {"cmd": "...", "expected": "...",
 "observed": "...", "passed": bool}, "blockers": [...]}
