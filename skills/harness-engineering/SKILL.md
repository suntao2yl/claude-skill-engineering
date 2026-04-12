---
name: harness-engineering
description: "Lifecycle orchestrator for AI-native software development. REQUIRES harness-plan skill (delegates implementation phase to it). 7 phases (discovery->design->architecture->implementation->test->release->ops) with schema-validated JSON artifacts as handoff protocol. Triggers: /harness-engineering, lifecycle, phase, discovery"
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
  if "All phases complete" in prior output: report + exit
  read @file resources/briefs/{current}.md for executor brief
  dispatch Agent(subagent_type="general-purpose", prompt=composed_prompt)
  run engineering_advance.py --project-root <path>
  exit 0 -> continue | exit 1 -> retry (max 2) | exit 3 -> LOOP_DETECTED, stop | exit 42 -> risk gate, pause for user
```
When multiple phases show "ready", dispatch executors in parallel.
Implementation phase delegates to harness-plan skill (see @file resources/briefs/implementation.md).

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
