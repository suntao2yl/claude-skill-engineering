---
phase: ops
context_budget:
  max_input_tokens: 3000
  truncation_strategy: none
role: Ops/SRE
completion_signal: "OPS_EXECUTOR_DONE OPS-XXX"
---

# Ops Phase Brief

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
