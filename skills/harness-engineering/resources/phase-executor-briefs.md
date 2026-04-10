# Phase Executor Briefs

> **DEPRECATED:** This monolithic file is kept for backward compatibility.
> Per-phase briefs have moved to `resources/briefs/{phase}.md`.
> Auto-drive should load individual brief files instead of this file.

Detailed prompt templates for each phase's subagent. The engineering skill's
auto-drive loop reads these when dispatching work via the `Agent` tool.

**Usage pattern:** auto-drive composes a prompt by concatenating:
1. The header (shared context about the project goal + upstream artifacts)
2. The phase-specific brief from this file
3. The schema's required fields still missing
4. Clear "finish by editing X and nothing else" instruction

Each brief ends with a "Completion signal" — what the subagent should print
when done so the loop knows to proceed.

---

## discovery

**Role:** Requirements analyst. Convert a goal into a structured requirement.

**Inputs:** `.engineering/lifecycle.json` (for `goal` field)

**Output artifact:** `.engineering/discovery/requirements.json`

**Required fields to fill:**
- `title` (≤80 chars, first sentence of goal)
- `problem_statement` (≥20 chars, markdown ok, expands on goal)
- `users` (array, each ≥3 chars, concrete user profiles not generic labels)
- `success_metrics` (array, each ≥5 chars, measurable outcomes)
- `constraints` (array, can be empty)
- `out_of_scope` (array, can be empty)

**Judgment rules:**
- Infer users from the goal. If goal says "pet game for loneliness", users
  are "independent young professionals", "people who can't own pets", etc.
- Success metrics must be observable. "Users like it" is not a metric;
  "D7 retention ≥30%" or "3+ interactions/day median" is.
- If the goal is vague, make reasonable concrete assumptions and put edge
  cases in `out_of_scope`. Do not leave fields empty because "needs user input".
- `constraints` captures hard boundaries ("runs on iOS 15+", "no server").

**Completion signal:** print `DISCOVERY_EXECUTOR_DONE REQ-XXX` when the
artifact is saved with all required fields filled.

---

## design

**Role:** UX/interaction designer. Propose how the solution looks and feels.

**Inputs:** `.engineering/discovery/requirements.json` (MUST read first)

**Output artifact:** `.engineering/design/design-spec.json`

**Required fields:**
- `id` (DES-001, DES-002, ...)
- `implements_requirements` (array of REQ ids — must include the active REQ)
- `flows` (array of {name, steps}; each flow has ≥2 non-empty steps)
- `components` (array of {name, spec}; each spec ≥10 chars)

**Judgment rules:**
- Flows are user journeys. Name them by intent ("First meeting", "Daily
  check-in"), not by screen ("Home screen flow").
- Components are the visible UI pieces needed to support flows.
- If a flow implies a screen transition, one component per significant screen.
- Reference a design_tokens file if one exists at project root; otherwise null.

**Completion signal:** print `DESIGN_EXECUTOR_DONE DES-XXX`.

---

## architecture

**Role:** Tech lead. Pick the stack and record non-obvious decisions.

**Inputs:** `.engineering/discovery/requirements.json` (MUST read first)

**Output artifacts:**
- `.engineering/architecture/stack.json`
- `.engineering/architecture/adrs/ADR-NNN.json` (at least 1 file required)

**Required fields in stack.json:**
- `id` (ARCH-001, ...)
- `stack` (object describing tech choices)
- `adrs` (array of ADR ids referencing files in adrs/)

**Required fields per ADR:**
- `id`, `title`, `status` (proposed|accepted|superseded), `context`,
  `decision`, `consequences` (array), `supersedes` (ADR id or null)

**Judgment rules:**
- Write an ADR only for non-obvious decisions (choice between alternatives,
  significant trade-offs). "Use Python" for a Python-focused project is not
  an ADR.
- `consequences` must include both positive and negative outcomes.
- `stack` object has free-form keys matching the project domain (engine,
  language, database, deployment, etc.).

**Completion signal:** print `ARCHITECTURE_EXECUTOR_DONE ARCH-XXX` after
stack.json and ≥1 ADR file exist.

---

## implementation

**Role:** Delegate to `harness-plan` skill. Do NOT write production code here.

**Inputs:**
- `.engineering/design/design-spec.json`
- `.engineering/architecture/stack.json` + ADRs

**Output artifact:** `.engineering/implementation/campaign-ref.json`

**Process:**
1. Derive a harness-plan campaign goal from design + architecture.
2. Initialize harness-plan at `.engineering/implementation/.harness/`:
   - invoke harness-plan INIT with `--project-root
     <project>/.engineering/implementation/`
   - decompose goal into features with real `verification.command` entries
     (tests that actually exist or will exist)
3. Drive harness-plan through each feature until `done`. Use harness-plan's own scripts
   (`harness_pick_next.py`, `harness_transition.py`, `harness_checkpoint.py`).
4. After `progress_counts.done == total`:
   - fill campaign-ref.json with campaign_id, harness_root,
     implements_requirements, implements_design, implements_architecture,
     harness_progress
   - the engineering_advance.py will live-execute verification commands on
     its own (engineering's hard validator), so features must have real
     working verification or advance will fail

**Required fields in campaign-ref.json:**
- `campaign_id`, `harness_root`, `implements_requirements`

**Judgment rules:**
- Decompose into 3-8 features, each independently verifiable.
- Every feature MUST have a `verification.command` that actually runs.
- Features with placeholder/fake verification WILL fail advance's live check.

**Completion signal:** print `IMPLEMENTATION_EXECUTOR_DONE IMPL-XXX`.

---

## test

**Role:** Test engineer. Build and execute a test plan.

**Inputs:** `.engineering/implementation/campaign-ref.json`

**Output artifact:** `.engineering/test/test-report.json`

**Required fields:**
- `id`, `campaign_ref` (IMPL-XXX), `plan`, `results`

**Judgment rules:**
- Plan types: `unit | integration | e2e | manual`.
- Each plan item SHOULD have a `command` field if it's automatable.
- `results` must correspond 1:1 with `plan` entries. Each result has
  `name, status (pass|fail|skipped), evidence`.
- Evidence must be non-empty strings. "Works" is not evidence; include
  exit code, stdout excerpt, or screenshot path.
- Any item with a `command` field will be re-executed by engineering_advance.py
  hard validator. Fake commands will fail.

**Completion signal:** print `TEST_EXECUTOR_DONE TEST-XXX`.

---

## release

**Role:** Release engineer. Prepare a release candidate.

**Inputs:** `.engineering/test/test-report.json` (must be approved)

**Output artifact:** `.engineering/release/release-checklist.json`

**Required fields:**
- `id`, `version` (semver), `checklist`, `rollback_plan`, `tagged_commit`

**Judgment rules:**
- `tagged_commit` must be a real git ref (engineering_advance.py will
  `git rev-parse --verify` it).
- `checklist` items each have `{item, status, notes}`. Status options:
  `pending | done | skipped`. Pending items will block advance.
- `rollback_plan` must be concrete ("users uninstall; state is local-only"
  counts; "we'll figure it out" does not).

**Completion signal:** print `RELEASE_EXECUTOR_DONE REL-XXX`.

---

## ops

**Role:** Ops/SRE. Record metrics, incidents, postmortems.

**Inputs:** `.engineering/release/release-checklist.json`

**Output artifacts:**
- `.engineering/ops/metrics.json` (primary)
- `.engineering/ops/incidents/INC-NNN.json` (as needed)
- `.engineering/ops/postmortems/PM-NNN.json` (as needed)

**Required fields in metrics.json:**
- `id` (OPS-001)

**Judgment rules:**
- Initial ops artifact can be skeletal — just the metrics to watch.
- Incidents and postmortems get added post-release as reality happens.
- `metrics_tracked` array has entries of `{name, target, source}`.

**Completion signal:** print `OPS_EXECUTOR_DONE OPS-XXX`.

---

## Prompt composition template

When auto-drive dispatches to a subagent, it should construct a prompt like:

```
You are the <phase> executor for project "<goal>".

Project root: <absolute path>
Your artifact: <absolute path to active artifact>

UPSTREAM ARTIFACTS (read these first):
<concatenated JSON summaries of upstream artifacts>

YOUR BRIEF:
<brief from this file>

REQUIRED FIELDS STILL MISSING: <list>

CONSTRAINTS:
- Do not modify any files outside <phase>/ directory.
- Do not call any engineering_*.py scripts — the main loop runs those.
- When done, print exactly: <COMPLETION_SIGNAL>
```
