"""Generate and validate the self-excluding portable release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
from typing import Any


SELF_EXCLUDED = ("release/manifest.json",)
SOURCE_EXCERPT_PREFIXES = (
    "venues/source-captures/",
    "venues/source-evidence/",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _tracked_files(root: pathlib.Path) -> list[str]:
    process = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return sorted(
        item.decode("utf-8")
        for item in process.stdout.split(b"\0")
        if item
    )


def _classification(path: str) -> tuple[str, str, str]:
    if path.startswith(SOURCE_EXCERPT_PREFIXES):
        return (
            "bounded-first-party-source-excerpt",
            "excluded-from-project-license",
            "THIRD_PARTY_NOTICES.md",
        )
    return ("project-authored", "project-authored-MIT", "LICENSE")


def _file_rows(root: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    for relative in _tracked_files(root):
        if relative in SELF_EXCLUDED:
            continue
        path = root / relative
        classification, licence_route, notice = _classification(relative)
        rows.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "size": path.stat().st_size,
                "classification": classification,
                "licence_route": licence_route,
                "source_or_notice": notice,
            }
        )
    return rows


def build_release_manifest(root: pathlib.Path) -> dict:
    root = pathlib.Path(root).resolve()
    decision = json.loads(
        (root / "release" / "version-decision.json").read_text(
            encoding="utf-8"
        )
    )
    rows = _file_rows(root)
    return {
        "schema_version": "1.0.0",
        "release_version": decision["selected_version"],
        "selected_tag": decision["selected_tag"],
        "self_excluded_paths": list(SELF_EXCLUDED),
        "taggable_tree_sha256": hashlib.sha256(
            _canonical_bytes(rows)
        ).hexdigest(),
        "files": rows,
    }


def validate_release_manifest(value: dict, root: pathlib.Path) -> list[str]:
    root = pathlib.Path(root).resolve()
    errors: list[str] = []
    required = {
        "schema_version",
        "release_version",
        "selected_tag",
        "self_excluded_paths",
        "taggable_tree_sha256",
        "files",
    }
    if not isinstance(value, dict) or set(value) != required:
        return ["release-manifest: top-level fields differ from the contract"]
    if value.get("schema_version") != "1.0.0":
        errors.append("release-manifest: schema version mismatch")
    if value.get("self_excluded_paths") != list(SELF_EXCLUDED):
        errors.append(
            "release-manifest: release/manifest.json is the sole permitted "
            "self-exclusion"
        )
    try:
        expected = build_release_manifest(root)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        subprocess.CalledProcessError,
    ) as exc:
        return [f"release-manifest: cannot reconstruct tree: {exc}"]
    expected_paths = [item["path"] for item in expected["files"]]
    rows = value.get("files")
    if not isinstance(rows, list):
        return ["release-manifest: files must be an array"]
    actual_paths = [
        item.get("path") for item in rows if isinstance(item, dict)
    ]
    if actual_paths != expected_paths:
        errors.append(
            "release-manifest: missing, extra, or out-of-order taggable path"
        )
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            errors.append("release-manifest: file row must be an object")
            continue
        path_value = item.get("path")
        if not isinstance(path_value, str) or path_value in seen:
            errors.append("release-manifest: paths must be unique strings")
            continue
        seen.add(path_value)
        if (
            path_value.startswith(("/", "\\"))
            or "\\" in path_value
            or ".." in pathlib.PurePosixPath(path_value).parts
        ):
            errors.append(f"release-manifest: unsafe path: {path_value}")
            continue
        path = root / path_value
        if not path.is_file() or path.is_symlink():
            errors.append(
                f"release-manifest: path is missing, non-file, or symlink: "
                f"{path_value}"
            )
            continue
        expected_row = next(
            (
                candidate
                for candidate in expected["files"]
                if candidate["path"] == path_value
            ),
            None,
        )
        if expected_row != item:
            errors.append(
                f"release-manifest: metadata or SHA-256 mismatch: {path_value}"
            )
        if item.get("classification") == "excluded":
            errors.append(
                f"release-manifest: tracked path cannot be classified "
                f"excluded: {path_value}"
            )
        if not SHA256_RE.fullmatch(str(item.get("sha256", ""))):
            errors.append(f"release-manifest: invalid SHA-256: {path_value}")
    for field in (
        "release_version",
        "selected_tag",
        "taggable_tree_sha256",
    ):
        if value.get(field) != expected.get(field):
            errors.append(f"release-manifest: {field} mismatch")
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    root = pathlib.Path(args.root).resolve()
    manifest = build_release_manifest(root)
    rendered = _canonical_bytes(manifest)
    if args.write:
        path = root / "release" / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered)
    else:
        print(rendered.decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
