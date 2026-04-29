# harness-engineering — Troubleshooting

## advance exits 1 (validation failure)

1. Read stderr — it names missing or invalid fields.
2. Open the phase artifact and fix flagged fields.
3. Re-run `engineering_advance.py --project-root <path>`.

## advance exits 3 (loop detected)

Same error signature repeated 3 times. Auto-drive must stop.

1. `engineering_status.py --project-root <path>` — see the stuck phase.
2. Inspect the artifact manually — usually a field that keeps failing the same validation.
3. Fix the root cause, then resume auto-drive.

## advance exits 42 (risk gate)

A phase requires user approval (`discovery.approved`, `architecture.approved`, `release.approved`).

1. Present the artifact summary to the user.
2. Wait for explicit approval before continuing.

## lint reports cross-phase inconsistencies

1. `engineering_lint.py --project-root <path> --json` — structured output.
2. Each finding includes `source_phase`, `target_phase`, `description`.
3. Fix the upstream artifact first, then re-validate downstream.

## harness-plan not installed

Tell the user:

```text
Install harness-plan: see https://github.com/suntao2yl/claude-skill-harness
```
