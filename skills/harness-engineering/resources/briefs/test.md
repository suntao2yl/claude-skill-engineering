---
phase: test
context_budget:
  max_input_tokens: 8000
  truncation_strategy: summary
role: Test engineer
completion_signal: "TEST_EXECUTOR_DONE TEST-XXX"
---

# Test Phase Brief

**Role:** Test engineer. Build and execute a test plan.

**Inputs:** `.engineering/implementation/campaign-ref.json`

**Output artifact:** `.engineering/test/test-report.json`

**Required fields:**
- `id`, `campaign_ref` (IMPL-XXX), `plan`, `results`

**Judgment rules:**
- Plan types: `unit | integration | e2e | manual`.
- Each plan item SHOULD have a `command` field if it's automatable.
- `results` must correspond 1:1 with `plan` entries. Each result has `name, status (pass|fail|skipped), evidence`.
- Evidence must be non-empty strings. "Works" is not evidence; include exit code, stdout excerpt, or screenshot path.
- Any item with a `command` field will be re-executed by engineering_advance.py hard validator. Fake commands will fail.

**Completion signal:** print `TEST_EXECUTOR_DONE TEST-XXX`.
