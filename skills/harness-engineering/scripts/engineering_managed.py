#!/usr/bin/env python3
"""Managed Agents session management for the implementation phase.

This is a thin state-tracking wrapper. Actual Managed Agents API calls
happen through the Claude API skill or direct HTTP — this script only
manages the local session state file.

Usage:
  python3 engineering_managed.py --create --project-root <path> --goal "..."
  python3 engineering_managed.py --status --project-root <path>
  python3 engineering_managed.py --checkpoint --project-root <path>
  python3 engineering_managed.py --resume --project-root <path>

Exit codes: 0=success, 1=error, 2=session still running
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from engineering_lib import (
    ManagedAgentSession,
    load_managed_session,
    project_root_arg,
    require_engineering,
    save_managed_session,
    utc_now,
)


def _create(root: Path, goal: str, features_total: int) -> int:
    existing = load_managed_session(root)
    if existing and existing.get("status") in ("running", "pending"):
        print(f"Session already exists: {existing.get('session_id')}", file=sys.stderr)
        return 1

    session = ManagedAgentSession(
        session_id=str(uuid.uuid4())[:8],
        status="pending",
        started_at=utc_now(),
        features_total=features_total,
    )
    save_managed_session(root, session)
    print(f"Created managed session: {session.session_id}")
    print(f"  features_total: {features_total}")
    print(f"  status: pending")
    print(f"  Next: start the session via Claude API / Managed Agents API")
    return 0


def _status(root: Path) -> int:
    session = load_managed_session(root)
    if session is None:
        print("No managed session found.", file=sys.stderr)
        return 1
    print(f"Session: {session.get('session_id', '?')}")
    print(f"  status: {session.get('status', '?')}")
    print(f"  features: {session.get('features_completed', 0)}/{session.get('features_total', 0)}")
    print(f"  started: {session.get('started_at', '?')}")
    print(f"  last checkpoint: {session.get('last_checkpoint', 'none')}")
    if session.get("status") == "running":
        return 2
    return 0


def _checkpoint(root: Path, features_completed: int) -> int:
    session = load_managed_session(root)
    if session is None:
        print("No managed session found.", file=sys.stderr)
        return 1
    session["status"] = "checkpointed"
    session["last_checkpoint"] = utc_now()
    session["features_completed"] = features_completed
    save_managed_session(root, session)
    print(f"Checkpointed: {features_completed}/{session.get('features_total', '?')} features")
    return 0


def _resume(root: Path) -> int:
    session = load_managed_session(root)
    if session is None:
        print("No managed session found.", file=sys.stderr)
        return 1
    if session.get("status") == "completed":
        print("Session already completed.", file=sys.stderr)
        return 0
    session["status"] = "running"
    save_managed_session(root, session)
    print(f"Resumed session: {session.get('session_id', '?')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Managed Agents session management")
    parser.add_argument("--project-root", default=".")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true")
    group.add_argument("--status", action="store_true")
    group.add_argument("--checkpoint", action="store_true")
    group.add_argument("--resume", action="store_true")
    parser.add_argument("--goal", default="")
    parser.add_argument("--features-total", type=int, default=0)
    parser.add_argument("--features-completed", type=int, default=0)
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    if args.create:
        return _create(root, args.goal, args.features_total)
    elif args.status:
        return _status(root)
    elif args.checkpoint:
        return _checkpoint(root, args.features_completed)
    elif args.resume:
        return _resume(root)
    return 1


if __name__ == "__main__":
    sys.exit(main())
