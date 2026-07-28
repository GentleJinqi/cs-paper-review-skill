"""Validate public evaluation closure without exposing private evidence."""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any

_BUNDLE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(_BUNDLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BUNDLE_ROOT))

from scripts.review_skill_validation import validate_json_schema_document


def _safe_public_file(root: pathlib.Path, locator: Any) -> pathlib.Path:
    if (
        not isinstance(locator, str)
        or not locator
        or locator.startswith(("/", "\\"))
        or "\\" in locator
        or ".." in pathlib.PurePosixPath(locator).parts
    ):
        raise ValueError("locator is not canonical and relative")
    root = root.resolve()
    path = (root / locator).resolve()
    if path.parent == root or root in path.parents:
        if path.is_file() and not path.is_symlink():
            return path
    raise ValueError("locator is outside the evidence root or is not a file")


def validate_output_manifest(
    value: dict,
    bundle_root: pathlib.Path,
    evidence_root: pathlib.Path,
) -> list[str]:
    errors = validate_json_schema_document(
        value,
        pathlib.Path(bundle_root),
        "evals/output-manifest.schema.json",
        "evaluation output manifest",
    )
    if errors:
        return sorted(set(errors))
    artifact_ids: list[str] = []
    for item in value["outputs"]:
        artifact_ids.append(item["artifact_id"])
        if item["privacy"] == "private-reference":
            locator = item["locator"]
            if not locator.startswith("local-evidence-ref:") or any(
                token in locator for token in ("/", "\\", "..", "home")
            ):
                errors.append(
                    "output-manifest: private reference must use an opaque "
                    "local-evidence-ref token, never a filesystem path"
                )
            continue
        try:
            path = _safe_public_file(
                pathlib.Path(evidence_root), item["locator"]
            )
        except ValueError as exc:
            errors.append(f"output-manifest: {item['artifact_id']}: {exc}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            errors.append(
                f"output-manifest: {item['artifact_id']}: SHA-256 mismatch"
            )
    if len(artifact_ids) != len(set(artifact_ids)):
        errors.append("output-manifest: artifact IDs must be unique")
    return sorted(set(errors))


def validate_closure_record(
    value: dict,
    bundle_root: pathlib.Path,
) -> list[str]:
    errors = validate_json_schema_document(
        value,
        pathlib.Path(bundle_root),
        "evals/review-closure.schema.json",
        "evaluation closure",
    )
    if errors:
        return sorted(set(errors))
    if value["status"] == "pass" and not value["evidence_ids"]:
        errors.append(
            "evaluation-closure: passing closure requires bound evidence"
        )
    return sorted(set(errors))


def validate_semantic_adjudication(
    value: dict,
    bundle_root: pathlib.Path,
) -> list[str]:
    errors = validate_json_schema_document(
        value,
        pathlib.Path(bundle_root),
        "evals/semantic-adjudication.schema.json",
        "semantic adjudication",
    )
    if errors:
        return sorted(set(errors))

    fixtures = value["fixtures"]
    fixture_ids = [row["fixture_id"] for row in fixtures]
    if len(fixture_ids) != len(set(fixture_ids)):
        errors.append(
            "semantic-adjudication: fixture IDs must be unique"
        )
    manifest_path = (
        pathlib.Path(bundle_root) / "evals/fixtures/manifest.json"
    )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(
            f"semantic-adjudication: cannot load fixture manifest: {exc}"
        )
    else:
        expected_ids = [
            row["fixture_id"] for row in manifest.get("fixtures", [])
        ]
        if fixture_ids != expected_ids:
            errors.append(
                "semantic-adjudication: fixture order or coverage differs "
                "from the public manifest"
            )

    pass_count = 0
    required_count = 0
    matched_count = 0
    prohibited_count = 0
    for row in fixtures:
        required = row["required_matches"]
        oracle_ids = [item["oracle_finding_id"] for item in required]
        if len(oracle_ids) != len(set(oracle_ids)):
            errors.append(
                "semantic-adjudication: oracle finding IDs must be unique "
                f"within {row['fixture_id']}"
            )
        for item in required:
            matched_ids = item["matched_candidate_finding_ids"]
            if item["semantic_match"] is True and not matched_ids:
                errors.append(
                    "semantic-adjudication: a semantic match requires a "
                    f"candidate finding ID in {row['fixture_id']}"
                )
            if item["semantic_match"] is False and matched_ids:
                errors.append(
                    "semantic-adjudication: an unmatched obligation cannot "
                    f"claim candidate finding IDs in {row['fixture_id']}"
                )
        required_count += len(required)
        matched_count += sum(
            item["semantic_match"] is True for item in required
        )
        prohibited_count += len(row["prohibited_retained"])
        expected_pass = (
            all(item["semantic_match"] is True for item in required)
            and not row["prohibited_retained"]
            and not row["hard_expectation_failures"]
            and not row["other_hard_gate_failures"]
            and not row["oracle_contract_issues"]
        )
        expected_verdict = "pass" if expected_pass else "fail"
        if row["verdict"] != expected_verdict:
            errors.append(
                "semantic-adjudication: fixture verdict is inconsistent: "
                f"{row['fixture_id']}"
            )
        pass_count += expected_pass

    aggregate = value["aggregate"]
    expected_aggregate = {
        "fixture_count": len(fixtures),
        "pass_count": pass_count,
        "fail_count": len(fixtures) - pass_count,
        "required_obligation_count": required_count,
        "matched_obligation_count": matched_count,
        "prohibited_retained_count": prohibited_count,
    }
    if aggregate != expected_aggregate:
        errors.append(
            "semantic-adjudication: aggregate counts are inconsistent"
        )
    expected_overall = (
        "pass" if pass_count == len(fixtures) else "fail"
    )
    if value["overall_verdict"] != expected_overall:
        errors.append(
            "semantic-adjudication: overall verdict is inconsistent"
        )
    return sorted(set(errors))


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python evals/validate_closure.py RECORD [...]")
        return 2
    bundle_root = pathlib.Path(__file__).resolve().parents[1]
    errors: list[str] = []
    for raw in sys.argv[1:]:
        path = pathlib.Path(raw).resolve()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        errors.extend(validate_closure_record(value, bundle_root))
    if errors:
        for error in sorted(set(errors)):
            print(error)
        return 1
    print("evaluation closure records validate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
