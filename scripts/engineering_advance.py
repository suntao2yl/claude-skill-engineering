#!/usr/bin/env python3
"""Validate current phase exit criteria and advance to next available phase.

'Next available' means: first phase (canonical order) that is not yet approved
and whose upstream phases are all approved. This naturally handles parallel
phases (design + architecture both depend only on discovery).

Phase-specific hard validation prevents "fill-blank-JSON-and-pass" shortcuts:
- architecture: at least 1 ADR file must exist on disk
- implementation: harness session-summary must show done == total, no failures
- test: results must have >= 1 pass and zero fails
- release: tagged_commit must be a resolvable git ref
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from engineering_lib import (
    PHASES,
    active_artifact_path,
    artifact_missing_fields,
    engineering_dir,
    is_phase_skipped,
    load_active_artifact,
    load_json,
    load_lifecycle,
    log_transition,
    phase_status,
    pick_next_phase,
    project_root_arg,
    require_engineering,
    save_json,
    save_lifecycle,
    utc_now,
)


# ── Phase-specific hard validators ────────────────────────────
# Each returns a list of error strings; empty = pass.


def _validate_discovery(root: Path, art: dict) -> list[str]:
    """users and success_metrics must have real content (no empty strings,
    no single-char entries)."""
    errors = []
    users = art.get("users", [])
    metrics = art.get("success_metrics", [])
    problem = art.get("problem_statement", "").strip()

    trivial_users = [u for u in users if not isinstance(u, str) or len(u.strip()) < 3]
    if trivial_users:
        errors.append(f"users has {len(trivial_users)} trivial entry(s) (empty or <3 chars).")

    trivial_metrics = [m for m in metrics if not isinstance(m, str) or len(m.strip()) < 5]
    if trivial_metrics:
        errors.append(f"success_metrics has {len(trivial_metrics)} trivial entry(s) (empty or <5 chars).")

    if len(problem) < 20:
        errors.append(f"problem_statement too short ({len(problem)} chars). Need >=20.")

    return errors


def _validate_design(root: Path, art: dict) -> list[str]:
    """Each flow must have steps, each component must have a spec."""
    errors = []
    flows = art.get("flows", [])
    components = art.get("components", [])

    for i, flow in enumerate(flows):
        if not isinstance(flow, dict):
            errors.append(f"flows[{i}] is not an object.")
            continue
        name = flow.get("name", "")
        steps = flow.get("steps", [])
        if not name or not str(name).strip():
            errors.append(f"flows[{i}] has no name.")
        if not steps:
            errors.append(f"flow '{name or i}' has empty steps.")
        elif any(not str(s).strip() for s in steps):
            errors.append(f"flow '{name or i}' has empty step(s).")

    for i, comp in enumerate(components):
        if not isinstance(comp, dict):
            errors.append(f"components[{i}] is not an object.")
            continue
        cname = comp.get("name", "")
        spec = comp.get("spec", "")
        if not cname or not str(cname).strip():
            errors.append(f"components[{i}] has no name.")
        if not spec or len(str(spec).strip()) < 10:
            errors.append(f"component '{cname or i}' spec too short (<10 chars).")

    # Cross-check: implements_requirements should reference the active REQ
    reqs = art.get("implements_requirements", [])
    disc = load_active_artifact(root, "discovery")
    if disc and reqs and disc.get("id") not in reqs:
        errors.append(f"implements_requirements {reqs} does not include '{disc.get('id')}'.")

    return errors


def _validate_architecture(root: Path, art: dict) -> list[str]:
    """At least 1 ADR file must exist in architecture/adrs/."""
    errors = []
    adrs_dir = engineering_dir(root) / "architecture" / "adrs"
    adr_files = list(adrs_dir.glob("ADR-*.json")) if adrs_dir.is_dir() else []
    if not adr_files:
        errors.append("No ADR files in architecture/adrs/. At least 1 required.")
    # Cross-check: art.adrs should reference existing files
    declared = art.get("adrs", [])
    for adr_id in declared:
        matching = [f for f in adr_files if adr_id in f.stem]
        if not matching:
            errors.append(f"Declared ADR '{adr_id}' has no matching file in adrs/.")
    return errors


def _validate_implementation(root: Path, art: dict) -> list[str]:
    """Harness must report all features done, no failing baseline, and
    verification commands must actually pass when executed."""
    errors = []
    harness_root = art.get("harness_root", "")
    if not harness_root:
        errors.append("harness_root is empty.")
        return errors

    # Resolve relative to project root (Path division honors absolute RHS)
    harness_path = root / harness_root
    summary_path = harness_path / "session-summary.json"
    if not summary_path.exists():
        errors.append(f"No session-summary.json at {summary_path}. Run harness_summary.py first.")
        return errors

    summary = load_json(summary_path, required=False)
    if summary is None:
        errors.append("Failed to read session-summary.json.")
        return errors

    counts = summary.get("progress_counts", {})
    total = counts.get("total", 0)
    done = counts.get("done", 0)
    in_prog = counts.get("in_progress", 0)
    blocked = counts.get("blocked", 0)

    if total == 0:
        errors.append("Harness has 0 features. Cannot approve empty campaign.")
    if done < total:
        errors.append(
            f"Harness features incomplete: {done}/{total} done "
            f"({in_prog} in_progress, {blocked} blocked)."
        )

    env_status = summary.get("environment_status", "unknown")
    if env_status == "failing":
        errors.append(f"Harness baseline_status is 'failing'. Fix tests before advancing.")

    # ── Layer 2: execute harness test_command + per-feature verification ──
    campaign_path = harness_path / "campaign.json"
    features_path = harness_path / "features.json"
    exec_errors = _run_harness_verification(root, campaign_path, features_path)
    errors.extend(exec_errors)

    return errors


def _run_harness_verification(root: Path, campaign_path: Path, features_path: Path) -> list[str]:
    """Actually execute the harness test_command and each done feature's
    verification.command. Checks exit codes, stderr for ERROR, and
    stdout against the verification.expected pattern."""
    errors = []

    campaign = load_json(campaign_path, required=False)
    if campaign is None:
        errors.append("Cannot read campaign.json for live verification.")
        return errors

    # 1. Run campaign-level test_command
    test_cmd = campaign.get("test_command", "")
    if test_cmd:
        result = _execute_command(test_cmd, root, label="campaign test_command")
        if result:
            errors.append(result)
    else:
        errors.append("campaign.json has no test_command. Cannot run live verification.")

    # 2. Run each done feature's verification.command + check expected output
    features_data = load_json(features_path, required=False)
    if features_data is None:
        errors.append("Cannot read features.json for per-feature verification.")
        return errors

    features = features_data.get("features", [])
    done_features = [f for f in features if f.get("status") == "done"]

    for feat in done_features:
        fid = feat.get("id", "?")
        v = feat.get("verification", {})
        if isinstance(v, dict):
            cmd = v.get("command", "")
            expected = v.get("expected", "")
        elif isinstance(v, str):
            cmd = v
            expected = ""
        else:
            cmd = ""
            expected = ""
        if not cmd:
            continue
        result = _execute_command(cmd, root, label=f"{fid} verification", expected=expected)
        if result:
            errors.append(result)

    return errors


def _execute_command(cmd: str, cwd: Path, label: str, timeout: int = 60,
                     expected: str = "") -> str | None:
    """Run a shell command. Validate:
    1. Exit code == 0
    2. No 'ERROR:' lines in stderr (catches tools that exit 0 on failure)
    3. If `expected` mentions 'contains X', check stdout for X
    Returns error string on failure or None on success."""
    print(f"  Running {label}: {cmd}", file=sys.stderr)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        combined = (result.stdout or "") + (result.stderr or "")

        # Gate 1: non-zero exit code
        if result.returncode != 0:
            preview = combined[:300].strip()
            return (
                f"{label} failed (exit {result.returncode}): {cmd}\n"
                f"    Output: {preview}"
            )

        # Gate 2: stderr ERROR lines (catches Godot, cargo, etc.)
        stderr_lines = (result.stderr or "").splitlines()
        error_lines = [l for l in stderr_lines if "ERROR:" in l or "FATAL:" in l]
        if error_lines:
            preview = "\n    ".join(error_lines[:5])
            return (
                f"{label} exit 0 but stderr contains errors:\n"
                f"    {preview}"
            )

        # Gate 3: expected output pattern
        if expected:
            expect_fail = _check_expected(expected, result.stdout or "", result.returncode)
            if expect_fail:
                return f"{label}: {expect_fail}"

        print(f"  ✓ {label} passed", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        return f"{label} timed out after {timeout}s: {cmd}"
    except Exception as e:
        return f"{label} execution error: {e}"


def _check_expected(expected: str, stdout: str, exit_code: int) -> str | None:
    """Parse the 'expected' field for simple assertions.
    Supports patterns like:
      - "stdout contains 'SMOKE_OK'"
      - "Exit code 0, stdout contains 'SMOKE_OK'"
      - Just a plain string → treated as 'stdout contains <string>'
    Returns error string on mismatch or None on success."""
    contains_patterns = re.findall(r"contains\s+['\"]([^'\"]+)['\"]", expected, re.IGNORECASE)
    if not contains_patterns:
        # Treat the whole expected string as a substring to find in stdout
        # (but skip if it looks like a general description like "All tests pass")
        if len(expected) < 40 and expected.replace(" ", "").isalnum():
            contains_patterns = [expected]

    for pattern in contains_patterns:
        if pattern not in stdout:
            stdout_preview = stdout[:200].strip() if stdout else "(empty)"
            return (
                f"Expected stdout to contain '{pattern}' but it was not found.\n"
                f"    Stdout: {stdout_preview}"
            )
    return None


def _validate_test(root: Path, art: dict) -> list[str]:
    """At least 1 pass, zero fails in results.
    Layer 2: re-execute any test plan items that have a command field."""
    errors = []
    results = art.get("results", [])
    if not results:
        errors.append("test-report has empty results. Execute tests first.")
        return errors

    pass_count = sum(1 for r in results if r.get("status") == "pass")
    fail_count = sum(1 for r in results if r.get("status") == "fail")

    if pass_count == 0:
        errors.append("No passing tests. At least 1 required.")
    if fail_count > 0:
        failed_names = [r.get("name", "?") for r in results if r.get("status") == "fail"]
        errors.append(f"{fail_count} test(s) failing: {', '.join(failed_names)}")

    # Check evidence is not empty
    empty_evidence = [
        r.get("name", "?") for r in results
        if r.get("status") == "pass" and not r.get("evidence", "").strip()
    ]
    if empty_evidence:
        errors.append(f"Passing tests with empty evidence: {', '.join(empty_evidence)}")

    # ── Layer 2: re-execute test commands from the plan ──
    plan = art.get("plan", [])
    for item in plan:
        cmd = item.get("command", "")
        if not cmd:
            continue
        name = item.get("name", cmd[:40])
        result = _execute_command(cmd, root, label=f"test '{name}'")
        if result:
            errors.append(result)

    return errors


def _validate_release(root: Path, art: dict) -> list[str]:
    """tagged_commit must be a resolvable git ref."""
    errors = []
    tag = art.get("tagged_commit", "")
    if not tag:
        errors.append("tagged_commit is empty.")
        return errors

    # Try to resolve as git ref
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", tag],
            capture_output=True, text=True, cwd=str(root), timeout=5,
        )
        if result.returncode != 0:
            errors.append(
                f"tagged_commit '{tag}' is not a valid git ref. "
                f"Create the tag first: git tag {tag}"
            )
    except FileNotFoundError:
        # git not available — skip this check but warn
        errors.append("Cannot verify tagged_commit — git not found on PATH.")
    except subprocess.TimeoutExpired:
        errors.append("git rev-parse timed out.")

    # Check for incomplete checklist items
    checklist = art.get("checklist", [])
    pending = [c.get("item", "?") for c in checklist if c.get("status") == "pending"]
    if pending:
        errors.append(f"Release checklist has {len(pending)} pending item(s): {', '.join(pending[:3])}")

    return errors


# Map phase → validator (phases without special validation have None)
PHASE_VALIDATORS = {
    "discovery": _validate_discovery,
    "design": _validate_design,
    "architecture": _validate_architecture,
    "implementation": _validate_implementation,
    "test": _validate_test,
    "release": _validate_release,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--approve-only", action="store_true",
                        help="Mark artifact approved but don't change current_phase")
    parser.add_argument("--refresh-stale", action="store_true",
                        help="Re-approve a stale artifact as-is (user confirms still valid)")
    parser.add_argument("--skip-hard-validation", action="store_true",
                        help="Bypass phase-specific hard validation (NOT recommended)")
    parser.add_argument("--confirm", action="store_true",
                        help="Confirm crossing a risk gate (required for auto-drive pauses)")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)
    lc = load_lifecycle(root)

    current = lc.get("current_phase")
    if not current:
        print("No current_phase in lifecycle.json", file=sys.stderr)
        return 1

    art = load_active_artifact(root, current)
    if art is None:
        print(f"No active artifact for {current}", file=sys.stderr)
        return 1

    # ── Gate 1: Required fields ──
    mode = lc.get("mode", "standard")
    missing = artifact_missing_fields(art, current, mode)
    if missing:
        print(f"Cannot advance — {current} artifact missing fields:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 1

    # ── Gate 2: Stale check ──
    if art.get("status") == "stale" and not args.refresh_stale:
        print(f"Cannot advance — {current} artifact is STALE (upstream was revised).", file=sys.stderr)
        print("Options:", file=sys.stderr)
        print("  - Re-enter the phase and update the artifact, then advance", file=sys.stderr)
        print("  - Pass --refresh-stale if the artifact is still valid as-is", file=sys.stderr)
        return 1

    # ── Gate 3: Phase-specific hard validation ──
    validator = PHASE_VALIDATORS.get(current)
    if validator and not args.skip_hard_validation:
        hard_errors = validator(root, art)
        if hard_errors:
            print(f"Cannot advance — {current} phase-specific validation failed:", file=sys.stderr)
            for e in hard_errors:
                print(f"  ✗ {e}", file=sys.stderr)
            print("Pass --skip-hard-validation to bypass (NOT recommended).", file=sys.stderr)
            return 1
        print(f"Hard validation passed for {current}")

    # ── Gate 4: Risk gate (artifact passed all validation, ready to approve) ──
    gate_key = f"{current}.approved"
    risk_gates = lc.get("risk_gates", [])
    if gate_key in risk_gates and not args.confirm:
        print(f"⏸  RISK GATE: approving {current} requires --confirm", file=sys.stderr)
        print(f"   Artifact passed all validation. Downstream will commit to it.", file=sys.stderr)
        print(f"   Review {active_artifact_path(root, current)} then re-run with --confirm.", file=sys.stderr)
        return 42

    # ── Approve ──
    art["status"] = "approved"
    art["last_updated"] = utc_now()
    save_json(active_artifact_path(root, current), art)
    print(f"Approved {current} · {art.get('id')}")

    if args.approve_only:
        log_transition(lc, "approve", {"phase": current, "id": art.get("id")})
        save_lifecycle(root, lc)
        return 0

    nxt = pick_next_phase(root, mode)
    if nxt is None:
        log_transition(lc, "approve", {"phase": current, "id": art.get("id"), "terminal": True})
        save_lifecycle(root, lc)
        print(f"All phases complete. Lifecycle done.")
        return 0

    lc["current_phase"] = nxt
    log_transition(lc, "advance", {"from": current, "to": nxt})
    save_lifecycle(root, lc)
    print(f"Advanced: {current} → {nxt}")

    parallel = [
        p for p in PHASES
        if p != nxt
        and not is_phase_skipped(p, mode)
        and phase_status(root, p, mode) == "ready"
    ]
    if parallel:
        print(f"Also ready (can work in parallel): {', '.join(parallel)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
