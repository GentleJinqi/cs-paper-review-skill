from __future__ import annotations

import copy
import json
import pathlib
import unittest

from scripts.release_manifest import (
    build_release_manifest,
    validate_release_manifest,
)
from scripts.validate_release import validate_release


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_release_identity_is_single_and_consistent(self) -> None:
        decision = json.loads(
            (ROOT / "release" / "version-decision.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            f"v{decision['selected_version']}",
            decision["selected_tag"],
        )
        self.assertEqual(
            decision["selected_version"],
            (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        )

    def test_canonical_release_manifest_validates(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], validate_release_manifest(manifest, ROOT))
        self.assertEqual([], validate_release(ROOT))

    def test_generator_is_deterministic_for_current_tree(self) -> None:
        expected = json.loads(
            (ROOT / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(expected, build_release_manifest(ROOT))

    def test_missing_extra_or_changed_file_is_rejected(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        changed = copy.deepcopy(manifest)
        changed["files"][0]["sha256"] = "0" * 64
        self.assertTrue(validate_release_manifest(changed, ROOT))
        missing = copy.deepcopy(manifest)
        missing["files"] = missing["files"][1:]
        self.assertTrue(validate_release_manifest(missing, ROOT))

    def test_manifest_self_exclusion_is_the_only_exclusion(self) -> None:
        manifest = json.loads(
            (ROOT / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            ["release/manifest.json"],
            manifest["self_excluded_paths"],
        )
        self.assertFalse(
            any(
                item["classification"] == "excluded"
                for item in manifest["files"]
            )
        )


if __name__ == "__main__":
    unittest.main()
