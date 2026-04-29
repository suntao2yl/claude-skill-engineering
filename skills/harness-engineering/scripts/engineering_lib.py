"""Shared library for engineering lifecycle orchestrator scripts."""
from __future__ import annotations

import hashlib
import json
import os
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

# v0.3.0: Scope levels for graduated ceremony (from CE brainstorm)
SCOPE_LEVELS = ["lightweight", "standard", "deep"]

# v0.3.0: Decision principles for auto-drive (from gstack autoplan)
DECISION_PRINCIPLES = [
    "completeness",          # finish what you started before starting new work
    "boil_lakes",            # do the complete thing when AI makes marginal cost near-zero
    "pragmatic",             # working code over perfect architecture
    "dry",                   # extract shared patterns, don't duplicate
    "explicit_over_clever",  # readable beats clever
    "bias_toward_action",    # when in doubt, ship it and iterate
]

# v0.3.0: Reviewer personas for multi-persona test review (from CE review)
REVIEWER_PERSONAS = [
    {"role": "security", "focus": "auth, injection, data exposure, secrets, input validation"},
    {"role": "performance", "focus": "latency, memory, N+1 queries, caching, algorithmic complexity"},
    {"role": "testing", "focus": "coverage gaps, edge cases, flaky tests, missing error paths"},
    {"role": "maintainability", "focus": "coupling, naming, documentation, complexity, dead code"},
]

# v0.3.0: Implementation backends
IMPL_BACKENDS = ["local", "managed_agents"]

# v0.5.0: Cross-phase insight kinds (Karpathy LLM Wiki inspired)
INSIGHT_KINDS = ["observation", "contradiction", "gap", "suggestion"]


# ── Platform detection (v0.4.0) ──────────────────────────────

def detect_platform() -> str:
    """Return 'codex' or 'claude' based on environment signals."""
    if os.environ.get("CODEX_SKILL_DIR"):
        return "codex"
    if os.environ.get("CLAUDE_SKILL_DIR"):
        return "claude"
    # Fallback: check if this script lives under ~/.codex/
    if ".codex" in Path(__file__).resolve().parts:
        return "codex"
    return "claude"


def skill_home() -> Path:
    """Return the platform's skill installation directory."""
    if detect_platform() == "codex":
        return Path.home() / ".codex" / "skills"
    return Path.home() / ".claude" / "skills"


def harness_plan_skill_dir() -> Path | None:
    """Locate the harness-plan skill directory across both platform conventions.
    Checks current platform first, then falls back to the other."""
    home = Path.home()
    platform = detect_platform()
    bases = [".codex", ".claude"] if platform == "codex" else [".claude", ".codex"]
    for base in bases:
        # Direct skill install
        direct = home / base / "skills" / "harness-plan"
        if (direct / "SKILL.md").exists() or (direct / "AGENTS.md").exists():
            return direct
        # Plugin/marketplace install
        plugins = home / base / "plugins"
        if plugins.exists():
            for match in plugins.glob("**/harness-plan/skills/harness-plan"):
                if (match / "SKILL.md").exists() or (match / "AGENTS.md").exists():
                    return match
        # Codex prompts directory
        prompts = home / base / "prompts"
        if prompts.exists():
            for match in prompts.glob("**/harness-plan"):
                if (match / "AGENTS.md").exists():
                    return match
    return None


def harness_discipline_completion_verify_script() -> Path | None:
    """Locate harness-discipline's completion_verify.py if installed.

    Engineering's implementation gate prefers this script over its own
    inline verification (single source of truth). Falls back to None if
    discipline isn't installed; callers handle that case.
    """
    home = Path.home()
    platform = detect_platform()
    bases = [".codex", ".claude"] if platform == "codex" else [".claude", ".codex"]
    for base in bases:
        plugins = home / base / "plugins"
        if not plugins.exists():
            continue
        for match in plugins.glob(
            "**/harness-discipline/skills/completion-verify/scripts/completion_verify.py"
        ):
            if match.exists():
                return match
    return None


@dataclass
class ManagedAgentSession:
    """Tracks a Managed Agents session for the implementation phase."""
    session_id: str
    status: str = "pending"  # pending | running | completed | failed | checkpointed
    started_at: str = ""
    last_checkpoint: str = ""
    features_completed: int = 0
    features_total: int = 0


@dataclass
class ValidationError:
    """Structured validation error with actionable fix hint."""
    code: str
    message: str
    fix_hint: str
    severity: str = "error"  # error | warning


@dataclass
class DecisionRecord:
    """Audit trail entry for auto-drive and executor decisions."""
    phase: str
    classification: str  # mechanical | taste | user_challenge
    principle: str       # which DECISION_PRINCIPLES entry applied (or "none")
    rationale: str
    rejected_alternative: str = ""
    auto: bool = True    # True if auto-drive made it, False if user
    timestamp: str = ""  # filled by log_decision if empty


def error_signature(errors: list[ValidationError]) -> str:
    """Hash sorted (code, message) tuples for loop detection."""
    items = sorted((e.code, e.message) for e in errors)
    raw = "|".join(f"{c}:{m}" for c, m in items)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ID format conventions are documented at docs/id-conventions.md.
# Phase 1 lint level: warning. Phase 4 will upgrade selected prefixes to error.
ID_PREFIX_PATTERNS: dict[str, str] = {
    "REQ":  r"^REQ-\d{3,}$",
    "DES":  r"^DES-\d{3,}$",
    "ADR":  r"^ADR-\d{3,}$",
    "IMPL": r"^IMPL-\d{3,}$",
    "TEST": r"^TEST-\d{3,}$",
    "REL":  r"^REL-\d{3,}$",
    "OPS":  r"^OPS-\d{3,}$",
    "EVAL": r"^EVAL-\d{3,}$",
    "CHG":  r"^CHG-\d{3,}$",
}


def validate_id_format(id_str: str, prefix: str) -> str | None:
    """Return None if id_str matches the convention for prefix, else a warn message.

    Caller decides severity. Phase 1 callers should treat the message as a
    warning (informational); Phase 4 will upgrade to error for new IDs.
    """
    import re
    pattern = ID_PREFIX_PATTERNS.get(prefix)
    if not pattern:
        return f"unknown ID prefix {prefix!r} (see docs/id-conventions.md)"
    if not isinstance(id_str, str) or not re.match(pattern, id_str):
        return (
            f"ID {id_str!r} does not match convention {pattern} "
            f"(see docs/id-conventions.md)"
        )
    return None


def _append_jsonl(path: Path, record: dict) -> None:
    """Fire-and-forget: append one JSON record to a .jsonl file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def record_metrics(project_root: Path, phase: str, metrics_dict: dict) -> None:
    """Fire-and-forget: append a metrics record to phase_runs.jsonl."""
    path = engineering_dir(project_root) / "metrics" / "phase_runs.jsonl"
    _append_jsonl(path, {"timestamp": utc_now(), "phase": phase, **metrics_dict})


def log_decision(project_root: Path, record: DecisionRecord) -> None:
    """Append a decision record to .engineering/decisions.jsonl."""
    if not record.timestamp:
        record.timestamp = utc_now()
    path = engineering_dir(project_root) / "decisions.jsonl"
    _append_jsonl(path, asdict(record))


def _load_jsonl(path: Path) -> list[dict]:
    """Read all records from a JSONL file."""
    if not path.exists():
        return []
    records = []
    try:
        for line in path.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                records.append(json.loads(line))
    except Exception:
        return []
    return records


def load_decisions(project_root: Path, phase: str | None = None, limit: int = 20) -> list[dict]:
    """Read recent decisions from decisions.jsonl, optionally filtered by phase."""
    records = _load_jsonl(engineering_dir(project_root) / "decisions.jsonl")
    if phase:
        records = [r for r in records if r.get("phase") == phase]
    return records[-limit:]


def load_insights(project_root: Path, target: str | None = None,
                  unaddressed_only: bool = False, limit: int = 50) -> list[dict]:
    """Read insights from insights.jsonl, optionally filtered."""
    records = _load_jsonl(engineering_dir(project_root) / "insights.jsonl")
    if target:
        records = [r for r in records if r.get("target_phase") == target]
    if unaddressed_only:
        records = [r for r in records if not r.get("addressed", False)]
    return records[-limit:]


def load_managed_session(project_root: Path) -> dict | None:
    """Load Managed Agents session state from implementation phase."""
    path = engineering_dir(project_root) / "implementation" / "managed-session.json"
    return load_json(path, required=False)


def save_managed_session(project_root: Path, session: ManagedAgentSession | dict) -> None:
    """Save Managed Agents session state."""
    path = engineering_dir(project_root) / "implementation" / "managed-session.json"
    data = asdict(session) if isinstance(session, ManagedAgentSession) else session
    save_json(path, data)


def get_scope_level(project_root: Path) -> str:
    """Read scope_level from discovery artifact, defaulting to 'standard'."""
    disc = load_active_artifact(project_root, "discovery")
    return disc.get("scope_level", "standard") if disc else "standard"


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


CURRENT_SCHEMA_VERSION = 2
_schema_warned: set = set()


def _migrate_v1_to_v2(data: dict) -> dict:
    """Non-destructive migration: adds v2 fields with safe defaults.
    Runs on read, not on write. Existing .engineering/ dirs continue to work."""
    if data.get("schema_version", 1) >= 2:
        return data
    # Discovery artifacts (detected by presence of problem_statement)
    if "problem_statement" in data:
        data.setdefault("raw_goal", data.get("problem_statement", ""))
        data.setdefault("scope_level", "")
        data.setdefault("pressure_test", {
            "is_right_problem": "",
            "cost_of_inaction": "",
            "highest_leverage_move": "",
        })
        data.setdefault("requirement_groups", [])
    # All artifacts: success criteria (Inc 3 prep)
    if "id" in data and "status" in data:
        data.setdefault("success_criteria", [])
        data.setdefault("success_evaluation", [])
    data["schema_version"] = 2
    return data


def load_json(path: Path, required: bool = True) -> Optional[Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Missing required file: {path}")
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Warn once per file on schema version mismatch, then auto-migrate
    if isinstance(data, dict):
        sv = data.get("schema_version")
        if sv is not None and sv < CURRENT_SCHEMA_VERSION:
            key = str(path)
            if key not in _schema_warned:
                _schema_warned.add(key)
                print(
                    f"Migrating {path.name} schema v{sv} → v{CURRENT_SCHEMA_VERSION}",
                    file=sys.stderr,
                )
            data = _migrate_v1_to_v2(data)
        elif sv is not None and sv > CURRENT_SCHEMA_VERSION:
            key = str(path)
            if key not in _schema_warned:
                _schema_warned.add(key)
                print(
                    f"WARNING: {path.name} schema_version={sv} "
                    f"(expected {CURRENT_SCHEMA_VERSION}). "
                    f"Newer version — some fields may be unknown.",
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
        "discovery": ["id", "title", "problem_statement", "users", "success_metrics", "scope_level", "pressure_test"],
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
