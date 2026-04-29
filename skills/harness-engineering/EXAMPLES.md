# harness-engineering — Examples

## Init and auto-drive a small project

```text
User: /harness-engineering init "Build a CLI tool that converts CSV to JSON"

→ engineering_init.py creates .engineering/ with lifecycle.json
→ Auto-drive loop:

  1. discovery: fills requirements.json (title, problem_statement, users, success_metrics)
     → advance validates → exit 0 → auto-advance
  2. design: fills design-spec.json (flows, components)
     → exit 0 → auto-advance
  3. architecture: fills stack.json + ADR-001.json
     → exit 42 (risk gate: architecture.approved) → pauses
User: approved
  4. implementation: delegates to harness-plan, drives features to done
     → exit 0 → auto-advance
  5. test: builds test-report.json, re-executes verification commands
     → exit 0 → auto-advance
  6. release: fills release-checklist.json, verifies tagged_commit
     → exit 42 (risk gate) → pauses
User: approved
  7. ops: creates metrics.json skeleton
     → exit 0 → all phases complete

→ engineering_lint.py reports findings, loop exits.
```

## Architecture: parallel interface design

```text
phase=architecture; the design names "event bus" but the team is split between Kafka, NATS, and an in-process queue.

→ Dispatch 3 parallel general-purpose Agents, each producing:
  - one ADR draft
  - one stack.json snippet
  - one rejected-alternatives list

→ Orchestrator merges into ADR-002, picks one, archives the others under
  .engineering/architecture/alternatives/.

→ engineering_advance.py runs as usual.
```
