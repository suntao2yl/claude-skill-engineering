#!/usr/bin/env python3
"""Generate Codex-compatible skill files from Claude Code sources.

Reads SKILL.md + briefs from harness-engineering and harness-plan,
applies tool name mappings, path replacements, and syntax transforms,
then writes AGENTS.md + transformed resources to the output directory.

Usage:
  python3 codex/generate_codex.py \\
    --engineering-src ./skills/harness-engineering \\
    --plan-src /path/to/harness-plan/skills/harness-plan \\
    --output-dir ./codex-output

  python3 codex/generate_codex.py \\
    --engineering-src ./skills/harness-engineering \\
    --output-dir ./codex-output \\
    --symlink-scripts
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import yaml
from pathlib import Path

# ── Tool name mapping ────────────────────────────────────────

TOOL_MAP = {
    "Bash": "Execute",
    "Write": "Create",
    "Read": "Read",
    "Edit": "Edit",
    "Glob": None,
    "Grep": None,
    "Agent": None,
    "TaskCreate": None,
    "TaskUpdate": None,
    "TaskList": None,
    "TaskGet": None,
    "EnterPlanMode": None,
    "AskUserQuestion": "request_user_input",
}

# Tools with no Codex equivalent get prose replacements
TOOL_PROSE = {
    "Glob": "Use `Execute` with `find` to search for files by pattern.",
    "Grep": "Use `Execute` with `grep` or `rg` to search file contents.",
    "Agent": "Execute sub-tasks sequentially in the current session.",
    "TaskCreate": "Track progress using structured prose notes.",
    "TaskUpdate": "Update progress tracking in prose.",
    "TaskList": "Review current task status.",
    "TaskGet": "Check task details.",
    "EnterPlanMode": "",  # silently removed
}

DESCRIPTION_MAX = 1024

# ── Frontmatter parsing ──────────────────────────────────────

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split markdown into YAML frontmatter dict and body."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    fm_str = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")
    try:
        fm = yaml.safe_load(fm_str) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def transform_frontmatter(fm: dict) -> str:
    """Convert Claude frontmatter to Codex-compatible YAML."""
    out = {}
    if "name" in fm:
        out["name"] = fm["name"]
    if "description" in fm:
        desc = fm["description"]
        if isinstance(desc, str) and len(desc) > DESCRIPTION_MAX:
            desc = desc[:DESCRIPTION_MAX - 3] + "..."
        out["description"] = desc
    if not out:
        return ""
    lines = ["---"]
    for k, v in out.items():
        if isinstance(v, str) and (":" in v or "\n" in v):
            lines.append(f'{k}: "{v}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ── Body transforms ─────────────────────────────────────────

def replace_skill_dir_var(text: str) -> str:
    return text.replace("${CLAUDE_SKILL_DIR}", "${CODEX_SKILL_DIR}")


def replace_claude_paths(text: str) -> str:
    text = text.replace("~/.claude/skills/", "~/.codex/skills/")
    text = text.replace("~/.claude/plugins/", "~/.codex/prompts/")
    text = text.replace("~/.claude/", "~/.codex/")
    return text


def replace_at_file_refs(text: str) -> str:
    """Replace @file references with prose."""
    text = re.sub(
        r'@file\s+(resources/\S+)',
        r'Read the file \1',
        text,
    )
    text = re.sub(
        r'read @file\s+(resources/\S+)',
        r'Read the file \1',
        text,
    )
    return text


def replace_tool_names(text: str) -> str:
    """Replace Claude tool names with Codex equivalents in prose."""
    for claude_name, codex_name in TOOL_MAP.items():
        if codex_name:
            # Replace in allowed-tools style lists and prose
            text = re.sub(
                rf'\b{claude_name}\b(?!\()',  # don't replace function calls
                codex_name,
                text,
            )
    # Agent tool dispatch pattern
    text = re.sub(
        r'dispatch Agent\([^)]*\)',
        'execute the phase brief directly (run the composed prompt inline)',
        text,
    )
    text = re.sub(
        r'Agent\(subagent_type=[^)]*\)',
        'execute the sub-task directly',
        text,
    )
    # Agent tool prose references
    text = re.sub(
        r'(?:via |using |the )Agent tool',
        'by executing sub-tasks sequentially',
        text,
    )
    text = re.sub(
        r'Agent tool',
        'sequential sub-task execution',
        text,
    )
    # AskUserQuestion -> request_user_input
    text = text.replace("AskUserQuestion", "request_user_input")
    return text


def replace_skill_md_refs(text: str) -> str:
    """Replace SKILL.md references with AGENTS.md."""
    text = text.replace("SKILL.md", "AGENTS.md")
    return text


def transform_body(text: str) -> str:
    """Apply all body-level transformations."""
    text = replace_skill_dir_var(text)
    text = replace_claude_paths(text)
    text = replace_at_file_refs(text)
    text = replace_tool_names(text)
    text = replace_skill_md_refs(text)
    return text


# ── File processors ──────────────────────────────────────────

def transform_skill_md(content: str) -> str:
    """Convert SKILL.md content to AGENTS.md content."""
    fm, body = parse_frontmatter(content)
    new_fm = transform_frontmatter(fm)
    new_body = transform_body(body)
    return new_fm + "\n" + new_body


def transform_brief(content: str) -> str:
    """Transform a brief .md file for Codex (strip frontmatter, apply body transforms)."""
    _, body = parse_frontmatter(content)
    return transform_body(body)


def transform_resource(content: str) -> str:
    """Transform a non-brief resource .md file (apply body transforms, keep frontmatter if any)."""
    fm, body = parse_frontmatter(content)
    new_body = transform_body(body)
    if fm:
        return transform_frontmatter(fm) + "\n" + new_body
    return new_body


def has_claude_refs(content: str) -> bool:
    """Check if content has any Claude-specific references that need transformation."""
    markers = ["${CLAUDE_SKILL_DIR}", "@file ", "~/.claude/", "SKILL.md",
               "Agent(", "Agent tool", "AskUserQuestion", "EnterPlanMode"]
    return any(m in content for m in markers)


def process_skill(src_dir: Path, skill_name: str, output_dir: Path,
                   symlink_scripts: bool = False) -> dict:
    """Process one skill directory: generate AGENTS.md + transformed resources."""
    out = output_dir / skill_name
    out.mkdir(parents=True, exist_ok=True)
    stats = {"skill": skill_name, "agents_md": False, "briefs": 0, "resources": 0, "scripts": False}

    # 1. SKILL.md -> AGENTS.md
    skill_md = src_dir / "SKILL.md"
    if skill_md.exists():
        content = skill_md.read_text(encoding="utf-8")
        agents_md = transform_skill_md(content)
        (out / "AGENTS.md").write_text(agents_md, encoding="utf-8")
        stats["agents_md"] = True

    # 2. Transform briefs
    briefs_dir = src_dir / "resources" / "briefs"
    if briefs_dir.is_dir():
        out_briefs = out / "resources" / "briefs"
        out_briefs.mkdir(parents=True, exist_ok=True)
        for brief in sorted(briefs_dir.glob("*.md")):
            content = brief.read_text(encoding="utf-8")
            transformed = transform_brief(content)
            (out_briefs / brief.name).write_text(transformed, encoding="utf-8")
            stats["briefs"] += 1

    # 3. Transform other resources
    res_dir = src_dir / "resources"
    if res_dir.is_dir():
        out_res = out / "resources"
        out_res.mkdir(parents=True, exist_ok=True)
        for res_file in sorted(res_dir.glob("*.md")):
            content = res_file.read_text(encoding="utf-8")
            if has_claude_refs(content):
                transformed = transform_resource(content)
            else:
                transformed = content  # copy as-is
            (out_res / res_file.name).write_text(transformed, encoding="utf-8")
            stats["resources"] += 1

    # 4. Scripts (symlink or copy)
    scripts_dir = src_dir / "scripts"
    if scripts_dir.is_dir():
        out_scripts = out / "scripts"
        if out_scripts.exists():
            if out_scripts.is_symlink():
                out_scripts.unlink()
            else:
                shutil.rmtree(out_scripts)
        if symlink_scripts:
            out_scripts.symlink_to(scripts_dir.resolve())
        else:
            shutil.copytree(scripts_dir, out_scripts,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        stats["scripts"] = True

    return stats


# ── Main ─────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Codex-compatible skill files from Claude Code sources")
    parser.add_argument("--engineering-src", required=True,
                        help="Path to harness-engineering skill dir")
    parser.add_argument("--plan-src", default=None,
                        help="Path to harness-plan skill dir (optional)")
    parser.add_argument("--output-dir", default="./codex-output",
                        help="Output directory")
    parser.add_argument("--symlink-scripts", action="store_true",
                        help="Symlink scripts/ instead of copying")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be generated without writing")
    args = parser.parse_args()

    eng_src = Path(args.engineering_src).resolve()
    out_dir = Path(args.output_dir).resolve()

    if not eng_src.is_dir():
        print(f"Error: {eng_src} is not a directory", file=sys.stderr)
        return 1

    if args.dry_run:
        print(f"Would generate Codex output at: {out_dir}")
        print(f"  harness-engineering from: {eng_src}")
        if args.plan_src:
            print(f"  harness-plan from: {Path(args.plan_src).resolve()}")
        print(f"  symlink scripts: {args.symlink_scripts}")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)

    # Process harness-engineering
    stats_eng = process_skill(eng_src, "harness-engineering", out_dir, args.symlink_scripts)
    print(f"✓ harness-engineering: AGENTS.md={stats_eng['agents_md']}, "
          f"briefs={stats_eng['briefs']}, resources={stats_eng['resources']}, "
          f"scripts={stats_eng['scripts']}")

    # Process harness-plan (optional)
    if args.plan_src:
        plan_src = Path(args.plan_src).resolve()
        if not plan_src.is_dir():
            print(f"Warning: {plan_src} is not a directory, skipping harness-plan", file=sys.stderr)
        else:
            stats_plan = process_skill(plan_src, "harness-plan", out_dir, args.symlink_scripts)
            print(f"✓ harness-plan: AGENTS.md={stats_plan['agents_md']}, "
                  f"briefs={stats_plan['briefs']}, resources={stats_plan['resources']}, "
                  f"scripts={stats_plan['scripts']}")

    # Verification summary
    print(f"\nOutput: {out_dir}")
    _verify_output(out_dir)
    return 0


def _verify_output(out_dir: Path) -> None:
    """Quick verification that no Claude-specific refs leaked through."""
    issues = []
    for md_file in out_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        rel = md_file.relative_to(out_dir)
        if "${CLAUDE_SKILL_DIR}" in content:
            issues.append(f"  {rel}: contains ${{CLAUDE_SKILL_DIR}}")
        if "allowed-tools:" in content and md_file.name == "AGENTS.md":
            issues.append(f"  {rel}: contains allowed-tools in frontmatter")
        # @file is ok in prose like "Read the file" but not as @file syntax
        if re.search(r'(?:read )?@file\s+\S', content):
            issues.append(f"  {rel}: contains @file syntax")
    if issues:
        print("⚠ Verification issues:")
        for i in issues:
            print(i)
    else:
        print("✓ Verification passed: no Claude-specific refs in output")


if __name__ == "__main__":
    sys.exit(main())
