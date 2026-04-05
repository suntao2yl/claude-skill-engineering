# Architecture

## Core principles (inherited from harness)

1. **Compact machine state** — every phase owns structured JSON state, not
   free-text memory. The orchestrator reads state, never reconstructs it.
2. **Structured artifacts as handoff protocol** — phases communicate through
   schema-validated JSON files, never through natural-language prompts or
   agent-to-agent chat.
3. **Deterministic transitions** — phase state changes go through scripts
   that enforce rules (precondition → validated action → postcondition).
4. **Risk-gated human approval** — most transitions auto-advance; only
   destructive or high-stakes transitions pause for the user.
5. **Single active unit per phase** — like `harness` only works on one
   feature at a time, each phase has at most one "active" unit of work.

## Lifecycle phases

Draft list — subject to refinement during implementation:

| Phase | Active unit | Produces | Consumes |
|-------|-------------|----------|----------|
| `discovery` | a problem statement | requirements.json | user input |
| `design` | a design spec | design-tokens.json, flows.json | requirements.json |
| `architecture` | an ADR | adr-NNN.json, stack.json | requirements.json |
| `implementation` | a campaign (delegates to `harness`) | code + tests | design + architecture |
| `test` | a test plan | test-report.json | implementation output |
| `release` | a release candidate | release-checklist.json | test-report.json |
| `ops` | an incident or metric | postmortem.json | release artifacts |

Each phase is optional and independently activatable. A small bugfix may only
touch `implementation` + `test`. A new product may walk the full chain.

## State model

### Top-level state

`.engineering/lifecycle.json` — the master state file:

```json
{
  "project": "string",
  "current_phase": "design",
  "active_units": {
    "discovery": "REQ-003",
    "design": "DES-002",
    "implementation": null
  },
  "last_transition": "ISO-8601",
  "phase_history": [...]
}
```

### Per-phase state

Each phase has its own subdirectory with phase-specific schemas:

```
.engineering/
├── lifecycle.json
├── discovery/
│   ├── requirements.json
│   └── archive/
├── design/
│   ├── design-spec.json
│   └── archive/
├── architecture/
│   ├── adrs.json
│   └── archive/
├── implementation/     ← this is where .harness/ lives (or a pointer)
├── test/
├── release/
└── ops/
```

### Cross-phase links

Each artifact references upstream artifacts by id, not by copying content:

```json
// design/design-spec.json
{
  "id": "DES-002",
  "implements_requirements": ["REQ-003", "REQ-005"],
  ...
}
```

Downstream phases can verify they are consuming the latest upstream version
via commit hashes or version fields.

## Phase transitions

A transition is:

```
phase A produces artifact → orchestrator validates schema → phase B consumes artifact
```

**Forward transitions** (discovery → design → ...) are the happy path.

**Backward transitions** (design → discovery, because requirements were wrong)
must be explicit. They mark the upstream artifact as "revising" and block
downstream phases until the upstream is refreshed.

**Skip transitions** (jump from discovery directly to implementation for a
trivial bug) are allowed but recorded. The lifecycle.json tracks which phases
were skipped and why.

## Agent model

Two classes of agents:

1. **The orchestrator** (the main skill) — reads lifecycle state, decides
   which phase is active, delegates to the phase executor, handles
   transitions. Holds no domain knowledge itself.

2. **Phase executors** — specialized skills/subagents invoked per phase:
   - `discovery` executor: requirements analyst subagent
   - `design` executor: design skill (could wrap DESIGN.md tools)
   - `architecture` executor: ADR-authoring subagent
   - `implementation` executor: the existing `harness` skill
   - `test` executor: test-authoring subagent
   - etc.

Phase executors never invoke each other. They only read inputs from disk and
write outputs to disk. The orchestrator is the only entity that routes.

## What `harness-engineering` explicitly does NOT do

- **No inter-agent chat.** If two phases need to "discuss", the design is wrong.
- **No flexible state.** State is schema-validated JSON. Free text lives in
  dedicated Markdown fields within the schema, never replacing it.
- **No implicit dependencies.** Phase B does not silently assume phase A ran.
  It either reads A's artifact or the orchestrator refuses to enter B.
- **No campaign-level AI memory.** Memory is in the files, not in conversation
  history. Any session can pick up any phase from the artifacts alone.
