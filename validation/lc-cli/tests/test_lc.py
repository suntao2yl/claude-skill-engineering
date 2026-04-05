"""Tests for lc module."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import lc  # noqa: E402


class TestCountLines:
    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.txt"
        p.write_text("")
        assert lc.count_lines(str(p)) == 0

    def test_single_line_no_newline(self, tmp_path: Path) -> None:
        p = tmp_path / "one.txt"
        p.write_text("hello")
        assert lc.count_lines(str(p)) == 1

    def test_single_line_with_newline(self, tmp_path: Path) -> None:
        p = tmp_path / "one_nl.txt"
        p.write_text("hello\n")
        assert lc.count_lines(str(p)) == 1

    def test_multiple_lines(self, tmp_path: Path) -> None:
        p = tmp_path / "many.txt"
        p.write_text("a\nb\nc\n")
        assert lc.count_lines(str(p)) == 3

    def test_multiple_lines_no_trailing_newline(self, tmp_path: Path) -> None:
        p = tmp_path / "many2.txt"
        p.write_text("a\nb\nc")
        assert lc.count_lines(str(p)) == 3

    def test_large_file_across_chunks(self, tmp_path: Path) -> None:
        p = tmp_path / "big.txt"
        # Write 100k lines, forces multiple chunk reads
        p.write_text("\n".join(f"line{i}" for i in range(100_000)) + "\n")
        assert lc.count_lines(str(p)) == 100_000


class TestFormatResult:
    def test_success(self) -> None:
        out = lc.format_result("a.txt", 5, None)
        assert json.loads(out) == {"file": "a.txt", "line_count": 5}

    def test_error(self) -> None:
        out = lc.format_result("x.txt", None, "file not found")
        assert json.loads(out) == {"file": "x.txt", "error": "file not found"}


class TestMainCLI:
    def test_happy_path(self, tmp_path: Path) -> None:
        p = tmp_path / "t.txt"
        p.write_text("a\nb\n")
        r = subprocess.run(
            [sys.executable, "lc.py", str(p)],
            capture_output=True, text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["line_count"] == 2
        assert data["file"] == str(p)

    def test_missing_file(self) -> None:
        r = subprocess.run(
            [sys.executable, "lc.py", "/tmp/definitely-does-not-exist-12345.txt"],
            capture_output=True, text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 2
        data = json.loads(r.stdout)
        assert data["error"] == "file not found"

    def test_version(self) -> None:
        r = subprocess.run(
            [sys.executable, "lc.py", "--version"],
            capture_output=True, text=True,
            cwd=Path(__file__).parent.parent,
        )
        assert r.returncode == 0
        assert "lc 0.1.0" in r.stdout
