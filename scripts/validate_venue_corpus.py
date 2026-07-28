#!/usr/bin/env python3
"""Validate evidence-graded venue corpus manifests offline."""

from __future__ import annotations

import json
import pathlib
import sys

try:
    from scripts.review_skill_validation import (
        validate_venue_corpus_document,
    )
except ModuleNotFoundError:
    from review_skill_validation import validate_venue_corpus_document


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python scripts/validate_venue_corpus.py MANIFEST [...]")
        return 2
    bundle_root = pathlib.Path(__file__).resolve().parents[1]
    errors: list[str] = []
    for raw_path in sys.argv[1:]:
        path = pathlib.Path(raw_path).resolve()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        errors.extend(
            validate_venue_corpus_document(
                value,
                bundle_root,
                path.as_posix(),
            )
        )
    if errors:
        for error in sorted(set(errors)):
            print(error)
        return 1
    print("venue corpus manifests validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
