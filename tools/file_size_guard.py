#!/usr/bin/env python3
"""Fail if any .py file exceeds 500 lines as per project rule.

Run in CI or locally: python tools/file_size_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[tuple[Path, int]] = []
    for path in root.rglob("*.py"):
        if any(p.startswith(".") for p in path.parts):
            continue
        # Ignore virtualenvs, caches, and tests for length
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("venv/", "env/", ".venv/", "__pycache__/", "tests/")):
            continue
        try:
            count = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
        except Exception:
            continue
        if count > 500:
            failures.append((path, count))
    if failures:
        print("Files exceeding 500 lines:")
        for path, count in failures:
            print(f" - {path}: {count} lines")
        return 1
    print("All source files within 500-line limit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

