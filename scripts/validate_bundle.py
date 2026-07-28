#!/usr/bin/env python3
"""Validate a portable paper-review bundle without network access."""

from __future__ import annotations

import pathlib
import sys

from review_skill_validation import validate_bundle


def main(argv: list[str]) -> int:
    if len(argv) > 2:
        print("usage: python scripts/validate_bundle.py [repository-root]")
        return 1
    root = pathlib.Path(argv[1] if len(argv) == 2 else ".")
    errors = validate_bundle(root)
    if errors:
        for error in errors:
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

