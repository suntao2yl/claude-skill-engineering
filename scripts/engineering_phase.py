#!/usr/bin/env python3
"""Enter a phase: validate upstream, print context, emit executor brief."""
from __future__ import annotations

import argparse
import sys

from engineering_lib import (
    PHASES,
    UPSTREAM,
    active_artifact_path,
    artifact_missing_fields,
    engineering_dir,
    is_phase_skipped,
    load_active_artifact,
    load_lifecycle,
    log_transition,
    project_root_arg,
    required_fields,
    require_engineering,
    save_lifecycle,
    truncate_display,
)

EXECUTOR_BRIEFS = {
    "discovery": (
        "You are the discovery executor. Interview the user to fill each\n"
        "missing field. Edit the artifact JSON directly. Do not invent\n"
        "users or success_metrics — the user must provide them."
    ),
    "design": (
        "You are the design executor. Read the upstream requirements, then\n"
        "author design-spec.json with fields: implements_requirements (ids),\n"
        "flows (user journeys with steps), components (UI inventory).\n"
        "Reference a design-tokens file if the project has one."
    ),
    "architecture": (
        "You are the architecture executor. Produce stack.json (tech\n"
        "choices + system boundaries) and one ADR file per non-obvious\n"
        "decision in architecture/adrs/ADR-NNN.json. Each ADR: context,\n"
        "decision, consequences."
    ),
    "implementation": (
        "You are the implementation executor. Delegate to the `harness`\n"
        "skill with --project-root pointing at .engineering/implementation/.\n"
        "Derive the harness goal from design+architecture artifacts.\n"
        "Do NOT implement features directly — harness owns that."
    ),
    "test": (
        "You are the test executor. Write test-report.json with a plan\n"
        "(unit/integration/e2e/manual items), execute each, record\n"
        "pass/fail + evidence. campaign_ref must match the implementation\n"
        "campaign id."
    ),
    "release": (
        "You are the release executor. Fill release-checklist.json: items,\n"
        "rollback_plan, tagged_commit. Do not mark shipped without user\n"
        "confirmation (risk-gated)."
    ),
    "ops": (
        "You are the ops executor. Record incidents, postmortems, and\n"
        "metrics. Link each back to requirements/releases by id."
    ),
}


def upstream_summary_line(project_root, up_phase):
    art = load_active_artifact(project_root, up_phase)
    if art is None:
        return f"  [{up_phase}] (no artifact)"
    title = truncate_display(art.get("title") or art.get("id", ""), 50)
    return f"  [{up_phase}] {art.get('id')} · {art.get('status')} · {title}"


def implementation_hint(project_root):
    harness_dir = engineering_dir(project_root) / "implementation" / ".harness"
    impl_root = engineering_dir(project_root) / "implementation"
    if harness_dir.is_dir():
        return (
            f"Harness is initialized at {harness_dir}\n"
            f"To resume: invoke harness scripts with --project-root {impl_root}\n"
            f"  python3 ~/.claude/skills/harness/scripts/harness_summary.py --project-root {impl_root}"
        )
    return (
        f"Harness not yet initialized.\n"
        f"Next: invoke harness INIT with --project-root {impl_root}\n"
        f"  (harness will create {harness_dir})\n"
        f"Derive the campaign goal from the design + architecture artifacts above."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--phase", required=True, choices=PHASES)
    parser.add_argument("--force-stale", action="store_true")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)
    lc = load_lifecycle(root)
    phase = args.phase

    # Upstream readiness check (skipped phases count as satisfied)
    mode = lc.get("mode", "standard")
    blockers = []
    for up in UPSTREAM[phase]:
        if is_phase_skipped(up, mode):
            continue
        art = load_active_artifact(root, up)
        if art is None:
            blockers.append(f"{up}: no artifact")
        elif art.get("status") == "stale":
            blockers.append(f"{up}: STALE")
        elif art.get("status") != "approved":
            blockers.append(f"{up}: status={art.get('status')}")

    if blockers and not args.force_stale:
        print("Cannot enter phase — upstream not ready:", file=sys.stderr)
        for b in blockers:
            print(f"  - {b}", file=sys.stderr)
        print("Pass --force-stale to override.", file=sys.stderr)
        return 1

    print(f"═══ ENTERING PHASE: {phase} ═══\n")

    if UPSTREAM[phase]:
        active_upstream = [up for up in UPSTREAM[phase] if not is_phase_skipped(up, mode)]
        if active_upstream:
            print("Upstream artifacts:")
            for up in active_upstream:
                print(upstream_summary_line(root, up))
            skipped_up = [up for up in UPSTREAM[phase] if is_phase_skipped(up, mode)]
            if skipped_up:
                print(f"  (skipped in {mode} mode: {', '.join(skipped_up)})")
            print()

    # Active artifact state
    art = load_active_artifact(root, phase)
    art_path = active_artifact_path(root, phase)
    print(f"Active artifact: {art_path}")
    if art:
        print(f"  id={art.get('id')}  status={art.get('status')}")
    else:
        print("  (none yet — executor will create it)")
    missing = artifact_missing_fields(art, phase, mode) if art else required_fields(phase, mode)

    total = len(required_fields(phase, mode))
    print(f"\nSchema: {total - len(missing)}/{total} required fields present")
    if missing:
        print("  Missing: " + ", ".join(missing))
    print()

    # Executor brief
    print("─── EXECUTOR BRIEF ───")
    print(EXECUTOR_BRIEFS[phase])
    print()

    # Phase-specific next-step hint
    if phase == "implementation":
        print("─── HARNESS DELEGATION ───")
        print(implementation_hint(root))
        print()

    # Exit step hint
    print("─── EXIT ───")
    print(f"When all {total} required fields are present and verified:")
    print(f"  python3 <skill>/scripts/engineering_advance.py --project-root {root}")

    # Update lifecycle
    lc["current_phase"] = phase
    log_transition(lc, "enter_phase", {
        "phase": phase,
        "forced_stale": args.force_stale,
        "blockers": blockers if args.force_stale else [],
    })
    save_lifecycle(root, lc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
