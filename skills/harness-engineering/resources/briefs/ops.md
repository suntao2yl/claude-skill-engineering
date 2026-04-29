---
phase: ops
context_budget:
  max_input_tokens: 3000
  truncation_strategy: none
role: Ops/SRE + Knowledge Engineer
completion_signal: "OPS_EXECUTOR_DONE OPS-XXX"
---

# Ops Phase Brief

**Role:** Ops/SRE and knowledge engineer. Record metrics, incidents, and extract learnings.

**Inputs:** `.engineering/release/release-checklist.json`

**Output artifacts:**
- `.engineering/ops/metrics.json` (primary)
- `.engineering/ops/incidents/INC-NNN.json` (as needed)
- `.engineering/ops/postmortems/PM-NNN.json` (as needed)

**Required fields in metrics.json:**
- `id` (OPS-001)
- `learnings` (required for standard/deep scope)

## Step 1: Metrics

`metrics_tracked` array has entries of `{name, target, source}`.
Initial ops artifact can be skeletal — just the metrics to watch.

## Step 1.5: Eval baseline (v1.0.0)

On entry to ops, distill the test phase's results into reusable EVAL-NNN
cases and mark a baseline. This produces a regression detection harness
that survives model upgrades and refactors.

```
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --create
python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_eval.py --project-root <path> --run --mark-baseline
```

If the run isn't clean (any failures), the test phase wasn't actually
green — revise the test phase, don't bake a broken baseline. See
`resources/briefs/eval.md` for the full protocol.

## Step 2: Incidents & Postmortems

Incidents and postmortems get added post-release as reality happens.

## Step 3: Knowledge Compounding (v0.3.0)

Extract 3-5 structured learnings from the entire lifecycle. This is the knowledge compounding step — learnings from this cycle inform future cycles.

Each learning must have:
```json
{
  "category": "process|technical|tooling|communication",
  "insight": "What was learned",
  "evidence": "Specific reference (decision ID, error code, metric, phase)",
  "applicable_to": "When this learning applies in future projects"
}
```

**Categories:**
- `process` — workflow improvements, phase ordering, ceremony calibration
- `technical` — code patterns, architecture decisions, performance findings
- `tooling` — tool configuration, script improvements, integration lessons
- `communication` — requirement clarity, handoff quality, review effectiveness

**Evidence must be specific:** Reference decision IDs from decisions.jsonl, error codes from advance failures, metrics from phase_runs.jsonl, or specific artifact fields.

**Applicable_to must be actionable:** "When building CLI tools" is good. "In general" is not.

Future discovery phases can retrieve prior learnings via:
`python3 engineering_learn.py --project-root <path>`

**Completion signal:** print `OPS_EXECUTOR_DONE OPS-XXX`.

## Decision Logging

Log metric selection rationale and incident triage decisions to `.engineering/decisions.jsonl` with: phase="ops", classification and principle as appropriate.

## Insight Awareness

Before starting, check for insights targeting this phase:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --list --target ops --unaddressed`
Ops is the final phase — record insights for upstream phases to inform future lifecycles:
`python3 ${CLAUDE_SKILL_DIR}/scripts/engineering_insight.py --project-root <path> --add --source ops --target <upstream_phase> --kind <kind> --insight "..." --evidence "..."`
