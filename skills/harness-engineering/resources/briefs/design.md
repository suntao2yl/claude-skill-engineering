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

**Completion signal:** print `DESIGN_EXECUTOR_DONE DES-XXX`.
