#!/usr/bin/env python3
"""Cross-phase consistency health checks (non-blocking).

Inspired by Karpathy's "lint" operation for LLM wikis. Unlike
engineering_advance.py which validates each phase in isolation,
lint checks cross-phase consistency and surfaces potential issues.

Usage:
  python3 engineering_lint.py --project-root <path>
  python3 engineering_lint.py --project-root <path> --json
  python3 engineering_lint.py --project-root <path> --severity warning

Exit codes: 0 always (lint is informational, never blocks)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

from engineering_lib import (
    PHASES,
    UPSTREAM,
    engineering_dir,
    load_active_artifact,
    load_decisions,
    load_insights,
    load_json,
    phase_dir,
    project_root_arg,
    require_engineering,
)

SEVERITY_ORDER = {"concern": 0, "warning": 1, "info": 2}
SEVERITY_GLYPH = {"concern": "\u2691", "warning": "\u26a0", "info": "\u2139"}


@dataclass
class LintFinding:
    check: str
    severity: str  # concern | warning | info
    message: str
    fix_hint: str = ""


# ── Lint checks ──────────────────────────────────────────────


def _check_requirement_coverage(root: Path) -> list[LintFinding]:
    """REQ IDs referenced downstream but missing, or REQs not referenced by anyone."""
    findings = []
    disc = load_active_artifact(root, "discovery")
    if not disc:
        return findings

    req_ids = {disc.get("id", "")}
    for g in disc.get("requirement_groups", []):
        if isinstance(g, dict):
            for r in g.get("requirements", []):
                req_ids.add(r)
    req_ids.discard("")

    referenced = set()
    for phase in ("design", "architecture", "implementation"):
        art = load_active_artifact(root, phase)
        if not art:
            continue
        for ref in art.get("implements_requirements", []):
            referenced.add(ref)

    for ref in referenced - req_ids:
        findings.append(LintFinding(
            check="requirement_coverage", severity="warning",
            message=f"Downstream references {ref} but it does not exist in requirements.",
            fix_hint=f"Add {ref} to requirements or remove the reference from downstream artifacts.",
        ))

    unreferenced = req_ids - referenced
    if unreferenced and any(load_active_artifact(root, p) for p in ("design", "architecture")):
        for req in sorted(unreferenced):
            findings.append(LintFinding(
                check="requirement_coverage", severity="info",
                message=f"{req} is not referenced by any downstream artifact.",
                fix_hint=f"Verify {req} is covered by design/architecture implements_requirements.",
            ))
    return findings



def _check_design_test_alignment(root: Path) -> list[LintFinding]:
    """Design components that may not be covered by the test plan."""
    findings = []
    design = load_active_artifact(root, "design")
    test = load_active_artifact(root, "test")
    if not design or not test:
        return findings

    components = [c.get("name", "") for c in design.get("components", []) if isinstance(c, dict)]
    plan_names = [p.get("name", "") for p in test.get("plan", []) if isinstance(p, dict)]
    plan_text = " ".join(plan_names).lower()

    for comp in components:
        if not comp:
            continue
        # Fuzzy: check if any word from component name appears in test plan
        words = [w for w in re.split(r"[\s_\-/]+", comp.lower()) if len(w) > 2]
        if words and not any(w in plan_text for w in words):
            findings.append(LintFinding(
                check="design_test_alignment", severity="warning",
                message=f"Component '{comp}' may not be covered by test plan.",
                fix_hint=f"Add a test plan entry covering '{comp}' or verify existing tests cover it.",
            ))
    return findings


def _check_adr_drift(root: Path) -> list[LintFinding]:
    """Remind to review accepted ADRs for implementation drift."""
    findings = []
    adrs_dir = engineering_dir(root) / "architecture" / "adrs"
    if not adrs_dir.is_dir():
        return findings

    impl = load_active_artifact(root, "implementation")
    if not impl or impl.get("status") not in ("approved", "done"):
        return findings

    for adr_file in sorted(adrs_dir.glob("ADR-*.json")):
        adr = load_json(adr_file, required=False)
        if not adr or adr.get("status") != "accepted":
            continue
        findings.append(LintFinding(
            check="adr_drift", severity="info",
            message=f"{adr.get('id', adr_file.stem)}: '{adr.get('title', '?')}' -- verify implementation still follows this decision.",
            fix_hint="Review the ADR decision against current implementation. Supersede if outdated.",
        ))
    return findings


def _check_stale_chain(root: Path) -> list[LintFinding]:
    """Artifacts marked stale but no upstream is revising -- inconsistent state."""
    findings = []

    for phase in PHASES:
        art = load_active_artifact(root, phase)
        if not art or art.get("status") != "stale":
            continue
        upstream_revising = any(
            (load_active_artifact(root, up) or {}).get("status") == "revising"
            for up in UPSTREAM[phase]
        )
        if not upstream_revising:
            findings.append(LintFinding(
                check="stale_chain", severity="concern",
                message=f"{phase} is stale but no upstream phase is revising -- inconsistent state.",
                fix_hint=f"Either revise the upstream phase or refresh {phase} with --refresh-stale.",
            ))
    return findings



def _check_decision_density(root: Path) -> list[LintFinding]:
    """Phases with approved artifacts but zero decisions logged."""
    findings = []
    decisions = load_decisions(root, limit=1000)
    phases_with_decisions = {d.get("phase") for d in decisions}

    for phase in PHASES:
        art = load_active_artifact(root, phase)
        if not art or art.get("status") != "approved":
            continue
        if phase not in phases_with_decisions:
            findings.append(LintFinding(
                check="decision_density", severity="warning",
                message=f"{phase} is approved but has zero decisions logged.",
                fix_hint="Review whether auto-drive skipped decision logging for this phase.",
            ))
    return findings


def _check_orphan_references(root: Path) -> list[LintFinding]:
    """Active artifacts referencing archived IDs."""
    findings = []
    id_pattern = re.compile(r"(?:REQ|DES|ARCH|IMPL|TEST|REL|OPS)-\d{3}")

    active_ids = set()
    for phase in PHASES:
        art = load_active_artifact(root, phase)
        if art and art.get("id"):
            active_ids.add(art["id"])

    # Build archive ID set upfront to avoid O(R*A) nested scan
    archived_ids = set()
    for p in PHASES:
        archive_dir = phase_dir(root, p) / "archive"
        if archive_dir.is_dir():
            for f in archive_dir.glob("*.json"):
                d = load_json(f, required=False)
                if d and d.get("id"):
                    archived_ids.add(d["id"])

    for phase in PHASES:
        art = load_active_artifact(root, phase)
        if not art:
            continue
        text = json.dumps(art)
        full_refs = set(id_pattern.findall(text))

        for ref in full_refs:
            if ref == art.get("id"):
                continue
            if ref not in active_ids and ref in archived_ids:
                findings.append(LintFinding(
                    check="orphan_references", severity="warning",
                    message=f"{phase} artifact references {ref} which is archived, not active.",
                    fix_hint="Update the reference to the current active artifact or remove it.",
                ))
    return findings


def _check_insight_backlog(root: Path) -> list[LintFinding]:
    """Unaddressed insights, especially contradictions."""
    findings = []
    unaddressed = load_insights(root, unaddressed_only=True)
    if not unaddressed:
        return findings

    by_target: dict[str, list[dict]] = {}
    for ins in unaddressed:
        tgt = ins.get("target_phase", "?")
        by_target.setdefault(tgt, []).append(ins)

    for target, items in sorted(by_target.items()):
        contradictions = [i for i in items if i.get("kind") == "contradiction"]
        if contradictions:
            findings.append(LintFinding(
                check="insight_backlog", severity="concern",
                message=f"{len(contradictions)} unaddressed contradiction(s) targeting {target}.",
                fix_hint=f"Review and address contradiction insights for {target} phase.",
            ))
        others = len(items) - len(contradictions)
        if others:
            findings.append(LintFinding(
                check="insight_backlog", severity="warning",
                message=f"{others} unaddressed insight(s) targeting {target}.",
                fix_hint=f"Run: engineering_insight.py --list --target {target} --unaddressed",
            ))
    return findings



ALL_CHECKS = [
    _check_requirement_coverage,
    _check_design_test_alignment,
    _check_adr_drift,
    _check_stale_chain,
    _check_decision_density,
    _check_orphan_references,
    _check_insight_backlog,
]


def run_all_checks(root: Path) -> list[LintFinding]:
    findings = []
    for check_fn in ALL_CHECKS:
        try:
            findings.extend(check_fn(root))
        except Exception as e:
            findings.append(LintFinding(
                check=check_fn.__name__, severity="warning",
                message=f"Check failed with error: {e}",
            ))
    findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 9))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-phase consistency lint")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--severity", default=None,
                        choices=["concern", "warning", "info"],
                        help="Minimum severity to show")
    args = parser.parse_args()

    root = project_root_arg(args.project_root)
    require_engineering(root)

    findings = run_all_checks(root)

    if args.severity:
        threshold = SEVERITY_ORDER.get(args.severity, 9)
        findings = [f for f in findings if SEVERITY_ORDER.get(f.severity, 9) <= threshold]

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        if not findings:
            print("Lint: all clear.")
            return 0
        print(f"Lint: {len(findings)} finding(s)\n")
        for f in findings:
            glyph = SEVERITY_GLYPH.get(f.severity, " ")
            print(f"  {glyph} [{f.check}] {f.message}")
            if f.fix_hint:
                print(f"    -> {f.fix_hint}")
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
