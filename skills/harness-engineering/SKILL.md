---
name: harness-engineering
description: "Lifecycle orchestrator for AI-native software development. Drives 7 phases (discovery → design → architecture → implementation → test → release → ops) via schema-validated JSON artifacts. REQUIRES harness-plan for the implementation phase. Use when user says 'start a project lifecycle', 'run discovery phase', 'advance to next phase', 'check lifecycle status', or invokes /harness-engineering."
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
  version: 1.0.3
---

# Engineering (harness-engineering)

Lifecycle orchestrator: drive AI-native projects across 7 fixed phases via structured JSON artifacts.

## Hard invariants

1. All state in `.engineering/` at project root. Phases communicate only through artifacts on disk.
2. One active unit per phase. Only the phase owner mutates that phase's artifacts.
3. Auto-advance on validation pass; pause at risk gates (`discovery.approved`, `architecture.approved`, `release.approved`).
4. Prefer `scripts/` over hand-editing JSON. Never hand-edit `.engineering/*.json` when a script exists.

## Phases (LOCKED)

| # | Phase | Artifact | Upstream |
|---|---|---|---|
| 1 | discovery | requirements.json | user |
| 2 | design | design-spec.json | discovery |
| 3 | architecture | stack.json + adrs/ | discovery |
| 4 | implementation | campaign-ref.json | design + architecture |
| 5 | test | test-report.json | implementation |
| 6 | release | release-checklist.json | test |
| 7 | ops | metrics.json + incidents/ | release |

## Command router

```text
/harness-engineering init "goal"   → create .engineering/ + auto-drive
/harness-engineering status        → one-screen view (no loop)
/harness-engineering phase <name>  → enter phase, print upstream + schema
/harness-engineering advance       → validate + advance
/harness-engineering revise <p>    → mark upstream revising; downstream → stale
/harness-engineering lint          → cross-phase consistency
/harness-engineering insight ...   → capture/list/address insights
/harness-engineering reset         → archive .engineering/, start fresh
/harness-engineering gc            → engineering_gc.py (dry-run by default)
```

## Auto-drive (one-paragraph)

On init/resume, loop: read `lifecycle.json` → load `resources/briefs/{current}.md` → dispatch `Agent(general-purpose)` to fill the phase artifact → run `engineering_advance.py`. Exit codes: `0` advance, `1` retry (max 2), `3` loop detected (stop), `42` risk gate (pause). Multiple "ready" phases dispatch in parallel. Implementation delegates to `harness-plan`. See [REFERENCE.md](REFERENCE.md#auto-drive) for full protocol and decision principles.

## Prerequisites

- **Required: `harness-plan`** for implementation phase. Check:
  `test -f ~/.claude/skills/harness-plan/SKILL.md || find ~/.claude/plugins -path '*/harness-plan/skills/harness-plan/SKILL.md' -print -quit | grep -q .`
- **Recommended: `harness-discipline`** — when installed, advance prefers `/completion-verify` for the implementation gate; design/implementation briefs invoke `/tdd-plan` and `/change-spec`. Without discipline, a degraded inline path produces same verdicts with less structured evidence. See `docs/dedup-matrix.md`.

## Runtime files

- `.engineering/lifecycle.json` — master state (also holds `eval_baseline`)
- `.engineering/{phase}/` — per-phase artifacts + `archive/`
- `.engineering/eval/cases/EVAL-NNN.json` — distilled regression cases (Phase 5)
- `.engineering/eval/runs/run-<ts>/result.json` — eval execution records
- `.engineering/metrics/phase_runs.jsonl` — append-only execution metrics
- `.engineering/decisions.jsonl` — append-only decision audit trail
- `.engineering/insights.jsonl` — append-only cross-phase insights
- `AGENTS.md` (project root) — cross-tool role contract; auto-generated and refreshed on phase transitions. Hand-edits outside BEGIN/END markers preserved.

## Anti-patterns

- **Don't inline schemas into briefs.** Briefs reference `@file resources/...`. Inlined schemas drift; referenced ones stay consistent.
- **Don't run review in two phases.** Test phase already includes `/security-review` + multi-persona reviewers; release should not re-run them. See `docs/dedup-matrix.md`.
- **Don't extend roles by writing prose.** Update generated `AGENTS.md` template (Phase 3+) so the role contract is the single source of truth across tools.
- **Subagents must NOT call `engineering_*.py`.** Only the auto-drive loop calls those. Subagents write artifacts; the loop validates and advances.
- **Don't load all upstream artifacts** into a subagent prompt — only the immediate upstream listed in the Phases table.

## Composes with

- `harness-plan` — drives the implementation phase.
- `/tdd-plan` — used inside design/implementation briefs.
- `/change-spec` — used to break large features into reviewable units.
- `/completion-verify` — canonical executor for test gate.
- `caveman` + `git-guardrails` — recommended in autodrive.

See [REFERENCE.md](REFERENCE.md), [EXAMPLES.md](EXAMPLES.md), [TROUBLESHOOTING.md](TROUBLESHOOTING.md), `docs/principles.md`, `docs/architecture.md`, `docs/phases.md`.
