# harness-engineering — Detailed Reference

## Auto-drive

Unmanned lifecycle execution. On init or resume, enter loop:

```text
while true:
  lc = read lifecycle.json; current = lc.current_phase
  if "All phases complete" in prior output:
    run engineering_lint.py, report findings + exit
  read @file resources/briefs/{current}.md for executor brief
  dispatch Agent(subagent_type="general-purpose", prompt=composed_prompt)
  run engineering_advance.py --project-root <path>
  exit 0  → continue
  exit 1  → retry (max 2)
  exit 3  → LOOP_DETECTED, stop
  exit 42 → risk gate, pause for user
```

When multiple phases show "ready", dispatch executors in parallel. The architecture phase may dispatch parallel sub-agents to design alternative interfaces (see "Parallel interface design" below).

Implementation phase delegates to harness-plan (see `@file resources/briefs/implementation.md`).

Do NOT read `resources/phase-executor-briefs.md` (deprecated; per-phase briefs live in `resources/briefs/`).

### Loop detection

After validation failure, error signatures are hashed and stored in `lifecycle.json`. Same signature 3 times consecutively → advance exits 3 → auto-drive stops.

### Decision principles (priority order)

1. **Completeness** — finish what you started before starting new work.
2. **Boil lakes** — do the complete thing when AI makes marginal cost near-zero.
3. **Pragmatic** — working code over perfect architecture.
4. **DRY** — extract shared patterns, don't duplicate.
5. **Explicit over clever** — readable beats clever.
6. **Bias toward action** — when in doubt, ship it and iterate.

Every auto-decision logged to `.engineering/decisions.jsonl` with phase, classification (`mechanical | taste | user_challenge`), principle, rationale.

### Parallel interface design (architecture phase, optional)

When the architecture phase faces a non-obvious interface choice (e.g. event bus vs. RPC vs. queue; columnar vs. row-store), dispatch 2-3 parallel sub-agents — each producing a complete interface sketch under a different paradigm — and have the orchestrator pick. Cheaper than living with the wrong choice. Adapted from `mattpocock/skills/design-an-interface`.

Use only when: the choice is contested, the cost of switching later is high, and a one-shot decision could trap the team.

## Script canon

```text
engineering_init.py --project-root <path> --goal "..."
engineering_status.py --project-root <path>
engineering_advance.py --project-root <path>
engineering_validate.py --project-root <path>
engineering_lint.py --project-root <path> [--json] [--severity warning]
engineering_insight.py --project-root <path> --add --source <phase> --target <phase> --kind <kind> --insight "..." --evidence "..."
engineering_insight.py --project-root <path> --list [--target <phase>] [--unaddressed]
engineering_gc.py --project-root <path> [--apply]
engineering_agents.py --project-root <path>
engineering_eval.py --project-root <path> [--create | --run [--mark-baseline] | --baseline | --compare baseline | --list-runs]
```

## Known limitations

- No concurrency safety (single-writer, like git working tree).
- Schema auto-migrates v1→v2 on read (backward compatible).
- Harness-plan progress is read-only inside engineering.
- Forward transitions only auto-advance; `revise` is explicit.

## Gotchas

- Never hand-edit `.engineering/lifecycle.json` or any phase artifact JSON to bypass a failed validation. Fix the root cause, re-run `engineering_advance.py`.
- Implementation phase MUST delegate to harness-plan. Don't write production code directly inside the implementation executor — it will pass advance validation but produce unmaintainable, untracked work.
- Subagents (phase executors) must NOT call `engineering_*.py` scripts. Only the auto-drive loop calls those.
- After `engineering_advance.py` exits 1, do not skip to the next phase. Read the error, fix the artifact, re-run advance.
- `engineering_lint.py` warnings are informational; errors are blocking. Don't ignore errors by re-running with `--severity warning` to hide them.
