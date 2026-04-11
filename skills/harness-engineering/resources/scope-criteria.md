# Scope Level Criteria

Reference for classifying project scope in the discovery phase.

## Lightweight

- Goal is well-bounded with clear acceptance criteria
- Likely touches <3 files
- Low ambiguity — one obvious approach
- Examples: bug fix, config change, small refactor, single-function addition

**Ceremony:** Fill core fields only. Skip requirement_groups. Pressure test can be brief but must still be substantive (>=10 chars per field).

## Standard

- Normal feature or bounded refactor
- Some decisions to make (approach, scope boundaries)
- Touches 3-15 files
- Examples: new feature, API endpoint, UI component, multi-file refactor

**Ceremony:** Full fields. Group requirements by topic. Pressure test should genuinely challenge the goal.

## Deep

- Cross-cutting change affecting multiple subsystems
- High ambiguity — multiple valid approaches with different tradeoffs
- Touches >15 files or introduces new architectural patterns
- Strategic implications beyond the immediate change
- Examples: auth system rewrite, new data pipeline, platform migration, major UX overhaul

**Ceremony:** Full fields with detailed groups. Pressure test should explore reframing and alternatives in depth. Consider whether the goal should be decomposed into multiple lifecycles.

## Decision Heuristic

When in doubt between two levels, choose the higher one. The cost of extra ceremony is minutes; the cost of insufficient analysis is wasted implementation.

Signals that push toward `deep`:
- Goal mentions "rewrite", "migrate", "platform", "architecture"
- Multiple user types affected differently
- External system integrations involved
- Performance or security implications
- Goal is phrased as a solution rather than a problem
