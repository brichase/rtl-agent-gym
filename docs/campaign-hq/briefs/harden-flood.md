# Task: harden the grader against the output-flood weakness (red-team finding mitigation)

## Context
Our red-team suite found a real defense-in-depth weakness (redteam/06_output_flood).
A functionally-wrong submission prints "TB_ALL_PASS" at t=0 then floods >64 KiB of
$display text. The sandbox truncates output at 64 KiB (OUTPUT_LIMIT), cutting away the
real "TB_FAIL:" lines the testbench emits later. grade.py's string-scan then reads a
forged pass: visible_pass=true AND hidden_pass=true. Only the value-based differential
oracle catches it (oracle_pass=false → reward capped at 0.2, flagged). We want the
visible/hidden gates to also be robust. This is a sanctioned "defense motivated by an
observed attack" (plan §4/§5).

## The fix (minimal, defensive — do NOT change ladder rewards or oracle logic)
1. `env/sandbox.py`: `SandboxResult` currently drops the internal `truncated` flag. Add
   `truncated: bool` to the frozen dataclass and populate it from the existing local
   `truncated` variable in the run function(s). Keep the field defaulted/threaded through
   every place SandboxResult is constructed so nothing breaks.
2. `env/grade.py`: in the visible-TB and hidden-TB gate evaluation, if the sandbox result
   for that TB run was truncated, the gate FAILS regardless of stdout contents — a
   legitimate testbench run never approaches 64 KiB, so truncation during a graded TB run
   is itself disqualifying. Set the fail_reason to something like "visible testbench
   output truncated (flood)" / "hidden testbench output truncated". Do not alter the
   reward numbers of the ladder rungs themselves, only make these two gates return
   fail when truncated.
3. Add a targeted regression to `env/tests/test_grade.py`: grading
   redteam/06_output_flood against tasks/gray_counter now yields visible_pass=False (was
   True); reward stays ≤0.2 and flagged stays true; and a normal ref
   (env/fixtures/toy_adder/ref/ref.v) is unaffected (reward still ≥0.95, not truncated).

## Environment
Branch `campaign/harden-flood`, worktree `/data/projects/rtl-agent-gym/.worktrees/harden-flood`, base 138f6c2.
Tools: RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin (not on PATH).
Python: /data/projects/rtl-agent-gym/venv/bin/python.

## Owned files
`env/sandbox.py`, `env/grade.py`, `env/tests/test_grade.py`. Do NOT touch tasks/,
redteam/ submissions, agent/, eval/, or the reward-ladder constants.

## IMPORTANT — update the red-team expectation, don't break it
After the fix, redteam/06_output_flood's blocked-by gate changes from "oracle only" to
"visible/hidden truncation + oracle". Update `redteam/06_output_flood/expected.yaml`:
keep max_reward 0.2 and flagged true (still correct), and change its documentation keys
to reflect that the visible/hidden gates now also block it (e.g. weakness: mitigated,
note updated). This is the one redteam file you may edit — it's the finding's before/after
record. Leave the other 6 redteam dirs untouched.

## Verification (report it)
`RTL_GYM_TOOLS=/data/projects/rtl-agent-gym/toolchain/oss-cad-suite/bin /data/projects/rtl-agent-gym/venv/bin/python -m unittest discover -s env/tests`
then `RTL_GYM_TOOLS=... make smoke-test` — must stay green at 22/22 (all attacks still on
their rungs; the 15 legit fixture/task cases unchanged; attack 06 now reports a
truncation fail on visible/hidden but same 0.2 flagged final reward).
Report before/after for attack 06: `env.grade --task tasks/gray_counter --rtl
redteam/06_output_flood/submission.v --json-out /tmp/f.json` showing visible_pass and
hidden_pass flipped False while reward/flagged unchanged.

## Constraints
No subagents, no network. You cannot commit; intended message:
`campaign/harden-flood: truncated TB output fails visible/hidden gates (flood mitigation)`.
Final report: standard JSON shape (status, branch, commit:"", files_changed, verify_cmd,
verify_result{passed,output_tail}, live_smoke{cmd,expected,observed,passed}, blockers).
