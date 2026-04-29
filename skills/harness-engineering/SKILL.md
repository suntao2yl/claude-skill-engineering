---
name: harness-engineering
description: "Lifecycle orchestrator for AI-native software development. REQUIRES harness-plan skill (delegates implementation phase to it). 7 phases (discovery->design->architecture->implementation->test->release->ops) with schema-validated JSON artifacts as handoff protocol. Use when user says 'start a project lifecycle', 'run discovery phase', 'advance to next phase', 'check lifecycle status', or invokes /harness-engineering."
compatibility: "Requires Python 3.8+. Works in Claude Code CLI and Claude.ai."
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
metadata:
  author: suntao2yl
  version: 0.7.1
---

# Engineering (harness-engineering)

Lifecycle orchestrator: drive AI-native projects across 7 fixed phases via structured JSON artifacts.

## Hard Invariants
1. All state in `.engineering/` at project root. Phases communicate only through artifacts on disk.
2. One active unit per phase. Only the phase owner mutates that phase's artifacts.
3. Auto-advance on validation pass; pause at risk gates (discovery.approved, architecture.approved, release.approved).
4. Prefer scripts in `scripts/` over hand-editing JSON. Never hand-edit `.engineering/*.json` when a script exists.

## Phases (LOCKED)
| # | Phase | Artifact | Upstream |
|---|-------|----------|----------|
| 1 | discovery | requirements.json | user |
| 2 | design | design-spec.json | discovery |
| 3 | architecture | stack.json + adrs/ | discovery |
| 4 | implementation | campaign-ref.json | design+architecture |
| 5 | test | test-report.json | implementation |
| 6 | release | release-checklist.json | test |
| 7 | ops | metrics.json + incidents/ | release |

## Command Router
```
/harness-engineering init "goal"    -> Create .engineering/ + AUTO-DRIVE
/harness-engineering status         -> One-screen view (no loop)
/harness-engineering phase <name>   -> Enter phase, print upstream + schema
/harness-engineering advance        -> Validate + advance
/harness-engineering revise <phase> -> Mark upstream revising; downstream -> stale
/harness-engineering lint           -> Cross-phase consistency health check
/harness-engineering insight ...    -> Capture/list/address cross-phase insights
/harness-engineering reset          -> Archive .engineering/, start fresh
/harness-engineering gc             -> Run engineering_gc.py (dry-run by default)
```

## Auto-Drive Protocol
The whole point is unmanned lifecycle execution. On init or resume, enter loop:
```
while true:
  lc = read lifecycle.json; current = lc.current_phase
  if "All phases complete" in prior output: run engineering_lint.py, report findings + exit
  read @file resources/briefs/{current}.md for executor brief
  dispatch Agent(subagent_type="general-purpose", prompt=composed_prompt)
  run engineering_advance.py --project-root <path>
  exit 0 -> continue | exit 1 -> retry (max 2) | exit 3 -> LOOP_DETECTED, stop | exit 42 -> risk gate, pause for user
```
When multiple phases show "ready", dispatch executors in parallel.
Implementation phase delegates to harness-plan skill (see @file resources/briefs/implementation.md).
Do NOT read resources/phase-executor-briefs.md (deprecated; per-phase briefs live in resources/briefs/).

Loop detection: after validation failure, error signatures are hashed and stored in lifecycle.json.
If the same signature repeats 3 times consecutively, advance exits 3 and auto-drive stops.

**Decision principles** for auto-decisions (in priority order):
1. Completeness — finish what you started before starting new work
2. Boil lakes — do the complete thing when AI makes marginal cost near-zero
3. Pragmatic — working code over perfect architecture
4. DRY — extract shared patterns, don't duplicate
5. Explicit over clever — readable beats clever
6. Bias toward action — when in doubt, ship it and iterate

Every auto-decision is logged to `.engineering/decisions.jsonl` with phase, classification (mechanical/taste/user_challenge), principle, and rationale.

## Prerequisites
**Requires `harness-plan` skill** for implementation phase. Check:
`test -f ~/.claude/skills/harness-plan/SKILL.md || find ~/.claude/plugins -path '*/harness-plan/skills/harness-plan/SKILL.md' -print -quit | grep -q .`
If missing, tell user to install it before proceeding.

**Recommended: `harness-discipline` skill** for canonical TDD planning,
completion verification, and change-spec authoring. When installed,
`engineering_advance.py` prefers `completion-verify` for the implementation
gate and design/implementation briefs invoke `/tdd-plan` and `/change-spec`.
Without discipline, a degraded inline path is used (same verdicts, less
structured evidence). See `docs/dedup-matrix.md` for capability mapping.

## Script Canon
```
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_init.py --project-root <path> --goal "..."
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_status.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_advance.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_validate.py --project-root <path>
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_lint.py --project-root <path> [--json] [--severity warning]
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --add --source <phase> --target <phase> --kind <kind> --insight "..." --evidence "..."
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list [--target <phase>] [--unaddressed]
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_gc.py --project-root <path> [--apply]
```

## Runtime Files
- `.engineering/lifecycle.json` — master state
- `.engineering/{phase}/` — per-phase artifacts + archive/
- `.engineering/metrics/phase_runs.jsonl` — execution metrics (append-only)
- `.engineering/decisions.jsonl` — decision audit trail (append-only)
- `.engineering/insights.jsonl` — cross-phase insights (append-only, non-blocking)

## Known Limitations
- No concurrency safety (single-writer like git working tree).
- Schema auto-migrates v1→v2 on read (backward compatible).
- Harness-plan progress is read-only inside engineering.
- Forward transitions only auto-advance; `revise` is explicit.

## Gotchas
- Never hand-edit `.engineering/lifecycle.json` or any phase artifact JSON to bypass a failed validation. Always fix the root cause and re-run `engineering_advance.py`.
- The implementation phase MUST delegate to harness-plan. Do not write production code directly inside the implementation executor — it will pass advance validation but produce unmaintainable, untracked work.
- Subagents (phase executors) must NOT call `engineering_*.py` scripts. Only the auto-drive loop calls those. Subagents write artifacts; the loop validates and advances.
- After `engineering_advance.py` exits 1 (validation failure), do not skip to the next phase. Read the error output, fix the artifact, and re-run advance.
- Do not load all upstream artifacts into a subagent prompt. Pass only the immediate upstream artifact(s) listed in the Phases table.
- `engineering_lint.py` warnings are informational; errors are blocking. Do not ignore errors by re-running lint with `--severity warning` to hide them.

## Anti-patterns

Meta-rules for operating this orchestrator, distinct from per-phase gotchas above.

- **Don't inline schemas into phase briefs.** Briefs in `resources/briefs/*.md` should reference `@file resources/...` for schemas, not paste them. Inlined schemas drift; referenced ones stay consistent.
- **Don't run review in two phases.** The test phase already includes `/security-review` and multi-persona reviewers; release should not re-run them. Each capability has exactly one canonical phase — see `docs/dedup-matrix.md`.
- **Don't extend roles by writing prose.** When you find yourself adding a new role responsibility into a brief, instead update the generated `AGENTS.md` template (Phase 3+) so the role contract is the single source of truth across tools.

## Troubleshooting

**advance exits 1 (validation failure)**
1. Read the stderr output — it names the missing or invalid fields.
2. Open the phase artifact and fix the flagged fields.
3. Re-run `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_advance.py --project-root <path>`.

**advance exits 3 (loop detected)**
The same error signature repeated 3 times. Auto-drive must stop.
1. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_status.py --project-root <path>` to see the stuck phase.
2. Inspect the artifact manually — the issue is usually a field that keeps failing the same validation.
3. Fix the root cause, then resume auto-drive.

**advance exits 42 (risk gate)**
A phase requires user approval (discovery.approved, architecture.approved, or release.approved).
1. Present the artifact summary to the user.
2. Wait for explicit approval before continuing.

**lint reports cross-phase inconsistencies**
1. Run `python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_lint.py --project-root <path> --json` to get structured output.
2. Each finding includes `source_phase`, `target_phase`, and `description`.
3. Fix the upstream artifact first, then re-validate downstream.

**harness-plan not installed**
If the prerequisite check fails, tell the user:
`Install harness-plan: see https://github.com/suntao2yl/claude-skill-harness`

## Examples

**Example: init and auto-drive a small project**

```
User: /harness-engineering init "Build a CLI tool that converts CSV to JSON"

→ Runs engineering_init.py, creates .engineering/ with lifecycle.json
→ Enters auto-drive loop:
  1. discovery: fills requirements.json (title, problem_statement, users, success_metrics)
     → engineering_advance.py validates → exit 0 → auto-advance
  2. design: fills design-spec.json (flows, components)
     → exit 0 → auto-advance
  3. architecture: fills stack.json + ADR-001.json
     → exit 42 (risk gate: architecture.approved) → pauses for user
User: approved
  4. implementation: delegates to harness-plan, drives features to done
     → exit 0 → auto-advance
  5. test: builds test-report.json, re-executes verification commands
     → exit 0 → auto-advance
  6. release: fills release-checklist.json, verifies tagged_commit
     → exit 42 (risk gate) → pauses for user
User: approved
  7. ops: creates metrics.json skeleton
     → exit 0 → all phases complete
→ Runs engineering_lint.py, reports findings, exits loop.
```
