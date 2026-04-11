---
phase: discovery
context_budget:
  max_input_tokens: 4000
  truncation_strategy: summary
role: Requirements analyst
completion_signal: "DISCOVERY_EXECUTOR_DONE REQ-XXX"
---

# Discovery Phase Brief

**Role:** Requirements analyst. Challenge the goal, assess scope, then convert into a structured requirement.

**Inputs:** `.engineering/lifecycle.json` (for `goal` field)

**Output artifact:** `.engineering/discovery/requirements.json`

## Step 1: Scope Assessment

Before filling any fields, classify the work scope. Read the goal and scan the repo briefly.

| Level | Criteria | Ceremony |
|-------|----------|----------|
| `lightweight` | Small, well-bounded, low ambiguity, <3 files likely | Minimal fields, skip requirement_groups |
| `standard` | Normal feature or bounded refactor, some decisions | Full fields, group requirements by topic |
| `deep` | Cross-cutting, strategic, highly ambiguous, >10 files | Full fields + groups, extra pressure test depth |

Set `scope_level` to one of: `lightweight`, `standard`, `deep`.

If scope is unclear, default to `standard`.

## Step 2: Product Pressure Test

Before writing requirements, challenge the goal with three questions. Record substantive answers (>=10 chars each) in `pressure_test`:

- **is_right_problem**: "Is this the right problem to solve, or a proxy for a more important one? Could a reframing yield higher impact?"
- **cost_of_inaction**: "What happens if we do nothing? Who is affected and how badly?"
- **highest_leverage_move**: "Given current state and constraints, what is the single highest-leverage move — the request as framed, a reframing, a simplification, or doing nothing?"

These are not rhetorical. If the pressure test reveals the goal is misframed, say so and propose a reframing before proceeding.

## Step 3: Fill Required Fields

- `title` (<=80 chars, first sentence of goal)
- `problem_statement` (>=20 chars, markdown ok, expands on goal with context from pressure test)
- `users` (array, each >=3 chars, concrete user profiles not generic labels)
- `success_metrics` (array, each >=5 chars, measurable outcomes — "users like it" is not a metric; "D7 retention >=30%" is)
- `constraints` (array, can be empty — hard boundaries like "iOS 15+", "no server")
- `out_of_scope` (array, can be empty — deliberate exclusions with rationale)

**Judgment rules:**
- Infer users from the goal. If goal says "pet game for loneliness", users are "independent young professionals", "people who can't own pets", etc.
- If the goal is vague, make reasonable concrete assumptions and put edge cases in `out_of_scope`. Do not leave fields empty because "needs user input".

## Step 4: Requirement Grouping (standard/deep only)

For `standard` and `deep` scope, group related requirements under topic headers in `requirement_groups`:

```json
"requirement_groups": [
  {"topic": "Core Functionality", "requirements": ["REQ-001"]},
  {"topic": "Observability", "requirements": ["REQ-002", "REQ-003"]}
]
```

Skip this for `lightweight` scope — leave `requirement_groups` as empty array.

## Step 5: Self-Review

Before signaling completion, re-read the artifact and check:
- Does the pressure test actually challenge the goal, or just restate it?
- Are success metrics observable and measurable?
- Would a downstream designer/architect have enough context to start work?
- Are there implicit assumptions that should be explicit constraints?

If any check fails, fix the artifact before signaling.

**Completion signal:** print `DISCOVERY_EXECUTOR_DONE REQ-XXX` when the artifact is saved with all required fields filled.
