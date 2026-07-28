from __future__ import annotations

import copy
import json
import pathlib
import unittest

from scripts.review_skill_validation import validate_venue_corpus_bundle


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return json.loads(
        (
            ROOT / "venue-intelligence" / "examples" / name
        ).read_text(encoding="utf-8")
    )


class VenueCorpusContractTests(unittest.TestCase):
    def test_published_examples_validate(self) -> None:
        self.assertEqual([], validate_venue_corpus_bundle(ROOT))

    def test_low_grade_status_evidence_is_discovery_only(self) -> None:
        record = load_example("topic-near-synthetic.json")
        record["items"][0]["evidence_grade"] = "D"
        record["items"][0]["eligible_for_material_inference"] = True
        errors = validate_venue_corpus_bundle(
            ROOT, documents=[("fixture.json", record)]
        )
        self.assertTrue(
            any("grade D" in error and "discovery" in error for error in errors)
        )

    def test_saturation_requires_zero_latest_marginal_coverage(self) -> None:
        record = load_example("accepted-synthetic.json")
        record["saturation"]["status"] = "saturated"
        record["saturation"]["latest_batch"]["marginal_additions"][
            "mechanism_family"
        ] = 1
        errors = validate_venue_corpus_bundle(
            ROOT, documents=[("fixture.json", record)]
        )
        self.assertTrue(
            any("saturated" in error and "marginal" in error for error in errors)
        )

    def test_topic_near_records_cover_all_similarity_axes(self) -> None:
        record = load_example("topic-near-synthetic.json")
        del record["items"][0]["topic_signature"]["claim_types"]
        errors = validate_venue_corpus_bundle(
            ROOT, documents=[("fixture.json", record)]
        )
        self.assertTrue(any("claim_types" in error for error in errors))

    def test_corpus_contains_metadata_not_manuscript_bytes(self) -> None:
        record = copy.deepcopy(load_example("accepted-synthetic.json"))
        record["rights_boundary"]["manuscript_bytes_stored"] = True
        errors = validate_venue_corpus_bundle(
            ROOT, documents=[("fixture.json", record)]
        )
        self.assertTrue(any("manuscript bytes" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
