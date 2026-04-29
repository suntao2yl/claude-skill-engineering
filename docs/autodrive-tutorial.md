# Autodrive Tutorial: end-to-end automated project advancement

This tutorial walks through running an entire project from "I have an idea"
to "shipped + regression baseline" without operator input between phases,
using `harness-engineering` + `harness-plan` (autodrive) +
`harness-discipline`.

You'll spend ~5 minutes on the human-in-the-loop steps (3 risk gates) and
several token-funded hours on the automated steps. Plan accordingly.

## Prerequisites

```bash
# All three plugins installed and at compatible versions
claude plugin list | grep -E "harness-(engineering|plan|discipline)"
# expected:
#   harness-discipline@harness-discipline-marketplace   ≥ 0.1.0
#   harness-engineering@harness-engineering-marketplace ≥ 1.0.0
#   harness-plan@suntao-skills                          ≥ 0.5.0
```

If any are missing or older, install / update them:

```bash
/plugin marketplace add suntao2yl/claude-skill-engineering
/plugin marketplace add suntao2yl/claude-skill-harness
/plugin marketplace add suntao2yl/harness-discipline
/plugin install harness-engineering@harness-engineering-marketplace
/plugin install harness-plan@suntao-skills
/plugin install harness-discipline@harness-discipline-marketplace
```

You'll also need:
- a fresh git repo (autodrive expects to commit per feature)
- the `claude` binary on your `PATH` (Stop hook spawns headless sessions)
- enough Anthropic API credit for ~20 full Claude sessions per campaign
  (each session is one feature; cap configurable)

## The full pipeline

```
   ┌──────────────────────── manual gates ──────────────────────────┐
   │                                                                │
   ▼                                                                ▼

discovery → design → architecture → implementation → test → release → ops
              ▲                            │                            │
              │                            │ delegates to               │
              │                            ▼                            │
              │                       harness-plan                      │
              │                            │                            │
              │                            │ autodrive on               │
              │                            ▼                            │
              │                  ┌─────────────────────┐                │
              │                  │ F001 → commit → end │                │
              │                  │   ↓ (Stop hook)     │                │
              │                  │ F002 → commit → end │                │
              │                  │   ↓                 │                │
              │                  │  ...                │                │
              │                  │   ↓                 │                │
              │                  │ Final review        │                │
              │                  └─────────────────────┘                │
              │                                                         │
              └────────── revise on insight (any → upstream) ───────────┘

   /harness-engineering         confirm gates             eval baseline
                                (discovery.approved,
                                 architecture.approved,
                                 release.approved)
```

## Step 1: init the lifecycle

In an empty (or near-empty) git repo:

```bash
mkdir my-project && cd my-project && git init && touch README.md
git add . && git commit -m "init"

claude
```

Then in the Claude session:

```
/harness-engineering "build a CLI tool that exports a Postgres table to CSV with optional column filtering and quoted strings"
```

Engineering creates `.engineering/` and `AGENTS.md`, runs the discovery
phase executor, and pauses at the `discovery.approved` risk gate.

What was created:

```
.engineering/
├── lifecycle.json
├── discovery/requirements.json
├── design/, architecture/, implementation/, test/, release/, ops/   (empty)
├── decisions.jsonl
└── insights.jsonl
AGENTS.md
```

Read `requirements.json`. If the discovered users / metrics / problem
statement match your intent, approve:

```
/harness-engineering advance --confirm
```

Engineering then auto-runs design → architecture → pauses at
`architecture.approved`. Read the ADRs at `.engineering/architecture/adrs/`,
approve again with `--confirm`.

## Step 2: kick off implementation under autodrive

After `architecture.approved`, engineering enters the implementation phase
and (per the implementation brief) delegates to harness-plan.

In the same Claude session, harness-plan runs INIT inside
`.engineering/implementation/.harness/` (with `/tdd-plan` from discipline
seeding each feature's verification command). When it presents the feature
plan, approve it.

Then enable autodrive:

```
/harness-plan autodrive on
```

This writes `.harness/autodrive.json` with `enabled: true,
max_iterations: 20`. Configure higher if you have many features:

```bash
python3 ~/.claude/plugins/cache/suntao-skills/harness-plan/*/skills/harness-plan/scripts/harness_autodrive.py \
    --project-root .engineering/implementation \
    --enable --max-iterations 30
```

Now end the current Claude session (just type `/exit` or close the
terminal). The Stop hook fires:

1. Reads `.engineering/implementation/.harness/autodrive.json`
2. Checks the campaign isn't done yet
3. Spawns `claude -p "/harness-plan"` as a detached process
4. Logs to `.engineering/implementation/.harness/autodrive.log`

The new headless session resumes the campaign, picks the first feature,
implements it, runs `/completion-verify`, transitions to done, commits,
and exits. Stop hook fires again, spawns the next session for F002. And
so on.

## Step 3: monitor

Tail the autodrive log:

```bash
tail -f .engineering/implementation/.harness/autodrive.log
```

You'll see one block per feature:

```
[2026-04-29T10:00:00Z] decide: continuing — iteration 1/20, counts=0/8, current=F001
[2026-04-29T10:00:00Z] decide: continuation session spawned
[2026-04-29T10:14:23Z] decide: continuing — iteration 2/20, counts=1/8, current=F002
...
```

Check git history:

```bash
git log --oneline | head
# feat(harness): complete F008 - Add CSV column-selector flag
# feat(harness): complete F007 - Quote strings with embedded commas
# feat(harness): complete F006 - ...
```

Status snapshots:

```bash
python3 ~/.claude/plugins/cache/suntao-skills/harness-plan/*/skills/harness-plan/scripts/harness_autodrive.py \
    --project-root .engineering/implementation --status
```

## Step 4: the final review session

When all features reach `done`, the Stop hook detects "all features
terminal", flips `phase` from `feature` to `review`, and spawns one more
headless session with a dedicated prompt:

1. Run `/security-review` against the campaign diff
2. Launch four parallel general-purpose Agent subagents:
   - Testability reviewer
   - Maintainability reviewer
   - Performance reviewer
   - Design-consistency reviewer
3. Concatenate findings into `.engineering/implementation/.harness/review-report.md`
4. Commit the report
5. Mark `phase: done`, exit

The chain is now stopped. Open the review report:

```bash
$EDITOR .engineering/implementation/.harness/review-report.md
```

## Step 5: continue the engineering lifecycle

Open a fresh Claude session in the project. The SessionStart hook injects
the autodrive summary; the engineering skill picks up where implementation
left off:

```
/harness-engineering advance
```

Engineering's implementation gate runs verification one more time
(via `/completion-verify` if discipline is installed) and advances to the
test phase. Test phase runs multi-persona review. Release phase asks for
the release-approval risk gate (`--confirm` once more). Then ops phase.

## Step 6: bake an eval baseline

In the ops phase, the brief tells the executor to:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --create
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --run --mark-baseline
```

This distills `test-report.json`'s passing tests into `EVAL-NNN` cases and
records a baseline run id in `lifecycle.json -> eval_baseline`.

Months later, after refactors or model changes:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --run
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root . --compare baseline
```

Exits 1 if any eval flipped pass → fail, listing every regression by id.

## Aborting the chain

At any point:

```bash
# Soft stop — next Stop tick will bail
touch .engineering/implementation/.harness/autodrive.fail

# Or fully delete config (no future Stop ticks do anything)
rm .engineering/implementation/.harness/autodrive.json
```

Or from inside a Claude session:

```
/harness-plan autodrive off
```

## Common failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Autodrive log shows "ERROR: cannot find `claude` binary" | `claude` not on `PATH` for the Stop-hook subprocess | export `CLAUDE_BINARY` in your shell init, or symlink to `/usr/local/bin` |
| Chain stops after iteration N with `phase=done` but features not all done | Hit `max_iterations` cap | `harness_autodrive.py --enable --max-iterations 50`, then `--reset` the fail marker if any |
| Autodrive log is empty even after session ends | Stop hook didn't fire (likely Ctrl-C exit, not natural completion) | Reopen Claude, type `/exit` to let session end naturally; or run `/harness-plan` once to nudge the next feature |
| Feature `git commit` produced "nothing to commit" warnings | Feature implementation didn't actually change tracked files | Read the feature's checkpoint to see what was done; consider whether the feature was correctly scoped |
| Stop hook exit 0 but no spawn happened | `.harness/autodrive.fail` exists from a prior failure | `rm .harness/autodrive.fail` to clear the marker, then `/harness-plan autodrive on` to resume |

## Cost model

- ~1 Claude session per feature
- 1 review session at the end of implementation
- 1 session per `--confirm` gate (3 gates total)
- 1 session for ops + eval baseline

For a 10-feature campaign, expect ~14 full Claude sessions, each running
to completion (10–20 minutes per session typical, depending on feature
complexity). Budget tokens accordingly.

## Recommended first run

Don't try this on a real project first. Pick a small toy:

```
/harness-engineering "build a CLI that prints fibonacci(N)"
```

3 features max, runs in ~30 minutes total, costs maybe $5 in Anthropic
API credit. You'll see exactly how the chain behaves before you commit
to a real campaign.
