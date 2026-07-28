"""Deterministic, offline validation for the portable paper-review bundle."""

from __future__ import annotations

import json
import pathlib
import re
import hashlib
import unicodedata
from typing import Any


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
_MODEL_INDEPENDENT_CORE = (
    "references/scientific-core.md",
    "references/review-coverage.md",
    "references/review-coverage.json",
    "references/review-workflow.md",
    "references/finding-contract.md",
    "references/delta-review.md",
    "references/privacy-and-authorisation.md",
)
_CANONICAL_CRITERIA = (
    "RC-AUTHORISATION",
    "RC-INPUT-LINEAGE",
    "RC-INPUT-ALIGNMENT",
    "RC-INPUT-VERIFIABILITY",
    "RC-CRITERIA-AUTHORITY",
    "RC-COVERAGE-ACCOUNTING",
    "RC-DELTA-LINEAGE",
    "RC-PROBLEM-FORMULATION",
    "RC-CONTRIBUTION-IDENTITY",
    "RC-CLAIM-EVIDENCE",
    "RC-RELATED-WORK",
    "RC-FORMAL-CORRECTNESS",
    "RC-METHOD-SOUNDNESS",
    "RC-DATA-VALIDITY",
    "RC-MEASUREMENT-VALIDITY",
    "RC-EXPERIMENT-DESIGN",
    "RC-STATISTICAL-VALIDITY",
    "RC-COMPARISON-FAIRNESS",
    "RC-ROBUSTNESS-SCOPE",
    "RC-REPRODUCIBILITY",
    "RC-RESOURCE-CLAIMS",
    "RC-WRITING-CLARITY",
    "RC-VISUAL-INTEGRITY",
    "RC-LIMITATIONS",
    "RC-RESPONSIBLE-RESEARCH",
    "RC-CITATION-SUPPORT",
    "RC-FINDING-EVIDENCE",
    "RC-CONFLICT-VERIFICATION",
    "RC-DEDUP-DISPOSITION",
    "RC-DISSENT-PRESERVATION",
    "RC-REQUIREMENT-LEGITIMACY",
    "RC-RISK-CLASS-SEPARATION",
    "RC-COMPLETION-TRUTH",
    "RC-LEDGER-CONSISTENCY",
)


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
    patterns = (
        re.compile(
            r"`((?:references|templates|schemas|adapters|scripts)/[^`\s]+)`"
        ),
        re.compile(
            r"\]\(((?:references|templates|schemas|adapters|scripts)/"
            r"[^)\s#]+)(?:#[^)]+)?\)"
        ),
        re.compile(
            r"(?<![\w/(])((?:references|templates|schemas|adapters|scripts)/"
            r"[A-Za-z0-9_./-]+\.(?:md|json|yaml|yml|toml|py))"
        ),
    )
    for path in active_text_files(root):
        if path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8")
        candidates: set[str] = set()
        for pattern in patterns:
            candidates.update(match.group(1) for match in pattern.finditer(text))
        for raw in sorted(candidates):
            relative = raw.rstrip(".,;:)")
            source = path.relative_to(root).as_posix()
            try:
                _safe_bundle_file(root, relative)
            except ValueError as exc:
                errors.append(
                    f"reference-boundary: {source} has invalid reference "
                    f"{relative}: {exc}"
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
        re.compile(
            r"\b(?:always|must|required|requiredly)\b.{0,50}\b\d+\s+"
            r"(?:reviewers?|agents?|tasks?|threads?)\b",
            re.I,
        ),
    )
    for path in active_text_files(root):
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if re.search(
                r"\b(?:no|not|never|without)\b.{0,35}\b"
                r"(?:fixed|default|required|minimum|maximum)\b.{0,25}\b"
                r"(?:count|roster|reviewers?|agents?|tasks?|threads?)\b",
                line,
                re.I,
            ):
                continue
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
    errors = [
        f"adapter-profile: missing {meaning}: {token}"
        for token, meaning in requirements.items()
        if token not in lowered
    ]
    normalised = " ".join(lowered.split())
    if not re.search(r"codex\s+`?max`?\s+is\s+not\s+equivalent\s+to\s+ultra", normalised):
        errors.append("adapter-profile: Codex max must be explicitly non-equivalent")
    if re.search(
        r"(?:not_surfaced|absent telemetry).{0,60}(?:proves|establishes|supports)"
        r".{0,30}runtime attestation",
        normalised,
    ):
        errors.append(
            "adapter-profile: absent telemetry cannot support runtime attestation"
        )
    if "neither is an active default" not in normalised:
        errors.append("adapter-profile: inactive lifecycle candidates are ambiguous")

    for relative in (
        "adapters/codex/agents/cs-paper-reviewer.toml",
        "adapters/codex/agents/cs-paper-ae.toml",
    ):
        agent_path = root / relative
        if not agent_path.is_file():
            errors.append(f"adapter-profile: missing custom agent example: {relative}")
            continue
        text = agent_path.read_text(encoding="utf-8")
        assignments = {
            key: value
            for key, value in re.findall(
                r'(?m)^(model|model_reasoning_effort|sandbox_mode)\s*=\s*"([^"]+)"\s*$',
                text,
            )
        }
        if assignments.get("model") != "gpt-5.6-sol":
            errors.append(f"adapter-profile: {relative} model must be gpt-5.6-sol")
        if assignments.get("model_reasoning_effort") != "ultra":
            errors.append(f"adapter-profile: {relative} effort must be ultra")
        if assignments.get("sandbox_mode") != "read-only":
            errors.append(f"adapter-profile: {relative} sandbox must be read-only")
        if not re.search(r"\bdo not\b.{0,220}\bdelegate any work\b", text, re.I | re.S):
            errors.append(f"adapter-profile: {relative} must prohibit delegation")
    return sorted(set(errors))


def validate_json_files(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    for path in active_text_files(root):
        if path.suffix.lower() != ".json":
            continue
        try:
            def no_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict:
                result: dict = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f"duplicate object key {key!r}")
                    result[key] = value
                return result

            json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=no_duplicate_pairs,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            relative = path.relative_to(root).as_posix()
            errors.append(f"json: invalid {relative}: {exc}")
    return errors


def _validate_core_boundaries(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    forbidden = (
        "gpt-",
        "ultra",
        "codex",
        "subagent",
        "work1-paper",
    )
    for relative in _MODEL_INDEPENDENT_CORE:
        path = root / relative
        if not path.is_file():
            continue
        lowered = path.read_text(encoding="utf-8").lower()
        for token in forbidden:
            if token in lowered:
                errors.append(
                    f"core-boundary: runtime or project token {token!r} in {relative}"
                )
        if re.search(r"\bdefault\s+(?:publication\s+)?(?:venue|target)\b", lowered):
            errors.append(f"core-boundary: fixed target default in {relative}")
        if re.search(
            r"\b(?:fixed|required|minimum|maximum)\s+(?:reviewer|agent|task|role)"
            r"(?:s|\s+count)?\b",
            lowered,
        ):
            errors.append(f"core-boundary: fixed execution topology in {relative}")
    return errors


def _validate_coverage_bundle(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    try:
        matrix = load_review_coverage(root)
    except ValueError as exc:
        return [f"coverage-bundle: {exc}"]
    ids = tuple(_coverage_ids(matrix))
    errors: list[str] = []
    if ids != _CANONICAL_CRITERIA:
        errors.append(
            "coverage-bundle: canonical criterion IDs or order changed without "
            "a contract migration"
        )
    markdown_path = root / "references/review-coverage.md"
    if not markdown_path.is_file():
        errors.append("coverage-bundle: missing Markdown companion")
    else:
        text = markdown_path.read_text(encoding="utf-8")
        markdown_ids = re.findall(r"`(RC-[A-Z0-9-]+)`", text)
        unique_markdown_ids = tuple(dict.fromkeys(markdown_ids))
        if unique_markdown_ids != _CANONICAL_CRITERIA:
            errors.append(
                "coverage-bundle: Markdown criterion IDs differ from canonical JSON"
            )
        if len(markdown_ids) != len(set(markdown_ids)):
            errors.append(
                "coverage-bundle: Markdown repeats a canonical criterion definition"
            )
    return errors


def validate_bundle(root: pathlib.Path) -> list[str]:
    validators = (
        validate_required_tree,
        validate_skill_frontmatter,
        validate_reference_boundaries,
        validate_no_count_based_rigor,
        validate_adapter_profile,
        validate_json_files,
        _validate_core_boundaries,
        _validate_coverage_bundle,
    )
    errors: list[str] = []
    for validator in validators:
        errors.extend(validator(root))
    return sorted(set(errors))


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CANDIDATE_MAPPING = {
    "minimal-settled-set":
        "adapters/codex/candidates/minimal-settled-set.md",
    "persisted-task-registry":
        "adapters/codex/candidates/persisted-task-registry.md",
}
_ACTIVE_ADAPTER_BASE = {
    "adapters/codex-gpt-5.6-sol-ultra.md",
    "adapters/codex/agents/cs-paper-reviewer.toml",
    "adapters/codex/agents/cs-paper-ae.toml",
}
_ALLOWED_ADJUDICATION = {
    "candidate",
    "retained",
    "merged",
    "downgraded",
    "rejected",
    "unresolved",
}
_ALLOWED_DELTA = {
    "not_applicable",
    "resolved",
    "partially_resolved",
    "still_open",
    "new",
    "made_worse",
}
_ALLOWED_IMPACT_CHANGE = {
    "not_applicable",
    "unchanged",
    "upgraded",
    "downgraded",
}
_ALLOWED_EVIDENCE_STATE = {"verified", "needs_verification", "blocked"}
_ALLOWED_DECISION_IMPACT = {
    "fundamental",
    "material",
    "limited",
    "advisory",
    "none",
}
_ALLOWED_CONFIDENCE = {"high", "medium", "low"}
_ALLOWED_ACTION_TYPE = {
    "author-judgement",
    "author-data",
    "experiment-required",
    "citation-required",
    "prose-repair",
    "method-clarification",
    "analysis-repair",
    "figure-layout-repair",
    "submission-packaging",
    "no-action",
}
_ALLOWED_COMPLETION = {"complete", "partial", "blocked"}
_ALLOWED_COVERAGE_DISPOSITION = {
    "assessed_no_finding",
    "finding_linked",
    "not_applicable",
    "needs_verification",
    "blocked",
}
_SUBSTANTIVE_OPERATIONS = {
    "add_finding",
    "verify_finding",
    "remove_finding",
    "adjudicate_finding",
    "rank_finding",
    "synthesise_findings",
    "alter_completion",
}


def _canonical_json_bytes(data: Any) -> bytes:
    return (
        json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _json_sha256(data: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(data)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _safe_bundle_file(root: pathlib.Path, locator: str) -> pathlib.Path:
    root = _normalise_root(root)
    if not isinstance(locator, str) or not locator:
        raise ValueError("locator must be a non-empty bundle-relative path")
    pure = pathlib.PurePosixPath(locator)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ValueError("locator must be traversal-free and canonical")
    if pure.as_posix() != locator or "\\" in locator:
        raise ValueError("locator must use canonical POSIX form")
    path = root.joinpath(*pure.parts)
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("locator escapes bundle root") from exc
    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise ValueError("locator may not traverse a symlink")
    if not path.is_file():
        raise ValueError("locator does not resolve to a regular file")
    return path


def _is_canonical_relative_locator(locator: Any) -> bool:
    if not isinstance(locator, str) or not locator or "\\" in locator:
        return False
    pure = pathlib.PurePosixPath(locator)
    return (
        not pure.is_absolute()
        and "." not in pure.parts
        and ".." not in pure.parts
        and pure.as_posix() == locator
    )


def _load_json_object(path: pathlib.Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unparsable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def load_adapter_manifest(root: pathlib.Path) -> dict:
    path = _safe_bundle_file(root, "adapters/codex/adapter-manifest.json")
    return _load_json_object(path, "adapter manifest")


def adapter_payload_sha256(root: pathlib.Path) -> str:
    root = _normalise_root(root)
    manifest = load_adapter_manifest(root)
    active = manifest.get("active_files")
    if not isinstance(active, list) or not all(
        isinstance(item, str) for item in active
    ):
        raise ValueError("adapter manifest active_files must be a string list")
    lines: list[str] = []
    for locator in sorted(active):
        if locator == "adapters/codex/adapter-manifest.json":
            raise ValueError("adapter manifest cannot hash itself")
        path = _safe_bundle_file(root, locator)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {locator}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def validate_adapter_manifest(data: dict, bundle_root: pathlib.Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["adapter-manifest: must be an object"]
    if data.get("schema_version") != "1.0.0":
        errors.append("adapter-manifest: schema_version must be 1.0.0")
    mapping = data.get("candidate_implementations")
    if mapping != _CANDIDATE_MAPPING:
        errors.append("adapter-manifest: candidate mapping is not canonical")
    selected = data.get("selected_candidate_id")
    selected_path = data.get("selected_lifecycle_implementation")
    promotion_locator = data.get("promotion_record_locator")
    active = data.get("active_files")
    if not isinstance(active, list) or not all(
        isinstance(item, str) for item in active
    ):
        errors.append("adapter-manifest: active_files must be a string list")
        active = []
    if len(active) != len(set(active)):
        errors.append("adapter-manifest: active_files contains duplicates")
    if not _ACTIVE_ADAPTER_BASE.issubset(set(active)):
        errors.append("adapter-manifest: active adapter/config allowlist is incomplete")

    if selected is None:
        if selected_path is not None or promotion_locator is not None:
            errors.append(
                "adapter-manifest: null candidate requires null implementation "
                "and promotion locator"
            )
        for candidate_path in _CANDIDATE_MAPPING.values():
            if candidate_path in active:
                errors.append(
                    "adapter-manifest: inactive candidate appears in active allowlist"
                )
    elif selected not in _CANDIDATE_MAPPING:
        errors.append("adapter-manifest: selected candidate ID is unknown")
    else:
        expected_path = _CANDIDATE_MAPPING[selected]
        if selected_path != expected_path:
            errors.append(
                "adapter-manifest: selected implementation does not match "
                "candidate mapping"
            )
        if active.count(expected_path) != 1:
            errors.append(
                "adapter-manifest: selected implementation must occur exactly "
                "once in active allowlist"
            )
        other_paths = set(_CANDIDATE_MAPPING.values()) - {expected_path}
        if any(path in active for path in other_paths):
            errors.append(
                "adapter-manifest: unselected lifecycle implementation is active"
            )
        if not isinstance(promotion_locator, str) or not promotion_locator:
            errors.append(
                "adapter-manifest: selected candidate requires promotion locator"
            )

    root = _normalise_root(bundle_root)
    for locator in active:
        try:
            _safe_bundle_file(root, locator)
        except ValueError as exc:
            errors.append(f"adapter-manifest: invalid active file {locator!r}: {exc}")
    recorded_digest = data.get("adapter_payload_sha256")
    if not _is_sha256(recorded_digest):
        errors.append("adapter-manifest: adapter_payload_sha256 must be SHA-256")
    else:
        try:
            actual = adapter_payload_sha256(root)
        except ValueError as exc:
            errors.append(f"adapter-manifest: cannot hash active payload: {exc}")
        else:
            if actual != recorded_digest:
                errors.append(
                    "adapter-manifest: adapter_payload_sha256 does not match "
                    "actual active payload"
                )
    return sorted(set(errors))


def validate_adapter_promotion(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["adapter-promotion: must be an object"]
    required = {
        "schema_version",
        "record_id",
        "evaluated_at",
        "candidate_id",
        "adapter_sha256",
        "result",
        "promotion_decision",
        "evaluation_summary",
    }
    missing = sorted(required - set(data))
    errors.extend(
        f"adapter-promotion: missing required field: {field}" for field in missing
    )
    if data.get("schema_version") != "1.0.0":
        errors.append("adapter-promotion: schema_version must be 1.0.0")
    if data.get("candidate_id") not in _CANDIDATE_MAPPING:
        errors.append("adapter-promotion: candidate_id is unknown")
    if not _is_sha256(data.get("adapter_sha256")):
        errors.append("adapter-promotion: adapter_sha256 must be SHA-256")
    if data.get("result") not in {"pass", "fail"}:
        errors.append("adapter-promotion: result must be pass or fail")
    if data.get("promotion_decision") not in {
        "selected",
        "not_selected",
        "rejected",
    }:
        errors.append("adapter-promotion: promotion_decision is invalid")
    if not isinstance(data.get("evaluation_summary"), dict):
        errors.append("adapter-promotion: evaluation_summary must be an object")
    return sorted(set(errors))


def load_adapter_promotion(
    root: pathlib.Path, locator: str
) -> tuple[dict, bytes]:
    path = _safe_bundle_file(root, locator)
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"promotion record is unparsable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("promotion record must be a JSON object")
    errors = validate_adapter_promotion(value)
    if errors:
        raise ValueError("; ".join(errors))
    if raw != _canonical_json_bytes(value):
        raise ValueError("promotion record bytes are not canonical JSON")
    return value, raw


def load_review_coverage(root: pathlib.Path) -> dict:
    path = _safe_bundle_file(root, "references/review-coverage.json")
    data = _load_json_object(path, "review coverage")
    criteria = data.get("criteria")
    if data.get("schema_version") != "1.0.0":
        raise ValueError("review coverage schema_version must be 1.0.0")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("review coverage criteria must be a non-empty list")
    ids: list[str] = []
    required = {
        "criterion_id",
        "review_question",
        "required_evidence",
        "primary_stage_owner",
        "conditional_specialist_trigger",
        "applicability_states",
        "required_when_inapplicable",
        "required_when_uncertain",
    }
    for index, row in enumerate(criteria):
        if not isinstance(row, dict):
            raise ValueError(f"review coverage criterion {index} must be an object")
        missing = required - set(row)
        if missing:
            raise ValueError(
                f"review coverage criterion {index} missing: "
                f"{', '.join(sorted(missing))}"
            )
        criterion_id = row.get("criterion_id")
        if not isinstance(criterion_id, str) or not criterion_id:
            raise ValueError(f"review coverage criterion {index} has invalid ID")
        ids.append(criterion_id)
        if row.get("applicability_states") != [
            "applicable",
            "inapplicable",
            "uncertain",
        ]:
            raise ValueError(
                f"review coverage criterion {criterion_id} has invalid "
                "applicability states"
            )
        if not row.get("primary_stage_owner"):
            raise ValueError(
                f"review coverage criterion {criterion_id} has no primary owner"
            )
    if len(ids) != len(set(ids)):
        raise ValueError("review coverage contains duplicate criterion IDs")
    return data


def _normalised_claim(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def stable_finding_id(finding: dict) -> str:
    evidence = finding.get("evidence")
    provenance = finding.get("provenance")
    evidence = evidence if isinstance(evidence, dict) else {}
    provenance = provenance if isinstance(provenance, dict) else {}
    identity = {
        "criterion": finding.get("criterion", ""),
        "claim": _normalised_claim(finding.get("claim")),
        "primary_artifact_lineage_id":
            provenance.get("primary_artifact_lineage_id", ""),
        "semantic_anchor": evidence.get("semantic_anchor", ""),
    }
    digest = hashlib.sha256(_canonical_json_bytes(identity)).hexdigest()
    return f"F-{digest[:16]}"


def _validate_evidence(
    evidence: Any, prefix: str, *, material: bool
) -> list[str]:
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return [f"{prefix}: evidence must be an object"]
    for field in ("artifact_id", "source_anchor", "semantic_anchor", "observation"):
        if material and not (
            isinstance(evidence.get(field), str) and evidence.get(field).strip()
        ):
            label = field.replace("_", " ")
            errors.append(f"{prefix}: material finding requires {label}")
    return errors


def validate_finding_ledger(data: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["finding-ledger: must be an object"]
    required_top = {
        "schema_version",
        "run_id",
        "review_kind",
        "completion",
        "findings",
    }
    for field in sorted(required_top - set(data)):
        errors.append(f"finding-ledger: missing required field: {field}")
    kind = data.get("review_kind")
    if kind not in {"initial", "delta"}:
        errors.append("finding-ledger: review_kind must be initial or delta")
    completion = data.get("completion")
    if completion not in _ALLOWED_COMPLETION:
        errors.append("finding-ledger: completion is invalid")
    findings = data.get("findings")
    if not isinstance(findings, list):
        return sorted(set(errors + ["finding-ledger: findings must be a list"]))
    seen: set[str] = set()
    required_finding = {
        "finding_id",
        "review_kind",
        "prior_finding_id",
        "adjudication_status",
        "adjudication_rationale",
        "delta_status",
        "impact_change",
        "evidence_state",
        "criterion",
        "related_criteria",
        "decision_impact",
        "confidence",
        "claim",
        "evidence",
        "why_it_matters",
        "action_type",
        "closure_requirement",
        "dissent",
        "provenance",
    }
    for index, finding in enumerate(findings):
        prefix = f"finding-ledger: finding[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for field in sorted(required_finding - set(finding)):
            errors.append(f"{prefix} missing required field: {field}")
        finding_id = finding.get("finding_id")
        if not isinstance(finding_id, str) or not finding_id:
            errors.append(f"{prefix}: finding_id must be non-empty")
        elif finding_id in seen:
            errors.append(f"{prefix}: duplicate finding_id: {finding_id}")
        else:
            seen.add(finding_id)
        if finding.get("review_kind") != kind:
            errors.append(f"{prefix}: review_kind does not match ledger")
        adjudication = finding.get("adjudication_status")
        if adjudication not in _ALLOWED_ADJUDICATION:
            errors.append(f"{prefix}: adjudication_status is invalid")
        if not (
            isinstance(finding.get("adjudication_rationale"), str)
            and finding.get("adjudication_rationale").strip()
        ):
            errors.append(f"{prefix}: adjudication_rationale is required")
        if completion == "complete" and adjudication == "candidate":
            errors.append(f"{prefix}: candidate cannot remain in a complete ledger")
        if completion == "complete" and (
            adjudication == "unresolved"
            or finding.get("evidence_state") in {"needs_verification", "blocked"}
        ):
            errors.append(
                f"{prefix}: unresolved evidence prevents complete ledger status"
            )
        delta_status = finding.get("delta_status")
        impact_change = finding.get("impact_change")
        prior_id = finding.get("prior_finding_id")
        if delta_status not in _ALLOWED_DELTA:
            errors.append(f"{prefix}: delta_status is invalid")
        if impact_change not in _ALLOWED_IMPACT_CHANGE:
            errors.append(f"{prefix}: impact_change is invalid")
        if kind == "initial":
            if (
                prior_id is not None
                or delta_status != "not_applicable"
                or impact_change != "not_applicable"
            ):
                errors.append(
                    f"{prefix}: initial finding must use null prior ID and "
                    "not_applicable delta axes"
                )
        elif delta_status == "new":
            if prior_id is not None or impact_change != "not_applicable":
                errors.append(
                    f"{prefix}: new delta finding must have null prior ID and "
                    "not_applicable impact change"
                )
        elif delta_status in {
            "resolved",
            "partially_resolved",
            "still_open",
            "made_worse",
        }:
            if not isinstance(prior_id, str) or not prior_id:
                errors.append(
                    f"{prefix}: carried-forward delta finding requires prior ID"
                )
            if impact_change not in {"unchanged", "upgraded", "downgraded"}:
                errors.append(
                    f"{prefix}: carried-forward delta finding requires explicit "
                    "impact change"
                )
            if finding_id != prior_id:
                errors.append(
                    f"{prefix}: carried-forward delta finding must preserve "
                    "finding_id == prior_finding_id"
                )
        else:
            errors.append(f"{prefix}: delta review has invalid delta axis")

        evidence_state = finding.get("evidence_state")
        if evidence_state not in _ALLOWED_EVIDENCE_STATE:
            errors.append(f"{prefix}: evidence_state is invalid")
        decision_impact = finding.get("decision_impact")
        if decision_impact not in _ALLOWED_DECISION_IMPACT:
            errors.append(f"{prefix}: decision_impact is invalid")
        if finding.get("confidence") not in _ALLOWED_CONFIDENCE:
            errors.append(f"{prefix}: confidence is invalid")
        if finding.get("action_type") not in _ALLOWED_ACTION_TYPE:
            errors.append(f"{prefix}: action_type is invalid")
        material = decision_impact in {"fundamental", "material", "limited"}
        errors.extend(_validate_evidence(finding.get("evidence"), prefix, material=material))
        closure = finding.get("closure_requirement")
        if not isinstance(closure, dict):
            errors.append(f"{prefix}: closure_requirement must be an object")
        else:
            state = closure.get("state")
            if state not in {"open", "closed", "not_applicable"}:
                errors.append(f"{prefix}: closure state is invalid")
            if closure.get("owner") not in {
                "author",
                "reviewer",
                "external",
                "none",
            }:
                errors.append(f"{prefix}: closure owner is invalid")
            if closure.get("gate") not in {
                "none",
                "author_judgement",
                "author_data",
                "experiment",
                "citation",
                "verification",
                "prose",
                "method",
                "analysis",
                "figure_layout",
                "packaging",
            }:
                errors.append(f"{prefix}: closure gate is invalid")
            if state == "open" and not (
                isinstance(closure.get("requirement"), str)
                and closure.get("requirement").strip()
            ):
                errors.append(f"{prefix}: open closure requires a requirement")
            if state == "not_applicable" and (
                closure.get("owner") != "none"
                or closure.get("gate") != "none"
            ):
                errors.append(
                    f"{prefix}: inapplicable closure requires owner/gate none"
                )
            if (
                adjudication == "unresolved"
                or evidence_state in {"needs_verification", "blocked"}
                or delta_status in {"partially_resolved", "still_open", "made_worse"}
            ) and state == "closed":
                errors.append(f"{prefix}: unresolved or blocked finding cannot be closed")
        provenance = finding.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{prefix}: provenance must be an object")
        elif adjudication == "merged":
            merged_from = provenance.get("merged_from_ids")
            if not merged_from:
                errors.append(
                    f"{prefix}: merged finding must preserve source finding IDs"
                )
            elif len(merged_from) != len(set(merged_from)):
                errors.append(
                    f"{prefix}: merged source finding IDs must be unique"
                )
            merged_into = provenance.get("merged_into_finding_id")
            if not isinstance(merged_into, str) or not merged_into:
                errors.append(
                    f"{prefix}: merged finding must identify canonical merge target"
                )
            elif merged_into == finding_id:
                errors.append(f"{prefix}: merged finding cannot target itself")
        dissent = finding.get("dissent")
        if not isinstance(dissent, dict):
            errors.append(f"{prefix}: dissent must be an object")
        elif dissent.get("state") not in {"none", "recorded", "unresolved"}:
            errors.append(f"{prefix}: dissent state is invalid")
        elif dissent.get("state") in {"recorded", "unresolved"} and not (
            isinstance(dissent.get("summary"), str)
            and dissent.get("summary").strip()
        ):
            errors.append(f"{prefix}: recorded dissent requires a summary")
        if adjudication == "rejected":
            if decision_impact != "none" or finding.get("action_type") != "no-action":
                errors.append(
                    f"{prefix}: rejected finding cannot remain a material obligation"
                )
        if finding_id and finding_id != stable_finding_id(finding) and prior_id is None:
            errors.append(
                f"{prefix}: new finding_id does not match stable identity fields"
            )
    return sorted(set(errors))


def _validate_validation_state(value: Any, prefix: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}: validation state must be an object"]
    errors: list[str] = []
    status = value.get("status")
    if status not in {"passed", "failed", "not_run"}:
        errors.append(f"{prefix}: status is invalid")
    locator = value.get("evidence_locator")
    digest = value.get("sha256")
    if status == "passed":
        if not isinstance(locator, str) or not locator:
            errors.append(f"{prefix}: passed validation requires evidence locator")
        if not _is_sha256(digest):
            errors.append(f"{prefix}: passed validation requires SHA-256")
    elif locator is not None or digest is not None:
        errors.append(f"{prefix}: non-passed validation must not claim evidence")
    return errors


def _validate_configuration_proof(
    value: Any, prefix: str, subject_kind: str, subject_id: str
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}: configuration proof must be an object"]
    errors: list[str] = []
    if value.get("subject_kind") != subject_kind:
        errors.append(f"{prefix}: configuration proof subject_kind mismatch")
    if value.get("subject_id") != subject_id:
        errors.append(f"{prefix}: configuration proof subject_id mismatch")
    if value.get("proof_kind") not in {
        "adapter_dispatch_record",
        "host_loaded_profile_receipt",
    }:
        errors.append(
            f"{prefix}: configuration proof cannot be self-report or static example"
        )
    if not _is_canonical_relative_locator(value.get("locator")):
        errors.append(
            f"{prefix}: configuration proof locator must be canonical and relative"
        )
    if not _is_sha256(value.get("sha256")):
        errors.append(f"{prefix}: configuration proof SHA-256 is required")
    return errors


def _coverage_ids(matrix: dict) -> list[str]:
    criteria = matrix.get("criteria", []) if isinstance(matrix, dict) else []
    return [
        row.get("criterion_id")
        for row in criteria
        if isinstance(row, dict) and isinstance(row.get("criterion_id"), str)
    ]


def validate_run_manifest(
    data: dict, coverage_matrix: dict, bundle_root: pathlib.Path
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["run-manifest: must be an object"]
    required = {
        "schema_version",
        "run_id",
        "created_at",
        "review_goal",
        "review_kind",
        "authorisation",
        "confidentiality",
        "review_only",
        "input_artifacts",
        "source_pdf_alignment",
        "target",
        "venue_profile",
        "runtime_profile",
        "delegation",
        "coverage",
        "stages",
        "output_artifacts",
        "completion",
        "limitations",
    }
    for field in sorted(required - set(data)):
        errors.append(f"run-manifest: missing required field: {field}")
    run_id = data.get("run_id")
    kind = data.get("review_kind")
    completion = data.get("completion")
    if kind not in {"initial", "delta"}:
        errors.append("run-manifest: review_kind must be initial or delta")
    if completion not in _ALLOWED_COMPLETION:
        errors.append("run-manifest: completion is invalid")
    if data.get("review_only") is not True:
        errors.append("run-manifest: review_only must be true")

    authorisation = data.get("authorisation")
    if not isinstance(authorisation, dict) or authorisation.get("authorised") is not True:
        errors.append("run-manifest: authorisation must be explicit and affirmative")
    elif authorisation.get("policy_status") == "prohibited":
        if completion != "blocked":
            errors.append(
                "run-manifest: prohibited policy requires blocked completion"
            )
    elif (
        authorisation.get("capacity") == "official_reviewer"
        and authorisation.get("policy_status") != "permitted"
        and completion != "blocked"
    ):
        errors.append(
            "run-manifest: unknown official-review policy requires blocked completion"
        )
    confidentiality = data.get("confidentiality")
    if not isinstance(confidentiality, dict):
        errors.append("run-manifest: confidentiality must be an object")
    else:
        if confidentiality.get("classification") not in {
            "public",
            "author_owned_draft",
            "official_confidential_submission",
        }:
            errors.append("run-manifest: confidentiality classification is invalid")
        if confidentiality.get("processing") not in {
            "local_only",
            "authorised_external",
        }:
            errors.append("run-manifest: confidentiality processing is invalid")
        if confidentiality.get("processing") == "authorised_external" and (
            confidentiality.get("external_transmission_authorised") is not True
        ):
            errors.append(
                "run-manifest: external processing requires transmission authority"
            )
        if confidentiality.get("processing") == "authorised_external" and not (
            isinstance(confidentiality.get("external_destination"), str)
            and confidentiality.get("external_destination").strip()
        ):
            errors.append(
                "run-manifest: external processing requires a recorded destination"
            )
        if confidentiality.get("processing") == "local_only" and (
            confidentiality.get("external_destination") is not None
        ):
            errors.append(
                "run-manifest: local-only processing cannot name an external destination"
            )
        if confidentiality.get("retention") not in {
            "run_only",
            "authorised_persistent",
            "unspecified",
        }:
            errors.append("run-manifest: retention boundary is invalid")
        if confidentiality.get("retention") == "unspecified" and completion == "complete":
            errors.append(
                "run-manifest: unspecified retention prevents complete status"
            )
        if confidentiality.get("untrusted_content_acknowledged") is not True:
            errors.append(
                "run-manifest: untrusted manuscript content boundary is required"
            )

    alignment = data.get("source_pdf_alignment")
    if not isinstance(alignment, dict):
        errors.append("run-manifest: source_pdf_alignment must be an object")
    elif (
        alignment.get("verified") is not True
        or alignment.get("status") not in {"matched", "source_only_verified"}
    ) and completion == "complete":
        errors.append(
            "run-manifest: source/PDF uncertainty or mismatch requires partial "
            "or blocked completion"
        )

    target = data.get("target")
    profile = data.get("venue_profile")
    if not isinstance(target, dict) or not isinstance(target.get("venue"), str):
        errors.append("run-manifest: target venue must be explicit, including unknown")
    elif target.get("venue") == "unknown":
        if not isinstance(profile, dict) or profile.get("status") != "unknown":
            errors.append("run-manifest: unknown venue requires unknown profile state")
    elif not isinstance(profile, dict) or profile.get("status") != "loaded":
        errors.append("run-manifest: known venue requires a loaded versioned profile")

    root = _normalise_root(bundle_root)
    try:
        canonical_coverage = load_review_coverage(root)
    except ValueError as exc:
        errors.append(f"run-manifest: canonical coverage unavailable: {exc}")
        canonical_coverage = {}
    if coverage_matrix != canonical_coverage:
        errors.append("run-manifest: supplied coverage matrix is not canonical")
    coverage = data.get("coverage")
    canonical_ids = _coverage_ids(canonical_coverage)
    coverage_finding_ids: set[str] = set()
    coverage_rows_for_links: list[dict] = []
    if not isinstance(coverage, dict):
        errors.append("run-manifest: coverage must be an object")
    else:
        if coverage.get("matrix_sha256") != _json_sha256(canonical_coverage):
            errors.append("run-manifest: coverage matrix hash mismatch")
        rows = coverage.get("criteria")
        if not isinstance(rows, list):
            errors.append("run-manifest: coverage criteria must be a list")
            rows = []
        row_ids = [
            row.get("criterion_id") for row in rows if isinstance(row, dict)
        ]
        for missing in sorted(set(canonical_ids) - set(row_ids)):
            errors.append(
                f"run-manifest: missing canonical criterion: {missing}"
            )
        for unknown in sorted(set(row_ids) - set(canonical_ids)):
            errors.append(f"run-manifest: unknown canonical criterion: {unknown}")
        if len(row_ids) != len(set(row_ids)):
            errors.append("run-manifest: duplicate canonical criterion")
        for index, row in enumerate(rows):
            prefix = f"run-manifest: coverage[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix} must be an object")
                continue
            coverage_rows_for_links.append(row)
            applicability = row.get("applicability")
            disposition = row.get("disposition")
            evidence = row.get("evidence")
            rationale = row.get("rationale")
            if applicability not in {"applicable", "inapplicable", "uncertain"}:
                errors.append(f"{prefix}: applicability is invalid")
            if disposition not in _ALLOWED_COVERAGE_DISPOSITION:
                errors.append(f"{prefix}: disposition is invalid")
            if applicability == "applicable":
                if not isinstance(evidence, list) or not evidence:
                    errors.append(
                        f"{prefix}: applicable criterion requires evidence"
                    )
                if disposition not in {
                    "assessed_no_finding",
                    "finding_linked",
                    "needs_verification",
                    "blocked",
                }:
                    errors.append(
                        f"{prefix}: applicable criterion disposition is inconsistent"
                    )
            elif applicability == "inapplicable":
                if disposition != "not_applicable" or not (
                    isinstance(rationale, str) and rationale.strip()
                ):
                    errors.append(
                        f"{prefix}: inapplicable criterion requires explicit rationale"
                    )
            elif applicability == "uncertain":
                if disposition not in {"needs_verification", "blocked"}:
                    errors.append(
                        f"{prefix}: uncertain criterion must need verification "
                        "or be blocked"
                    )
                if completion == "complete":
                    errors.append(
                        f"{prefix}: uncertain criterion requires partial or blocked "
                        "completion"
                    )
            if disposition == "blocked" and completion == "complete":
                errors.append(
                    f"{prefix}: blocked criterion requires partial or blocked completion"
                )
            finding_ids = row.get("finding_ids")
            if isinstance(finding_ids, list):
                coverage_finding_ids.update(
                    item for item in finding_ids if isinstance(item, str)
                )
                if disposition == "finding_linked" and not finding_ids:
                    errors.append(
                        f"{prefix}: finding_linked disposition requires finding IDs"
                    )
                if disposition in {"assessed_no_finding", "not_applicable"} and (
                    finding_ids
                ):
                    errors.append(
                        f"{prefix}: no-finding disposition cannot cite finding IDs"
                    )

    runtime = data.get("runtime_profile")
    manifest: dict = {}
    if not isinstance(runtime, dict):
        errors.append("run-manifest: runtime_profile must be an object")
        runtime = {}
    try:
        manifest = load_adapter_manifest(root)
    except ValueError as exc:
        errors.append(f"run-manifest: adapter manifest unavailable: {exc}")
    else:
        errors.extend(validate_adapter_manifest(manifest, root))
    errors.extend(
        _validate_configuration_proof(
            runtime.get("configuration_proof"),
            "run-manifest: root",
            "root",
            run_id if isinstance(run_id, str) else "",
        )
    )
    errors.extend(
        _validate_validation_state(
            runtime.get("model_validation"), "run-manifest: root model"
        )
    )
    errors.extend(
        _validate_validation_state(
            runtime.get("mode_validation"), "run-manifest: root mode"
        )
    )
    if runtime.get("requested_model") != "gpt-5.6-sol" or (
        runtime.get("requested_mode") != "ultra"
    ):
        errors.append("run-manifest: adapter root must request gpt-5.6-sol + ultra")
    if runtime.get("adapter_controlled_fallback") != "prohibited_and_checked":
        errors.append("run-manifest: root fallback must be prohibited and checked")
    if runtime.get("adapter_sha256") != manifest.get("adapter_payload_sha256"):
        errors.append("run-manifest: adapter SHA does not match adapter manifest")
    if runtime.get("selected_candidate_id") != manifest.get(
        "selected_candidate_id"
    ):
        errors.append("run-manifest: selected candidate disagrees with manifest")

    delegation = data.get("delegation")
    substantive_tasks: list[dict] = []
    if not isinstance(delegation, dict):
        errors.append("run-manifest: delegation must be an object")
        tasks: list = []
    else:
        if delegation.get("owner") != "root":
            errors.append("run-manifest: delegation owner must be root")
        tasks = delegation.get("tasks")
        if not isinstance(tasks, list):
            errors.append("run-manifest: delegation tasks must be a list")
            tasks = []
        if delegation.get("task_count_as_runtime_observation") != len(tasks):
            errors.append(
                "run-manifest: task_count_as_runtime_observation must equal "
                "observed task entries"
            )
    task_ids: set[str] = set()
    for index, task in enumerate(tasks):
        prefix = f"run-manifest: task[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be an object")
            continue
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{prefix}: task_id is required")
            task_id = ""
        elif task_id in task_ids:
            errors.append(f"{prefix}: duplicate task_id")
        task_ids.add(task_id)
        task_effects = task.get("task_effects")
        derived_substantive = isinstance(task_effects, list) and bool(
            set(item for item in task_effects if isinstance(item, str))
            & _SUBSTANTIVE_OPERATIONS
        )
        if derived_substantive and task.get("substantive") is not True:
            errors.append(
                f"{prefix}: finding/completion operation is derived substantive"
            )
        if task.get("substantive") is True:
            substantive_tasks.append(task)
            if (
                task.get("requested_model") != "gpt-5.6-sol"
                or task.get("requested_mode") != "ultra"
            ):
                errors.append(
                    f"{prefix}: substantive task must request gpt-5.6-sol + ultra"
                )
            errors.extend(
                _validate_configuration_proof(
                    task.get("configuration_proof"),
                    prefix,
                    "task",
                    task_id,
                )
            )
            errors.extend(
                _validate_validation_state(
                    task.get("model_validation"), f"{prefix} model"
                )
            )
            errors.extend(
                _validate_validation_state(
                    task.get("mode_validation"), f"{prefix} mode"
                )
            )
            if task.get("adapter_controlled_fallback") != "prohibited_and_checked":
                errors.append(f"{prefix}: substantive fallback is not controlled")
            if task.get("leaf_only") is not True:
                errors.append(f"{prefix}: substantive task must be leaf-only")
            if (
                task.get("status") == "completed"
                and task.get("descendant_state") != "none"
            ):
                errors.append(
                    f"{prefix}: completed substantive task descendant state "
                    "must be none"
                )
            if task.get("descendant_state") != "none" and completion == "complete":
                errors.append(
                    f"{prefix}: unknown descendant state requires partial or blocked "
                    "completion"
                )

    artifact_ids = {
        artifact.get("artifact_id")
        for artifact in data.get("input_artifacts", [])
        if isinstance(artifact, dict)
        and isinstance(artifact.get("artifact_id"), str)
    }
    stage_ids = {
        stage.get("stage_id")
        for stage in data.get("stages", [])
        if isinstance(stage, dict) and isinstance(stage.get("stage_id"), str)
    }
    canonical_owners = {
        row.get("criterion_id"): row.get("primary_stage_owner")
        for row in canonical_coverage.get("criteria", [])
        if isinstance(row, dict)
    }
    for row in coverage_rows_for_links:
        criterion_id = row.get("criterion_id")
        prefix = f"run-manifest: coverage[{criterion_id}]"
        stage_id = row.get("stage_id")
        if stage_id not in stage_ids:
            errors.append(f"{prefix}: stage_id does not reference a run stage")
        if canonical_owners.get(criterion_id) != stage_id:
            errors.append(
                f"{prefix}: stage owner differs from canonical primary owner"
            )
        for task_id in row.get("task_ids", []):
            if task_id not in task_ids:
                errors.append(f"{prefix}: unknown task_id reference: {task_id}")
        for evidence in row.get("evidence", []):
            if (
                not isinstance(evidence, dict)
                or evidence.get("artifact_id") not in artifact_ids
            ):
                errors.append(f"{prefix}: evidence references unknown artifact")

    claim = runtime.get("compatibility_claim")
    if claim not in {
        "evaluation_pending",
        "configured-and-evaluated",
        "runtime-attested",
    }:
        errors.append("run-manifest: compatibility_claim is invalid")
    if claim in {"configured-and-evaluated", "runtime-attested"}:
        promotion_ref = runtime.get("promotion_evaluation_record")
        if not isinstance(promotion_ref, dict):
            errors.append(
                "run-manifest: configured compatibility requires promotion record"
            )
        else:
            locator = promotion_ref.get("record_locator")
            if locator != manifest.get("promotion_record_locator"):
                errors.append(
                    "run-manifest: promotion locator does not match adapter manifest"
                )
            try:
                promotion, raw = load_adapter_promotion(root, locator)
            except (TypeError, ValueError) as exc:
                errors.append(f"run-manifest: promotion record invalid: {exc}")
            else:
                if hashlib.sha256(raw).hexdigest() != promotion_ref.get("sha256"):
                    errors.append("run-manifest: promotion record hash mismatch")
                for field in (
                    "record_id",
                    "candidate_id",
                    "adapter_sha256",
                    "result",
                    "promotion_decision",
                ):
                    if promotion_ref.get(field) != promotion.get(field):
                        errors.append(
                            f"run-manifest: promotion {field} does not match record"
                        )
                if promotion.get("result") != "pass":
                    errors.append("run-manifest: promotion result must be pass")
                if promotion.get("promotion_decision") != "selected":
                    errors.append("run-manifest: promotion decision must be selected")
                if promotion.get("candidate_id") != manifest.get(
                    "selected_candidate_id"
                ):
                    errors.append(
                        "run-manifest: promotion candidate disagrees with manifest"
                    )
                if promotion.get("adapter_sha256") != manifest.get(
                    "adapter_payload_sha256"
                ):
                    errors.append("run-manifest: promotion adapter SHA is stale")
        if runtime.get("model_validation", {}).get("status") != "passed":
            errors.append("run-manifest: root model validation did not pass")
        if runtime.get("mode_validation", {}).get("status") != "passed":
            errors.append("run-manifest: root mode validation did not pass")
        for task in substantive_tasks:
            if task.get("model_validation", {}).get("status") != "passed":
                errors.append(
                    f"run-manifest: substantive task {task.get('task_id')} model "
                    "validation did not pass"
                )
            if task.get("mode_validation", {}).get("status") != "passed":
                errors.append(
                    f"run-manifest: substantive task {task.get('task_id')} mode "
                    "validation did not pass"
                )
    elif runtime.get("promotion_evaluation_record") is not None:
        errors.append(
            "run-manifest: evaluation_pending must not claim a promotion record"
        )

    if claim == "runtime-attested":
        if (
            runtime.get("effective_telemetry") == "not_surfaced"
            or runtime.get("resolved_model") != "gpt-5.6-sol"
            or runtime.get("resolved_mode") != "ultra"
        ):
            errors.append(
                "run-manifest: runtime attestation requires surfaced matching telemetry"
            )
    elif runtime.get("effective_telemetry") == "not_surfaced":
        if runtime.get("resolved_model") is not None or runtime.get(
            "resolved_mode"
        ) is not None:
            errors.append(
                "run-manifest: absent telemetry requires null resolved model/mode"
            )

    # Retained for validate_run_pair without trusting a parallel field.
    data_finding_ids = data.get("_coverage_finding_ids")
    if data_finding_ids is not None:
        errors.append("run-manifest: private coverage helper field is forbidden")
    return sorted(set(errors))


def validate_run_pair(
    run: dict,
    ledger: dict,
    coverage_matrix: dict,
    bundle_root: pathlib.Path,
) -> list[str]:
    errors = validate_run_manifest(run, coverage_matrix, bundle_root)
    errors.extend(validate_finding_ledger(ledger))
    if isinstance(run, dict) and isinstance(ledger, dict):
        if run.get("run_id") != ledger.get("run_id"):
            errors.append("run-pair: run_id mismatch")
        if run.get("review_kind") != ledger.get("review_kind"):
            errors.append("run-pair: review_kind mismatch")
        if run.get("completion") != ledger.get("completion"):
            errors.append("run-pair: completion mismatch")
        ledger_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
        }
        canonical_criteria = set(_coverage_ids(coverage_matrix))
        for finding in ledger.get("findings", []):
            if not isinstance(finding, dict):
                continue
            criterion = finding.get("criterion")
            if criterion not in canonical_criteria:
                errors.append(
                    f"run-pair: finding uses unknown primary criterion: {criterion}"
                )
            related = finding.get("related_criteria")
            if not isinstance(related, list):
                errors.append("run-pair: finding related_criteria must be a list")
            else:
                if len(related) != len(set(related)):
                    errors.append(
                        "run-pair: finding related_criteria contains duplicates"
                    )
                for unknown in sorted(set(related) - canonical_criteria):
                    errors.append(
                        f"run-pair: finding uses unknown related criterion: {unknown}"
                    )
        artifact_ids = {
            artifact.get("artifact_id")
            for artifact in run.get("input_artifacts", [])
            if isinstance(artifact, dict)
        }
        for finding in ledger.get("findings", []):
            if not isinstance(finding, dict):
                continue
            evidence = finding.get("evidence")
            if (
                isinstance(evidence, dict)
                and evidence.get("artifact_id") not in artifact_ids
            ):
                errors.append(
                    "run-pair: finding evidence references unknown artifact_id: "
                    f"{evidence.get('artifact_id')}"
                )
        coverage_ids: set[str] = set()
        coverage = run.get("coverage")
        if isinstance(coverage, dict):
            for row in coverage.get("criteria", []):
                if isinstance(row, dict):
                    ids = row.get("finding_ids")
                    if isinstance(ids, list):
                        coverage_ids.update(
                            item for item in ids if isinstance(item, str)
                        )
        for unknown in sorted(coverage_ids - ledger_ids):
            errors.append(
                f"run-pair: coverage references unknown finding_id: {unknown}"
            )
        surviving_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status")
            in {"retained", "downgraded", "unresolved", "merged"}
        }
        merged_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status") == "merged"
        }
        rejected_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status") == "rejected"
        }
        if coverage_ids & merged_ids:
            errors.append("run-pair: merged finding cannot satisfy coverage")
        if coverage_ids & rejected_ids:
            errors.append("run-pair: rejected finding cannot satisfy coverage")
        for finding in ledger.get("findings", []):
            if not isinstance(finding, dict):
                continue
            if finding.get("adjudication_status") != "merged":
                continue
            provenance = finding.get("provenance")
            target = (
                provenance.get("merged_into_finding_id")
                if isinstance(provenance, dict)
                else None
            )
            if target not in ledger_ids:
                errors.append(
                    f"run-pair: merge target does not exist: {target}"
                )
        for missing in sorted(surviving_ids - coverage_ids):
            errors.append(
                f"run-pair: surviving finding missing from coverage: {missing}"
            )
    return sorted(set(errors))
