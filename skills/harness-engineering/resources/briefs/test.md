---
phase: test
context_budget:
  max_input_tokens: 8000
  truncation_strategy: summary
role: Test engineer
completion_signal: "TEST_EXECUTOR_DONE TEST-XXX"
---

# Test Phase Brief

**Role:** Test engineer. Build a test plan, execute it, and run multi-persona review.

**Inputs:** `.engineering/implementation/campaign-ref.json`

**Output artifact:** `.engineering/test/test-report.json`

**Required fields:**
- `id`, `campaign_ref` (IMPL-XXX), `plan`, `results`
- `review_personas` (required for standard/deep scope)

## Step 1: Build Test Plan

- Plan types: `unit | integration | e2e | manual`.
- Each plan item SHOULD have a `command` field if it's automatable.
- Any item with a `command` field will be re-executed by engineering_advance.py hard validator. Fake commands will fail.

## Step 2: Execute Tests

- `results` must correspond 1:1 with `plan` entries. Each result has `name, status (pass|fail|skipped), evidence`.
- Evidence must be non-empty strings. "Works" is not evidence; include exit code, stdout excerpt, or screenshot path.

## Step 3: Multi-Persona Review (standard/deep scope)

Read @file resources/reviewer-personas.md for persona definitions.

For each persona (security, performance, testing, maintainability):
1. Spawn a parallel sub-agent (via Agent tool) with the persona's prompt template
2. Provide: test report, implementation diff (`git diff` of implementation changes), and focused review prompt
3. Collect structured findings: `{persona, findings: [{severity, description, recommendation}], verdict}`

Record all persona results in `review_personas` array in the test-report.

**Deduplication:** If two personas flag the same issue, keep the higher-severity entry.

**Blocking:** Any persona with `verdict: "block"` will prevent advance. Address blocking findings before signaling completion.

For `lightweight` scope, multi-persona review is optional — skip if the change is trivial.

## Step 4: Success Criteria Self-Evaluation

Define 2-5 measurable success criteria in `success_criteria` array. Before signaling completion, self-evaluate each:

```json
"success_criteria": ["All new code paths have test coverage", "No security findings above medium"],
"success_evaluation": [
  {"criterion": "All new code paths have test coverage", "met": true, "evidence": "12/12 paths covered"},
  {"criterion": "No security findings above medium", "met": true, "evidence": "Security reviewer: 0 high/critical findings"}
]
```

If any criterion is not met, iterate (up to 2 retries) before signaling.

**Completion signal:** print `TEST_EXECUTOR_DONE TEST-XXX`.

## Decision Logging

When choosing test strategies, coverage tradeoffs, or skipping manual tests, log to `.engineering/decisions.jsonl` with: phase="test", classification="taste", the applicable principle, rationale, and rejected alternative.
