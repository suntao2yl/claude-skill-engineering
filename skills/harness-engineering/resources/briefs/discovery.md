---
phase: discovery
context_budget:
  max_input_tokens: 4000
  truncation_strategy: summary
role: Requirements analyst
completion_signal: "DISCOVERY_EXECUTOR_DONE REQ-XXX"
---

# Discovery Phase Brief

**Role:** Requirements analyst. Convert a goal into a structured requirement.

**Inputs:** `.engineering/lifecycle.json` (for `goal` field)

**Output artifact:** `.engineering/discovery/requirements.json`

**Required fields to fill:**
- `title` (<=80 chars, first sentence of goal)
- `problem_statement` (>=20 chars, markdown ok, expands on goal)
- `users` (array, each >=3 chars, concrete user profiles not generic labels)
- `success_metrics` (array, each >=5 chars, measurable outcomes)
- `constraints` (array, can be empty)
- `out_of_scope` (array, can be empty)

**Judgment rules:**
- Infer users from the goal. If goal says "pet game for loneliness", users are "independent young professionals", "people who can't own pets", etc.
- Success metrics must be observable. "Users like it" is not a metric; "D7 retention >=30%" or "3+ interactions/day median" is.
- If the goal is vague, make reasonable concrete assumptions and put edge cases in `out_of_scope`. Do not leave fields empty because "needs user input".
- `constraints` captures hard boundaries ("runs on iOS 15+", "no server").

**Completion signal:** print `DISCOVERY_EXECUTOR_DONE REQ-XXX` when the artifact is saved with all required fields filled.
