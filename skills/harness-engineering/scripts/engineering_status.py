#!/usr/bin/env python3
"""One-screen status view of the engineering lifecycle."""
from __future__ import annotations

import argparse
import json
import sys

from engineering_lib import (
    PHASES,
    artifact_missing_fields,
    display_width,
    engineering_dir,
    is_phase_skipped,
    load_active_artifact,
    load_json,
    load_lifecycle,
    pad_display,
    phase_status,
    project_root_arg,
    required_fields,
    require_engineering,
    truncate_display,
)

STATUS_GLYPH = {
    "approved": "✓",
    "in_progress": "⋯",
    "draft": "◐",
    "ready": "○",
    "revising": "✎",
    "stale": "⚠",
    "archived": "▪",
    "pending": "·",
    "skipped": "—",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)
    lc = load_lifecycle(root)

    bar = "─" * 78
    project = lc.get("project", "?")
    mode = lc.get("mode", "?")
    current = lc.get("current_phase", "?")

    header = f"PROJECT: {project}    MODE: {mode}    CURRENT: {current}"
    print(header)
    print(bar)

    # Column widths (in display cells)
    W_PHASE = 14
    W_STATUS = 12
    W_ID = 10
    W_TITLE = 30
    W_PROG = 6

    for p in PHASES:
        if is_phase_skipped(p, mode):
            status = "skipped"
            artifact = None
        else:
            artifact = load_active_artifact(root, p)
            if artifact is not None:
                status = artifact.get("status") or "draft"
            else:
                status = phase_status(root, p, mode)

        glyph = STATUS_GLYPH.get(status, "?")
        aid = lc["active_units"].get(p) or (artifact.get("id") if artifact else "—")
        title = (artifact.get("title") or "") if artifact else ""
        title = truncate_display(title, W_TITLE)

        if artifact and status != "approved":
            fields = required_fields(p, mode)
            missing = artifact_missing_fields(artifact, p, mode)
            progress = f"{len(fields) - len(missing)}/{len(fields)}"
        else:
            progress = ""

        marker = "▶" if p == current else " "
        line = (
            f"{marker} "
            f"{pad_display(p, W_PHASE)} "
            f"{glyph} "
            f"{pad_display(status, W_STATUS)} "
            f"{pad_display(str(aid), W_ID)} "
            f"{pad_display(title, W_TITLE)} "
            f"{pad_display(progress, W_PROG)}"
        )
        print(line)

    print(bar)
    hist = lc.get("phase_history", [])
    if hist:
        last = hist[-1]
        print(f"Last transition: {last.get('at')} · {last.get('kind')}")

    # Show parallel-ready phases
    ready = [p for p in PHASES
             if not is_phase_skipped(p, mode) and phase_status(root, p, mode) == "ready"]
    if ready:
        print(f"Ready to work on: {', '.join(ready)}")

    # Unified harness progress if implementation has an active harness campaign
    harness_summary_path = (
        engineering_dir(root) / "implementation" / ".harness" / "session-summary.json"
    )
    if harness_summary_path.exists():
        summary = load_json(harness_summary_path, required=False)
        if summary:
            counts = summary.get("progress_counts", {})
            total = counts.get("total", 0)
            done = counts.get("done", 0)
            in_prog = counts.get("in_progress", 0)
            blocked = counts.get("blocked", 0)
            current_f = summary.get("current_feature") or "none"
            print(
                f"Harness: {done}/{total} done · {in_prog} in_progress · "
                f"{blocked} blocked · current: {current_f}"
            )

    # Show basic metrics if available
    metrics_path = engineering_dir(root) / "metrics" / "phase_runs.jsonl"
    if metrics_path.exists():
        try:
            lines = metrics_path.read_text(encoding="utf-8").strip().splitlines()
            if lines:
                records = [json.loads(l) for l in lines[-20:]]  # last 20
                last = records[-1]
                total_runs = len(records)
                avg_ms = sum(r.get("execution_time_ms", 0) for r in records) // max(total_runs, 1)
                print(f"Metrics: {total_runs} runs · avg {avg_ms}ms · last: {last.get('phase', '?')} exit {last.get('exit_code', '?')}")
        except Exception:
            pass  # metrics are best-effort

    return 0


if __name__ == "__main__":
    sys.exit(main())
