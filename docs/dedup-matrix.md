# Capability Dedup Matrix

This table is the single source of truth for "which skill owns which capability"
across `harness-discipline`, `harness-plan`, and `harness-engineering`. The
goal is to prevent capability duplication that wastes tokens and produces
inconsistent verdicts (e.g., two reviewers disagreeing on the same diff).

## Reading the table

- **canon** — this skill is the authoritative implementation. Other skills
  delegate by invoking the canonical command, not by reimplementing.
- **delegate** — this skill calls the canonical implementation. It does not
  hold its own copy of the logic.
- **reference** — this skill mentions the capability in prose / briefs but
  does not invoke it. End users invoke it directly when needed.
- **off** — this skill explicitly does not participate in this capability,
  even when given the opportunity. Used to prevent overlap.

## The matrix

| Capability                  | harness-discipline    | harness-plan                  | harness-engineering                |
| --------------------------- | --------------------- | ----------------------------- | ---------------------------------- |
| **TDD plan / test design**  | `/tdd-plan` — canon   | INIT step 2 — delegate        | design phase brief — reference     |
| **Completion verification** | `/completion-verify` — canon | Self-Test phase — delegate | implementation advance — delegate |
| **Change spec (mini-RFC)**  | `/change-spec` — canon | INIT decompose — delegate (Phase 2+) | discovery / design — reference |
| **Per-feature code review** | (not implemented)     | `review_policy: qa` — canon (legacy) | (off when delegating to harness-plan) |
| **Multi-persona review**    | (off)                 | (off — defer to engineering)  | test phase — canon                 |
| **Security scan**           | (off)                 | (off)                         | test phase, releases — delegates to `/security-review` (Claude Code built-in) |
| **State persistence (cross-session)** | (off)       | `.harness/` — canon           | `.engineering/` — canon for phase state, delegates implementation state to harness-plan |
| **Phase / risk gates**      | (off)                 | (off)                         | `engineering_advance.py` — canon   |
| **Insight capture**         | (off)                 | (off)                         | `engineering_insight.py` — canon   |

## Mode-specific overrides

When `harness-engineering` is driving and delegates implementation to
`harness-plan`:

- harness-plan contracts created by engineering MUST set
  `review_policy: selftest` (not `qa`). engineering owns review.
- harness-plan's `harness_autodrive.py` review session SHOULD NOT run when
  engineering is in charge — engineering's test phase already covers it.

When `harness-plan` is running standalone (no `.engineering/` directory):

- harness-plan owns review via `review_policy: qa`. multi-persona review
  becomes a no-op since the engineering test phase isn't active.

## Where to update this matrix

Adding a new capability to any of the three skills? Update this matrix in
the same PR. If you can't decide which skill owns it, the answer is usually
"the smallest one" — push capabilities downward (toward harness-discipline)
when possible, since they become more reusable.

Removing or merging a capability? Mark the row removed with a date and
reason. Keep the history; capability boundaries evolve and the diff matters.
