#!/usr/bin/env python3
"""Mark a phase's artifact as revising; propagate stale status downstream."""
from __future__ import annotations

import argparse
import sys

from engineering_lib import (
    PHASES,
    UPSTREAM,
    active_artifact_path,
    load_active_artifact,
    load_lifecycle,
    log_transition,
    project_root_arg,
    require_engineering,
    save_json,
    save_lifecycle,
    utc_now,
)


def downstream_of(phase: str) -> list[str]:
    """Return phases that (transitively) depend on this phase."""
    result = []
    frontier = [phase]
    visited = {phase}
    while frontier:
        nxt = []
        for p in PHASES:
            if p in visited:
                continue
            for up in UPSTREAM[p]:
                if up in frontier:
                    nxt.append(p)
                    visited.add(p)
                    break
        result.extend(nxt)
        frontier = nxt
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--phase", required=True, choices=PHASES)
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)
    lc = load_lifecycle(root)

    phase = args.phase
    art = load_active_artifact(root, phase)
    if art is None:
        print(f"No active artifact for {phase}", file=sys.stderr)
        return 1

    art["status"] = "revising"
    art["last_updated"] = utc_now()
    save_json(active_artifact_path(root, phase), art)
    print(f"Marked {phase} · {art.get('id')} as revising")

    affected = []
    for d in downstream_of(phase):
        d_art = load_active_artifact(root, d)
        if d_art and d_art.get("status") not in ("stale", "archived"):
            d_art["status"] = "stale"
            d_art["last_updated"] = utc_now()
            save_json(active_artifact_path(root, d), d_art)
            affected.append(f"{d}:{d_art.get('id')}")

    if affected:
        print("Marked downstream stale: " + ", ".join(affected))
    else:
        print("No downstream artifacts affected.")

    lc["current_phase"] = phase
    log_transition(lc, "revise", {"phase": phase, "affected": affected})
    save_lifecycle(root, lc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
