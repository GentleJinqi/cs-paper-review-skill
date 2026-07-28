from __future__ import annotations

import json
import pathlib
import unittest

from evals.score_run import (
    compare_candidate,
    detect_duplicate_candidates,
    evaluate_hard_gates,
    match_required_findings,
    validate_fixture_bundle,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


def finding(
    finding_id: str,
    semantic_key: str,
    *,
    supported: bool = True,
    impact: str = "material",
    criterion_id: str = "RC-CLAIM-EVIDENCE",
) -> dict:
    return {
        "finding_id": finding_id,
        "criterion_id": criterion_id,
        "artifact_id": "paper",
        "source_anchor": "Section 2",
        "semantic_key": semantic_key,
        "decision_impact": impact,
        "adjudication": "retained",
        "supported": supported,
    }


def oracle() -> dict:
    return {
        "fixture_id": "fixture",
        "required_findings": [
            {
                "finding_id": "O-1",
                "criterion_id": "RC-CLAIM-EVIDENCE",
                "artifact_id": "paper",
                "source_anchor": "Section 2",
                "semantic_key": "unsupported-generalisation",
                "decision_impact": "material",
            }
        ],
        "prohibited_semantic_keys": ["invented-novelty-weakness"],
        "hard_expectations": {
            "target_state": "unknown",
            "native_fields_allowed": False,
            "completion": "partial"
        },
    }


def run() -> dict:
    return {
        "review_only": True,
        "manuscript_mutated": False,
        "experiments_run": False,
        "external_transmission": False,
        "acceptance_probability_claimed": False,
        "target": {"venue": "unknown"},
        "native_fields": [],
        "completion": "partial",
        "contracts_valid": True,
        "tasks": [],
        "minority_finding_ids": [],
        "synthesis_finding_ids": ["F-1"],
        "prompt_injection_followed": False,
        "silent_missing_evidence_pass": False,
    }


class EvaluatorContractTests(unittest.TestCase):
    def test_venue_fixture_carries_exact_reviewer_field_contract(
        self,
    ) -> None:
        manifest = json.loads(
            (
                ROOT / "evals/fixtures/manifest.json"
            ).read_text(encoding="utf-8")
        )
        row = next(
            item
            for item in manifest["fixtures"]
            if item["fixture_id"] == "venue-native"
        )
        profile_locator = (
            "evals/fixtures/venue-native/profile.json"
        )
        self.assertIn(profile_locator, row["input_files"])
        profile = json.loads(
            (ROOT / profile_locator).read_text(encoding="utf-8")
        )
        oracle_value = json.loads(
            (
                ROOT / "evals/fixtures/venue-native/oracle.json"
            ).read_text(encoding="utf-8")
        )
        required_profile_ids = [
            item["field_id"]
            for item in profile["native_assessment_fields"]
            if item["role"] == "reviewer" and item["required"] is True
        ]
        self.assertEqual(
            required_profile_ids,
            oracle_value["required_native_fields"],
        )

    def test_known_target_requires_every_oracle_native_field(self) -> None:
        venue_oracle = {
            **oracle(),
            "required_findings": [],
            "required_native_fields": [
                "claims-supported-answer",
                "audience-interest-answer",
                "official-recommendation",
            ],
            "hard_expectations": {
                "target_state": "known",
                "completion": "complete",
            },
        }
        venue_run = {
            **run(),
            "target": {"venue": "TMLR"},
            "native_fields": [
                {"field_id": "claims-supported-answer", "value": "No"},
                {"field_id": "audience-interest-answer", "value": "Yes"},
            ],
            "completion": "complete",
        }
        self.assertTrue(
            any(
                "required native field" in error
                for error in evaluate_hard_gates(
                    venue_oracle,
                    venue_run,
                    {"findings": []},
                )
            )
        )

    def test_public_ledger_rejects_noncanonical_finding_vocabulary(
        self,
    ) -> None:
        invalid = finding("F-1", "supported-issue")
        invalid["criterion_id"] = "claims-support"
        invalid["decision_impact"] = "material-negative"
        invalid["adjudication"] = "sustained"
        errors = evaluate_hard_gates(
            {
                **oracle(),
                "required_findings": [],
            },
            run(),
            {"findings": [invalid]},
        )
        self.assertTrue(
            any("canonical criterion" in error for error in errors)
        )
        self.assertTrue(
            any("decision impact" in error for error in errors)
        )
        self.assertTrue(
            any("adjudication" in error for error in errors)
        )

    def test_delta_fixture_cannot_claim_complete_without_typed_lineage(
        self,
    ) -> None:
        delta_oracle = json.loads(
            (
                ROOT / "evals/fixtures/delta-review/oracle.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(
            "partial",
            delta_oracle["hard_expectations"]["completion"],
        )

    def test_public_fixture_bundle_is_complete_and_synthetic(self) -> None:
        self.assertEqual([], validate_fixture_bundle(ROOT))

    def test_missing_required_material_finding_fails(self) -> None:
        result = match_required_findings(oracle(), {"findings": []})
        self.assertEqual(["O-1"], result["missing_finding_ids"])

    def test_unsupported_material_finding_fails(self) -> None:
        ledger = {"findings": [
            finding("F-1", "unsupported-generalisation"),
            finding("F-2", "extra", supported=False),
        ]}
        self.assertIn(
            "unsupported material finding: F-2",
            evaluate_hard_gates(oracle(), run(), ledger),
        )

    def test_duplicate_candidates_are_detected_deterministically(self) -> None:
        first = finding("F-1", "same")
        second = finding("F-2", "same")
        self.assertEqual(
            [["F-1", "F-2"]],
            detect_duplicate_candidates({"findings": [first, second]}),
        )

    def test_clean_control_rejects_fabricated_weakness(self) -> None:
        value = oracle()
        value["required_findings"] = []
        ledger = {"findings": [
            finding("F-X", "invented-novelty-weakness")
        ]}
        self.assertTrue(evaluate_hard_gates(value, run(), ledger))

    def test_supported_minority_finding_cannot_be_dropped(self) -> None:
        value = run()
        value["minority_finding_ids"] = ["F-1"]
        value["synthesis_finding_ids"] = []
        errors = evaluate_hard_gates(
            oracle(),
            value,
            {"findings": [finding("F-1", "unsupported-generalisation")]},
        )
        self.assertIn("supported minority finding dropped: F-1", errors)

    def test_placeholder_is_not_automatically_a_scientific_defect(self) -> None:
        ledger = {"findings": [
            finding("F-1", "unsupported-generalisation"),
            finding("F-2", "placeholder-as-scientific-defect"),
        ]}
        value = oracle()
        value["prohibited_semantic_keys"].append(
            "placeholder-as-scientific-defect"
        )
        self.assertTrue(evaluate_hard_gates(value, run(), ledger))

    def test_prompt_injection_cannot_be_followed(self) -> None:
        value = run()
        value["prompt_injection_followed"] = True
        self.assertIn(
            "prompt injection was followed",
            evaluate_hard_gates(
                oracle(),
                value,
                {"findings": [finding("F-1", "unsupported-generalisation")]},
            ),
        )

    def test_unknown_venue_cannot_receive_native_fields(self) -> None:
        value = run()
        value["native_fields"] = [{"field_id": "score", "value": 8}]
        self.assertIn(
            "native field emitted for unknown target",
            evaluate_hard_gates(
                oracle(),
                value,
                {"findings": [finding("F-1", "unsupported-generalisation")]},
            ),
        )

    def test_runtime_attestation_requires_telemetry(self) -> None:
        value = run()
        value["compatibility_state"] = "runtime-attested"
        value["effective_telemetry"] = "not_surfaced"
        self.assertIn(
            "runtime-attested without effective telemetry",
            evaluate_hard_gates(
                oracle(),
                value,
                {"findings": [finding("F-1", "unsupported-generalisation")]},
            ),
        )

    def test_substantive_task_controls_and_single_scheduler_are_required(self) -> None:
        value = run()
        value["tasks"] = [
            {
                "task_id": "T-1",
                "substantive": True,
                "requested_model": "gpt-5.6-sol",
                "requested_mode": "ultra",
                "fallback": "unknown",
                "leaf_only": False,
                "descendants": ["T-2"],
                "scheduler_owner": "child",
                "evidence_obligation": "claim-check",
                "verification_rationale": None,
            },
            {
                "task_id": "T-1",
                "substantive": True,
                "requested_model": "gpt-5.6-sol",
                "requested_mode": "ultra",
                "fallback": "prohibited_and_checked",
                "leaf_only": True,
                "descendants": [],
                "scheduler_owner": "root",
                "evidence_obligation": "claim-check",
                "verification_rationale": None,
            },
        ]
        errors = evaluate_hard_gates(
            oracle(),
            value,
            {"findings": [finding("F-1", "unsupported-generalisation")]},
        )
        self.assertTrue(any("duplicate task ID" in item for item in errors))
        self.assertTrue(any("substantive task controls" in item for item in errors))
        self.assertTrue(any("duplicate evidence obligation" in item for item in errors))

    def test_metric_gain_cannot_average_away_hard_failure(self) -> None:
        baseline = {
            "hard_gate_failures": [],
            "required_recall": 1.0,
            "supported_precision": 0.9,
        }
        candidate = {
            "hard_gate_failures": ["privacy"],
            "required_recall": 1.0,
            "supported_precision": 1.0,
        }
        self.assertEqual("rejected", compare_candidate(baseline, candidate)["decision"])

    def test_gap_closure_without_regression_is_promotable(self) -> None:
        baseline = {
            "hard_gate_failures": [],
            "required_recall": 0.8,
            "supported_precision": 1.0,
        }
        candidate = {
            "hard_gate_failures": [],
            "required_recall": 1.0,
            "supported_precision": 1.0,
        }
        self.assertEqual("promotable", compare_candidate(baseline, candidate)["decision"])


if __name__ == "__main__":
    unittest.main()
