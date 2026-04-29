---
phase: eval
context_budget:
  max_input_tokens: 4000
  truncation_strategy: summary
role: Eval baseline curator
completion_signal: "EVAL_EXECUTOR_DONE EVAL-baseline"
---

# Eval Phase Brief

**Role:** Eval baseline curator. Distill the test phase's results into
reusable EVAL-NNN cases and establish a baseline for regression detection.

This phase is invoked from the ops phase, not as a standalone phase in the
PHASES list. Its purpose is to give the lifecycle a frozen pass/fail
fingerprint that can be re-run later (after model upgrades, refactors,
infrastructure changes) to detect regressions without re-doing the test
phase from scratch.

**Inputs:**
- `.engineering/test/test-report.json` — passing tests are the eval source

**Outputs:**
- `.engineering/eval/cases/EVAL-NNN.json` — one per passing test
- `.engineering/eval/runs/run-<timestamp>/result.json` — execution record
- `lifecycle.json -> eval_baseline` — pointer to the baseline run id

**Workflow:**

1. Distill cases from the test report:
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --create
   ```
   Skipped tests:
   - non-passing tests
   - tests without a `command` in the plan

2. Run the cases and mark baseline:
   ```
   python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --run --mark-baseline
   ```
   The script writes a run directory; `--mark-baseline` records its id
   in `lifecycle.json -> eval_baseline`.

3. Verify the baseline run was clean (passed == total). If any case
   fails on the baseline run, the test phase wasn't actually green — go
   back and fix the failing test, don't bake a broken baseline.

**Re-runs (later):**

Once a baseline exists, anyone can detect regressions:

```
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --run
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --compare baseline
```

The compare exits 1 if any regression is detected, listing each
regression's EVAL id.

**Judgment Rules:**
- Don't curate cases by hand. The script is deterministic; trust it.
- If a passing test has no `command` in the plan, the script skips it.
  Either fix the plan to include the command, or accept the skip — don't
  fabricate a synthetic command.
- One project, one baseline. If the test phase regenerates (revise →
  retest), re-create cases and re-mark baseline.

**Anti-patterns:**
- Don't run `--baseline` against a failed run. The script will let you,
  but the baseline becomes meaningless.
- Don't compare runs from different projects. Each project's eval lives
  in its own `.engineering/eval/`; cases aren't portable across projects.
