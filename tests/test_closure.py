from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

from evals.validate_closure import (
    validate_closure_record,
    validate_output_manifest,
    validate_semantic_adjudication,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ClosureContractTests(unittest.TestCase):
    def test_closure_validator_cli_runs_from_repository_root(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "evals/validate_closure.py",
                (
                    "evals/results/public-conformance-v1/"
                    "closure-oracle-blindness.json"
                ),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            0,
            completed.returncode,
            msg=completed.stdout + completed.stderr,
        )
        self.assertIn(
            "evaluation closure records validate",
            completed.stdout,
        )

    def test_semantic_adjudication_reconciles_counts_and_verdict(self) -> None:
        record = {
            "schema_version": "1.0.0",
            "judge_performed": True,
            "candidate_sha256": "a" * 64,
            "requested_configuration": {
                "model": "gpt-5.6-sol",
                "mode": "ultra",
                "fork_turns": "none",
                "leaf_only": True,
            },
            "fixtures": [
                {
                    "fixture_id": "fixture-a",
                    "required_matches": [
                        {
                            "oracle_finding_id": "O-1",
                            "matched_candidate_finding_ids": ["F-1"],
                            "semantic_match": True,
                            "evidence": "The frozen finding states the same "
                            "scientific defect at the same evidence anchor.",
                        }
                    ],
                    "prohibited_retained": [],
                    "hard_expectation_failures": [],
                    "other_hard_gate_failures": [],
                    "oracle_contract_issues": [],
                    "verdict": "pass",
                }
            ],
            "aggregate": {
                "fixture_count": 1,
                "pass_count": 1,
                "fail_count": 0,
                "required_obligation_count": 1,
                "matched_obligation_count": 1,
                "prohibited_retained_count": 0,
            },
            "overall_verdict": "pass",
            "limitations": [
                "Semantic equivalence remains a bounded judge assessment."
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "evals/fixtures").mkdir(parents=True)
            shutil.copy2(
                ROOT / "evals/semantic-adjudication.schema.json",
                root / "evals/semantic-adjudication.schema.json",
            )
            (root / "evals/fixtures/manifest.json").write_text(
                json.dumps(
                    {"fixtures": [{"fixture_id": "fixture-a"}]}
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                validate_semantic_adjudication(record, root),
            )
            changed = copy.deepcopy(record)
            changed["aggregate"]["pass_count"] = 0
            self.assertTrue(
                validate_semantic_adjudication(changed, root)
            )

    def test_output_manifest_reloads_and_hashes_every_public_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / "result.json"
            path.write_text('{"result":"pass"}\n', encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {
                "schema_version": "1.0.0",
                "evaluation_id": "eval-1",
                "compatibility_payload_sha256": "a" * 64,
                "fixture_set": "public-conformance-v1",
                "outputs": [
                    {
                        "artifact_id": "result",
                        "locator": "result.json",
                        "sha256": digest,
                        "privacy": "public",
                        "role": "aggregate-result",
                    }
                ],
            }
            self.assertEqual([], validate_output_manifest(manifest, ROOT, root))
            path.write_text('{"result":"changed"}\n', encoding="utf-8")
            self.assertTrue(validate_output_manifest(manifest, ROOT, root))

    def test_private_evidence_is_referenced_by_digest_not_path(self) -> None:
        manifest = {
            "schema_version": "1.0.0",
            "evaluation_id": "eval-1",
            "compatibility_payload_sha256": "a" * 64,
            "fixture_set": "public-conformance-v1",
            "outputs": [
                {
                    "artifact_id": "private-control",
                    "locator": "/home/example/private.json",
                    "sha256": "b" * 64,
                    "privacy": "private-reference",
                    "role": "external-mechanism-evidence",
                }
            ],
        }
        errors = validate_output_manifest(manifest, ROOT, ROOT)
        self.assertTrue(any("private reference" in error for error in errors))

    def test_closure_domain_and_payload_are_exact(self) -> None:
        record = {
            "schema_version": "1.0.0",
            "closure_id": "closure-science",
            "domain": "scientific-quality",
            "status": "pass",
            "evaluated_payload_sha256": "a" * 64,
            "evidence_ids": ["public-suite", "adapter-promotion"],
            "limitations": ["Runtime telemetry is not surfaced."],
        }
        self.assertEqual([], validate_closure_record(record, ROOT))
        changed = copy.deepcopy(record)
        changed["domain"] = "style"
        self.assertTrue(validate_closure_record(changed, ROOT))

    def test_pass_requires_evidence_and_retains_limitations(self) -> None:
        record = {
            "schema_version": "1.0.0",
            "closure_id": "closure-runtime",
            "domain": "runtime-provenance",
            "status": "pass",
            "evaluated_payload_sha256": "a" * 64,
            "evidence_ids": [],
            "limitations": [],
        }
        errors = validate_closure_record(record, ROOT)
        self.assertTrue(any("passing closure" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
