from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

from scripts.review_skill_validation import (
    _contains_count_based_confidence,
    _contains_non_execution_claim,
    _contains_positive_acceptance_prediction,
    _validate_human_output,
    _validate_task_dependency_chronology,
    adapter_payload_sha256,
    compatibility_payload_sha256,
    human_machine_binding,
    load_adapter_manifest,
    load_adapter_promotion,
    load_review_coverage,
    render_human_view,
    stable_finding_id,
    validate_adapter_manifest,
    validate_adapter_promotion,
    validate_finding_ledger,
    validate_json_schema_document,
    validate_run_manifest,
    validate_run_pair,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
HEX_A = "a" * 64
HEX_B = "b" * 64
MAPPING = {
    "minimal-settled-set": "adapters/codex/candidates/minimal-settled-set.md",
    "persisted-task-registry":
        "adapters/codex/candidates/persisted-task-registry.md",
}


def canonical_bytes(data: dict) -> bytes:
    return (
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(data))


def coverage_fixture() -> dict:
    return json.loads(
        (ROOT / "references/review-coverage.json").read_text(encoding="utf-8")
    )


def coverage_digest(data: dict) -> str:
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def make_bundle(
    root: pathlib.Path,
    *,
    selected: str | None = None,
    promotion_result: str = "pass",
    promotion_decision: str = "selected",
) -> tuple[dict, dict | None]:
    shutil.copytree(ROOT / "schemas", root / "schemas", dirs_exist_ok=True)
    shutil.copytree(ROOT / "scripts", root / "scripts", dirs_exist_ok=True)
    shutil.copytree(ROOT / "templates", root / "templates", dirs_exist_ok=True)
    shutil.copytree(ROOT / "agents", root / "agents", dirs_exist_ok=True)
    shutil.copytree(ROOT / "evals", root / "evals", dirs_exist_ok=True)
    (root / "references").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "SKILL.md", root / "SKILL.md")
    for relative in (
        "references/scientific-core.md",
        "references/review-coverage.md",
        "references/review-workflow.md",
        "references/finding-contract.md",
        "references/delta-review.md",
        "references/privacy-and-authorisation.md",
    ):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    files = {
        "adapters/codex-gpt-5.6-sol-ultra.md": "adapter\n",
        "adapters/codex/agents/cs-paper-reviewer.toml": "reviewer\n",
        "adapters/codex/agents/cs-paper-ae.toml": "ae\n",
        MAPPING["minimal-settled-set"]: "minimal candidate\n",
        MAPPING["persisted-task-registry"]: "persisted candidate\n",
    }
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    active_files = [
        "adapters/codex-gpt-5.6-sol-ultra.md",
        "adapters/codex/agents/cs-paper-reviewer.toml",
        "adapters/codex/agents/cs-paper-ae.toml",
    ]
    selected_path = MAPPING[selected] if selected else None
    if selected_path:
        active_files.append(selected_path)

    coverage = coverage_fixture()
    write_json(root / "references/review-coverage.json", coverage)
    registry_path = root / "references/venue-authorities.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "references/venue-authorities.json",
        registry_path,
    )
    shutil.copy2(
        ROOT / "references/adapter-evaluation-authority.json",
        root / "references/adapter-evaluation-authority.json",
    )

    manifest = {
        "schema_version": "1.0.0",
        "selected_candidate_id": selected,
        "selected_lifecycle_implementation": selected_path,
        "promotion_record_locator":
            "compatibility/adapter-promotion.json" if selected else None,
        "promotion_record_sha256": None,
        "candidate_implementations": dict(MAPPING),
        "active_files": active_files,
        "adapter_payload_sha256": "",
        "compatibility_payload_sha256": "",
    }
    write_json(root / "adapters/codex/adapter-manifest.json", manifest)
    manifest["adapter_payload_sha256"] = adapter_payload_sha256(root)
    manifest["compatibility_payload_sha256"] = compatibility_payload_sha256(root)
    write_json(root / "adapters/codex/adapter-manifest.json", manifest)

    promotion = None
    if selected:
        fixture_manifest_locator = "evals/adapter-fixtures/manifest.json"
        fixture_manifest_path = root / fixture_manifest_locator
        fixture_manifest = json.loads(
            fixture_manifest_path.read_text(encoding="utf-8")
        )
        fixture_rows = fixture_manifest["fixtures"]
        fixture_manifest_sha = hashlib.sha256(
            fixture_manifest_path.read_bytes()
        ).hexdigest()
        candidate_evaluations = []
        executor_ids = []
        runner_locator = "scripts/adapter_evaluation_scorer.py"
        runner_sha256 = hashlib.sha256(
            (root / runner_locator).read_bytes()
        ).hexdigest()
        for candidate_id in MAPPING:
            candidate_sha = hashlib.sha256(
                (root / MAPPING[candidate_id]).read_bytes()
            ).hexdigest()
            case_rows = []
            execution_cases = []
            for fixture in fixture_rows:
                fixture_id = fixture["fixture_id"]
                dimension = fixture["dimension"]
                case_result = (
                    "fail"
                    if candidate_id == selected
                    and promotion_result == "fail"
                    and dimension == "quality"
                    else "pass"
                )
                output_locator = (
                    f"compatibility/{candidate_id}/{fixture_id}-output.json"
                )
                output_path = root / output_locator
                oracle = json.loads(
                    (root / fixture["oracle_locator"]).read_text(
                        encoding="utf-8"
                    )
                )
                write_json(
                    output_path,
                    {
                        "schema_version": "1.0.0",
                        "fixture_id": fixture_id,
                        "dimension": dimension,
                        "candidate_id": candidate_id,
                        "observations": [
                            {
                                "assertion_id": assertion["assertion_id"],
                                "observed": (
                                    assertion["expected"]
                                    if not (
                                        case_result == "fail" and index == 0
                                    )
                                    else not assertion["expected"]
                                ),
                                "evidence":
                                    "Bounded candidate observation retained "
                                    "by the evaluation harness.",
                            }
                            for index, assertion in enumerate(
                                oracle["assertions"]
                            )
                        ],
                    },
                )
                output_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
                case_rows.append(
                    {
                        "fixture_id": fixture_id,
                        "dimension": dimension,
                        "result": case_result,
                        "output_locator": output_locator,
                        "output_sha256": output_sha,
                    }
                )
                execution_cases.append(
                    {
                        "fixture_id": fixture_id,
                        "input_locator": fixture["input_locator"],
                        "input_sha256": fixture["input_sha256"],
                        "oracle_locator": fixture["oracle_locator"],
                        "oracle_sha256": fixture["oracle_sha256"],
                        "output_locator": output_locator,
                        "output_sha256": output_sha,
                        "result": case_result,
                    }
                )
            quality_result = (
                "pass"
                if all(
                    case["result"] == "pass"
                    for case in case_rows
                    if case["dimension"] == "quality"
                )
                else "fail"
            )
            lifecycle_result = (
                "pass"
                if all(
                    case["result"] == "pass"
                    for case in case_rows
                    if case["dimension"] == "lifecycle"
                )
                else "fail"
            )
            report_locator = (
                f"compatibility/{candidate_id}/evaluation-report.json"
            )
            report_path = root / report_locator
            write_json(
                report_path,
                {
                    "schema_version": "1.0.0",
                    "fixture_set": "forward-v1",
                    "candidate_id": candidate_id,
                    "candidate_implementation_sha256": candidate_sha,
                    "adapter_sha256": manifest["adapter_payload_sha256"],
                    "compatibility_payload_sha256":
                        manifest["compatibility_payload_sha256"],
                    "evaluated_at": "2026-07-28T12:15:00Z",
                    "runner": "codex-evaluation-harness",
                    "runner_locator": runner_locator,
                    "runner_sha256": runner_sha256,
                    "runner_version": "1.0.0",
                    "quality_result": quality_result,
                    "lifecycle_result": lifecycle_result,
                    "cases": case_rows,
                },
            )
            report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
            executor_id = f"executor-{candidate_id}"
            executor_ids.append(executor_id)
            execution_locator = (
                f"compatibility/{candidate_id}/execution-receipt.json"
            )
            execution_path = root / execution_locator
            write_json(
                execution_path,
                {
                    "schema_version": "1.0.0",
                    "receipt_kind": "adapter_candidate_execution",
                    "execution_id": f"exec-{candidate_id}",
                    "executed_at": "2026-07-28T12:10:00Z",
                    "candidate_id": candidate_id,
                    "candidate_implementation_sha256": candidate_sha,
                    "adapter_sha256": manifest["adapter_payload_sha256"],
                    "compatibility_payload_sha256":
                        manifest["compatibility_payload_sha256"],
                    "executor": {
                        "executor_id": executor_id,
                        "requested_model": "gpt-5.6-sol",
                        "requested_mode": "ultra",
                        "configuration_state": "requested_and_recorded",
                        "effective_telemetry": "not_surfaced",
                        "resolved_model": None,
                        "resolved_mode": None,
                        "role": "candidate_executor",
                    },
                    "runner": "codex-evaluation-harness",
                    "runner_locator": runner_locator,
                    "runner_sha256": runner_sha256,
                    "runner_version": "1.0.0",
                    "fixture_set": "forward-v1",
                    "fixture_manifest_locator": fixture_manifest_locator,
                    "fixture_manifest_sha256": fixture_manifest_sha,
                    "evaluation_report_locator": report_locator,
                    "evaluation_report_sha256": report_sha,
                    "status": "completed",
                    "execution_performed": True,
                    "raw_output_produced": True,
                    "oracle_access_record":
                        "declared_withheld_until_output_frozen",
                    "oracle_boundary_verification":
                        "dispatch_snapshot_excludes_oracle",
                    "dispatch_input_snapshot_sha256": hashlib.sha256(
                        canonical_bytes(
                            {
                                "schema_version": "1.0.0",
                                "candidate_id": candidate_id,
                                "candidate_implementation_sha256":
                                    candidate_sha,
                                "inputs": [
                                    {
                                        "fixture_id":
                                            fixture["fixture_id"],
                                        "input_locator":
                                            fixture["input_locator"],
                                        "input_sha256":
                                            fixture["input_sha256"],
                                    }
                                    for fixture in fixture_rows
                                ],
                            }
                        )
                    ).hexdigest(),
                    "cases": [
                        {
                            key: (
                                "2026-07-28T12:05:00Z"
                                if key == "output_frozen_at"
                                else value
                            )
                            for key, value in {
                                **case,
                                "output_frozen_at": None,
                            }.items()
                            if key not in {
                                "oracle_locator",
                                "oracle_sha256",
                            }
                        }
                        for case in execution_cases
                    ],
                    "limitations": [
                        "The receipt records configured controls; host telemetry "
                        "is not asserted."
                    ],
                },
            )
            execution_sha = hashlib.sha256(
                execution_path.read_bytes()
            ).hexdigest()
            candidate_evaluations.append(
                {
                    "candidate_id": candidate_id,
                    "candidate_implementation_sha256": candidate_sha,
                    "execution_receipt_locator": execution_locator,
                    "execution_receipt_sha256": execution_sha,
                    "evaluation_report_locator": report_locator,
                    "evaluation_report_sha256": report_sha,
                    "quality_result": quality_result,
                    "lifecycle_result": lifecycle_result,
                }
            )
        semantic_candidate_evaluations = [
            {
                key: row[key]
                for key in (
                    "candidate_id",
                    "candidate_implementation_sha256",
                    "execution_receipt_locator",
                    "execution_receipt_sha256",
                    "evaluation_report_locator",
                    "evaluation_report_sha256",
                )
            }
            for row in candidate_evaluations
        ]
        dimensions = [
            "compaction_recovery",
            "late_result_handling",
            "duplicate_dispatch",
            "evidence_retention",
            "complexity",
            "review_quality",
        ]
        semantic_review = {
            "schema_version": "1.0.0",
            "receipt_kind": "adapter_semantic_review",
            "review_id": "SEM-2026-001",
            "reviewed_at": "2026-07-28T12:30:00Z",
            "reviewer": {
                "reviewer_id": "independent-semantic-reviewer",
                "requested_model": "gpt-5.6-sol",
                "requested_mode": "ultra",
                "configuration_state": "requested_and_recorded",
                "effective_telemetry": "not_surfaced",
                "resolved_model": None,
                "resolved_mode": None,
                "independent": True,
            },
            "independent_review_performed": True,
            "executor_ids": executor_ids,
            "fixture_set": "forward-v1",
            "fixture_manifest_locator": fixture_manifest_locator,
            "fixture_manifest_sha256": fixture_manifest_sha,
            "candidate_evaluations": semantic_candidate_evaluations,
            "dimensions": [
                {
                    "dimension": dimension,
                    "assessments": [
                        {
                            "candidate_id": candidate_id,
                            "rating":
                                "preferred"
                                if candidate_id == selected
                                else "acceptable",
                            "evidence":
                                "The independent comparison inspected bound "
                                "outputs and lifecycle traces.",
                        }
                        for candidate_id in MAPPING
                    ],
                    "preferred_candidate_id": selected,
                }
                for dimension in dimensions
            ],
            "selected_candidate_id": selected,
            "verdict": "selected",
            "selection_rule": "strict_preference_majority",
            "rationale":
                "The selected candidate best preserves evidence and lifecycle "
                "completion across the bounded comparison.",
            "limitations": [
                "This comparison supports adapter selection, not paper acceptance."
            ],
        }
        semantic_review_locator = "compatibility/semantic-review.json"
        semantic_review_path = root / semantic_review_locator
        write_json(semantic_review_path, semantic_review)
        selected_evaluation = next(
            row
            for row in candidate_evaluations
            if row["candidate_id"] == selected
        )
        promotion = {
            "schema_version": "1.0.0",
            "record_id": "AP-2026-001",
            "evaluated_at": "2026-07-28T13:00:00Z",
            "candidate_id": selected,
            "adapter_sha256": manifest["adapter_payload_sha256"],
            "compatibility_payload_sha256":
                manifest["compatibility_payload_sha256"],
            "result": promotion_result,
            "promotion_decision": promotion_decision,
            "evaluation_summary": {
                "fixture_set": "forward-v1",
                "fixture_manifest_locator": fixture_manifest_locator,
                "fixture_manifest_sha256": fixture_manifest_sha,
                "candidate_evaluations": candidate_evaluations,
                "semantic_review_locator": semantic_review_locator,
                "semantic_review_sha256": hashlib.sha256(
                    semantic_review_path.read_bytes()
                ).hexdigest(),
                "quality_result": selected_evaluation["quality_result"],
                "lifecycle_result": selected_evaluation["lifecycle_result"],
            },
        }
        promotion_path = root / "compatibility/adapter-promotion.json"
        write_json(promotion_path, promotion)
        manifest["promotion_record_sha256"] = hashlib.sha256(
            promotion_path.read_bytes()
        ).hexdigest()
        write_json(root / "adapters/codex/adapter-manifest.json", manifest)
    return manifest, promotion


def persist_promotion(root: pathlib.Path, promotion: dict) -> None:
    promotion_path = root / "compatibility/adapter-promotion.json"
    write_json(promotion_path, promotion)
    manifest_path = root / "adapters/codex/adapter-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["promotion_record_sha256"] = hashlib.sha256(
        promotion_path.read_bytes()
    ).hexdigest()
    write_json(manifest_path, manifest)


def sync_semantic_promotion_bindings(
    root: pathlib.Path,
    promotion: dict,
) -> None:
    summary = promotion["evaluation_summary"]
    semantic_path = root / summary["semantic_review_locator"]
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    semantic["candidate_evaluations"] = [
        {
            key: row[key]
            for key in (
                "candidate_id",
                "candidate_implementation_sha256",
                "execution_receipt_locator",
                "execution_receipt_sha256",
                "evaluation_report_locator",
                "evaluation_report_sha256",
            )
        }
        for row in summary["candidate_evaluations"]
    ]
    write_json(semantic_path, semantic)
    summary["semantic_review_sha256"] = hashlib.sha256(
        semantic_path.read_bytes()
    ).hexdigest()
    persist_promotion(root, promotion)


_RUN_RECORD_EVIDENCE = {
    "RC-AUTHORISATION": "authorisation",
    "RC-INPUT-LINEAGE": "input_artifacts",
    "RC-CRITERIA-AUTHORITY": "venue_profile",
    "RC-COVERAGE-ACCOUNTING": "coverage",
    "RC-DEDUP-DISPOSITION": "finding_ledger",
    "RC-DISSENT-PRESERVATION": "finding_ledger",
    "RC-REQUIREMENT-LEGITIMACY": "finding_ledger",
    "RC-RISK-CLASS-SEPARATION": "finding_ledger",
    "RC-COMPLETION-TRUTH": "completion",
    "RC-LEDGER-CONSISTENCY": "finding_ledger",
}

RESOLUTION_EXCERPT = (
    "The revised scope statement is limited to the single evaluated domain."
)


def criterion_excerpt(criterion_id: str) -> str:
    return (
        f"EVIDENCE {criterion_id}: bounded synthetic observation for this "
        "criterion."
    )


def fixture_source_text(coverage: dict) -> str:
    return (
        "\\title{Synthetic Review Fixture}\n"
        "\\section{Introduction}\n"
        "The headline claim covers unseen domains while the reported "
        "experiment covers one domain.\n"
        f"{RESOLUTION_EXCERPT}\n"
        + "\n".join(
            criterion_excerpt(row["criterion_id"])
            for row in coverage["criteria"]
            if row["criterion_id"] != "RC-DELTA-LINEAGE"
            and row["criterion_id"] not in _RUN_RECORD_EVIDENCE
            and row["criterion_id"]
            not in {
                "RC-INPUT-ALIGNMENT",
                "RC-INPUT-VERIFIABILITY",
                "RC-VISUAL-INTEGRITY",
            }
        )
        + "\n"
    )


def exact_span_fields(excerpt: str, source_text: str) -> dict:
    source = source_text.encode("utf-8")
    target = excerpt.encode("utf-8")
    offsets: list[int] = []
    cursor = 0
    while cursor <= len(source) - len(target):
        offset = source.find(target, cursor)
        if offset < 0:
            break
        offsets.append(offset)
        cursor = offset + 1
    if not offsets:
        raise AssertionError("fixture excerpt is absent from source")
    start = offsets[0]
    end = start + len(target)
    return {
        "source_anchor": f"bytes:{start}-{end};occurrence:1",
        "start_byte": start,
        "end_byte": end,
        "occurrence": 1,
    }


def minimal_valid_pdf(
    revision_text: str = RESOLUTION_EXCERPT,
    *,
    variant_marker: str | None = None,
) -> bytes:
    """Return a deterministic one-page text PDF accepted by Poppler."""

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    if variant_marker is not None:
        header += (
            f"% fixture-variant:{variant_marker}\n"
        ).encode("ascii")
    revision_literal = (
        revision_text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("ascii")
    )
    stream = (
        b"BT\n/F1 14 Tf\n72 740 Td\n"
        b"(Synthetic Review Fixture) Tj\n"
        b"0 -24 Td\n/F1 12 Tf\n(Introduction) Tj\n"
        b"0 -20 Td\n"
        b"(The headline claim covers unseen domains while the reported "
        b"experiment covers one domain.) Tj\n"
        b"0 -20 Td\n("
        + revision_literal
        + b") Tj\nET\n"
    )
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
            b"/MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> "
            b"/Contents 4 0 R >>\nendobj\n"
        ),
        (
            f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream\nendobj\n"
        ),
        (
            b"5 0 obj\n<< /Type /Font /Subtype /Type1 "
            b"/BaseFont /Helvetica >>\nendobj\n"
        ),
    ]
    body = bytearray(header)
    offsets = [0]
    for item in objects:
        offsets.append(len(body))
        body.extend(item)
    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    body.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    body.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(body)


def coverage_evidence(
    criterion_id: str,
    *,
    source_text: str,
    rendered_receipt: tuple[str, str] | None = None,
) -> dict:
    if criterion_id in _RUN_RECORD_EVIDENCE:
        subject = _RUN_RECORD_EVIDENCE[criterion_id]
        return {
            "artifact_id": f"run:{subject}",
            "source_anchor": f"run-manifest:{subject}",
            "semantic_anchor": f"criterion:{criterion_id}",
            "observation": "The canonical run record was inspected.",
            "evidence_kind": "run_record",
            "verification_method": "canonical_run_field",
            "excerpt": None,
            "excerpt_sha256": None,
        }
    if criterion_id in {"RC-INPUT-ALIGNMENT", "RC-INPUT-VERIFIABILITY"}:
        return {
            "artifact_id": "alignment:source-pdf",
            "source_anchor": "alignment-receipt:checks",
            "semantic_anchor": f"criterion:{criterion_id}",
            "observation": "The byte-bound alignment receipt was inspected.",
            "evidence_kind": "alignment_receipt",
            "verification_method": "alignment_receipt",
            "excerpt": None,
            "excerpt_sha256": None,
        }
    if criterion_id == "RC-VISUAL-INTEGRITY":
        if rendered_receipt is None:
            raise AssertionError("rendered coverage requires a receipt")
        receipt_locator, receipt_sha256 = rendered_receipt
        return {
            "artifact_id": "paper-pdf",
            "source_anchor": f"rendered:{receipt_locator}#page=1",
            "semantic_anchor": f"criterion:{criterion_id}",
            "observation": "The matched frozen rendering was inspected.",
            "evidence_kind": "rendered",
            "verification_method": "rendered_receipt",
            "excerpt": None,
            "excerpt_sha256": None,
            "rendered_receipt_locator": receipt_locator,
            "rendered_receipt_sha256": receipt_sha256,
        }
    excerpt = criterion_excerpt(criterion_id)
    evidence = {
        "artifact_id": "paper-source",
        "semantic_anchor": f"criterion:{criterion_id}",
        "observation": "The bounded source excerpt was inspected.",
        "evidence_kind": "text_exact",
        "verification_method": "utf8_exact_excerpt",
        "excerpt": excerpt,
        "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
    }
    evidence.update(exact_span_fields(excerpt, source_text))
    return evidence


def coverage_rows(
    coverage: dict,
    *,
    rendered_receipt: tuple[str, str],
) -> list[dict]:
    source_text = fixture_source_text(coverage)
    rows: list[dict] = []
    for row in coverage["criteria"]:
        delta_not_applicable = row["criterion_id"] == "RC-DELTA-LINEAGE"
        rows.append({
            "criterion_id": row["criterion_id"],
            "applicability":
                "inapplicable" if delta_not_applicable else "applicable",
            "disposition":
                "not_applicable"
                if delta_not_applicable
                else "assessed_no_finding",
            "evidence":
                []
                if delta_not_applicable
                else [
                    coverage_evidence(
                        row["criterion_id"],
                        source_text=source_text,
                        rendered_receipt=rendered_receipt,
                    )
                ],
            "stage_id": row["primary_stage_owner"],
            "task_ids": [],
            "finding_ids": [],
            "rationale":
                "Initial review has no prior ledger."
                if delta_not_applicable
                else "Evidence inspected; no material defect found.",
        })
    return rows


def run_coverage_row(run: dict, criterion_id: str) -> dict:
    return next(
        row
        for row in run["coverage"]["criteria"]
        if row["criterion_id"] == criterion_id
    )


def write_venue_source_evidence(
    root: pathlib.Path,
    *,
    source_url: str,
    statement: str,
    native_fields: list[dict],
) -> tuple[str, str]:
    criterion_excerpt = (
        "Assess soundness under the venue guidance and explain the venue "
        "assessment."
    )
    claims = [
        {
            "claim_id": "criterion:venue-soundness",
            "claim_kind": "criterion",
            "projection_basis": "source_bounded_interpretation",
            "projection": {
                "rule_id": "venue-soundness",
                "statement": statement,
            },
            "excerpt_ids": ["criterion-venue-soundness"],
            "support_terms": ["soundness", "venue"],
        }
    ]
    verbatim_excerpts = [
        {
            "excerpt_id": "criterion-venue-soundness",
            "source_locator": "Fixture reviewer form > Review criteria",
            "text": criterion_excerpt,
            "sha256": hashlib.sha256(
                criterion_excerpt.encode("utf-8")
            ).hexdigest(),
        }
    ]
    claims.extend(
        {
            "claim_id": f"native:{field['field_id']}",
            "claim_kind": "native_field",
            "projection_basis": "source_bounded_native_semantics",
            "projection": {
                key: field.get(key)
                for key in (
                    "field_id",
                    "role",
                    "field_type",
                    "minimum",
                    "maximum",
                    "allowed_labels",
                    "anchors",
                    "direction",
                )
            },
            "excerpt_ids": [f"native-{field['field_id']}"],
            "support_terms": [
                str(field["field_id"]),
                str(field["field_type"]),
            ],
        }
        for field in native_fields
    )
    for field in native_fields:
        field_id = str(field["field_id"])
        source_parts = [
            f"The official {field_id} field is a "
            f"{field['field_type']} for the {field['role']}."
        ]
        if field.get("field_type") == "categorical":
            source_parts.append(
                "Allowed values: "
                + ", ".join(str(item) for item in field["allowed_labels"])
                + "."
            )
        elif field.get("field_type") in {"integer_scale", "numeric_scale"}:
            source_parts.append(
                f"The scale runs from {field.get('minimum')} to "
                f"{field.get('maximum')}."
            )
            source_parts.extend(
                f"{anchor.get('value')}: {anchor.get('label')}."
                for anchor in field.get("anchors", [])
                if isinstance(anchor, dict)
            )
        native_excerpt = " ".join(source_parts)
        verbatim_excerpts.append(
            {
                "excerpt_id": f"native-{field_id}",
                "source_locator":
                    f"Fixture reviewer form > {field_id}",
                "text": native_excerpt,
                "sha256": hashlib.sha256(
                    native_excerpt.encode("utf-8")
                ).hexdigest(),
            }
        )
    capture_text = "\n\n".join(
        excerpt["text"] for excerpt in verbatim_excerpts
    )
    for excerpt in verbatim_excerpts:
        span = exact_span_fields(excerpt["text"], capture_text)
        excerpt["capture_start_byte"] = span["start_byte"]
        excerpt["capture_end_byte"] = span["end_byte"]
        excerpt["capture_occurrence"] = span["occurrence"]
    capture_locator, capture_sha = write_receipt(
        root,
        "venues/source-captures/icml-2026-reviewer-instructions.json",
        {
            "schema_version": "1.0.0",
            "source_id": "reviewer-instructions",
            "url": source_url,
            "captured_at": "2026-07-28T12:00:00Z",
            "capture_method": "manual_browser_visible_text",
            "capture_scope": "bounded_official_excerpts_not_full_page",
            "captured_text": capture_text,
        },
    )
    return write_receipt(
        root,
        "venues/source-evidence/icml-2026-reviewer-instructions.json",
        {
            "schema_version": "1.0.0",
            "source_id": "reviewer-instructions",
            "url": source_url,
            "title": "ICML 2026 Reviewer Instructions",
            "retrieved_at": "2026-07-28T12:00:00Z",
            "capture_locator": capture_locator,
            "capture_sha256": capture_sha,
            "sections": [
                {
                    "section_anchor": "review-criteria",
                    "extracted_fact":
                        "The official instructions define criteria that "
                        "reviewers must assess and justify.",
                    "source_verification": {
                        "status": "verified",
                        "method": "manual_browser_text_comparison",
                        "verified_at": "2026-07-28T12:00:00Z",
                        "semantic_projection_review":
                            "human_release_reviewed",
                        "offline_nonclaim":
                            "does_not_attest_live_official_page_truth",
                    },
                    "verbatim_excerpts": verbatim_excerpts,
                    "claims": claims,
                }
            ],
        },
    )


def install_icml_venue_profile(
    root: pathlib.Path,
    run: dict,
    *,
    evidence_root: pathlib.Path,
    source_url: str = "https://icml.cc/Conferences/2026/ReviewerInstructions",
    statement: str = "Assess soundness under the venue guidance.",
    native_fields: list[dict] | None = None,
) -> None:
    prepared_native_fields = copy.deepcopy(native_fields or [])
    for field in prepared_native_fields:
        field.setdefault(
            "portable_criterion_ids",
            ["RC-CLAIM-EVIDENCE"],
        )
        field.setdefault(
            "source_anchors",
            [
                {
                    "source_id": "reviewer-instructions",
                    "section_anchor": "review-criteria",
                }
            ],
        )
        field.setdefault(
            "direction",
            "not_applicable"
            if field.get("field_type") == "text"
            else (
                "not_ordered"
                if field.get("field_type") == "categorical"
                else "higher_better"
            ),
        )
    registry_path = root / "references/venue-authorities.json"
    content_locator, content_sha = write_venue_source_evidence(
        root,
        source_url=source_url,
        statement=statement,
        native_fields=prepared_native_fields,
    )
    source_manifest = {
        "schema_version": "1.0.0",
        "venue": "ICML",
        "year": 2026,
        "track": "main",
        "authority": "official-first-party",
        "authority_registry_locator": "references/venue-authorities.json",
        "authority_registry_id": "venue-authority-registry-v1",
        "retrieved_at": "2026-07-28T12:00:00Z",
        "sources": [
            {
                "source_id": "reviewer-instructions",
                "authority": "first_party",
                "url": source_url,
                "content_locator": content_locator,
                "content_sha256": content_sha,
                "title": "ICML 2026 Reviewer Instructions",
                "retrieved_section_anchors": ["review-criteria"],
            }
        ],
    }
    source_locator, source_sha = write_receipt(
        root,
        "venues/source-manifests/icml-2026-main.json",
        source_manifest,
    )
    profile = {
        "schema_version": "1.0.0",
        "profile_id": "icml-2026-main-v1",
        "profile_version": "1.0.0",
        "venue": "ICML",
        "year": 2026,
        "track": "main",
        "source_manifest_locator": source_locator,
        "source_sha256": source_sha,
        "criteria": [
            {
                "rule_id": "venue-soundness",
                "statement": statement,
                "portable_criterion_ids": ["RC-CLAIM-EVIDENCE"],
                "source_ids": ["reviewer-instructions"],
                "source_anchors": [
                    {
                        "source_id": "reviewer-instructions",
                        "section_anchor": "review-criteria",
                    }
                ],
                "source_claim_ids": ["criterion:venue-soundness"],
            }
        ],
        "native_assessment_fields": prepared_native_fields,
    }
    for field in profile["native_assessment_fields"]:
        field["source_claim_ids"] = [f"native:{field['field_id']}"]
    profile_locator, profile_sha = write_receipt(
        root,
        "venues/profiles/icml-2026-main.json",
        profile,
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_row = next(
        row
        for row in registry["venues"]
        if row["venue"] == "ICML"
    )
    registry_row["profiles"] = [
        {
            "profile_id": profile["profile_id"],
            "profile_version": profile["profile_version"],
            "year": profile["year"],
            "track": profile["track"],
            "profile_locator": profile_locator,
            "profile_sha256": profile_sha,
            "source_manifest_locator": source_locator,
            "source_sha256": source_sha,
        }
    ]
    write_json(registry_path, registry)

    manifest_path = root / "adapters/codex/adapter-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compatibility_payload_sha256"] = (
        compatibility_payload_sha256(root)
    )
    write_json(manifest_path, manifest)
    runtime = run["runtime_profile"]
    runtime["compatibility_payload_sha256"] = (
        manifest["compatibility_payload_sha256"]
    )
    if runtime["compatibility_claim"] in {
        "evaluation_pending",
        "configured-and-evaluated",
        "runtime-attested",
    }:
        proof, model_validation, mode_validation, _ = (
            configured_subject_evidence(
                evidence_root,
                subject_kind="root",
                subject_id=run["run_id"],
                configuration_source=runtime["configuration_source"],
                proof_kind=runtime["configuration_proof"]["proof_kind"],
                adapter_sha256=runtime["adapter_sha256"],
                compatibility_payload_sha256=
                    runtime["compatibility_payload_sha256"],
                selected_candidate_id=runtime["selected_candidate_id"],
                promotion_record_sha256=
                    runtime["promotion_record_sha256"],
            )
        )
        runtime["configuration_proof"] = proof
        runtime["model_validation"] = model_validation
        runtime["mode_validation"] = mode_validation
    run["target"] = {
        "venue": "ICML",
        "year": 2026,
        "track": "main",
    }
    run["venue_profile"] = {
        "status": "loaded",
        "profile_id": profile["profile_id"],
        "profile_version": profile["profile_version"],
        "venue": "ICML",
        "year": 2026,
        "track": "main",
        "profile_locator": profile_locator,
        "profile_sha256": profile_sha,
        "source_manifest_locator": source_locator,
        "source_sha256": source_sha,
        "blocked_reason": None,
    }
    mapped_finding_ids = sorted(
        {
            finding_id
            for rule in profile["criteria"]
            for criterion_id in rule["portable_criterion_ids"]
            for finding_id in run_coverage_row(
                run,
                criterion_id,
            ).get("finding_ids", [])
        }
    )
    native_results = []
    for field in profile["native_assessment_fields"]:
        field_type = field["field_type"]
        if field_type == "categorical":
            value = field["allowed_labels"][0]
        elif field_type in {"integer_scale", "numeric_scale"}:
            value = field["minimum"]
        else:
            value = "Evidence-bounded venue assessment."
        reported_in = (
            ["reviewer_report", "ae_assessment", "review_summary"]
            if field["role"] == "reviewer"
            else ["ae_assessment", "review_summary"]
        )
        native_results.append(
            {
                "field_id": field["field_id"],
                "role": field["role"],
                "status": "provided",
                "value": value,
                "rationale": "The value follows the loaded venue profile.",
                "basis": {
                    "kind": "bounded_judgement",
                    "criterion_ids": field["portable_criterion_ids"],
                    "finding_ids": [
                        finding_id
                        for criterion_id in field["portable_criterion_ids"]
                        for finding_id in run_coverage_row(
                            run,
                            criterion_id,
                        ).get("finding_ids", [])
                    ],
                },
                "reported_in": reported_in,
            }
        )
    run["venue_assessment"] = {
        "status": "completed",
        "profile_id": profile["profile_id"],
        "criteria": [
            {
                "rule_id": rule["rule_id"],
                "assessment":
                    "concern" if mapped_finding_ids else "satisfied",
                "evidence": [
                    {
                        "reference_kind":
                            "finding"
                            if mapped_finding_ids
                            else "coverage_evidence",
                        "criterion_id": rule["portable_criterion_ids"][0],
                        "evidence_index":
                            None if mapped_finding_ids else 0,
                        "finding_id":
                            mapped_finding_ids[0]
                            if mapped_finding_ids
                            else None,
                    }
                ],
                "finding_ids": mapped_finding_ids,
            }
            for rule in profile["criteria"]
        ],
        "native_fields": native_results,
        "limitations": [
            "The loaded profile is a local snapshot, not a live authority check."
        ],
    }


def validation_state(status: str = "not_run") -> dict:
    return {
        "status": status,
        "evidence_locator": "evidence/model-check.json" if status == "passed" else None,
        "sha256": HEX_B if status == "passed" else None,
    }


def write_receipt(root: pathlib.Path, locator: str, data: dict) -> tuple[str, str]:
    path = root / locator
    write_json(path, data)
    return locator, hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_task_input_records(
    evidence_root: pathlib.Path,
    input_artifact_ids: list[str],
    *,
    dependency_tasks: list[dict] | None = None,
    bundle_inputs: list[dict] | None = None,
) -> list[dict]:
    locator_by_id = {
        "paper-source": ("paper/main.tex", "paper-v1"),
        "paper-pdf": ("paper/main.pdf", "paper-v1"),
    }
    records: list[dict] = []
    for artifact_id in sorted(input_artifact_ids):
        locator, lineage_id = locator_by_id[artifact_id]
        path = evidence_root / locator
        records.append(
            {
                "input_id": f"run:{artifact_id}",
                "kind": "run_input",
                "source_id": artifact_id,
                "locator": locator,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "lineage_id": lineage_id,
                "source_kind":
                    "source" if artifact_id == "paper-source" else "pdf",
                "state": "frozen",
            }
        )
    for task in sorted(
        dependency_tasks or [],
        key=lambda item: item["task_id"],
    ):
        records.append(
            {
                "input_id": f"task:{task['task_id']}",
                "kind": "task_report",
                "source_id": task["task_id"],
                "locator": task["report_artifact"],
                "sha256": task["report_sha256"],
                "lineage_id": None,
                "source_kind": None,
                "state": None,
            }
        )
    for item in sorted(
        bundle_inputs or [],
        key=lambda value: value["locator"],
    ):
        records.append(
            {
                "input_id": f"bundle:{item['locator']}",
                "kind": "bundle_file",
                "source_id": item["locator"],
                "locator": item["locator"],
                "sha256": item["sha256"],
                "lineage_id": None,
                "source_kind": None,
                "state": None,
            }
        )
    return sorted(records, key=lambda item: item["input_id"])


def fixture_input_snapshot_sha256(records: list[dict]) -> str:
    return hashlib.sha256(
        canonical_bytes(
            {
                "schema_version": "1.0.0",
                "inputs": records,
            }
        )
    ).hexdigest()


def install_terminal_inventory(evidence_root: pathlib.Path, run: dict) -> None:
    tasks = [
        {
            "task_id": task["task_id"],
            "agent_or_task_identifier": task["agent_or_task_identifier"],
            "status": task["status"],
            "report_artifact": task["report_artifact"],
            "report_sha256": task["report_sha256"],
            "descendant_state": task["descendant_state"],
            "terminal_reason": task["terminal_reason"],
        }
        for task in sorted(
            run["delegation"]["tasks"],
            key=lambda item: item["task_id"],
        )
    ]
    locator, digest = write_receipt(
        evidence_root,
        "evidence/delegation-terminal-inventory.json",
        {
            "schema_version": "1.0.0",
            "receipt_kind": "delegation_terminal_inventory",
            "recorded_at": "2026-07-28T12:30:00Z",
            "run_id": run["run_id"],
            "tasks": tasks,
        },
    )
    run["delegation"]["terminal_inventory"] = {
        "locator": locator,
        "sha256": digest,
    }


def human_output_bytes(
    name: str,
    *,
    run_id: str = "RUN-2026-001",
    completion: str = "complete",
    criterion_ids: list[str] | None = None,
    finding_ids: list[str] | None = None,
    limitations: list[str] | None = None,
    machine_binding: dict | None = None,
) -> bytes:
    criterion_ids = criterion_ids or []
    finding_ids = finding_ids or []
    limitations = limitations or []
    machine_binding = machine_binding or {
        "schema_version": "1.0.0",
        "role": name,
        "run_id": run_id,
        "review_kind": "initial",
        "completion": completion,
        "limitations": limitations,
        "target": None,
        "source_pdf_alignment": None,
        "coverage": [],
        "findings": [],
        "tasks": [],
        "venue_profile": None,
        "venue_profile_authority_sha256": None,
        "venue_profile_authority": None,
        "venue_assessment_sha256": None,
        "venue_assessment": None,
    }
    binding_block = (
        "\n<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->\n"
        + canonical_bytes(machine_binding).decode("utf-8")
        + "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-END -->\n"
    )
    shared = (
        f"- Run ID: {run_id}\n"
        f"- Completion: {completion}\n"
        + "\n".join(f"- Criterion: {item}" for item in criterion_ids)
        + "\n"
        + "\n".join(f"- Finding: {item}" for item in finding_ids)
        + "\n"
        + "\n".join(f"- Limitation: {item}" for item in limitations)
        + "\n"
    )
    if name == "reviewer_report":
        text = (
            "# Independent Reviewer Report\n\n"
            "## Provenance\n\n"
            f"{shared}\n"
            "## Criterion assessment\n\n"
            "Evidence-bounded criterion assessment is recorded here.\n\n"
            "## Candidate findings\n\n"
            "Candidate findings are recorded with canonical anchors.\n\n"
            "## Strengths and clean controls\n\n"
            "Evidence-backed strengths and clean controls are recorded here.\n\n"
            "## Limitations and non-claims\n\n"
            "No acceptance prediction and no manuscript changes are claimed.\n"
        )
    elif name == "ae_assessment":
        text = (
            "# Adjudicated Assessment\n\n"
            "## Provenance\n\n"
            f"{shared}\n"
            "## Candidate disposition\n\n"
            "Every candidate is reconciled to a canonical disposition.\n\n"
            "## Canonical coverage\n\n"
            "Every criterion is accounted for with evidence.\n\n"
            "## Portable assessment\n\n"
            "Portable scientific findings remain separate from venue labels.\n\n"
            "## Target-conditioned assessment\n\n"
            "No venue-native field is invented.\n\n"
            "## Completion and non-claims\n\n"
            "The assessment is evidence bounded.\n"
        )
    else:
        text = (
            "# Review Summary\n\n"
            "## Outcome\n\n"
            f"{shared}\n"
            "## Most decision-relevant findings\n\n"
            "Canonical decision-relevant findings are listed above.\n\n"
            "## Strengths\n\n"
            "Only evidence-backed strengths are retained.\n\n"
            "## Coverage and dissent\n\n"
            "Coverage and dissent are reconciled.\n\n"
            "## Author and readiness gates\n\n"
            "Scientific, author, experiment, and packaging gates remain separate.\n\n"
            "## Limitations and non-claims\n\n"
            "No acceptance probability or fabricated evidence is claimed.\n\n"
            "## Next boundary\n\n"
            "This review does not authorise manuscript revision.\n"
        )
    return (text + binding_block).encode("utf-8")


def configured_subject_evidence(
    root: pathlib.Path,
    *,
    subject_kind: str,
    subject_id: str,
    configuration_source: str,
    proof_kind: str,
    adapter_sha256: str,
    compatibility_payload_sha256: str,
    selected_candidate_id: str | None,
    promotion_record_sha256: str | None,
    configured_model: str = "gpt-5.6-sol",
    configured_mode: str = "ultra",
    configured_sandbox: str | None = None,
    input_artifact_ids: list[str] | None = None,
    task_effects: list[str] | None = None,
    report_contract: str | None = None,
    stop_condition: str | None = None,
    agent_or_task_identifier: str | None = None,
    fork_policy: str | None = None,
    leaf_only: bool | None = None,
    dependency_task_ids: list[str] | None = None,
    bundle_input_artifacts: list[dict] | None = None,
    input_records: list[dict] | None = None,
    trigger: str | None = None,
    assigned_criterion_ids: list[str] | None = None,
) -> tuple[dict, dict, dict, dict | None]:
    requested_sandbox = "read-only" if subject_kind == "task" else None
    if subject_kind == "task" and configured_sandbox is None:
        configured_sandbox = "read-only"
    if subject_kind == "task":
        input_artifact_ids = input_artifact_ids or ["paper-source"]
        dependency_task_ids = dependency_task_ids or []
        bundle_input_artifacts = bundle_input_artifacts or []
        task_effects = task_effects or ["verify_finding"]
        report_contract = (
            report_contract or "schemas/task-report.schema.json"
        )
        stop_condition = (
            stop_condition
            or "Return after the bounded delegated check is reported."
        )
        agent_or_task_identifier = (
            agent_or_task_identifier or f"runtime-{subject_id}"
        )
        fork_policy = fork_policy or "none"
        leaf_only = True if leaf_only is None else leaf_only
        trigger = trigger or "Material independent verification is needed."
        assigned_criterion_ids = assigned_criterion_ids or [
            "RC-CLAIM-EVIDENCE"
        ]
        input_records = input_records or fixture_task_input_records(
            root,
            input_artifact_ids,
            bundle_inputs=bundle_input_artifacts,
        )
        input_snapshot_sha256 = fixture_input_snapshot_sha256(input_records)
    else:
        input_artifact_ids = None
        dependency_task_ids = None
        bundle_input_artifacts = None
        task_effects = None
        report_contract = None
        stop_condition = None
        agent_or_task_identifier = None
        fork_policy = None
        leaf_only = None
        input_records = None
        input_snapshot_sha256 = None
        trigger = None
        assigned_criterion_ids = None
    proof_locator = (
        f"evidence/{subject_kind}-{subject_id}-configuration.json"
    )
    proof_receipt = {
        "schema_version": "1.0.0",
        "receipt_kind": "configuration",
        "recorded_at": "2026-07-28T12:00:00Z",
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "requested_model": "gpt-5.6-sol",
        "requested_mode": "ultra",
        "requested_sandbox": requested_sandbox,
        "agent_or_task_identifier": agent_or_task_identifier,
        "fork_policy": fork_policy,
        "leaf_only": leaf_only,
        "input_artifact_ids": input_artifact_ids,
        "dependency_task_ids": dependency_task_ids,
        "bundle_input_artifacts": bundle_input_artifacts,
        "inputs": input_records,
        "input_snapshot_sha256": input_snapshot_sha256,
        "task_effects": task_effects,
        "report_contract": report_contract,
        "stop_condition": stop_condition,
        "configuration_source": configuration_source,
        "proof_kind": proof_kind,
        "surface": "Codex",
        "host_build": "not_surfaced",
        "configured_model": configured_model,
        "configured_mode": configured_mode,
        "configured_sandbox": configured_sandbox,
        "adapter_sha256": adapter_sha256,
        "compatibility_payload_sha256": compatibility_payload_sha256,
        "selected_candidate_id": selected_candidate_id,
        "promotion_record_sha256": promotion_record_sha256,
        "trigger": trigger,
        "assigned_criterion_ids": assigned_criterion_ids,
        "fallback_policy": "prohibited_and_checked",
    }
    proof_locator, proof_sha = write_receipt(
        root, proof_locator, proof_receipt
    )
    proof = {
        "subject_kind": subject_kind,
        "subject_id": subject_id,
        "proof_kind": proof_kind,
        "locator": proof_locator,
        "sha256": proof_sha,
    }

    states: dict[str, dict] = {}
    for control, expected_value, configured_value in (
        ("model", "gpt-5.6-sol", configured_model),
        ("mode", "ultra", configured_mode),
        *((("sandbox", "read-only", configured_sandbox),)
          if subject_kind == "task" else ()),
    ):
        locator = (
            f"evidence/{subject_kind}-{subject_id}-{control}-validation.json"
        )
        receipt = {
            "schema_version": "1.0.0",
            "receipt_kind": "control_validation",
            "recorded_at": "2026-07-28T12:00:01Z",
            "subject_kind": subject_kind,
            "subject_id": subject_id,
            "control": control,
            "expected_value": expected_value,
            "configured_value": configured_value,
            "result":
                "passed"
                if configured_value == expected_value
                else "failed",
            "configuration_receipt_locator": proof_locator,
            "configuration_receipt_sha256": proof_sha,
            "validator": "adapter-conformance-suite",
        }
        locator, digest = write_receipt(root, locator, receipt)
        states[control] = {
            "status":
                "passed"
                if configured_value == expected_value
                else "failed",
            "evidence_locator": locator,
            "sha256": digest,
        }
    return (
        proof,
        states["model"],
        states["mode"],
        states.get("sandbox"),
    )


def run_fixture(
    coverage: dict,
    manifest: dict,
    promotion: dict | None,
    *,
    compatibility: str = "evaluation_pending",
    review_kind: str = "initial",
    evidence_root: pathlib.Path,
    write_runtime_evidence: bool = True,
) -> dict:
    selected = manifest["selected_candidate_id"]
    promotion_ref = None
    if promotion:
        promotion_path_bytes = canonical_bytes(promotion)
        promotion_ref = {
            "record_id": promotion["record_id"],
            "record_locator": manifest["promotion_record_locator"],
            "sha256": hashlib.sha256(promotion_path_bytes).hexdigest(),
            "candidate_id": promotion["candidate_id"],
            "adapter_sha256": promotion["adapter_sha256"],
            "compatibility_payload_sha256":
                promotion["compatibility_payload_sha256"],
            "result": promotion["result"],
            "promotion_decision": promotion["promotion_decision"],
        }
    proof = {
        "subject_kind": "root",
        "subject_id": "RUN-2026-001",
        "proof_kind": "host_loaded_profile_receipt",
        "locator": "evidence/root-profile.json",
        "sha256": HEX_A,
    }
    model_validation = validation_state()
    mode_validation = validation_state()
    if compatibility in {
        "evaluation_pending",
        "configured-and-evaluated",
        "runtime-attested",
    }:
        model_validation = validation_state("passed")
        mode_validation = validation_state("passed")
        if write_runtime_evidence:
            (
                proof,
                model_validation,
                mode_validation,
                _,
            ) = configured_subject_evidence(
                evidence_root,
                subject_kind="root",
                subject_id="RUN-2026-001",
                configuration_source="adapter-controlled root dispatch",
                proof_kind="host_loaded_profile_receipt",
                adapter_sha256=manifest["adapter_payload_sha256"],
                compatibility_payload_sha256=
                    manifest["compatibility_payload_sha256"],
                selected_candidate_id=manifest["selected_candidate_id"],
                promotion_record_sha256=
                    manifest["promotion_record_sha256"],
            )
    source_text = fixture_source_text(coverage)
    input_bytes = {
        "paper/main.tex": source_text.encode("utf-8"),
        "paper/main.pdf": minimal_valid_pdf(),
    }
    input_digests: dict[str, str] = {}
    for locator, raw in input_bytes.items():
        path = evidence_root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        input_digests[locator] = hashlib.sha256(raw).hexdigest()
    pdftotext = shutil.which("pdftotext")
    if pdftotext is None:
        raise AssertionError("test contract requires pdftotext")
    extracted = subprocess.run(
        [
            pdftotext,
            "-f",
            "1",
            "-l",
            "1",
            "-layout",
            "-enc",
            "UTF-8",
            str(evidence_root / "paper/main.pdf"),
            "-",
        ],
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")
    extracted_sha = hashlib.sha256(extracted.encode("utf-8")).hexdigest()
    alignment_checks = []
    for check_id, excerpt in (
        ("title", "Synthetic Review Fixture"),
        ("section_sequence", "Introduction"),
    ):
        span = exact_span_fields(excerpt, source_text)
        alignment_checks.append(
            {
                "check_id": check_id,
                "source_anchor": span["source_anchor"],
                "source_excerpt": excerpt,
                "source_excerpt_sha256": hashlib.sha256(
                    excerpt.encode("utf-8")
                ).hexdigest(),
                "source_start_byte": span["start_byte"],
                "source_end_byte": span["end_byte"],
                "source_occurrence": span["occurrence"],
                "pdf_anchor": "pdf:page-1;occurrence:1",
                "pdf_excerpt": excerpt,
                "pdf_excerpt_sha256": hashlib.sha256(
                    excerpt.encode("utf-8")
                ).hexdigest(),
                "pdf_page": 1,
                "pdf_occurrence": 1,
                "pdf_page_text_sha256": extracted_sha,
                "result": "matched",
            }
        )
    alignment_locator, alignment_sha = write_receipt(
        evidence_root,
        "evidence/source-pdf-alignment.json",
        {
            "schema_version": "1.0.0",
            "receipt_kind": "source_pdf_alignment",
            "recorded_at": "2026-07-28T12:00:00Z",
            "source_artifact_id": "paper-source",
            "source_sha256": input_digests["paper/main.tex"],
            "pdf_artifact_id": "paper-pdf",
            "pdf_sha256": input_digests["paper/main.pdf"],
            "comparison_basis": "manual_structural_comparison",
            "pdf_integrity": {
                "method": "parsed",
                "tool": "pdfinfo",
                "page_count": 1,
                "result": "passed",
            },
            "checks": alignment_checks,
            "result": "matched",
            "limitations": [
                "Synthetic fixture receipt demonstrates contract binding only."
            ],
        },
    )
    pdftoppm = shutil.which("pdftoppm")
    if pdftoppm is None:
        raise AssertionError("test contract requires pdftoppm")
    version_process = subprocess.run(
        [pdftoppm, "-v"],
        check=True,
        capture_output=True,
    )
    version_text = (
        version_process.stdout + version_process.stderr
    ).decode("utf-8", errors="replace")
    version_match = re.search(
        r"\bpdftoppm version ([^\s]+)",
        version_text,
    )
    if version_match is None:
        raise AssertionError("pdftoppm version is unavailable")
    rendered_bytes = subprocess.run(
        [
            pdftoppm,
            "-f",
            "1",
            "-l",
            "1",
            "-singlefile",
            "-r",
            "72",
            "-png",
            str(evidence_root / "paper/main.pdf"),
        ],
        check=True,
        capture_output=True,
    ).stdout
    rendered_locator = "evidence/rendered-page-1.png"
    rendered_path = evidence_root / rendered_locator
    rendered_path.write_bytes(rendered_bytes)
    rendered_observation = "The matched frozen rendering was inspected."
    rendered_receipt_locator, rendered_receipt_sha = write_receipt(
        evidence_root,
        "evidence/rendered-visual-integrity.json",
        {
            "schema_version": "1.0.0",
            "receipt_kind": "rendered_evidence",
            "recorded_at": "2026-07-28T12:00:01Z",
            "subject_id": "RC-VISUAL-INTEGRITY",
            "artifact_id": "paper-pdf",
            "pdf_sha256": input_digests["paper/main.pdf"],
            "render_tool": "pdftoppm",
            "render_tool_version": version_match.group(1),
            "render_dpi": 72,
            "render_format": "png",
            "page_count": 1,
            "page": 1,
            "region": {
                "x0": 0,
                "y0": 0,
                "x1": 1,
                "y1": 1,
            },
            "rendered_artifact_locator": rendered_locator,
            "rendered_artifact_sha256": hashlib.sha256(
                rendered_bytes
            ).hexdigest(),
            "observation_sha256": hashlib.sha256(
                rendered_observation.encode("utf-8")
            ).hexdigest(),
        },
    )
    output_bytes = {
        "finding-ledger.json": canonical_bytes({"placeholder": True}),
        "reviewer-report.md": human_output_bytes("reviewer_report"),
        "ae-assessment.md": human_output_bytes("ae_assessment"),
        "review-summary.md": human_output_bytes("review_summary"),
    }
    output_records: dict[str, dict] = {}
    for name, locator in (
        ("finding_ledger", "finding-ledger.json"),
        ("reviewer_report", "reviewer-report.md"),
        ("ae_assessment", "ae-assessment.md"),
        ("review_summary", "review-summary.md"),
    ):
        raw = output_bytes[locator]
        path = evidence_root / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        output_records[name] = {
            "status": "produced",
            "locator": locator,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    run = {
        "schema_version": "1.0.0",
        "run_id": "RUN-2026-001",
        "created_at": "2026-07-28T12:00:00Z",
        "finalized_at": "2026-07-28T12:31:00Z",
        "review_goal": "Author-side pre-submission scientific review.",
        "review_kind": review_kind,
        "authorisation": {
            "capacity": "author_side",
            "authorised": True,
            "policy_status": "permitted",
            "rationale":
                "The author supplied the draft for local pre-submission review.",
        },
        "confidentiality": {
            "classification": "author_owned_draft",
            "processing": "local_only",
            "external_transmission_authorised": False,
            "external_destination": None,
            "retention": "run_only",
            "untrusted_content_acknowledged": True,
        },
        "review_only": True,
        "input_artifacts": [
            {
                "artifact_id": "paper-source",
                "kind": "source",
                "lineage_id": "paper-v1",
                "state": "frozen",
                "locator": "paper/main.tex",
                "sha256": input_digests["paper/main.tex"],
            },
            {
                "artifact_id": "paper-pdf",
                "kind": "pdf",
                "lineage_id": "paper-v1",
                "state": "frozen",
                "locator": "paper/main.pdf",
                "sha256": input_digests["paper/main.pdf"],
            },
        ],
        "source_pdf_alignment": {
            "status": "matched",
            "verified": True,
            "evidence": "Title, section sequence, and build lineage match.",
            "source_artifact_id": "paper-source",
            "pdf_artifact_id": "paper-pdf",
            "receipt_locator": alignment_locator,
            "receipt_sha256": alignment_sha,
        },
        "target": {"venue": "unknown", "year": None, "track": None},
        "venue_profile": {
            "status": "unknown",
            "profile_id": None,
            "profile_version": None,
            "venue": None,
            "year": None,
            "track": None,
            "profile_locator": None,
            "profile_sha256": None,
            "source_manifest_locator": None,
            "source_sha256": None,
            "blocked_reason": None,
        },
        "venue_assessment": {
            "status": "not_applicable",
            "profile_id": None,
            "criteria": [],
            "native_fields": [],
            "limitations": [],
        },
        "runtime_profile": {
            "surface": "Codex",
            "host_build": "not_surfaced",
            "requested_model": "gpt-5.6-sol",
            "requested_mode": "ultra",
            "configuration_source": "adapter-controlled root dispatch",
            "configuration_proof": proof,
            "adapter_controlled_fallback": "prohibited_and_checked",
            "selected_candidate_id": selected,
            "adapter_sha256": manifest["adapter_payload_sha256"],
            "compatibility_payload_sha256":
                manifest["compatibility_payload_sha256"],
            "promotion_record_sha256":
                manifest["promotion_record_sha256"],
            "model_validation": model_validation,
            "mode_validation": mode_validation,
            "promotion_evaluation_record": promotion_ref,
            "effective_telemetry":
                "surfaced_and_verified"
                if compatibility == "runtime-attested"
                else "not_surfaced",
            "resolved_model":
                "gpt-5.6-sol" if compatibility == "runtime-attested" else None,
            "resolved_mode": "ultra" if compatibility == "runtime-attested" else None,
            "compatibility_claim": compatibility,
        },
        "delegation": {
            "owner": "root",
            "coverage_risk_map": [
                {
                    "criterion_id": criterion_id,
                    "risk":
                        "material"
                        if criterion_id == "RC-CLAIM-EVIDENCE"
                        else "low",
                    "delegation_decision": "root_covers",
                    "task_ids": [],
                    "rationale":
                        "The root directly covers this bounded criterion.",
                }
                for criterion_id in (
                    ["RC-CLAIM-EVIDENCE"]
                    + [
                        row["criterion_id"]
                        for row in coverage["criteria"]
                        if row["criterion_id"] != "RC-CLAIM-EVIDENCE"
                    ]
                )
            ],
            "task_count_as_runtime_observation": 0,
            "tasks": [],
            "terminal_inventory": {
                "locator": "evidence/delegation-terminal-inventory.json",
                "sha256": HEX_A,
            },
        },
        "coverage": {
            "matrix_sha256": coverage_digest(coverage),
            "criteria": coverage_rows(
                coverage,
                rendered_receipt=(
                    rendered_receipt_locator,
                    rendered_receipt_sha,
                ),
            ),
        },
        "stages": [
            {
                "stage_id": stage_id,
                "status": "complete",
                "evidence": [
                    {
                        "kind": "input_artifact",
                        "reference": "paper-source",
                        "source_anchor": "frozen source bytes",
                    }
                ],
            }
            for stage_id in dict.fromkeys(
                row["primary_stage_owner"]
                for row in coverage["criteria"]
            )
        ],
        "output_artifacts": output_records,
        "completion": "complete",
        "limitations": [],
    }
    install_terminal_inventory(evidence_root, run)
    return run


def finding_fixture(*, review_kind: str = "initial") -> dict:
    source_text = fixture_source_text(coverage_fixture())
    excerpt = (
        "The headline claim covers unseen domains while the reported "
        "experiment covers one domain."
    )
    span = exact_span_fields(excerpt, source_text)
    finding = {
        "finding_id": "",
        "review_kind": review_kind,
        "prior_finding_id": None,
        "adjudication_status": "retained",
        "adjudication_rationale": "Evidence supports retaining this issue.",
        "delta_status": "not_applicable" if review_kind == "initial" else "new",
        "impact_change": "not_applicable",
        "evidence_state": "verified",
        "criterion": "RC-CLAIM-EVIDENCE",
        "related_criteria": [],
        "decision_impact": "material",
        "confidence": "high",
        "claim": "The headline claim exceeds the experiment's tested scope.",
        "evidence": {
            "artifact_id": "paper-source",
            "source_anchor": span["source_anchor"],
            "semantic_anchor": "claim:headline-generalisation",
            "observation": "The claim covers unseen domains; experiments cover one domain.",
            "anchor_verification": {
                "method": "utf8_exact_excerpt",
                "excerpt": excerpt,
                "excerpt_sha256": hashlib.sha256(
                    excerpt.encode("utf-8")
                ).hexdigest(),
                "start_byte": span["start_byte"],
                "end_byte": span["end_byte"],
                "occurrence": span["occurrence"],
                "rendered_receipt_locator": None,
                "rendered_receipt_sha256": None,
            },
        },
        "why_it_matters": "The central conclusion is not established as written.",
        "action_type": "prose-repair",
        "closure_requirement": {
            "state": "open",
            "owner": "author",
            "gate": "prose",
            "requirement": "Narrow the claim or provide matching evidence.",
            "resolution_evidence": None,
        },
        "dissent": {"state": "none", "summary": None},
        "provenance": {
            "primary_artifact_lineage_id": "paper-v1",
            "originating_task_ids": ["root"],
            "merged_from_ids": [],
            "merged_into_finding_id": None,
        },
    }
    finding["finding_id"] = stable_finding_id(finding)
    return finding


def ledger_fixture(*, review_kind: str = "initial") -> dict:
    return {
        "schema_version": "1.0.0",
        "run_id": "RUN-2026-001",
        "review_kind": review_kind,
        "completion": "complete",
        "findings": [finding_fixture(review_kind=review_kind)],
    }


class RunContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name) / "bundle"
        self.evidence_root = pathlib.Path(self.temp.name) / "run-evidence"
        self.manifest, self.promotion = make_bundle(self.root)
        self.coverage = load_review_coverage(self.root)
        self.run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        self.ledger = ledger_fixture()
        claim_row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        claim_row["disposition"] = "finding_linked"
        finding_id = self.ledger["findings"][0]["finding_id"]
        claim_row["finding_ids"] = [finding_id]
        self.sync_ledger_output()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assertErrorContains(self, errors: list[str], needle: str) -> None:
        self.assertTrue(
            any(needle in error for error in errors),
            f"{needle!r} not found in {errors!r}",
        )

    def sync_ledger_output(self) -> None:
        locator = self.run["output_artifacts"]["finding_ledger"]["locator"]
        path = self.evidence_root / locator
        write_json(path, self.ledger)
        self.run["output_artifacts"]["finding_ledger"]["sha256"] = (
            hashlib.sha256(path.read_bytes()).hexdigest()
        )
        for name, locator in (
            ("reviewer_report", "reviewer-report.md"),
            ("ae_assessment", "ae-assessment.md"),
            ("review_summary", "review-summary.md"),
        ):
            raw = render_human_view(
                name,
                self.run,
                self.ledger,
                self.root,
            ).encode("utf-8")
            path = self.evidence_root / locator
            path.write_bytes(raw)
            self.run["output_artifacts"][name]["sha256"] = hashlib.sha256(
                raw
            ).hexdigest()

    def validate_pair(self) -> list[str]:
        self.sync_ledger_output()
        return validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )

    def mutate_installed_venue_evidence(
        self,
        mutator: Any,
    ) -> list[str]:
        source_manifest_path = (
            self.root
            / self.run["venue_profile"]["source_manifest_locator"]
        )
        source_manifest = json.loads(
            source_manifest_path.read_text(encoding="utf-8")
        )
        source_row = source_manifest["sources"][0]
        evidence_path = self.root / source_row["content_locator"]
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        mutator(evidence)
        write_json(evidence_path, evidence)
        source_row["content_sha256"] = hashlib.sha256(
            evidence_path.read_bytes()
        ).hexdigest()
        write_json(source_manifest_path, source_manifest)
        source_manifest_sha = hashlib.sha256(
            source_manifest_path.read_bytes()
        ).hexdigest()

        profile_path = (
            self.root / self.run["venue_profile"]["profile_locator"]
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_sha256"] = source_manifest_sha
        write_json(profile_path, profile)
        profile_sha = hashlib.sha256(profile_path.read_bytes()).hexdigest()

        registry_path = self.root / "references/venue-authorities.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry_venue = next(
            row
            for row in registry["venues"]
            if row["venue"] == self.run["target"]["venue"]
        )
        registry_profile = next(
            row
            for row in registry_venue["profiles"]
            if row["profile_id"]
            == self.run["venue_profile"]["profile_id"]
        )
        registry_profile["profile_sha256"] = profile_sha
        registry_profile["source_sha256"] = source_manifest_sha
        write_json(registry_path, registry)

        self.run["venue_profile"]["profile_sha256"] = profile_sha
        self.run["venue_profile"]["source_sha256"] = source_manifest_sha
        return validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )

    def set_completion(self, completion: str) -> None:
        self.run["completion"] = completion
        self.ledger["completion"] = completion
        if completion in {"partial", "blocked"}:
            limitation = (
                "A bounded contract responsibility remains unresolved."
                if completion == "partial"
                else "A bounded contract responsibility is blocked."
            )
            if limitation not in self.run["limitations"]:
                self.run["limitations"].append(limitation)
            self.run["stages"][-1]["status"] = completion
        self.sync_ledger_output()

    def test_shipped_template_is_a_valid_fail_closed_preflight(self) -> None:
        template_run = json.loads(
            (ROOT / "templates/run-manifest.json").read_text(encoding="utf-8")
        )
        template_ledger = json.loads(
            (ROOT / "templates/finding-ledger.json").read_text(encoding="utf-8")
        )
        template_coverage = load_review_coverage(ROOT)
        self.assertFalse(template_run["authorisation"]["authorised"])
        self.assertEqual(template_run["input_artifacts"], [])
        self.assertEqual(template_run["delegation"]["tasks"], [])
        self.assertTrue(
            all(
                value["status"] == "not_produced"
                for value in template_run["output_artifacts"].values()
            )
        )
        self.assertEqual(
            validate_run_pair(
                template_run,
                template_ledger,
                template_coverage,
                ROOT,
                evidence_root=ROOT,
            ),
            [],
        )

        authorised = copy.deepcopy(template_run)
        authorised["authorisation"].update(
            {
                "authorised": True,
                "capacity": "author_side",
                "policy_status": "permitted",
            }
        )
        authorised["confidentiality"]["classification"] = "author_owned_draft"
        errors = validate_run_manifest(
            authorised,
            template_coverage,
            ROOT,
            evidence_root=ROOT,
        )
        self.assertErrorContains(errors, "cannot retain template sentinels")

        command = [
            sys.executable,
            str(ROOT / "scripts/render_human_binding.py"),
            "--bundle-root",
            str(ROOT),
            "--role",
            "review_summary",
            str(ROOT / "templates/run-manifest.json"),
            str(ROOT / "templates/finding-ledger.json"),
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(
            '"venue_assessment":{"criteria":[],"limitations":[]',
            completed.stdout,
        )

    def reset_valid_pair(self) -> None:
        self.run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        self.ledger = ledger_fixture()
        claim_row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        claim_row["disposition"] = "finding_linked"
        claim_row["finding_ids"] = [
            self.ledger["findings"][0]["finding_id"]
        ]
        self.sync_ledger_output()

    def install_completed_task(
        self,
        *,
        task_id: str = "T-1",
        task_effects: list[str] | None = None,
        finding_ids: list[str] | None = None,
        configured_model: str = "gpt-5.6-sol",
        configured_mode: str = "ultra",
        configured_sandbox: str = "read-only",
    ) -> dict:
        task_effects = task_effects or ["verify_finding"]
        finding_ids = finding_ids or []
        input_artifact_ids = ["paper-source"]
        dependency_task_ids: list[str] = []
        bundle_input_artifacts = [
            {
                "locator": "schemas/task-report.schema.json",
                "sha256": hashlib.sha256(
                    (self.root / "schemas/task-report.schema.json").read_bytes()
                ).hexdigest(),
            }
        ]
        input_records = fixture_task_input_records(
            self.evidence_root,
            input_artifact_ids,
            bundle_inputs=bundle_input_artifacts,
        )
        input_snapshot_sha256 = fixture_input_snapshot_sha256(input_records)
        stop_condition = (
            "Return after the bounded evidence and requested effects are "
            "fully reported."
        )
        (
            proof,
            model_validation,
            mode_validation,
            sandbox_validation,
        ) = configured_subject_evidence(
            self.evidence_root,
            subject_kind="task",
            subject_id=task_id,
            configuration_source="adapter-controlled dispatch",
            proof_kind="adapter_dispatch_record",
            adapter_sha256=self.manifest["adapter_payload_sha256"],
            compatibility_payload_sha256=
                self.manifest["compatibility_payload_sha256"],
            selected_candidate_id=self.manifest["selected_candidate_id"],
            promotion_record_sha256=
                self.manifest["promotion_record_sha256"],
            configured_model=configured_model,
            configured_mode=configured_mode,
            configured_sandbox=configured_sandbox,
            input_artifact_ids=input_artifact_ids,
            task_effects=task_effects,
            report_contract="schemas/task-report.schema.json",
            stop_condition=stop_condition,
            agent_or_task_identifier=f"runtime-{task_id}",
            fork_policy="none",
            leaf_only=True,
            dependency_task_ids=dependency_task_ids,
            bundle_input_artifacts=bundle_input_artifacts,
            input_records=input_records,
            trigger=(
                "Material independent verification is needed."
            ),
            assigned_criterion_ids=["RC-CLAIM-EVIDENCE"],
        )
        finding_effect = next(
            (
                effect
                for effect in task_effects
                if effect
                in {
                    "add_finding",
                    "verify_finding",
                    "remove_finding",
                    "adjudicate_finding",
                    "rank_finding",
                    "synthesise_findings",
                }
            ),
            None,
        )
        contributions = []
        for finding_id in finding_ids:
            finding = finding_fixture()
            finding["finding_id"] = finding_id
            contributions.append(
                {
                    "effect": finding_effect,
                    "finding_id": finding_id,
                    "criterion": finding["criterion"],
                    "claim": finding["claim"],
                    "artifact_id": finding["evidence"]["artifact_id"],
                    "source_anchor": finding["evidence"]["source_anchor"],
                    "semantic_anchor":
                        finding["evidence"]["semantic_anchor"],
                    "observation": finding["evidence"]["observation"],
                    "evidence_state": finding["evidence_state"],
                    "decision_impact": finding["decision_impact"],
                    "adjudication_status":
                        finding["adjudication_status"],
                    "rationale": finding["adjudication_rationale"],
                    "dissent": finding["dissent"],
                }
            )
        canonical_finding = finding_fixture()
        task_evidence = {
            "input_id": "run:paper-source",
            "artifact_id": "paper-source",
            "source_anchor":
                canonical_finding["evidence"]["source_anchor"],
            "semantic_anchor":
                canonical_finding["evidence"]["semantic_anchor"],
            "observation":
                canonical_finding["evidence"]["observation"],
        }
        report_locator, report_sha = write_receipt(
            self.evidence_root,
            f"reports/{task_id}.json",
            {
                "schema_version": "1.0.0",
                "reported_at": "2026-07-28T12:00:02Z",
                "run_id": self.run["run_id"],
                "task_id": task_id,
                "agent_or_task_identifier": f"runtime-{task_id}",
                "status": "completed",
                "task_effects": task_effects,
                "input_snapshot_sha256": input_snapshot_sha256,
                "configuration_receipt_sha256": proof["sha256"],
                "evidence": [task_evidence],
                "coverage_assessments": [
                    {
                        "criterion_id": "RC-CLAIM-EVIDENCE",
                        "applicability": "applicable",
                        "disposition":
                            "finding_linked"
                            if finding_ids
                            else "assessed_no_finding",
                        "evidence": [task_evidence],
                        "finding_ids": finding_ids,
                        "rationale":
                            "The assigned claim-evidence criterion was "
                            "assessed against bounded inputs.",
                    }
                ],
                "finding_contributions": contributions,
                "finding_ids": finding_ids,
                "summary":
                    "Completed the bounded delegated check and recorded its "
                    "evidence.",
                "limitations": [],
            },
        )
        task = {
            "task_id": task_id,
            "substantive": True,
            "trigger": "Material independent verification is needed.",
            "assigned_criterion_ids": ["RC-CLAIM-EVIDENCE"],
            "task_effects": task_effects,
            "input_artifact_ids": input_artifact_ids,
            "dependency_task_ids": dependency_task_ids,
            "bundle_input_artifacts": bundle_input_artifacts,
            "input_snapshot_sha256": input_snapshot_sha256,
            "report_contract": "schemas/task-report.schema.json",
            "stop_condition": stop_condition,
            "requested_model": "gpt-5.6-sol",
            "requested_mode": "ultra",
            "requested_sandbox": "read-only",
            "configuration_source": "adapter-controlled dispatch",
            "configuration_proof": proof,
            "adapter_controlled_fallback": "prohibited_and_checked",
            "model_validation": model_validation,
            "mode_validation": mode_validation,
            "sandbox_validation": sandbox_validation,
            "fork_policy": "none",
            "leaf_only": True,
            "descendant_state": "none",
            "agent_or_task_identifier": f"runtime-{task_id}",
            "status": "completed",
            "terminal_reason": None,
            "report_artifact": report_locator,
            "report_sha256": report_sha,
        }
        self.run["delegation"]["tasks"] = [task]
        self.run["delegation"]["task_count_as_runtime_observation"] = 1
        self.run["delegation"]["coverage_risk_map"][0][
            "delegation_decision"
        ] = "delegate"
        self.run["delegation"]["coverage_risk_map"][0]["task_ids"] = [task_id]
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["task_ids"] = [task_id]
        install_terminal_inventory(self.evidence_root, self.run)
        return task

    def convert_to_valid_delta(self) -> dict:
        prior = copy.deepcopy(self.ledger)
        prior["run_id"] = "RUN-2026-000"
        prior_scope_line = (
            "The prior scope statement still covers all domains without "
            "evaluation."
        )
        self.assertEqual(len(prior_scope_line), len(RESOLUTION_EXCERPT))
        prior_source_raw = (
            fixture_source_text(self.coverage).replace(
                f"{RESOLUTION_EXCERPT}\n",
                f"{prior_scope_line}\n",
            )
            + "% prior revision marker\n"
        ).encode("utf-8")
        prior_source_path = self.evidence_root / "prior/main.tex"
        prior_source_path.parent.mkdir(parents=True, exist_ok=True)
        prior_source_path.write_bytes(prior_source_raw)
        prior_source_sha = hashlib.sha256(prior_source_raw).hexdigest()
        prior_pdf_path = self.evidence_root / "prior/main.pdf"
        prior_pdf_raw = minimal_valid_pdf(
            prior_scope_line,
            variant_marker="prior",
        )
        prior_pdf_path.write_bytes(prior_pdf_raw)
        prior_pdf_sha = hashlib.sha256(prior_pdf_raw).hexdigest()
        prior_locator, prior_sha = write_receipt(
            self.evidence_root,
            "prior/finding-ledger.json",
            prior,
        )
        prior_run = copy.deepcopy(self.run)
        prior_run["run_id"] = "RUN-2026-000"
        prior_run["created_at"] = "2026-07-27T12:00:00Z"
        prior_run["finalized_at"] = "2026-07-27T12:31:00Z"
        prior_run["review_kind"] = "initial"
        prior_run["input_artifacts"] = [
            {
                "artifact_id": "paper-source",
                "kind": "source",
                "lineage_id": "paper-v1",
                "state": "frozen",
                "locator": "prior/main.tex",
                "sha256": prior_source_sha,
            },
            {
                "artifact_id": "paper-pdf",
                "kind": "pdf",
                "lineage_id": "paper-v1",
                "state": "frozen",
                "locator": "prior/main.pdf",
                "sha256": prior_pdf_sha,
            },
        ]
        current_alignment_path = (
            self.evidence_root
            / self.run["source_pdf_alignment"]["receipt_locator"]
        )
        current_alignment = json.loads(
            current_alignment_path.read_text(encoding="utf-8")
        )
        current_source_text = fixture_source_text(self.coverage)
        current_pdf_path = self.evidence_root / "paper/main.pdf"
        current_pdf_text = subprocess.run(
            [
                shutil.which("pdftotext"),
                "-f",
                "1",
                "-l",
                "1",
                "-layout",
                "-enc",
                "UTF-8",
                str(current_pdf_path),
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
        current_span = exact_span_fields(
            RESOLUTION_EXCERPT,
            current_source_text,
        )
        current_alignment["checks"].append(
            {
                "check_id": "revision_marker",
                "source_anchor": current_span["source_anchor"],
                "source_excerpt": RESOLUTION_EXCERPT,
                "source_excerpt_sha256": hashlib.sha256(
                    RESOLUTION_EXCERPT.encode("utf-8")
                ).hexdigest(),
                "source_start_byte": current_span["start_byte"],
                "source_end_byte": current_span["end_byte"],
                "source_occurrence": current_span["occurrence"],
                "pdf_anchor": "pdf:page-1;occurrence:1",
                "pdf_excerpt": RESOLUTION_EXCERPT,
                "pdf_excerpt_sha256": hashlib.sha256(
                    RESOLUTION_EXCERPT.encode("utf-8")
                ).hexdigest(),
                "pdf_page": 1,
                "pdf_occurrence": 1,
                "pdf_page_text_sha256": hashlib.sha256(
                    current_pdf_text.encode("utf-8")
                ).hexdigest(),
                "result": "matched",
            }
        )
        write_json(current_alignment_path, current_alignment)
        self.run["source_pdf_alignment"]["receipt_sha256"] = hashlib.sha256(
            current_alignment_path.read_bytes()
        ).hexdigest()
        prior_alignment = copy.deepcopy(current_alignment)
        prior_alignment["source_sha256"] = prior_source_sha
        prior_alignment["pdf_sha256"] = prior_pdf_sha
        prior_alignment["recorded_at"] = "2026-07-27T12:00:00Z"
        prior_pdf_text = subprocess.run(
            [
                shutil.which("pdftotext"),
                "-f",
                "1",
                "-l",
                "1",
                "-layout",
                "-enc",
                "UTF-8",
                str(prior_pdf_path),
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8")
        prior_page_text_sha = hashlib.sha256(
            prior_pdf_text.encode("utf-8")
        ).hexdigest()
        for check in prior_alignment["checks"]:
            check["pdf_page_text_sha256"] = prior_page_text_sha
            if check["check_id"] == "revision_marker":
                prior_source_text = prior_source_raw.decode("utf-8")
                prior_span = exact_span_fields(
                    prior_scope_line,
                    prior_source_text,
                )
                check.update(
                    {
                        "source_anchor": prior_span["source_anchor"],
                        "source_excerpt": prior_scope_line,
                        "source_excerpt_sha256": hashlib.sha256(
                            prior_scope_line.encode("utf-8")
                        ).hexdigest(),
                        "source_start_byte": prior_span["start_byte"],
                        "source_end_byte": prior_span["end_byte"],
                        "source_occurrence": prior_span["occurrence"],
                        "pdf_excerpt": prior_scope_line,
                        "pdf_excerpt_sha256": hashlib.sha256(
                            prior_scope_line.encode("utf-8")
                        ).hexdigest(),
                    }
                )
        prior_alignment_locator, prior_alignment_sha = write_receipt(
            self.evidence_root,
            "prior/source-pdf-alignment.json",
            prior_alignment,
        )
        prior_run["source_pdf_alignment"] = {
            "status": "matched",
            "verified": True,
            "evidence":
                "The prior source and rendered PDF were structurally aligned.",
            "source_artifact_id": "paper-source",
            "pdf_artifact_id": "paper-pdf",
            "receipt_locator": prior_alignment_locator,
            "receipt_sha256": prior_alignment_sha,
        }
        current_visual_evidence = run_coverage_row(
            self.run,
            "RC-VISUAL-INTEGRITY",
        )["evidence"][0]
        current_rendered_receipt_path = (
            self.evidence_root
            / current_visual_evidence["rendered_receipt_locator"]
        )
        prior_rendered_receipt = json.loads(
            current_rendered_receipt_path.read_text(encoding="utf-8")
        )
        current_rendered_artifact_path = (
            self.evidence_root
            / prior_rendered_receipt["rendered_artifact_locator"]
        )
        prior_rendered_artifact_locator = "prior/rendered-page-1.png"
        prior_rendered_artifact_path = (
            self.evidence_root / prior_rendered_artifact_locator
        )
        prior_rendered_artifact_path.write_bytes(
            subprocess.run(
                [
                    shutil.which("pdftoppm"),
                    "-f",
                    "1",
                    "-l",
                    "1",
                    "-singlefile",
                    "-r",
                    "72",
                    "-png",
                    str(prior_pdf_path),
                ],
                check=True,
                capture_output=True,
            ).stdout
        )
        prior_rendered_receipt["recorded_at"] = (
            "2026-07-27T12:00:01Z"
        )
        prior_rendered_receipt["pdf_sha256"] = prior_pdf_sha
        prior_rendered_receipt["rendered_artifact_locator"] = (
            prior_rendered_artifact_locator
        )
        prior_rendered_receipt["rendered_artifact_sha256"] = hashlib.sha256(
            prior_rendered_artifact_path.read_bytes()
        ).hexdigest()
        prior_rendered_receipt_locator, prior_rendered_receipt_sha = (
            write_receipt(
                self.evidence_root,
                "prior/rendered-visual-integrity.json",
                prior_rendered_receipt,
            )
        )
        prior_visual_evidence = run_coverage_row(
            prior_run,
            "RC-VISUAL-INTEGRITY",
        )["evidence"][0]
        prior_visual_evidence["source_anchor"] = (
            f"rendered:{prior_rendered_receipt_locator}#page=1"
        )
        prior_visual_evidence["rendered_receipt_locator"] = (
            prior_rendered_receipt_locator
        )
        prior_visual_evidence["rendered_receipt_sha256"] = (
            prior_rendered_receipt_sha
        )
        prior_run["runtime_profile"] = None
        prior_inventory_locator, prior_inventory_sha = write_receipt(
            self.evidence_root,
            "prior/delegation-terminal-inventory.json",
            {
                "schema_version": "1.0.0",
                "receipt_kind": "delegation_terminal_inventory",
                "recorded_at": "2026-07-27T12:00:00Z",
                "run_id": "RUN-2026-000",
                "tasks": [],
            },
        )
        prior_run["delegation"]["terminal_inventory"] = {
            "locator": prior_inventory_locator,
            "sha256": prior_inventory_sha,
        }
        prior_run["output_artifacts"]["finding_ledger"] = {
            "status": "produced",
            "locator": prior_locator,
            "sha256": prior_sha,
        }
        for name, locator in (
            ("reviewer_report", "prior/reviewer-report.md"),
            ("ae_assessment", "prior/ae-assessment.md"),
            ("review_summary", "prior/review-summary.md"),
        ):
            prior_run["output_artifacts"][name] = {
                "status": "produced",
                "locator": locator,
                "sha256": HEX_A,
            }
        for name, locator in (
            ("reviewer_report", "prior/reviewer-report.md"),
            ("ae_assessment", "prior/ae-assessment.md"),
            ("review_summary", "prior/review-summary.md"),
        ):
            raw = render_human_view(
                name,
                prior_run,
                prior,
                self.root,
            ).encode("utf-8")
            path = self.evidence_root / locator
            path.write_bytes(raw)
            prior_run["output_artifacts"][name]["sha256"] = hashlib.sha256(
                raw
            ).hexdigest()
        prior_run_locator, prior_run_sha = write_receipt(
            self.evidence_root,
            "prior/run-manifest.json",
            prior_run,
        )
        response_locator, response_sha = write_receipt(
            self.evidence_root,
            "prior/author-response.json",
            {
                "schema_version": "1.0.0",
                "response_id": "AR-2026-001",
                "recorded_at": "2026-07-28T11:30:00Z",
                "prior_run_id": "RUN-2026-000",
                "prior_run_sha256": prior_run_sha,
                "prior_ledger_sha256": prior_sha,
                "prior_source_sha256": prior_source_sha,
                "revised_source_sha256": next(
                    artifact["sha256"]
                    for artifact in self.run["input_artifacts"]
                    if artifact["kind"] == "source"
                ),
                "summary":
                    "The author reports a revised scope claim for delta review.",
                "transitions": [
                    {
                        "prior_finding_id": prior["findings"][0]["finding_id"],
                        "criterion_id": prior["findings"][0]["criterion"],
                        "prior_claim_sha256": hashlib.sha256(
                            prior["findings"][0]["claim"].encode("utf-8")
                        ).hexdigest(),
                        "disposition": "not_addressed",
                        "summary":
                            "The prior finding remains open in this revision.",
                        "successor_evidence": None,
                    }
                ],
            },
        )
        self.run["review_kind"] = "delta"
        self.run["input_artifacts"].extend(
            [
                {
                    "artifact_id": "prior-run",
                    "kind": "prior_run",
                    "lineage_id": "prior-review-v1",
                    "state": "frozen",
                    "locator": prior_run_locator,
                    "sha256": prior_run_sha,
                },
                {
                "artifact_id": "prior-ledger",
                "kind": "prior_ledger",
                "lineage_id": "prior-review-v1",
                "state": "frozen",
                "locator": prior_locator,
                "sha256": prior_sha,
                },
                {
                    "artifact_id": "prior-source",
                    "kind": "prior_source",
                    "lineage_id": "paper-v1",
                    "state": "frozen",
                    "locator": "prior/main.tex",
                    "sha256": prior_source_sha,
                },
                {
                    "artifact_id": "author-response",
                    "kind": "author_response",
                    "lineage_id": "prior-review-v1",
                    "state": "frozen",
                    "locator": response_locator,
                    "sha256": response_sha,
                },
            ]
        )
        self.ledger["review_kind"] = "delta"
        finding = self.ledger["findings"][0]
        finding["review_kind"] = "delta"
        finding["prior_finding_id"] = finding["finding_id"]
        finding["delta_status"] = "still_open"
        finding["impact_change"] = "unchanged"
        delta_row = run_coverage_row(self.run, "RC-DELTA-LINEAGE")
        delta_row["applicability"] = "applicable"
        delta_row["disposition"] = "assessed_no_finding"
        delta_row["evidence"] = [
            {
                "artifact_id": artifact_id,
                "source_anchor": f"delta-input:{artifact_id}",
                "semantic_anchor": f"delta:predecessor:{artifact_id}",
                "observation": "The delta predecessor record was byte-bound.",
                "evidence_kind": "prior_record",
                "verification_method": "prior_record_binding",
                "excerpt": None,
                "excerpt_sha256": None,
            }
            for artifact_id in (
                "prior-run",
                "prior-ledger",
                "prior-source",
                "author-response",
            )
        ]
        delta_row["rationale"] = (
            "Every surviving prior finding is reconciled exactly once."
        )
        delta_row["delta_applicability_reconciliation"] = {
            "prior_applicability": "inapplicable",
            "current_applicability": "applicable",
            "author_response_id": "AR-2026-001",
            "evidence_artifact_ids": [
                "prior-run",
                "prior-ledger",
                "prior-source",
                "author-response",
            ],
            "rationale": (
                "The delta-lineage criterion becomes applicable because this "
                "run explicitly reviews a frozen predecessor."
            ),
        }
        return prior

    def test_valid_initial_pair_and_unknown_venue(self) -> None:
        self.assertEqual(
            [],
            self.validate_pair(),
        )

    def test_evidence_root_is_an_explicit_api_boundary(self) -> None:
        with self.assertRaises(TypeError):
            validate_run_manifest(self.run, self.coverage, self.root)
        with self.assertRaises(TypeError):
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
            )

    def test_frozen_inputs_reject_traversal_missing_tamper_and_symlink(self) -> None:
        source = self.run["input_artifacts"][0]
        source["locator"] = "../outside.tex"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "frozen input locator is invalid",
        )

        source["locator"] = "paper/missing.tex"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "regular file",
        )

        source["locator"] = "paper/main.tex"
        source_path = self.evidence_root / source["locator"]
        source_path.write_text("tampered\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "frozen input hash mismatch",
        )

        run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        source_path = self.evidence_root / "paper/main.tex"
        backing = self.evidence_root / "paper/main-source-backing.tex"
        source_path.rename(backing)
        source_path.symlink_to(backing)
        self.assertErrorContains(
            validate_run_manifest(
                run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "symlink",
        )

    def test_produced_outputs_reject_traversal_missing_tamper_and_empty(self) -> None:
        output = self.run["output_artifacts"]["reviewer_report"]
        output["locator"] = "../outside.md"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "produced output locator is invalid",
        )

        output["locator"] = "missing-reviewer-report.md"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "regular file",
        )

        output["locator"] = "reviewer-report.md"
        output_path = self.evidence_root / output["locator"]
        output_path.write_text("tampered\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "produced output hash mismatch",
        )

        output["sha256"] = hashlib.sha256(b"").hexdigest()
        output_path.write_bytes(b"")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "cannot be empty",
        )

    def test_bundle_and_run_evidence_roots_must_be_disjoint(self) -> None:
        shutil.copytree(
            self.evidence_root,
            self.root,
            dirs_exist_ok=True,
            symlinks=True,
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.root,
            ),
            "physically separate",
        )

    def test_portable_run_does_not_require_the_optional_codex_adapter(self) -> None:
        self.run["runtime_profile"] = None
        self.assertEqual(
            [],
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )

    def test_strict_datetime_and_nonfinite_values_are_rejected(self) -> None:
        self.run["created_at"] = "2026-07-28 12:00:00Z"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "RFC 3339",
        )
        self.run["created_at"] = "2026-07-28T12:00:00Z"
        self.run["target"]["year"] = float("nan")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "non-finite",
        )
        self.run["target"]["year"] = float("inf")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "non-finite",
        )

    def test_stable_id_ignores_line_status_and_reviewer_changes(self) -> None:
        finding = finding_fixture()
        expected = stable_finding_id(finding)
        changed = copy.deepcopy(finding)
        changed["adjudication_status"] = "unresolved"
        changed["decision_impact"] = "fundamental"
        changed["evidence"]["source_anchor"] = "Section 5, line 999"
        changed["provenance"]["originating_task_ids"] = ["different-reviewer"]
        self.assertEqual(expected, stable_finding_id(changed))
        changed["evidence"]["semantic_anchor"] = "claim:different"
        self.assertNotEqual(expected, stable_finding_id(changed))

    def test_stable_id_has_unicode_and_delimiter_safe_canonicalisation(self) -> None:
        finding = finding_fixture()
        finding["claim"] = "ＦOO\t bar"
        equivalent = copy.deepcopy(finding)
        equivalent["claim"] = "foo bar"
        self.assertEqual(
            stable_finding_id(finding), stable_finding_id(equivalent)
        )
        collision_a = copy.deepcopy(finding)
        collision_b = copy.deepcopy(finding)
        collision_a["criterion"] = "a|b"
        collision_a["claim"] = "c"
        collision_b["criterion"] = "a"
        collision_b["claim"] = "b|c"
        self.assertNotEqual(
            stable_finding_id(collision_a), stable_finding_id(collision_b)
        )

    def test_material_finding_requires_evidence(self) -> None:
        self.ledger["findings"][0]["evidence"]["source_anchor"] = ""
        self.assertErrorContains(
            validate_finding_ledger(self.ledger), "source_anchor"
        )

    def test_duplicate_finding_id_is_rejected(self) -> None:
        self.ledger["findings"].append(copy.deepcopy(self.ledger["findings"][0]))
        self.assertErrorContains(
            validate_finding_ledger(self.ledger), "duplicate finding_id"
        )

    def test_initial_and_delta_axes_are_orthogonal(self) -> None:
        finding = self.ledger["findings"][0]
        finding["delta_status"] = "still_open"
        finding["impact_change"] = "unchanged"
        finding["prior_finding_id"] = "F-prior"
        errors = validate_finding_ledger(self.ledger)
        self.assertErrorContains(errors, "delta_status")
        self.assertErrorContains(errors, "impact_change")
        self.assertErrorContains(errors, "prior_finding_id")

        delta = ledger_fixture(review_kind="delta")
        carried = delta["findings"][0]
        carried["delta_status"] = "still_open"
        carried["impact_change"] = "unchanged"
        carried["prior_finding_id"] = None
        self.assertErrorContains(
            validate_finding_ledger(delta), "prior_finding_id"
        )

    def test_rejected_carried_finding_keeps_delta_axis_orthogonal(self) -> None:
        delta = ledger_fixture(review_kind="delta")
        carried = delta["findings"][0]
        carried["prior_finding_id"] = carried["finding_id"]
        carried["adjudication_status"] = "rejected"
        carried["adjudication_rationale"] = (
            "The current review rejects this candidate while preserving the "
            "separate delta observation."
        )
        carried["delta_status"] = "still_open"
        carried["impact_change"] = "downgraded"
        carried["decision_impact"] = "none"
        carried["action_type"] = "no-action"
        carried["closure_requirement"] = {
            "state": "not_applicable",
            "owner": "none",
            "gate": "none",
            "requirement": None,
            "resolution_evidence": None,
        }
        self.assertEqual([], validate_finding_ledger(delta, self.root))

    def test_carried_delta_finding_preserves_stable_id(self) -> None:
        delta = ledger_fixture(review_kind="delta")
        carried = delta["findings"][0]
        carried["prior_finding_id"] = "F-1111111111111111"
        carried["delta_status"] = "still_open"
        carried["impact_change"] = "unchanged"
        self.assertErrorContains(
            validate_finding_ledger(delta), "preserve finding_id"
        )

    def test_valid_delta_pair_binds_prior_and_accounts_every_survivor(self) -> None:
        self.convert_to_valid_delta()
        self.assertEqual([], self.validate_pair())

        self.ledger["findings"] = []
        claim_row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        claim_row["disposition"] = "assessed_no_finding"
        claim_row["finding_ids"] = []
        self.assertErrorContains(
            self.validate_pair(),
            "prior surviving finding is not accounted for",
        )

    def test_delta_transition_binds_prior_criterion_claim_and_chronology(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["transitions"][0]["criterion_id"] = "RC-LIMITATIONS"
        response["transitions"][0]["prior_claim_sha256"] = HEX_A
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        errors = self.validate_pair()
        self.assertErrorContains(errors, "transition criterion")
        self.assertErrorContains(errors, "transition claim hash")

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["recorded_at"] = "2026-07-29T12:00:00Z"
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "delta chronology",
        )

    def test_addressed_transition_requires_typed_successor_evidence(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["transitions"][0]["disposition"] = "partially_addressed"
        response["transitions"][0]["successor_evidence"] = None
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "successor_evidence",
        )

    def test_delta_applicability_change_requires_exact_reconciliation(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        row = run_coverage_row(self.run, "RC-VISUAL-INTEGRITY")
        row["applicability"] = "inapplicable"
        row["disposition"] = "not_applicable"
        row["evidence"] = []
        self.assertErrorContains(
            self.validate_pair(),
            "applicability change requires explicit reconciliation",
        )

    def test_inapplicable_carried_issue_can_be_disputed_and_rejected(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["adjudication_status"] = "rejected"
        finding["adjudication_rationale"] = (
            "The revised scope makes the prior obligation inapplicable; the "
            "review preserves the delta observation without retaining it."
        )
        finding["delta_status"] = "still_open"
        finding["impact_change"] = "downgraded"
        finding["decision_impact"] = "none"
        finding["action_type"] = "no-action"
        finding["closure_requirement"] = {
            "state": "not_applicable",
            "owner": "none",
            "gate": "none",
            "requirement": None,
            "resolution_evidence": None,
        }
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["applicability"] = "inapplicable"
        row["disposition"] = "not_applicable"
        row["evidence"] = []
        row["finding_ids"] = []
        row["delta_applicability_reconciliation"] = {
            "prior_applicability": "applicable",
            "current_applicability": "inapplicable",
            "author_response_id": "AR-2026-001",
            "evidence_artifact_ids": [
                "paper-source",
                "author-response",
            ],
            "rationale": (
                "The bounded revision removes the broad claim that made the "
                "prior issue applicable."
            ),
        }
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["transitions"][0]["disposition"] = "disputed"
        response["transitions"][0]["summary"] = (
            "The prior issue is disputed after the claim was removed."
        )
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertEqual([], self.validate_pair())

    def test_delta_rejects_reused_predecessor_pdf(self) -> None:
        self.convert_to_valid_delta()
        prior_run_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_run"
        )
        prior_run = json.loads(
            (
                self.evidence_root / prior_run_artifact["locator"]
            ).read_text(encoding="utf-8")
        )
        prior_pdf_sha = next(
            artifact["sha256"]
            for artifact in prior_run["input_artifacts"]
            if artifact["kind"] == "pdf"
        )
        current_pdf = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "pdf"
        )
        current_pdf["sha256"] = prior_pdf_sha
        self.assertErrorContains(
            self.validate_pair(),
            "revised source cannot reuse the predecessor PDF",
        )

    def test_delta_rejects_missing_self_current_and_resurrected_prior(
        self,
    ) -> None:
        self.run["review_kind"] = "delta"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "requires exactly one prior-ledger",
        )

        self.convert_to_valid_delta()
        prior_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_ledger"
        )
        current_output = self.run["output_artifacts"]["finding_ledger"]
        self.sync_ledger_output()
        prior_artifact["locator"] = current_output["locator"]
        prior_artifact["sha256"] = current_output["sha256"]
        errors = validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "aliases frozen input")
        self.assertErrorContains(errors, "run_id must differ")

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["prior_finding_id"] = None
        finding["delta_status"] = "new"
        finding["impact_change"] = "not_applicable"
        self.assertErrorContains(
            self.validate_pair(),
            "new finding ID already exists in prior ledger",
        )

    def test_invalid_prior_ledger_fails_without_accounting_crash(self) -> None:
        self.convert_to_valid_delta()
        prior_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_ledger"
        )
        prior_path = self.evidence_root / prior_artifact["locator"]
        write_json(
            prior_path,
            {
                "schema_version": "1.0.0",
                "run_id": "RUN-BAD",
                "review_kind": "initial",
                "completion": "complete",
                "findings": [{"finding_id": None}],
            },
        )
        prior_artifact["sha256"] = hashlib.sha256(
            prior_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "prior ledger",
        )

    def test_resolved_delta_requires_non_obligating_closed_evidence(self) -> None:
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["delta_status"] = "resolved"
        finding["impact_change"] = "downgraded"
        finding["decision_impact"] = "none"
        finding["action_type"] = "no-action"
        closure = finding["closure_requirement"]
        closure["state"] = "closed"
        closure["owner"] = "author"
        closure["gate"] = "experiment"
        closure["requirement"] = "A future experiment is still required."
        closure["resolution_evidence"] = "The prior concern was checked."
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "resolution_evidence",
        )

        span = exact_span_fields(
            RESOLUTION_EXCERPT,
            fixture_source_text(self.coverage),
        )
        closure["resolution_evidence"] = {
            "artifact_id": "paper-source",
            "source_anchor": span["source_anchor"],
            "semantic_anchor": finding["evidence"]["semantic_anchor"],
            "observation":
                "The revised source now states the bounded evaluated scope.",
            "anchor_verification": {
                "method": "utf8_exact_excerpt",
                "excerpt": RESOLUTION_EXCERPT,
                "excerpt_sha256": hashlib.sha256(
                    RESOLUTION_EXCERPT.encode("utf-8")
                ).hexdigest(),
                "start_byte": span["start_byte"],
                "end_byte": span["end_byte"],
                "occurrence": span["occurrence"],
                "rendered_receipt_locator": None,
                "rendered_receipt_sha256": None,
            },
            "author_response_id": "AR-2026-001",
            "prior_finding_id": finding["prior_finding_id"],
        }
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "closed closure requires no surviving owner",
        )
        closure["owner"] = "none"
        closure["gate"] = "none"
        closure["requirement"] = None
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["transitions"][0]["disposition"] = "addressed"
        response["transitions"][0]["summary"] = (
            "The revised source now explicitly bounds the scope."
        )
        response["transitions"][0]["successor_evidence"] = {
            key: copy.deepcopy(closure["resolution_evidence"][key])
            for key in (
                "artifact_id",
                "source_anchor",
                "semantic_anchor",
                "observation",
                "anchor_verification",
            )
        }
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertEqual([], self.validate_pair())

        response["transitions"][0]["successor_evidence"]["observation"] = (
            "A different observation is substituted after closure."
        )
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "exactly bind the author-response successor evidence",
        )

        response["transitions"][0]["successor_evidence"] = {
            key: copy.deepcopy(closure["resolution_evidence"][key])
            for key in (
                "artifact_id",
                "source_anchor",
                "semantic_anchor",
                "observation",
                "anchor_verification",
            )
        }
        response["transitions"][0]["successor_evidence"][
            "semantic_anchor"
        ] = "criterion:RC-LIMITATIONS"
        closure["resolution_evidence"]["semantic_anchor"] = (
            "criterion:RC-LIMITATIONS"
        )
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "successor semantic anchor",
        )

    def test_invalid_values_and_closed_unresolved_are_rejected(self) -> None:
        finding = self.ledger["findings"][0]
        finding["decision_impact"] = "major"
        finding["action_type"] = "rewrite-it"
        finding["adjudication_status"] = "unresolved"
        finding["closure_requirement"]["state"] = "closed"
        errors = validate_finding_ledger(self.ledger)
        self.assertErrorContains(errors, "decision_impact")
        self.assertErrorContains(errors, "action_type")
        finding["decision_impact"] = "material"
        finding["action_type"] = "prose-repair"
        errors = validate_finding_ledger(self.ledger)
        self.assertErrorContains(errors, "cannot be closed")

    def test_candidate_cannot_survive_complete_ledger(self) -> None:
        self.ledger["findings"][0]["adjudication_status"] = "candidate"
        self.assertErrorContains(
            validate_finding_ledger(self.ledger), "candidate"
        )

    def test_run_and_ledger_kinds_must_match(self) -> None:
        self.ledger["review_kind"] = "delta"
        self.assertErrorContains(
            self.validate_pair(),
            "review_kind mismatch",
        )

    def test_coverage_is_exact_and_evidence_bounded(self) -> None:
        self.run["coverage"]["criteria"].pop()
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "missing canonical criterion",
        )
        self.run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        self.run["coverage"]["criteria"][0]["evidence"] = []
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "applicable criterion requires evidence",
        )

    def test_run_record_evidence_requires_an_explicit_criterion_mapping(
        self,
    ) -> None:
        row = run_coverage_row(self.run, "RC-PROBLEM-FORMULATION")
        row["evidence"] = [
            {
                "artifact_id": "run:None",
                "source_anchor": "run-manifest:None",
                "semantic_anchor": "criterion:RC-PROBLEM-FORMULATION",
                "observation": "An unmapped pseudo-field was claimed.",
                "evidence_kind": "run_record",
                "verification_method": "canonical_run_field",
                "excerpt": None,
                "excerpt_sha256": None,
            }
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "run-record evidence is not authorised",
        )

    def test_run_record_evidence_binds_the_named_canonical_field(self) -> None:
        row = run_coverage_row(self.run, "RC-AUTHORISATION")
        row["evidence"][0]["source_anchor"] = "run-manifest:completion"
        self.assertErrorContains(
            self.validate_pair(),
            "run-record evidence is not authorised",
        )

    def test_uncertain_or_blocked_coverage_cannot_be_complete(self) -> None:
        row = self.run["coverage"]["criteria"][0]
        row["applicability"] = "uncertain"
        row["disposition"] = "blocked"
        row["rationale"] = "The source lineage receipt is missing."
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "uncertain criterion requires partial or blocked completion",
        )

    def test_needs_verification_cannot_be_hidden_in_complete_coverage(self) -> None:
        row = self.run["coverage"]["criteria"][0]
        row["applicability"] = "applicable"
        row["disposition"] = "needs_verification"
        row["rationale"] = "A material input claim still needs verification."
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "unresolved criterion disposition",
        )

    def test_criterion_specific_applicability_cannot_be_bypassed(self) -> None:
        self.coverage["criteria"][0]["applicability_states"] = [
            "applicable",
            "uncertain",
        ]
        write_json(
            self.root / "references/review-coverage.json",
            self.coverage,
        )
        self.run["coverage"]["matrix_sha256"] = coverage_digest(self.coverage)
        row = self.run["coverage"]["criteria"][0]
        row["applicability"] = "inapplicable"
        row["disposition"] = "not_applicable"
        row["evidence"] = []
        row["rationale"] = "Attempted bypass of an always-applicable duty."
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "applicability is forbidden",
        )

    def test_run_path_rejects_reduced_noncanonical_coverage_matrix(self) -> None:
        reduced = {
            "schema_version": "1.0.0",
            "criteria": [copy.deepcopy(self.coverage["criteria"][0])],
        }
        write_json(
            self.root / "references/review-coverage.json",
            reduced,
        )
        with self.assertRaisesRegex(ValueError, "fewer than 34"):
            load_review_coverage(self.root)

    def test_source_pdf_failure_cannot_be_complete(self) -> None:
        self.run["source_pdf_alignment"]["verified"] = False
        self.run["source_pdf_alignment"]["status"] = "mismatch"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "source/PDF"
        )

    def test_configuration_proof_cannot_be_self_report_or_static_example(self) -> None:
        proof = self.run["runtime_profile"]["configuration_proof"]
        proof["proof_kind"] = "self_report"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "runtime_profile",
        )
        proof["proof_kind"] = "host_loaded_profile_receipt"
        proof["locator"] = "../outside.json"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "canonical and relative",
        )
        proof["proof_kind"] = "static_toml"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "runtime_profile",
        )

    def test_runtime_surface_and_configuration_source_are_closed_enums(self) -> None:
        self.run["runtime_profile"]["surface"] = "OtherHost"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "surface",
        )
        self.run["runtime_profile"]["surface"] = "Codex"
        self.run["runtime_profile"]["configuration_source"] = "self-report"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "configuration_source",
        )

    def test_unverified_telemetry_mismatch_forces_blocked_claim(self) -> None:
        runtime = self.run["runtime_profile"]
        runtime["effective_telemetry"] = "surfaced_unverified"
        runtime["resolved_model"] = "gpt-5.6-terra"
        runtime["resolved_mode"] = "max"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "mismatch requires blocked",
        )
        runtime["compatibility_claim"] = "blocked"
        self.set_completion("partial")
        self.assertEqual(
            [],
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )

    def test_failed_control_validation_requires_and_accepts_failure_evidence(
        self,
    ) -> None:
        (
            proof,
            model_validation,
            mode_validation,
            _,
        ) = configured_subject_evidence(
            self.evidence_root,
            subject_kind="root",
            subject_id=self.run["run_id"],
            configuration_source="adapter-controlled root dispatch",
            proof_kind="host_loaded_profile_receipt",
            adapter_sha256=self.manifest["adapter_payload_sha256"],
            compatibility_payload_sha256=
                self.manifest["compatibility_payload_sha256"],
            selected_candidate_id=self.manifest["selected_candidate_id"],
            promotion_record_sha256=
                self.manifest["promotion_record_sha256"],
            configured_model="gpt-5.6-terra",
        )
        runtime = self.run["runtime_profile"]
        runtime["compatibility_claim"] = "blocked"
        self.set_completion("partial")
        runtime["configuration_proof"] = proof
        runtime["model_validation"] = model_validation
        runtime["mode_validation"] = mode_validation
        self.assertEqual(
            [],
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )
        runtime["model_validation"] = {
            "status": "failed",
            "evidence_locator": None,
            "sha256": None,
        }
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "model_validation",
        )
    def test_configuration_and_validation_receipts_are_byte_bound(self) -> None:
        manifest, promotion = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        coverage = load_review_coverage(self.root)
        missing = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
            write_runtime_evidence=False,
        )
        self.assertErrorContains(
            validate_run_manifest(
                missing,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "configuration proof",
        )

        valid = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        self.assertEqual(
            [],
            validate_run_manifest(
                valid,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )
        proof_path = (
            self.evidence_root
            / valid["runtime_profile"]["configuration_proof"]["locator"]
        )
        proof_path.write_text("{}\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                valid,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "hash mismatch",
        )
        valid = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        model_path = (
            self.evidence_root
            / valid["runtime_profile"]["model_validation"][
                "evidence_locator"
            ]
        )
        model_path.write_text("{}\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                valid,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "root model validation: evidence hash mismatch",
        )

    def test_runtime_receipts_bind_the_current_release_contract(self) -> None:
        core_path = self.root / "references/scientific-core.md"
        core_path.write_text(
            core_path.read_text(encoding="utf-8")
            + "\nA changed compatibility contract.\n",
            encoding="utf-8",
        )
        manifest_path = self.root / "adapters/codex/adapter-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["compatibility_payload_sha256"] = (
            compatibility_payload_sha256(self.root)
        )
        write_json(manifest_path, manifest)
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "compatibility payload SHA")
        self.run["runtime_profile"]["compatibility_payload_sha256"] = (
            manifest["compatibility_payload_sha256"]
        )
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(
            errors,
            "configuration proof receipt compatibility_payload_sha256",
        )

    def test_dispatch_scope_is_bound_before_task_execution(self) -> None:
        task = self.install_completed_task(
            task_effects=["format_report"],
            finding_ids=[],
        )
        claim_risk = next(
            row
            for row in self.run["delegation"]["coverage_risk_map"]
            if row["criterion_id"] == "RC-CLAIM-EVIDENCE"
        )
        method_risk = next(
            row
            for row in self.run["delegation"]["coverage_risk_map"]
            if row["criterion_id"] == "RC-METHOD-SOUNDNESS"
        )
        claim_risk["delegation_decision"] = "root_covers"
        claim_risk["task_ids"] = []
        method_risk["delegation_decision"] = "delegate"
        method_risk["task_ids"] = [task["task_id"]]
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["task_ids"] = []
        run_coverage_row(
            self.run, "RC-METHOD-SOUNDNESS"
        )["task_ids"] = [task["task_id"]]
        task["assigned_criterion_ids"] = ["RC-METHOD-SOUNDNESS"]
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["coverage_assessments"][0]["criterion_id"] = (
            "RC-METHOD-SOUNDNESS"
        )
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "configuration proof receipt assigned_criterion_ids",
        )

    def test_task_snapshot_binds_the_full_input_descriptor(self) -> None:
        self.install_completed_task(
            task_effects=["format_report"],
            finding_ids=[],
        )
        source = next(
            item
            for item in self.run["input_artifacts"]
            if item["artifact_id"] == "paper-source"
        )
        source["kind"] = "supplement"
        self.assertErrorContains(
            self.validate_pair(),
            "input_snapshot_sha256 does not bind exact task inputs",
        )

    def test_configuration_receipt_symlink_is_rejected(self) -> None:
        manifest, promotion = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        coverage = load_review_coverage(self.root)
        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        proof_path = (
            self.evidence_root
            / run["runtime_profile"]["configuration_proof"]["locator"]
        )
        backing = self.evidence_root / "evidence/configuration-backing.json"
        proof_path.rename(backing)
        proof_path.symlink_to(backing)
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "symlink",
        )

    def test_structural_schema_precedes_semantic_validation(self) -> None:
        self.run["schema_version"] = "9.9.9"
        self.run["created_at"] = "not-a-date"
        self.run["unknown_top_level"] = True
        self.run["target"]["year"] = True
        del self.run["authorisation"]["capacity"]
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "schema")
        self.assertErrorContains(errors, "schema_version")
        self.assertErrorContains(errors, "date-time")
        self.assertErrorContains(errors, "expected type integer|null")
        self.assertErrorContains(errors, "unknown_top_level")
        self.assertErrorContains(errors, "capacity")

        self.ledger["schema_version"] = "9.9.9"
        self.ledger["findings"][0]["unexpected"] = "bypass"
        errors = validate_finding_ledger(self.ledger, self.root)
        self.assertErrorContains(errors, "schema_version")
        self.assertErrorContains(errors, "unexpected")

    def test_substantive_task_requires_sol_ultra_leaf_and_no_fallback(self) -> None:
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        self.assertEqual(
            [],
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )
        task["requested_mode"] = "max"
        task["adapter_controlled_fallback"] = "not_applicable"
        task["leaf_only"] = False
        task["fork_policy"] = "full_history"
        task["descendant_state"] = "unknown"
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "gpt-5.6-sol + ultra")
        self.assertErrorContains(errors, "fallback")
        self.assertErrorContains(errors, "leaf-only")
        self.assertErrorContains(errors, "fork_policy none")
        self.assertErrorContains(errors, "descendant")

    def test_task_dependency_report_must_precede_child_dispatch(self) -> None:
        tasks = [
            {
                "task_id": "T-parent",
                "status": "completed",
                "dependency_task_ids": [],
            },
            {
                "task_id": "T-child",
                "status": "completed",
                "dependency_task_ids": ["T-parent"],
            },
        ]
        at = lambda second: datetime(  # noqa: E731
            2026, 7, 28, 12, 0, second, tzinfo=timezone.utc
        )
        self.assertErrorContains(
            _validate_task_dependency_chronology(
                tasks,
                {
                    "T-parent": at(0),
                    "T-child": at(1),
                },
                {
                    "T-parent": at(2),
                    "T-child": at(3),
                },
            ),
            "task dependency chronology",
        )
        self.assertEqual(
            [],
            _validate_task_dependency_chronology(
                tasks,
                {
                    "T-parent": at(0),
                    "T-child": at(2),
                },
                {
                    "T-parent": at(1),
                    "T-child": at(3),
                },
            ),
        )

    def test_completed_substantive_task_report_is_structured_and_identified(
        self,
    ) -> None:
        task = self.install_completed_task(task_effects=["format_report"])
        report_path = self.evidence_root / task["report_artifact"]
        report_path.write_bytes(b"x")
        task["report_sha256"] = hashlib.sha256(b"x").hexdigest()
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "unparsable",
        )

        task = self.install_completed_task(
            task_id="T-2",
            task_effects=["format_report"],
        )
        task["agent_or_task_identifier"] = None
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "runtime agent or task identifier",
        )

    def test_task_report_finding_ids_are_reconciled_both_directions(self) -> None:
        finding_id = self.ledger["findings"][0]["finding_id"]
        self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=["F-deadbeefdeadbeef"],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "references unknown finding ID",
        )

        task = self.install_completed_task(
            task_id="T-2",
            task_effects=["verify_finding"],
            finding_ids=[finding_id],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "not attributed to originating task",
        )

        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append("T-2")
        self.assertEqual([], self.validate_pair())

        omitted = copy.deepcopy(self.ledger["findings"][0])
        omitted["claim"] = "A second independently reported claim is unsupported."
        omitted["evidence"]["semantic_anchor"] = "claim:second"
        omitted["provenance"]["originating_task_ids"] = ["T-2"]
        omitted["finding_id"] = stable_finding_id(omitted)
        self.ledger["findings"].append(omitted)
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["finding_ids"].append(
            omitted["finding_id"]
        )
        self.assertErrorContains(
            self.validate_pair(),
            "absent from completed task report",
        )
        self.ledger["findings"].pop()
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["finding_ids"].pop()

        report_path = self.evidence_root / task["report_artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["finding_ids"] = []
        write_json(report_path, report)
        task["report_sha256"] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "finding contribution IDs",
        )

    def test_finding_operation_cannot_be_marked_non_substantive(self) -> None:
        task = self.install_completed_task(
            task_effects=["adjudicate_finding"],
            finding_ids=[self.ledger["findings"][0]["finding_id"]],
        )
        task["substantive"] = False
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "derived substantive",
        )

    def test_task_scope_report_evidence_and_limitations_are_reconciled(
        self,
    ) -> None:
        task = self.install_completed_task(task_effects=["format_report"])
        report_path = self.evidence_root / task["report_artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["evidence"][0]["artifact_id"] = "paper-pdf"
        report["limitations"] = [
            "A critical delegated evidence limitation remains."
        ]
        write_json(report_path, report)
        task["report_sha256"] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "exact mixed-input snapshot")
        self.assertErrorContains(errors, "not propagated to run limitations")

    def test_task_report_semantic_fields_cannot_be_whitespace(self) -> None:
        task = self.install_completed_task(task_effects=["format_report"])
        report_path = self.evidence_root / task["report_artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["summary"] = " \n\t"
        report["evidence"][0]["source_anchor"] = " \n\t"
        report["limitations"] = [" \n\t"]
        write_json(report_path, report)
        task["report_sha256"] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "summary")
        self.assertErrorContains(errors, "source_anchor")
        self.assertErrorContains(errors, "limitations")

    def test_blocked_adapter_cannot_certify_complete_or_unverified_task(
        self,
    ) -> None:
        task = self.install_completed_task(task_effects=["format_report"])
        runtime = self.run["runtime_profile"]
        runtime["compatibility_claim"] = "blocked"
        task["requested_model"] = None
        task["requested_mode"] = None
        task["requested_sandbox"] = None
        task["configuration_source"] = None
        task["configuration_proof"] = None
        task["adapter_controlled_fallback"] = "not_applicable"
        task["model_validation"] = validation_state()
        task["mode_validation"] = validation_state()
        task["sandbox_validation"] = validation_state()
        task["fork_policy"] = "full_history"
        task["leaf_only"] = False
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "blocked adapter compatibility")
        self.assertErrorContains(errors, "completed adapter task")

    def test_portable_core_can_record_delegation_without_codex_adapter(
        self,
    ) -> None:
        finding_id = self.ledger["findings"][0]["finding_id"]
        input_records = fixture_task_input_records(
            self.evidence_root,
            ["paper-source"],
        )
        input_snapshot_sha256 = fixture_input_snapshot_sha256(input_records)
        finding = self.ledger["findings"][0]
        task_evidence = {
            "input_id": "run:paper-source",
            "artifact_id": "paper-source",
            "source_anchor": finding["evidence"]["source_anchor"],
            "semantic_anchor": finding["evidence"]["semantic_anchor"],
            "observation": finding["evidence"]["observation"],
        }
        report_locator, report_sha = write_receipt(
            self.evidence_root,
            "reports/T-portable.json",
            {
                "schema_version": "1.0.0",
                "reported_at": "2026-07-28T12:00:02Z",
                "run_id": self.run["run_id"],
                "task_id": "T-portable",
                "agent_or_task_identifier": "portable-runtime-T-portable",
                "status": "completed",
                "task_effects": ["verify_finding"],
                "input_snapshot_sha256": input_snapshot_sha256,
                "configuration_receipt_sha256": None,
                "evidence": [task_evidence],
                "coverage_assessments": [
                    {
                        "criterion_id": "RC-CLAIM-EVIDENCE",
                        "applicability": "applicable",
                        "disposition": "finding_linked",
                        "evidence": [task_evidence],
                        "finding_ids": [finding_id],
                        "rationale":
                            "The portable task assessed the assigned criterion.",
                    }
                ],
                "finding_contributions": [
                    {
                        "effect": "verify_finding",
                        "finding_id": finding_id,
                        "criterion": finding["criterion"],
                        "claim": finding["claim"],
                        "artifact_id": "paper-source",
                        "source_anchor": finding["evidence"]["source_anchor"],
                        "semantic_anchor":
                            finding["evidence"]["semantic_anchor"],
                        "observation": finding["evidence"]["observation"],
                        "evidence_state": finding["evidence_state"],
                        "decision_impact": finding["decision_impact"],
                        "adjudication_status":
                            finding["adjudication_status"],
                        "rationale": finding["adjudication_rationale"],
                        "dissent": finding["dissent"],
                    }
                ],
                "finding_ids": [finding_id],
                "summary":
                    "Verified the bounded finding through a portable delegated "
                    "task.",
                "limitations": [],
            },
        )
        task = {
            "task_id": "T-portable",
            "substantive": True,
            "trigger": "A bounded independent finding verification is needed.",
            "assigned_criterion_ids": ["RC-CLAIM-EVIDENCE"],
            "task_effects": ["verify_finding"],
            "input_artifact_ids": ["paper-source"],
            "dependency_task_ids": [],
            "bundle_input_artifacts": [],
            "input_snapshot_sha256": input_snapshot_sha256,
            "report_contract": "schemas/task-report.schema.json",
            "stop_condition":
                "Return after the bounded portable verification is reported.",
            "requested_model": None,
            "requested_mode": None,
            "requested_sandbox": None,
            "configuration_source": None,
            "configuration_proof": None,
            "adapter_controlled_fallback": "not_applicable",
            "model_validation": validation_state(),
            "mode_validation": validation_state(),
            "sandbox_validation": validation_state(),
            "fork_policy": "not_applicable",
            "leaf_only": True,
            "descendant_state": "none",
            "agent_or_task_identifier": "portable-runtime-T-portable",
            "status": "completed",
            "terminal_reason": None,
            "report_artifact": report_locator,
            "report_sha256": report_sha,
        }
        self.run["runtime_profile"] = None
        self.run["delegation"]["tasks"] = [task]
        self.run["delegation"]["task_count_as_runtime_observation"] = 1
        risk = self.run["delegation"]["coverage_risk_map"][0]
        risk["delegation_decision"] = "delegate"
        risk["task_ids"] = ["T-portable"]
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["task_ids"] = ["T-portable"]
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append("T-portable")
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertEqual([], self.validate_pair())

    def test_risk_map_binds_canonical_criteria_and_real_tasks(self) -> None:
        risk = self.run["delegation"]["coverage_risk_map"][0]
        risk["criterion_id"] = "RC-INVENTED"
        risk["delegation_decision"] = "delegate"
        risk["task_ids"] = ["T-missing"]
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "criterion_id is not canonical")
        self.assertErrorContains(errors, "unknown delegated task ID")

        risk["criterion_id"] = "RC-CLAIM-EVIDENCE"
        risk["delegation_decision"] = "root_covers"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "root_covers decision cannot reference task IDs",
        )

    def test_configured_and_evaluated_requires_selected_promotion(self) -> None:
        self.run["runtime_profile"]["compatibility_claim"] = (
            "configured-and-evaluated"
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "promotion"
        )

    def test_valid_selected_promotion_enables_configured_claim(self) -> None:
        manifest, promotion = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        coverage = load_review_coverage(self.root)
        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        self.assertEqual(
            [],
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )

    def test_failed_wrong_or_stale_promotion_is_rejected(self) -> None:
        manifest, promotion = make_bundle(
            self.root,
            selected="minimal-settled-set",
            promotion_result="fail",
            promotion_decision="not_selected",
        )
        coverage = load_review_coverage(self.root)
        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        errors = validate_run_manifest(
            run,
            coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "promotion result")
        self.assertErrorContains(errors, "promotion decision")

        run["runtime_profile"]["promotion_evaluation_record"]["candidate_id"] = (
            "persisted-task-registry"
        )
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "candidate",
        )

    def test_promotion_locator_rejects_traversal_and_tamper(self) -> None:
        manifest, promotion = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        coverage = load_review_coverage(self.root)
        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        run["runtime_profile"]["promotion_evaluation_record"][
            "record_locator"
        ] = "../outside.json"
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "locator",
        )

        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
            evidence_root=self.evidence_root,
        )
        promotion_path = self.root / "compatibility/adapter-promotion.json"
        promotion_path.write_text("{}\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "promotion",
        )

    def test_adapter_digest_is_recomputed_from_actual_payload(self) -> None:
        self.assertEqual([], validate_adapter_manifest(self.manifest, self.root))
        path = self.root / "adapters/codex-gpt-5.6-sol-ultra.md"
        path.write_text("changed adapter\n", encoding="utf-8")
        self.assertErrorContains(
            validate_adapter_manifest(self.manifest, self.root),
            "adapter_payload_sha256",
        )

    def test_merged_finding_requires_existing_target_and_cannot_cover(self) -> None:
        merged = copy.deepcopy(self.ledger["findings"][0])
        merged["finding_id"] = "F-1111111111111111"
        merged["adjudication_status"] = "merged"
        merged["adjudication_rationale"] = "Semantically duplicate."
        merged["provenance"]["merged_from_ids"] = ["F-source-candidate"]
        merged["provenance"]["merged_into_finding_id"] = "F-does-not-exist"
        self.ledger["findings"].append(merged)
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["finding_ids"].append(
            merged["finding_id"]
        )
        errors = self.validate_pair()
        self.assertErrorContains(errors, "merged finding cannot satisfy coverage")
        self.assertErrorContains(errors, "merge target does not exist")

    def test_complete_status_requires_completed_stages_and_tasks(self) -> None:
        self.run["stages"][0]["status"] = "blocked"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "stage",
        )

        self.run["stages"][0]["status"] = "complete"
        input_records = fixture_task_input_records(
            self.evidence_root,
            ["paper-source"],
        )
        task = {
            "task_id": "T-failed",
            "substantive": True,
            "trigger": "Material independent verification.",
            "assigned_criterion_ids": ["RC-CLAIM-EVIDENCE"],
            "task_effects": ["verify_finding"],
            "input_artifact_ids": ["paper-source"],
            "dependency_task_ids": [],
            "bundle_input_artifacts": [],
            "input_snapshot_sha256":
                fixture_input_snapshot_sha256(input_records),
            "report_contract": "schemas/task-report.schema.json",
            "stop_condition": "Stop after the requested verification attempt.",
            "requested_model": "gpt-5.6-sol",
            "requested_mode": "ultra",
            "requested_sandbox": "read-only",
            "configuration_source": "adapter-controlled dispatch",
            "configuration_proof": None,
            "adapter_controlled_fallback": "prohibited_and_checked",
            "model_validation": validation_state(),
            "mode_validation": validation_state(),
            "sandbox_validation": validation_state(),
            "fork_policy": "none",
            "leaf_only": True,
            "descendant_state": "none",
            "agent_or_task_identifier": "runtime-T-failed",
            "status": "failed",
            "terminal_reason": "The delegated verification failed.",
            "report_artifact": None,
            "report_sha256": None,
        }
        self.run["delegation"]["tasks"] = [task]
        self.run["delegation"]["task_count_as_runtime_observation"] = 1
        self.run["delegation"]["coverage_risk_map"][0][
            "delegation_decision"
        ] = "delegate"
        self.run["delegation"]["coverage_risk_map"][0]["task_ids"] = [
            "T-failed"
        ]
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["task_ids"] = ["T-failed"]
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "failed",
        )

    def test_artifact_and_stage_identifiers_are_unique(self) -> None:
        self.run["input_artifacts"].append(
            copy.deepcopy(self.run["input_artifacts"][0])
        )
        self.run["stages"].append(copy.deepcopy(self.run["stages"][0]))
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "duplicate artifact_id")
        self.assertErrorContains(errors, "duplicate stage_id")

    def test_finding_lineage_matches_referenced_artifact(self) -> None:
        finding = self.ledger["findings"][0]
        finding["provenance"]["primary_artifact_lineage_id"] = (
            "invented-lineage"
        )
        finding["finding_id"] = stable_finding_id(finding)
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["finding_ids"] = [
            finding["finding_id"]
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "provenance lineage does not match artifact",
        )

    def test_coverage_link_must_match_finding_criterion(self) -> None:
        self.run["coverage"]["criteria"][0]["disposition"] = "finding_linked"
        self.run["coverage"]["criteria"][0]["finding_ids"] = [
            self.ledger["findings"][0]["finding_id"]
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "criterion does not match",
        )

    def test_merge_target_must_be_a_surviving_canonical_finding(self) -> None:
        target = self.ledger["findings"][0]
        target["adjudication_status"] = "rejected"
        target["decision_impact"] = "none"
        target["action_type"] = "no-action"
        merged = copy.deepcopy(target)
        merged["finding_id"] = "F-1111111111111111"
        merged["adjudication_status"] = "merged"
        merged["adjudication_rationale"] = "Duplicate of the rejected row."
        merged["provenance"]["merged_from_ids"] = ["F-source-candidate"]
        merged["provenance"]["merged_into_finding_id"] = target["finding_id"]
        self.ledger["findings"].append(merged)
        claim_row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        claim_row["finding_ids"] = []
        claim_row["disposition"] = (
            "assessed_no_finding"
        )
        self.assertErrorContains(
            self.validate_pair(),
            "merge target is not canonical",
        )

    def test_valid_merge_has_disposed_source_and_reciprocal_target(self) -> None:
        target = self.ledger["findings"][0]
        merged = copy.deepcopy(target)
        merged["claim"] = "A duplicate wording of the same bounded concern."
        merged["evidence"]["semantic_anchor"] = "claim:duplicate-wording"
        merged["finding_id"] = stable_finding_id(merged)
        merged["adjudication_status"] = "merged"
        merged["adjudication_rationale"] = (
            "The source row duplicates the retained canonical concern."
        )
        merged["decision_impact"] = "none"
        merged["action_type"] = "no-action"
        merged["closure_requirement"] = {
            "state": "not_applicable",
            "owner": "none",
            "gate": "none",
            "requirement": None,
            "resolution_evidence": None,
        }
        merged["provenance"]["merged_from_ids"] = [merged["finding_id"]]
        merged["provenance"]["merged_into_finding_id"] = target["finding_id"]
        target["provenance"]["merged_from_ids"] = [merged["finding_id"]]
        self.ledger["findings"].append(merged)
        self.assertEqual([], self.validate_pair())

        target["provenance"]["merged_from_ids"] = []
        self.assertErrorContains(
            self.validate_pair(),
            "does not reciprocally record source",
        )

    def test_complete_ledger_rejects_unresolved_dissent_and_empty_origin(
        self,
    ) -> None:
        finding = self.ledger["findings"][0]
        finding["dissent"] = {
            "state": "unresolved",
            "summary": "Material evidence remains in dispute.",
        }
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "unresolved evidence prevents complete ledger status",
        )
        finding["dissent"] = {"state": "none", "summary": None}
        finding["provenance"]["originating_task_ids"] = []
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "originating_task_ids",
        )

    def test_dissent_state_and_summary_must_be_consistent(self) -> None:
        finding = self.ledger["findings"][0]
        finding["dissent"] = {
            "state": "none",
            "summary": "A material conflict remains.",
        }
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "summary",
        )

    def test_non_root_finding_origin_must_be_finding_effect_task(self) -> None:
        self.install_completed_task(
            task_effects=["format_report"],
            finding_ids=[],
        )
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append("T-1")
        self.assertErrorContains(
            self.validate_pair(),
            "finding origin is not a finding-effect task",
        )

    def test_failed_task_cannot_be_a_finding_origin(self) -> None:
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[],
        )
        task["status"] = "failed"
        task["terminal_reason"] = "The bounded task failed before reporting."
        task["report_artifact"] = None
        task["report_sha256"] = None
        self.set_completion("partial")
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append(task["task_id"])
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "finding origin is not a finding-effect task with completed report",
        )

    def test_finding_capable_task_may_return_no_supported_finding(self) -> None:
        self.install_completed_task(
            task_effects=["add_finding"],
            finding_ids=[],
        )
        finding_id = self.ledger["findings"][0]["finding_id"]
        run_coverage_row(
            self.run,
            "RC-CLAIM-EVIDENCE",
        )["task_reconciliations"] = [
            {
                "task_id": "T-1",
                "task_applicability": "applicable",
                "task_disposition": "assessed_no_finding",
                "task_finding_ids": [],
                "canonical_applicability": "applicable",
                "canonical_disposition": "finding_linked",
                "canonical_finding_ids": [finding_id],
                "outcome": "canonical_overrides",
                "dissent_state": "recorded",
                "rationale":
                    "The root retained independently verified source evidence "
                    "that the bounded task did not establish or rebut.",
            }
        ]
        self.assertEqual([], self.validate_pair())

    def test_task_coverage_difference_requires_typed_reconciliation(
        self,
    ) -> None:
        self.install_completed_task(
            task_effects=["add_finding"],
            finding_ids=[],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "requires one exact typed reconciliation",
        )

    def test_orphan_and_same_tuple_reconciliations_are_rejected(self) -> None:
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["task_reconciliations"] = [
            {
                "task_id": "T-never-existed",
                "task_applicability": "applicable",
                "task_disposition": "assessed_no_finding",
                "task_finding_ids": [],
                "canonical_applicability": "applicable",
                "canonical_disposition": "finding_linked",
                "canonical_finding_ids": [
                    self.ledger["findings"][0]["finding_id"]
                ],
                "outcome": "unresolved",
                "dissent_state": "unresolved",
                "rationale":
                    "This fabricated row has no completed task assessment "
                    "and therefore cannot reconcile canonical coverage.",
            }
        ]
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "bind one completed task assessment")
        self.assertErrorContains(
            errors,
            "unresolved task reconciliation prevents complete status",
        )

        self.reset_valid_pair()
        finding_id = self.ledger["findings"][0]["finding_id"]
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[finding_id],
        )
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append(task["task_id"])
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["task_reconciliations"] = [
            {
                "task_id": task["task_id"],
                "task_applicability": "applicable",
                "task_disposition": "finding_linked",
                "task_finding_ids": [finding_id],
                "canonical_applicability": "applicable",
                "canonical_disposition": "finding_linked",
                "canonical_finding_ids": [finding_id],
                "outcome": "canonical_overrides",
                "dissent_state": "recorded",
                "rationale":
                    "An unnecessary reconciliation must not be accepted when "
                    "the task and canonical tuples already agree exactly.",
            }
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "forbidden when task and canonical coverage agree",
        )

    def test_task_contribution_cannot_exceed_assigned_criterion(self) -> None:
        finding_id = self.ledger["findings"][0]["finding_id"]
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[finding_id],
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["finding_contributions"][0]["criterion"] = (
            "RC-METHOD-SOUNDNESS"
        )
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "exceeds the task's assigned criteria",
        )

    def test_nonadjudicating_task_cannot_change_impact_silently(self) -> None:
        finding_id = self.ledger["findings"][0]["finding_id"]
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[finding_id],
        )
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append(task["task_id"])
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["finding_contributions"][0]["decision_impact"] = "fundamental"
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "changes decision_impact without preserved dissent",
        )

    def test_nonadjudicating_task_conflict_requires_preserved_dissent(
        self,
    ) -> None:
        finding_id = self.ledger["findings"][0]["finding_id"]
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[finding_id],
        )
        self.ledger["findings"][0]["provenance"][
            "originating_task_ids"
        ].append(task["task_id"])
        report_path = self.evidence_root / task["report_artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["finding_contributions"][0][
            "adjudication_status"
        ] = "rejected"
        write_json(report_path, report)
        task["report_sha256"] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "conflicts with canonical finding without preserved dissent",
        )

    def test_unresolved_task_assessment_propagates_to_run_completion(
        self,
    ) -> None:
        task = self.install_completed_task(
            task_effects=["format_report"],
            finding_ids=[],
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["coverage_assessments"][0]["disposition"] = "blocked"
        report["coverage_assessments"][0]["rationale"] = (
            "The delegated evidence could not be verified."
        )
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "unresolved task assessment",
        )

    def test_task_assessment_disposition_matches_its_finding_ids(self) -> None:
        task = self.install_completed_task(
            task_effects=["add_finding"],
            finding_ids=[],
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["coverage_assessments"][0]["finding_ids"] = [
            self.ledger["findings"][0]["finding_id"]
        ]
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "assessed_no_finding cannot link findings",
        )

    def test_task_contribution_cannot_hide_unresolved_evidence_or_dissent(
        self,
    ) -> None:
        finding = self.ledger["findings"][0]
        task = self.install_completed_task(
            task_effects=["verify_finding"],
            finding_ids=[finding["finding_id"]],
        )
        finding["provenance"]["originating_task_ids"].append(task["task_id"])
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        contribution = report["finding_contributions"][0]
        contribution["evidence_state"] = "needs_verification"
        contribution["dissent"] = {
            "state": "unresolved",
            "summary": "The delegated evidence remains disputed.",
        }
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        errors = self.validate_pair()
        self.assertErrorContains(
            errors,
            "task finding contribution changes evidence_state",
        )
        self.assertErrorContains(
            errors,
            "task finding contribution changes dissent",
        )

    def test_adapter_manifest_mapping_and_selected_allowlist_are_fixed(self) -> None:
        manifest, _ = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        manifest["candidate_implementations"]["minimal-settled-set"] = (
            MAPPING["persisted-task-registry"]
        )
        errors = validate_adapter_manifest(manifest, self.root)
        self.assertErrorContains(
            errors,
            "candidate_implementations.minimal-settled-set",
        )

        manifest, _ = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        manifest["active_files"].append(MAPPING["persisted-task-registry"])
        errors = validate_adapter_manifest(manifest, self.root)
        self.assertErrorContains(errors, "unselected lifecycle implementation")

    def test_adapter_manifest_rejects_control_characters_in_locator(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["active_files"].append("adapters/x\ninjected")
        errors = validate_adapter_manifest(manifest, self.root)
        self.assertErrorContains(errors, "pattern")

    def test_runtime_attestation_requires_surfaced_matching_telemetry(self) -> None:
        manifest, promotion = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        coverage = load_review_coverage(self.root)
        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="runtime-attested",
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "offline validator cannot verify runtime attestation",
        )
        run["runtime_profile"]["effective_telemetry"] = "not_surfaced"
        run["runtime_profile"]["resolved_model"] = None
        run["runtime_profile"]["resolved_mode"] = None
        self.assertErrorContains(
            validate_run_manifest(
                run,
                coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "runtime attestation",
        )

    def test_downgrade_belongs_only_to_impact_change(self) -> None:
        self.ledger["findings"][0]["adjudication_status"] = "downgraded"
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "adjudication_status",
        )

    def test_known_venue_profile_is_resolved_and_byte_bound(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        self.assertEqual(
            [],
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
        )
        profile_path = (
            self.root
            / self.run["venue_profile"]["profile_locator"]
        )
        profile_path.write_text("{}\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "venue profile hash mismatch",
        )

    def test_venue_rules_hosts_and_native_scales_are_fail_closed(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            statement=" \n\t",
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "statement",
        )

        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            source_url="https://evil.example/pretend-official",
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "not approved by the release authority registry",
        )

        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[
                {
                    "field_id": "overall-score",
                    "role": "reviewer",
                    "field_type": "integer_scale",
                    "prompt": "Provide the venue-native overall score.",
                    "required": True,
                    "minimum": 10,
                    "maximum": 1,
                    "allowed_labels": ["accept"],
                    "anchors": [
                        {"value": 11, "label": "outside scale"}
                    ],
                    "source_ids": ["reviewer-instructions"],
                }
            ],
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "numeric native field requires ordered bounds",
        )

    def test_venue_hash_and_url_patterns_reject_terminal_newline(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        source_path = (
            self.root
            / self.run["venue_profile"]["source_manifest_locator"]
        )
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["sources"][0]["url"] += "\n"
        source["sources"][0]["content_sha256"] = HEX_A + "\n"
        write_json(source_path, source)
        source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        profile_path = (
            self.root / self.run["venue_profile"]["profile_locator"]
        )
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["source_sha256"] = source_sha
        write_json(profile_path, profile)
        self.run["venue_profile"]["source_sha256"] = source_sha
        self.run["venue_profile"]["profile_sha256"] = hashlib.sha256(
            profile_path.read_bytes()
        ).hexdigest()
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "url")
        self.assertErrorContains(errors, "content_sha256")

    def test_artifact_roles_reject_empty_aliases_and_hardlinks(self) -> None:
        source = self.run["input_artifacts"][0]
        source_path = self.evidence_root / source["locator"]
        source_path.write_bytes(b"")
        source["sha256"] = hashlib.sha256(b"").hexdigest()
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "frozen input cannot be empty",
        )

        run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        run["input_artifacts"][1]["locator"] = (
            run["input_artifacts"][0]["locator"]
        )
        run["input_artifacts"][1]["sha256"] = (
            run["input_artifacts"][0]["sha256"]
        )
        self.assertErrorContains(
            validate_run_manifest(
                run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "aliases artifact",
        )

        run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        source = run["input_artifacts"][0]
        output = run["output_artifacts"]["reviewer_report"]
        output["locator"] = source["locator"]
        output["sha256"] = source["sha256"]
        self.assertErrorContains(
            validate_run_manifest(
                run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "aliases frozen input",
        )

        run = run_fixture(
            self.coverage,
            self.manifest,
            self.promotion,
            evidence_root=self.evidence_root,
        )
        active_file = self.root / "adapters/codex-gpt-5.6-sol-ultra.md"
        hardlink = self.evidence_root / "hardlinked-review.md"
        os.link(active_file, hardlink)
        output = run["output_artifacts"]["reviewer_report"]
        output["locator"] = "hardlinked-review.md"
        output["sha256"] = hashlib.sha256(
            hardlink.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            validate_run_manifest(
                run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "hard-linked",
        )

    def test_evidence_locator_cannot_be_reused_across_roles(self) -> None:
        runtime = self.run["runtime_profile"]
        runtime["configuration_proof"]["locator"] = "paper/main.tex"
        runtime["configuration_proof"]["sha256"] = (
            self.run["input_artifacts"][0]["sha256"]
        )
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "reused across roles",
        )

    def test_finding_ledger_output_must_equal_supplied_ledger(self) -> None:
        recorded = copy.deepcopy(self.ledger)
        recorded["findings"] = []
        output = self.run["output_artifacts"]["finding_ledger"]
        path = self.evidence_root / output["locator"]
        write_json(path, recorded)
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "differs from the byte-bound finding-ledger output",
        )

    def test_complete_stage_evidence_must_resolve(self) -> None:
        self.run["stages"][0]["evidence"] = [
            {
                "kind": "input_artifact",
                "reference": "invented-evidence-id",
                "source_anchor": "invented",
            }
        ]
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "does not resolve to a frozen artifact",
        )

    def test_coverage_evidence_anchor_must_be_nonblank(self) -> None:
        run_coverage_row(
            self.run, "RC-CLAIM-EVIDENCE"
        )["evidence"][0]["source_anchor"] = " \n\t"
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "source_anchor",
        )

    def test_human_views_bind_ledger_coverage_and_limitations(self) -> None:
        ae_raw = human_output_bytes(
            "ae_assessment",
            run_id=self.run["run_id"],
            completion=self.run["completion"],
        )
        ae_path = self.evidence_root / "ae-assessment.md"
        ae_path.write_bytes(ae_raw)
        self.run["output_artifacts"]["ae_assessment"][
            "sha256"
        ] = hashlib.sha256(ae_raw).hexdigest()
        errors = validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "AE assessment omits surviving finding")
        self.assertErrorContains(errors, "omits canonical criterion")

        self.sync_ledger_output()
        self.run["limitations"] = ["A bounded external check was unavailable."]
        summary_raw = human_output_bytes(
            "review_summary",
            run_id=self.run["run_id"],
            completion=self.run["completion"],
            criterion_ids=[
                row["criterion_id"]
                for row in self.run["coverage"]["criteria"]
            ],
            finding_ids=[self.ledger["findings"][0]["finding_id"]],
        )
        summary_path = self.evidence_root / "review-summary.md"
        summary_path.write_bytes(summary_raw)
        self.run["output_artifacts"]["review_summary"][
            "sha256"
        ] = hashlib.sha256(summary_raw).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "omits run limitation",
        )

    def test_locator_control_characters_are_rejected(self) -> None:
        for suffix in ("\n", "\t", "\x7f"):
            with self.subTest(suffix=repr(suffix)):
                run = copy.deepcopy(self.run)
                run["input_artifacts"][0]["locator"] = (
                    "paper/main.tex" + suffix
                )
                self.assertErrorContains(
                    validate_run_manifest(
                        run,
                        self.coverage,
                        self.root,
                        evidence_root=self.evidence_root,
                    ),
                    "control characters",
                )

    def test_loader_only_accepts_canonical_manifest_and_promotion_paths(self) -> None:
        loaded = load_adapter_manifest(self.root)
        self.assertEqual(self.manifest, loaded)
        with self.assertRaises(ValueError):
            load_adapter_promotion(self.root, "../promotion.json")

    def test_finding_evidence_must_resolve_to_frozen_bytes(self) -> None:
        self.set_completion("partial")
        self.run["input_artifacts"].append(
            {
                "artifact_id": "declared-only",
                "kind": "supplement",
                "lineage_id": "declared-v1",
                "state": "declared",
                "locator": "paper/not-provided.txt",
                "sha256": None,
            }
        )
        finding = self.ledger["findings"][0]
        finding["evidence"]["artifact_id"] = "declared-only"
        finding["provenance"]["primary_artifact_lineage_id"] = "declared-v1"
        finding["finding_id"] = stable_finding_id(finding)
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["finding_ids"] = [finding["finding_id"]]
        row["evidence"][0]["artifact_id"] = "declared-only"
        self.assertErrorContains(self.validate_pair(), "frozen artifact")

    def test_source_only_cannot_settle_visual_integrity(self) -> None:
        self.run["input_artifacts"] = [
            item
            for item in self.run["input_artifacts"]
            if item["kind"] != "pdf"
        ]
        self.run["source_pdf_alignment"] = {
            "status": "source_only_verified",
            "verified": True,
            "evidence": "Only source bytes were available.",
            "source_artifact_id": "paper-source",
            "pdf_artifact_id": None,
            "receipt_locator": None,
            "receipt_sha256": None,
        }
        self.assertErrorContains(
            self.validate_pair(),
            "visual integrity",
        )

    def test_source_only_alignment_rejects_multiple_frozen_sources(
        self,
    ) -> None:
        self.run["input_artifacts"] = [
            item
            for item in self.run["input_artifacts"]
            if item["kind"] != "pdf"
        ]
        path = self.evidence_root / "paper/other.tex"
        path.write_text("distinct secondary source\n", encoding="utf-8")
        self.run["input_artifacts"].append(
            {
                "artifact_id": "other-source",
                "kind": "source",
                "lineage_id": "paper-v2",
                "state": "frozen",
                "locator": "paper/other.tex",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        self.run["source_pdf_alignment"] = {
            "status": "source_only_verified",
            "verified": True,
            "evidence": "Only source bytes were available.",
            "source_artifact_id": "paper-source",
            "pdf_artifact_id": None,
            "receipt_locator": None,
            "receipt_sha256": None,
        }
        for criterion_id in (
            "RC-INPUT-ALIGNMENT",
            "RC-INPUT-VERIFIABILITY",
            "RC-VISUAL-INTEGRITY",
        ):
            row = run_coverage_row(self.run, criterion_id)
            row["applicability"] = "inapplicable"
            row["disposition"] = "not_applicable"
            row["evidence"] = []
            row["finding_ids"] = []
            row["rationale"] = (
                "No PDF was supplied, so this PDF-specific duty does not apply."
            )
        self.assertErrorContains(
            self.validate_pair(),
            "exactly one frozen source",
        )

    def test_matched_alignment_rejects_ambiguous_extra_primary_source(self) -> None:
        path = self.evidence_root / "paper/other.tex"
        path.write_text("unmatched source\n", encoding="utf-8")
        self.run["input_artifacts"].append(
            {
                "artifact_id": "other-source",
                "kind": "source",
                "lineage_id": "paper-v2",
                "state": "frozen",
                "locator": "paper/other.tex",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
        self.assertErrorContains(self.validate_pair(), "unique source/PDF pair")

    def test_distinct_roles_reject_identical_content_hashes(self) -> None:
        source = self.evidence_root / "paper/main.tex"
        pdf = self.evidence_root / "paper/main.pdf"
        pdf.write_bytes(source.read_bytes())
        pdf_record = next(
            item
            for item in self.run["input_artifacts"]
            if item["artifact_id"] == "paper-pdf"
        )
        pdf_record["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "source and PDF content must be distinct",
        )

        self.reset_valid_pair()
        union = (
            "# Independent Reviewer Report\n"
            "# Adjudicated Assessment\n"
            "# Review Summary\n"
            "## Provenance\n"
            f"- Run ID: {self.run['run_id']}\n"
            f"- Completion: {self.run['completion']}\n"
            + "\n".join(
                f"- Criterion: {row['criterion_id']}"
                for row in self.run["coverage"]["criteria"]
            )
            + f"\n- Finding: {self.ledger['findings'][0]['finding_id']}\n"
            "## Criterion assessment\n"
            "## Candidate findings\n"
            "## Strengths and clean controls\n"
            "## Limitations and non-claims\n"
            "## Candidate disposition\n"
            "## Canonical coverage\n"
            "## Portable assessment\n"
            "## Target-conditioned assessment\n"
            "## Completion and non-claims\n"
            "## Outcome\n"
            "## Most decision-relevant findings\n"
            "## Strengths\n"
            "## Coverage and dissent\n"
            "## Author and readiness gates\n"
            "## Next boundary\n"
            + ("role-bound evidence text " * 24)
        ).encode("utf-8")
        for name in ("reviewer_report", "ae_assessment", "review_summary"):
            output = self.run["output_artifacts"][name]
            path = self.evidence_root / output["locator"]
            path.write_bytes(union)
            output["sha256"] = hashlib.sha256(union).hexdigest()
        errors = validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "human output content is reused")

    def test_carried_delta_preserves_semantic_identity_and_impact_change(self) -> None:
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["claim"] = "A different unrelated defect is now alleged."
        self.assertErrorContains(self.validate_pair(), "semantic identity")

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["decision_impact"] = "fundamental"
        finding["impact_change"] = "unchanged"
        self.assertErrorContains(self.validate_pair(), "derived impact_change")

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["provenance"]["primary_artifact_lineage_id"] = "stolen-lineage"
        self.assertErrorContains(
            self.validate_pair(),
            "primary artifact lineage",
        )

    def test_merge_graph_rejects_nonexistent_target_side_source(self) -> None:
        finding = self.ledger["findings"][0]
        finding["provenance"]["merged_from_ids"] = [
            "F-deadbeefdeadbeef"
        ]
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "merged_from_ids",
        )

    def test_surviving_material_finding_requires_actionable_closure(self) -> None:
        finding = self.ledger["findings"][0]
        finding["action_type"] = "no-action"
        finding["closure_requirement"] = {
            "state": "not_applicable",
            "owner": "none",
            "gate": "none",
            "requirement": None,
            "resolution_evidence": None,
        }
        self.assertErrorContains(
            validate_finding_ledger(self.ledger, self.root),
            "material obligation",
        )

    def test_failed_delegation_and_blocked_risk_cannot_look_settled(self) -> None:
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        self.set_completion("partial")
        task["status"] = "failed"
        task["configuration_proof"] = None
        task["model_validation"] = validation_state()
        task["mode_validation"] = validation_state()
        task["sandbox_validation"] = validation_state()
        task["report_artifact"] = None
        task["report_sha256"] = None
        self.assertErrorContains(
            self.validate_pair(),
            "failed delegated task",
        )

        self.reset_valid_pair()
        self.set_completion("partial")
        risk = self.run["delegation"]["coverage_risk_map"][0]
        risk["delegation_decision"] = "blocked"
        self.assertErrorContains(
            self.validate_pair(),
            "blocked risk requires blocked coverage",
        )

    def test_prohibited_policy_is_a_preflight_stop(self) -> None:
        self.set_completion("blocked")
        self.run["authorisation"]["policy_status"] = "prohibited"
        self.assertErrorContains(
            self.validate_pair(),
            "preflight stop",
        )

    def test_closed_preflight_cannot_classify_scientific_work_inapplicable(
        self,
    ) -> None:
        self.set_completion("blocked")
        self.run["authorisation"]["policy_status"] = "prohibited"
        row = run_coverage_row(self.run, "RC-PROBLEM-FORMULATION")
        row["applicability"] = "inapplicable"
        row["disposition"] = "not_applicable"
        row["evidence"] = []
        row["finding_ids"] = []
        row["rationale"] = (
            "The protected scientific content was not inspected."
        )
        self.assertErrorContains(
            self.validate_pair(),
            "preflight stop cannot classify scientific criterion",
        )

    def test_human_views_reject_contradictory_metadata_and_malformed_ids(
        self,
    ) -> None:
        self.sync_ledger_output()
        output = self.run["output_artifacts"]["review_summary"]
        path = self.evidence_root / output["locator"]
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\n- Run ID: RUN-OTHER\n- Completion: blocked\n",
            encoding="utf-8",
        )
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        errors = validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "exactly one Run ID")
        self.assertErrorContains(errors, "exactly one Completion")

        self.sync_ledger_output()
        finding_id = self.ledger["findings"][0]["finding_id"]
        for name in ("ae_assessment", "review_summary"):
            output = self.run["output_artifacts"][name]
            path = self.evidence_root / output["locator"]
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    finding_id,
                    finding_id + "-bogus",
                ),
                encoding="utf-8",
            )
            output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        errors = validate_run_pair(
            self.run,
            self.ledger,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertErrorContains(errors, "malformed finding ID")

    def test_venue_rejects_fractional_integer_scale_and_invalid_port(self) -> None:
        native_field = {
            "field_id": "confidence",
            "role": "reviewer",
            "field_type": "integer_scale",
            "prompt": "Confidence",
            "required": True,
            "minimum": 1.5,
            "maximum": 5.5,
            "allowed_labels": [],
            "anchors": [{"value": 2.5, "label": "Fractional"}],
            "source_ids": ["reviewer-instructions"],
        }
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[native_field],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "integer native field",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            source_url="https://icml.cc:not-a-port/pretend",
        )
        self.assertErrorContains(
            self.validate_pair(),
            "invalid HTTPS authority",
        )

    def test_selected_adapter_cannot_remain_evaluation_pending(self) -> None:
        manifest, promotion = make_bundle(
            self.root,
            selected="minimal-settled-set",
        )
        self.manifest = manifest
        self.promotion = promotion
        self.run = run_fixture(
            self.coverage,
            manifest,
            None,
            compatibility="evaluation_pending",
            evidence_root=self.evidence_root,
        )
        self.ledger = ledger_fixture()
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["disposition"] = "finding_linked"
        row["finding_ids"] = [self.ledger["findings"][0]["finding_id"]]
        self.assertErrorContains(
            self.validate_pair(),
            "selected adapter requires configured-and-evaluated",
        )

    def test_task_configuration_binds_identifier_fork_leaf_and_input_snapshot(
        self,
    ) -> None:
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        task["agent_or_task_identifier"] = "runtime-other"
        task["fork_policy"] = "full_history"
        task["leaf_only"] = False
        errors = self.validate_pair()
        self.assertErrorContains(errors, "agent_or_task_identifier")
        self.assertErrorContains(errors, "fork_policy")
        self.assertErrorContains(errors, "leaf_only")

        self.reset_valid_pair()
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        source = self.evidence_root / "paper/main.tex"
        source.write_bytes(source.read_bytes() + b"\nchanged after dispatch\n")
        source_record = next(
            item
            for item in self.run["input_artifacts"]
            if item["artifact_id"] == "paper-source"
        )
        source_record["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "input_snapshot_sha256",
        )

    def test_terminal_inventory_is_exact_and_cannot_hide_a_task(self) -> None:
        self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        inventory = self.run["delegation"]["terminal_inventory"]
        path = self.evidence_root / inventory["locator"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["tasks"] = []
        write_json(path, receipt)
        inventory["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "terminal task inventory",
        )

        self.reset_valid_pair()
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        report_path = self.evidence_root / task["report_artifact"]
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["reported_at"] = "2026-07-28T11:59:59Z"
        write_json(report_path, report)
        task["report_sha256"] = hashlib.sha256(
            report_path.read_bytes()
        ).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "task report chronology",
        )

        self.reset_valid_pair()
        self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        inventory = self.run["delegation"]["terminal_inventory"]
        inventory_path = self.evidence_root / inventory["locator"]
        receipt = json.loads(
            inventory_path.read_text(encoding="utf-8")
        )
        receipt["recorded_at"] = "2026-07-28T12:00:01Z"
        write_json(inventory_path, receipt)
        inventory["sha256"] = hashlib.sha256(
            inventory_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "inventory chronology",
        )

        self.reset_valid_pair()
        self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        self.run["delegation"]["tasks"] = []
        self.run["delegation"]["task_count_as_runtime_observation"] = 0
        self.assertErrorContains(
            self.validate_pair(),
            "terminal task inventory",
        )

    def test_terminal_inventory_builder_derives_canonical_rows(self) -> None:
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        run_path = self.evidence_root / "run-for-inventory.json"
        write_json(run_path, self.run)
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_terminal_inventory.py"),
                "--bundle-root",
                str(ROOT),
                "--recorded-at",
                "2026-07-28T12:30:00Z",
                str(run_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        inventory = json.loads(completed.stdout)
        self.assertEqual(inventory["run_id"], self.run["run_id"])
        self.assertEqual(
            inventory["tasks"],
            [
                {
                    "task_id": task["task_id"],
                    "agent_or_task_identifier":
                        task["agent_or_task_identifier"],
                    "status": task["status"],
                    "report_artifact": task["report_artifact"],
                    "report_sha256": task["report_sha256"],
                    "descendant_state": task["descendant_state"],
                    "terminal_reason": task["terminal_reason"],
                }
            ],
        )
        self.assertEqual(
            completed.stdout.encode("utf-8"),
            canonical_bytes(inventory),
        )

    def test_future_configuration_cannot_precede_validation_or_inventory(
        self,
    ) -> None:
        proof = self.run["runtime_profile"]["configuration_proof"]
        path = self.evidence_root / proof["locator"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["recorded_at"] = "2026-07-28T13:00:00Z"
        write_json(path, receipt)
        proof["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        errors = validate_run_manifest(
            self.run,
            self.coverage,
            self.root,
            evidence_root=self.evidence_root,
        )
        self.assertTrue(
            any("chronology" in error for error in errors),
            errors,
        )

    def test_task_report_requires_assessments_and_semantic_contributions(
        self,
    ) -> None:
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["coverage_assessments"] = []
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "coverage_assessments",
        )

        self.reset_valid_pair()
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["finding_contributions"] = []
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "finding contribution",
        )

        self.reset_valid_pair()
        task = self.install_completed_task(
            finding_ids=[self.ledger["findings"][0]["finding_id"]]
        )
        path = self.evidence_root / task["report_artifact"]
        report = json.loads(path.read_text(encoding="utf-8"))
        report["finding_contributions"][0]["claim"] = (
            "A semantically different claim."
        )
        write_json(path, report)
        task["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        install_terminal_inventory(self.evidence_root, self.run)
        self.assertErrorContains(
            self.validate_pair(),
            "normalised claim",
        )

    def test_adapter_risk_map_must_cover_every_canonical_criterion(self) -> None:
        self.run["delegation"]["coverage_risk_map"].pop()
        self.assertErrorContains(
            self.validate_pair(),
            "exactly cover all canonical criteria",
        )

    def test_partial_and_blocked_completion_require_matching_barriers(self) -> None:
        self.run["completion"] = "partial"
        self.ledger["completion"] = "partial"
        self.run["limitations"] = []
        self.assertErrorContains(
            self.validate_pair(),
            "partial completion requires",
        )

        self.reset_valid_pair()
        self.run["completion"] = "blocked"
        self.ledger["completion"] = "blocked"
        self.run["limitations"] = ["No actual blocked responsibility exists."]
        self.assertErrorContains(
            self.validate_pair(),
            "blocked completion requires",
        )

    def test_alignment_coverage_and_finding_anchors_are_byte_bound(self) -> None:
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["source_sha256"] = HEX_A
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "does not bind the frozen pair",
        )

        self.reset_valid_pair()
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        evidence = row["evidence"][0]
        evidence["excerpt"] = "This sentence is not in the frozen source."
        evidence["excerpt_sha256"] = hashlib.sha256(
            evidence["excerpt"].encode("utf-8")
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "excerpt is absent from the frozen source",
        )

        self.reset_valid_pair()
        verification = self.ledger["findings"][0]["evidence"][
            "anchor_verification"
        ]
        verification["excerpt"] = "A fabricated anchor that is absent."
        verification["excerpt_sha256"] = hashlib.sha256(
            verification["excerpt"].encode("utf-8")
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "finding anchor excerpt is absent",
        )

    def test_alignment_requires_the_same_source_and_pdf_excerpt(self) -> None:
        alignment = self.run["source_pdf_alignment"]
        path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["checks"][0]["pdf_excerpt"] = "Introduction"
        receipt["checks"][0]["pdf_excerpt_sha256"] = hashlib.sha256(
            b"Introduction"
        ).hexdigest()
        write_json(path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "source and PDF excerpts do not establish the same check",
        )

    def test_exact_anchors_require_a_canonical_span_and_meaningful_excerpt(
        self,
    ) -> None:
        verification = self.ledger["findings"][0]["evidence"][
            "anchor_verification"
        ]
        verification["excerpt"] = "e"
        verification["excerpt_sha256"] = hashlib.sha256(b"e").hexdigest()
        self.ledger["findings"][0]["evidence"]["source_anchor"] = "Section 999"
        self.assertErrorContains(
            self.validate_pair(),
            "exact finding anchor span",
        )

        self.reset_valid_pair()
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        evidence = row["evidence"][0]
        evidence["excerpt"] = "e"
        evidence["excerpt_sha256"] = hashlib.sha256(b"e").hexdigest()
        evidence["source_anchor"] = "Section 999"
        self.assertErrorContains(
            self.validate_pair(),
            "exact-text evidence span",
        )

    def test_rendered_finding_requires_a_finding_specific_receipt(self) -> None:
        finding = self.ledger["findings"][0]
        finding["evidence"]["artifact_id"] = "paper-pdf"
        finding["evidence"]["source_anchor"] = "Page 999"
        finding["evidence"]["anchor_verification"] = {
            "method": "rendered_receipt",
            "excerpt": None,
            "excerpt_sha256": None,
        }
        self.assertErrorContains(
            self.validate_pair(),
            "rendered finding receipt",
        )

    def test_rendered_receipt_rejects_an_unrelated_image(self) -> None:
        row = run_coverage_row(self.run, "RC-VISUAL-INTEGRITY")
        evidence = row["evidence"][0]
        receipt_path = (
            self.evidence_root / evidence["rendered_receipt_locator"]
        )
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        image_path = (
            self.evidence_root / receipt["rendered_artifact_locator"]
        )
        unrelated = image_path.read_bytes() + b"unrelated"
        image_path.write_bytes(unrelated)
        receipt["rendered_artifact_sha256"] = hashlib.sha256(
            unrelated
        ).hexdigest()
        write_json(receipt_path, receipt)
        evidence["rendered_receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "not the reproducible page rendered from the bound PDF",
        )

    def test_rendered_finding_receipt_must_fall_within_run(self) -> None:
        finding = self.ledger["findings"][0]
        pdf = next(
            item
            for item in self.run["input_artifacts"]
            if item["artifact_id"] == "paper-pdf"
        )
        visual_evidence = run_coverage_row(
            self.run, "RC-VISUAL-INTEGRITY"
        )["evidence"][0]
        template_path = (
            self.evidence_root
            / visual_evidence["rendered_receipt_locator"]
        )
        receipt = json.loads(template_path.read_text(encoding="utf-8"))
        receipt["recorded_at"] = "2099-01-01T00:00:00Z"
        receipt["subject_id"] = finding["finding_id"]
        receipt["artifact_id"] = pdf["artifact_id"]
        receipt["pdf_sha256"] = pdf["sha256"]
        receipt["observation_sha256"] = hashlib.sha256(
            finding["evidence"]["observation"].encode("utf-8")
        ).hexdigest()
        locator, digest = write_receipt(
            self.evidence_root,
            "evidence/rendered-finding.json",
            receipt,
        )
        finding["evidence"]["artifact_id"] = pdf["artifact_id"]
        finding["evidence"]["source_anchor"] = "Page 1"
        finding["evidence"]["anchor_verification"] = {
            "method": "rendered_receipt",
            "excerpt": None,
            "excerpt_sha256": None,
            "start_byte": None,
            "end_byte": None,
            "occurrence": None,
            "rendered_receipt_locator": locator,
            "rendered_receipt_sha256": digest,
        }
        self.assertErrorContains(
            self.validate_pair(),
            "rendered receipt chronology",
        )

    def test_alignment_receipt_requires_unique_required_check_ids(
        self,
    ) -> None:
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["checks"][1]["check_id"] = receipt["checks"][0]["check_id"]
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "alignment receipt check IDs",
        )

    def test_alignment_checks_cannot_reuse_the_same_evidence(self) -> None:
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        reused = copy.deepcopy(receipt["checks"][0])
        reused["check_id"] = "section_sequence"
        receipt["checks"][1] = reused
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "alignment checks must use distinct evidence",
        )

    def test_delta_requires_a_visible_revision_marker(self) -> None:
        self.convert_to_valid_delta()
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["checks"] = [
            check
            for check in receipt["checks"]
            if check["check_id"] != "revision_marker"
        ]
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "delta alignment requires a revision_marker",
        )

    def test_alignment_receipt_cannot_postdate_run_finalization(self) -> None:
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["recorded_at"] = "2099-01-01T00:00:00Z"
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "alignment receipt chronology",
        )

    def test_alignment_receipt_requires_a_parseable_pdf_and_real_pages(
        self,
    ) -> None:
        pdf = next(
            item
            for item in self.run["input_artifacts"]
            if item["kind"] == "pdf"
        )
        pdf_path = self.evidence_root / pdf["locator"]
        pdf_path.write_bytes(b"%PDF-1.4\n% incomplete\n%%EOF\n")
        pdf["sha256"] = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["pdf_sha256"] = pdf["sha256"]
        receipt["pdf_integrity"]["page_count"] = 999
        receipt["checks"][0]["pdf_anchor"] = "pdf:page-999-title"
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "PDF parser",
        )

    def test_blank_parseable_pdf_cannot_satisfy_structural_alignment(
        self,
    ) -> None:
        pdf = next(
            item
            for item in self.run["input_artifacts"]
            if item["kind"] == "pdf"
        )
        pdf_path = self.evidence_root / pdf["locator"]
        raw = pdf_path.read_bytes()
        for visible in (
            b"Synthetic Review Fixture",
            b"Introduction",
            (
                b"The headline claim covers unseen domains while the reported "
                b"experiment covers one domain."
            ),
        ):
            raw = raw.replace(visible, b" " * len(visible))
        pdf_path.write_bytes(raw)
        pdf["sha256"] = hashlib.sha256(raw).hexdigest()

        alignment = self.run["source_pdf_alignment"]
        receipt_path = self.evidence_root / alignment["receipt_locator"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["pdf_sha256"] = pdf["sha256"]
        extracted = subprocess.run(
            [
                shutil.which("pdftotext"),
                "-f",
                "1",
                "-l",
                "1",
                "-layout",
                "-enc",
                "UTF-8",
                str(pdf_path),
                "-",
            ],
            check=True,
            capture_output=True,
        ).stdout
        for check in receipt["checks"]:
            check["pdf_page_text_sha256"] = hashlib.sha256(
                extracted
            ).hexdigest()
        write_json(receipt_path, receipt)
        alignment["receipt_sha256"] = hashlib.sha256(
            receipt_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "not recomputable from extracted page text",
        )

    def test_human_machine_binding_and_narrative_cannot_contradict_ledger(
        self,
    ) -> None:
        self.sync_ledger_output()
        output = self.run["output_artifacts"]["review_summary"]
        path = self.evidence_root / output["locator"]
        text = path.read_text(encoding="utf-8").replace(
            '"completion":"complete"',
            '"completion":"blocked"',
        )
        path.write_text(text, encoding="utf-8")
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "machine binding",
        )

        self.reset_valid_pair()
        output = self.run["output_artifacts"]["review_summary"]
        path = self.evidence_root / output["locator"]
        text = path.read_text(encoding="utf-8").replace(
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
            "Fatal blocker exists without a finding identifier.\n\n"
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
        )
        path.write_text(text, encoding="utf-8")
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "without a canonical finding ID",
        )

        self.reset_valid_pair()
        finding_id = self.ledger["findings"][0]["finding_id"]
        output = self.run["output_artifacts"]["ae_assessment"]
        path = self.evidence_root / output["locator"]
        text = path.read_text(encoding="utf-8").replace(
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
            f"{finding_id} was rejected.\n\n"
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
        )
        path.write_text(text, encoding="utf-8")
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "narratively rejects surviving finding",
        )

        self.reset_valid_pair()
        output = self.run["output_artifacts"]["review_summary"]
        path = self.evidence_root / output["locator"]
        text = path.read_text(encoding="utf-8").replace(
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
            "There are no scientific findings; every claim is fully supported.\n\n"
            "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
        )
        path.write_text(text, encoding="utf-8")
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "contradicts retained findings",
        )

    def test_visible_human_view_cannot_diverge_from_machine_binding(self) -> None:
        self.sync_ledger_output()
        output = self.run["output_artifacts"]["review_summary"]
        path = self.evidence_root / output["locator"]
        claim = self.ledger["findings"][0]["claim"]
        text = path.read_text(encoding="utf-8")
        self.assertIn(claim, text)
        text = text.replace(
            claim,
            "The visible table silently reports a different claim.",
            1,
        )
        path.write_text(text, encoding="utf-8")
        output["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertErrorContains(
            validate_run_pair(
                self.run,
                self.ledger,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "differs from the deterministic canonical human view",
        )

    def test_human_nonclaims_reject_acceptance_odds_and_count_confidence(
        self,
    ) -> None:
        for sentence, needle in (
            (
                "There is a 0.92 probability of a positive venue decision.",
                "acceptance prediction",
            ),
            (
                "This paper is likely to be accepted.",
                "acceptance prediction",
            ),
            (
                "The paper will probably be accepted.",
                "acceptance prediction",
            ),
            (
                "I predict this paper will be accepted.",
                "acceptance prediction",
            ),
            (
                "Twelve independent reviewers agreed, therefore confidence is high.",
                "execution topology",
            ),
            (
                "Confidence is high because twelve reviewers agreed.",
                "execution topology",
            ),
            (
                "Because twelve reviewers agreed, this result is reliable.",
                "execution topology",
            ),
        ):
            with self.subTest(sentence=sentence):
                self.reset_valid_pair()
                output = self.run["output_artifacts"]["review_summary"]
                path = self.evidence_root / output["locator"]
                text = path.read_text(encoding="utf-8").replace(
                    "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
                    sentence + "\n\n"
                    "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->",
                )
                path.write_text(text, encoding="utf-8")
                output["sha256"] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                self.assertErrorContains(
                    validate_run_pair(
                        self.run,
                        self.ledger,
                        self.coverage,
                        self.root,
                        evidence_root=self.evidence_root,
                    ),
                    needle,
                )

        self.reset_valid_pair()
        self.run["venue_assessment"]["limitations"] = [
            "The paper is likely to be accepted."
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "acceptance prediction is forbidden anywhere",
        )

        self.reset_valid_pair()
        self.ledger["findings"][0]["why_it_matters"] = (
            "Confidence is high because twelve reviewers agreed."
        )
        self.assertErrorContains(
            self.validate_pair(),
            "count cannot establish scientific confidence",
        )

    def test_policy_detectors_handle_polarity_unicode_and_chinese(self) -> None:
        acceptance_reject = (
            "Acceptance is highly likely.",
            "This paper is unlikely to be accepted.",
            "This paper will not be accepted.",
            "The acceptance likelihood is 80%.",
            "该论文很可能被接收。",
            "本文不太可能被录用。",
            "预计该工作将被收录。",
            "This paper is l\u034fikely to be accepted.",
        )
        acceptance_allow = (
            "I cannot predict whether this paper will be accepted.",
            "Whether the paper will be accepted cannot be predicted.",
            "No acceptance probability is claimed.",
            "Official recommendation: leaning accept.",
            "If accepted, we will release code.",
            "无法预测该论文是否会被接收。",
            "尚不清楚论文是否会被录用。",
            "I can\u034fnot predict whether this paper will be accepted.",
        )
        for sentence in acceptance_reject:
            with self.subTest(kind="acceptance-reject", sentence=sentence):
                self.assertTrue(
                    _contains_positive_acceptance_prediction(sentence)
                )
        for sentence in acceptance_allow:
            with self.subTest(kind="acceptance-allow", sentence=sentence):
                self.assertFalse(
                    _contains_positive_acceptance_prediction(sentence)
                )

        count_reject = (
            "Thirteen reviewers agreed, therefore confidence is high.",
            "A dozen subagents agreed, so the result is more reliable.",
            "More reviewers guarantee better review quality.",
            "十三位审稿人一致，因此可信度很高。",
            "审稿人越多，评审质量越高。",
        )
        count_allow = (
            "Twelve reviewers reported confidence intervals.",
            "We used twelve reviewers; confidence derives from evidence quality.",
            "Reviewer count does not establish confidence.",
            "Confidence comes from evidence rather than reviewer count.",
            "审稿人数量仅用于记录，不代表质量。",
        )
        for sentence in count_reject:
            with self.subTest(kind="count-reject", sentence=sentence):
                self.assertTrue(_contains_count_based_confidence(sentence))
        for sentence in count_allow:
            with self.subTest(kind="count-allow", sentence=sentence):
                self.assertFalse(_contains_count_based_confidence(sentence))

        execution_reject = (
            "No execution took place.",
            "Execution was skipped.",
            "This was a mock runner.",
            "The runner is a placeholder.",
            "The oracle was read.",
            "Outputs were copied from the answer key.",
            "候选方案未执行。",
            "The o\U000e0100racle was read.",
        )
        execution_allow = (
            "Execution was not skipped.",
            "This was not a dry run.",
            "No placeholder remains.",
            "We did not read the oracle.",
            "No oracle values were copied.",
            "Oracle was not consulted before output freeze.",
            "We did n\ufe0fot read the oracle.",
        )
        for sentence in execution_reject:
            with self.subTest(kind="execution-reject", sentence=sentence):
                self.assertTrue(_contains_non_execution_claim(sentence))
        for sentence in execution_allow:
            with self.subTest(kind="execution-allow", sentence=sentence):
                self.assertFalse(_contains_non_execution_claim(sentence))

    def test_machine_binding_sibling_fields_are_scanned_independently(
        self,
    ) -> None:
        raw = human_output_bytes(
            "review_summary",
            limitations=[
                "accepted",
                "probability calibration",
            ],
        )
        errors = _validate_human_output(
            "review_summary",
            raw,
            "RUN-2026-001",
            "complete",
        )
        self.assertFalse(
            any("acceptance prediction" in error for error in errors),
            errors,
        )

    def test_delta_requires_and_cross_binds_full_predecessor_set(self) -> None:
        for input_kind in (
            "prior_run",
            "prior_ledger",
            "prior_source",
            "author_response",
        ):
            with self.subTest(input_kind=input_kind):
                self.reset_valid_pair()
                self.convert_to_valid_delta()
                self.run["input_artifacts"] = [
                    artifact
                    for artifact in self.run["input_artifacts"]
                    if artifact["kind"] != input_kind
                ]
                self.assertErrorContains(
                    self.validate_pair(),
                    f"exactly one {input_kind.replace('_', '-')}",
                )

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        prior_run_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_run"
        )
        prior_run_path = (
            self.evidence_root / prior_run_artifact["locator"]
        )
        prior_run = json.loads(prior_run_path.read_text(encoding="utf-8"))
        prior_run["output_artifacts"]["finding_ledger"]["sha256"] = HEX_A
        write_json(prior_run_path, prior_run)
        prior_run_artifact["sha256"] = hashlib.sha256(
            prior_run_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "does not bind the frozen prior ledger",
        )

    def test_delta_findings_must_anchor_current_not_prior_source(self) -> None:
        self.convert_to_valid_delta()
        finding = self.ledger["findings"][0]
        finding["evidence"]["artifact_id"] = "prior-source"
        self.assertErrorContains(
            self.validate_pair(),
            "current delta finding",
        )

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["evidence"][0]["artifact_id"] = "prior-source"
        self.assertErrorContains(
            self.validate_pair(),
            "current source artifact",
        )

    def test_prior_finding_exact_span_is_revalidated_against_prior_bytes(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        prior_ledger_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_ledger"
        )
        prior_ledger_path = (
            self.evidence_root / prior_ledger_artifact["locator"]
        )
        prior_ledger = json.loads(
            prior_ledger_path.read_text(encoding="utf-8")
        )
        verification = prior_ledger["findings"][0]["evidence"][
            "anchor_verification"
        ]
        verification["start_byte"] += 1
        verification["end_byte"] += 1
        prior_ledger["findings"][0]["evidence"]["source_anchor"] = (
            f"bytes:{verification['start_byte']}-{verification['end_byte']};"
            f"occurrence:{verification['occurrence']}"
        )
        write_json(prior_ledger_path, prior_ledger)
        prior_ledger_artifact["sha256"] = hashlib.sha256(
            prior_ledger_path.read_bytes()
        ).hexdigest()

        prior_run_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_run"
        )
        prior_run_path = self.evidence_root / prior_run_artifact["locator"]
        prior_run = json.loads(prior_run_path.read_text(encoding="utf-8"))
        prior_run["output_artifacts"]["finding_ledger"]["sha256"] = (
            prior_ledger_artifact["sha256"]
        )
        write_json(prior_run_path, prior_run)
        prior_run_artifact["sha256"] = hashlib.sha256(
            prior_run_path.read_bytes()
        ).hexdigest()

        self.assertErrorContains(
            self.validate_pair(),
            "prior finding exact anchor span",
        )

    def test_author_response_binds_all_predecessor_bytes_and_transitions(
        self,
    ) -> None:
        self.convert_to_valid_delta()
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["revised_source_sha256"] = HEX_A
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "exact revised source",
        )

        self.reset_valid_pair()
        self.convert_to_valid_delta()
        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["transitions"] = []
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            self.validate_pair(),
            "transitions must exactly account",
        )

    def test_semantically_invalid_or_future_prior_run_is_rejected(self) -> None:
        self.convert_to_valid_delta()
        prior_run_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "prior_run"
        )
        prior_run_path = self.evidence_root / prior_run_artifact["locator"]
        prior_run = json.loads(prior_run_path.read_text(encoding="utf-8"))
        prior_run["coverage"]["criteria"][0]["disposition"] = (
            "needs_verification"
        )
        prior_run["coverage"]["criteria"][0]["evidence"] = []
        prior_run["created_at"] = "2026-07-29T12:00:00Z"
        write_json(prior_run_path, prior_run)
        prior_run_artifact["sha256"] = hashlib.sha256(
            prior_run_path.read_bytes()
        ).hexdigest()

        response_artifact = next(
            artifact
            for artifact in self.run["input_artifacts"]
            if artifact["kind"] == "author_response"
        )
        response_path = self.evidence_root / response_artifact["locator"]
        response = json.loads(response_path.read_text(encoding="utf-8"))
        response["prior_run_sha256"] = prior_run_artifact["sha256"]
        write_json(response_path, response)
        response_artifact["sha256"] = hashlib.sha256(
            response_path.read_bytes()
        ).hexdigest()

        errors = self.validate_pair()
        self.assertErrorContains(errors, "prior run semantic validation")
        self.assertErrorContains(errors, "prior run must precede")

    def test_venue_assessment_exactly_binds_rules_and_native_values(self) -> None:
        native_field = {
            "field_id": "overall-rating",
            "role": "reviewer",
            "field_type": "integer_scale",
            "prompt": "Provide the official overall rating.",
            "required": True,
            "minimum": 1,
            "maximum": 5,
            "allowed_labels": [],
            "anchors": [
                {"value": 1, "label": "lowest"},
                {"value": 5, "label": "highest"},
            ],
            "source_ids": ["reviewer-instructions"],
        }
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[native_field],
        )
        self.run["venue_assessment"]["criteria"] = []
        self.assertErrorContains(
            self.validate_pair(),
            "criteria must exactly cover",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[native_field],
        )
        self.run["venue_assessment"]["native_fields"][0]["value"] = 1.5
        self.assertErrorContains(
            self.validate_pair(),
            "integer native value must be integral",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        self.run["venue_assessment"]["criteria"][0]["evidence"] = [
            "Unbound venue prose is not canonical evidence."
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "schema:",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[native_field],
        )
        self.run["venue_assessment"]["native_fields"][0].pop("basis")
        self.assertErrorContains(
            self.validate_pair(),
            "basis",
        )

    def test_venue_overlay_cannot_clear_a_portable_concern(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        criterion = self.run["venue_assessment"]["criteria"][0]
        criterion["assessment"] = "satisfied"
        criterion["finding_ids"] = []
        criterion["evidence"] = [
            {
                "reference_kind": "coverage_evidence",
                "criterion_id": "RC-CLAIM-EVIDENCE",
                "evidence_index": 0,
                "finding_id": None,
            }
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "additive venue overlay cannot mark a mapped portable concern",
        )

    def test_venue_overlay_cannot_omit_a_mapped_finding(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        criterion = self.run["venue_assessment"]["criteria"][0]
        criterion["finding_ids"] = []
        criterion["evidence"] = [
            {
                "reference_kind": "coverage_evidence",
                "criterion_id": "RC-CLAIM-EVIDENCE",
                "evidence_index": 0,
                "finding_id": None,
            }
        ]
        errors = self.validate_pair()
        self.assertErrorContains(
            errors,
            "exactly account for every mapped portable finding",
        )
        self.assertErrorContains(
            errors,
            "exactly reference every mapped portable finding",
        )

    def test_clean_portable_coverage_cannot_invent_a_venue_blocker(
        self,
    ) -> None:
        row = run_coverage_row(self.run, "RC-CLAIM-EVIDENCE")
        row["disposition"] = "assessed_no_finding"
        row["finding_ids"] = []
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        self.run["venue_assessment"]["criteria"][0][
            "assessment"
        ] = "blocked"
        self.run["venue_assessment"]["status"] = "blocked"
        self.run["venue_assessment"]["limitations"].append(
            "The venue row claims a blocker without canonical support."
        )
        self.set_completion("blocked")
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "status does not derive from the mapped portable coverage",
        )

    def test_human_views_bind_profile_semantics_and_reported_roles(
        self,
    ) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[
                {
                    "field_id": "meta-review",
                    "role": "meta_reviewer",
                    "field_type": "text",
                    "prompt": "Record the evidence-backed meta-review.",
                    "required": True,
                    "minimum": None,
                    "maximum": None,
                    "allowed_labels": [],
                    "anchors": [],
                    "source_ids": ["reviewer-instructions"],
                }
            ],
        )
        self.run["venue_assessment"]["native_fields"][0]["value"] = (
            "SECRET META RESULT ONLY"
        )
        reviewer = render_human_view(
            "reviewer_report",
            self.run,
            self.ledger,
            self.root,
        )
        ae = render_human_view(
            "ae_assessment",
            self.run,
            self.ledger,
            self.root,
        )
        summary = render_human_view(
            "review_summary",
            self.run,
            self.ledger,
            self.root,
        )
        self.assertNotIn("SECRET META RESULT ONLY", reviewer)
        self.assertIn("SECRET META RESULT ONLY", ae)
        self.assertIn("SECRET META RESULT ONLY", summary)
        self.assertIn("Assess soundness under the venue guidance.", reviewer)

        profile_path = self.root / self.run["venue_profile"][
            "profile_locator"
        ]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["criteria"][0]["statement"] = (
            "A changed release-governed venue statement."
        )
        write_json(profile_path, profile)
        self.run["venue_profile"]["profile_sha256"] = hashlib.sha256(
            profile_path.read_bytes()
        ).hexdigest()
        changed = render_human_view(
            "review_summary",
            self.run,
            self.ledger,
            self.root,
        )
        self.assertNotEqual(summary, changed)
        self.assertIn(
            "A changed release-governed venue statement.",
            changed,
        )

    def test_venue_numeric_fields_require_anchors_and_direction(self) -> None:
        base = {
            "field_id": "overall-rating",
            "role": "reviewer",
            "field_type": "integer_scale",
            "prompt": "Provide the official overall rating.",
            "required": True,
            "minimum": 1,
            "maximum": 5,
            "allowed_labels": [],
            "anchors": [],
            "source_ids": ["reviewer-instructions"],
        }
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[base],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "endpoint anchors",
        )

        self.reset_valid_pair()
        invalid_direction = copy.deepcopy(base)
        invalid_direction["anchors"] = [
            {"value": 1, "label": "lowest"},
            {"value": 5, "label": "highest"},
        ]
        invalid_direction["direction"] = None
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[invalid_direction],
        )
        self.assertErrorContains(
            self.validate_pair(),
            "direction",
        )

    def test_venue_profile_semantics_must_equal_typed_source_claims(
        self,
    ) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[
                {
                    "field_id": "overall-rating",
                    "role": "reviewer",
                    "field_type": "integer_scale",
                    "prompt": "Provide the official overall rating.",
                    "required": True,
                    "minimum": 1,
                    "maximum": 5,
                    "allowed_labels": [],
                    "anchors": [
                        {"value": 1, "label": "lowest"},
                        {"value": 5, "label": "highest"},
                    ],
                    "source_ids": ["reviewer-instructions"],
                }
            ],
        )
        profile_path = self.root / self.run["venue_profile"][
            "profile_locator"
        ]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["criteria"][0]["statement"] = (
            "Every submission must compare exactly twelve baselines."
        )
        profile["native_assessment_fields"][0]["maximum"] = 6
        write_json(profile_path, profile)
        self.run["venue_profile"]["profile_sha256"] = hashlib.sha256(
            profile_path.read_bytes()
        ).hexdigest()
        self.assertErrorContains(
            validate_run_manifest(
                self.run,
                self.coverage,
                self.root,
                evidence_root=self.evidence_root,
            ),
            "differs from its typed source claim projection",
        )

    def test_venue_excerpt_self_hash_cannot_replace_frozen_capture(
        self,
    ) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )

        def mutate(evidence: dict) -> None:
            excerpt = evidence["sections"][0]["verbatim_excerpts"][0]
            excerpt["text"] += " Every paper must compare twelve baselines."
            excerpt["sha256"] = hashlib.sha256(
                excerpt["text"].encode("utf-8")
            ).hexdigest()
            excerpt["capture_end_byte"] = (
                excerpt["capture_start_byte"]
                + len(excerpt["text"].encode("utf-8"))
            )

        self.assertErrorContains(
            self.mutate_installed_venue_evidence(mutate),
            "does not match its frozen capture byte span",
        )

    def test_venue_claim_cannot_reference_an_unknown_excerpt(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )

        def mutate(evidence: dict) -> None:
            evidence["sections"][0]["claims"][0]["excerpt_ids"] = [
                "invented-official-text"
            ]

        self.assertErrorContains(
            self.mutate_installed_venue_evidence(mutate),
            "unknown verbatim excerpt ID",
        )

    def test_venue_native_scale_requires_exact_value_label_pairs(
        self,
    ) -> None:
        native_field = {
            "field_id": "overall-rating",
            "role": "reviewer",
            "field_type": "integer_scale",
            "prompt": "Provide the official overall rating.",
            "required": True,
            "minimum": 1,
            "maximum": 5,
            "allowed_labels": [],
            "anchors": [
                {"value": 1, "label": "lowest"},
                {"value": 5, "label": "highest"},
            ],
            "source_ids": ["reviewer-instructions"],
        }
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[native_field],
        )

        def mutate(evidence: dict) -> None:
            section = evidence["sections"][0]
            criterion_excerpt = section["verbatim_excerpts"][0]
            swapped_texts = [
                "The official overall-rating endpoint is 1 highest.",
                "The official overall-rating endpoint is 5 lowest.",
            ]
            capture_text = (
                criterion_excerpt["text"]
                + "\n\n"
                + "\n\n".join(swapped_texts)
            )
            capture_path = self.root / evidence["capture_locator"]
            capture = json.loads(capture_path.read_text(encoding="utf-8"))
            capture["captured_text"] = capture_text
            write_json(capture_path, capture)
            evidence["capture_sha256"] = hashlib.sha256(
                capture_path.read_bytes()
            ).hexdigest()

            replacement_excerpts = [criterion_excerpt]
            criterion_span = exact_span_fields(
                criterion_excerpt["text"], capture_text
            )
            criterion_excerpt["capture_start_byte"] = criterion_span[
                "start_byte"
            ]
            criterion_excerpt["capture_end_byte"] = criterion_span["end_byte"]
            criterion_excerpt["capture_occurrence"] = criterion_span[
                "occurrence"
            ]
            for index, text in enumerate(swapped_texts, start=1):
                span = exact_span_fields(text, capture_text)
                replacement_excerpts.append(
                    {
                        "excerpt_id": f"swapped-anchor-{index}",
                        "source_locator":
                            f"Fixture reviewer form > swapped endpoint {index}",
                        "text": text,
                        "sha256": hashlib.sha256(
                            text.encode("utf-8")
                        ).hexdigest(),
                        "capture_start_byte": span["start_byte"],
                        "capture_end_byte": span["end_byte"],
                        "capture_occurrence": span["occurrence"],
                    }
                )
            section["verbatim_excerpts"] = replacement_excerpts
            native_claim = next(
                claim
                for claim in section["claims"]
                if claim["claim_kind"] == "native_field"
            )
            native_claim["excerpt_ids"] = [
                "swapped-anchor-1",
                "swapped-anchor-2",
            ]

        self.assertErrorContains(
            self.mutate_installed_venue_evidence(mutate),
            "value-label pair is absent",
        )

    def test_venue_assessment_status_machine_is_closed(self) -> None:
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        self.run["venue_assessment"]["criteria"][0]["assessment"] = "satisfied"
        finding_id = self.ledger["findings"][0]["finding_id"]
        self.run["venue_assessment"]["criteria"][0]["finding_ids"] = [
            finding_id
        ]
        self.assertErrorContains(
            self.validate_pair(),
            "satisfied venue rule cannot link a finding",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        finding_id = self.ledger["findings"][0]["finding_id"]
        criterion = self.run["venue_assessment"]["criteria"][0]
        criterion["assessment"] = "concern"
        criterion["finding_ids"] = [finding_id]
        criterion["evidence"] = [
            {
                "reference_kind": "finding",
                "criterion_id": "RC-CLAIM-EVIDENCE",
                "evidence_index": None,
                "finding_id": finding_id,
            }
        ]
        self.assertEqual(self.validate_pair(), [])
        self.ledger["findings"][0]["adjudication_status"] = "candidate"
        self.assertErrorContains(
            self.validate_pair(),
            "venue concern must link a surviving canonical finding",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
        )
        self.run["venue_assessment"]["status"] = "blocked"
        self.set_completion("blocked")
        self.assertErrorContains(
            self.validate_pair(),
            "requires an actually blocked rule or native field",
        )

        self.reset_valid_pair()
        install_icml_venue_profile(
            self.root,
            self.run,
            evidence_root=self.evidence_root,
            native_fields=[
                {
                    "field_id": "overall-rating",
                    "role": "reviewer",
                    "field_type": "integer_scale",
                    "prompt": "Provide the official overall rating.",
                    "required": True,
                    "minimum": 1,
                    "maximum": 5,
                    "allowed_labels": [],
                    "anchors": [],
                    "source_ids": ["reviewer-instructions"],
                }
            ],
        )
        self.run["venue_assessment"]["status"] = "blocked"
        native = self.run["venue_assessment"]["native_fields"][0]
        native["status"] = "blocked"
        native["value"] = None
        native["rationale"] = "The venue-native value could not be established."
        native["basis"] = {
            "kind": "blocked",
            "criterion_ids": ["RC-CLAIM-EVIDENCE"],
            "finding_ids": [],
        }
        self.set_completion("blocked")
        errors = self.validate_pair()
        self.assertFalse(
            any("required native field is not provided" in error for error in errors),
            errors,
        )


class AdapterPromotionShapeTests(unittest.TestCase):
    def test_runner_must_equal_the_release_governed_scorer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            report_path = root / row["evaluation_report_locator"]
            receipt_path = root / row["execution_receipt_locator"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            replacement_locator = "SKILL.md"
            replacement_sha256 = hashlib.sha256(
                (root / replacement_locator).read_bytes()
            ).hexdigest()
            for artifact in (report, receipt):
                artifact["runner_locator"] = replacement_locator
                artifact["runner_sha256"] = replacement_sha256
            write_json(report_path, report)
            row["evaluation_report_sha256"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            receipt["evaluation_report_sha256"] = row[
                "evaluation_report_sha256"
            ]
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("release-governed scorer" in error for error in errors),
                errors,
            )

    def test_release_authority_rejects_a_renamed_canonical_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            manifest_path = root / "evals/adapter-fixtures/manifest.json"
            fixture_manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            fixture_manifest["fixtures"][0]["fixture_id"] = "renamed-quality"
            write_json(manifest_path, fixture_manifest)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("canonical fixture authority" in error for error in errors),
                errors,
            )

    def test_runner_execution_and_identity_bindings_are_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            report_path = root / row["evaluation_report_locator"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["runner"] = "different-evaluation-runner"
            write_json(report_path, report)
            row["evaluation_report_sha256"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["evaluation_report_sha256"] = row[
                "evaluation_report_sha256"
            ]
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "report and execution receipt runner mismatch" in error
                    for error in errors
                ),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            rows = promotion["evaluation_summary"]["candidate_evaluations"]
            first_receipt = json.loads(
                (root / rows[0]["execution_receipt_locator"]).read_text(
                    encoding="utf-8"
                )
            )
            second_path = root / rows[1]["execution_receipt_locator"]
            second_receipt = json.loads(second_path.read_text(encoding="utf-8"))
            second_receipt["execution_id"] = first_receipt["execution_id"]
            write_json(second_path, second_receipt)
            rows[1]["execution_receipt_sha256"] = hashlib.sha256(
                second_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("distinct execution IDs" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][1]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["executor"]["executor_id"] = (
                " Executor-minimal-settled-set "
            )
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "executor identifier is invalid" in error
                    or "executor identities" in error
                    or "executor.executor_id" in error
                    for error in errors
                ),
                errors,
            )

    def test_promotion_chronology_and_semantic_selection_are_derived(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            promotion["evaluated_at"] = "2026-07-28T12:20:00Z"
            persist_promotion(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("chronology is invalid" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            summary = promotion["evaluation_summary"]
            semantic_path = root / summary["semantic_review_locator"]
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            selected = promotion["candidate_id"]
            other = next(candidate for candidate in MAPPING if candidate != selected)
            for dimension in semantic["dimensions"][:5]:
                for assessment in dimension["assessments"]:
                    assessment["rating"] = (
                        "preferred"
                        if assessment["candidate_id"] == other
                        else "weaker"
                    )
                dimension["preferred_candidate_id"] = other
            write_json(semantic_path, semantic)
            summary["semantic_review_sha256"] = hashlib.sha256(
                semantic_path.read_bytes()
            ).hexdigest()
            persist_promotion(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "verdict is not derived from the complete comparison"
                    in error
                    for error in errors
                ),
                errors,
            )

    def test_explicit_nonexecution_and_oracle_copy_claims_fail_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["limitations"] = [
                "The candidate was not executed and outputs were copied from "
                "the oracle."
            ]
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("contradict actual execution" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(
                receipt_path.read_text(encoding="utf-8")
            )
            receipt["limitations"] = [
                "The candidate was not \ufeffexecuted and outputs were copied "
                "from the \ufefforacle."
            ]
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("contradict actual execution" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            report_path = root / row["evaluation_report_locator"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            case = report["cases"][0]
            output_path = root / case["output_locator"]
            output = json.loads(output_path.read_text(encoding="utf-8"))
            output["observations"][0]["evidence"] = (
                "The expected value was copied from the oracle."
            )
            write_json(output_path, output)
            output_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
            case["output_sha256"] = output_sha
            write_json(report_path, report)
            row["evaluation_report_sha256"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["evaluation_report_sha256"] = row[
                "evaluation_report_sha256"
            ]
            receipt_case = next(
                item
                for item in receipt["cases"]
                if item["fixture_id"] == case["fixture_id"]
            )
            receipt_case["output_sha256"] = output_sha
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("candidate output contradicts actual execution" in error
                    for error in errors),
                errors,
            )

    def test_supplied_promotion_must_equal_the_canonical_stored_record(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            promotion["record_id"] = "AP-memory-only-mutation"
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("canonical stored promotion" in error for error in errors),
                errors,
            )

    def test_reported_pass_cannot_override_oracle_derived_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            self.assertIsNotNone(promotion)
            report_path = (
                root
                / "compatibility/minimal-settled-set/evaluation-report.json"
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
            first_case = report["cases"][0]
            output_path = root / first_case["output_locator"]
            output = json.loads(output_path.read_text(encoding="utf-8"))
            output["observations"][0]["observed"] = False
            write_json(output_path, output)
            first_case["output_sha256"] = hashlib.sha256(
                output_path.read_bytes()
            ).hexdigest()
            write_json(report_path, report)
            selected_row = next(
                row
                for row in promotion["evaluation_summary"][
                    "candidate_evaluations"
                ]
                if row["candidate_id"] == "minimal-settled-set"
            )
            selected_row["evaluation_report_sha256"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("oracle-derived result" in error for error in errors),
                errors,
            )

    def test_promotion_shape_rejects_unknown_values(self) -> None:
        data = {
            "schema_version": "1.0.0",
            "record_id": "AP-1",
            "evaluated_at": "2026-07-28T12:00:00Z",
            "candidate_id": "unknown",
            "adapter_sha256": HEX_A,
            "result": "maybe",
            "promotion_decision": "perhaps",
            "evaluation_summary": {},
        }
        errors = validate_adapter_promotion(data)
        self.assertTrue(errors)

    def test_selected_promotion_requires_complete_evaluation_summary(self) -> None:
        data = {
            "schema_version": "1.0.0",
            "record_id": "AP-1",
            "evaluated_at": "2026-07-28T12:00:00Z",
            "candidate_id": "minimal-settled-set",
            "adapter_sha256": HEX_A,
            "result": "pass",
            "promotion_decision": "selected",
            "evaluation_summary": {},
        }
        errors = validate_adapter_promotion(data)
        self.assertTrue(errors)
        self.assertTrue(
            any("fixture_set" in error for error in errors),
            errors,
        )

    def test_promotion_requires_two_executions_and_independent_semantic_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            summary = promotion["evaluation_summary"]
            summary["candidate_evaluations"].pop()
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "both lifecycle candidates" in error
                    or "fewer than 2" in error
                    for error in errors
                ),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["runner"] = "NOT EXECUTED placeholder"
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("runner" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            summary = promotion["evaluation_summary"]
            semantic_path = root / summary["semantic_review_locator"]
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            semantic["reviewer"]["reviewer_id"] = semantic["executor_ids"][0]
            write_json(semantic_path, semantic)
            summary["semantic_review_sha256"] = hashlib.sha256(
                semantic_path.read_bytes()
            ).hexdigest()
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("distinct from both executors" in error for error in errors),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            summary = promotion["evaluation_summary"]
            semantic_path = root / summary["semantic_review_locator"]
            semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
            semantic["dimensions"].pop()
            write_json(semantic_path, semantic)
            summary["semantic_review_sha256"] = hashlib.sha256(
                semantic_path.read_bytes()
            ).hexdigest()
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "six comparison axes" in error
                    or "fewer than 6" in error
                    for error in errors
                ),
                errors,
            )

    def test_release_authority_pins_fixture_input_and_oracle_bytes(self) -> None:
        for side in ("input", "oracle"):
            with self.subTest(side=side):
                with tempfile.TemporaryDirectory() as temp:
                    root = pathlib.Path(temp)
                    _, promotion = make_bundle(
                        root,
                        selected="minimal-settled-set",
                    )
                    summary = promotion["evaluation_summary"]
                    manifest_path = (
                        root / summary["fixture_manifest_locator"]
                    )
                    fixture_manifest = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )
                    fixture = fixture_manifest["fixtures"][0]
                    locator_key = f"{side}_locator"
                    sha_key = f"{side}_sha256"
                    artifact_path = root / fixture[locator_key]
                    artifact = json.loads(
                        artifact_path.read_text(encoding="utf-8")
                    )
                    artifact["schema_version"] = "1.0.0-mutated"
                    write_json(artifact_path, artifact)
                    fixture[sha_key] = hashlib.sha256(
                        artifact_path.read_bytes()
                    ).hexdigest()
                    write_json(manifest_path, fixture_manifest)
                    summary["fixture_manifest_sha256"] = hashlib.sha256(
                        manifest_path.read_bytes()
                    ).hexdigest()
                    persist_promotion(root, promotion)
                    errors = validate_adapter_promotion(promotion, root)
                    self.assertTrue(
                        any(
                            "canonical fixture authority" in error
                            or "fixture namespace" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_requested_controls_do_not_overclaim_effective_telemetry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(
                receipt_path.read_text(encoding="utf-8")
            )
            receipt["executor"]["resolved_model"] = "gpt-5.6-sol"
            receipt["executor"]["resolved_mode"] = "ultra"
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "absent host telemetry requires null resolved" in error
                    for error in errors
                ),
                errors,
            )

        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            row = promotion["evaluation_summary"]["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(
                receipt_path.read_text(encoding="utf-8")
            )
            receipt["executor"]["effective_telemetry"] = (
                "surfaced_unverified"
            )
            receipt["executor"]["resolved_model"] = "gpt-5.6-terra"
            receipt["executor"]["resolved_mode"] = "max"
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any(
                    "surfaced telemetry conflicts" in error
                    for error in errors
                ),
                errors,
            )

    def test_dispatch_snapshot_must_exclude_oracle_material(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            _, promotion = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            summary = promotion["evaluation_summary"]
            row = summary["candidate_evaluations"][0]
            receipt_path = root / row["execution_receipt_locator"]
            receipt = json.loads(
                receipt_path.read_text(encoding="utf-8")
            )
            fixture_manifest = json.loads(
                (root / summary["fixture_manifest_locator"]).read_text(
                    encoding="utf-8"
                )
            )
            receipt["dispatch_input_snapshot_sha256"] = hashlib.sha256(
                canonical_bytes(
                    {
                        "schema_version": "1.0.0",
                        "candidate_id": row["candidate_id"],
                        "inputs": [
                            {
                                "fixture_id": fixture["fixture_id"],
                                "input_locator": fixture["input_locator"],
                                "oracle_locator": fixture["oracle_locator"],
                            }
                            for fixture in fixture_manifest["fixtures"]
                        ],
                    }
                )
            ).hexdigest()
            write_json(receipt_path, receipt)
            row["execution_receipt_sha256"] = hashlib.sha256(
                receipt_path.read_bytes()
            ).hexdigest()
            sync_semantic_promotion_bindings(root, promotion)
            errors = validate_adapter_promotion(promotion, root)
            self.assertTrue(
                any("oracle-free candidate/input set" in error for error in errors),
                errors,
            )

    def test_selected_manifest_rejects_traversal_or_missing_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            manifest, _ = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            manifest["promotion_record_locator"] = "../outside.json"
            errors = validate_adapter_manifest(manifest, root)
            self.assertTrue(
                any("promotion" in error and "canonical" in error for error in errors),
                errors,
            )

            manifest, _ = make_bundle(
                root,
                selected="minimal-settled-set",
            )
            (root / manifest["promotion_record_locator"]).unlink()
            errors = validate_adapter_manifest(manifest, root)
            self.assertTrue(
                any("promotion" in error and "invalid" in error for error in errors),
                errors,
            )


class JsonSchemaSubsetAdversarialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        (self.root / "schemas").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self, value: object, schema: dict) -> list[str]:
        write_json(self.root / "schemas/probe.schema.json", schema)
        return validate_json_schema_document(
            value,
            self.root,
            "schemas/probe.schema.json",
            "probe",
        )

    def test_remote_unresolved_and_non_schema_refs_fail_closed(self) -> None:
        for schema in (
            {"$ref": "https://example.invalid/schema"},
            {"$defs": {}, "$ref": "#/$defs/missing"},
            {"$comment": {}, "$ref": "#/$comment"},
            {
                "$defs": {"wrapper": {"const": {}}},
                "$ref": "#/$defs/wrapper/const",
            },
        ):
            with self.subTest(schema=schema):
                self.assertTrue(self.validate({}, schema))

    def test_direct_and_mutual_ref_cycles_fail_closed(self) -> None:
        direct = {
            "$defs": {"loop": {"$ref": "#/$defs/loop"}},
            "$ref": "#/$defs/loop",
        }
        mutual = {
            "$defs": {
                "left": {"$ref": "#/$defs/right"},
                "right": {"$ref": "#/$defs/left"},
            },
            "$ref": "#/$defs/left",
        }
        for schema in (direct, mutual):
            errors = self.validate({}, schema)
            self.assertTrue(
                any("cyclic JSON Schema reference" in error for error in errors),
                errors,
            )

    def test_nested_id_rebasing_and_unsupported_keywords_are_rejected(
        self,
    ) -> None:
        nested_id = {
            "$defs": {
                "outer": {"const": "outer"},
                "inner": {
                    "$id": "inner.json",
                    "$defs": {"outer": {"const": "inner"}},
                    "$ref": "#/$defs/outer",
                },
            },
            "$ref": "#/$defs/inner",
        }
        self.assertTrue(
            any(
                "nested $id" in error
                for error in self.validate("outer", nested_id)
            )
        )
        unsupported = {
            "$defs": {"item": {"type": "object", "maxProperties": 0}},
            "$ref": "#/$defs/item",
        }
        self.assertTrue(
            any(
                "unsupported keyword" in error
                for error in self.validate({}, unsupported)
            )
        )

    def test_numeric_oneof_and_unique_items_follow_json_semantics(self) -> None:
        one_of = {
            "oneOf": [
                {"type": "integer"},
                {"type": "number"},
            ]
        }
        self.assertTrue(self.validate(1.0, one_of))
        unique = {
            "type": "array",
            "uniqueItems": True,
        }
        self.assertTrue(self.validate([1, 1.0], unique))
        self.assertTrue(self.validate([0, -0.0], unique))

    def test_nonfinite_and_non_string_object_keys_are_not_json(self) -> None:
        schema = {"type": "object"}
        self.assertTrue(self.validate({"value": float("nan")}, schema))
        self.assertTrue(self.validate({"value": float("inf")}, schema))
        self.assertTrue(self.validate({1: "not-json"}, schema))

    def test_rfc3339_accepts_long_fraction_and_lowercase_tz(self) -> None:
        schema = {"type": "string", "format": "date-time"}
        self.assertEqual(
            [],
            self.validate("2026-07-28T12:34:56.123456789Z", schema),
        )
        self.assertEqual(
            [],
            self.validate("2026-07-28t12:34:56.123456789z", schema),
        )
        self.assertEqual(
            [],
            self.validate("2026-06-30T23:59:60Z", schema),
        )
        self.assertTrue(self.validate("2026-02-30T12:34:56Z", schema))
        self.assertTrue(self.validate("2026-07-28T12:34:56+24:00", schema))


if __name__ == "__main__":
    unittest.main()
