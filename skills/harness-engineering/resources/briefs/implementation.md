---
phase: implementation
context_budget:
  max_input_tokens: 10000
  truncation_strategy: fields_only
role: Implementation delegate (harness-plan)
completion_signal: "IMPLEMENTATION_EXECUTOR_DONE IMPL-XXX"
---

# Implementation Phase Brief

**Role:** Delegate to `harness-plan` skill. Do NOT write production code here.

**Inputs:**
- `.engineering/design/design-spec.json`
- `.engineering/architecture/stack.json` + ADRs

**Output artifact:** `.engineering/implementation/campaign-ref.json`

**Process:**
1. Derive a harness-plan campaign goal from design + architecture.
2. Initialize harness-plan at `.engineering/implementation/.harness/`:
   - invoke harness-plan INIT with `--project-root <project>/.engineering/implementation/`
   - decompose goal into features with real `verification.command` entries
3. Drive harness-plan through each feature until `done`.
4. After `progress_counts.done == total`:
   - fill campaign-ref.json with campaign_id, harness_root, implements_requirements, implements_design, implements_architecture, harness_progress
   - engineering_advance.py will live-execute verification commands

**Required fields in campaign-ref.json:**
- `campaign_id`, `harness_root`, `implements_requirements`

**Judgment rules:**
- Decompose into 3-8 features, each independently verifiable.
- Every feature MUST have a `verification.command` that actually runs.
- Features with placeholder/fake verification WILL fail advance's live check.

**Completion signal:** print `IMPLEMENTATION_EXECUTOR_DONE IMPL-XXX`.
