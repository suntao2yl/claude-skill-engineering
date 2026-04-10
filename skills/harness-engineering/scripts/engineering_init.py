#!/usr/bin/env python3
"""Initialize a .engineering/ lifecycle in the target project."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engineering_lib import (
    MINIMAL_SKIP,
    PHASES,
    active_artifact_path,
    engineering_dir,
    log_transition,
    phase_dir,
    project_root_arg,
    save_json,
    save_lifecycle,
    utc_now,
)


def _check_harness_dependency() -> None:
    """Warn (don't block) if the harness-plan skill isn't installed.
    engineering's implementation phase delegates to it."""
    home = Path.home()
    candidates = [
        home / ".claude" / "skills" / "harness-plan" / "SKILL.md",
    ]
    # also scan installed plugins for any harness-plan skill
    plugins_root = home / ".claude" / "plugins"
    if plugins_root.exists():
        candidates.extend(plugins_root.glob("**/harness-plan/skills/harness-plan/SKILL.md"))
    if not any(c.exists() for c in candidates):
        print(
            "⚠  harness-plan skill not found at ~/.claude/skills/harness-plan/.\n"
            "   engineering's implementation phase needs it. You can still\n"
            "   run discovery/design/architecture/test/release/ops without it,\n"
            "   but implementation will fail. Install with:\n"
            "     ./install.sh --with-harness-plan /path/to/harness-plan-skill",
            file=sys.stderr,
        )


def _default_risk_gates(mode: str) -> list:
    """Default risk gates: where auto-drive must pause for human confirmation.
    Rationale: these are the points where downstream commits to direction."""
    if mode == "minimal":
        return ["release.approved"]  # only gate left in minimal mode
    return [
        "discovery.approved",    # downstream commits to requirements
        "architecture.approved", # downstream commits to stack
        "release.approved",      # release goes public
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .engineering/ lifecycle")
    parser.add_argument("--project-root", default=".", help="Project root path")
    parser.add_argument("--goal", required=True, help="One-sentence project goal")
    parser.add_argument("--mode", default="standard", choices=["standard", "minimal"])
    parser.add_argument("--project-name", default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing .engineering/")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    eng = engineering_dir(root)

    _check_harness_dependency()

    if eng.exists() and not args.force:
        print(f"Error: .engineering/ already exists at {eng}", file=sys.stderr)
        print("Use --force to overwrite or run /harness-engineering reset.", file=sys.stderr)
        return 1

    # Create directory structure
    root.mkdir(parents=True, exist_ok=True)
    eng.mkdir(exist_ok=True)
    for p in PHASES:
        phase_dir(root, p).mkdir(exist_ok=True)
        (phase_dir(root, p) / "archive").mkdir(exist_ok=True)
    # Architecture and ops have nested dirs
    (phase_dir(root, "architecture") / "adrs").mkdir(exist_ok=True)
    (phase_dir(root, "ops") / "incidents").mkdir(exist_ok=True)
    (phase_dir(root, "ops") / "postmortems").mkdir(exist_ok=True)
    # Metrics directory
    (eng / "metrics").mkdir(exist_ok=True)

    project_name = args.project_name or root.name
    goal = args.goal.strip()
    title = goal.split("。")[0].split(".")[0][:80]

    # active_units starts all null
    active_units = {p: None for p in PHASES}

    # Determine starting phase (first non-skipped)
    start_phase = next(p for p in PHASES if not (args.mode == "minimal" and p in MINIMAL_SKIP))

    # Only seed discovery if discovery is not skipped
    if "discovery" not in MINIMAL_SKIP or args.mode != "minimal":
        req = {
            "schema_version": 1,
            "id": "REQ-001",
            "title": title,
            "problem_statement": goal,
            "users": [],
            "success_metrics": [],
            "constraints": [],
            "out_of_scope": [],
            "status": "draft",
            "created_at": utc_now(),
            "last_updated": utc_now(),
        }
        save_json(active_artifact_path(root, "discovery"), req)
        active_units["discovery"] = "REQ-001"

    lifecycle = {
        "schema_version": 1,
        "project": project_name,
        "goal": goal,
        "mode": args.mode,
        "current_phase": start_phase,
        "active_units": active_units,
        "risk_gates": _default_risk_gates(args.mode),
        "phase_history": [],
        "created_at": utc_now(),
        "last_updated": utc_now(),
    }
    log_transition(lifecycle, "init", {"goal": goal, "mode": args.mode, "start_phase": start_phase})
    save_lifecycle(root, lifecycle)

    print(f"Initialized .engineering/ at {eng}")
    print(f"  project: {project_name}")
    print(f"  mode: {args.mode}")
    print(f"  current_phase: {start_phase}")
    if active_units.get("discovery"):
        print(f"  seeded REQ-001: {title}")
    else:
        print(f"  skipped phases: {sorted(MINIMAL_SKIP)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
