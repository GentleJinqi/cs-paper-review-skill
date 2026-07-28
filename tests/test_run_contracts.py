from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

from scripts.review_skill_validation import (
    adapter_payload_sha256,
    load_adapter_manifest,
    load_adapter_promotion,
    load_review_coverage,
    stable_finding_id,
    validate_adapter_manifest,
    validate_adapter_promotion,
    validate_finding_ledger,
    validate_run_manifest,
    validate_run_pair,
)


HEX_A = "a" * 64
HEX_B = "b" * 64
MAPPING = {
    "minimal-settled-set": "adapters/codex/candidates/minimal-settled-set.md",
    "persisted-task-registry":
        "adapters/codex/candidates/persisted-task-registry.md",
}


def canonical_bytes(data: dict) -> bytes:
    return (
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def write_json(path: pathlib.Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(data))


def coverage_fixture() -> dict:
    return {
        "schema_version": "1.0.0",
        "criteria": [
            {
                "criterion_id": "SC-LINEAGE",
                "review_question": "Are the reviewed inputs and versions unambiguous?",
                "required_evidence": ["artifact lineage", "source/PDF check"],
                "primary_stage_owner": "input-freeze",
                "conditional_specialist_trigger": None,
                "applicability_states": [
                    "applicable",
                    "inapplicable",
                    "uncertain",
                ],
                "required_when_inapplicable": "A rationale tied to the input form.",
                "required_when_uncertain": "The missing evidence and blocking effect.",
            },
            {
                "criterion_id": "SC-CLAIMS",
                "review_question": "Are material claims supported and calibrated?",
                "required_evidence": ["claim anchor", "supporting result"],
                "primary_stage_owner": "scientific-assessment",
                "conditional_specialist_trigger": "Formal or causal claims.",
                "applicability_states": [
                    "applicable",
                    "inapplicable",
                    "uncertain",
                ],
                "required_when_inapplicable": "A paper-specific rationale.",
                "required_when_uncertain": "The unresolved verification need.",
            },
        ],
    }


def coverage_digest(data: dict) -> str:
    return hashlib.sha256(canonical_bytes(data)).hexdigest()


def make_bundle(
    root: pathlib.Path,
    *,
    selected: str | None = None,
    promotion_result: str = "pass",
    promotion_decision: str = "selected",
) -> tuple[dict, dict | None]:
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

    manifest = {
        "schema_version": "1.0.0",
        "selected_candidate_id": selected,
        "selected_lifecycle_implementation": selected_path,
        "promotion_record_locator":
            "compatibility/adapter-promotion.json" if selected else None,
        "candidate_implementations": dict(MAPPING),
        "active_files": active_files,
        "adapter_payload_sha256": "",
    }
    write_json(root / "adapters/codex/adapter-manifest.json", manifest)
    manifest["adapter_payload_sha256"] = adapter_payload_sha256(root)
    write_json(root / "adapters/codex/adapter-manifest.json", manifest)

    promotion = None
    if selected:
        promotion = {
            "schema_version": "1.0.0",
            "record_id": "AP-2026-001",
            "evaluated_at": "2026-07-28T12:00:00Z",
            "candidate_id": selected,
            "adapter_sha256": manifest["adapter_payload_sha256"],
            "result": promotion_result,
            "promotion_decision": promotion_decision,
            "evaluation_summary": {
                "fixture_set": "forward-v1",
                "quality_result": "no material regression",
                "lifecycle_result": "all hard gates passed",
            },
        }
        write_json(root / "compatibility/adapter-promotion.json", promotion)
    return manifest, promotion


def coverage_rows(coverage: dict) -> list[dict]:
    return [
        {
            "criterion_id": row["criterion_id"],
            "applicability": "applicable",
            "disposition": "assessed_no_finding",
            "evidence": [
                {
                    "artifact_id": "paper-source",
                    "source_anchor": "section:introduction",
                }
            ],
            "stage_id": row["primary_stage_owner"],
            "task_ids": [],
            "finding_ids": [],
            "rationale": "Evidence inspected; no material defect found.",
        }
        for row in coverage["criteria"]
    ]


def validation_state(status: str = "not_run") -> dict:
    return {
        "status": status,
        "evidence_locator": "evidence/model-check.json" if status == "passed" else None,
        "sha256": HEX_B if status == "passed" else None,
    }


def run_fixture(
    coverage: dict,
    manifest: dict,
    promotion: dict | None,
    *,
    compatibility: str = "evaluation_pending",
    review_kind: str = "initial",
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
            "result": promotion["result"],
            "promotion_decision": promotion["promotion_decision"],
        }
    passed = compatibility in {"configured-and-evaluated", "runtime-attested"}
    return {
        "schema_version": "1.0.0",
        "run_id": "RUN-2026-001",
        "created_at": "2026-07-28T12:00:00Z",
        "review_goal": "Author-side pre-submission scientific review.",
        "review_kind": review_kind,
        "authorisation": {
            "capacity": "author_side",
            "authorised": True,
            "policy_status": "permitted",
        },
        "confidentiality": {
            "classification": "author_owned_draft",
            "processing": "local_only",
            "external_transmission_authorised": False,
        },
        "review_only": True,
        "input_artifacts": [
            {
                "artifact_id": "paper-source",
                "kind": "source",
                "lineage_id": "paper-v1",
                "locator": "paper/main.tex",
                "sha256": HEX_A,
            },
            {
                "artifact_id": "paper-pdf",
                "kind": "pdf",
                "lineage_id": "paper-v1",
                "locator": "paper/main.pdf",
                "sha256": HEX_B,
            },
        ],
        "source_pdf_alignment": {
            "status": "matched",
            "verified": True,
            "evidence": "Title, section sequence, and build lineage match.",
        },
        "target": {"venue": "unknown", "year": None, "track": None},
        "venue_profile": {
            "status": "unknown",
            "profile_id": None,
            "source_sha256": None,
        },
        "runtime_profile": {
            "surface": "Codex",
            "host_build": "not_surfaced",
            "requested_model": "gpt-5.6-sol",
            "requested_mode": "ultra",
            "configuration_source": "adapter-controlled root dispatch",
            "configuration_proof": {
                "subject_kind": "root",
                "subject_id": "RUN-2026-001",
                "proof_kind": "host_loaded_profile_receipt",
                "locator": "evidence/root-profile.json",
                "sha256": HEX_A,
            },
            "adapter_controlled_fallback": "prohibited_and_checked",
            "selected_candidate_id": selected,
            "adapter_sha256": manifest["adapter_payload_sha256"],
            "model_validation": validation_state("passed" if passed else "not_run"),
            "mode_validation": validation_state("passed" if passed else "not_run"),
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
                    "criterion_id": "SC-CLAIMS",
                    "risk": "material",
                    "delegation_decision": "root_covers",
                    "rationale": "Bounded source; no isolated specialist needed.",
                }
            ],
            "task_count_as_runtime_observation": 0,
            "tasks": [],
        },
        "coverage": {
            "matrix_sha256": coverage_digest(coverage),
            "criteria": coverage_rows(coverage),
        },
        "stages": [
            {
                "stage_id": "input-freeze",
                "status": "complete",
                "evidence": ["paper-source", "paper-pdf"],
            },
            {
                "stage_id": "scientific-assessment",
                "status": "complete",
                "evidence": ["paper-source"],
            },
        ],
        "output_artifacts": {
            "finding_ledger": "finding-ledger.json",
            "reviewer_report": "reviewer-report.md",
            "ae_assessment": "ae-assessment.md",
            "review_summary": "review-summary.md",
        },
        "completion": "complete",
        "limitations": [],
    }


def finding_fixture(*, review_kind: str = "initial") -> dict:
    finding = {
        "finding_id": "",
        "review_kind": review_kind,
        "prior_finding_id": None,
        "adjudication_status": "retained",
        "adjudication_rationale": "Evidence supports retaining this issue.",
        "delta_status": "not_applicable" if review_kind == "initial" else "new",
        "impact_change": "not_applicable",
        "evidence_state": "verified",
        "criterion": "SC-CLAIMS",
        "related_criteria": [],
        "decision_impact": "material",
        "confidence": "high",
        "claim": "The headline claim exceeds the experiment's tested scope.",
        "evidence": {
            "artifact_id": "paper-source",
            "source_anchor": "Section 5, first paragraph",
            "semantic_anchor": "claim:headline-generalisation",
            "observation": "The claim covers unseen domains; experiments cover one domain.",
        },
        "why_it_matters": "The central conclusion is not established as written.",
        "action_type": "prose-repair",
        "closure_requirement": {
            "state": "open",
            "owner": "author",
            "gate": "prose",
            "requirement": "Narrow the claim or provide matching evidence.",
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
        self.root = pathlib.Path(self.temp.name)
        self.manifest, self.promotion = make_bundle(self.root)
        self.coverage = load_review_coverage(self.root)
        self.run = run_fixture(self.coverage, self.manifest, self.promotion)
        self.ledger = ledger_fixture()
        self.run["coverage"]["criteria"][1]["disposition"] = "finding_linked"
        finding_id = self.ledger["findings"][0]["finding_id"]
        self.run["coverage"]["criteria"][1]["finding_ids"] = [finding_id]

    def tearDown(self) -> None:
        self.temp.cleanup()

    def assertErrorContains(self, errors: list[str], needle: str) -> None:
        self.assertTrue(
            any(needle in error for error in errors),
            f"{needle!r} not found in {errors!r}",
        )

    def test_valid_initial_pair_and_unknown_venue(self) -> None:
        self.assertEqual(
            [],
            validate_run_pair(
                self.run, self.ledger, self.coverage, self.root
            ),
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
            validate_finding_ledger(self.ledger), "source anchor"
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
        self.assertErrorContains(
            validate_finding_ledger(self.ledger), "initial finding"
        )

        delta = ledger_fixture(review_kind="delta")
        carried = delta["findings"][0]
        carried["delta_status"] = "still_open"
        carried["impact_change"] = "unchanged"
        carried["prior_finding_id"] = None
        self.assertErrorContains(
            validate_finding_ledger(delta), "carried-forward delta finding"
        )

    def test_carried_delta_finding_preserves_stable_id(self) -> None:
        delta = ledger_fixture(review_kind="delta")
        carried = delta["findings"][0]
        carried["prior_finding_id"] = "F-1111111111111111"
        carried["delta_status"] = "still_open"
        carried["impact_change"] = "unchanged"
        self.assertErrorContains(
            validate_finding_ledger(delta), "preserve finding_id"
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
        self.assertErrorContains(errors, "cannot be closed")

    def test_candidate_cannot_survive_complete_ledger(self) -> None:
        self.ledger["findings"][0]["adjudication_status"] = "candidate"
        self.assertErrorContains(
            validate_finding_ledger(self.ledger), "candidate"
        )

    def test_run_and_ledger_kinds_must_match(self) -> None:
        self.ledger["review_kind"] = "delta"
        self.assertErrorContains(
            validate_run_pair(self.run, self.ledger, self.coverage, self.root),
            "review_kind mismatch",
        )

    def test_coverage_is_exact_and_evidence_bounded(self) -> None:
        self.run["coverage"]["criteria"].pop()
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "missing canonical criterion",
        )
        self.run = run_fixture(self.coverage, self.manifest, self.promotion)
        self.run["coverage"]["criteria"][0]["evidence"] = []
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "applicable criterion requires evidence",
        )

    def test_uncertain_or_blocked_coverage_cannot_be_complete(self) -> None:
        row = self.run["coverage"]["criteria"][0]
        row["applicability"] = "uncertain"
        row["disposition"] = "blocked"
        row["rationale"] = "The source lineage receipt is missing."
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "uncertain criterion requires partial or blocked completion",
        )

    def test_source_pdf_failure_cannot_be_complete(self) -> None:
        self.run["source_pdf_alignment"]["verified"] = False
        self.run["source_pdf_alignment"]["status"] = "mismatch"
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "source/PDF"
        )

    def test_configuration_proof_cannot_be_self_report_or_static_example(self) -> None:
        proof = self.run["runtime_profile"]["configuration_proof"]
        proof["proof_kind"] = "self_report"
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "configuration proof"
        )
        proof["proof_kind"] = "static_toml"
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "configuration proof"
        )

    def test_substantive_task_requires_sol_ultra_leaf_and_no_fallback(self) -> None:
        task = {
            "task_id": "T-1",
            "substantive": True,
            "trigger": "Independent finding verification is materially needed.",
            "task_effects": ["verify_finding"],
            "requested_model": "gpt-5.6-sol",
            "requested_mode": "ultra",
            "configuration_source": "adapter-controlled dispatch",
            "configuration_proof": {
                "subject_kind": "task",
                "subject_id": "T-1",
                "proof_kind": "adapter_dispatch_record",
                "locator": "evidence/T-1-dispatch.json",
                "sha256": HEX_A,
            },
            "adapter_controlled_fallback": "prohibited_and_checked",
            "model_validation": validation_state(),
            "mode_validation": validation_state(),
            "fork_policy": "none",
            "leaf_only": True,
            "descendant_state": "none",
            "agent_or_task_identifier": "runtime-T-1",
            "status": "completed",
            "report_artifact": "reports/T-1.json",
        }
        self.run["delegation"]["tasks"] = [task]
        self.run["delegation"]["task_count_as_runtime_observation"] = 1
        self.assertEqual(
            [], validate_run_manifest(self.run, self.coverage, self.root)
        )
        task["requested_mode"] = "max"
        task["adapter_controlled_fallback"] = "uncontrolled"
        task["leaf_only"] = False
        task["descendant_state"] = "unknown"
        errors = validate_run_manifest(self.run, self.coverage, self.root)
        self.assertErrorContains(errors, "gpt-5.6-sol + ultra")
        self.assertErrorContains(errors, "fallback")
        self.assertErrorContains(errors, "leaf-only")
        self.assertErrorContains(errors, "descendant")

    def test_finding_operation_cannot_be_marked_non_substantive(self) -> None:
        task = {
            "task_id": "T-1",
            "substantive": False,
            "trigger": "Check a finding.",
            "task_effects": ["adjudicate_finding"],
            "requested_model": None,
            "requested_mode": None,
            "configuration_source": None,
            "configuration_proof": None,
            "adapter_controlled_fallback": "not_applicable",
            "model_validation": validation_state(),
            "mode_validation": validation_state(),
            "fork_policy": "none",
            "leaf_only": True,
            "descendant_state": "none",
            "agent_or_task_identifier": "runtime-T-1",
            "status": "completed",
            "report_artifact": "reports/T-1.json",
        }
        self.run["delegation"]["tasks"] = [task]
        self.run["delegation"]["task_count_as_runtime_observation"] = 1
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
            "derived substantive",
        )

    def test_configured_and_evaluated_requires_selected_promotion(self) -> None:
        self.run["runtime_profile"]["compatibility_claim"] = (
            "configured-and-evaluated"
        )
        self.assertErrorContains(
            validate_run_manifest(self.run, self.coverage, self.root),
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
        )
        self.assertEqual([], validate_run_manifest(run, coverage, self.root))

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
        )
        errors = validate_run_manifest(run, coverage, self.root)
        self.assertErrorContains(errors, "promotion result")
        self.assertErrorContains(errors, "promotion decision")

        run["runtime_profile"]["promotion_evaluation_record"]["candidate_id"] = (
            "persisted-task-registry"
        )
        self.assertErrorContains(
            validate_run_manifest(run, coverage, self.root),
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
        )
        run["runtime_profile"]["promotion_evaluation_record"][
            "record_locator"
        ] = "../outside.json"
        self.assertErrorContains(
            validate_run_manifest(run, coverage, self.root), "locator"
        )

        run = run_fixture(
            coverage,
            manifest,
            promotion,
            compatibility="configured-and-evaluated",
        )
        promotion_path = self.root / "compatibility/adapter-promotion.json"
        promotion_path.write_text("{}\n", encoding="utf-8")
        self.assertErrorContains(
            validate_run_manifest(run, coverage, self.root), "promotion"
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
        self.run["coverage"]["criteria"][1]["finding_ids"].append(
            merged["finding_id"]
        )
        errors = validate_run_pair(
            self.run, self.ledger, self.coverage, self.root
        )
        self.assertErrorContains(errors, "merged finding cannot satisfy coverage")
        self.assertErrorContains(errors, "merge target does not exist")

    def test_adapter_manifest_mapping_and_selected_allowlist_are_fixed(self) -> None:
        manifest, _ = make_bundle(
            self.root, selected="minimal-settled-set"
        )
        manifest["candidate_implementations"]["minimal-settled-set"] = (
            MAPPING["persisted-task-registry"]
        )
        manifest["active_files"].append(MAPPING["persisted-task-registry"])
        errors = validate_adapter_manifest(manifest, self.root)
        self.assertErrorContains(errors, "candidate mapping")
        self.assertErrorContains(errors, "unselected lifecycle implementation")

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
        )
        self.assertEqual([], validate_run_manifest(run, coverage, self.root))
        run["runtime_profile"]["effective_telemetry"] = "not_surfaced"
        run["runtime_profile"]["resolved_model"] = None
        run["runtime_profile"]["resolved_mode"] = None
        self.assertErrorContains(
            validate_run_manifest(run, coverage, self.root), "runtime attestation"
        )

    def test_loader_only_accepts_canonical_manifest_and_promotion_paths(self) -> None:
        loaded = load_adapter_manifest(self.root)
        self.assertEqual(self.manifest, loaded)
        with self.assertRaises(ValueError):
            load_adapter_promotion(self.root, "../promotion.json")


class AdapterPromotionShapeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
