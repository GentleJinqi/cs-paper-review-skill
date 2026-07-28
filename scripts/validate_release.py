"""Validate release identity, package bytes, privacy, and manifest."""

from __future__ import annotations

import json
import pathlib
import sys

try:
    from scripts.release_manifest import validate_release_manifest
except ModuleNotFoundError:
    from release_manifest import validate_release_manifest


FORBIDDEN_PRIVATE_TEXT = (
    "/home/jinqiwang",
    "work1-paper",
    "paper-revision-skeleton",
    "review-run-2026",
    "main_edited",
    "Foreground Entity",
    "FE Manifold",
    "BEGIN PRIVATE",
    "API_KEY",
)
TEXT_SUFFIXES = {
    ".json",
    ".md",
    ".py",
    ".tex",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
}
POLICY_DEFINITION_PATHS = {
    "scripts/review_skill_validation.py",
    "scripts/validate_release.py",
}


def _load_json(path: pathlib.Path, label: str) -> tuple[dict | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"release: {label}: {exc}"]
    if not isinstance(value, dict):
        return None, [f"release: {label} must be an object"]
    return value, []


def validate_release(root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root).resolve()
    errors: list[str] = []
    decision, decision_errors = _load_json(
        root / "release" / "version-decision.json",
        "version decision",
    )
    manifest, manifest_errors = _load_json(
        root / "release" / "manifest.json",
        "manifest",
    )
    errors.extend(decision_errors)
    errors.extend(manifest_errors)
    if isinstance(manifest, dict):
        errors.extend(validate_release_manifest(manifest, root))
    if isinstance(decision, dict):
        required = {
            "schema_version",
            "observed_remote_main",
            "observed_tags_and_releases",
            "previous_released_version_or_none",
            "change_class",
            "selected_version",
            "selected_tag",
            "rationale",
            "decided_at",
        }
        if set(decision) != required:
            errors.append("release: version decision fields differ")
        version = decision.get("selected_version")
        tag = decision.get("selected_tag")
        if tag != f"v{version}":
            errors.append("release: selected tag/version mismatch")
        try:
            version_file = (root / "VERSION").read_text(
                encoding="utf-8"
            ).strip()
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"release: identity file unavailable: {exc}")
        else:
            if version_file != version:
                errors.append("release: VERSION differs from version decision")
            if f"## {version} " not in changelog:
                errors.append("release: CHANGELOG lacks selected version")
        if isinstance(manifest, dict) and (
            manifest.get("release_version") != version
            or manifest.get("selected_tag") != tag
        ):
            errors.append("release: manifest identity mismatch")

    for relative in (
        "LICENSE",
        "MIGRATION.md",
        "SOURCES.md",
        "THIRD_PARTY_NOTICES.md",
        "release/release-gates.md",
    ):
        path = root / relative
        if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
            errors.append(f"release: missing or unsafe release file: {relative}")

    if isinstance(manifest, dict):
        for item in manifest.get("files", []):
            if not isinstance(item, dict):
                continue
            relative = item.get("path")
            if (
                not isinstance(relative, str)
                or pathlib.Path(relative).suffix.lower() not in TEXT_SUFFIXES
                or relative.startswith("tests/")
                or relative in POLICY_DEFINITION_PATHS
            ):
                continue
            try:
                text = (root / relative).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for token in FORBIDDEN_PRIVATE_TEXT:
                if token in text:
                    errors.append(
                        f"release: private or secret token {token!r} in "
                        f"{relative}"
                    )
    return sorted(set(errors))


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    errors = validate_release(root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("release validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
