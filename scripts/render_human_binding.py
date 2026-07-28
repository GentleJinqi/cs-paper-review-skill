#!/usr/bin/env python3
"""Render one complete deterministic human review view from JSON authority."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from review_skill_validation import (
    render_human_view,
    validate_finding_ledger,
    validate_json_schema_document,
)


ROLES = ("reviewer_report", "ae_assessment", "review_summary")
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
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-JSON numeric constant {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"{path.as_posix()}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.as_posix()}: top-level value must be an object")
    return value


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Print one complete deterministic human review view, including "
            "its canonical machine-binding block. Full run validation remains "
            "a separate final gate."
        )
    )
    result.add_argument("--bundle-root", required=True)
    result.add_argument("--role", required=True, choices=ROLES)
    result.add_argument("run_manifest")
    result.add_argument("finding_ledger")
    return result


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv[1:])
    root = pathlib.Path(args.bundle_root)
    try:
        run = load_json_object(pathlib.Path(args.run_manifest))
        ledger = load_json_object(pathlib.Path(args.finding_ledger))
    except ValueError as exc:
        print(f"human-binding: {exc}", file=sys.stderr)
        return 1
    errors = validate_json_schema_document(
        run,
        root,
        "schemas/run-manifest.schema.json",
        "run-manifest",
    )
    errors.extend(validate_finding_ledger(ledger, root))
    for field in ("run_id", "review_kind", "completion"):
        if run.get(field) != ledger.get(field):
            errors.append(f"human-binding: run/ledger {field} mismatch")
    if errors:
        for error in sorted(set(errors)):
            print(error, file=sys.stderr)
        return 1
    sys.stdout.write(render_human_view(args.role, run, ledger, root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
