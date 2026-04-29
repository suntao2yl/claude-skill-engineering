---
phase: implementation
context_budget:
  max_input_tokens: 10000
  truncation_strategy: fields_only
role: Implementation delegate (harness-plan or Managed Agents)
completion_signal: "IMPLEMENTATION_EXECUTOR_DONE IMPL-XXX"
---

# Implementation Phase Brief

**Role:** Delegate implementation to the chosen backend. Do NOT write production code here directly.

**Inputs:**
- `.engineering/design/design-spec.json`
- `.engineering/architecture/stack.json` + ADRs

**Output artifact:** `.engineering/implementation/campaign-ref.json`

## Backend Selection (v0.3.0)

Choose implementation backend based on scope and environment:

**LOCAL (harness-plan) — default:**
- Works offline, no external dependencies
- Best for: lightweight/standard scope, < 8 features
- Requires: harness-plan skill installed

**MANAGED AGENTS — optional:**
- Requires Anthropic API access with Managed Agents enabled
- Best for: deep scope, > 8 features, long-running campaigns needing sandboxed execution
- Cost: standard token rates + $0.08/session-hour
- Provides: sandboxed code execution, long-running sessions, checkpoint/resume

Record the backend choice in campaign-ref.json as `"backend": "local"` or `"backend": "managed_agents"`.
Log the decision with rationale to `.engineering/decisions.jsonl`.

## Local Backend (harness-plan)

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

## Managed Agents Backend

Read @file resources/briefs/managed-agents-guide.md for detailed instructions.

1. Create a managed session:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py --create --project-root <path> --goal "..." --features-total N`
2. Start the session via Claude API / Managed Agents API
3. Monitor progress:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py --status --project-root <path>`
4. Checkpoint periodically:
   `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_managed.py --checkpoint --project-root <path> --features-completed N`
5. After completion, fill campaign-ref.json with `"backend": "managed_agents"`

**Required fields in campaign-ref.json (managed_agents backend):**
- `campaign_id`, `backend: "managed_agents"`, `implements_requirements`

## Judgment Rules

- Decompose into 3-8 features, each independently verifiable.
- Every feature MUST have a `verification.command` that actually runs.
- Features with placeholder/fake verification WILL fail advance's live check.
- Use `/tdd-plan` from `harness-discipline` to seed each feature's
  verification command. The skill emits JSON; `verification_command` is the
  field to copy into `feature.verification.command`.
- Use `/completion-verify` (not inline shell loops) when validating that a
  feature is done. This is the canonical Self-Test executor; engineering
  advance also calls it during the implementation gate.

**Completion signal:** print `IMPLEMENTATION_EXECUTOR_DONE IMPL-XXX`.

## Decision Logging

Log backend selection (local vs managed_agents) and feature decomposition choices to `.engineering/decisions.jsonl` with: phase="implementation", classification and principle as appropriate.

## Insight Awareness

Before starting, check for insights targeting this phase:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list --target implementation --unaddressed`
Address relevant insights during artifact creation. Mark addressed:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --address <index>`
