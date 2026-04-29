#!/usr/bin/env python3
"""Evaluation harness for completed engineering lifecycles.

Distills the test phase's passing tests into reusable EVAL-NNN cases that
can be re-run later to detect regressions when code, models, or harness
configuration change. The baseline run is recorded in lifecycle.json so
subsequent runs can compare against it.

Subcommands:
  --create        Distill test-report.json -> .engineering/eval/cases/
  --run           Execute every case; write runs/run-<ts>/result.json
  --baseline      Mark the latest run as baseline
  --compare REF   Compare current run with REF (run id, or 'baseline')
  --list-runs     List all runs
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from engineering_lib import (  # noqa: E402
    engineering_dir,
    load_json,
    load_lifecycle,
    project_root_arg,
    require_engineering,
    save_json,
    save_lifecycle,
    utc_now,
)


def utc_now_compact() -> str:
    # Filesystem-safe variant of utc_now (no dashes/colons).
    return utc_now().translate({ord("-"): None, ord(":"): None})


def eval_dir(root: Path) -> Path:
    return engineering_dir(root) / "eval"


def cases_dir(root: Path) -> Path:
    return eval_dir(root) / "cases"


def runs_dir(root: Path) -> Path:
    return eval_dir(root) / "runs"


def test_report_path(root: Path) -> Path:
    return engineering_dir(root) / "test" / "test-report.json"


def next_eval_id(root: Path) -> str:
    cd = cases_dir(root)
    if not cd.exists():
        return "EVAL-001"
    nums = []
    for p in cd.glob("EVAL-*.json"):
        m = re.match(r"^EVAL-(\d+)\.json$", p.name)
        if m:
            nums.append(int(m.group(1)))
    n = (max(nums) + 1) if nums else 1
    return f"EVAL-{n:03d}"


def load_test_report(root: Path) -> dict[str, Any]:
    report = load_json(test_report_path(root), required=False)
    if report is None:
        print(json.dumps({"error": f"test-report.json not found at {test_report_path(root)}"}))
        sys.exit(2)
    return report


def cmd_create(args, root: Path) -> int:
    """Distill passing test cases from test-report.json into EVAL cases."""
    report = load_test_report(root)
    results = report.get("results") or []
    plan = report.get("plan") or []

    # Index plan entries by name to recover the command for each result
    plan_by_name = {p.get("name"): p for p in plan if isinstance(p, dict)}

    cases_dir(root).mkdir(parents=True, exist_ok=True)
    created = []
    skipped = []
    for r in results:
        if r.get("status") != "pass":
            skipped.append(r.get("name"))
            continue
        name = r.get("name")
        plan_entry = plan_by_name.get(name) or {}
        cmd = plan_entry.get("command") or ""
        if not cmd:
            skipped.append(name)
            continue
        eid = next_eval_id(root)
        evidence = r.get("evidence") or ""
        case = {
            "id": eid,
            "source_test_id": report.get("id"),
            "source_test_name": name,
            "case_type": plan_entry.get("type") or "unit",
            "command": cmd,
            "expected": {
                "exit_code": 0,
                "stdout_contains": _extract_passing_marker(evidence),
            },
            "tolerance": {"runtime_ms": 60000},
            "created_at": utc_now(),
        }
        path = cases_dir(root) / f"{eid}.json"
        save_json(path, case)
        created.append(eid)

    print(json.dumps({
        "created": created,
        "skipped": skipped,
        "cases_dir": str(cases_dir(root).relative_to(root)),
    }, indent=2))
    return 0


def _extract_passing_marker(evidence: str) -> list[str]:
    """Heuristic: pull a small substring that demonstrated the test passed.

    For pytest: 'X passed'. For jest: 'Tests:        X passed'. For tap:
    'ok N'. Returns [] when no recognizable marker is present — in that
    case the case relies on exit_code alone, which is the safer default
    than requiring a needle that may not be in stdout.
    """
    if not evidence:
        return []
    for pattern in (r"\d+\s+passed", r"PASS", r"ok\s+\d+"):
        m = re.search(pattern, evidence)
        if m:
            return [m.group(0)]
    return []


def cmd_run(args, root: Path) -> int:
    """Execute every case file. Write results to runs/run-<timestamp>/result.json."""
    cd = cases_dir(root)
    if not cd.exists() or not list(cd.glob("EVAL-*.json")):
        print(json.dumps({"error": "no eval cases. Run --create first."}))
        return 2

    run_id = f"run-{utc_now_compact()}"
    run_path = runs_dir(root) / run_id
    run_path.mkdir(parents=True, exist_ok=True)

    case_files = sorted(cd.glob("EVAL-*.json"))
    results: list[dict[str, Any]] = []
    for cf in case_files:
        case = load_json(cf)
        results.append(_execute_case(case, root))

    summary = {
        "run_id": run_id,
        "executed_at": utc_now(),
        "total": len(results),
        "passed": sum(1 for r in results if r["status"] == "pass"),
        "failed": sum(1 for r in results if r["status"] == "fail"),
        "results": results,
    }
    save_json(run_path / "result.json", summary)

    if args.mark_baseline:
        lc = load_lifecycle(root)
        lc["eval_baseline"] = run_id
        save_lifecycle(root, lc)
        summary["marked_baseline"] = True

    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    return 0 if summary["failed"] == 0 else 1


def _execute_case(case: dict, root: Path) -> dict:
    cmd = case.get("command", "")
    expected = (case.get("expected") or {})
    timeout_ms = (case.get("tolerance") or {}).get("runtime_ms", 60000)
    started = time.monotonic()
    timed_out = False
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(root), capture_output=True, text=True,
            timeout=max(1, timeout_ms / 1000),
        )
        exit_code = proc.returncode
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    except subprocess.TimeoutExpired:
        timed_out = True
    duration_ms = int((time.monotonic() - started) * 1000)

    expected_exit = expected.get("exit_code", 0)
    needles = expected.get("stdout_contains") or []
    matched = (
        not timed_out
        and exit_code == expected_exit
        and all(n in stdout for n in needles)
    )
    return {
        "id": case.get("id"),
        "command": cmd,
        "status": "pass" if matched else "fail",
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
        "missing_needles": [n for n in needles if n not in stdout],
        "stdout_tail": stdout[-300:] if len(stdout) > 300 else stdout,
        "stderr_tail": stderr[-300:] if len(stderr) > 300 else stderr,
    }


def cmd_baseline(args, root: Path) -> int:
    """Mark the most recent run as baseline."""
    runs = sorted(runs_dir(root).glob("run-*")) if runs_dir(root).exists() else []
    if not runs:
        print(json.dumps({"error": "no runs found. --run first."}))
        return 2
    latest = runs[-1].name
    lc = load_lifecycle(root)
    lc["eval_baseline"] = latest
    save_lifecycle(root, lc)
    print(json.dumps({"baseline": latest}, indent=2))
    return 0


def cmd_compare(args, root: Path) -> int:
    """Diff a run against another (or 'baseline')."""
    target = args.compare
    rd = runs_dir(root)
    if target == "baseline":
        lc = load_lifecycle(root)
        target = lc.get("eval_baseline")
        if not target:
            print(json.dumps({"error": "no baseline marked. --baseline first."}))
            return 2

    target_path = rd / target / "result.json"
    if not target_path.exists():
        print(json.dumps({"error": f"run not found: {target}"}))
        return 2

    runs = sorted(rd.glob("run-*"))
    if not runs:
        print(json.dumps({"error": "no runs"}))
        return 2
    latest_path = runs[-1] / "result.json"
    if latest_path.parent.name == target:
        print(json.dumps({"error": "latest run IS the target — nothing to compare"}))
        return 2

    base = load_json(target_path)
    cur = load_json(latest_path)

    base_status = {r["id"]: r["status"] for r in base.get("results") or []}
    cur_status = {r["id"]: r["status"] for r in cur.get("results") or []}

    regressions = sorted(eid for eid, s in cur_status.items()
                         if s == "fail" and base_status.get(eid) == "pass")
    fixes = sorted(eid for eid, s in cur_status.items()
                   if s == "pass" and base_status.get(eid) == "fail")
    new_cases = sorted(set(cur_status) - set(base_status))
    removed_cases = sorted(set(base_status) - set(cur_status))

    out = {
        "baseline_run": target,
        "current_run": latest_path.parent.name,
        "regressions": regressions,
        "fixes": fixes,
        "new_cases": new_cases,
        "removed_cases": removed_cases,
        "summary": {
            "baseline": {"passed": base.get("passed"), "failed": base.get("failed")},
            "current":  {"passed": cur.get("passed"),  "failed": cur.get("failed")},
        },
    }
    print(json.dumps(out, indent=2))
    return 1 if regressions else 0


def cmd_list_runs(args, root: Path) -> int:
    rd = runs_dir(root)
    if not rd.exists():
        print(json.dumps({"runs": []}))
        return 0
    runs = []
    lc = load_lifecycle(root)
    baseline = lc.get("eval_baseline")
    for d in sorted(rd.glob("run-*")):
        result_path = d / "result.json"
        if not result_path.exists():
            continue
        result = load_json(result_path)
        runs.append({
            "run_id": d.name,
            "passed": result.get("passed"),
            "failed": result.get("failed"),
            "is_baseline": d.name == baseline,
        })
    print(json.dumps({"runs": runs, "baseline": baseline}, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--project-root", default=".")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--create", action="store_true")
    g.add_argument("--run", action="store_true")
    g.add_argument("--baseline", action="store_true",
                   help="Standalone: mark latest run as baseline")
    g.add_argument("--compare",
                   help="Compare latest run with REF (run id or 'baseline')")
    g.add_argument("--list-runs", action="store_true")
    p.add_argument("--mark-baseline", dest="mark_baseline", action="store_true",
                   help="When used with --run, mark this run as baseline.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root_arg(args.project_root)
    require_engineering(root)
    if args.create:
        return cmd_create(args, root)
    if args.run:
        return cmd_run(args, root)
    if args.baseline:
        return cmd_baseline(args, root)
    if args.compare:
        return cmd_compare(args, root)
    if args.list_runs:
        return cmd_list_runs(args, root)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
