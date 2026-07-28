from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import json

from scripts.review_skill_validation import (
    REQUIRED_TREE,
    _audit_schema_node,
    _validate_schema_node,
    active_text_files,
    adapter_payload_sha256,
    compatibility_payload_sha256,
    validate_adapter_profile,
    validate_bundle,
    validate_json_files,
    validate_no_count_based_rigor,
    validate_no_retired_public_guidance,
    validate_reference_boundaries,
    validate_required_tree,
    validate_skill_frontmatter,
    load_review_coverage,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
CORE_FILES = (
    "references/scientific-core.md",
    "references/review-coverage.md",
    "references/review-coverage.json",
    "references/review-workflow.md",
    "references/finding-contract.md",
    "references/delta-review.md",
    "references/privacy-and-authorisation.md",
    "references/venue-conditioning.md",
)


class BundleContractTests(unittest.TestCase):
    def test_bundle_validator_cli_runs_from_repository_root(self) -> None:
        completed = subprocess.run(
            [sys.executable, "scripts/validate_bundle.py", "."],
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

    def test_required_tree_is_complete(self) -> None:
        self.assertEqual([], validate_required_tree(ROOT))
        for relative in REQUIRED_TREE:
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_skill_frontmatter_is_single_and_trigger_specific(self) -> None:
        self.assertEqual([], validate_skill_frontmatter(ROOT))

    def test_active_markdown_references_resolve(self) -> None:
        self.assertEqual([], validate_reference_boundaries(ROOT))

    def test_all_active_json_parses(self) -> None:
        self.assertEqual([], validate_json_files(ROOT))

    def test_active_guidance_has_no_count_based_rigor(self) -> None:
        self.assertEqual([], validate_no_count_based_rigor(ROOT))

    def test_adapter_profile_exposes_required_controls(self) -> None:
        self.assertEqual([], validate_adapter_profile(ROOT))

    def test_model_independent_core_has_no_runtime_or_project_terms(self) -> None:
        forbidden = (
            "gpt-",
            "ultra",
            "codex",
            "subagent",
            "work1-paper",
            "default venue",
        )
        for relative in CORE_FILES:
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            lowered = path.read_text(encoding="utf-8").lower()
            for token in forbidden:
                self.assertNotIn(token, lowered, f"{relative}: {token}")

    def test_canonical_coverage_has_34_aligned_owned_criteria(self) -> None:
        matrix = load_review_coverage(ROOT)
        rows = matrix["criteria"]
        ids = [row["criterion_id"] for row in rows]
        self.assertEqual(34, len(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(row["primary_stage_owner"] for row in rows))
        markdown = (ROOT / "references/review-coverage.md").read_text(
            encoding="utf-8"
        )
        markdown_ids = re.findall(r"`(RC-[A-Z0-9-]+)`", markdown)
        self.assertEqual(ids, markdown_ids)

    def test_scientific_core_covers_material_review_responsibilities(self) -> None:
        text = " ".join(
            (ROOT / "references/scientific-core.md")
            .read_text(encoding="utf-8")
            .casefold()
            .split()
        )
        for token in (
            "input",
            "source",
            "rendered",
            "authorisation",
            "confidential",
            "problem",
            "contribution",
            "prior work",
            "formal",
            "method",
            "data provenance",
            "metric",
            "experiment",
            "statistical",
            "effect size",
            "multiple comparisons",
            "robustness",
            "generalisation",
            "reproducibility",
            "compute",
            "figures",
            "limitations",
            "ethics",
            "partial",
            "blocked",
        ):
            self.assertIn(token, text, token)

    def test_skill_is_a_lean_router_with_intake_and_stopping_logic(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        lowered = text.lower()
        for token in (
            "authorisation",
            "confidential",
            "source",
            "pdf",
            "target",
            "review-only",
            "coverage",
            "partial",
            "blocked",
            "stop",
        ):
            self.assertIn(token, lowered, token)
        self.assertLessEqual(len(text.split()), 1100)
        self.assertLessEqual(lowered.count("## "), 8)

    def test_history_sources_and_tests_are_not_active_guidance(self) -> None:
        relatives = {
            path.relative_to(ROOT).as_posix() for path in active_text_files(ROOT)
        }
        self.assertIn("README.md", relatives)
        self.assertIn("README.zh-CN.md", relatives)
        self.assertFalse(any(path.startswith("docs/") for path in relatives))
        self.assertFalse(any(path.startswith("sources/") for path in relatives))
        self.assertFalse(any(path.startswith("tests/") for path in relatives))

    def test_bundle_aggregate_is_clean(self) -> None:
        self.assertEqual([], validate_bundle(ROOT))

    def test_adapter_fixture_inputs_do_not_disclose_oracle_answers(self) -> None:
        for path in sorted(
            (ROOT / "evals" / "adapter-fixtures").glob("*/input.json")
        ):
            value = json.loads(path.read_text(encoding="utf-8"))
            payload = value["payload"]
            self.assertNotIn("required_behavior", payload, path.as_posix())
            questions = payload.get("evaluation_questions")
            self.assertIsInstance(questions, list, path.as_posix())
            self.assertEqual(value["assertion_ids"], [
                item["assertion_id"] for item in questions
            ])
            scenario = value["scenario"].casefold()
            for answer_leak in (
                "must retain",
                "must avoid",
                "must not",
                "required behavior",
                "expected result",
            ):
                self.assertNotIn(answer_leak, scenario, path.as_posix())


class ValidatorNegativeFixtureTests(unittest.TestCase):
    def test_count_based_rigor_is_detected_but_history_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "references").mkdir()
            (root / "docs").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: fixture\ndescription: Author-side CS paper review\n---\n"
                "Use 10-13 reviewers as a strict tier.\n",
                encoding="utf-8",
            )
            (root / "docs" / "legacy.md").write_text(
                "Use 10-13 reviewers as a strict tier.\n", encoding="utf-8"
            )
            errors = validate_no_count_based_rigor(root)
            self.assertTrue(errors)
            self.assertTrue(all("docs/legacy.md" not in error for error in errors))

    def test_negated_count_guidance_is_not_a_false_positive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "SKILL.md").write_text(
                "---\nname: fixture\ndescription: Author-side CS paper review\n---\n"
                "There is no fixed task count or required reviewer roster.\n",
                encoding="utf-8",
            )
            self.assertEqual([], validate_no_count_based_rigor(root))

    def test_negation_does_not_hide_a_later_positive_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "SKILL.md").write_text(
                "---\nname: fixture\ndescription: Author-side CS paper review\n---\n"
                "There is no fixed task count; the default venue is TMLR.\n",
                encoding="utf-8",
            )
            errors = validate_no_count_based_rigor(root)
            self.assertTrue(errors)

    def test_structured_and_wrapped_fixed_topology_guidance_is_detected(
        self,
    ) -> None:
        fixtures = {
            "SKILL.md": (
                "---\nname: fixture\n"
                "description: Author-side CS paper review\n---\n"
                "- Always dispatch thirteen\n"
                "  reviewers for every review.\n"
            ),
            "README.md": (
                "# Fixture\n\n"
                "```json\n"
                '{"guidance":"Always dispatch thir\\u0074een reviewers."}\n'
                "```\n"
            ),
            "references/policy.json": (
                '{"guidance":"Always dispatch thir\\u0074een reviewers."}\n'
            ),
            "agents/policy.yaml": (
                "guidance: >\n"
                "  Always dispatch thirteen\n"
                "  reviewers.\n"
            ),
            "adapters/policy.toml": (
                'guidance = """\n'
                "Always dispatch thirteen\n"
                "reviewers.\n"
                '"""\n'
            ),
        }
        for relative, content in fixtures.items():
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                    self.assertTrue(validate_no_count_based_rigor(root))

    def test_structured_siblings_and_negated_topology_are_not_joined(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / "references/policy.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "first": "Always dispatch thirteen",
                        "second": "reviewers.",
                        "nonclaim":
                            "There is no fixed reviewer count.",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual([], validate_no_count_based_rigor(root))

    def test_invisible_unicode_and_late_positive_topology_are_detected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "SKILL.md").write_text(
                "---\nname: fixture\n"
                "description: Author-side CS paper review\n---\n"
                "No fixed count; however, always dispatch "
                "thir\ufe0fteen reviewers.\n",
                encoding="utf-8",
            )
            self.assertTrue(validate_no_count_based_rigor(root))

    def test_numeric_runtime_assignment_but_not_schema_property_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            config = root / "references/config.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"max_threads":12}\n', encoding="utf-8")
            self.assertTrue(validate_no_count_based_rigor(root))

            config.write_text(
                '{"properties":{"max_threads":{"type":"integer"}}}\n',
                encoding="utf-8",
            )
            self.assertEqual([], validate_no_count_based_rigor(root))

    def test_missing_relative_reference_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "references").mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: fixture\ndescription: Author-side CS paper review\n---\n"
                "Read `references/missing.md`.\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [
                    "reference-boundary: SKILL.md has invalid reference "
                    "references/missing.md: locator does not resolve to a "
                    "regular file"
                ],
                validate_reference_boundaries(root),
            )

    def test_traversal_and_symlink_references_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "references").mkdir()
            (root / "outside.md").write_text("outside\n", encoding="utf-8")
            (root / "references" / "linked.md").symlink_to(root / "outside.md")
            (root / "SKILL.md").write_text(
                "---\nname: fixture\ndescription: Author-side CS paper review\n---\n"
                "Read `references/../outside.md` and "
                "`references/linked.md`.\n",
                encoding="utf-8",
            )
            errors = validate_reference_boundaries(root)
            self.assertTrue(any("traversal-free" in error for error in errors))
            self.assertTrue(any("symlink" in error for error in errors))

    def test_duplicate_json_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "schemas").mkdir()
            (root / "schemas" / "duplicate.json").write_text(
                '{"value": 1, "value": 2}\n', encoding="utf-8"
            )
            errors = validate_json_files(root)
            self.assertTrue(errors)
            self.assertIn("duplicate object key", errors[0])

    def test_aggregate_validates_adapter_manifest_not_only_prose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            path = root / "adapters/codex/adapter-manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["adapter_payload_sha256"] = "0" * 64
            path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any("adapter_payload_sha256" in error for error in errors),
                errors,
            )

    def test_aggregate_audits_every_published_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            path = root / "schemas/task-report.schema.json"
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema["maxProperties"] = 0
            path.write_text(
                json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any(
                    "schema-audit" in error and "maxProperties" in error
                    for error in errors
                ),
                errors,
            )

    def test_schema_subset_uses_json_numeric_integer_semantics(self) -> None:
        schema = {"type": "array", "minItems": 1.0, "maxItems": 2.0}
        self.assertEqual([], _audit_schema_node(schema))
        self.assertEqual(
            [],
            _validate_schema_node(
                ["one", "two"], schema, schema, "$"
            ),
        )
        errors = _validate_schema_node(
            ["one", "two", "three"], schema, schema, "$"
        )
        self.assertTrue(any("more than 2" in error for error in errors), errors)

    def test_schema_enum_rejects_json_equal_duplicates(self) -> None:
        errors = _audit_schema_node({"enum": [1, 1.0]})
        self.assertTrue(any("enum values must be unique" in error for error in errors))

    def test_aggregate_validates_the_venue_authority_registry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            path = root / "references/venue-authorities.json"
            registry = json.loads(path.read_text(encoding="utf-8"))
            registry["venues"] = []
            path.write_text(
                json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            manifest_path = root / "adapters/codex/adapter-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            from scripts.review_skill_validation import (
                compatibility_payload_sha256,
            )
            manifest["compatibility_payload_sha256"] = (
                compatibility_payload_sha256(root)
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any("venue-authority-registry" in error for error in errors),
                errors,
            )

    def test_aggregate_validates_the_canonical_coverage_instance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            path = root / "references/review-coverage.json"
            coverage = json.loads(path.read_text(encoding="utf-8"))
            coverage["criteria"][0]["review_question"] = 7
            coverage["criteria"][0]["required_evidence"] = "not-an-array"
            coverage["criteria"][0]["unexpected"] = True
            path.write_text(
                json.dumps(coverage, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any(
                    "review coverage schema validation failed" in error
                    for error in errors
                ),
                errors,
            )

    def test_compatibility_digest_covers_runtime_contract_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            manifest_path = root / "adapters/codex/adapter-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["adapter_payload_sha256"] = adapter_payload_sha256(root)
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            schema_path = root / "schemas/task-report.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["title"] = "Weakened or changed task report contract"
            schema_path.write_text(
                json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any("compatibility_payload_sha256" in error for error in errors),
                errors,
            )

    def test_compatibility_digest_covers_every_execution_generator(self) -> None:
        for relative in (
            "scripts/render_human_binding.py",
            "scripts/build_terminal_inventory.py",
        ):
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    shutil.copytree(ROOT, root, dirs_exist_ok=True)
                    path = root / relative
                    path.write_text(
                        path.read_text(encoding="utf-8")
                        + "\n# contract mutation\n",
                        encoding="utf-8",
                    )
                    errors = validate_bundle(root)
                    self.assertTrue(
                        any(
                            "compatibility_payload_sha256" in error
                            for error in errors
                        ),
                        errors,
                    )

    def test_adapter_evaluation_authority_is_unconditional(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            shutil.copytree(ROOT, root, dirs_exist_ok=True)
            authority_path = (
                root / "references/adapter-evaluation-authority.json"
            )
            authority = json.loads(
                authority_path.read_text(encoding="utf-8")
            )
            authority.pop("fixture_set")
            authority_path.write_text(
                json.dumps(authority, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            manifest_path = root / "adapters/codex/adapter-manifest.json"
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                "persisted-task-registry",
                manifest["selected_candidate_id"],
            )
            manifest["compatibility_payload_sha256"] = (
                compatibility_payload_sha256(root)
            )
            manifest_path.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            errors = validate_bundle(root)
            self.assertTrue(
                any(
                    "fixture_set" in error
                    for error in errors
                ),
                errors,
            )

    def test_schema_audit_rejects_nonfinite_bounds(self) -> None:
        errors = _audit_schema_node(
            {"type": "number", "minimum": float("-inf")}
        )
        self.assertTrue(
            any("must be finite" in error for error in errors),
            errors,
        )

    def test_pattern_validation_uses_ecmascript_whitespace_for_bom(self) -> None:
        schema = {"type": "string", "pattern": "\\S"}
        errors = _validate_schema_node("\ufeff", schema, schema, "$")
        self.assertTrue(
            any("does not match pattern" in error for error in errors),
            errors,
        )

    def test_venue_release_authority_pins_hosts_and_profile_bytes(self) -> None:
        for mutation in ("host", "profile_sha"):
            with self.subTest(mutation=mutation):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    shutil.copytree(ROOT, root, dirs_exist_ok=True)
                    registry_path = (
                        root / "references/venue-authorities.json"
                    )
                    registry = json.loads(
                        registry_path.read_text(encoding="utf-8")
                    )
                    icml = next(
                        row
                        for row in registry["venues"]
                        if row["venue"] == "ICML"
                    )
                    if mutation == "host":
                        icml["official_hosts"] = ["attacker.example"]
                    else:
                        icml["profiles"][0]["profile_sha256"] = "0" * 64
                    registry_path.write_text(
                        json.dumps(
                            registry,
                            indent=2,
                            ensure_ascii=False,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    manifest_path = (
                        root / "adapters/codex/adapter-manifest.json"
                    )
                    manifest = json.loads(
                        manifest_path.read_text(encoding="utf-8")
                    )
                    manifest["compatibility_payload_sha256"] = (
                        compatibility_payload_sha256(root)
                    )
                    manifest_path.write_text(
                        json.dumps(
                            manifest,
                            indent=2,
                            ensure_ascii=False,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    errors = validate_bundle(root)
                    self.assertTrue(
                        any(
                            "venue-authority-registry" in error
                            and (
                                "not approved" in error
                                or "hash mismatch" in error
                            )
                            for error in errors
                        ),
                        errors,
                    )

    def test_published_venue_claims_bind_the_release_truth_table(self) -> None:
        expected_sources = {
            "tmlr-current-general:criterion:claims-supported":
                "tmlr-acceptance-criteria.json",
            "tmlr-current-general:criterion:audience-interest":
                "tmlr-acceptance-criteria.json",
            "tmlr-current-general:native_field:claims-supported-answer":
                "tmlr-reviewer-guide.json",
            "tmlr-current-general:native_field:audience-interest-answer":
                "tmlr-reviewer-guide.json",
            "tmlr-current-general:native_field:official-recommendation":
                "tmlr-reviewer-guide.json",
            "tmlr-current-general:native_field:action-editor-decision":
                "tmlr-ae-guide.json",
            "icml-2026-main:criterion:soundness":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:criterion:presentation":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:criterion:significance":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:criterion:originality":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:criterion:limitations":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:criterion:ethics":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:soundness-score":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:presentation-score":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:significance-score":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:originality-score":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:overall-recommendation":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:reviewer-confidence":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:final-justification":
                "icml-2026-reviewer-instructions.json",
            "icml-2026-main:native_field:meta-review":
                "icml-2026-ac-instructions.json",
            "cvpr-2026-main:criterion:sound-contribution":
                "cvpr-2026-reviewer-guidelines.json",
            "cvpr-2026-main:criterion:balanced-contribution":
                "cvpr-2026-reviewer-guidelines.json",
            "cvpr-2026-main:criterion:repairable-issues":
                "cvpr-2026-reviewer-guidelines.json",
            "cvpr-2026-main:criterion:meta-review-evidence":
                "cvpr-2026-ac-guidelines.json",
            "cvpr-2026-main:native_field:rating-and-justification":
                "cvpr-2026-training.json",
            "cvpr-2026-main:native_field:final-justification":
                "cvpr-2026-training.json",
            "cvpr-2026-main:native_field:meta-review":
                "cvpr-2026-ac-guidelines.json",
            "eccv-2026-main:criterion:sound-contribution":
                "eccv-2026-reviewer-guide.json",
            "eccv-2026-main:criterion:contribution-type-lens":
                "eccv-2026-contribution-types.json",
            "eccv-2026-main:criterion:meta-review-evidence":
                "eccv-2026-ac-guidelines.json",
            "eccv-2026-main:native_field:justification-of-rating":
                "eccv-2026-contribution-types.json",
            "eccv-2026-main:native_field:final-justification":
                "eccv-2026-ac-guidelines.json",
            "eccv-2026-main:native_field:meta-review":
                "eccv-2026-ac-guidelines.json",
        }
        expected_support = {
            "tmlr-current-general:criterion:claims-supported": (
                "provide more evidence by running more experiments",
                "adjust (reduce) their claims",
            ),
            "tmlr-current-general:criterion:audience-interest": (
                "new state-of-the-art",
                "not “novel enough”",
                "potential for impact",
            ),
            "icml-2026-main:criterion:soundness": (
                "Are the methods used appropriate?",
                "are the proofs correct",
                "are the experiments well-designed?",
            ),
            "icml-2026-main:criterion:presentation": (
                "overall narrative easy to follow",
                "prior/concurrent literature",
                "expert reader to reproduce",
            ),
            "icml-2026-main:criterion:significance": (
                "advance understanding, capabilities, or practice",
                "influence future research or applications",
            ),
            "icml-2026-main:criterion:originality": (
                "new tasks, methods, theory, data, or perspectives",
                "novel combination of existing techniques",
            ),
            "icml-2026-main:criterion:ethics": (
                "flag the paper for an ethics review",
                "explain your concerns in detail",
            ),
            "icml-2026-main:native_field:final-justification": (
                "weighed the strengths and weaknesses",
                "rebuttal addressed your main concerns",
            ),
            "icml-2026-main:native_field:overall-recommendation": (
                "Technically flawless paper with exceptional impact",
                "Technically solid paper, with high impact",
                "weaknesses, which overall outweigh the merits",
                "inadequate reproducibility",
                "paper with well-known results",
            ),
            "icml-2026-main:native_field:reviewer-confidence": (
                "very familiar with the related work",
                "not absolutely certain",
                "Math/other details were not carefully checked",
                "submission is not in your area",
            ),
            "icml-2026-main:native_field:meta-review": (
                "reviews themselves or the (anonymized) discussions",
                "average (or other aggregate) numerical scores",
                "read their rebuttals/comments and incorporated them",
                "important contradictions between reviews",
            ),
            "cvpr-2026-main:criterion:sound-contribution": (
                "list of strengths and weaknesses",
                "basis for your recommendation",
            ),
            "cvpr-2026-main:criterion:balanced-contribution": (
                "does not exceed the state-of-the-art accuracy",
                "novelty and potential impact",
            ),
            "cvpr-2026-main:criterion:meta-review-evidence": (
                "reviewers’ initial assessment",
                "reviewers’ reason for their final recommendation",
            ),
            "eccv-2026-main:criterion:sound-contribution": (
                "knowledge advancement it has made",
                "does not exceed the state-of-the-art accuracy",
                "novelty and potential impact of the work",
                "Minor flaws that can be easily corrected",
            ),
            "eccv-2026-main:criterion:meta-review-evidence": (
                "reviews, the authors’ rebuttal, and the discussion",
                "reviewer's confidence score",
                "more a measure of personality",
            ),
        }

        actual: dict[str, tuple[str, str]] = {}
        for evidence_path in sorted(
            (ROOT / "venues/source-evidence").glob("*.json")
        ):
            evidence = json.loads(
                evidence_path.read_text(encoding="utf-8")
            )
            for section in evidence["sections"]:
                excerpts = {
                    row["excerpt_id"]: row["text"]
                    for row in section["verbatim_excerpts"]
                }
                for claim in section["claims"]:
                    actual[claim["claim_id"]] = (
                        evidence_path.name,
                        "\n".join(
                            excerpts[excerpt_id]
                            for excerpt_id in claim["excerpt_ids"]
                        ),
                    )

        for claim_id, expected_source in expected_sources.items():
            with self.subTest(claim_id=claim_id, boundary="source"):
                self.assertIn(claim_id, actual)
                self.assertEqual(expected_source, actual[claim_id][0])
        for claim_id, phrases in expected_support.items():
            with self.subTest(claim_id=claim_id, boundary="support"):
                bound_text = actual[claim_id][1]
                for phrase in phrases:
                    self.assertIn(phrase, bound_text)

        icml_profile = json.loads(
            (ROOT / "venues/profiles/icml-2026-main.json").read_text(
                encoding="utf-8"
            )
        )
        icml_rules = {
            row["rule_id"]: row for row in icml_profile["criteria"]
        }
        icml_fields = {
            row["field_id"]: row
            for row in icml_profile["native_assessment_fields"]
        }
        for field_id, phrases in {
            "overall-recommendation": (
                "Technically flawless paper with exceptional impact",
                "inadequate reproducibility",
                "paper with well-known results",
            ),
            "reviewer-confidence": (
                "very familiar with the related work",
                "Math/other details were not carefully checked",
                "submission is not in your area",
            ),
        }.items():
            prompt = icml_fields[field_id]["prompt"]
            for phrase in phrases:
                with self.subTest(
                    field_id=field_id,
                    boundary="operational-calibration",
                    phrase=phrase,
                ):
                    self.assertIn(phrase, prompt)

        soundness_basis = {
            "RC-CLAIM-EVIDENCE",
            "RC-FORMAL-CORRECTNESS",
            "RC-METHOD-SOUNDNESS",
            "RC-DATA-VALIDITY",
            "RC-MEASUREMENT-VALIDITY",
            "RC-EXPERIMENT-DESIGN",
            "RC-STATISTICAL-VALIDITY",
            "RC-COMPARISON-FAIRNESS",
            "RC-ROBUSTNESS-SCOPE",
            "RC-RESOURCE-CLAIMS",
        }
        overall_basis = soundness_basis | {
            "RC-PROBLEM-FORMULATION",
            "RC-CONTRIBUTION-IDENTITY",
            "RC-RELATED-WORK",
            "RC-CITATION-SUPPORT",
            "RC-REPRODUCIBILITY",
            "RC-WRITING-CLARITY",
            "RC-VISUAL-INTEGRITY",
            "RC-LIMITATIONS",
            "RC-RESPONSIBLE-RESEARCH",
        }
        required_bases = {
            "criterion:soundness": soundness_basis,
            "field:soundness-score": soundness_basis,
            "field:overall-recommendation": overall_basis,
            "field:final-justification": overall_basis
                | {
                    "RC-DISSENT-PRESERVATION",
                    "RC-COMPLETION-TRUTH",
                },
            "field:meta-review": overall_basis
                | {
                    "RC-FINDING-EVIDENCE",
                    "RC-CONFLICT-VERIFICATION",
                    "RC-DISSENT-PRESERVATION",
                    "RC-COMPLETION-TRUTH",
                },
        }
        for locator, required_basis in required_bases.items():
            kind, item_id = locator.split(":", 1)
            item = (
                icml_rules[item_id]
                if kind == "criterion"
                else icml_fields[item_id]
            )
            actual_basis = set(item["portable_criterion_ids"])
            with self.subTest(
                locator=locator,
                boundary="portable-criterion-basis",
            ):
                self.assertTrue(
                    required_basis <= actual_basis,
                    sorted(required_basis - actual_basis),
                )


class AdapterProfileNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        shutil.copytree(ROOT / "adapters", self.root / "adapters")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def adapter_text(self) -> str:
        return (
            self.root / "adapters/codex-gpt-5.6-sol-ultra.md"
        ).read_text(encoding="utf-8")

    def write_adapter(self, text: str) -> None:
        (
            self.root / "adapters/codex-gpt-5.6-sol-ultra.md"
        ).write_text(text, encoding="utf-8")

    def assertProfileError(self, needle: str) -> None:
        errors = validate_adapter_profile(self.root)
        self.assertTrue(
            any(needle in error for error in errors),
            f"{needle!r} not found in {errors!r}",
        )

    def test_selected_manifest_requires_explicit_active_candidate(self) -> None:
        text = self.adapter_text()
        self.write_adapter(
            text.replace(
                "`persisted-task-registry` is the manifest-selected active "
                "lifecycle\nimplementation.",
                "The selected implementation is not stated here.",
            )
        )
        self.assertProfileError("selected lifecycle implementation is ambiguous")

    def test_terra_or_max_custom_agent_fails(self) -> None:
        path = self.root / "adapters/codex/agents/cs-paper-reviewer.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace('model = "gpt-5.6-sol"', 'model = "gpt-5.6-terra"'),
            encoding="utf-8",
        )
        self.assertProfileError("model must be gpt-5.6-sol")
        path.write_text(
            text.replace(
                'model_reasoning_effort = "ultra"',
                'model_reasoning_effort = "max"',
            ),
            encoding="utf-8",
        )
        self.assertProfileError("effort must be ultra")

    def test_custom_agent_name_is_exact_and_role_bound(self) -> None:
        path = self.root / "adapters/codex/agents/cs-paper-reviewer.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                'name = "cs_paper_reviewer"',
                'name = "generic_reviewer"',
            ),
            encoding="utf-8",
        )
        self.assertProfileError("name must be cs_paper_reviewer")

    def test_missing_leaf_or_fallback_control_fails(self) -> None:
        text = self.adapter_text()
        self.write_adapter(text.replace("leaf-only", "bounded-child"))
        self.assertProfileError("child topology")
        self.write_adapter(text.replace("no silent fallback", "fallback may occur"))
        self.assertProfileError("fallback prohibition")

    def test_max_equivalence_and_false_telemetry_claim_fail(self) -> None:
        text = self.adapter_text()
        self.write_adapter(
            text.replace(
                "`max` is not equivalent to Ultra",
                "`max` is equivalent to Ultra",
            )
        )
        self.assertProfileError("non-equivalent")
        self.write_adapter(
            text
            + "\n`effective_telemetry: not_surfaced` proves runtime attestation.\n"
        )
        self.assertProfileError("absent telemetry")

    def test_positive_fixed_reviewer_count_fails(self) -> None:
        self.write_adapter(self.adapter_text() + "\nAlways dispatch 4 reviewers.\n")
        errors = validate_no_count_based_rigor(self.root)
        self.assertTrue(errors)

    def test_public_readme_fixed_scheduler_guidance_fails(self) -> None:
        (self.root / "README.md").write_text(
            "# Fixture\n\nSet `max_threads = 12` for strict review.\n",
            encoding="utf-8",
        )
        errors = validate_no_count_based_rigor(self.root)
        self.assertTrue(any("README.md" in error for error in errors), errors)

    def test_public_readme_retired_contract_name_fails(self) -> None:
        (self.root / "README.md").write_text(
            "# Fixture\n\nWrite `frozen-inputs.md` first.\n",
            encoding="utf-8",
        )
        errors = validate_no_retired_public_guidance(self.root)
        self.assertTrue(any("frozen-inputs.md" in error for error in errors))

    def test_custom_agent_toml_rejects_trailing_invalid_syntax(self) -> None:
        path = self.root / "adapters/codex/agents/cs-paper-reviewer.toml"
        path.write_text(
            path.read_text(encoding="utf-8") + "\ninvalid = [\n",
            encoding="utf-8",
        )
        self.assertProfileError("invalid custom agent TOML")


if __name__ == "__main__":
    unittest.main()
