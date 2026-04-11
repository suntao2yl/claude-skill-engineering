#!/usr/bin/env python3
"""Extract and display learnings across current and archived lifecycles.

Usage:
  python3 engineering_learn.py --project-root <path>
  python3 engineering_learn.py --project-root <path> --category technical
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engineering_lib import load_json, project_root_arg


def _collect_learnings(root: Path) -> list[dict]:
    """Collect learnings from current and archived .engineering/ directories."""
    learnings = []

    # Current lifecycle
    ops_path = root / ".engineering" / "ops" / "metrics.json"
    if ops_path.exists():
        data = load_json(ops_path, required=False)
        if data and isinstance(data.get("learnings"), list):
            for l in data["learnings"]:
                learnings.append({**l, "_source": "current", "_project": data.get("id", "?")})

    # Archived lifecycles
    archive_root = root / ".engineering-archive"
    if archive_root.is_dir():
        for archive_dir in sorted(archive_root.iterdir()):
            ops_path = archive_dir / "ops" / "metrics.json"
            if ops_path.exists():
                data = load_json(ops_path, required=False)
                if data and isinstance(data.get("learnings"), list):
                    for l in data["learnings"]:
                        learnings.append({**l, "_source": f"archive/{archive_dir.name}", "_project": data.get("id", "?")})

    return learnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract learnings across lifecycles")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--category", default=None,
                        help="Filter by category (process|technical|tooling|communication)")
    parser.add_argument("--json", action="store_true", help="Output as JSON array")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    learnings = _collect_learnings(root)

    if args.category:
        learnings = [l for l in learnings if l.get("category") == args.category]

    if args.json:
        print(json.dumps(learnings, indent=2, ensure_ascii=False))
    else:
        if not learnings:
            print("No learnings found.")
            return 0
        print(f"Found {len(learnings)} learning(s):\n")
        for i, l in enumerate(learnings, 1):
            cat = l.get("category", "?")
            insight = l.get("insight", "?")
            evidence = l.get("evidence", "")[:80]
            source = l.get("_source", "?")
            print(f"  {i}. [{cat}] {insight}")
            if evidence:
                print(f"     Evidence: {evidence}")
            print(f"     Source: {source}")
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
