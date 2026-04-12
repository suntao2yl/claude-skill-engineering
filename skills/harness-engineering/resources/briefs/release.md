---
phase: release
context_budget:
  max_input_tokens: 4000
  truncation_strategy: summary
role: Release engineer
completion_signal: "RELEASE_EXECUTOR_DONE REL-XXX"
---

# Release Phase Brief

**Role:** Release engineer. Prepare and execute a release.

**Inputs:** `.engineering/test/test-report.json` (must be approved)

**Output artifact:** `.engineering/release/release-checklist.json`

**Required fields:**
- `id`, `version` (semver), `checklist`, `rollback_plan`, `tagged_commit`

## Step 1: Build Checklist

`checklist` items each have `{item, status, notes}`. Status options: `pending | done | skipped`. Pending items will block advance.

## Step 2: Release Automation (v0.3.0)

Instead of manually tracking checklist items, define executable automation steps in `release_automation` array. Each step:

```json
{
  "step": "run_tests",
  "command": "python3 -m pytest",
  "expected": "",
  "output": "",
  "status": "pending"
}
```

Recommended automation steps (adapt to project):
1. `run_tests` — full test suite
2. `version_bump` — update version file/field
3. `changelog_update` — update CHANGELOG.md
4. `create_tag` — `git tag v{version}`
5. `create_pr` — `gh pr create ...` or equivalent

Execute each step, record output and status. engineering_advance.py will re-execute commands to verify.

Read @file resources/briefs/release-automation.md for detailed automation patterns.

## Step 3: Rollback Plan

`rollback_plan` must be concrete with specific revert commands:
- "git revert {tagged_commit}" counts
- "we'll figure it out" does not

## Step 4: Tag

`tagged_commit` must be a real git ref. engineering_advance.py will `git rev-parse --verify` it.

**Completion signal:** print `RELEASE_EXECUTOR_DONE REL-XXX`.

## Decision Logging

Log version bump level choice, checklist item skip decisions, and rollback strategy choices to `.engineering/decisions.jsonl` with: phase="release", classification and principle as appropriate.

## Insight Awareness

Before starting, check for insights targeting this phase:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list --target release --unaddressed`
Address relevant insights during artifact creation. When release prep reveals upstream issues, record them:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --add --source release --target <upstream_phase> --kind <kind> --insight "..." --evidence "..."`
