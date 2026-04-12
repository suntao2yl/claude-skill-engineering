#!/usr/bin/env python3
"""Capture and manage cross-phase insights without triggering stale propagation.

Insights are lightweight feedback from downstream phases to upstream phases.
Unlike revise (which marks artifacts stale), insights are additive observations
that inform future work without disrupting the current lifecycle.

Usage:
  python3 engineering_insight.py --project-root <path> --add --source test --target discovery --kind gap --insight "..." --evidence "..."
  python3 engineering_insight.py --project-root <path> --list [--target discovery] [--unaddressed]
  python3 engineering_insight.py --project-root <path> --address <index>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engineering_lib import (
    INSIGHT_KINDS,
    PHASES,
    _append_jsonl,
    _load_jsonl,
    engineering_dir,
    project_root_arg,
    require_engineering,
    utc_now,
)


def _insights_path(root: Path) -> Path:
    return engineering_dir(root) / "insights.jsonl"


def _load_all(root: Path) -> list[dict]:
    return _load_jsonl(_insights_path(root))


def _add(root: Path, source: str, target: str, kind: str,
         insight: str, evidence: str) -> int:
    if source not in PHASES:
        print(f"Invalid source phase: {source}", file=sys.stderr)
        return 1
    if target not in PHASES:
        print(f"Invalid target phase: {target}", file=sys.stderr)
        return 1
    if kind not in INSIGHT_KINDS:
        print(f"Invalid kind: {kind}. Must be one of: {', '.join(INSIGHT_KINDS)}", file=sys.stderr)
        return 1
    if len(insight.strip()) < 5:
        print("Insight text too short (need >=5 chars)", file=sys.stderr)
        return 1

    record = {
        "source_phase": source,
        "target_phase": target,
        "kind": kind,
        "insight": insight.strip(),
        "evidence": evidence.strip(),
        "addressed": False,
        "timestamp": utc_now(),
    }
    _append_jsonl(_insights_path(root), record)
    print(f"Recorded {kind} insight: {source} -> {target}")
    return 0


def _list(root: Path, target: str | None, unaddressed_only: bool) -> int:
    records = _load_all(root)
    if target:
        records = [r for r in records if r.get("target_phase") == target]
    if unaddressed_only:
        records = [r for r in records if not r.get("addressed", False)]

    if not records:
        print("No insights found.")
        return 0

    print(f"Found {len(records)} insight(s):\n")
    for i, r in enumerate(records, 1):
        kind = r.get("kind", "?")
        src = r.get("source_phase", "?")
        tgt = r.get("target_phase", "?")
        text = r.get("insight", "?")
        addr = "addressed" if r.get("addressed") else "open"
        glyph = {"observation": ".", "contradiction": "!", "gap": "?", "suggestion": "+"}.get(kind, " ")
        print(f"  {i}. [{glyph}{kind}] {src} -> {tgt}  ({addr})")
        print(f"     {text}")
        ev = r.get("evidence", "")
        if ev:
            print(f"     Evidence: {ev[:80]}")
        print()
    return 0



def _address(root: Path, index: int) -> int:
    records = _load_all(root)
    if index < 1 or index > len(records):
        print(f"Index {index} out of range (1-{len(records)})", file=sys.stderr)
        return 1

    records[index - 1]["addressed"] = True
    records[index - 1]["addressed_at"] = utc_now()

    path = _insights_path(root)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    text = records[index - 1].get("insight", "")[:60]
    print(f"Marked insight #{index} as addressed: {text}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-phase insight capture")
    parser.add_argument("--project-root", default=".")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--add", action="store_true", help="Record a new insight")
    group.add_argument("--list", action="store_true", help="List insights")
    group.add_argument("--address", type=int, metavar="INDEX",
                       help="Mark insight as addressed (1-based index)")

    parser.add_argument("--source", help="Source phase (for --add)")
    parser.add_argument("--target", help="Target phase (for --add and --list)")
    parser.add_argument("--kind", choices=INSIGHT_KINDS, help="Insight kind (for --add)")
    parser.add_argument("--insight", help="Insight text (for --add)")
    parser.add_argument("--evidence", default="", help="Evidence (for --add)")
    parser.add_argument("--unaddressed", action="store_true",
                        help="Show only unaddressed insights (for --list)")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    if args.add:
        if not all([args.source, args.target, args.kind, args.insight]):
            print("--add requires --source, --target, --kind, --insight", file=sys.stderr)
            return 1
        return _add(root, args.source, args.target, args.kind,
                     args.insight, args.evidence)
    elif args.list:
        return _list(root, args.target, args.unaddressed)
    elif args.address is not None:
        return _address(root, args.address)
    return 0


if __name__ == "__main__":
    sys.exit(main())
