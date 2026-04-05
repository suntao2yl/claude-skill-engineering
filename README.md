# harness-engineering

[![Release](https://img.shields.io/github/v/release/suntao2yl/claude-skill-engineering)](https://github.com/suntao2yl/claude-skill-engineering/releases)
[![License](https://img.shields.io/github/license/suntao2yl/claude-skill-engineering)](./LICENSE)

**Lifecycle orchestrator for AI-native software development.**

A top-level Claude Code skill that coordinates the entire software
development lifecycle — from requirements capture through release — by
applying harness theory (compact machine state, structured artifacts,
deterministic transitions) at the phase level instead of the task level.

English · [中文](./README.zh-CN.md)

---

## What this is

`harness-engineering` is not a replacement for `harness-plan`. It is one layer up:

```
harness-engineering  ← lifecycle orchestrator (this project)
        │
        └── invokes harness-plan as the implementation-phase executor
                 │
                 └── harness-plan drives feature-level coding
```

### The 7 phases (locked)

```
discovery → design → architecture → implementation → test → release → ops
                  │                ▲
                  │                │
                  └────────────────┘
                (parallel where upstream allows)
```

Each phase owns a schema-validated JSON artifact. Transitions are enforced
by scripts, not ceremony. Failed validation blocks advance. Stale upstream
propagates downstream.

---

## Dependency: REQUIRES `harness-plan` skill

This skill **delegates implementation phase** to the
[`harness-plan`](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
skill. Without harness-plan, phases 1-3 and 5-7 work but phase 4 (implementation)
will block.

**Why not merge the two skills?**
- harness-plan is useful on its own for pure coding tasks
- merging would force all harness-plan users to load engineering's 3500-token
  lifecycle body on every invocation
- "Compose, do not embed" is principle #8

**Where harness-plan is expected:**
- `~/.claude/skills/harness-plan/SKILL.md`, or
- any installed plugin providing `harness-plan/skills/harness-plan/SKILL.md`

---

## Install

### Option A: manual (repo clone)

```bash
git clone https://github.com/suntao2yl/claude-skill-engineering.git && cd claude-skill-engineering

# install engineering only (checks for harness-plan, warns if missing):
./install.sh

# install engineering + harness-plan from a local source:
./install.sh --with-harness-plan /path/to/harness-plan-skill

# custom skills directory:
./install.sh --prefix /custom/skills/path
```

### Option B: Claude Code skill system

If you install `engineering` via Claude's skill manager/marketplace,
**install `harness-plan` first** via the same mechanism. Engineering's
`SKILL.md` includes a preflight check that verifies harness-plan is present
before running `init`.

---

## Quick start

```bash
# after installing both skills:

# in Claude Code:
/engineering init "Build a Python CLI that counts lines in a file, emit JSON, ship v0.1"

# Claude will:
# 1. create .engineering/ with 7 phase subdirs + seed REQ-001
# 2. auto-drive: fill discovery → advance → pause at risk gate → await --confirm
# 3. fill design + architecture in parallel → advance each → pause at arch gate
# 4. enter implementation → delegate to harness-plan → drive features to done
# 5. advance implementation (live-executes verification commands)
# 6. fill test-report → advance (live-executes test commands)
# 7. create git tag → advance release → pause at release gate
# 8. fill ops metrics → terminal
```

The user only confirms at **risk gates** (discovery / architecture / release
approval). Everything else auto-advances.

---

## The 7 phases

| # | Phase | Unit | Artifact | Validation |
|---|---|---|---|---|
| 1 | `discovery` | problem statement | `requirements.json` | users ≥3 chars, metrics ≥5 chars, statement ≥20 chars |
| 2 | `design` | design spec | `design-spec.json` | each flow has ≥2 non-empty steps, components specs ≥10 chars |
| 3 | `architecture` | ADR + stack | `stack.json` + `adrs/ADR-NNN.json` | ≥1 ADR file, declarations match files |
| 4 | `implementation` | harness-plan campaign | `campaign-ref.json` | harness-plan done==total, **live-execute** each verification.command |
| 5 | `test` | test plan | `test-report.json` | ≥1 pass, 0 fail, **live-execute** plan commands |
| 6 | `release` | release candidate | `release-checklist.json` | git tag is valid ref, no pending checklist items |
| 7 | `ops` | metrics/incidents | `metrics.json` + `incidents/` + `postmortems/` | minimal |

**Minimal mode** (`--mode minimal`) skips phases 1/2/3/6/7, keeping only
`implementation + test` — for bug fixes and small features.

---

## Key behaviors

- **Live verification**: `implementation` and `test` advance actually runs
  the declared commands, checks exit code, scans stderr for `ERROR:`/`FATAL:`,
  validates stdout against `expected` patterns. Filling fake JSON doesn't
  pass.
- **Risk gates**: `discovery.approved`, `architecture.approved`,
  `release.approved` require `--confirm` flag. `advance` exits 42 at a gate.
- **Stale propagation**: `revise <phase>` marks downstream artifacts stale;
  `advance` refuses stale artifacts without `--refresh-stale`.
- **Parallel phases**: design + architecture both depend only on discovery
  and can run concurrently.
- **Resumable**: a fresh Claude session reads `.engineering/lifecycle.json`
  and knows exactly where to resume.

---

## Project layout

```
harness-engineering/
├── SKILL.md                          # skill entry + auto-drive protocol
├── README.md                         # this file
├── README.zh-CN.md                   # Chinese version
├── USAGE.md                          # detailed operational guide
├── install.sh                        # installer with --with-harness-plan option
├── scripts/
│   ├── engineering_lib.py            # shared helpers
│   ├── engineering_init.py           # create .engineering/
│   ├── engineering_status.py         # one-screen lifecycle view
│   ├── engineering_phase.py          # enter a phase
│   ├── engineering_advance.py        # validate + advance (with live verification)
│   ├── engineering_revise.py         # rollback upstream, propagate stale
│   ├── engineering_reset.py          # archive + fresh start
│   └── engineering_validate.py       # state integrity check
├── resources/
│   └── phase-executor-briefs.md      # subagent prompt templates per phase
└── docs/
    ├── architecture.md               # design rationale
    ├── phases.md                     # phase specifications
    ├── principles.md                 # 10 guiding principles
    └── open-questions.md             # resolved/deferred decisions
```

---

## Status

**v0.1.0 shipped** — see [release notes](https://github.com/suntao2yl/claude-skill-engineering/releases/tag/v0.1.0).

Dogfooded end-to-end on two projects:
- `validation/lc-cli/` — real Python CLI, 11 pytest cases, full auto-drive loop
- `validation/godot-ai-pet/` — Godot 4.3 AI pet companion, standard 7-phase walkthrough

See `docs/` for architecture rationale and open questions.

---

## Related reading

Inspired by the [awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering)
curated list, particularly:
- Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- Anthropic's [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Thoughtworks' [humans and agents in software engineering loops](https://martinfowler.com/articles/exploring-gen-ai/humans-and-agents.html)

---

## License

MIT © 2026 — see [LICENSE](./LICENSE).
