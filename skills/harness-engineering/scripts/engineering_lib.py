"""Shared library for engineering lifecycle orchestrator scripts."""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PHASES = [
    "discovery",
    "design",
    "architecture",
    "implementation",
    "test",
    "release",
    "ops",
]

# Phases that minimal mode skips
MINIMAL_SKIP = {"discovery", "design", "architecture", "release", "ops"}

# Status values per artifact
ARTIFACT_STATUS = {"draft", "in_progress", "approved", "revising", "stale", "archived"}

# Upstream dependency graph (phase -> list of phases it consumes)
UPSTREAM = {
    "discovery": [],
    "design": ["discovery"],
    "architecture": ["discovery"],
    "implementation": ["design", "architecture"],
    "test": ["implementation"],
    "release": ["test"],
    "ops": ["release"],
}


# Loop detection constants
LOOP_THRESHOLD = 3
LOOP_WINDOW = 5


@dataclass
class ValidationError:
    """Structured validation error with actionable fix hint."""
    code: str
    message: str
    fix_hint: str
    severity: str = "error"  # error | warning


def error_signature(errors: list[ValidationError]) -> str:
    """Hash sorted (code, message) tuples for loop detection."""
    items = sorted((e.code, e.message) for e in errors)
    raw = "|".join(f"{c}:{m}" for c, m in items)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def record_metrics(project_root: Path, phase: str, metrics_dict: dict) -> None:
    """Fire-and-forget: append a metrics record to phase_runs.jsonl."""
    try:
        metrics_dir = engineering_dir(project_root) / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": utc_now(), "phase": phase, **metrics_dict}
        path = metrics_dir / "phase_runs.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # fire-and-forget


def load_phase_brief(phase: str) -> str:
    """Load the per-phase brief from resources/briefs/{phase}.md."""
    skill_dir = Path(__file__).resolve().parent.parent
    brief_path = skill_dir / "resources" / "briefs" / f"{phase}.md"
    if brief_path.exists():
        return brief_path.read_text(encoding="utf-8")
    # Fallback: try legacy monolithic file
    legacy = skill_dir / "resources" / "phase-executor-briefs.md"
    if legacy.exists():
        return legacy.read_text(encoding="utf-8")
    return ""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def display_width(s: str) -> int:
    """Monospace display width, counting CJK wide chars as 2."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def truncate_display(s: str, max_width: int) -> str:
    """Truncate to max_width display cells, appending … if cut."""
    if display_width(s) <= max_width:
        return s
    out = []
    w = 0
    for c in s:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw + 1 > max_width:
            break
        out.append(c)
        w += cw
    return "".join(out) + "…"


def pad_display(s: str, width: int) -> str:
    """Right-pad with spaces to a given display width."""
    return s + " " * max(0, width - display_width(s))


def project_root_arg(value: Optional[str]) -> Path:
    if value and value != ".":
        return Path(value).resolve()
    return Path.cwd().resolve()


def engineering_dir(project_root: Path) -> Path:
    return project_root / ".engineering"


def require_engineering(project_root: Path) -> None:
    d = engineering_dir(project_root)
    if not d.is_dir():
        print(
            f"No .engineering/ directory at {d}.\n"
            f"Resolved project root: {project_root}\n"
            f"Working directory: {Path.cwd()}\n"
            f"Hint: run engineering_init.py first, or pass --project-root <path>.",
            file=sys.stderr,
        )
        sys.exit(1)


def lifecycle_path(project_root: Path) -> Path:
    return engineering_dir(project_root) / "lifecycle.json"


def phase_dir(project_root: Path, phase: str) -> Path:
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    return engineering_dir(project_root) / phase


CURRENT_SCHEMA_VERSION = 1
_schema_warned: set = set()


def load_json(path: Path, required: bool = True) -> Optional[Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing required file: {path}")
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Warn once per file on schema version mismatch
    if isinstance(data, dict):
        sv = data.get("schema_version")
        if sv is not None and sv != CURRENT_SCHEMA_VERSION:
            key = str(path)
            if key not in _schema_warned:
                _schema_warned.add(key)
                print(
                    f"WARNING: {path.name} schema_version={sv} "
                    f"(expected {CURRENT_SCHEMA_VERSION}). "
                    f"Migration may be required.",
                    file=sys.stderr,
                )
    return data


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_lifecycle(project_root: Path) -> dict:
    return load_json(lifecycle_path(project_root))


def save_lifecycle(project_root: Path, lifecycle: dict) -> None:
    lifecycle["last_updated"] = utc_now()
    save_json(lifecycle_path(project_root), lifecycle)


def active_artifact_path(project_root: Path, phase: str) -> Path:
    """Path to the single active artifact for a phase (may not exist)."""
    mapping = {
        "discovery": "requirements.json",
        "design": "design-spec.json",
        "architecture": "stack.json",
        "implementation": "campaign-ref.json",
        "test": "test-report.json",
        "release": "release-checklist.json",
        "ops": "metrics.json",
    }
    return phase_dir(project_root, phase) / mapping[phase]


def load_active_artifact(project_root: Path, phase: str) -> Optional[dict]:
    return load_json(active_artifact_path(project_root, phase), required=False)


def log_transition(lifecycle: dict, kind: str, detail: dict) -> None:
    entry = {"at": utc_now(), "kind": kind, **detail}
    lifecycle.setdefault("phase_history", []).append(entry)


def required_fields(phase: str, mode: str = "standard") -> list[str]:
    """Minimum required fields for a phase's active artifact to be 'approved'.
    In minimal mode, implementation/test drop references to skipped phases."""
    base = {
        "discovery": ["id", "title", "problem_statement", "users", "success_metrics"],
        "design": ["id", "implements_requirements", "flows"],
        "architecture": ["id", "stack", "adrs"],
        "implementation": ["campaign_id", "harness_root", "implements_requirements"],
        "test": ["id", "campaign_ref", "plan", "results"],
        "release": ["id", "version", "checklist", "rollback_plan"],
        "ops": ["id"],
    }[phase]
    if mode == "minimal":
        if phase == "implementation":
            return [f for f in base if f != "implements_requirements"]
    return base


def artifact_missing_fields(artifact: Optional[dict], phase: str, mode: str = "standard") -> list[str]:
    if artifact is None:
        return required_fields(phase, mode)
    missing = []
    for f in required_fields(phase, mode):
        v = artifact.get(f)
        if v in (None, "", [], {}):
            missing.append(f)
    return missing


def phase_status(project_root: Path, phase: str, mode: str = "standard") -> str:
    """Derived status of a phase: pending | ready | draft | in_progress |
    approved | revising | stale | archived."""
    art = load_active_artifact(project_root, phase)
    if art is not None:
        return art.get("status") or "draft"
    # No artifact yet: pending if upstream not ready, else ready
    for up in UPSTREAM[phase]:
        if is_phase_skipped(up, mode):
            continue
        up_art = load_active_artifact(project_root, up)
        if up_art is None or up_art.get("status") != "approved":
            return "pending"
    return "ready"


def is_phase_skipped(phase: str, mode: str) -> bool:
    return mode == "minimal" and phase in MINIMAL_SKIP


def pick_next_phase(project_root: Path, mode: str) -> Optional[str]:
    """Find the first phase (canonical order) that is not yet approved and
    whose upstream is all approved. Handles parallel phases naturally."""
    for p in PHASES:
        if is_phase_skipped(p, mode):
            continue
        status = phase_status(project_root, p, mode)
        if status == "approved":
            continue
        # Need upstream all approved (or phase is ready)
        upstream_ok = all(
            phase_status(project_root, up, mode) == "approved" or is_phase_skipped(up, mode)
            for up in UPSTREAM[p]
        )
        if upstream_ok:
            return p
    return None


def next_id(phase: str, existing_ids: list[str]) -> str:
    prefix = {
        "discovery": "REQ",
        "design": "DES",
        "architecture": "ARCH",
        "implementation": "IMPL",
        "test": "TEST",
        "release": "REL",
        "ops": "OPS",
    }[phase]
    nums = []
    for id_ in existing_ids:
        if id_ and id_.startswith(prefix + "-"):
            try:
                nums.append(int(id_.split("-")[1]))
            except (ValueError, IndexError):
                pass
    return f"{prefix}-{(max(nums) + 1 if nums else 1):03d}"
