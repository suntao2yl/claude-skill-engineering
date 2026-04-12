---
phase: architecture
context_budget:
  max_input_tokens: 6000
  truncation_strategy: summary
role: Tech lead
completion_signal: "ARCHITECTURE_EXECUTOR_DONE ARCH-XXX"
---

# Architecture Phase Brief

**Role:** Tech lead. Pick the stack and record non-obvious decisions.

**Inputs:** `.engineering/discovery/requirements.json` (MUST read first)

**Output artifacts:**
- `.engineering/architecture/stack.json`
- `.engineering/architecture/adrs/ADR-NNN.json` (at least 1 file required)

**Required fields in stack.json:**
- `id` (ARCH-001, ...)
- `stack` (object describing tech choices)
- `adrs` (array of ADR ids referencing files in adrs/)

**Required fields per ADR:**
- `id`, `title`, `status` (proposed|accepted|superseded), `context`, `decision`, `consequences` (array), `supersedes` (ADR id or null)

**Judgment rules:**
- Write an ADR only for non-obvious decisions (choice between alternatives, significant trade-offs). "Use Python" for a Python-focused project is not an ADR.
- `consequences` must include both positive and negative outcomes.
- `stack` object has free-form keys matching the project domain (engine, language, database, deployment, etc.).

**Completion signal:** print `ARCHITECTURE_EXECUTOR_DONE ARCH-XXX` after stack.json and >=1 ADR file exist.

## Decision Logging

Every ADR is inherently a decision record. Additionally, when making choices not captured in ADRs (e.g., what NOT to write an ADR for, scope of stack object), log to `.engineering/decisions.jsonl` with: phase="architecture", classification="taste", the applicable principle, rationale, and rejected alternative.

## Insight Awareness

Before starting, check for insights targeting this phase:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list --target architecture --unaddressed`
Address relevant insights during artifact creation. Mark addressed:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --address <index>`
