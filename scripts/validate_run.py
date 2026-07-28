#!/usr/bin/env python3
"""Validate one run-manifest/finding-ledger pair without network access."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from review_skill_validation import load_review_coverage, validate_run_pair


def load_json_object(path: pathlib.Path) -> dict:
    def no_duplicates(pairs: list[tuple[str, object]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate object key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=no_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{path.as_posix()}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.as_posix()}: top-level value must be an object")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        usage=(
            "python scripts/validate_run.py --bundle-root ROOT "
            "RUN_MANIFEST FINDING_LEDGER"
        )
    )
    result.add_argument("--bundle-root", required=True)
    result.add_argument("run_manifest")
    result.add_argument("finding_ledger")
    return result


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv[1:])
    root = pathlib.Path(args.bundle_root)
    try:
        run = load_json_object(pathlib.Path(args.run_manifest))
        ledger = load_json_object(pathlib.Path(args.finding_ledger))
        coverage = load_review_coverage(root)
        errors = validate_run_pair(run, ledger, coverage, root)
    except ValueError as exc:
        errors = [f"run-validation: {exc}"]
    if errors:
        for error in sorted(set(errors)):
            print(error)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
