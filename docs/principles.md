# Principles

These are the constraints we will design under. When a decision is unclear,
these should break ties.

## 1. Machine state is the source of truth

The orchestrator never reconstructs state from conversation. If it cannot be
found in an artifact file, it does not exist. This means every handoff must
write to disk before the next phase starts.

## 2. Phases communicate through artifacts, not through agents

Phase executors are isolated. They read input artifacts, produce output
artifacts, and terminate. No phase knows about another phase's internals.
The orchestrator is the only entity that knows the phase graph.

## 3. Structured first, prose second

Every schema prefers typed fields over freeform strings. Markdown fields
exist only where prose is genuinely needed (problem statements, ADR context).
Never store critical state in a Markdown blob.

## 4. One active unit per phase

Like `harness` only works on one feature at a time, each phase has at most
one active unit. Parallelism happens *within* a unit (via subagents) or
*across phases* (design + architecture simultaneously), not across multiple
units in the same phase.

## 5. Deterministic transitions

State changes happen through scripts with clear preconditions. If you cannot
write a validation check for a transition, the transition rule is wrong.

## 6. Risk-gated human control

Most transitions auto-advance. Only these require explicit user confirmation:
- Destructive actions (archive, delete, reset)
- Accepting a requirement or design (downstream phases depend on it)
- Marking a release as shipped
- Invoking a phase with stale inputs (forced override)

## 7. Skippable phases, non-skippable gates

Users can skip phases entirely (`mode: minimal` for bug fixes). But within
an active phase, the exit criteria cannot be bypassed — you finish the phase
or you explicitly cancel it.

## 8. Compose, do not embed

`harness-engineering` does not reimplement `harness`. It invokes it. Same
for any phase that maps to an existing skill. The orchestrator's job is
routing and state management, not domain logic.

## 9. New sessions pick up from artifacts alone

A fresh Claude session should be able to read `lifecycle.json` and know
exactly what phase it is in, what the last action was, and what to do next.
No conversation history required.

## 10. Observable, auditable, reversible

Every transition is logged with timestamps and inputs. Every artifact has a
history. Backward transitions are explicit and reversible.

---

## Anti-principles (what we will not do)

- **No "smart" orchestrators that guess the next phase.** The user or the
  rules decide, not vibes.
- **No conversational memory as state.** If the user has to remind the
  orchestrator of prior context, the artifacts are wrong.
- **No silent cross-phase mutations.** Phase B cannot edit phase A's
  artifacts. Only A can revise A.
- **No "framework" sprawl.** If a feature is not proven useful, it is
  not in the core. Skills can be layered on top.
