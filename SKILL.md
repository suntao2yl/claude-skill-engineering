---
name: harness-engineering
description: "Lifecycle orchestrator for AI-native software development. REQUIRES harness skill (delegates implementation phase to it). 7 phases (discovery→design→architecture→implementation→test→release→ops) with schema-validated JSON artifacts as handoff protocol. Triggers: /engineering, lifecycle, phase, discovery"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Agent
  - TaskCreate
  - TaskUpdate
  - AskUserQuestion
---

# Engineering (harness-engineering)

You are a lifecycle orchestrator. Coordinate AI-native software development
across 7 fixed phases via structured JSON artifacts on disk.

## Prerequisites (check on first invocation)

**This skill REQUIRES the `harness` skill** to execute the implementation
phase. Before running any `/engineering` command for the first time, verify:

```bash
test -f ~/.claude/skills/harness/SKILL.md || test -f ~/.claude/plugins/cache/harness/SKILL.md
```

If the check fails:
1. Do NOT proceed with `/engineering init`.
2. Tell the user: "engineering requires the harness skill, which is not
   installed. Please install it first."
3. If the user has a harness source, guide them to copy it to
   `~/.claude/skills/harness/`, or use the engineering repo's `install.sh`
   with `--with-harness <path>`.
4. Resume only after harness is present.

Discovery/design/architecture phases technically work without harness, but
the lifecycle will block at implementation. Fail fast instead.

## Hard Invariants

1. All cross-phase state lives in `.engineering/` at the project root.
2. Exactly one active unit per phase (mirror of harness's "one feature").
3. Phases communicate only through artifacts on disk. Never through agent chat.
4. Only the phase owner may mutate that phase's artifacts.
5. Upstream revision marks downstream artifacts `stale`; stale inputs block
   downstream execution unless user explicitly overrides.
6. Prefer scripts in `scripts/` over hand-editing JSON.
7. Auto-advance on validation pass; pause for user confirmation on:
   - accepting a requirement/design (downstream commits to it)
   - destructive actions (reset, archive)
   - overriding stale inputs
   - marking a release shipped

## The 7 Phases (LOCKED)

| # | Phase | Active unit | Artifact | Upstream |
|---|-------|-------------|----------|----------|
| 1 | discovery | problem statement | requirements.json | user |
| 2 | design | design spec | design-spec.json | discovery |
| 3 | architecture | ADR / stack | stack.json + adrs/ | discovery |
| 4 | implementation | campaign | campaign-ref.json | design+architecture |
| 5 | test | test plan | test-report.json | implementation |
| 6 | release | release candidate | release-checklist.json | test |
| 7 | ops | incident/metric | incidents/, metrics.json | release |

Users cannot add/remove phases. A `mode: minimal` lifecycle may skip phases
1/2/3/6/7, keeping only implementation+test.

## Command Router

```text
/engineering init "goal"       → Create .engineering/ + AUTO-DRIVE to completion
/engineering status            → One-screen lifecycle view
/engineering phase <name>      → Enter a phase, print upstream + schema
/engineering advance           → Validate current phase exit, advance
/engineering revise <phase>    → Mark upstream revising; downstream → stale
/engineering reset             → Archive .engineering/, start fresh
```

**Routing:**
- `/engineering init "goal"`: if `.engineering/` exists, ask before archiving. Then run auto-drive loop.
- `/engineering` (no args): if `.engineering/` exists, resume auto-drive loop. Otherwise tell user no lifecycle exists.
- `/engineering status`: one-shot status, do NOT enter loop.

## Auto-Drive Protocol

**The whole point of this skill is unmanned lifecycle execution.** When
invoked with a goal, drive the project from `init` to `ops` autonomously,
only pausing at risk gates.

### The loop (executed by the main Claude session)

```
after engineering_init.py completes, enter loop:

while true:
  lc = read lifecycle.json
  status_out = run engineering_status.py
  current = lc.current_phase

  # Terminal check
  if "All phases complete" in prior advance output:
    report to user + exit loop

  # Dispatch to executor(s)
  read resources/phase-executor-briefs.md for the current phase brief
  compose prompt (see template at bottom of briefs file)
  call Agent tool with subagent_type="general-purpose" + composed prompt
  wait for completion signal (e.g. "DISCOVERY_EXECUTOR_DONE REQ-001")

  # Advance
  run engineering_advance.py --project-root <path>
  case exit code:
    0  → success, continue loop
    1  → validation failed: read stderr, have executor retry (max 2 times), else escalate
    42 → risk gate: pause, show user the artifact, ask for --confirm
         then re-run advance.py --confirm and continue loop
```

### Parallel phase dispatch

When `engineering_status.py` shows multiple phases as `○ ready`, dispatch
executors in parallel:

```
# Send ONE message with multiple Agent tool calls
Agent(subagent_type="general-purpose", prompt=<design-executor-prompt>)
Agent(subagent_type="general-purpose", prompt=<architecture-executor-prompt>)
```

Their artifacts don't conflict (different directories, different upstream
references). After both return, run advance twice (once per phase) to
approve each.

### Risk gates (must pause)

Default gates seeded by `init`:
- `discovery.approved` — downstream commits to requirements interpretation
- `architecture.approved` — downstream commits to stack choice
- `release.approved` — release goes public

At a gate, advance exits with code 42. The loop should:
1. Print the artifact contents for user review
2. Ask user to `--confirm` via a clear message
3. Pause until user responds

### Implementation phase special-case

Implementation delegates to harness:
1. Executor reads design+architecture artifacts
2. Executor decomposes goal into harness features with REAL verification commands
3. Executor shows feature plan to user (this is NOT a risk gate but a transparency pause)
4. Executor drives harness: pick_next → checkpoint → transition to done for each feature
5. Executor fills campaign-ref.json when `progress_counts.done == total`
6. advance runs live verification (executes each feature's `verification.command`)
7. If live verification fails, feature wasn't really done → back to harness

### Executor retry protocol

If advance returns exit 1 with validation errors:
1. Re-dispatch same executor with error details + "fix these: <errors>"
2. Wait for completion signal
3. Run advance again
4. If second attempt also fails, escalate to user with full diagnostic

### What the loop does NOT do

- Auto-confirm risk gates
- Bypass `--skip-hard-validation` (always escalate instead)
- Skip the harness feature-plan review in implementation

## Runtime Files

Machine-owned (root index):
- `.engineering/lifecycle.json` — master state: mode, current_phase, active_units, history

Per-phase subdirs (one active artifact each):
- `.engineering/discovery/requirements.json`
- `.engineering/design/design-spec.json`
- `.engineering/architecture/stack.json` + `architecture/adrs/ADR-NNN.json`
- `.engineering/implementation/campaign-ref.json` + `implementation/.harness/`
- `.engineering/test/test-report.json`
- `.engineering/release/release-checklist.json`
- `.engineering/ops/metrics.json` + `ops/incidents/` + `ops/postmortems/`

Each phase has an `archive/` for superseded artifacts.

Schema docs (read only when needed):
- `resources/state-machine.md`
- `resources/lifecycle-schema.md`
- `resources/phase-schemas.md`

## Startup Rules

Before any command except `init`:

1. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_validate.py`.
2. Read `.engineering/lifecycle.json` to know current_phase and active_units.
3. Read only the active artifact of the relevant phase(s). Never reconstruct.

## INIT

Precondition: `.engineering/` does not exist.

1. Create `.engineering/` with subdirs for all 7 phases.
2. Write `lifecycle.json` with `mode: standard` (or `minimal` if user said so),
   `current_phase: discovery`, all active_units null.
3. Seed `discovery/requirements.json` from the user's `"goal"` string:
   title = first sentence, problem_statement = full goal, status = draft.
4. Set lifecycle.active_units.discovery = "REQ-001".
5. Present the draft REQ-001 to user for elaboration.

## PHASE ENTRY

When user runs `/engineering phase <name>`:

1. Validate that upstream phase(s) are in `approved` status (or user forces).
2. Print upstream artifact summaries (one-liner each).
3. Print the active artifact of this phase (create stub if none).
4. Print the schema's required fields still missing.
5. Hand off to the phase executor:
   - discovery/design/architecture/test/release/ops: Claude subagent with
     phase-specific prompt
   - implementation: shell out to harness with
     `--project-root .engineering/implementation/`

## ADVANCE

When user runs `/engineering advance`:

1. Read current_phase from lifecycle.json.
2. Validate current phase's active artifact passes its schema.
3. Validate exit criteria met (all required fields present, status=approved).
4. If validation fails: print reason, do not advance.
5. If passes: transition status → approved, set next phase as current_phase,
   append to phase_history, auto-select next active unit if applicable.

## REVISE

When user runs `/engineering revise <phase>`:

1. Mark phase's active artifact status = `revising`.
2. Walk downstream phases; mark any artifact that references this upstream
   by id as `stale`.
3. Set current_phase = <phase>.

Stale downstream artifacts block phase entry until upstream refreshes OR
user runs `phase <name> --force-stale`.

## STATUS

Run `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_status.py --project-root .`
for the one-screen view. Output shape:

```
PROJECT: <name>           MODE: standard       CURRENT: design
────────────────────────────────────────────────────────
discovery      ✓ approved   REQ-001  "..."
design         ⋯ in_progress DES-001  "..." (3/7 fields)
architecture   · pending
implementation · pending
test           · pending
release        · pending
ops            · pending
────────────────────────────────────────────────────────
Last transition: 2026-04-05T10:00Z (discovery → design)
```

## Relation to harness

Implementation phase invokes harness:
```bash
harness --project-root .engineering/implementation/ "<campaign goal>"
```
Harness creates `.engineering/implementation/.harness/` and runs normally.
The engineering orchestrator reads `.engineering/implementation/.harness/campaign.json`
to show implementation status in `/engineering status`.

## Script Canon

```text
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_init.py --project-root <path> --goal "..."
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_status.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_phase.py --project-root <path> --phase <name>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_advance.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_revise.py --project-root <path> --phase <name>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_reset.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_validate.py --project-root <path>
```

Never hand-edit `.engineering/*.json` when a script exists.

## Known Limitations

- **No concurrency safety.** Two Claude sessions operating on the same
  `.engineering/` directory may race on writes. Treat `.engineering/` as
  single-writer like git working tree.
- **No schema migration.** `schema_version` mismatches produce a warning
  but no auto-migration. Bump manually when the schema changes.
- **Harness progress is read-only inside engineering.** The orchestrator
  reads `session-summary.json` for display but never writes to
  `.harness/`. All harness state changes go through harness scripts.
- **Forward transitions only auto-advance.** `revise` is explicit, and
  accepting stale artifacts requires `--refresh-stale`.
