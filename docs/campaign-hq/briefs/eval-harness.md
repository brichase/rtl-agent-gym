# Task: eval/ — sweep runner + report generator

## Goal
Build `eval/run_eval.py` and `eval/report.py` per plan §6: sweep tasks × models ×
conditions × trials → `results/results.jsonl` → markdown report tables.

## Read first (worktree root)
`docs/CONTRACTS.md` — especially §agent/ episode API (you consume exactly that; a
sibling worker is building agent/ right now — code against the contract, use a stub
in your tests) and §results row. `rtl-agent-gym-weekend-plan-v2.md` §6.

## Environment
- Branch `campaign/eval-harness`, worktree `/data/projects/rtl-agent-gym/.worktrees/eval-harness`, base `0c7c31a`.
- venv `/data/projects/rtl-agent-gym/venv/bin/python`. Keyless; no live model calls.

## Owned files
`eval/__init__.py`, `eval/run_eval.py`, `eval/report.py`, `eval/tests/`.

## Excluded
`env/**`, `tasks/**`, `agent/**`, `redteam/**`, `Makefile`, `README.md`, `docs/campaign-hq/**`

## Design decisions (binding)
- run_eval.py CLI: `--tasks a,b,c|all --models id1,id2 --conditions single_shot,agentic
  --trials N --out results/ [--max-turns 10] [--resume]`. Iterates sequentially (no
  parallel episodes — sim workdirs and plan-quota safety first), calls
  `agent.loop.run_episode` via a late import (module may not exist in your worktree —
  import inside main, and tests inject a fake run_episode). Appends each row to
  `results/results.jsonl` immediately (crash-safe), flushes. `--resume` skips
  (task,model,condition,trial) tuples already present. Logs progress lines with running
  totals. Episodes with error field still get rows.
- Codex model IDs may map to effort: accept `gpt-5.6-luna@max` syntax → model_id
  gpt-5.6-luna, effort max, passed through to run_episode via max-effort kwarg if the
  API supports it; store the full string in the row's model_id.
- report.py CLI: `--in results/results.jsonl --out results/report.md`. Tables per plan
  §6: per task×model×condition — pass counts as "4/5" + rate, pass@1, pass@5 (any trial
  ≥0.7), mean reward, mean turns/tool_calls, mean tokens_in/out, cost when present,
  area_norm/depth_norm means on solved episodes, flagged-episode count with pointers.
  Headline table: single_shot → agentic delta per model. Latency percentiles + cache hit
  rate if fields present. Counts always alongside rates; no significance language.
- Both modules stdlib+pyyaml only.

## Verification (goes in report)
```
cd /data/projects/rtl-agent-gym/.worktrees/eval-harness && /data/projects/rtl-agent-gym/venv/bin/python -m unittest discover -s eval/tests -v
```
Tests: sweep with injected fake run_episode producing deterministic rows → resume
skips correctly, jsonl complete; report.py on a synthetic 2-model×2-task×2-cond×3-trial
results file → tables contain correct counts (assert exact strings for a few cells).

## Live smoke
`run_eval.py --tasks env/fixtures/toy_adder --models mock --conditions agentic --trials 1`
against the real agent module IF it exists on main by the time you finish (pull main
read-only to check: `git fetch && git show origin/main:agent/loop.py | head -1` — if
absent, do the fake-injection path and say so honestly in the report).

## Constraints
No subagents, no network, no live model calls. Cannot commit; intended message:
`campaign/eval-harness: sweep runner + report tables`.

## Final report: same JSON shape (status, branch, commit:"", files_changed, verify_cmd,
verify_result, live_smoke, blockers).
