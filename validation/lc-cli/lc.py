"""lc — count lines in a text file, emit JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

__version__ = "0.1.0"

CHUNK = 64 * 1024


def count_lines(path: str) -> int:
    """Count newline bytes in a file. Returns 0 for empty files.
    Counts final line without trailing newline as +1."""
    p = Path(path)
    total = 0
    has_content = False
    last_byte = b""
    with p.open("rb") as f:
        while chunk := f.read(CHUNK):
            has_content = True
            total += chunk.count(b"\n")
            last_byte = chunk[-1:]
    if has_content and last_byte != b"\n":
        total += 1
    return total


def format_result(file: str, count: int | None, error: str | None) -> str:
    if error is not None:
        return json.dumps({"file": file, "error": error}, ensure_ascii=False)
    return json.dumps({"file": file, "line_count": count}, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lc", description="Count lines in a text file, emit JSON."
    )
    parser.add_argument("path", help="File to count lines in")
    parser.add_argument("--version", action="version", version=f"lc {__version__}")
    args = parser.parse_args(argv)

    try:
        count = count_lines(args.path)
    except FileNotFoundError:
        print(format_result(args.path, None, "file not found"))
        return 2
    except PermissionError:
        print(format_result(args.path, None, "permission denied"))
        return 2
    except IsADirectoryError:
        print(format_result(args.path, None, "is a directory"))
        return 2

    print(format_result(args.path, count, None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
