#!/usr/bin/env python3
"""Archive the entire .engineering/ lifecycle and optionally remove it."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone

from engineering_lib import (
    engineering_dir,
    load_lifecycle,
    project_root_arg,
    require_engineering,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--keep", action="store_true",
                        help="Archive but don't delete current .engineering/")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    lc = load_lifecycle(root)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Archive lives OUTSIDE .engineering/ so reset doesn't wipe it
    archive_parent = root / ".engineering-archive"
    archive_parent.mkdir(exist_ok=True)
    archive_path = archive_parent / f"{lc.get('project', 'unknown')}-{ts}"

    eng = engineering_dir(root)
    shutil.copytree(eng, archive_path)
    print(f"Archived .engineering/ → {archive_path}")

    if not args.keep:
        shutil.rmtree(eng)
        print(f"Removed .engineering/ — run engineering_init.py to start fresh.")
    else:
        print(f"Kept .engineering/ in place (--keep).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
