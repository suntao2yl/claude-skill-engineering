---
phase: release
context_budget:
  max_input_tokens: 4000
  truncation_strategy: summary
role: Release engineer
completion_signal: "RELEASE_EXECUTOR_DONE REL-XXX"
---

# Release Phase Brief

**Role:** Release engineer. Prepare a release candidate.

**Inputs:** `.engineering/test/test-report.json` (must be approved)

**Output artifact:** `.engineering/release/release-checklist.json`

**Required fields:**
- `id`, `version` (semver), `checklist`, `rollback_plan`, `tagged_commit`

**Judgment rules:**
- `tagged_commit` must be a real git ref (engineering_advance.py will `git rev-parse --verify` it).
- `checklist` items each have `{item, status, notes}`. Status options: `pending | done | skipped`. Pending items will block advance.
- `rollback_plan` must be concrete ("users uninstall; state is local-only" counts; "we'll figure it out" does not).

**Completion signal:** print `RELEASE_EXECUTOR_DONE REL-XXX`.
