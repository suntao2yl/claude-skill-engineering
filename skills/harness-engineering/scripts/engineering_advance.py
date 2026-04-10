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

Exit codes: 0=success, 1=validation fail, 3=loop detected, 42=risk gate
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

from engineering_lib import (
    LOOP_THRESHOLD,
    LOOP_WINDOW,
    PHASES,
    ValidationError,
    active_artifact_path,
    artifact_missing_fields,
    engineering_dir,
    error_signature,
    is_phase_skipped,
    load_active_artifact,
    load_json,
    load_lifecycle,
    log_transition,
    phase_status,
    pick_next_phase,
    project_root_arg,
    record_metrics,
    require_engineering,
    save_json,
    save_lifecycle,
    utc_now,
)

# ── Phase-specific hard validators ────────────────────────────
# Each returns a list of ValidationError; empty = pass.


def _validate_discovery(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    users = art.get("users", [])
    metrics = art.get("success_metrics", [])
    problem = art.get("problem_statement", "").strip()

    trivial_users = [u for u in users if not isinstance(u, str) or len(u.strip()) < 3]
    if trivial_users:
        errors.append(ValidationError(
            code="DISC-001", severity="error",
            message=f"users has {len(trivial_users)} trivial entry(s) (empty or <3 chars).",
            fix_hint="Set artifact.users to an array of >=1 strings, each >=3 chars describing a concrete user profile.",
        ))

    trivial_metrics = [m for m in metrics if not isinstance(m, str) or len(m.strip()) < 5]
    if trivial_metrics:
        errors.append(ValidationError(
            code="DISC-002", severity="error",
            message=f"success_metrics has {len(trivial_metrics)} trivial entry(s) (empty or <5 chars).",
            fix_hint="Set artifact.success_metrics to an array of measurable outcomes, each >=5 chars (e.g. 'D7 retention >=30%').",
        ))

    if len(problem) < 20:
        errors.append(ValidationError(
            code="DISC-003", severity="error",
            message=f"problem_statement too short ({len(problem)} chars). Need >=20.",
            fix_hint="Expand problem_statement to >=20 chars with a clear description of the problem being solved.",
        ))
    return errors


def _validate_design(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    flows = art.get("flows", [])
    components = art.get("components", [])

    for i, flow in enumerate(flows):
        if not isinstance(flow, dict):
            errors.append(ValidationError(
                code="DES-001", severity="error",
                message=f"flows[{i}] is not an object.",
                fix_hint=f"Replace flows[{i}] with an object having 'name' and 'steps' fields.",
            ))
            continue
        name = flow.get("name", "")
        steps = flow.get("steps", [])
        if not name or not str(name).strip():
            errors.append(ValidationError(
                code="DES-002", severity="error",
                message=f"flows[{i}] has no name.",
                fix_hint=f"Set flows[{i}].name to a descriptive user journey name (e.g. 'First meeting').",
            ))
        if not steps:
            errors.append(ValidationError(
                code="DES-003", severity="error",
                message=f"flow '{name or i}' has empty steps.",
                fix_hint=f"Add >=2 non-empty steps to flow '{name or i}'.steps array.",
            ))
        elif any(not str(s).strip() for s in steps):
            errors.append(ValidationError(
                code="DES-004", severity="error",
                message=f"flow '{name or i}' has empty step(s).",
                fix_hint=f"Remove or fill empty strings in flow '{name or i}'.steps.",
            ))

    for i, comp in enumerate(components):
        if not isinstance(comp, dict):
            errors.append(ValidationError(
                code="DES-005", severity="error",
                message=f"components[{i}] is not an object.",
                fix_hint=f"Replace components[{i}] with an object having 'name' and 'spec' fields.",
            ))
            continue
        cname = comp.get("name", "")
        spec = comp.get("spec", "")
        if not cname or not str(cname).strip():
            errors.append(ValidationError(
                code="DES-006", severity="error",
                message=f"components[{i}] has no name.",
                fix_hint=f"Set components[{i}].name to a descriptive component name.",
            ))
        if not spec or len(str(spec).strip()) < 10:
            errors.append(ValidationError(
                code="DES-007", severity="error",
                message=f"component '{cname or i}' spec too short (<10 chars).",
                fix_hint=f"Expand component '{cname or i}'.spec to >=10 chars describing its purpose and behavior.",
            ))

    reqs = art.get("implements_requirements", [])
    disc = load_active_artifact(root, "discovery")
    if disc and reqs and disc.get("id") not in reqs:
        errors.append(ValidationError(
            code="DES-008", severity="error",
            message=f"implements_requirements {reqs} does not include '{disc.get('id')}'.",
            fix_hint=f"Add '{disc.get('id')}' to the implements_requirements array.",
        ))
    return errors


def _validate_architecture(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    adrs_dir = engineering_dir(root) / "architecture" / "adrs"
    adr_files = list(adrs_dir.glob("ADR-*.json")) if adrs_dir.is_dir() else []
    if not adr_files:
        errors.append(ValidationError(
            code="ARCH-001", severity="error",
            message="No ADR files in architecture/adrs/. At least 1 required.",
            fix_hint="Create at least one ADR file at .engineering/architecture/adrs/ADR-001.json with required fields: id, title, status, context, decision, consequences.",
        ))
    declared = art.get("adrs", [])
    for adr_id in declared:
        matching = [f for f in adr_files if adr_id in f.stem]
        if not matching:
            errors.append(ValidationError(
                code="ARCH-002", severity="error",
                message=f"Declared ADR '{adr_id}' has no matching file in adrs/.",
                fix_hint=f"Create .engineering/architecture/adrs/{adr_id}.json or remove '{adr_id}' from stack.json adrs array.",
            ))
    return errors


def _validate_implementation(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    harness_root = art.get("harness_root", "")
    if not harness_root:
        errors.append(ValidationError(
            code="IMPL-001", severity="error",
            message="harness_root is empty.",
            fix_hint="Set harness_root to the relative path of the .harness directory (e.g. '.engineering/implementation/.harness').",
        ))
        return errors

    harness_path = root / harness_root
    summary_path = harness_path / "session-summary.json"
    if not summary_path.exists():
        errors.append(ValidationError(
            code="IMPL-002", severity="error",
            message=f"No session-summary.json at {summary_path}.",
            fix_hint="Run harness_summary.py to generate session-summary.json, or create it manually with progress_counts.",
        ))
        return errors

    summary = load_json(summary_path, required=False)
    if summary is None:
        errors.append(ValidationError(
            code="IMPL-003", severity="error",
            message="Failed to read session-summary.json.",
            fix_hint="Ensure session-summary.json is valid JSON.",
        ))
        return errors

    counts = summary.get("progress_counts", {})
    total = counts.get("total", 0)
    done = counts.get("done", 0)
    in_prog = counts.get("in_progress", 0)
    blocked = counts.get("blocked", 0)

    if total == 0:
        errors.append(ValidationError(
            code="IMPL-004", severity="error",
            message="Harness has 0 features. Cannot approve empty campaign.",
            fix_hint="Add features to the harness campaign with progress_counts.total > 0.",
        ))
    if done < total:
        errors.append(ValidationError(
            code="IMPL-005", severity="error",
            message=f"Harness features incomplete: {done}/{total} done ({in_prog} in_progress, {blocked} blocked).",
            fix_hint="Complete all remaining features until progress_counts.done == progress_counts.total.",
        ))

    env_status = summary.get("environment_status", "unknown")
    if env_status == "failing":
        errors.append(ValidationError(
            code="IMPL-006", severity="error",
            message="Harness baseline_status is 'failing'. Fix tests before advancing.",
            fix_hint="Fix failing tests so environment_status becomes 'passing'.",
        ))

    campaign_path = harness_path / "campaign.json"
    features_path = harness_path / "features.json"
    exec_errors = _run_harness_verification(root, campaign_path, features_path)
    errors.extend(exec_errors)
    return errors


def _run_harness_verification(root: Path, campaign_path: Path, features_path: Path) -> list[ValidationError]:
    """Execute harness test_command and per-feature verification."""
    errors = []
    campaign = load_json(campaign_path, required=False)
    if campaign is None:
        errors.append(ValidationError(
            code="IMPL-010", severity="error",
            message="Cannot read campaign.json for live verification.",
            fix_hint="Create campaign.json in the .harness directory with a test_command field.",
        ))
        return errors

    test_cmd = campaign.get("test_command", "")
    if test_cmd:
        result = _execute_command(test_cmd, root, label="campaign test_command")
        if result:
            errors.append(ValidationError(
                code="IMPL-011", severity="error", message=result,
                fix_hint="Fix the campaign test_command so it exits 0 with no ERROR lines.",
            ))
    else:
        errors.append(ValidationError(
            code="IMPL-012", severity="error",
            message="campaign.json has no test_command. Cannot run live verification.",
            fix_hint="Add a test_command field to campaign.json (e.g. 'python3 -m pytest').",
        ))

    features_data = load_json(features_path, required=False)
    if features_data is None:
        errors.append(ValidationError(
            code="IMPL-013", severity="error",
            message="Cannot read features.json for per-feature verification.",
            fix_hint="Create features.json in the .harness directory.",
        ))
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
            errors.append(ValidationError(
                code=f"IMPL-V-{fid}", severity="error", message=result,
                fix_hint=f"Fix feature {fid}'s verification command or its implementation so the command passes.",
            ))
    return errors


def _execute_command(cmd: str, cwd: Path, label: str, timeout: int = 60,
                     expected: str = "") -> str | None:
    """Run a shell command. Returns error string on failure or None on success."""
    print(f"  Running {label}: {cmd}", file=sys.stderr)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        combined = (result.stdout or "") + (result.stderr or "")
        if result.returncode != 0:
            preview = combined[:300].strip()
            return f"{label} failed (exit {result.returncode}): {cmd}\n    Output: {preview}"
        stderr_lines = (result.stderr or "").splitlines()
        error_lines = [l for l in stderr_lines if "ERROR:" in l or "FATAL:" in l]
        if error_lines:
            preview = "\n    ".join(error_lines[:5])
            return f"{label} exit 0 but stderr contains errors:\n    {preview}"
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
    """Parse the 'expected' field for simple assertions."""
    contains_patterns = re.findall(r"contains\s+['\"]([^'\"]+)['\"]", expected, re.IGNORECASE)
    if not contains_patterns:
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


def _validate_test(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    results = art.get("results", [])
    if not results:
        errors.append(ValidationError(
            code="TEST-001", severity="error",
            message="test-report has empty results. Execute tests first.",
            fix_hint="Run the test plan and populate results array with {name, status, evidence} objects.",
        ))
        return errors

    pass_count = sum(1 for r in results if r.get("status") == "pass")
    fail_count = sum(1 for r in results if r.get("status") == "fail")

    if pass_count == 0:
        errors.append(ValidationError(
            code="TEST-002", severity="error",
            message="No passing tests. At least 1 required.",
            fix_hint="Ensure at least one test result has status='pass'.",
        ))
    if fail_count > 0:
        failed_names = [r.get("name", "?") for r in results if r.get("status") == "fail"]
        errors.append(ValidationError(
            code="TEST-003", severity="error",
            message=f"{fail_count} test(s) failing: {', '.join(failed_names)}",
            fix_hint="Fix failing tests or update their status. All tests must pass to advance.",
        ))

    empty_evidence = [
        r.get("name", "?") for r in results
        if r.get("status") == "pass" and not r.get("evidence", "").strip()
    ]
    if empty_evidence:
        errors.append(ValidationError(
            code="TEST-004", severity="error",
            message=f"Passing tests with empty evidence: {', '.join(empty_evidence)}",
            fix_hint="Add non-empty evidence strings to passing test results (exit code, stdout excerpt, etc.).",
        ))

    plan = art.get("plan", [])
    for item in plan:
        cmd = item.get("command", "")
        if not cmd:
            continue
        name = item.get("name", cmd[:40])
        result = _execute_command(cmd, root, label=f"test '{name}'")
        if result:
            errors.append(ValidationError(
                code="TEST-005", severity="error", message=result,
                fix_hint=f"Fix test '{name}' so its command passes.",
            ))
    return errors


def _validate_release(root: Path, art: dict) -> list[ValidationError]:
    errors = []
    tag = art.get("tagged_commit", "")
    if not tag:
        errors.append(ValidationError(
            code="REL-001", severity="error",
            message="tagged_commit is empty.",
            fix_hint="Set tagged_commit to a valid git tag or commit SHA.",
        ))
        return errors

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", tag],
            capture_output=True, text=True, cwd=str(root), timeout=5,
        )
        if result.returncode != 0:
            errors.append(ValidationError(
                code="REL-002", severity="error",
                message=f"tagged_commit '{tag}' is not a valid git ref.",
                fix_hint=f"Create the tag first: git tag {tag}",
            ))
    except FileNotFoundError:
        errors.append(ValidationError(
            code="REL-003", severity="warning",
            message="Cannot verify tagged_commit — git not found on PATH.",
            fix_hint="Install git or skip this check.",
        ))
    except subprocess.TimeoutExpired:
        errors.append(ValidationError(
            code="REL-004", severity="warning",
            message="git rev-parse timed out.",
            fix_hint="Check git repository health.",
        ))

    checklist = art.get("checklist", [])
    pending = [c.get("item", "?") for c in checklist if c.get("status") == "pending"]
    if pending:
        errors.append(ValidationError(
            code="REL-005", severity="error",
            message=f"Release checklist has {len(pending)} pending item(s): {', '.join(pending[:3])}",
            fix_hint="Complete all checklist items (set status to 'done' or 'skipped').",
        ))
    return errors


# Map phase -> validator
PHASE_VALIDATORS = {
    "discovery": _validate_discovery,
    "design": _validate_design,
    "architecture": _validate_architecture,
    "implementation": _validate_implementation,
    "test": _validate_test,
    "release": _validate_release,
}


# ── Loop detection helpers ──

def _check_loop(lc: dict, sig: str) -> bool:
    """Check if the same error signature has repeated >= LOOP_THRESHOLD times."""
    ld = lc.get("loop_detection", {})
    recent = ld.get("recent_signatures", [])
    if len(recent) < LOOP_THRESHOLD - 1:
        return False
    tail = recent[-(LOOP_THRESHOLD - 1):]
    return all(s == sig for s in tail)


def _record_loop_signature(lc: dict, sig: str) -> None:
    """Append signature to loop_detection.recent_signatures (bounded)."""
    ld = lc.setdefault("loop_detection", {})
    recent = ld.setdefault("recent_signatures", [])
    recent.append(sig)
    if len(recent) > LOOP_WINDOW:
        ld["recent_signatures"] = recent[-LOOP_WINDOW:]


def _clear_loop_signatures(lc: dict) -> None:
    """Clear loop detection state on success."""
    if "loop_detection" in lc:
        lc["loop_detection"]["recent_signatures"] = []


def main() -> int:
    t0 = time.time()
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

    exit_code = 0
    error_sigs = []
    try:
        # Gate 1: Required fields
        mode = lc.get("mode", "standard")
        missing = artifact_missing_fields(art, current, mode)
        if missing:
            print(f"Cannot advance — {current} artifact missing fields:", file=sys.stderr)
            for m in missing:
                print(f"  - {m}", file=sys.stderr)
            exit_code = 1
            return exit_code

        # Gate 2: Stale check
        if art.get("status") == "stale" and not args.refresh_stale:
            print(f"Cannot advance — {current} artifact is STALE (upstream was revised).", file=sys.stderr)
            print("Options:", file=sys.stderr)
            print("  - Re-enter the phase and update the artifact, then advance", file=sys.stderr)
            print("  - Pass --refresh-stale if the artifact is still valid as-is", file=sys.stderr)
            exit_code = 1
            return exit_code

        # Gate 3: Phase-specific hard validation
        validator = PHASE_VALIDATORS.get(current)
        if validator and not args.skip_hard_validation:
            hard_errors = validator(root, art)
            if hard_errors:
                print(f"Cannot advance — {current} phase-specific validation failed:", file=sys.stderr)
                for e in hard_errors:
                    print(f"  ✗ {e.message}", file=sys.stderr)
                    print(f"    → Fix: {e.fix_hint}", file=sys.stderr)
                print("Pass --skip-hard-validation to bypass (NOT recommended).", file=sys.stderr)

                # Loop detection
                sig = error_signature(hard_errors)
                error_sigs = [sig]
                if _check_loop(lc, sig):
                    print(f"\nLOOP_DETECTED: same validation errors repeated {LOOP_THRESHOLD} times. Escalating to user.", file=sys.stderr)
                    _record_loop_signature(lc, sig)
                    save_lifecycle(root, lc)
                    exit_code = 3
                    return exit_code
                _record_loop_signature(lc, sig)
                save_lifecycle(root, lc)

                exit_code = 1
                return exit_code
            print(f"Hard validation passed for {current}")

        # Gate 4: Risk gate
        gate_key = f"{current}.approved"
        risk_gates = lc.get("risk_gates", [])
        if gate_key in risk_gates and not args.confirm:
            print(f"⏸  RISK GATE: approving {current} requires --confirm", file=sys.stderr)
            print(f"   Artifact passed all validation. Downstream will commit to it.", file=sys.stderr)
            print(f"   Review {active_artifact_path(root, current)} then re-run with --confirm.", file=sys.stderr)
            exit_code = 42
            return exit_code

        # Approve
        art["status"] = "approved"
        art["last_updated"] = utc_now()
        save_json(active_artifact_path(root, current), art)
        print(f"Approved {current} · {art.get('id')}")

        # Clear loop detection on success
        _clear_loop_signatures(lc)

        if args.approve_only:
            log_transition(lc, "approve", {"phase": current, "id": art.get("id")})
            save_lifecycle(root, lc)
            return 0

        nxt = pick_next_phase(root, mode)
        if nxt is None:
            log_transition(lc, "approve", {"phase": current, "id": art.get("id"), "terminal": True})
            save_lifecycle(root, lc)
            print("All phases complete. Lifecycle done.")
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

    finally:
        elapsed_ms = int((time.time() - t0) * 1000)
        record_metrics(root, current, {
            "execution_time_ms": elapsed_ms,
            "exit_code": exit_code,
            "error_signatures": error_sigs,
        })


if __name__ == "__main__":
    sys.exit(main())
