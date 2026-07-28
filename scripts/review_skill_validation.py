"""Deterministic, offline validation for the portable paper-review bundle."""

from __future__ import annotations

import json
import pathlib
import re


REQUIRED_TREE = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/scientific-core.md",
    "references/review-coverage.md",
    "references/review-coverage.json",
    "references/review-workflow.md",
    "references/finding-contract.md",
    "references/delta-review.md",
    "references/privacy-and-authorisation.md",
    "adapters/codex-gpt-5.6-sol-ultra.md",
    "adapters/codex/agents/cs-paper-reviewer.toml",
    "adapters/codex/agents/cs-paper-ae.toml",
    "adapters/codex/adapter-manifest.json",
    "adapters/codex/candidates/minimal-settled-set.md",
    "adapters/codex/candidates/persisted-task-registry.md",
    "schemas/run-manifest.schema.json",
    "schemas/finding-ledger.schema.json",
    "schemas/adapter-promotion.schema.json",
    "schemas/adapter-manifest.schema.json",
    "templates/run-manifest.json",
    "templates/finding-ledger.json",
    "templates/reviewer-report.md",
    "templates/ae-assessment.md",
    "templates/review-summary.md",
    "scripts/review_skill_validation.py",
    "scripts/validate_bundle.py",
    "scripts/validate_run.py",
    "tests/test_bundle.py",
    "tests/test_run_contracts.py",
)

_ACTIVE_ROOT_FILES = ("SKILL.md",)
_ACTIVE_DIRECTORIES = (
    "agents",
    "references",
    "adapters",
    "schemas",
    "templates",
    "scripts",
)
_ACTIVE_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".toml", ".py"}


def _normalise_root(root: pathlib.Path) -> pathlib.Path:
    return pathlib.Path(root).resolve()


def active_text_files(root: pathlib.Path) -> list[pathlib.Path]:
    """Return active bundle text files, excluding history, sources, and tests."""

    root = _normalise_root(root)
    paths: list[pathlib.Path] = []
    for name in _ACTIVE_ROOT_FILES:
        candidate = root / name
        if candidate.is_file() and not candidate.is_symlink():
            paths.append(candidate)
    for directory in _ACTIVE_DIRECTORIES:
        base = root / directory
        if not base.is_dir() or base.is_symlink():
            continue
        for candidate in base.rglob("*"):
            if (
                candidate.is_file()
                and not candidate.is_symlink()
                and candidate.suffix.lower() in _ACTIVE_SUFFIXES
                and "__pycache__" not in candidate.parts
            ):
                paths.append(candidate)
    return sorted(set(paths), key=lambda path: path.relative_to(root).as_posix())


def validate_required_tree(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    for relative in REQUIRED_TREE:
        path = root / relative
        if not path.is_file():
            errors.append(f"required-tree: missing regular file: {relative}")
        elif path.is_symlink():
            errors.append(f"required-tree: symlink is not allowed: {relative}")
    return errors


def validate_skill_frontmatter(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    path = root / "SKILL.md"
    if not path.is_file():
        return ["skill-frontmatter: missing SKILL.md"]
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"(?ms)^---\n(.*?)^---\n", text))
    if len(matches) != 1 or matches[0].start() != 0:
        return ["skill-frontmatter: SKILL.md must have exactly one leading YAML block"]
    block = matches[0].group(1)
    description_match = re.search(r"(?m)^description:\s*(.+?)\s*$", block)
    if not description_match:
        return ["skill-frontmatter: description is required"]
    description = description_match.group(1).strip().strip("\"'")
    errors: list[str] = []
    if not 30 <= len(description) <= 320:
        errors.append("skill-frontmatter: description must be specific and concise")
    if not re.search(r"\b(CS|ML|CV|NLP|computer|machine)\b", description, re.I):
        errors.append("skill-frontmatter: description must identify the paper domain")
    if not re.search(r"author|pre-submission|delta|re-review", description, re.I):
        errors.append("skill-frontmatter: description must identify the author-side review trigger")
    return errors


def validate_reference_boundaries(root: pathlib.Path) -> list[str]:
    """Reject missing repository-relative paths referenced by active Markdown."""

    root = _normalise_root(root)
    errors: list[str] = []
    path_pattern = re.compile(
        r"`((?:references|templates|schemas|adapters|scripts)/[^`\s]+)"
        r"|(?<!\()(?<![\w/])((?:references|templates|schemas|adapters|scripts)/"
        r"[A-Za-z0-9_./-]+\.(?:md|json|yaml|yml|toml|py))"
    )
    for path in active_text_files(root):
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        for match in path_pattern.finditer(text):
            raw = match.group(1) or match.group(2)
            relative = raw.rstrip(".,;:)")
            target = root / relative
            if not target.is_file():
                source = path.relative_to(root).as_posix()
                errors.append(
                    f"reference-boundary: {source} references missing file: {relative}"
                )
    return sorted(set(errors))


def validate_no_count_based_rigor(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    patterns = (
        re.compile(r"\b(?:strict|standard)\s+(?:tier|mode)\b", re.I),
        re.compile(r"\b(?:default|fixed|required|minimum|maximum)\s+"
                   r"(?:number|count|roster|reviewers?|agents?|tasks?|threads?)\b", re.I),
        re.compile(r"\b\d+\s*(?:-|–|—|to)\s*\d+\s+"
                   r"(?:reviewers?|agents?|tasks?|threads?)\b", re.I),
        re.compile(r"\bmax_threads\s*=", re.I),
        re.compile(r"\bdefault\s+venue\b", re.I),
        re.compile(r"\bdefault\s+(?:task|reviewer|agent|thread)\s+count\b", re.I),
    )
    for path in active_text_files(root):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if any(pattern.search(line) for pattern in patterns):
                relative = path.relative_to(root).as_posix()
                errors.append(
                    f"count-based-rigor: forbidden active guidance at "
                    f"{relative}:{line_number}"
                )
    return errors


def validate_adapter_profile(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    path = root / "adapters/codex-gpt-5.6-sol-ultra.md"
    if not path.is_file():
        return ["adapter-profile: missing adapters/codex-gpt-5.6-sol-ultra.md"]
    lowered = path.read_text(encoding="utf-8").lower()
    requirements = {
        "gpt-5.6-sol": "configured Sol model",
        "ultra": "configured product mode",
        "root": "single delegation owner",
        "leaf-only": "child topology",
        "no silent fallback": "fallback prohibition",
        "effective_telemetry": "telemetry disclosure",
        "not_surfaced": "absent-telemetry state",
    }
    return [
        f"adapter-profile: missing {meaning}: {token}"
        for token, meaning in requirements.items()
        if token not in lowered
    ]


def validate_json_files(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    for path in active_text_files(root):
        if path.suffix.lower() != ".json":
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            relative = path.relative_to(root).as_posix()
            errors.append(f"json: invalid {relative}: {exc}")
    return errors


def validate_bundle(root: pathlib.Path) -> list[str]:
    validators = (
        validate_required_tree,
        validate_skill_frontmatter,
        validate_reference_boundaries,
        validate_no_count_based_rigor,
        validate_adapter_profile,
        validate_json_files,
    )
    errors: list[str] = []
    for validator in validators:
        errors.extend(validator(root))
    return sorted(set(errors))

