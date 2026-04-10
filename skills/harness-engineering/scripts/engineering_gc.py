#!/usr/bin/env python3
"""Entropy governance: scan .engineering/ for stale drafts, old archives, temp files.

Default dry-run outputs a JSON report. --apply moves files to .trash/.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from engineering_lib import (
    PHASES,
    engineering_dir,
    load_json,
    phase_dir,
    project_root_arg,
    require_engineering,
    utc_now,
)

DEFAULT_STALE_DAYS = 7
DEFAULT_ARCHIVE_DAYS = 30
TEMP_PATTERNS = {"*.tmp", "*.bak", ".loop_state.json"}


def _age_days(path: Path) -> float:
    mtime = path.stat().st_mtime
    return (time.time() - mtime) / 86400


def _scan_stale_artifacts(root: Path, max_age: int) -> list[dict]:
    findings = []
    eng = engineering_dir(root)
    for p in PHASES:
        pd = phase_dir(root, p)
        for f in pd.glob("*.json"):
            if f.name == ".DS_Store":
                continue
            try:
                data = load_json(f, required=False)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            if data.get("status") == "draft":
                age = _age_days(f)
                if age > max_age:
                    findings.append({
                        "type": "stale_artifact",
                        "path": str(f),
                        "age_days": round(age, 1),
                        "recommended_action": "archive or delete",
                    })
    return findings


def _scan_old_archives(root: Path, max_age: int) -> list[dict]:
    findings = []
    eng = engineering_dir(root)
    for archive_dir in eng.rglob("archive"):
        if not archive_dir.is_dir():
            continue
        for f in archive_dir.iterdir():
            if f.is_file():
                age = _age_days(f)
                if age > max_age:
                    findings.append({
                        "type": "old_archive",
                        "path": str(f),
                        "age_days": round(age, 1),
                        "recommended_action": "delete",
                    })
    return findings


def _scan_temp_files(root: Path) -> list[dict]:
    findings = []
    eng = engineering_dir(root)
    for pattern in TEMP_PATTERNS:
        for f in eng.rglob(pattern):
            if f.is_file():
                findings.append({
                    "type": "temp_file",
                    "path": str(f),
                    "age_days": round(_age_days(f), 1),
                    "recommended_action": "delete",
                })
    return findings


def _apply_cleanup(root: Path, findings: list[dict]) -> int:
    eng = engineering_dir(root)
    trash_dir = eng / ".trash" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trash_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for item in findings:
        src = Path(item["path"])
        if src.exists():
            dest = trash_dir / src.name
            shutil.move(str(src), str(dest))
            moved += 1
    return moved


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan .engineering/ for entropy")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--apply", action="store_true", help="Move stale files to .trash/")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_STALE_DAYS)
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    findings = []
    findings.extend(_scan_stale_artifacts(root, args.max_age_days))
    findings.extend(_scan_old_archives(root, DEFAULT_ARCHIVE_DAYS))
    findings.extend(_scan_temp_files(root))

    total_bytes = 0
    for item in findings:
        p = Path(item["path"])
        if p.exists():
            total_bytes += p.stat().st_size

    report = {
        "scan_time": utc_now(),
        "project_root": str(root),
        "findings": findings,
        "summary": {
            "total_findings": len(findings),
            "estimated_reclaim_bytes": total_bytes,
        },
    }

    if args.apply and findings:
        moved = _apply_cleanup(root, findings)
        report["applied"] = True
        report["moved_count"] = moved

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
