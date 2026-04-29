---
phase: design
context_budget:
  max_input_tokens: 6000
  truncation_strategy: summary
role: UX/interaction designer
completion_signal: "DESIGN_EXECUTOR_DONE DES-XXX"
---

# Design Phase Brief

**Role:** UX/interaction designer. Propose how the solution looks and feels.

**Inputs:** `.engineering/discovery/requirements.json` (MUST read first)

**Output artifact:** `.engineering/design/design-spec.json`

**Required fields:**
- `id` (DES-001, DES-002, ...)
- `implements_requirements` (array of REQ ids — must include the active REQ)
- `flows` (array of {name, steps}; each flow has >=2 non-empty steps)
- `components` (array of {name, spec}; each spec >=10 chars)

**Judgment rules:**
- Flows are user journeys. Name them by intent ("First meeting", "Daily check-in"), not by screen ("Home screen flow").
- Components are the visible UI pieces needed to support flows.
- If a flow implies a screen transition, one component per significant screen.
- Reference a design_tokens file if one exists at project root; otherwise null.

**Change-spec authoring:** for each significant design unit, invoke
`/change-spec --feature-id DES-XXX --output .engineering/design/specs/DES-XXX-spec.md`
to produce a mini-RFC alongside the design spec. The RFC captures the
testable pre/post-conditions, interface signatures, and out-of-scope
items that downstream phases will reference. Skip for trivial changes
(<= 30 LOC of UI changes).

**Completion signal:** print `DESIGN_EXECUTOR_DONE DES-XXX`.

## Decision Logging

When making non-obvious choices during artifact creation (e.g., choosing between flow structures, component granularity, design patterns), log each as a taste decision to `.engineering/decisions.jsonl` with: phase="design", classification="taste", the applicable principle, rationale, and rejected alternative.

## Insight Awareness

Before starting, check for insights targeting this phase:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list --target design --unaddressed`
Address relevant insights during artifact creation. Mark addressed:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --address <index>`
