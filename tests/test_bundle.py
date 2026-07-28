from __future__ import annotations

import pathlib
import re
import shutil
import tempfile
import unittest

from scripts.review_skill_validation import (
    REQUIRED_TREE,
    active_text_files,
    validate_adapter_profile,
    validate_bundle,
    validate_json_files,
    validate_no_count_based_rigor,
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
)


class BundleContractTests(unittest.TestCase):
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
        self.assertFalse(any(path.startswith("docs/") for path in relatives))
        self.assertFalse(any(path.startswith("sources/") for path in relatives))
        self.assertFalse(any(path.startswith("tests/") for path in relatives))

    def test_bundle_aggregate_is_clean(self) -> None:
        self.assertEqual([], validate_bundle(ROOT))


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
                    "reference-boundary: SKILL.md references missing file: "
                    "references/missing.md"
                ],
                validate_reference_boundaries(root),
            )

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


if __name__ == "__main__":
    unittest.main()
