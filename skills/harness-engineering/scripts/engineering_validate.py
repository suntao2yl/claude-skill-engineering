#!/usr/bin/env python3
"""Validate integrity of .engineering/ state."""
from __future__ import annotations

import argparse
import sys

from engineering_lib import (
    ARTIFACT_STATUS,
    PHASES,
    active_artifact_path,
    engineering_dir,
    load_active_artifact,
    load_lifecycle,
    project_root_arg,
    require_engineering,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    errors = []
    warnings = []

    try:
        lc = load_lifecycle(root)
    except Exception as e:
        print(f"FATAL: cannot load lifecycle.json: {e}", file=sys.stderr)
        return 2

    # current_phase valid?
    if lc.get("current_phase") not in PHASES:
        errors.append(f"current_phase invalid: {lc.get('current_phase')}")

    # mode valid?
    if lc.get("mode") not in ("standard", "minimal"):
        errors.append(f"mode invalid: {lc.get('mode')}")

    # active_units keys = PHASES
    au = lc.get("active_units", {})
    for p in PHASES:
        if p not in au:
            errors.append(f"active_units missing phase: {p}")

    # each referenced active unit has an artifact on disk
    for p in PHASES:
        unit = au.get(p)
        if unit is None:
            continue
        art = load_active_artifact(root, p)
        if art is None:
            errors.append(f"active_unit {p}={unit} but no artifact on disk")
            continue
        if art.get("id") != unit:
            warnings.append(f"active_unit {p}={unit} but artifact.id={art.get('id')}")
        if art.get("status") not in ARTIFACT_STATUS:
            errors.append(f"{p}/{art.get('id')} has invalid status: {art.get('status')}")

    # Print results
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  ⚠ {w}")
    if not errors and not warnings:
        print("OK — lifecycle state valid.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
