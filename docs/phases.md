# Phase Specifications (draft)

Each phase is defined by its **active unit**, **entry criteria**,
**exit criteria**, and **artifact schema**. These are drafts — refine during
implementation.

## discovery

**Purpose:** Capture what problem we are solving, for whom, and why.

**Active unit:** A problem statement (one at a time).

**Entry criteria:** User describes a goal or pain point.

**Exit criteria:** `requirements.json` exists with validated fields.

**Artifact:** `discovery/requirements.json`
```json
{
  "id": "REQ-001",
  "title": "string",
  "problem_statement": "string (markdown)",
  "users": ["string"],
  "success_metrics": ["string"],
  "constraints": ["string"],
  "out_of_scope": ["string"],
  "status": "draft | approved | revising",
  "created_at": "ISO-8601",
  "last_updated": "ISO-8601"
}
```

## design

**Purpose:** Define how the solution looks and feels.

**Active unit:** A design spec tied to one or more requirements.

**Entry criteria:** At least one `requirements.json` in `approved` status.

**Exit criteria:** `design-spec.json` exists and references upstream
requirements by id.

**Artifact:** `design/design-spec.json`
```json
{
  "id": "DES-001",
  "implements_requirements": ["REQ-001"],
  "design_tokens_ref": "path or URL",
  "flows": [{"name": "string", "steps": ["string"]}],
  "components": [{"name": "string", "spec": "string"}],
  "status": "draft | approved | revising"
}
```

May wrap an external DESIGN.md (e.g. from awesome-design-md) as the token ref.

## architecture

**Purpose:** Define technical decisions and system boundaries.

**Active unit:** An ADR (Architecture Decision Record) or a stack choice.

**Entry criteria:** Requirements approved. Design may be in parallel.

**Exit criteria:** Stack decisions recorded, ADRs written for major choices.

**Artifacts:**
- `architecture/stack.json` — tech stack and boundaries
- `architecture/adrs/ADR-NNN.json` — one file per decision

```json
// ADR schema
{
  "id": "ADR-001",
  "title": "string",
  "status": "proposed | accepted | superseded",
  "context": "string (markdown)",
  "decision": "string (markdown)",
  "consequences": ["string"],
  "supersedes": "ADR-NNN | null"
}
```

## implementation

**Purpose:** Build the thing.

**Active unit:** A campaign (in `harness` terminology).

**Entry criteria:** Requirements, design (if applicable), architecture all in
approved status.

**Exit criteria:** Campaign `done`, all features complete.

**Executor:** Invoke the existing `harness` skill, pointing it at
`.engineering/implementation/.harness/` or similar isolated path.

**Artifact pointer:** `implementation/campaign-ref.json`
```json
{
  "campaign_id": "string",
  "harness_root": "path to .harness/ directory",
  "implements_requirements": ["REQ-001"],
  "status": "active | done | archived"
}
```

## test

**Purpose:** Verify the built thing matches the contract.

**Active unit:** A test plan for one campaign.

**Entry criteria:** Implementation campaign marked `done`.

**Exit criteria:** All planned tests executed, results recorded.

**Artifact:** `test/test-report.json`
```json
{
  "id": "TEST-001",
  "campaign_ref": "campaign-id",
  "plan": [{"name": "string", "type": "unit | integration | e2e | manual"}],
  "results": [{"name": "string", "status": "pass | fail | skipped",
               "evidence": "string"}],
  "status": "in_progress | passed | failed"
}
```

## release

**Purpose:** Prepare a release candidate for deployment.

**Active unit:** A release candidate.

**Entry criteria:** Test report in `passed` status.

**Exit criteria:** Release checklist complete, artifact tagged.

**Artifact:** `release/release-checklist.json`
```json
{
  "id": "REL-001",
  "version": "string (semver)",
  "checklist": [{"item": "string", "status": "pending | done | skipped",
                 "notes": "string"}],
  "rollback_plan": "string (markdown)",
  "tagged_commit": "string",
  "status": "preparing | released | rolled_back"
}
```

## ops

**Purpose:** Track what happens after release.

**Active unit:** A metric check, incident, or postmortem.

**Entry criteria:** A release exists.

**Exit criteria:** Varies by unit type.

**Artifacts:**
- `ops/incidents/INC-NNN.json`
- `ops/postmortems/PM-NNN.json`
- `ops/metrics.json`

---

## Minimal lifecycle

For trivial changes (bug fixes, small refactors), declare
`mode: minimal` in `lifecycle.json`. This requires only `implementation`
+ `test`, skipping discovery/design/architecture/release/ops.

## Relationship diagram

```
discovery ──┬──> design ─────┐
            │                 │
            └──> architecture ┴──> implementation ──> test ──> release ──> ops
```

Horizontal arrows show forward flow. Revisions propagate backward and mark
downstream artifacts as `stale`.
