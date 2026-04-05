# Usage Guide

How to actually use `harness-engineering` skill on a real project. Read this once,
reference later.

## Prerequisites

- Python 3.10+
- `harness-plan` skill installed at `~/.claude/skills/harness-plan/` (for implementation phase)
- Optional: `git` (needed only for release phase `tagged_commit` validation)

## Install

```bash
cp -r harness-engineering ~/.claude/skills/harness-engineering
```

Claude should now recognize `/engineering` as a skill. Verify:

```bash
ls ~/.claude/skills/harness-engineering/SKILL.md
```

## First project: walk-through

### 1. Initialize lifecycle in your project

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_init.py \
  --project-root /path/to/your/project \
  --goal "One-sentence description of what you're building." \
  --mode standard
```

Creates `.engineering/` with 7 phase subdirs and seeds `REQ-001` from your goal.

**Modes:**
- `standard` — all 7 phases active
- `minimal` — only `implementation` + `test` (for bug fixes, tiny features)

### 2. Check status anytime

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_status.py \
  --project-root /path/to/your/project
```

Shows which phases are `ready`, `in_progress`, `approved`, `stale`, or `skipped`,
plus harness-plan progress if implementation has started.

### 3. Enter a phase

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_phase.py \
  --project-root /path/to/your/project \
  --phase discovery
```

Prints upstream artifacts, active artifact state, and a brief for the phase
executor. You (or Claude) then edit the phase's JSON artifact to fill
required fields.

**Artifact locations:**
- `discovery/requirements.json`
- `design/design-spec.json`
- `architecture/stack.json` + `architecture/adrs/ADR-NNN.json`
- `implementation/campaign-ref.json` + `implementation/.harness/`
- `test/test-report.json`
- `release/release-checklist.json`
- `ops/metrics.json`

### 4. Advance to next phase

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_advance.py \
  --project-root /path/to/your/project
```

Runs 3 gates:
1. **Required fields present** (no empty strings / empty arrays)
2. **Not stale** (pass `--refresh-stale` to re-approve stale artifacts)
3. **Phase-specific hard validation** (see below)

If all pass, marks current artifact `approved` and sets `current_phase` to
the next phase whose upstream is ready.

**Hard validators per phase:**

| Phase | Checks |
|---|---|
| `discovery` | users and success_metrics have non-trivial content; problem_statement ≥20 chars |
| `design` | each flow has non-empty steps; each component has spec ≥10 chars |
| `architecture` | ≥1 ADR file exists; declared ADRs reference real files |
| `implementation` | harness-plan done == total; baseline not failing; **live-executes** campaign `test_command` + each done feature's `verification.command` |
| `test` | ≥1 pass, 0 fails, non-empty evidence; **live-executes** any plan item with a `command` field |
| `release` | `tagged_commit` is a valid git ref; checklist has no `pending` items |

Live execution catches "exit 0 but stderr has ERROR:" (e.g. Godot, cargo
failures) and "expected stdout missing" patterns.

**Bypass hard validation** (use sparingly, leaves audit trail in
`phase_history`):
```bash
... engineering_advance.py --skip-hard-validation
```

### 5. Revise (rollback upstream)

If requirements change mid-project:

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_revise.py \
  --project-root /path/to/your/project \
  --phase discovery
```

Marks discovery as `revising`, propagates `stale` to all downstream
artifacts. Downstream phases can't be advanced until their artifacts are
re-approved via `--refresh-stale` or regenerated.

### 6. Reset (archive + start fresh)

```bash
python3 ~/.claude/skills/harness-engineering/scripts/engineering_reset.py \
  --project-root /path/to/your/project
```

Copies entire `.engineering/` to `.engineering-archive/<name>-<ts>/` and
removes the live one. Pass `--keep` to archive without deleting.

## Implementation phase: harness-plan integration

The implementation phase delegates to the `harness-plan` skill. When you enter
it, engineering tells you to:

```bash
# Initialize harness-plan with engineering's implementation dir as its project-root:
# (Claude performs this interactively via the `harness-plan` skill)
# Harness-plan creates .engineering/implementation/.harness/
```

After harness-plan runs and completes all features (`progress_counts.done == total`):

1. Fill `.engineering/implementation/campaign-ref.json`:
   - `campaign_id`, `harness_root`, `implements_requirements`
   - `harness_progress: {"done": N, "total": N}`
2. Run `engineering_advance.py` — it will read harness-plan summary, verify
   completion, live-run verification commands, and approve.

## Principles recap

1. **Machine state is source of truth.** Don't reconstruct from memory.
2. **Phases communicate via artifacts**, never through chat.
3. **Structured first, prose second.** Prefer typed fields.
4. **One active unit per phase.**
5. **Auto-advance, risk-gated pause.** Stale and destructive transitions
   require explicit flags.
6. **Skippable phases, non-skippable gates.** `minimal` mode skips discovery/
   design/architecture/release/ops. But within an active phase, exit
   criteria can't be bypassed (except via `--skip-hard-validation`).

## Troubleshooting

**`No .engineering/ directory at ...`** → you haven't run `engineering_init.py`
on this project, or `--project-root` points at the wrong path.

**`Cannot advance — artifact is STALE`** → run the phase script again, update
the artifact, or use `--refresh-stale` if still valid.

**`Harness features incomplete: 2/3 done`** → go back to harness-plan, finish the
remaining features, then re-run advance.

**`stderr contains errors: ERROR: File not found`** → your verification
command is broken (missing test file, wrong path). Fix the underlying issue
— don't mask it with `--skip-hard-validation` except as a temporary unblock.

**`tagged_commit '...' is not a valid git ref`** → `git tag v0.1.0` first,
then re-run advance.

## Known limitations

- No concurrency safety (single-writer model)
- No schema version migration (manual bump on change)
- Risk-gated human confirmation prompts are documented in SKILL.md but not
  yet implemented in scripts
