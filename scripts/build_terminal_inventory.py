#!/usr/bin/env python3
"""Build a canonical terminal-task inventory from one run manifest."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from review_skill_validation import (
    validate_json_schema_document,
)


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


def build_inventory(run: dict, recorded_at: str) -> dict:
    delegation = run.get("delegation")
    if not isinstance(delegation, dict):
        raise ValueError("run manifest delegation must be an object")
    tasks = delegation.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("run manifest delegation.tasks must be an array")
    task_ids = [
        task.get("task_id")
        for task in tasks
        if isinstance(task, dict)
    ]
    if len(task_ids) != len(tasks) or any(
        not isinstance(task_id, str) or not task_id.strip()
        for task_id in task_ids
    ):
        raise ValueError("every delegated task must have a nonblank task_id")
    if len(set(task_ids)) != len(task_ids):
        raise ValueError("delegated task IDs must be unique")
    rows = []
    for task in sorted(tasks, key=lambda value: value["task_id"]):
        rows.append(
            {
                "task_id": task.get("task_id"),
                "agent_or_task_identifier":
                    task.get("agent_or_task_identifier"),
                "status": task.get("status"),
                "report_artifact": task.get("report_artifact"),
                "report_sha256": task.get("report_sha256"),
                "descendant_state": task.get("descendant_state"),
                "terminal_reason": task.get("terminal_reason"),
            }
        )
    return {
        "schema_version": "1.0.0",
        "receipt_kind": "delegation_terminal_inventory",
        "recorded_at": recorded_at,
        "run_id": run.get("run_id"),
        "tasks": rows,
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Print the canonical terminal-task inventory derived from one run "
            "manifest. The caller supplies the observation time explicitly."
        )
    )
    result.add_argument("--bundle-root", required=True)
    result.add_argument("--recorded-at", required=True)
    result.add_argument("run_manifest")
    return result


def main(argv: list[str]) -> int:
    args = parser().parse_args(argv[1:])
    root = pathlib.Path(args.bundle_root)
    try:
        run = load_json_object(pathlib.Path(args.run_manifest))
        inventory = build_inventory(run, args.recorded_at)
    except ValueError as exc:
        print(f"terminal-inventory: {exc}", file=sys.stderr)
        return 1
    errors = validate_json_schema_document(
        inventory,
        root,
        "schemas/runtime-evidence-receipt.schema.json",
        "delegation-terminal-inventory",
    )
    if errors:
        for error in sorted(set(errors)):
            print(error, file=sys.stderr)
        return 1
    sys.stdout.write(
        json.dumps(
            inventory,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
