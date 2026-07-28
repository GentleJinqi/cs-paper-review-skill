"""Deterministic, offline validation for the portable paper-review bundle."""

from __future__ import annotations

import ast
import json
import pathlib
import re
import hashlib
import math
import shutil
import subprocess
import unicodedata
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

try:
    from scripts.adapter_evaluation_scorer import score_assertions
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from adapter_evaluation_scorer import score_assertions


REQUIRED_TREE = (
    "README.md",
    "README.zh-CN.md",
    "SKILL.md",
    "LICENSE",
    "VERSION",
    "CHANGELOG.md",
    "MIGRATION.md",
    "SOURCES.md",
    "THIRD_PARTY_NOTICES.md",
    "agents/openai.yaml",
    "references/scientific-core.md",
    "references/review-coverage.md",
    "references/review-coverage.json",
    "references/review-workflow.md",
    "references/finding-contract.md",
    "references/delta-review.md",
    "references/privacy-and-authorisation.md",
    "references/venue-conditioning.md",
    "references/venue-authorities.json",
    "references/adapter-evaluation-authority.json",
    "evals/adapter-fixtures/manifest.json",
    "evals/adapter-fixtures/quality-claim-evidence/input.json",
    "evals/adapter-fixtures/quality-claim-evidence/oracle.json",
    "evals/adapter-fixtures/lifecycle-interruption/input.json",
    "evals/adapter-fixtures/lifecycle-interruption/oracle.json",
    "evals/README.md",
    "evals/criteria.json",
    "evals/fixtures/manifest.json",
    "evals/score_run.py",
    "evals/output-manifest.schema.json",
    "evals/review-closure.schema.json",
    "evals/semantic-adjudication.schema.json",
    "evals/validate_closure.py",
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
    "schemas/adapter-evaluation-fixture-manifest.schema.json",
    "schemas/adapter-evaluation-input.schema.json",
    "schemas/adapter-evaluation-oracle.schema.json",
    "schemas/adapter-evaluation-output.schema.json",
    "schemas/adapter-evaluation-report.schema.json",
    "schemas/adapter-evaluation-execution-receipt.schema.json",
    "schemas/adapter-semantic-review-receipt.schema.json",
    "schemas/adapter-evaluation-authority.schema.json",
    "schemas/runtime-evidence-receipt.schema.json",
    "schemas/task-report.schema.json",
    "schemas/source-pdf-alignment-receipt.schema.json",
    "schemas/rendered-evidence-receipt.schema.json",
    "schemas/author-response.schema.json",
    "schemas/review-coverage.schema.json",
    "schemas/venue-profile.schema.json",
    "schemas/venue-source-manifest.schema.json",
    "schemas/venue-source-evidence.schema.json",
    "schemas/venue-source-capture.schema.json",
    "schemas/venue-authority-registry.schema.json",
    "schemas/venue-corpus-manifest.schema.json",
    "venue-intelligence/README.md",
    "venue-intelligence/examples/accepted-synthetic.json",
    "venue-intelligence/examples/topic-near-synthetic.json",
    "templates/run-manifest.json",
    "templates/finding-ledger.json",
    "templates/delegation-terminal-inventory.json",
    "templates/reviewer-report.md",
    "templates/ae-assessment.md",
    "templates/review-summary.md",
    "scripts/review_skill_validation.py",
    "scripts/adapter_evaluation_scorer.py",
    "scripts/render_human_binding.py",
    "scripts/build_terminal_inventory.py",
    "scripts/validate_bundle.py",
    "scripts/validate_run.py",
    "scripts/validate_venue_corpus.py",
    "scripts/release_manifest.py",
    "scripts/validate_release.py",
    "release/version-decision.json",
    "release/release-gates.md",
    "release/manifest.json",
    "tests/test_bundle.py",
    "tests/test_run_contracts.py",
    "tests/test_venue_corpus.py",
    "tests/test_evaluator.py",
    "tests/test_closure.py",
    "tests/test_release.py",
)

_ACTIVE_ROOT_FILES = ("README.md", "README.zh-CN.md", "SKILL.md")
_ACTIVE_DIRECTORIES = (
    "agents",
    "references",
    "adapters",
    "schemas",
    "templates",
    "scripts",
    "venue-intelligence",
)
_ACTIVE_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".toml", ".py"}
_ADAPTER_PROMOTION_LOCATOR = "compatibility/adapter-promotion.json"
_MODEL_INDEPENDENT_CORE = (
    "references/scientific-core.md",
    "references/review-coverage.md",
    "references/review-coverage.json",
    "references/review-workflow.md",
    "references/finding-contract.md",
    "references/delta-review.md",
    "references/privacy-and-authorisation.md",
    "references/venue-conditioning.md",
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
            r"`((?:references|templates|schemas|adapters|scripts|sources|docs)/"
            r"[^`\s]+)`"
        ),
        re.compile(
            r"\]\(((?:references|templates|schemas|adapters|scripts|sources|docs)/"
            r"[^)\s#]+)(?:#[^)]+)?\)"
        ),
        re.compile(
            r"(?<![\w/(])((?:references|templates|schemas|adapters|scripts|"
            r"sources|docs)/"
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
        if path.relative_to(root).as_posix() in {
            "README.md",
            "README.zh-CN.md",
        }:
            for match in re.finditer(r"\]\(([^)]+)\)", text):
                target = match.group(1).split("#", 1)[0].strip()
                if (
                    target
                    and not target.startswith(("http://", "https://", "mailto:"))
                ):
                    candidates.add(target)
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


_TOPOLOGY_NUMBER = (
    r"(?:[0-9]+|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    r"eighteen|nineteen|twenty|dozen)"
)
_TOPOLOGY_ROLE = r"(?:reviewers?|agents?|subagents?|tasks?|threads?)"


def _contains_fixed_topology_guidance(value: Any) -> bool:
    for arm in _policy_arms(value):
        nonclaim = re.search(
            r"\b(?:there\s+is\s+)?no\s+(?:fixed|required|default|minimum|"
            r"maximum)?\s*(?:reviewer|agent|subagent|task|thread)?\s*"
            r"(?:number|count|roster)\b"
            r"|\b(?:reviewer|agent|subagent|task|thread)\s+"
            r"(?:number|count|roster)\s+(?:is\s+)?not\s+(?:fixed|required)\b"
            r"|\b(?:do|must|should)\s+not\s+(?:always\s+)?"
            r"(?:dispatch|use|spawn|run)\b"
            r"|(?:没有|不设|无需|不要求|禁止).{0,18}"
            r"(?:固定|默认|最少|最多).{0,18}"
            r"(?:审稿人|评审员|代理|子代理|任务|线程)(?:数量|人数|个数)?",
            arm,
        )
        if nonclaim:
            continue
        if re.search(
            r"\bdefault\s+(?:publication\s+)?(?:venue|target)\b",
            arm,
        ):
            return True
        if re.search(r"\bmax[\s_]threads\s*(?:=|:)\s*[0-9]+\b", arm):
            return True
        topology_present = re.search(
            rf"\b{_TOPOLOGY_ROLE}\b"
            r"|\b(?:reviewer|agent|subagent|task|thread)\s+"
            r"(?:number|count|roster)\b"
            r"|(?:审稿人|评审员|代理|子代理|任务|线程)",
            arm,
        )
        if (
            topology_present
            and re.search(r"\b(?:strict|standard)\s+(?:tier|mode)\b", arm)
        ):
            return True
        if re.search(
            r"\b(?:default|fixed|required|minimum|maximum)\s+"
            r"(?:(?:number|count|roster)\s+(?:of\s+)?"
            rf"{_TOPOLOGY_ROLE}|{_TOPOLOGY_ROLE}|"
            r"(?:reviewer|agent|subagent|task|thread)\s+"
            r"(?:number|count|roster))\b",
            arm,
        ):
            return True
        if topology_present and re.search(
            rf"\b(?:always|must|required|requiredly|default(?:s)?\s+to|"
            rf"use|dispatch|spawn)\b.{{0,70}}\b{_TOPOLOGY_NUMBER}\b"
            rf"|\b{_TOPOLOGY_NUMBER}\b.{{0,50}}\b{_TOPOLOGY_ROLE}\b"
            r".{0,35}\b(?:strict|standard|required|default)\b"
            rf"|\b[0-9]+\s*(?:-|to)\s*[0-9]+\s+{_TOPOLOGY_ROLE}\b",
            arm,
        ):
            return True
        if re.search(
            r"(?:始终|总是|必须|默认|固定|至少|最多).{0,20}"
            r"(?:[零一二三四五六七八九十百两0-9]+位?)?"
            r"(?:审稿人|评审员|代理|子代理|任务|线程)"
            r"|(?:固定|默认)(?:审稿人|评审员|代理|子代理|任务|线程)"
            r"(?:数量|人数|个数)",
            arm,
        ):
            return True
    return False


def _markdown_policy_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    paragraph: list[str] = []
    fenced: list[str] | None = None
    fence_kind = ""

    def flush() -> None:
        if paragraph:
            fragments.append(" ".join(item.strip() for item in paragraph))
            paragraph.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            if fenced is None:
                flush()
                fenced = []
                fence_kind = stripped[3:].strip().split(maxsplit=1)[0].lower()
            else:
                fenced_text = "\n".join(fenced)
                if fence_kind == "json":
                    fragments.extend(
                        value
                        for _, value in _json_policy_fragments(fenced_text)
                    )
                elif fence_kind == "toml":
                    fragments.extend(
                        value
                        for _, value in _toml_policy_fragments(fenced_text)
                    )
                elif fence_kind in {"yaml", "yml"}:
                    fragments.extend(
                        value
                        for _, value in _yaml_policy_fragments(fenced_text)
                    )
                elif fence_kind in {"python", "py"}:
                    fragments.extend(
                        value
                        for _, value in _python_policy_fragments(fenced_text)
                    )
                else:
                    fragments.append(fenced_text)
                fenced = None
                fence_kind = ""
            continue
        if fenced is not None:
            fenced.append(raw_line)
            continue
        if not stripped:
            flush()
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush()
            fragments.extend(
                cell.strip()
                for cell in stripped.strip("|").split("|")
                if cell.strip()
            )
            continue
        if re.match(r"^(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", stripped):
            flush()
            paragraph.append(
                re.sub(
                    r"^(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)",
                    "",
                    stripped,
                )
            )
            continue
        paragraph.append(stripped)
    flush()
    if fenced is not None:
        raise ValueError("unterminated Markdown code fence")
    return [fragment for fragment in fragments if fragment.strip()]


def _json_policy_fragments(text: str) -> list[tuple[str, str]]:
    data = json.loads(
        text,
        object_pairs_hook=lambda pairs: _reject_duplicate_pairs(
            pairs, "active JSON"
        ),
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-JSON numeric constant {value}")
        ),
    )
    fragments: list[tuple[str, str]] = []

    def visit(value: Any, pointer: str) -> None:
        if isinstance(value, str):
            fragments.append((pointer or "/", value))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{pointer}/{index}")
        elif isinstance(value, dict):
            for key, item in value.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                child = f"{pointer}/{escaped}"
                if (
                    key == "max_threads"
                    and isinstance(item, int)
                    and not isinstance(item, bool)
                    and "/properties/" not in child
                ):
                    fragments.append((child, f"max_threads = {item}"))
                visit(item, child)

    visit(data, "")
    return fragments


def _toml_policy_fragments(text: str) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        index += 1
        if not stripped or stripped.startswith("#") or stripped.startswith("["):
            continue
        match = re.match(r"^([A-Za-z0-9_-]+)\s*=\s*(.*)$", stripped)
        if match is None:
            raise ValueError(f"unsupported TOML syntax at line {index}")
        key, raw_value = match.groups()
        if raw_value.startswith('"""'):
            content = raw_value[3:]
            collected: list[str] = []
            if content.endswith('"""') and len(content) >= 3:
                collected.append(content[:-3])
            else:
                if content:
                    collected.append(content)
                while index < len(lines):
                    line = lines[index]
                    index += 1
                    if '"""' in line:
                        before, after = line.split('"""', 1)
                        if after.strip():
                            raise ValueError(
                                f"trailing TOML syntax at line {index}"
                            )
                        collected.append(before)
                        break
                    collected.append(line)
                else:
                    raise ValueError("unterminated TOML multiline string")
            fragments.append((key, "\n".join(collected)))
        elif raw_value.startswith('"') and raw_value.endswith('"'):
            fragments.append((key, json.loads(raw_value)))
        elif raw_value.startswith("'") and raw_value.endswith("'"):
            fragments.append((key, raw_value[1:-1].replace("''", "'")))
        elif re.fullmatch(r"[+-]?[0-9]+", raw_value):
            if key == "max_threads":
                fragments.append((key, f"max_threads = {raw_value}"))
        else:
            raise ValueError(f"unsupported TOML value at line {index}")
    return fragments


def _yaml_policy_fragments(text: str) -> list[tuple[str, str]]:
    fragments: list[tuple[str, str]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        index += 1
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(
            r"^(\s*)([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$",
            raw_line,
        )
        if match is None:
            raise ValueError(f"unsupported YAML syntax at line {index}")
        indent, key, raw_value = match.groups()
        if raw_value in {"|", ">"}:
            collected: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                if (
                    candidate.strip()
                    and len(candidate) - len(candidate.lstrip())
                    <= len(indent)
                ):
                    break
                index += 1
                collected.append(candidate.strip())
            value = (
                " ".join(collected)
                if raw_value == ">"
                else "\n".join(collected)
            )
            fragments.append((key, value))
        elif not raw_value:
            continue
        elif raw_value.startswith('"') and raw_value.endswith('"'):
            fragments.append((key, json.loads(raw_value)))
        elif raw_value.startswith("'") and raw_value.endswith("'"):
            fragments.append((key, raw_value[1:-1].replace("''", "'")))
        else:
            fragments.append((key, raw_value))
    return fragments


def _python_policy_fragments(text: str) -> list[tuple[str, str]]:
    tree = ast.parse(text)
    excluded: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if (
            isinstance(function, ast.Attribute)
            and isinstance(function.value, ast.Name)
            and (
                function.value.id == "re"
                or (
                    function.value.id == "errors"
                    and function.attr == "append"
                )
            )
        ):
            for argument in node.args:
                for descendant in ast.walk(argument):
                    if isinstance(descendant, ast.Constant):
                        excluded.add(id(descendant))
    fragments: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in excluded
        ):
            fragments.append((f"line-{getattr(node, 'lineno', 1)}", node.value))
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(getattr(node, "value", None), ast.Constant)
            and isinstance(node.value.value, int)
        ):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            if any(
                isinstance(target, ast.Name)
                and target.id == "max_threads"
                for target in targets
            ):
                fragments.append(
                    (
                        f"line-{getattr(node, 'lineno', 1)}",
                        f"max_threads = {node.value.value}",
                    )
                )
    return fragments


def _policy_fragments_for_file(
    path: pathlib.Path,
) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".md":
        return [
            (f"fragment-{index}", fragment)
            for index, fragment in enumerate(
                _markdown_policy_fragments(text), start=1
            )
        ]
    if suffix == ".json":
        return _json_policy_fragments(text)
    if suffix == ".toml":
        return _toml_policy_fragments(text)
    if suffix in {".yaml", ".yml"}:
        return _yaml_policy_fragments(text)
    if suffix == ".py":
        return _python_policy_fragments(text)
    return [("/", text)]


def validate_no_count_based_rigor(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    for path in active_text_files(root):
        relative = path.relative_to(root).as_posix()
        try:
            fragments = _policy_fragments_for_file(path)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValueError,
            SyntaxError,
        ) as exc:
            errors.append(
                "count-based-rigor: cannot structurally scan active guidance "
                f"at {relative}: {exc}"
            )
            continue
        for locator, fragment in fragments:
            if _contains_fixed_topology_guidance(fragment):
                errors.append(
                    "count-based-rigor: forbidden active guidance at "
                    f"{relative}:{locator}"
                )
    return sorted(set(errors))


_RETIRED_PUBLIC_GUIDANCE = (
    "$cs-paper-review-protocol",
    "frozen-inputs.md",
    "official-rubric.md",
    "review-run-contract.md",
    "issue-ledger.md",
    "rejected-suggestions.md",
    "subagent-cleanup.md",
    "ae-adjudication.md",
)


def validate_no_retired_public_guidance(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    errors: list[str] = []
    for name in ("README.md", "README.zh-CN.md"):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        text = path.read_text(encoding="utf-8")
        for token in _RETIRED_PUBLIC_GUIDANCE:
            if token in text:
                errors.append(
                    f"retired-guidance: {name} references obsolete {token}"
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
    manifest_path = root / "adapters/codex/adapter-manifest.json"
    selected_candidate: Any = None
    if manifest_path.is_file():
        try:
            selected_candidate = _load_json_object(
                manifest_path,
                "adapter manifest",
            ).get("selected_candidate_id")
        except ValueError as exc:
            errors.append(f"adapter-profile: cannot read active manifest: {exc}")
    if selected_candidate is None:
        if "a null selection means `evaluation_pending`" not in normalised:
            errors.append(
                "adapter-profile: pending lifecycle selection is ambiguous"
            )
    else:
        selected_statement = (
            f"`{selected_candidate}` is the manifest-selected active "
            "lifecycle implementation"
        )
        if selected_statement not in normalised:
            errors.append(
                "adapter-profile: selected lifecycle implementation is "
                "ambiguous"
            )

    for relative in (
        "adapters/codex/agents/cs-paper-reviewer.toml",
        "adapters/codex/agents/cs-paper-ae.toml",
    ):
        agent_path = root / relative
        if not agent_path.is_file():
            errors.append(f"adapter-profile: missing custom agent example: {relative}")
            continue
        text = agent_path.read_text(encoding="utf-8")
        try:
            assignments = _parse_custom_agent_toml(text)
        except ValueError as exc:
            errors.append(
                f"adapter-profile: invalid custom agent TOML {relative}: {exc}"
            )
            continue
        expected_name = (
            "cs_paper_reviewer"
            if relative.endswith("cs-paper-reviewer.toml")
            else "cs_paper_ae"
        )
        if assignments.get("name") != expected_name:
            errors.append(
                f"adapter-profile: {relative} name must be {expected_name}"
            )
        if assignments.get("model") != "gpt-5.6-sol":
            errors.append(f"adapter-profile: {relative} model must be gpt-5.6-sol")
        if assignments.get("model_reasoning_effort") != "ultra":
            errors.append(f"adapter-profile: {relative} effort must be ultra")
        if assignments.get("sandbox_mode") != "read-only":
            errors.append(f"adapter-profile: {relative} sandbox must be read-only")
        instructions = assignments.get("developer_instructions", "")
        if not re.search(
            r"\bdo not\b.{0,220}\bdelegate any work\b",
            instructions,
            re.I | re.S,
        ):
            errors.append(f"adapter-profile: {relative} must prohibit delegation")
    return sorted(set(errors))


_CUSTOM_AGENT_KEYS = {
    "name",
    "description",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "developer_instructions",
}


def _parse_custom_agent_toml(text: str) -> dict[str, str]:
    """Parse the deliberately closed custom-agent TOML grammar.

    The portable validator runs under Python 3.9 and ``python -S``.  The two
    shipped profiles therefore use only top-level string assignments and one
    multiline basic string.  Rejecting everything else is safer than silently
    accepting syntax that this validator did not inspect.
    """

    lines = text.splitlines()
    values: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        multiline = re.fullmatch(
            r"([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*\"\"\"[ \t]*",
            line,
        )
        if multiline:
            key = multiline.group(1)
            body: list[str] = []
            while index < len(lines) and not re.fullmatch(
                r"\"\"\"[ \t]*", lines[index]
            ):
                if '"""' in lines[index]:
                    raise ValueError("multiline string terminator must stand alone")
                body.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError("unterminated multiline string")
            index += 1
            value = "\n".join(body)
        else:
            single = re.fullmatch(
                r'([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*'
                r'("(?:[^"\\]|\\.)*")[ \t]*',
                line,
            )
            if not single:
                raise ValueError(f"unsupported or malformed syntax on line {index}")
            key = single.group(1)
            raw_value = single.group(2)[1:-1]
            if "\\" in raw_value:
                raise ValueError(
                    f"escapes are outside the closed grammar on line {index}"
                )
            value = raw_value
        if key not in _CUSTOM_AGENT_KEYS:
            raise ValueError(f"unknown key {key!r}")
        if key in values:
            raise ValueError(f"duplicate key {key!r}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"key {key!r} requires a nonblank string")
        if "\\" in value:
            raise ValueError(
                f"backslashes are outside the closed grammar for key {key!r}"
            )
        values[key] = value
    missing = sorted(_CUSTOM_AGENT_KEYS - set(values))
    if missing:
        raise ValueError(f"missing required keys: {', '.join(missing)}")
    return values


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

            value = json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=no_duplicate_pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-JSON numeric constant {value}")
                ),
            )
            if _contains_nonfinite_number(value):
                raise ValueError("non-finite JSON number")
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
        if any(
            _contains_fixed_topology_guidance(fragment)
            for fragment in _markdown_policy_fragments(lowered)
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


def validate_contract_templates(root: pathlib.Path) -> list[str]:
    root = _normalise_root(root)
    try:
        run = _load_json_object(
            root / "templates/run-manifest.json",
            "run-manifest template",
        )
        ledger = _load_json_object(
            root / "templates/finding-ledger.json",
            "finding-ledger template",
        )
        coverage = load_review_coverage(root)
    except ValueError as exc:
        return [f"contract-template: {exc}"]
    return [
        f"contract-template: {error}"
        for error in validate_run_pair(
            run,
            ledger,
            coverage,
            root,
            evidence_root=root,
        )
    ]


def validate_bundle(root: pathlib.Path) -> list[str]:
    validators = (
        validate_required_tree,
        validate_skill_frontmatter,
        validate_reference_boundaries,
        validate_no_count_based_rigor,
        validate_no_retired_public_guidance,
        validate_adapter_profile,
        validate_active_adapter_manifest,
        validate_json_files,
        validate_schema_bundle,
        validate_venue_authority_registry,
        validate_venue_corpus_bundle,
        validate_adapter_evaluation_authority,
        validate_public_fixture_bundle,
        validate_release_bundle,
        _validate_core_boundaries,
        _validate_coverage_bundle,
        validate_contract_templates,
    )
    errors: list[str] = []
    for validator in validators:
        errors.extend(validator(root))
    return sorted(set(errors))


def validate_public_fixture_bundle(root: pathlib.Path) -> list[str]:
    """Route public-fixture validation through its deterministic evaluator."""

    try:
        from evals.score_run import validate_fixture_bundle
    except ModuleNotFoundError:
        return ["fixture-bundle: evaluator module is unavailable"]
    return validate_fixture_bundle(_normalise_root(root))


def validate_release_bundle(root: pathlib.Path) -> list[str]:
    """Route package-release validation through the release authority."""

    try:
        from scripts.validate_release import validate_release
    except ModuleNotFoundError:
        return ["release: validator module is unavailable"]
    return validate_release(_normalise_root(root))


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_FINDING_ID_RE = re.compile(r"F-[0-9a-f]{16}")
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x1f\x7f]")
_RFC3339_RE = re.compile(
    r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})[Tt]"
    r"(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?"
    r"(?:(?P<zulu>[Zz])|(?P<sign>[+-])(?P<offset_hour>[0-9]{2}):"
    r"(?P<offset_minute>[0-9]{2}))$"
)
_ACTIVE_ADAPTER_BASE = {
    "adapters/codex-gpt-5.6-sol-ultra.md",
    "adapters/codex/agents/cs-paper-reviewer.toml",
    "adapters/codex/agents/cs-paper-ae.toml",
}
_ALLOWED_ADJUDICATION = {
    "candidate",
    "retained",
    "merged",
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
_DECISION_IMPACT_RANK = {
    "none": 0,
    "advisory": 1,
    "limited": 2,
    "material": 3,
    "fundamental": 4,
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
_HUMAN_OUTPUT_HEADINGS = {
    "reviewer_report": (
        "# Independent Reviewer Report",
        "## Provenance",
        "## Criterion assessment",
        "## Candidate findings",
        "## Strengths and clean controls",
        "## Limitations and non-claims",
    ),
    "ae_assessment": (
        "# Adjudicated Assessment",
        "## Provenance",
        "## Candidate disposition",
        "## Canonical coverage",
        "## Portable assessment",
        "## Target-conditioned assessment",
        "## Completion and non-claims",
    ),
    "review_summary": (
        "# Review Summary",
        "## Outcome",
        "## Most decision-relevant findings",
        "## Strengths",
        "## Coverage and dissent",
        "## Author and readiness gates",
        "## Limitations and non-claims",
        "## Next boundary",
    ),
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
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _json_sha256(data: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(data)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_SHA256_RE.fullmatch(value))


def _is_nonblank_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_finding_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_FINDING_ID_RE.fullmatch(value))


def _is_rfc3339_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = _RFC3339_RE.fullmatch(value)
    if not match:
        return False
    second = int(match.group("second"))
    if second > 60:
        return False
    try:
        datetime(
            int(match.group("year")),
            int(match.group("month")),
            int(match.group("day")),
            int(match.group("hour")),
            int(match.group("minute")),
            min(second, 59),
        )
    except (TypeError, ValueError):
        return False
    if match.group("zulu") is not None:
        return True
    return (
        int(match.group("offset_hour")) <= 23
        and int(match.group("offset_minute")) <= 59
    )


def _parse_rfc3339_datetime(value: Any) -> datetime | None:
    if not _is_rfc3339_datetime(value) or not isinstance(value, str):
        return None
    normalised = value
    if normalised.endswith(("Z", "z")):
        normalised = normalised[:-1] + "+00:00"
    if re.search(r":60(?:[.,][0-9]+)?(?:Z|z|[+-])", value):
        return None
    try:
        return datetime.fromisoformat(normalised.replace(",", "."))
    except ValueError:
        return None


_MACHINE_BINDING_BEGIN = "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-BEGIN -->"
_MACHINE_BINDING_END = "<!-- CS-PAPER-REVIEW-MACHINE-BINDING-END -->"


def _human_venue_profile_authority(
    run: dict,
    bundle_root: pathlib.Path | None,
) -> dict | None:
    profile = run.get("venue_profile")
    if (
        bundle_root is None
        or not isinstance(profile, dict)
        or profile.get("status") != "loaded"
    ):
        return None
    try:
        receipt, _, errors = _load_bound_json_receipt(
            _normalise_root(bundle_root),
            profile.get("profile_locator"),
            profile.get("profile_sha256"),
            "human-view: venue profile",
        )
    except (TypeError, ValueError):
        return None
    return receipt if isinstance(receipt, dict) and not errors else None


def human_machine_binding(
    name: str,
    run: dict,
    ledger: dict,
    bundle_root: pathlib.Path | None = None,
) -> dict:
    venue_assessment = run.get("venue_assessment")
    role_assessment = venue_assessment
    if isinstance(venue_assessment, dict):
        role_assessment = json.loads(
            _canonical_json_bytes(venue_assessment).decode("utf-8")
        )
        role_assessment["native_fields"] = [
            row
            for row in role_assessment.get("native_fields", [])
            if isinstance(row, dict)
            and name in row.get("reported_in", [])
        ]
    profile_authority = _human_venue_profile_authority(
        run,
        bundle_root,
    )
    clone = lambda value: json.loads(  # noqa: E731
        _canonical_json_bytes(value).decode("utf-8")
    )
    return {
        "schema_version": "1.0.0",
        "role": name,
        "run_id": run.get("run_id"),
        "review_kind": run.get("review_kind"),
        "completion": run.get("completion"),
        "limitations": clone(run.get("limitations", [])),
        "target": clone(run.get("target")),
        "source_pdf_alignment": clone(run.get("source_pdf_alignment")),
        "coverage": clone(run.get("coverage", {}).get("criteria", [])),
        "findings": clone(ledger.get("findings", [])),
        "tasks": clone(run.get("delegation", {}).get("tasks", [])),
        "venue_profile": clone(run.get("venue_profile")),
        "venue_profile_authority_sha256": (
            _json_sha256(profile_authority)
            if isinstance(profile_authority, dict)
            else None
        ),
        "venue_profile_authority": clone(profile_authority),
        "venue_assessment_sha256": (
            _json_sha256(venue_assessment)
            if isinstance(venue_assessment, dict)
            else None
        ),
        "venue_assessment": clone(role_assessment),
    }


def _markdown_cell(value: Any) -> str:
    if value is None:
        text = "—"
    elif isinstance(value, (dict, list)):
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    else:
        text = str(value)
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def _human_binding_block(binding: dict) -> str:
    payload = _canonical_json_bytes(binding).decode("utf-8").strip()
    return "\n".join(
        (_MACHINE_BINDING_BEGIN, payload, _MACHINE_BINDING_END)
    )


def _render_coverage_table(run: dict) -> str:
    lines = [
        "| Criterion | Applicability | Disposition | Findings | Rationale |",
        "|---|---|---|---|---|",
    ]
    for row in run.get("coverage", {}).get("criteria", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row.get("criterion_id"),
                    row.get("applicability"),
                    row.get("disposition"),
                    row.get("finding_ids", []),
                    row.get("rationale"),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _render_finding_table(ledger: dict) -> str:
    lines = [
        "| Finding | Criterion | Status | Impact | Confidence | Evidence state | "
        "Claim | Action | Closure | Dissent |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for finding in ledger.get("findings", []):
        if not isinstance(finding, dict):
            continue
        closure = finding.get("closure_requirement", {})
        dissent = finding.get("dissent", {})
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    finding.get("finding_id"),
                    finding.get("criterion"),
                    finding.get("adjudication_status"),
                    finding.get("decision_impact"),
                    finding.get("confidence"),
                    finding.get("evidence_state"),
                    finding.get("claim"),
                    finding.get("action_type"),
                    closure if isinstance(closure, dict) else None,
                    dissent if isinstance(dissent, dict) else None,
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _render_venue_rule_table(binding: dict) -> str:
    lines = [
        "| Rule | Statement | Portable mapping | Assessment | Findings | "
        "Evidence | Rationale |",
        "|---|---|---|---|---|---|---|",
    ]
    profile = binding.get("venue_profile_authority")
    assessment = binding.get("venue_assessment")
    assessment_by_id = {
        row.get("rule_id"): row
        for row in (
            assessment.get("criteria", [])
            if isinstance(assessment, dict)
            else []
        )
        if isinstance(row, dict)
    }
    for rule in (
        profile.get("criteria", [])
        if isinstance(profile, dict)
        else []
    ):
        if not isinstance(rule, dict):
            continue
        row = assessment_by_id.get(rule.get("rule_id"), {})
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    rule.get("rule_id"),
                    rule.get("statement"),
                    rule.get("portable_criterion_ids", []),
                    row.get("assessment")
                    if isinstance(row, dict)
                    else None,
                    row.get("finding_ids", [])
                    if isinstance(row, dict)
                    else [],
                    row.get("evidence", [])
                    if isinstance(row, dict)
                    else [],
                    row.get("rationale")
                    if isinstance(row, dict)
                    else None,
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _render_native_table(run: dict, name: str) -> str:
    lines = [
        "| Field | Role | Status | Value | Basis | Rationale |",
        "|---|---|---|---|---|---|",
    ]
    assessment = run.get("venue_assessment", {})
    for row in (
        assessment.get("native_fields", [])
        if isinstance(assessment, dict)
        else []
    ):
        if not isinstance(row, dict):
            continue
        if name not in row.get("reported_in", []):
            continue
        lines.append(
            "| "
            + " | ".join(
                _markdown_cell(value)
                for value in (
                    row.get("field_id"),
                    row.get("role"),
                    row.get("status"),
                    row.get("value"),
                    row.get("basis"),
                    row.get("rationale"),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _render_limitations(run: dict) -> str:
    limitations = run.get("limitations", [])
    if not limitations:
        return "- None recorded."
    return "\n".join(f"- {_markdown_cell(item)}" for item in limitations)


def render_human_view(
    name: str,
    run: dict,
    ledger: dict,
    bundle_root: pathlib.Path | None = None,
) -> str:
    """Render the complete deterministic human view from canonical records."""

    if name not in _HUMAN_OUTPUT_HEADINGS:
        raise ValueError(f"unknown human view role: {name}")
    binding = human_machine_binding(name, run, ledger, bundle_root)
    target = run.get("target", {})
    target_text = "/".join(
        _markdown_cell(value)
        for value in (
            target.get("venue") if isinstance(target, dict) else None,
            target.get("year") if isinstance(target, dict) else None,
            target.get("track") if isinstance(target, dict) else None,
        )
    )
    provenance = "\n".join(
        (
            f"- Run ID: {_markdown_cell(run.get('run_id'))}",
            f"- Completion: {_markdown_cell(run.get('completion'))}",
            f"- Review kind: {_markdown_cell(run.get('review_kind'))}",
            f"- Target: {target_text}",
            "- Source/PDF alignment: "
            + _markdown_cell(
                run.get("source_pdf_alignment", {}).get("status")
                if isinstance(run.get("source_pdf_alignment"), dict)
                else None
            ),
            "- Bound task reports: "
            + _markdown_cell(
                [
                    {
                        "task_id": task.get("task_id"),
                        "agent_or_task_identifier":
                            task.get("agent_or_task_identifier"),
                        "report_sha256": task.get("report_sha256"),
                        "configuration_proof":
                            task.get("configuration_proof"),
                        "model_validation": task.get("model_validation"),
                        "mode_validation": task.get("mode_validation"),
                        "sandbox_validation": task.get("sandbox_validation"),
                    }
                    for task in run.get("delegation", {}).get("tasks", [])
                    if isinstance(task, dict)
                ]
            ),
        )
    )
    coverage = _render_coverage_table(run)
    findings = _render_finding_table(ledger)
    venue_rules = _render_venue_rule_table(binding)
    native = _render_native_table(run, name)
    limitations = _render_limitations(run)
    clean_controls = [
        row.get("criterion_id")
        for row in run.get("coverage", {}).get("criteria", [])
        if isinstance(row, dict)
        and row.get("disposition") == "assessed_no_finding"
    ]
    clean_text = _markdown_cell(clean_controls)
    if name == "reviewer_report":
        body = f"""# Independent Reviewer Report

## Provenance

{provenance}

## Criterion assessment

{coverage}

## Candidate findings

{findings}

## Strengths and clean controls

Assessed without a canonical finding: {clean_text}

## Target-native fields

### Venue criteria

{venue_rules}

### Native fields

{native}

## Limitations and non-claims

{limitations}
"""
    elif name == "ae_assessment":
        body = f"""# Adjudicated Assessment

## Provenance

{provenance}

## Candidate disposition

{findings}

## Canonical coverage

{coverage}

## Portable assessment

The canonical finding and coverage tables above are the portable assessment.

## Target-conditioned assessment

### Venue criteria

{venue_rules}

### Native fields

{native}

## Completion and non-claims

{limitations}
"""
    else:
        body = f"""# Review Summary

## Outcome

{provenance}

## Most decision-relevant findings

{findings}

## Strengths

Assessed without a canonical finding: {clean_text}

## Coverage and dissent

{coverage}

## Target-conditioned assessment

### Venue criteria

{venue_rules}

### Native fields

{native}

## Author and readiness gates

Closure owners, gates, requirements, and evidence are shown in the finding table.

## Limitations and non-claims

{limitations}

## Next boundary

This review does not authorise manuscript revision or experimental execution.
"""
    return body.rstrip() + "\n\n" + _human_binding_block(binding) + "\n"


def _reject_duplicate_pairs(
    pairs: list[tuple[str, Any]],
    label: str,
) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"{label} contains duplicate key {key!r}")
        result[key] = value
    return result


def _extract_machine_binding(
    text: str,
    prefix: str,
) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    if text.count(_MACHINE_BINDING_BEGIN) != 1 or text.count(
        _MACHINE_BINDING_END
    ) != 1:
        return (
            None,
            [
                f"{prefix}: human view requires exactly one machine-binding "
                "block"
            ],
        )
    start = text.find(_MACHINE_BINDING_BEGIN) + len(_MACHINE_BINDING_BEGIN)
    end = text.find(_MACHINE_BINDING_END, start)
    if end < start:
        return None, [f"{prefix}: machine-binding block is malformed"]
    payload = text[start:end].strip()
    try:
        binding = json.loads(
            payload,
            object_pairs_hook=lambda pairs: _reject_duplicate_pairs(
                pairs, "machine binding"
            ),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-JSON numeric constant {value}")
            ),
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [f"{prefix}: machine-binding JSON is invalid: {exc}"]
    if not isinstance(binding, dict):
        return None, [f"{prefix}: machine binding must be a JSON object"]
    canonical = _canonical_json_bytes(binding).decode("utf-8").strip()
    if payload != canonical:
        errors.append(f"{prefix}: machine-binding JSON is not canonical")
    exact_keys = {
        "schema_version",
        "role",
        "run_id",
        "review_kind",
        "completion",
        "limitations",
        "target",
        "source_pdf_alignment",
        "coverage",
        "findings",
        "tasks",
        "venue_profile",
        "venue_profile_authority_sha256",
        "venue_profile_authority",
        "venue_assessment_sha256",
        "venue_assessment",
    }
    if set(binding) != exact_keys:
        errors.append(f"{prefix}: machine binding has an invalid field set")
    return binding, errors


def _contains_positive_acceptance_prediction(text: str) -> bool:
    """Return whether text forecasts a venue outcome in either direction."""

    for arm in _policy_arms(text):
        if re.search(
            r"^\s*if\s+(?:the\s+)?(?:paper|submission|work\s+)?"
            r"(?:is\s+)?accepted\b",
            arm,
        ):
            continue
        if re.search(
            r"\bofficial\s+(?:venue\s+)?recommendation\s*:"
            r"\s*(?:leaning\s+)?(?:accept|reject)\b",
            arm,
        ):
            continue
        if re.search(
            r"\b(?:cannot|can't|unable\s+to|do\s+not|don't)\s+"
            r"(?:predict|estimate|know|determine)\b.{0,80}\b"
            r"(?:whether|if)\b.{0,80}\baccept",
            arm,
        ) or re.search(
            r"\bwhether\b.{0,80}\baccept(?:ed|ance)?\b.{0,80}"
            r"\b(?:cannot\s+be\s+predicted|is\s+unknown|remains\s+unknown)\b",
            arm,
        ) or re.search(
            r"\bno\s+acceptance\s+(?:probability|prediction|likelihood|"
            r"forecast)\b.{0,40}\b(?:is\s+)?"
            r"(?:claimed|predicted|provided|estimated|made)\b",
            arm,
        ) or re.search(
            r"(?:无法|不能)预测.{0,40}是否.{0,30}(?:接收|录用|收录)"
            r"|尚不清楚.{0,40}是否.{0,30}(?:接收|录用|收录)"
            r"|不(?:声称|提供|预测).{0,20}(?:接收|录用|收录)概率",
            arm,
        ):
            continue
        if re.search(
            r"\baccept(?:ance|ed)?\b.{0,50}\b"
            r"(?:probability|percentage|likelihood|chance|odds|forecast)\b"
            r"|\b(?:probability|percentage|likelihood|chance|odds|forecast)\b"
            r".{0,50}\b(?:accept(?:ance|ed)?|positive\s+venue\s+decision)\b"
            r"|\bacceptance\s+(?:is|seems|appears)\s+"
            r"(?:highly\s+|very\s+)?(?:likely|unlikely|probable)\b"
            r"|\b(?:likely|unlikely|probably|almost\s+certainly|not\s+likely)"
            r"\s+(?:to\s+be\s+)?accepted\b"
            r"|\b(?:will|would|should|is\s+going\s+to)\s+"
            r"(?:(?:likely|probably|almost\s+certainly)\s+)?"
            r"(?:not\s+)?(?:be|get)\s+accepted\b"
            r"|\b(?:predict|expect|believe|estimate)\b.{0,70}\b"
            r"(?:accepted|acceptance|positive\s+venue\s+decision)\b"
            r"|\b(?:this|the)\s+(?:paper|submission|work)\s+"
            r"(?:will|would|should|is\s+going\s+to)\s+"
            r"(?:not\s+)?(?:be|get)\s+accepted\b"
            r"|(?:很可能|大概率|不太可能|预计|预测).{0,30}"
            r"(?:被)?(?:接收|录用|收录)"
            r"|(?:接收|录用|收录)(?:概率|可能性|几率)",
            arm,
        ):
            return True
    return False


def _contains_acceptance_metric_request(value: Any) -> bool:
    text = _normalised_semantic_scan_text(value)
    return bool(
        re.search(
            r"\baccept(?:ance)?\s+(?:probability|percentage|likelihood|"
            r"chance|odds|forecast)\b"
            r"|\b(?:probability|percentage|likelihood|chance|odds|forecast)"
            r"\s+of\s+accept"
            r"|(?:接收|录用|收录)(?:概率|可能性|几率)",
            text,
        )
    )


def _string_leaves(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [
            leaf
            for item in value
            for leaf in _string_leaves(item)
        ]
    if isinstance(value, dict):
        return [
            leaf
            for item in value.values()
            for leaf in _string_leaves(item)
        ]
    return []


def _contains_count_based_confidence(value: Any) -> bool:
    for text in _string_leaves(value):
        for arm in _policy_arms(text):
            topology = re.search(
                r"\b(?:agent|subagent|reviewer|task|thread)\s+"
                r"(?:count|number|roster)\b"
                r"|\b(?:[0-9]+|one|two|three|four|five|six|seven|eight|"
                r"nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
                r"sixteen|seventeen|eighteen|nineteen|twenty|dozen|more|"
                r"fewer|many|several)\s+(?:independent\s+)?"
                r"(?:agents?|subagents?|reviewers?|tasks?|threads?)\b"
                r"|(?:审稿人|评审员|代理|子代理|任务)(?:数量|人数|个数|越多)"
                r"|(?:[零一二三四五六七八九十百两0-9]+)位?"
                r"(?:审稿人|评审员|代理|子代理)",
                arm,
            )
            quality_arm = re.sub(
                r"\bconfidence\s+intervals?\b",
                "",
                arm,
            )
            quality = re.search(
                r"\b(?:confidence|quality|rigour|rigor|reliab(?:le|ility)|"
                r"trustworth(?:y|iness)|certaint(?:y|ies)|credib(?:le|ility)|"
                r"validity)\b|(?:可信度|可靠性|置信度|评审质量|质量越高)",
                quality_arm,
            )
            causal = re.search(
                r"\b(?:because|therefore|hence|thus|so|consequently|"
                r"guarantee[sd]?|establish(?:es|ed)?|prove[sd]?|"
                r"improv(?:e|es|ed)|increase[sd]?|make[sd]?|means?|"
                r"lead[sd]?\s+to)\b|(?:因此|所以|意味着|代表|保证|导致|"
                r"越多.{0,30}越高)",
                arm,
            )
            nonclaim = re.search(
                r"\b(?:does|do|did|can|cannot|must)\s+not\b.{0,45}"
                r"\b(?:establish|guarantee|prove|improve|increase|mean|"
                r"represent)\b"
                r"|\b(?:rather\s+than|comes?\s+from\s+evidence|"
                r"derives?\s+from\s+evidence)\b"
                r"|(?:不代表|不意味着|不能证明|仅用于记录|与.{0,20}无关)",
                arm,
            )
            if topology and quality and causal and not nonclaim:
                return True
    return False


def _validate_human_output(
    name: str,
    raw: bytes,
    run_id: Any,
    completion: Any,
) -> list[str]:
    prefix = f"run-manifest: output_artifact[{name}]"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"{prefix}: human view is not UTF-8: {exc}"]
    errors: list[str] = []
    binding, binding_errors = _extract_machine_binding(text, prefix)
    errors.extend(binding_errors)
    binding_begin = text.find(_MACHINE_BINDING_BEGIN)
    binding_end = text.find(_MACHINE_BINDING_END)
    visible_text = text
    if binding_begin >= 0 and binding_end >= binding_begin:
        visible_text = (
            text[:binding_begin]
            + text[
                binding_end + len(_MACHINE_BINDING_END):
            ]
        )
    if len(raw) < 256:
        errors.append(f"{prefix}: human view is too short to satisfy its contract")
    for heading in _HUMAN_OUTPUT_HEADINGS[name]:
        count = len(
            re.findall(
                rf"(?m)^{re.escape(heading)}[ \t]*$",
                text,
            )
        )
        if count != 1:
            errors.append(
                f"{prefix}: human view requires exactly one {heading!r} heading"
            )
    run_lines = re.findall(r"(?m)^-\s*Run ID:\s*(.*?)\s*$", text)
    if len(run_lines) != 1:
        errors.append(f"{prefix}: human view requires exactly one Run ID")
    elif _is_nonblank_string(run_id) and run_lines[0] != run_id:
        errors.append(f"{prefix}: human view does not bind run_id")
    completion_lines = re.findall(
        r"(?m)^-\s*Completion:\s*(.*?)\s*$",
        text,
    )
    if len(completion_lines) != 1:
        errors.append(f"{prefix}: human view requires exactly one Completion")
    elif (
        completion in _ALLOWED_COMPLETION
        and completion_lines[0] != completion
    ):
        errors.append(f"{prefix}: human view does not bind completion")
    candidate_tokens = re.findall(
        r"(?<![A-Za-z0-9-])F-[A-Za-z0-9-]+",
        text,
    )
    for token in candidate_tokens:
        if _FINDING_ID_RE.fullmatch(token) is None:
            errors.append(f"{prefix}: malformed finding ID token: {token}")
    try:
        policy_fragments = _markdown_policy_fragments(visible_text)
    except ValueError as exc:
        errors.append(
            f"{prefix}: visible Markdown policy scan failed closed: {exc}"
        )
        policy_fragments = []
    if isinstance(binding, dict):
        policy_fragments.extend(_string_leaves(binding))
    if any(
        _contains_positive_acceptance_prediction(fragment)
        for fragment in policy_fragments
    ):
        errors.append(f"{prefix}: acceptance prediction is forbidden")
    if _contains_count_based_confidence(policy_fragments):
        errors.append(
            f"{prefix}: execution topology cannot establish scientific confidence"
        )
    if isinstance(binding, dict):
        if binding.get("schema_version") != "1.0.0":
            errors.append(f"{prefix}: machine binding schema version is invalid")
        if binding.get("role") != name:
            errors.append(f"{prefix}: machine binding role is invalid")
        if binding.get("run_id") != run_id:
            errors.append(f"{prefix}: machine binding does not bind run_id")
        if binding.get("completion") != completion:
            errors.append(f"{prefix}: machine binding does not bind completion")
    return errors


def _safe_bundle_file(root: pathlib.Path, locator: str) -> pathlib.Path:
    root = _normalise_root(root)
    if not isinstance(locator, str) or not locator:
        raise ValueError("locator must be a non-empty bundle-relative path")
    if _CONTROL_CHARACTER_RE.search(locator):
        raise ValueError("locator may not contain control characters")
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
    if path.stat().st_nlink != 1:
        raise ValueError("locator may not resolve to a hard-linked file")
    return path


def _parsed_pdf_page_count(path: pathlib.Path) -> tuple[int | None, str | None]:
    """Parse a frozen PDF instead of trusting its header or receipt prose."""

    executable = shutil.which("pdfinfo")
    if executable is None:
        return None, "pdfinfo is unavailable"
    try:
        completed = subprocess.run(
            [executable, str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"pdfinfo failed: {exc}"
    if completed.returncode != 0:
        return None, "pdfinfo rejected the frozen PDF"
    match = re.search(r"(?m)^Pages:\s*([0-9]+)\s*$", completed.stdout)
    if match is None:
        return None, "pdfinfo did not report a page count"
    page_count = int(match.group(1))
    if page_count < 1:
        return None, "pdfinfo reported no pages"
    return page_count, None


def _extracted_pdf_page_text(
    path: pathlib.Path,
    page: int,
) -> tuple[str | None, str | None]:
    """Extract one page with fixed Poppler arguments for reproducible checks."""

    executable = shutil.which("pdftotext")
    if executable is None:
        return None, "pdftotext is unavailable"
    try:
        completed = subprocess.run(
            [
                executable,
                "-f",
                str(page),
                "-l",
                str(page),
                "-layout",
                "-enc",
                "UTF-8",
                str(path),
                "-",
            ],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"pdftotext failed: {exc}"
    if completed.returncode != 0:
        return None, "pdftotext rejected the frozen PDF"
    try:
        return completed.stdout.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return None, f"pdftotext returned non-UTF-8 output: {exc}"


def _pdftoppm_version() -> tuple[str | None, str | None]:
    executable = shutil.which("pdftoppm")
    if executable is None:
        return None, "pdftoppm is unavailable"
    try:
        completed = subprocess.run(
            [executable, "-v"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"pdftoppm version check failed: {exc}"
    output = (completed.stdout + completed.stderr).decode(
        "utf-8", errors="replace"
    )
    match = re.search(r"\bpdftoppm version ([^\s]+)", output)
    if completed.returncode != 0 or match is None:
        return None, "pdftoppm version is unavailable"
    return match.group(1), None


def _render_pdf_page_png(
    path: pathlib.Path,
    page: int,
) -> tuple[bytes | None, str | None]:
    executable = shutil.which("pdftoppm")
    if executable is None:
        return None, "pdftoppm is unavailable"
    try:
        completed = subprocess.run(
            [
                executable,
                "-f",
                str(page),
                "-l",
                str(page),
                "-singlefile",
                "-r",
                "72",
                "-png",
                str(path),
            ],
            check=False,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"pdftoppm rendering failed: {exc}"
    if completed.returncode != 0:
        return None, "pdftoppm rejected the frozen PDF"
    if not completed.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        return None, "pdftoppm did not return a PNG page"
    return completed.stdout, None


def _is_canonical_relative_locator(locator: Any) -> bool:
    if (
        not isinstance(locator, str)
        or not locator
        or "\\" in locator
        or _CONTROL_CHARACTER_RE.search(locator)
    ):
        return False
    pure = pathlib.PurePosixPath(locator)
    return (
        not pure.is_absolute()
        and "." not in pure.parts
        and ".." not in pure.parts
        and pure.as_posix() == locator
    )


def _roots_overlap(left: pathlib.Path, right: pathlib.Path) -> bool:
    left = _normalise_root(left)
    right = _normalise_root(right)
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _load_json_object(path: pathlib.Path, label: str) -> dict:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict:
        result: dict = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate object key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=no_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"non-JSON numeric constant {value}")
            ),
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unparsable: {exc}") from exc
    except ValueError as exc:
        raise ValueError(f"{label} is unparsable: {exc}") from exc
    if _contains_nonfinite_number(value):
        raise ValueError(f"{label} is unparsable: non-finite JSON number")
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _contains_nonfinite_number(value: Any) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, int):
        return False
    if isinstance(value, list):
        return any(_contains_nonfinite_number(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_nonfinite_number(item) for item in value.values())
    return False


def _json_equal(left: Any, right: Any) -> bool:
    """Compare JSON values without treating booleans as numbers."""

    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if left is None or right is None:
        return left is right
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, dict) or isinstance(right, dict):
        return (
            isinstance(left, dict)
            and isinstance(right, dict)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return type(left) is type(right) and left == right


def _schema_type_matches(value: Any, expected: str) -> bool:
    mapping = {
        "null": lambda item: item is None,
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: (
            isinstance(item, int) and not isinstance(item, bool)
        ) or (
            isinstance(item, float)
            and math.isfinite(item)
            and item.is_integer()
        ),
        "number": lambda item: isinstance(item, (int, float))
        and not isinstance(item, bool),
    }
    predicate = mapping.get(expected)
    return bool(predicate and predicate(value))


def _schema_branch_declared_type_matches(
    value: Any,
    schema: dict,
    root_schema: dict,
) -> bool:
    candidate = schema
    reference = candidate.get("$ref")
    if isinstance(reference, str):
        try:
            candidate = _resolve_local_schema_ref(root_schema, reference)
        except ValueError:
            return False
    expected = candidate.get("type")
    expected_types = [expected] if isinstance(expected, str) else expected
    if not isinstance(expected_types, list):
        return True
    return any(
        isinstance(item, str) and _schema_type_matches(value, item)
        for item in expected_types
    )


def _resolve_local_schema_ref(root_schema: dict, reference: str) -> dict:
    match = (
        re.fullmatch(r"#/\$defs/([^~/]+)", reference)
        if isinstance(reference, str)
        else None
    )
    if not match:
        raise ValueError(
            "only direct local #/$defs/<name> JSON Schema references are "
            "supported"
        )
    definitions = root_schema.get("$defs")
    name = match.group(1)
    if not isinstance(definitions, dict) or name not in definitions:
        raise ValueError(f"unresolved JSON Schema reference: {reference}")
    value: Any = definitions[name]
    if not isinstance(value, dict):
        raise ValueError(f"JSON Schema reference is not an object: {reference}")
    return value


_SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "$ref",
    "$defs",
    "$comment",
    "title",
    "description",
    "type",
    "const",
    "enum",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minLength",
    "maxLength",
    "pattern",
    "minimum",
    "format",
    "oneOf",
    "allOf",
    "if",
    "then",
    "else",
}
_SUPPORTED_JSON_TYPES = {
    "null",
    "boolean",
    "object",
    "array",
    "string",
    "integer",
    "number",
}


def _audit_schema_node(
    schema: Any,
    path: str = "$",
    root_schema: dict | None = None,
    ref_stack: tuple[str, ...] = (),
) -> list[str]:
    if not isinstance(schema, dict):
        return [f"schema-audit: {path}: schema node must be an object"]
    root_schema = schema if root_schema is None else root_schema
    errors: list[str] = []
    for keyword in sorted(set(schema) - _SUPPORTED_SCHEMA_KEYWORDS):
        errors.append(
            f"schema-audit: {path}: unsupported keyword {keyword}"
        )
    if path != "$" and "$id" in schema:
        errors.append(
            f"schema-audit: {path}: nested $id resource rebasing is unsupported"
        )
    for keyword in ("$schema", "$id", "$comment", "title", "description"):
        metadata = schema.get(keyword)
        if metadata is not None and not isinstance(metadata, str):
            errors.append(
                f"schema-audit: {path}: {keyword} must be a string"
            )
    declared_type = schema.get("type")
    if declared_type is not None:
        declared_types = (
            [declared_type]
            if isinstance(declared_type, str)
            else declared_type
        )
        if (
            not isinstance(declared_types, list)
            or not declared_types
            or any(
                not isinstance(item, str)
                or item not in _SUPPORTED_JSON_TYPES
                for item in declared_types
            )
            or len(declared_types) != len(set(declared_types))
        ):
            errors.append(
                f"schema-audit: {path}: type must contain unique supported "
                "JSON types"
            )
    for keyword in ("required",):
        value = schema.get(keyword)
        if value is not None and (
            not isinstance(value, list)
            or any(not isinstance(item, str) for item in value)
            or len(value) != len(set(value))
        ):
            errors.append(
                f"schema-audit: {path}: {keyword} must be a unique string list"
            )
    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list) or not enum:
            errors.append(
                f"schema-audit: {path}: enum must be a non-empty array"
            )
        elif any(
            _json_equal(enum[left], enum[right])
            for left in range(len(enum))
            for right in range(left + 1, len(enum))
        ):
            errors.append(
                f"schema-audit: {path}: enum values must be unique"
            )
    for keyword in ("$defs", "properties"):
        value = schema.get(keyword)
        if value is not None and (
            not isinstance(value, dict)
            or any(not isinstance(child, dict) for child in value.values())
        ):
            errors.append(
                f"schema-audit: {path}: {keyword} must map names to schemas"
            )
    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, (bool, dict)):
        errors.append(
            f"schema-audit: {path}: additionalProperties must be boolean or schema"
        )
    items = schema.get("items")
    if items is not None and not isinstance(items, dict):
        errors.append(f"schema-audit: {path}: items must be a schema object")
    for keyword in ("minItems", "maxItems", "minLength", "maxLength"):
        value = schema.get(keyword)
        if value is not None and (
            not _schema_type_matches(value, "integer") or value < 0
        ):
            errors.append(
                f"schema-audit: {path}: {keyword} must be a non-negative integer"
            )
    minimum = schema.get("minimum")
    if minimum is not None and (
        not isinstance(minimum, (int, float)) or isinstance(minimum, bool)
    ):
        errors.append(f"schema-audit: {path}: minimum must be numeric")
    elif isinstance(minimum, float) and not math.isfinite(minimum):
        errors.append(f"schema-audit: {path}: minimum must be finite")
    unique_items = schema.get("uniqueItems")
    if unique_items is not None and not isinstance(unique_items, bool):
        errors.append(f"schema-audit: {path}: uniqueItems must be boolean")
    pattern = schema.get("pattern")
    if pattern is not None:
        if not isinstance(pattern, str):
            errors.append(f"schema-audit: {path}: pattern must be a string")
        else:
            try:
                re.compile(pattern)
            except re.error as exc:
                errors.append(
                    f"schema-audit: {path}: pattern is invalid: {exc}"
                )
            if re.search(r"\(\?P|\\[AZ]|\(\?<[-=!]", pattern):
                errors.append(
                    f"schema-audit: {path}: pattern uses syntax outside the "
                    "closed ECMAScript-compatible subset"
                )
    format_name = schema.get("format")
    if format_name is not None and format_name != "date-time":
        errors.append(
            f"schema-audit: {path}: unsupported format {format_name!r}"
        )
    for keyword in ("oneOf", "allOf"):
        value = schema.get(keyword)
        if value is not None and (
            not isinstance(value, list)
            or not value
            or any(not isinstance(child, dict) for child in value)
        ):
            errors.append(
                f"schema-audit: {path}: {keyword} must be a non-empty schema list"
            )
    for keyword in ("if", "then", "else"):
        value = schema.get(keyword)
        if value is not None and not isinstance(value, dict):
            errors.append(
                f"schema-audit: {path}: {keyword} must be a schema object"
            )
    if ("then" in schema or "else" in schema) and "if" not in schema:
        errors.append(
            f"schema-audit: {path}: then/else requires an if schema"
        )
    reference = schema.get("$ref")
    if reference is not None and (
        not isinstance(reference, str)
        or re.fullmatch(r"#/\$defs/[^~/]+", reference) is None
    ):
        errors.append(
            f"schema-audit: {path}: only direct local #/$defs/<name> refs "
            "are supported"
        )
    elif isinstance(reference, str):
        try:
            target = _resolve_local_schema_ref(root_schema, reference)
        except ValueError as exc:
            errors.append(f"schema-audit: {path}: {exc}")
        else:
            if reference in ref_stack:
                chain = " -> ".join((*ref_stack, reference))
                errors.append(
                    f"schema-audit: {path}: cyclic JSON Schema reference: {chain}"
                )
            else:
                errors.extend(
                    _audit_schema_node(
                        target,
                        f"{path}.$ref({reference})",
                        root_schema,
                        (*ref_stack, reference),
                    )
                )
    for container_key in ("$defs", "properties"):
        container = schema.get(container_key)
        if isinstance(container, dict):
            for name, child in container.items():
                errors.extend(
                    _audit_schema_node(
                        child,
                        f"{path}.{container_key}.{name}",
                        root_schema,
                        ref_stack,
                    )
                )
    for child_key in ("additionalProperties", "items", "if", "then", "else"):
        child = schema.get(child_key)
        if isinstance(child, dict):
            errors.extend(
                _audit_schema_node(
                    child,
                    f"{path}.{child_key}",
                    root_schema,
                    ref_stack,
                )
            )
    for array_key in ("oneOf", "allOf"):
        children = schema.get(array_key)
        if isinstance(children, list):
            for index, child in enumerate(children):
                errors.extend(
                    _audit_schema_node(
                        child,
                        f"{path}.{array_key}[{index}]",
                        root_schema,
                        ref_stack,
                    )
                )
    return errors


def validate_schema_bundle(root: pathlib.Path) -> list[str]:
    """Audit every published schema, independent of template reachability."""

    root = _normalise_root(root)
    schema_root = root / "schemas"
    errors: list[str] = []
    if not schema_root.is_dir() or schema_root.is_symlink():
        return ["schema-audit: schemas directory is missing or unsafe"]
    for path in sorted(schema_root.glob("*.json")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink() or not path.is_file():
            errors.append(f"schema-audit: unsafe schema file: {relative}")
            continue
        try:
            schema = _load_json_object(path, relative)
        except ValueError as exc:
            errors.append(f"schema-audit: {relative}: {exc}")
            continue
        errors.extend(
            f"{relative}: {error}" for error in _audit_schema_node(schema)
        )
    return sorted(set(errors))


_VENUE_CORPUS_TOPIC_DIMENSIONS = {
    "problem_family",
    "contribution_type",
    "mechanism_family",
    "claim_types",
    "evidence_structures",
    "modality_applications",
}
_VENUE_CORPUS_GRADE_SOURCES = {
    "A": {
        "official-program",
        "official-proceedings",
        "official-decision-record",
    },
    "B": {"venue-authorised-platform"},
    "C": {"bibliographic-index", "author-record"},
    "D": {"unverified"},
}


def validate_venue_corpus_document(
    value: Any,
    bundle_root: pathlib.Path,
    label: str,
) -> list[str]:
    """Validate one corpus manifest and its evidence semantics."""

    prefix = f"venue-corpus: {label}"
    if not isinstance(value, dict):
        return [f"{prefix}: manifest must be an object"]
    errors = [
        f"{prefix}: {error}"
        for error in validate_json_schema_document(
            value,
            bundle_root,
            "schemas/venue-corpus-manifest.schema.json",
            label,
        )
    ]
    rights = value.get("rights_boundary")
    if isinstance(rights, dict) and (
        rights.get("metadata_only") is not True
        or rights.get("manuscript_bytes_stored") is not False
    ):
        errors.append(
            f"{prefix}: corpus must contain metadata only; manuscript bytes "
            "must not be stored"
        )
    if errors:
        return sorted(set(errors))

    items = value["items"]
    search = value["search"]
    if search["included_count"] != len(items):
        errors.append(
            f"{prefix}: search included_count must equal the item inventory"
        )
    if search["included_count"] > search["screened_count"]:
        errors.append(
            f"{prefix}: included_count cannot exceed screened_count"
        )
    paper_ids = [item["paper_id"] for item in items]
    if len(paper_ids) != len(set(paper_ids)):
        errors.append(f"{prefix}: paper IDs must be unique")

    boundary = value["inclusion_boundary"]
    if set(boundary["topic_dimensions"]) != _VENUE_CORPUS_TOPIC_DIMENSIONS:
        errors.append(
            f"{prefix}: inclusion boundary must declare exactly the six "
            "topic-comparison dimensions"
        )
    allowed_statuses = set(boundary["decision_statuses"])
    purpose = value["purpose"]
    material_items = 0
    for item in items:
        item_prefix = f"{prefix}: item {item['paper_id']}"
        status = item["status"]
        if status not in allowed_statuses:
            errors.append(
                f"{item_prefix}: status is outside the declared inclusion "
                "boundary"
            )
        grade = item["evidence_grade"]
        source_type = item["status_source_type"]
        if source_type not in _VENUE_CORPUS_GRADE_SOURCES[grade]:
            errors.append(
                f"{item_prefix}: grade {grade} is inconsistent with status "
                f"source type {source_type}"
            )
        eligible = item["eligible_for_material_inference"]
        if grade in {"C", "D"} and eligible:
            errors.append(
                f"{item_prefix}: grade {grade} is discovery/background only "
                "and cannot support material inference"
            )
        if eligible:
            material_items += 1
            if status not in {"accepted", "rejected"}:
                errors.append(
                    f"{item_prefix}: material decision calibration requires "
                    "a verified accepted or rejected status"
                )
        similarity = item["similarity_assessment"]["state"]
        if purpose == "topic-near" and similarity == "not-assessed":
            errors.append(
                f"{item_prefix}: topic-near corpus requires an explicit "
                "similarity assessment"
            )
        if purpose == "topic-near" and eligible and similarity != "near":
            errors.append(
                f"{item_prefix}: a material topic-near item must be assessed "
                "as near across the declared axes"
            )
        if purpose == "venue-background" and similarity != "not-assessed":
            errors.append(
                f"{item_prefix}: venue-background corpus must not imply "
                "manuscript similarity"
            )

    saturation = value["saturation"]
    latest = saturation["latest_batch"]
    if latest["included_count"] > latest["screened_count"]:
        errors.append(
            f"{prefix}: latest batch included_count cannot exceed "
            "screened_count"
        )
    if saturation["status"] == "saturated":
        marginal = latest["marginal_additions"]
        if any(value != 0 for value in marginal.values()):
            errors.append(
                f"{prefix}: saturated status requires zero latest marginal "
                "additions across eligible papers and every topic dimension"
            )
        if material_items == 0:
            errors.append(
                f"{prefix}: a materially saturated corpus requires at least "
                "one grade A or B eligible item"
            )
    return sorted(set(errors))


def validate_venue_corpus_bundle(
    root: pathlib.Path,
    documents: list[tuple[str, dict]] | None = None,
) -> list[str]:
    """Validate published examples or caller-supplied corpus documents."""

    root = _normalise_root(root)
    if documents is None:
        examples = root / "venue-intelligence" / "examples"
        if not examples.is_dir() or examples.is_symlink():
            return ["venue-corpus: examples directory is missing or unsafe"]
        documents = []
        for path in sorted(examples.glob("*.json")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or not path.is_file():
                return [f"venue-corpus: unsafe example: {relative}"]
            try:
                value = _load_json_object(path, relative)
            except ValueError as exc:
                return [f"venue-corpus: {exc}"]
            documents.append((relative, value))
    errors: list[str] = []
    for label, value in documents:
        errors.extend(validate_venue_corpus_document(value, root, label))
    return sorted(set(errors))


def validate_venue_authority_registry(root: pathlib.Path) -> list[str]:
    """Validate the release-governed venue host allowlist itself."""

    root = _normalise_root(root)
    path = root / "references/venue-authorities.json"
    try:
        registry = _load_json_object(path, "venue authority registry")
    except ValueError as exc:
        return [f"venue-authority-registry: {exc}"]
    errors = [
        f"venue-authority-registry: {error}"
        for error in validate_json_schema_document(
            registry,
            root,
            "schemas/venue-authority-registry.schema.json",
            "venue-authority-registry",
        )
    ]
    venues = registry.get("venues", [])
    venue_names = [
        row.get("venue")
        for row in venues
        if isinstance(row, dict) and isinstance(row.get("venue"), str)
    ]
    if len(venue_names) != len(set(venue_names)):
        errors.append("venue-authority-registry: duplicate venue")
    profile_tuples: list[tuple[Any, ...]] = []
    for venue_row in venues:
        if not isinstance(venue_row, dict):
            continue
        venue = venue_row.get("venue")
        for profile_row in venue_row.get("profiles", []):
            if not isinstance(profile_row, dict):
                continue
            identity = (
                venue,
                profile_row.get("year"),
                profile_row.get("track"),
                profile_row.get("profile_id"),
                profile_row.get("profile_version"),
            )
            profile_tuples.append(identity)
            binding = {
                "status": "loaded",
                "profile_id": profile_row.get("profile_id"),
                "profile_version": profile_row.get("profile_version"),
                "venue": venue,
                "year": profile_row.get("year"),
                "track": profile_row.get("track"),
                "profile_locator": profile_row.get("profile_locator"),
                "profile_sha256": profile_row.get("profile_sha256"),
                "source_manifest_locator":
                    profile_row.get("source_manifest_locator"),
                "source_sha256": profile_row.get("source_sha256"),
                "blocked_reason": None,
            }
            target = {
                "venue": venue,
                "year": profile_row.get("year"),
                "track": profile_row.get("track"),
            }
            errors.extend(
                error.replace(
                    "run-manifest: ",
                    "venue-authority-registry: ",
                    1,
                )
                for error in _validate_venue_profile_binding(
                    target,
                    binding,
                    root,
                    "complete",
                )
            )
    if len(profile_tuples) != len(set(profile_tuples)):
        errors.append(
            "venue-authority-registry: duplicate exact venue profile tuple"
        )
    return errors


def _validate_schema_node(
    value: Any,
    schema: dict,
    root_schema: dict,
    path: str,
    ref_stack: tuple[str, ...] = (),
) -> list[str]:
    """Validate the Draft 2020-12 subset used by this bundle."""

    if not isinstance(schema, dict):
        return [f"schema: {path}: schema node must be an object"]
    errors: list[str] = []
    if "$ref" in schema:
        reference = schema["$ref"]
        if reference in ref_stack:
            chain = " -> ".join((*ref_stack, reference))
            return [f"schema: {path}: cyclic JSON Schema reference: {chain}"]
        try:
            target = _resolve_local_schema_ref(root_schema, reference)
        except ValueError as exc:
            return [f"schema: {path}: {exc}"]
        errors.extend(
            _validate_schema_node(
                value,
                target,
                root_schema,
                path,
                (*ref_stack, reference),
            )
        )
        schema = {
            keyword: constraint
            for keyword, constraint in schema.items()
            if keyword != "$ref"
        }
    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        expected_types = [expected_type]
    elif isinstance(expected_type, list):
        expected_types = [
            item for item in expected_type if isinstance(item, str)
        ]
    else:
        expected_types = []
    if expected_types and not any(
        _schema_type_matches(value, item) for item in expected_types
    ):
        rendered = "|".join(expected_types)
        return [f"schema: {path}: expected type {rendered}"]

    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(
            f"schema: {path}: value does not equal const {schema['const']!r}"
        )
    enum = schema.get("enum")
    if isinstance(enum, list) and not any(
        _json_equal(value, candidate) for candidate in enum
    ):
        errors.append(f"schema: {path}: value is not in enum")

    if isinstance(value, str):
        minimum_length = schema.get("minLength")
        if (
            _schema_type_matches(minimum_length, "integer")
            and len(value) < minimum_length
        ):
            errors.append(
                f"schema: {path}: string is shorter than minLength "
                f"{int(minimum_length)}"
            )
        maximum_length = schema.get("maxLength")
        if (
            _schema_type_matches(maximum_length, "integer")
            and len(value) > maximum_length
        ):
            errors.append(
                f"schema: {path}: string is longer than maxLength "
                f"{int(maximum_length)}"
            )
        pattern = schema.get("pattern")
        if isinstance(pattern, str):
            try:
                regex_value = value.replace("\ufeff", " ")
                matched = (
                    re.fullmatch(pattern[1:-1], regex_value)
                    if pattern.startswith("^") and pattern.endswith("$")
                    else re.search(pattern, regex_value)
                )
            except re.error as exc:
                errors.append(f"schema: {path}: invalid schema pattern: {exc}")
            else:
                if not matched:
                    errors.append(f"schema: {path}: string does not match pattern")
        if schema.get("format") == "date-time":
            if not _is_rfc3339_datetime(value):
                errors.append(
                    f"schema: {path}: value is not an RFC 3339 date-time"
                )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and value < minimum:
            errors.append(f"schema: {path}: value is below minimum {minimum}")

    if isinstance(value, list):
        minimum_items = schema.get("minItems")
        if (
            _schema_type_matches(minimum_items, "integer")
            and len(value) < minimum_items
        ):
            errors.append(
                f"schema: {path}: array has fewer than "
                f"{int(minimum_items)} items"
            )
        maximum_items = schema.get("maxItems")
        if (
            _schema_type_matches(maximum_items, "integer")
            and len(value) > maximum_items
        ):
            errors.append(
                f"schema: {path}: array has more than "
                f"{int(maximum_items)} items"
            )
        if schema.get("uniqueItems") is True:
            if any(
                _json_equal(value[left], value[right])
                for left in range(len(value))
                for right in range(left + 1, len(value))
            ):
                errors.append(f"schema: {path}: array items are not unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    _validate_schema_node(
                        item,
                        item_schema,
                        root_schema,
                        f"{path}[{index}]",
                        ref_stack,
                    )
                )

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for field in sorted(
                item for item in required if isinstance(item, str)
            ):
                if field not in value:
                    errors.append(
                        f"schema: {path}: missing required property {field}"
                    )
        properties = schema.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        for field, child_schema in properties.items():
            if field in value and isinstance(child_schema, dict):
                errors.extend(
                    _validate_schema_node(
                        value[field],
                        child_schema,
                        root_schema,
                        f"{path}.{field}",
                        ref_stack,
                    )
                )
        additional = schema.get("additionalProperties", True)
        unknown = sorted(set(value) - set(properties))
        if additional is False:
            for field in unknown:
                errors.append(
                    f"schema: {path}: unexpected property {field}"
                )
        elif isinstance(additional, dict):
            for field in unknown:
                errors.extend(
                    _validate_schema_node(
                        value[field],
                        additional,
                        root_schema,
                        f"{path}.{field}",
                        ref_stack,
                    )
                )

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for child in all_of:
            if isinstance(child, dict):
                errors.extend(
                    _validate_schema_node(
                        value, child, root_schema, path, ref_stack
                    )
                )
    one_of = schema.get("oneOf")
    if isinstance(one_of, list):
        matches = 0
        branch_errors: list[list[str]] = []
        for child in one_of:
            child_errors = (
                _validate_schema_node(
                    value, child, root_schema, path, ref_stack
                )
                if isinstance(child, dict)
                else [f"schema: {path}: oneOf branch is not a schema"]
            )
            branch_errors.append(child_errors)
            if not child_errors:
                matches += 1
        if matches != 1:
            errors.append(
                f"schema: {path}: expected exactly one oneOf branch, got {matches}"
            )
            if matches == 0 and branch_errors:
                type_matched_errors = [
                    child_errors
                    for child, child_errors in zip(one_of, branch_errors)
                    if isinstance(child, dict)
                    and _schema_branch_declared_type_matches(
                        value, child, root_schema
                    )
                ]
                errors.extend(
                    min(
                        type_matched_errors or branch_errors,
                        key=len,
                    )
                )
    condition = schema.get("if")
    consequence = schema.get("then")
    alternative = schema.get("else")
    if isinstance(condition, dict):
        condition_matches = not _validate_schema_node(
            value, condition, root_schema, path, ref_stack
        )
        if condition_matches and isinstance(consequence, dict):
            errors.extend(
                _validate_schema_node(
                    value, consequence, root_schema, path, ref_stack
                )
            )
        if not condition_matches and isinstance(alternative, dict):
            errors.extend(
                _validate_schema_node(
                    value, alternative, root_schema, path, ref_stack
                )
            )
    return errors


def _validate_json_value(value: Any, path: str = "$") -> list[str]:
    """Reject Python-only values before applying a JSON Schema."""

    if value is None or isinstance(value, (bool, int, str)):
        return []
    if isinstance(value, float):
        if not math.isfinite(value):
            return [f"schema: {path}: non-finite number is not valid JSON"]
        return []
    if isinstance(value, list):
        errors: list[str] = []
        for index, item in enumerate(value):
            errors.extend(_validate_json_value(item, f"{path}[{index}]"))
        return errors
    if isinstance(value, dict):
        errors = []
        for key, item in value.items():
            if not isinstance(key, str):
                errors.append(
                    f"schema: {path}: object property names must be strings"
                )
                continue
            errors.extend(_validate_json_value(item, f"{path}.{key}"))
        return errors
    return [f"schema: {path}: value is not representable in JSON"]


def validate_json_schema_document(
    value: Any,
    bundle_root: pathlib.Path,
    schema_locator: str,
    label: str,
) -> list[str]:
    value_errors = _validate_json_value(value)
    if value_errors:
        return sorted(set(value_errors))
    try:
        schema_path = _safe_bundle_file(bundle_root, schema_locator)
        schema = _load_json_object(schema_path, f"{label} schema")
    except ValueError as exc:
        return [f"schema: {label}: {exc}"]
    audit_errors = _audit_schema_node(schema)
    if audit_errors:
        return sorted(set(audit_errors))
    return sorted(
        set(_validate_schema_node(value, schema, schema, "$"))
    )


def _default_bundle_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


def _candidate_mapping_from_schema(root: pathlib.Path) -> dict[str, str]:
    schema_path = _safe_bundle_file(
        root, "schemas/adapter-manifest.schema.json"
    )
    schema = _load_json_object(schema_path, "adapter manifest schema")
    definitions = (
        schema.get("properties", {})
        .get("candidate_implementations", {})
        .get("properties", {})
    )
    if not isinstance(definitions, dict):
        raise ValueError("candidate mapping schema is missing")
    mapping: dict[str, str] = {}
    for candidate_id, definition in definitions.items():
        if not isinstance(definition, dict) or not isinstance(
            definition.get("const"), str
        ):
            raise ValueError(
                f"candidate mapping schema is invalid for {candidate_id}"
            )
        mapping[candidate_id] = definition["const"]
    if not mapping:
        raise ValueError("candidate mapping schema is empty")
    return mapping


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
    entries: list[dict[str, str]] = []
    for locator in sorted(active):
        if locator == "adapters/codex/adapter-manifest.json":
            raise ValueError("adapter manifest cannot hash itself")
        path = _safe_bundle_file(root, locator)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append({"locator": locator, "sha256": digest})
    return hashlib.sha256(_canonical_json_bytes(entries)).hexdigest()


def compatibility_payload_sha256(root: pathlib.Path) -> str:
    """Hash the full contract that makes an adapter evaluation transferable."""

    root = _normalise_root(root)
    relative_paths: set[str] = {"SKILL.md", "agents/openai.yaml"}
    for base, suffixes in (
        (root / "references", {".json", ".md"}),
        (root / "templates", {".json", ".md"}),
        (root / "scripts", {".py"}),
        (root / "schemas", {".json"}),
        (root / "adapters", {".md", ".toml"}),
        (root / "evals", {".json", ".py", ".md"}),
        (root / "venues", {".json"}),
        (root / "venue-intelligence", {".json", ".md"}),
    ):
        if base.name in {"venues", "venue-intelligence"} and not base.exists():
            continue
        if not base.is_dir() or base.is_symlink():
            raise ValueError(
                f"compatibility payload directory is missing or unsafe: "
                f"{base.relative_to(root).as_posix()}"
            )
        for path in base.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if (
                path.is_file()
                and not path.is_symlink()
                and path.suffix.lower() in suffixes
                and relative != "adapters/codex/adapter-manifest.json"
                and not relative.startswith("evals/results/")
            ):
                relative_paths.add(relative)
    entries: list[dict[str, str]] = []
    for locator in sorted(relative_paths):
        path = _safe_bundle_file(root, locator)
        entries.append(
            {
                "locator": locator,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return hashlib.sha256(_canonical_json_bytes(entries)).hexdigest()


def validate_adapter_manifest(data: dict, bundle_root: pathlib.Path) -> list[str]:
    structural_errors = validate_json_schema_document(
        data,
        bundle_root,
        "schemas/adapter-manifest.schema.json",
        "adapter-manifest",
    )
    if structural_errors:
        return structural_errors
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["adapter-manifest: must be an object"]
    if data.get("schema_version") != "1.0.0":
        errors.append("adapter-manifest: schema_version must be 1.0.0")
    try:
        candidate_mapping = _candidate_mapping_from_schema(bundle_root)
    except ValueError as exc:
        errors.append(f"adapter-manifest: canonical mapping unavailable: {exc}")
        candidate_mapping = {}
    mapping = data.get("candidate_implementations")
    if mapping != candidate_mapping:
        errors.append("adapter-manifest: candidate mapping is not canonical")
    selected = data.get("selected_candidate_id")
    selected_path = data.get("selected_lifecycle_implementation")
    promotion_locator = data.get("promotion_record_locator")
    promotion_sha256 = data.get("promotion_record_sha256")
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
        if (
            selected_path is not None
            or promotion_locator is not None
            or promotion_sha256 is not None
        ):
            errors.append(
                "adapter-manifest: null candidate requires null implementation "
                "and promotion record"
            )
        for candidate_path in candidate_mapping.values():
            if candidate_path in active:
                errors.append(
                    "adapter-manifest: inactive candidate appears in active allowlist"
                )
    elif selected not in candidate_mapping:
        errors.append("adapter-manifest: selected candidate ID is unknown")
    else:
        expected_path = candidate_mapping[selected]
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
        other_paths = set(candidate_mapping.values()) - {expected_path}
        if any(path in active for path in other_paths):
            errors.append(
                "adapter-manifest: unselected lifecycle implementation is active"
            )
        if not _is_canonical_relative_locator(promotion_locator):
            errors.append(
                "adapter-manifest: selected candidate requires canonical "
                "promotion locator"
            )
        if not _is_sha256(promotion_sha256):
            errors.append(
                "adapter-manifest: selected candidate requires promotion SHA-256"
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
    compatibility_digest = data.get("compatibility_payload_sha256")
    if not _is_sha256(compatibility_digest):
        errors.append(
            "adapter-manifest: compatibility_payload_sha256 must be SHA-256"
        )
    else:
        try:
            actual_compatibility = compatibility_payload_sha256(root)
        except ValueError as exc:
            errors.append(
                f"adapter-manifest: cannot hash compatibility payload: {exc}"
            )
        else:
            if actual_compatibility != compatibility_digest:
                errors.append(
                    "adapter-manifest: compatibility_payload_sha256 does not "
                    "match the published execution contract"
                )
    if (
        selected in candidate_mapping
        and _is_canonical_relative_locator(promotion_locator)
        and _is_sha256(promotion_sha256)
    ):
        promotion, raw, load_errors = _load_adapter_promotion_record(
            root, promotion_locator
        )
        errors.extend(
            f"adapter-manifest: promotion record invalid: {error}"
            for error in load_errors
        )
        if raw is not None and hashlib.sha256(raw).hexdigest() != promotion_sha256:
            errors.append("adapter-manifest: promotion record hash mismatch")
        if isinstance(promotion, dict):
            errors.extend(
                f"adapter-manifest: promotion record invalid: {error}"
                for error in validate_adapter_promotion(
                    promotion,
                    root,
                    _skip_manifest_binding=True,
                )
            )
            expected_promotion = {
                "candidate_id": selected,
                "adapter_sha256": recorded_digest,
                "compatibility_payload_sha256": compatibility_digest,
                "result": "pass",
                "promotion_decision": "selected",
            }
            for field, expected in expected_promotion.items():
                if promotion.get(field) != expected:
                    if field == "result":
                        errors.append(
                            "adapter-manifest: promotion result does not bind "
                            "selected release"
                        )
                    elif field == "promotion_decision":
                        errors.append(
                            "adapter-manifest: promotion decision does not bind "
                            "selected release"
                        )
                    else:
                        errors.append(
                            "adapter-manifest: promotion record "
                            f"{field} does not bind selected release"
                        )
    return sorted(set(errors))


def validate_active_adapter_manifest(root: pathlib.Path) -> list[str]:
    try:
        manifest = load_adapter_manifest(root)
    except ValueError as exc:
        return [f"adapter-manifest: {exc}"]
    return validate_adapter_manifest(manifest, root)


_SEMANTIC_REVIEW_DIMENSIONS = {
    "compaction_recovery",
    "late_result_handling",
    "duplicate_dispatch",
    "evidence_retention",
    "complexity",
    "review_quality",
}


def _normalised_identity(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return unicodedata.normalize("NFKC", value).strip().casefold()


_DEFAULT_IGNORABLE_RANGES = (
    (0x00AD, 0x00AD),
    (0x034F, 0x034F),
    (0x061C, 0x061C),
    (0x115F, 0x1160),
    (0x17B4, 0x17B5),
    (0x180B, 0x180E),
    (0x200B, 0x200F),
    (0x202A, 0x202E),
    (0x2060, 0x206F),
    (0x3164, 0x3164),
    (0xFE00, 0xFE0F),
    (0xFEFF, 0xFEFF),
    (0xFFA0, 0xFFA0),
    (0xFFF0, 0xFFF8),
    (0x1BCA0, 0x1BCA3),
    (0x1D173, 0x1D17A),
    (0xE0000, 0xE0FFF),
)


def _is_default_ignorable(character: str) -> bool:
    codepoint = ord(character)
    return any(
        start <= codepoint <= end
        for start, end in _DEFAULT_IGNORABLE_RANGES
    )


def _normalised_semantic_scan_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalised = unicodedata.normalize(
        "NFKC",
        unicodedata.normalize("NFKC", value).casefold(),
    )
    prepared = "".join(
        ""
        if _is_default_ignorable(character)
        else " "
        if (
            character.isspace()
            or unicodedata.category(character) in {"Cc", "Cs"}
        )
        else character
        for character in normalised
    )
    return " ".join(prepared.split())


def _semantic_scan_variants(value: Any) -> tuple[str, ...]:
    return (_normalised_semantic_scan_text(value),)


def _policy_arms(value: Any) -> tuple[str, ...]:
    normalised = _normalised_semantic_scan_text(value)
    if not normalised:
        return ()
    connector_split = re.sub(
        r"\b(?:but|however|yet|nevertheless)\b|(?:但是|然而|不过)",
        "\n",
        normalised,
    )
    return tuple(
        arm.strip()
        for arm in re.split(r"[.;!?。；！？]+", connector_split)
        if arm.strip()
    )


def _validate_requested_execution_identity(
    value: Any,
    prefix: str,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}: execution identity must be an object"]
    errors: list[str] = []
    if (
        value.get("requested_model") != "gpt-5.6-sol"
        or value.get("requested_mode") != "ultra"
        or value.get("configuration_state") != "requested_and_recorded"
    ):
        errors.append(
            f"{prefix}: requested Sol Ultra configuration is not recorded"
        )
    telemetry = value.get("effective_telemetry")
    resolved_model = value.get("resolved_model")
    resolved_mode = value.get("resolved_mode")
    if telemetry == "not_surfaced":
        if resolved_model is not None or resolved_mode is not None:
            errors.append(
                f"{prefix}: absent host telemetry requires null resolved "
                "model and mode"
            )
    elif telemetry == "surfaced_unverified":
        if not (
            _is_nonblank_string(resolved_model)
            and _is_nonblank_string(resolved_mode)
        ):
            errors.append(
                f"{prefix}: surfaced unverified telemetry requires recorded "
                "resolved values"
            )
        elif (
            _normalised_identity(resolved_model) != "gpt-5.6-sol"
            or _normalised_identity(resolved_mode) != "ultra"
        ):
            errors.append(
                f"{prefix}: surfaced telemetry conflicts with the requested "
                "Sol Ultra configuration"
            )
    else:
        errors.append(f"{prefix}: effective telemetry state is invalid")
    return errors


def _contains_non_execution_claim(value: Any) -> bool:
    for text in _string_leaves(value):
        for arm in _policy_arms(text):
            prepared = re.sub(r"[_-]+", " ", arm)
            safe_nonexecution = re.search(
                r"\bexecution\s+(?:was\s+)?not\s+(?:skipped|omitted)\b"
                r"|\bnot\s+(?:a\s+)?(?:dry\s+run|mock\s+runner|"
                r"placeholder)\b"
                r"|\bno\s+placeholder\s+(?:remains?|exists?)\b"
                r"|(?:不是|并非)(?:模拟运行器|占位符|试运行)",
                prepared,
            )
            nonexecution = re.search(
                r"\bno\s+execution\s+took\s+place\b"
                r"|\b(?:candidate|adapter|runner|execution|run)\s+"
                r"(?:was\s+)?(?:not\s+executed|not\s+run|"
                r"skipped|omitted)\b"
                r"|\b(?:did\s+not|never)\s+(?:actually\s+)?execute\b"
                r"|\bexecution\s+(?:was\s+)?(?:skipped|omitted|"
                r"not\s+performed)\b"
                r"|\b(?:this|it|the\s+runner)\s+(?:was|is)\s+"
                r"(?:a\s+)?(?:mock|placeholder|dry\s+run)\b"
                r"|\b(?:mock|synthetic(?:\s+test)?)\s+runner\b"
                r"|(?:未执行|没有执行|跳过执行|执行被跳过|模拟运行器)",
                prepared,
            )
            if nonexecution and not safe_nonexecution:
                return True
            safe_oracle = re.search(
                r"\b(?:did\s+not|never)\s+"
                r"(?:read|use|consult|open|copy)\b.{0,35}"
                r"\b(?:oracle|answer\s+key)\b"
                r"|\bno\s+(?:oracle|answer\s+key)\s+values?\s+"
                r"(?:were\s+)?(?:copied|used|read)\b"
                r"|\b(?:oracle|answer\s+key)\s+(?:was\s+)?not\s+"
                r"(?:read|used|consulted|opened|copied)\b",
                prepared,
            )
            oracle = re.search(
                r"\b(?:copied|derived)\s+(?:directly\s+)?from\s+"
                r"(?:the\s+)?(?:oracle|answer\s+key)\b"
                r"|\b(?:oracle|answer\s+key)\s+values?\s+"
                r"(?:were\s+)?copied\b"
                r"|\b(?:read|used|consulted|opened)\s+(?:the\s+)?"
                r"(?:oracle|answer\s+key)\b"
                r"|\b(?:oracle|answer\s+key)\s+(?:was\s+)?"
                r"(?:read|used|consulted|opened)\b"
                r"|(?:从|读取|使用|复制).{0,12}(?:oracle|答案|标准答案)"
                r".{0,12}(?:复制|读取|使用)?",
                prepared,
            )
            if oracle and not safe_oracle:
                return True
    return False


def _load_adapter_evaluation_authority(
    root: pathlib.Path,
) -> tuple[dict | None, list[str]]:
    locator = "references/adapter-evaluation-authority.json"
    try:
        path = _safe_bundle_file(root, locator)
        authority = _load_json_object(
            path, "adapter evaluation authority"
        )
    except ValueError as exc:
        return None, [f"adapter-promotion: evaluation authority: {exc}"]
    errors = validate_json_schema_document(
        authority,
        root,
        "schemas/adapter-evaluation-authority.schema.json",
        "adapter-evaluation-authority",
    )
    if not errors:
        errors.extend(
            _validate_release_governed_scorer(
                authority,
                root,
                "adapter-promotion: evaluation authority",
            )
        )
    return authority, errors


def _validate_release_governed_scorer(
    authority: dict,
    root: pathlib.Path,
    prefix: str,
) -> list[str]:
    """Bind deterministic scoring to the implementation approved by release."""

    scorer = authority.get("scorer")
    if not isinstance(scorer, dict):
        return [f"{prefix}: release-governed scorer is missing"]
    try:
        scorer_path = _safe_bundle_file(root, scorer.get("locator"))
        actual_sha256 = hashlib.sha256(scorer_path.read_bytes()).hexdigest()
    except (ValueError, OSError) as exc:
        return [
            f"{prefix}: release-governed scorer is unavailable: {exc}"
        ]
    if actual_sha256 != scorer.get("sha256"):
        return [
            f"{prefix}: release-governed scorer SHA-256 mismatch"
        ]
    return []


def validate_adapter_evaluation_authority(root: pathlib.Path) -> list[str]:
    """Validate the release fixture authority even before adapter promotion."""

    authority, errors = _load_adapter_evaluation_authority(
        _normalise_root(root)
    )
    prefix = "adapter-evaluation-authority"
    normalised = [
        error.replace("adapter-promotion: evaluation authority", prefix, 1)
        for error in errors
    ]
    if not isinstance(authority, dict):
        return sorted(set(normalised))
    fixture_ids = [
        row.get("fixture_id")
        for row in authority.get("fixtures", [])
        if isinstance(row, dict)
    ]
    if len(fixture_ids) != len(set(fixture_ids)):
        normalised.append(f"{prefix}: duplicate fixture_id")
    manifest, _, manifest_errors = _load_bound_json_receipt(
        _normalise_root(root),
        authority.get("fixture_manifest_locator"),
        authority.get("fixture_manifest_sha256"),
        prefix,
    )
    normalised.extend(manifest_errors)
    if isinstance(manifest, dict):
        normalised.extend(
            validate_json_schema_document(
                manifest,
                _normalise_root(root),
                "schemas/adapter-evaluation-fixture-manifest.schema.json",
                prefix,
            )
        )
        normalised.extend(
            _validate_fixture_authority(
                manifest,
                authority,
                _normalise_root(root),
            )
        )
    return sorted(set(normalised))


def _validate_fixture_authority(
    fixture_manifest: dict,
    authority: dict,
    root: pathlib.Path,
) -> list[str]:
    prefix = "adapter-promotion: canonical fixture authority"
    errors: list[str] = []
    expected_rows = authority.get("fixtures", [])
    actual_rows = fixture_manifest.get("fixtures", [])
    if fixture_manifest.get("fixture_set") != authority.get("fixture_set"):
        errors.append(f"{prefix}: fixture_set mismatch")
    manifest_locator = authority.get("fixture_manifest_locator")
    try:
        manifest_path = _safe_bundle_file(root, manifest_locator)
        manifest_sha256 = hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest()
    except (ValueError, OSError) as exc:
        errors.append(f"{prefix}: release manifest is unavailable: {exc}")
    else:
        if manifest_sha256 != authority.get("fixture_manifest_sha256"):
            errors.append(f"{prefix}: release manifest SHA-256 mismatch")
    expected_ids = [
        row.get("fixture_id")
        for row in expected_rows
        if isinstance(row, dict)
    ]
    actual_ids = [
        row.get("fixture_id")
        for row in actual_rows
        if isinstance(row, dict)
    ]
    if actual_ids != expected_ids:
        errors.append(
            f"{prefix}: fixture IDs/order differ from release authority"
        )
    expected_by_id = {
        row.get("fixture_id"): row
        for row in expected_rows
        if isinstance(row, dict)
    }
    for row in actual_rows:
        if not isinstance(row, dict):
            continue
        fixture_id = row.get("fixture_id")
        expected = expected_by_id.get(fixture_id)
        if not isinstance(expected, dict):
            continue
        expected_input = (
            f"evals/adapter-fixtures/{fixture_id}/input.json"
        )
        expected_oracle = (
            f"evals/adapter-fixtures/{fixture_id}/oracle.json"
        )
        if (
            row.get("dimension") != expected.get("dimension")
            or row.get("input_locator") != expected_input
            or row.get("oracle_locator") != expected_oracle
            or row.get("input_sha256") != expected.get("input_sha256")
            or row.get("oracle_sha256") != expected.get("oracle_sha256")
        ):
            errors.append(
                f"{prefix}: fixture namespace or dimension mismatch: "
                f"{fixture_id}"
            )
        input_record, _, input_errors = _load_bound_json_receipt(
            root,
            row.get("input_locator"),
            row.get("input_sha256"),
            f"{prefix} input {fixture_id}",
        )
        oracle_record, _, oracle_errors = _load_bound_json_receipt(
            root,
            row.get("oracle_locator"),
            row.get("oracle_sha256"),
            f"{prefix} oracle {fixture_id}",
        )
        errors.extend(input_errors)
        errors.extend(oracle_errors)
        assertion_ids = expected.get("assertion_ids")
        if (
            not isinstance(input_record, dict)
            or input_record.get("assertion_ids") != assertion_ids
        ):
            errors.append(
                f"{prefix}: input assertion inventory mismatch: {fixture_id}"
            )
        if isinstance(input_record, dict):
            payload = input_record.get("payload")
            questions = (
                payload.get("evaluation_questions")
                if isinstance(payload, dict)
                else None
            )
            question_ids = [
                item.get("assertion_id")
                for item in questions
                if isinstance(item, dict)
            ] if isinstance(questions, list) else []
            if (
                not isinstance(payload, dict)
                or "required_behavior" in payload
                or question_ids != assertion_ids
                or not all(
                    isinstance(item, dict)
                    and isinstance(item.get("question"), str)
                    and item["question"].strip()
                    for item in questions or []
                )
            ):
                errors.append(
                    f"{prefix}: input must expose neutral aligned questions "
                    f"without required behavior: {fixture_id}"
                )
            scenario = input_record.get("scenario")
            if isinstance(scenario, str) and re.search(
                r"\b(?:must\s+(?:retain|avoid|not)|required\s+behavior|"
                r"expected\s+result)\b",
                scenario,
                re.I,
            ):
                errors.append(
                    f"{prefix}: input scenario discloses an oracle direction: "
                    f"{fixture_id}"
                )
        oracle_ids = [
            item.get("assertion_id")
            for item in (
                oracle_record.get("assertions", [])
                if isinstance(oracle_record, dict)
                else []
            )
            if isinstance(item, dict)
        ]
        if oracle_ids != assertion_ids:
            errors.append(
                f"{prefix}: oracle assertion inventory mismatch: {fixture_id}"
            )
    return errors


def _validate_candidate_evaluation(
    row: dict,
    fixture_manifest: dict,
    promotion: dict,
    schema_root: pathlib.Path,
    candidate_mapping: dict[str, str],
    evaluation_authority: dict | None,
) -> tuple[list[str], dict[str, Any] | None]:
    candidate_id = row.get("candidate_id")
    prefix = f"adapter-promotion: candidate {candidate_id}"
    errors: list[str] = []
    candidate_path = candidate_mapping.get(candidate_id)
    if not isinstance(candidate_path, str):
        return [f"{prefix}: candidate ID is unknown"], None
    try:
        actual_candidate_sha = hashlib.sha256(
            _safe_bundle_file(schema_root, candidate_path).read_bytes()
        ).hexdigest()
    except (ValueError, OSError) as exc:
        return [f"{prefix}: implementation is unavailable: {exc}"], None
    if row.get("candidate_implementation_sha256") != actual_candidate_sha:
        errors.append(f"{prefix}: implementation SHA-256 is stale")

    report, _, report_errors = _load_bound_json_receipt(
        schema_root,
        row.get("evaluation_report_locator"),
        row.get("evaluation_report_sha256"),
        f"{prefix} evaluation report",
    )
    receipt, _, receipt_errors = _load_bound_json_receipt(
        schema_root,
        row.get("execution_receipt_locator"),
        row.get("execution_receipt_sha256"),
        f"{prefix} execution receipt",
    )
    errors.extend(report_errors)
    errors.extend(receipt_errors)
    report_schema_errors: list[str] = []
    receipt_schema_errors: list[str] = []
    if isinstance(report, dict):
        report_schema_errors = validate_json_schema_document(
            report,
            schema_root,
            "schemas/adapter-evaluation-report.schema.json",
            f"{prefix} evaluation report",
        )
        errors.extend(report_schema_errors)
    if isinstance(receipt, dict):
        receipt_schema_errors = validate_json_schema_document(
            receipt,
            schema_root,
            "schemas/adapter-evaluation-execution-receipt.schema.json",
            f"{prefix} execution receipt",
        )
        errors.extend(receipt_schema_errors)
    if (
        not isinstance(report, dict)
        or report_schema_errors
        or not isinstance(receipt, dict)
        or receipt_schema_errors
    ):
        return errors, None
    if _contains_non_execution_claim(report) or _contains_non_execution_claim(
        receipt
    ):
        errors.append(
            f"{prefix}: authoritative evaluation records contradict actual "
            "execution"
        )

    expected_common = {
        "candidate_id": candidate_id,
        "candidate_implementation_sha256": actual_candidate_sha,
        "adapter_sha256": promotion.get("adapter_sha256"),
        "compatibility_payload_sha256":
            promotion.get("compatibility_payload_sha256"),
        "fixture_set": fixture_manifest.get("fixture_set"),
    }
    for artifact_name, artifact in (
        ("evaluation report", report),
        ("execution receipt", receipt),
    ):
        for field, expected in expected_common.items():
            if artifact.get(field) != expected:
                errors.append(
                    f"{prefix}: {artifact_name} {field} mismatch"
                )
        runner = artifact.get("runner")
        if (
            not _is_nonblank_string(runner)
            or _normalised_identity(runner) != runner
            or _contains_non_execution_claim(runner)
        ):
            errors.append(
                f"{prefix}: {artifact_name} runner cannot claim skipped, "
                "placeholder, dry-run, or synthetic-test execution"
            )
    for field in (
        "runner",
        "runner_locator",
        "runner_sha256",
        "runner_version",
    ):
        if report.get(field) != receipt.get(field):
            errors.append(
                f"{prefix}: report and execution receipt {field} mismatch"
            )
    release_scorer = (
        evaluation_authority.get("scorer")
        if isinstance(evaluation_authority, dict)
        else None
    )
    if not isinstance(release_scorer, dict):
        errors.append(f"{prefix}: release-governed scorer is unavailable")
    else:
        expected_runner = {
            "runner": release_scorer.get("scorer_id"),
            "runner_locator": release_scorer.get("locator"),
            "runner_sha256": release_scorer.get("sha256"),
            "runner_version": release_scorer.get("version"),
        }
        for artifact_name, artifact in (
            ("evaluation report", report),
            ("execution receipt", receipt),
        ):
            for field, expected in expected_runner.items():
                if artifact.get(field) != expected:
                    errors.append(
                        f"{prefix}: {artifact_name} {field} differs from "
                        "the release-governed scorer"
                    )
    try:
        runner_path = _safe_bundle_file(
            schema_root, receipt.get("runner_locator")
        )
        actual_runner_sha = hashlib.sha256(
            runner_path.read_bytes()
        ).hexdigest()
    except (ValueError, OSError) as exc:
        errors.append(f"{prefix}: runner implementation is unavailable: {exc}")
    else:
        if actual_runner_sha != receipt.get("runner_sha256"):
            errors.append(f"{prefix}: runner implementation SHA-256 is stale")
    executor = receipt.get("executor", {})
    errors.extend(
        _validate_requested_execution_identity(executor, f"{prefix}: executor")
    )
    executor_id = (
        executor.get("executor_id") if isinstance(executor, dict) else None
    )
    if (
        not _is_nonblank_string(executor_id)
        or _normalised_identity(executor_id) != executor_id
        or _contains_non_execution_claim(executor_id)
    ):
        errors.append(f"{prefix}: executor identifier is invalid")
        executor_id = None
    execution_id = receipt.get("execution_id")
    if (
        not _is_nonblank_string(execution_id)
        or _normalised_identity(execution_id) != execution_id
    ):
        errors.append(f"{prefix}: execution identifier is invalid")
        execution_id = None
    if receipt.get("status") != "completed":
        errors.append(f"{prefix}: execution receipt is not completed")
    if (
        receipt.get("execution_performed") is not True
        or receipt.get("raw_output_produced") is not True
        or receipt.get("oracle_access_record")
        != "declared_withheld_until_output_frozen"
        or receipt.get("oracle_boundary_verification")
        != "dispatch_snapshot_excludes_oracle"
    ):
        errors.append(
            f"{prefix}: execution truth or oracle-withholding state is invalid"
        )
    expected_fixture_binding = {
        "fixture_manifest_locator":
            promotion.get("evaluation_summary", {}).get(
                "fixture_manifest_locator"
            ),
        "fixture_manifest_sha256":
            promotion.get("evaluation_summary", {}).get(
                "fixture_manifest_sha256"
            ),
        "evaluation_report_locator": row.get("evaluation_report_locator"),
        "evaluation_report_sha256": row.get("evaluation_report_sha256"),
    }
    for field, expected in expected_fixture_binding.items():
        if receipt.get(field) != expected:
            errors.append(f"{prefix}: execution receipt {field} mismatch")

    fixtures = fixture_manifest.get("fixtures", [])
    expected_dispatch_snapshot = hashlib.sha256(
        _canonical_json_bytes(
            {
                "schema_version": "1.0.0",
                "candidate_id": candidate_id,
                "candidate_implementation_sha256": actual_candidate_sha,
                "inputs": [
                    {
                        "fixture_id": fixture.get("fixture_id"),
                        "input_locator": fixture.get("input_locator"),
                        "input_sha256": fixture.get("input_sha256"),
                    }
                    for fixture in fixtures
                    if isinstance(fixture, dict)
                ],
            }
        )
    ).hexdigest()
    if (
        receipt.get("dispatch_input_snapshot_sha256")
        != expected_dispatch_snapshot
    ):
        errors.append(
            f"{prefix}: dispatch input snapshot is not the oracle-free "
            "candidate/input set"
        )
    fixture_by_id: dict[str, dict] = {}
    oracle_by_id: dict[str, dict] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            continue
        fixture_id = fixture.get("fixture_id")
        if fixture_id in fixture_by_id:
            errors.append(f"{prefix}: duplicate fixture ID: {fixture_id}")
        fixture_by_id[fixture_id] = fixture
        input_data, _, input_errors = _load_bound_json_receipt(
            schema_root,
            fixture.get("input_locator"),
            fixture.get("input_sha256"),
            f"{prefix} fixture {fixture_id} input",
        )
        oracle_data, _, oracle_errors = _load_bound_json_receipt(
            schema_root,
            fixture.get("oracle_locator"),
            fixture.get("oracle_sha256"),
            f"{prefix} fixture {fixture_id} oracle",
        )
        errors.extend(input_errors)
        errors.extend(oracle_errors)
        if isinstance(input_data, dict):
            errors.extend(
                validate_json_schema_document(
                    input_data,
                    schema_root,
                    "schemas/adapter-evaluation-input.schema.json",
                    f"{prefix} input {fixture_id}",
                )
            )
        if isinstance(oracle_data, dict):
            oracle_schema_errors = validate_json_schema_document(
                oracle_data,
                schema_root,
                "schemas/adapter-evaluation-oracle.schema.json",
                f"{prefix} oracle {fixture_id}",
            )
            errors.extend(oracle_schema_errors)
            if not oracle_schema_errors:
                oracle_by_id[fixture_id] = oracle_data
        if isinstance(input_data, dict) and isinstance(oracle_data, dict):
            input_ids = input_data.get("assertion_ids", [])
            oracle_ids = [
                item.get("assertion_id")
                for item in oracle_data.get("assertions", [])
                if isinstance(item, dict)
            ]
            if (
                input_data.get("fixture_id") != fixture_id
                or oracle_data.get("fixture_id") != fixture_id
                or input_data.get("dimension") != fixture.get("dimension")
                or oracle_data.get("dimension") != fixture.get("dimension")
                or input_ids != oracle_ids
                or len(oracle_ids) != len(set(oracle_ids))
            ):
                errors.append(
                    f"{prefix}: fixture input/oracle binding is inconsistent: "
                    f"{fixture_id}"
                )
    if {
        fixture.get("dimension")
        for fixture in fixtures
        if isinstance(fixture, dict)
    } != {"quality", "lifecycle"}:
        errors.append(
            f"{prefix}: fixture manifest must cover quality and lifecycle"
        )

    cases = report.get("cases", [])
    case_by_id: dict[str, dict] = {}
    derived_results: dict[str, str] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        fixture_id = case.get("fixture_id")
        if fixture_id in case_by_id:
            errors.append(f"{prefix}: duplicate evaluation case: {fixture_id}")
        case_by_id[fixture_id] = case
        fixture = fixture_by_id.get(fixture_id)
        output, _, output_errors = _load_bound_json_receipt(
            schema_root,
            case.get("output_locator"),
            case.get("output_sha256"),
            f"{prefix} output {fixture_id}",
        )
        errors.extend(output_errors)
        output_schema_errors: list[str] = []
        if isinstance(output, dict):
            output_schema_errors = validate_json_schema_document(
                output,
                schema_root,
                "schemas/adapter-evaluation-output.schema.json",
                f"{prefix} output {fixture_id}",
            )
            errors.extend(output_schema_errors)
            if _contains_non_execution_claim(output):
                errors.append(
                    f"{prefix}: candidate output contradicts actual execution: "
                    f"{fixture_id}"
                )
        derived = "fail"
        oracle = oracle_by_id.get(fixture_id)
        if (
            isinstance(fixture, dict)
            and isinstance(output, dict)
            and not output_schema_errors
            and isinstance(oracle, dict)
        ):
            if (
                case.get("dimension") != fixture.get("dimension")
                or output.get("fixture_id") != fixture_id
                or output.get("dimension") != fixture.get("dimension")
                or output.get("candidate_id") != candidate_id
            ):
                errors.append(
                    f"{prefix}: evaluation output binding mismatch: {fixture_id}"
                )
            expected_by_id = {
                item.get("assertion_id"): item.get("expected")
                for item in oracle.get("assertions", [])
                if isinstance(item, dict)
            }
            observations = output.get("observations", [])
            derived, scoring_errors = score_assertions(
                expected_by_id,
                observations,
            )
            errors.extend(
                f"{prefix}: {error}: {fixture_id}"
                for error in scoring_errors
            )
        derived_results[fixture_id] = derived
        if case.get("result") != derived:
            errors.append(
                f"{prefix}: reported case result disagrees with oracle-derived "
                f"result: {fixture_id}"
            )
    if set(case_by_id) != set(fixture_by_id):
        errors.append(
            f"{prefix}: evaluation cases do not exactly cover fixtures"
        )
    for dimension, field in (
        ("quality", "quality_result"),
        ("lifecycle", "lifecycle_result"),
    ):
        dimension_cases = [
            case
            for case in cases
            if isinstance(case, dict)
            and case.get("dimension") == dimension
        ]
        derived = (
            "pass"
            if dimension_cases
            and all(
                derived_results.get(case.get("fixture_id")) == "pass"
                for case in dimension_cases
            )
            else "fail"
        )
        if report.get(field) != derived or row.get(field) != derived:
            errors.append(
                f"{prefix}: {field} is not derived from evaluation cases"
            )

    receipt_cases_by_id = {
        case.get("fixture_id"): case
        for case in receipt.get("cases", [])
        if isinstance(case, dict)
    }
    expected_execution_cases = [
        {
            "fixture_id": case.get("fixture_id"),
            "input_locator": fixture_by_id.get(
                case.get("fixture_id"), {}
            ).get("input_locator"),
            "input_sha256": fixture_by_id.get(
                case.get("fixture_id"), {}
            ).get("input_sha256"),
            "output_locator": case.get("output_locator"),
            "output_sha256": case.get("output_sha256"),
            "output_frozen_at": receipt_cases_by_id.get(
                case.get("fixture_id"), {}
            ).get("output_frozen_at"),
            "result": case.get("result"),
        }
        for case in cases
        if isinstance(case, dict)
    ]
    if receipt.get("cases") != expected_execution_cases:
        errors.append(
            f"{prefix}: execution receipt cases do not exactly bind report, "
            "fixtures, and outputs"
        )
    executed_at = _parse_rfc3339_datetime(receipt.get("executed_at"))
    evaluated_at = _parse_rfc3339_datetime(report.get("evaluated_at"))
    output_times = [
        _parse_rfc3339_datetime(case.get("output_frozen_at"))
        for case in receipt.get("cases", [])
        if isinstance(case, dict)
    ]
    if (
        executed_at is None
        or evaluated_at is None
        or any(item is None for item in output_times)
        or any(item > executed_at for item in output_times if item is not None)
        or executed_at > evaluated_at
    ):
        errors.append(
            f"{prefix}: output, execution, and scoring chronology is invalid"
        )
    return errors, {
        "executor_id": executor_id,
        "execution_id": execution_id,
        "executed_at": executed_at,
        "evaluated_at": evaluated_at,
    }


def _validate_adapter_semantic_review(
    summary: dict,
    promotion: dict,
    fixture_manifest: dict,
    candidate_rows: list[dict],
    executor_ids: list[str],
    evaluation_times: list[datetime],
    schema_root: pathlib.Path,
) -> list[str]:
    prefix = "adapter-promotion: semantic review"
    errors: list[str] = []
    receipt, _, receipt_errors = _load_bound_json_receipt(
        schema_root,
        summary.get("semantic_review_locator"),
        summary.get("semantic_review_sha256"),
        prefix,
    )
    errors.extend(receipt_errors)
    if not isinstance(receipt, dict):
        return errors
    structural_errors = validate_json_schema_document(
        receipt,
        schema_root,
        "schemas/adapter-semantic-review-receipt.schema.json",
        prefix,
    )
    errors.extend(structural_errors)
    if structural_errors:
        return errors
    if _contains_non_execution_claim(receipt):
        errors.append(
            f"{prefix}: semantic record contradicts independent executed review"
        )
    if receipt.get("independent_review_performed") is not True:
        errors.append(
            f"{prefix}: independent review was not performed"
        )
    expected_candidate_rows = [
        {
            key: row.get(key)
            for key in (
                "candidate_id",
                "candidate_implementation_sha256",
                "execution_receipt_locator",
                "execution_receipt_sha256",
                "evaluation_report_locator",
                "evaluation_report_sha256",
            )
        }
        for row in candidate_rows
    ]
    for field, expected in (
        ("fixture_set", fixture_manifest.get("fixture_set")),
        (
            "fixture_manifest_locator",
            summary.get("fixture_manifest_locator"),
        ),
        (
            "fixture_manifest_sha256",
            summary.get("fixture_manifest_sha256"),
        ),
        ("candidate_evaluations", expected_candidate_rows),
        ("executor_ids", executor_ids),
    ):
        if receipt.get(field) != expected:
            errors.append(f"{prefix}: {field} does not bind evaluation inputs")
    reviewer = receipt.get("reviewer", {})
    errors.extend(
        _validate_requested_execution_identity(
            reviewer, f"{prefix}: reviewer"
        )
    )
    reviewer_id = (
        reviewer.get("reviewer_id") if isinstance(reviewer, dict) else None
    )
    normalised_executors = {
        _normalised_identity(item) for item in executor_ids
    }
    if (
        _normalised_identity(reviewer_id) in normalised_executors
        or _normalised_identity(reviewer_id) != reviewer_id
        or _contains_non_execution_claim(reviewer_id)
    ):
        errors.append(
            f"{prefix}: reviewer must be distinct from both executors"
        )
    candidate_ids = [row.get("candidate_id") for row in candidate_rows]
    dimensions = receipt.get("dimensions", [])
    dimension_ids = [
        row.get("dimension") for row in dimensions if isinstance(row, dict)
    ]
    if (
        len(dimension_ids) != len(set(dimension_ids))
        or set(dimension_ids) != _SEMANTIC_REVIEW_DIMENSIONS
    ):
        errors.append(
            f"{prefix}: dimensions must exactly cover the six comparison axes"
        )
    preferred_counts = {candidate_id: 0 for candidate_id in candidate_ids}
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        assessments = dimension.get("assessments", [])
        assessment_ids = [
            row.get("candidate_id")
            for row in assessments
            if isinstance(row, dict)
        ]
        if (
            len(assessment_ids) != len(set(assessment_ids))
            or assessment_ids != candidate_ids
        ):
            errors.append(
                f"{prefix}: every dimension must assess both candidates in "
                "the bound order"
            )
        preferred = dimension.get("preferred_candidate_id")
        rating_by_id = {
            row.get("candidate_id"): row.get("rating")
            for row in assessments
            if isinstance(row, dict)
        }
        rated_preferred = [
            candidate_id
            for candidate_id, rating in rating_by_id.items()
            if rating == "preferred"
        ]
        if preferred is None:
            if rated_preferred or len(set(rating_by_id.values())) != 1:
                errors.append(
                    f"{prefix}: null dimension preference must be a genuine tie"
                )
        elif (
            preferred not in candidate_ids
            or rated_preferred != [preferred]
        ):
            errors.append(
                f"{prefix}: dimension ratings do not derive the declared "
                "preference"
            )
        else:
            preferred_counts[preferred] += 1
    ordered = sorted(
        preferred_counts,
        key=lambda item: preferred_counts[item],
        reverse=True,
    )
    derived_selected = (
        ordered[0]
        if len(ordered) == 2
        and preferred_counts[ordered[0]] > preferred_counts[ordered[1]]
        else None
    )
    if receipt.get("selection_rule") != "strict_preference_majority":
        errors.append(f"{prefix}: selection rule is invalid")
    if derived_selected is None:
        expected_verdict = "no_selection"
    else:
        expected_verdict = "selected"
    if (
        receipt.get("verdict") != expected_verdict
        or receipt.get("selected_candidate_id") != derived_selected
        or (
            promotion.get("promotion_decision") == "selected"
            and derived_selected != promotion.get("candidate_id")
        )
    ):
        errors.append(
            f"{prefix}: verdict is not derived from the complete comparison"
        )
    reviewed_at = _parse_rfc3339_datetime(receipt.get("reviewed_at"))
    promoted_at = _parse_rfc3339_datetime(promotion.get("evaluated_at"))
    if (
        reviewed_at is None
        or promoted_at is None
        or any(time > reviewed_at for time in evaluation_times)
        or reviewed_at > promoted_at
    ):
        errors.append(
            f"{prefix}: execution, semantic review, and promotion chronology "
            "is invalid"
        )
    return errors


def validate_adapter_promotion(
    data: dict,
    bundle_root: pathlib.Path | None = None,
    *,
    _skip_manifest_binding: bool = False,
) -> list[str]:
    schema_root = (
        _normalise_root(bundle_root)
        if bundle_root is not None
        else _default_bundle_root()
    )
    structural_errors = validate_json_schema_document(
        data,
        schema_root,
        "schemas/adapter-promotion.schema.json",
        "adapter-promotion",
    )
    if structural_errors:
        return structural_errors
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["adapter-promotion: must be an object"]
    required = {
        "schema_version",
        "record_id",
        "evaluated_at",
        "candidate_id",
        "adapter_sha256",
        "compatibility_payload_sha256",
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
    try:
        candidate_mapping = _candidate_mapping_from_schema(schema_root)
    except ValueError as exc:
        errors.append(f"adapter-promotion: candidate mapping unavailable: {exc}")
        candidate_mapping = {}
    if data.get("candidate_id") not in candidate_mapping:
        errors.append("adapter-promotion: candidate_id is unknown")
    if not _is_sha256(data.get("adapter_sha256")):
        errors.append("adapter-promotion: adapter_sha256 must be SHA-256")
    if not _is_sha256(data.get("compatibility_payload_sha256")):
        errors.append(
            "adapter-promotion: compatibility_payload_sha256 must be SHA-256"
        )
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
    else:
        summary = data.get("evaluation_summary")
        component_pass = (
            summary.get("quality_result") == "pass"
            and summary.get("lifecycle_result") == "pass"
        )
        if (data.get("result") == "pass") != component_pass:
            errors.append(
                "adapter-promotion: result must equal component evaluation results"
            )
        if (
            data.get("promotion_decision") == "selected"
            and data.get("result") != "pass"
        ):
            errors.append(
                "adapter-promotion: selected decision requires passing evaluation"
            )
        if (
            data.get("promotion_decision") == "rejected"
            and data.get("result") != "fail"
        ):
            errors.append(
                "adapter-promotion: rejected decision requires failing evaluation"
            )
        fixture_manifest, _, fixture_errors = _load_bound_json_receipt(
            schema_root,
            summary.get("fixture_manifest_locator"),
            summary.get("fixture_manifest_sha256"),
            "adapter-promotion: fixture manifest",
        )
        errors.extend(fixture_errors)
        fixture_structural_errors: list[str] = []
        if isinstance(fixture_manifest, dict):
            fixture_structural_errors = validate_json_schema_document(
                fixture_manifest,
                schema_root,
                "schemas/adapter-evaluation-fixture-manifest.schema.json",
                "adapter-evaluation-fixture-manifest",
            )
            errors.extend(fixture_structural_errors)
        if (
            isinstance(fixture_manifest, dict)
            and not fixture_structural_errors
        ):
            authority, authority_errors = (
                _load_adapter_evaluation_authority(schema_root)
            )
            errors.extend(authority_errors)
            if isinstance(authority, dict):
                if (
                    summary.get("fixture_manifest_locator")
                    != authority.get("fixture_manifest_locator")
                ):
                    errors.append(
                        "adapter-promotion: fixture manifest locator differs "
                        "from release authority"
                    )
                errors.extend(
                    _validate_fixture_authority(
                        fixture_manifest,
                        authority,
                        schema_root,
                    )
                )
            fixture_set = summary.get("fixture_set")
            if fixture_manifest.get("fixture_set") != fixture_set:
                errors.append(
                    "adapter-promotion: fixture manifest fixture_set mismatch"
                )
            candidate_rows = summary.get("candidate_evaluations", [])
            candidate_ids = [
                row.get("candidate_id")
                for row in candidate_rows
                if isinstance(row, dict)
            ]
            if (
                len(candidate_ids) != len(set(candidate_ids))
                or set(candidate_ids) != set(candidate_mapping)
            ):
                errors.append(
                    "adapter-promotion: candidate evaluations must exactly "
                    "cover both lifecycle candidates"
                )
            executor_ids: list[str] = []
            execution_ids: list[str] = []
            evaluation_times: list[datetime] = []
            for row in candidate_rows:
                if not isinstance(row, dict):
                    continue
                row_errors, metadata = _validate_candidate_evaluation(
                    row,
                    fixture_manifest,
                    data,
                    schema_root,
                    candidate_mapping,
                    authority if isinstance(authority, dict) else None,
                )
                errors.extend(row_errors)
                if isinstance(metadata, dict):
                    executor_id = metadata.get("executor_id")
                    execution_id = metadata.get("execution_id")
                    evaluated_at = metadata.get("evaluated_at")
                    if isinstance(executor_id, str):
                        executor_ids.append(executor_id)
                    if isinstance(execution_id, str):
                        execution_ids.append(execution_id)
                    if isinstance(evaluated_at, datetime):
                        evaluation_times.append(evaluated_at)
            selected_row = next(
                (
                    row
                    for row in candidate_rows
                    if isinstance(row, dict)
                    and row.get("candidate_id") == data.get("candidate_id")
                ),
                None,
            )
            if not isinstance(selected_row, dict):
                errors.append(
                    "adapter-promotion: selected candidate has no evaluation"
                )
            else:
                for field in ("quality_result", "lifecycle_result"):
                    if summary.get(field) != selected_row.get(field):
                        errors.append(
                            f"adapter-promotion: selected {field} mismatch"
                        )
            if (
                len(executor_ids) != len(candidate_mapping)
                or len(executor_ids)
                != len(
                    {
                        _normalised_identity(item)
                        for item in executor_ids
                    }
                )
            ):
                errors.append(
                    "adapter-promotion: candidate executions require two "
                    "distinct executor identities"
                )
            if (
                len(execution_ids) != len(candidate_mapping)
                or len(execution_ids)
                != len(
                    {
                        _normalised_identity(item)
                        for item in execution_ids
                    }
                )
            ):
                errors.append(
                    "adapter-promotion: candidate executions require two "
                    "distinct execution IDs"
                )
            errors.extend(
                _validate_adapter_semantic_review(
                    summary,
                    data,
                    fixture_manifest,
                    [
                        row
                        for row in candidate_rows
                        if isinstance(row, dict)
                    ],
                    executor_ids,
                    evaluation_times,
                    schema_root,
                )
            )
    if bundle_root is not None:
        try:
            actual_compatibility = compatibility_payload_sha256(schema_root)
        except ValueError as exc:
            errors.append(
                f"adapter-promotion: compatibility payload unavailable: {exc}"
            )
        else:
            if data.get("compatibility_payload_sha256") != actual_compatibility:
                errors.append(
                    "adapter-promotion: compatibility_payload_sha256 is stale"
                )
    if bundle_root is not None and not _skip_manifest_binding:
        try:
            manifest = load_adapter_manifest(schema_root)
        except ValueError as exc:
            errors.append(f"adapter-promotion: adapter manifest unavailable: {exc}")
        else:
            manifest_promotion_locator = manifest.get(
                "promotion_record_locator"
            )
            if manifest_promotion_locator != _ADAPTER_PROMOTION_LOCATOR:
                errors.append(
                    "adapter-promotion: active manifest must bind the fixed "
                    "canonical promotion locator"
                )
            canonical_promotion, canonical_raw, canonical_errors = (
                _load_adapter_promotion_record(
                    schema_root, _ADAPTER_PROMOTION_LOCATOR
                )
            )
            errors.extend(
                f"adapter-promotion: canonical promotion record invalid: {error}"
                for error in canonical_errors
            )
            if canonical_raw is not None:
                if (
                    hashlib.sha256(canonical_raw).hexdigest()
                    != manifest.get("promotion_record_sha256")
                ):
                    errors.append(
                        "adapter-promotion: canonical promotion record hash "
                        "does not bind active manifest"
                    )
                if _canonical_json_bytes(data) != canonical_raw:
                    errors.append(
                        "adapter-promotion: supplied promotion record differs "
                        "from the canonical stored promotion record"
                    )
            if (
                isinstance(canonical_promotion, dict)
                and not _json_equal(canonical_promotion, data)
            ):
                errors.append(
                    "adapter-promotion: supplied promotion object differs "
                    "from the canonical stored promotion object"
                )
            try:
                actual_adapter = adapter_payload_sha256(schema_root)
            except ValueError as exc:
                errors.append(
                    f"adapter-promotion: active adapter payload unavailable: {exc}"
                )
            else:
                if data.get("adapter_sha256") != actual_adapter:
                    errors.append(
                        "adapter-promotion: adapter_sha256 is stale"
                    )
                if manifest.get("adapter_payload_sha256") != actual_adapter:
                    errors.append(
                        "adapter-promotion: manifest adapter payload SHA is stale"
                    )
            for field, manifest_field in (
                ("candidate_id", "selected_candidate_id"),
                ("adapter_sha256", "adapter_payload_sha256"),
                (
                    "compatibility_payload_sha256",
                    "compatibility_payload_sha256",
                ),
            ):
                if data.get(field) != manifest.get(manifest_field):
                    errors.append(
                        f"adapter-promotion: {field} does not bind active manifest"
                    )
            if data.get("result") != "pass" or data.get(
                "promotion_decision"
            ) != "selected":
                errors.append(
                    "adapter-promotion: active manifest requires a selected "
                    "passing promotion"
                )
    return sorted(set(errors))


def _load_adapter_promotion_record(
    root: pathlib.Path,
    locator: Any,
) -> tuple[dict | None, bytes | None, list[str]]:
    if locator != _ADAPTER_PROMOTION_LOCATOR:
        return (
            None,
            None,
            [
                "locator must be the fixed canonical promotion path "
                f"{_ADAPTER_PROMOTION_LOCATOR}"
            ],
        )
    try:
        path = _safe_bundle_file(root, locator)
        raw = path.read_bytes()
        value = _load_json_object(path, "promotion record")
    except (ValueError, OSError) as exc:
        return None, None, [str(exc)]
    errors: list[str] = []
    if raw != _canonical_json_bytes(value):
        errors.append("promotion record bytes are not canonical JSON")
    return value, raw, errors


def load_adapter_promotion(
    root: pathlib.Path, locator: str
) -> tuple[dict, bytes]:
    value, raw, load_errors = _load_adapter_promotion_record(root, locator)
    if load_errors or not isinstance(value, dict) or raw is None:
        raise ValueError("; ".join(load_errors or ["promotion record is invalid"]))
    errors = validate_adapter_promotion(value, root)
    if errors:
        raise ValueError("; ".join(errors))
    return value, raw


def load_review_coverage(root: pathlib.Path) -> dict:
    path = _safe_bundle_file(root, "references/review-coverage.json")
    data = _load_json_object(path, "review coverage")
    schema_errors = validate_json_schema_document(
        data,
        root,
        "schemas/review-coverage.schema.json",
        "review coverage",
    )
    if schema_errors:
        raise ValueError(
            "review coverage schema validation failed: "
            + "; ".join(schema_errors)
        )
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
        applicability_states = row.get("applicability_states")
        if (
            not isinstance(applicability_states, list)
            or not applicability_states
            or "applicable" not in applicability_states
            or len(applicability_states) != len(set(applicability_states))
            or not set(applicability_states)
            <= {"applicable", "inapplicable", "uncertain"}
        ):
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
    if tuple(ids) != _CANONICAL_CRITERIA:
        raise ValueError(
            "review coverage canonical criterion IDs or order changed "
            "without a contract migration"
        )
    return data


def _normalised_claim(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _normalised_alignment_excerpt(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalised = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalised.split())


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


def _canonical_exact_source_anchor(
    start_byte: int,
    end_byte: int,
    occurrence: int,
) -> str:
    return (
        f"bytes:{start_byte}-{end_byte};occurrence:{occurrence}"
    )


def _exact_occurrence_offsets(source: bytes, excerpt: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while excerpt and cursor <= len(source) - len(excerpt):
        offset = source.find(excerpt, cursor)
        if offset < 0:
            break
        offsets.append(offset)
        cursor = offset + 1
    return offsets


def _validate_exact_span_shape(
    evidence: dict,
    verification: dict,
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    excerpt = verification.get("excerpt")
    start = verification.get("start_byte")
    end = verification.get("end_byte")
    occurrence = verification.get("occurrence")
    if (
        not _is_nonblank_string(excerpt)
        or len("".join(excerpt.split())) < 8
        or not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or not isinstance(occurrence, int)
        or isinstance(occurrence, bool)
        or start < 0
        or end <= start
        or occurrence < 1
        or evidence.get("source_anchor")
        != _canonical_exact_source_anchor(start, end, occurrence)
    ):
        errors.append(
            f"{prefix}: exact finding anchor span must bind a meaningful "
            "excerpt to canonical UTF-8 byte offsets and occurrence"
        )
    return errors


def _validate_exact_span_against_source(
    evidence: dict,
    verification: dict,
    source: bytes,
    prefix: str,
) -> tuple[list[str], bool]:
    errors = _validate_exact_span_shape(evidence, verification, prefix)
    if errors:
        return errors, False
    excerpt = verification["excerpt"].encode("utf-8")
    start = verification["start_byte"]
    end = verification["end_byte"]
    occurrence = verification["occurrence"]
    offsets = _exact_occurrence_offsets(source, excerpt)
    if (
        end - start != len(excerpt)
        or end > len(source)
        or source[start:end] != excerpt
        or occurrence > len(offsets)
        or offsets[occurrence - 1] != start
    ):
        return (
            [
                f"{prefix}: exact finding anchor span does not resolve to the "
                "declared excerpt occurrence in frozen source bytes"
            ],
            False,
        )
    return [], True


def _validate_rendered_evidence_receipt(
    *,
    verification: dict,
    evidence: dict,
    artifact: dict,
    evidence_root: pathlib.Path,
    schema_root: pathlib.Path,
    subject_id: str,
    prefix: str,
    run_created_at: Any = None,
    run_finalized_at: Any = None,
) -> tuple[list[str], bool]:
    errors: list[str] = []
    locator = verification.get("rendered_receipt_locator")
    digest = verification.get("rendered_receipt_sha256")
    if not _is_canonical_relative_locator(locator) or not _is_sha256(digest):
        return (
            [
                f"{prefix}: rendered finding receipt requires a canonical "
                "locator and SHA-256"
            ],
            False,
        )
    receipt, _, receipt_errors = _load_bound_json_receipt(
        evidence_root,
        locator,
        digest,
        f"{prefix}: rendered finding receipt",
    )
    errors.extend(receipt_errors)
    if not isinstance(receipt, dict):
        return errors, False
    schema_errors = validate_json_schema_document(
        receipt,
        schema_root,
        "schemas/rendered-evidence-receipt.schema.json",
        f"{prefix}: rendered finding receipt",
    )
    errors.extend(schema_errors)
    if schema_errors:
        return errors, False
    recorded_time = _parse_rfc3339_datetime(receipt.get("recorded_at"))
    created_time = _parse_rfc3339_datetime(run_created_at)
    finalized_time = _parse_rfc3339_datetime(run_finalized_at)
    if (
        recorded_time is None
        or (
            created_time is not None
            and recorded_time < created_time
        )
        or (
            finalized_time is not None
            and recorded_time > finalized_time
        )
    ):
        errors.append(
            f"{prefix}: rendered receipt chronology must fall within the run"
        )
    expected = {
        "subject_id": subject_id,
        "artifact_id": artifact.get("artifact_id"),
        "pdf_sha256": artifact.get("sha256"),
        "observation_sha256": hashlib.sha256(
            str(evidence.get("observation", "")).encode("utf-8")
        ).hexdigest(),
    }
    for field, value in expected.items():
        if receipt.get(field) != value:
            errors.append(
                f"{prefix}: rendered finding receipt {field} mismatch"
            )
    region = receipt.get("region")
    if (
        not isinstance(region, dict)
        or not region.get("x0") < region.get("x1")
        or not region.get("y0") < region.get("y1")
        or region.get("x1") > 1
        or region.get("y1") > 1
    ):
        errors.append(
            f"{prefix}: rendered finding receipt region is empty or invalid"
        )
    pdf_path: pathlib.Path | None = None
    try:
        pdf_path = _safe_bundle_file(
            evidence_root, artifact.get("locator")
        )
        page_count, pdf_error = _parsed_pdf_page_count(pdf_path)
    except (ValueError, OSError) as exc:
        page_count, pdf_error = None, str(exc)
    if (
        pdf_error is not None
        or page_count is None
        or receipt.get("page_count") != page_count
        or receipt.get("page") > page_count
    ):
        errors.append(
            f"{prefix}: rendered finding receipt does not bind a real PDF page"
        )
    try:
        rendered_path = _safe_bundle_file(
            evidence_root, receipt.get("rendered_artifact_locator")
        )
        rendered_bytes = rendered_path.read_bytes()
    except (ValueError, OSError) as exc:
        errors.append(
            f"{prefix}: rendered finding artifact is unavailable: {exc}"
        )
    else:
        if (
            hashlib.sha256(rendered_bytes).hexdigest()
            != receipt.get("rendered_artifact_sha256")
            or len(rendered_bytes) < 16
            or not rendered_bytes.startswith(
                (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"P6", b"P3")
            )
        ):
            errors.append(
                f"{prefix}: rendered finding artifact is not a bound image"
            )
        version, version_error = _pdftoppm_version()
        if pdf_path is None:
            regenerated, render_error = None, "bound PDF is unavailable"
        else:
            regenerated, render_error = _render_pdf_page_png(
                pdf_path,
                receipt.get("page"),
            )
        if (
            version_error is not None
            or render_error is not None
            or version != receipt.get("render_tool_version")
            or regenerated != rendered_bytes
        ):
            errors.append(
                f"{prefix}: rendered finding artifact is not the reproducible "
                "page rendered from the bound PDF"
            )
    expected_anchor = (
        f"rendered:{locator}#page={receipt.get('page')}"
    )
    if evidence.get("source_anchor") != expected_anchor:
        errors.append(
            f"{prefix}: rendered finding anchor does not bind its receipt page"
        )
    return errors, not errors


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
    verification = evidence.get("anchor_verification")
    if not isinstance(verification, dict):
        errors.append(f"{prefix}: evidence requires anchor verification")
    elif verification.get("method") == "utf8_exact_excerpt":
        excerpt = verification.get("excerpt")
        if not _is_nonblank_string(excerpt):
            errors.append(
                f"{prefix}: exact anchor verification requires a bounded excerpt"
            )
        elif verification.get("excerpt_sha256") != hashlib.sha256(
            excerpt.encode("utf-8")
        ).hexdigest():
            errors.append(
                f"{prefix}: exact anchor verification excerpt hash mismatch"
            )
        errors.extend(
            _validate_exact_span_shape(evidence, verification, prefix)
        )
    elif verification.get("method") == "rendered_receipt":
        if (
            verification.get("excerpt") is not None
            or verification.get("excerpt_sha256") is not None
        ):
            errors.append(
                f"{prefix}: rendered anchor verification cannot claim text bytes"
            )
        if (
            not _is_canonical_relative_locator(
                verification.get("rendered_receipt_locator")
            )
            or not _is_sha256(
                verification.get("rendered_receipt_sha256")
            )
        ):
            errors.append(
                f"{prefix}: rendered finding receipt requires a canonical "
                "locator and SHA-256"
            )
    else:
        errors.append(f"{prefix}: anchor verification method is invalid")
    return errors


def validate_finding_ledger(
    data: dict, bundle_root: pathlib.Path | None = None
) -> list[str]:
    schema_root = (
        _normalise_root(bundle_root)
        if bundle_root is not None
        else _default_bundle_root()
    )
    structural_errors = validate_json_schema_document(
        data,
        schema_root,
        "schemas/finding-ledger.schema.json",
        "finding-ledger",
    )
    if structural_errors:
        return structural_errors
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
        if not _is_finding_id(finding_id):
            errors.append(
                f"{prefix}: finding_id must be a canonical F- plus 16-hex ID"
            )
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
            or finding.get("dissent", {}).get("state") == "unresolved"
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
            if (
                delta_status == "made_worse"
                and impact_change == "downgraded"
            ):
                errors.append(
                    f"{prefix}: made_worse cannot have downgraded impact"
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
        if not _is_nonblank_string(finding.get("claim")):
            errors.append(f"{prefix}: claim must be nonblank")
        if not _is_nonblank_string(finding.get("why_it_matters")):
            errors.append(f"{prefix}: why_it_matters must be nonblank")
        errors.extend(
            _validate_evidence(
                finding.get("evidence"),
                prefix,
                material=True,
            )
        )
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
            if state == "open" and closure.get("resolution_evidence") is not None:
                errors.append(
                    f"{prefix}: open closure cannot claim resolution evidence"
                )
            if state == "closed" and (
                closure.get("owner") != "none"
                or closure.get("gate") != "none"
                or closure.get("requirement") is not None
                or not isinstance(closure.get("resolution_evidence"), dict)
            ):
                errors.append(
                    f"{prefix}: closed closure requires no surviving owner, "
                    "gate, or requirement and must record typed resolution evidence"
                )
            if state == "closed" and isinstance(
                closure.get("resolution_evidence"), dict
            ):
                errors.extend(
                    _validate_evidence(
                        closure.get("resolution_evidence"),
                        f"{prefix}: resolution evidence",
                        material=True,
                    )
                )
            if state == "not_applicable" and (
                closure.get("owner") != "none"
                or closure.get("gate") != "none"
                or closure.get("requirement") is not None
                or closure.get("resolution_evidence") is not None
            ):
                errors.append(
                    f"{prefix}: inapplicable closure requires no owner, gate, "
                    "requirement, or resolution evidence"
                )
            if (
                adjudication == "unresolved"
                or evidence_state in {"needs_verification", "blocked"}
                or delta_status in {"partially_resolved", "still_open", "made_worse"}
            ) and state == "closed":
                errors.append(f"{prefix}: unresolved or blocked finding cannot be closed")
            if (
                delta_status == "resolved"
                and adjudication not in {"merged", "rejected"}
                and state != "closed"
            ):
                errors.append(
                    f"{prefix}: resolved delta finding requires closed closure"
                )
            if adjudication in {"merged", "rejected"} and (
                state != "not_applicable"
                or closure.get("owner") != "none"
                or closure.get("gate") != "none"
            ):
                errors.append(
                    f"{prefix}: merged or rejected finding requires an "
                    "inapplicable closure"
                )
        provenance = finding.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{prefix}: provenance must be an object")
        else:
            originating = provenance.get("originating_task_ids")
            if not isinstance(originating, list) or not originating:
                errors.append(
                    f"{prefix}: provenance requires at least one originating "
                    "task ID or root"
                )
        if isinstance(provenance, dict) and adjudication == "merged":
            merged_from = provenance.get("merged_from_ids")
            if not merged_from:
                errors.append(
                    f"{prefix}: merged finding must preserve source finding IDs"
                )
            elif len(merged_from) != len(set(merged_from)):
                errors.append(
                    f"{prefix}: merged source finding IDs must be unique"
                )
            elif set(merged_from) != {finding_id}:
                errors.append(
                    f"{prefix}: a merged row must identify exactly its own "
                    "stable ID as the disposed source"
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
        if adjudication in {"merged", "rejected"}:
            if decision_impact != "none" or finding.get("action_type") != "no-action":
                errors.append(
                    f"{prefix}: merged or rejected finding cannot remain a "
                    "material obligation"
                )
        elif decision_impact in {"fundamental", "material", "limited"}:
            if (
                finding.get("action_type") == "no-action"
                or not isinstance(closure, dict)
                or closure.get("state") != "open"
                or closure.get("owner") == "none"
                or closure.get("gate") == "none"
            ):
                errors.append(
                    f"{prefix}: surviving material obligation requires an "
                    "actionable open closure with a real owner and gate"
                )
        if delta_status == "resolved" and (
            decision_impact != "none"
            or finding.get("action_type") != "no-action"
            or impact_change != "downgraded"
        ):
            errors.append(
                f"{prefix}: resolved delta finding must close and downgrade "
                "the surviving obligation"
            )
        if finding_id and finding_id != stable_finding_id(finding) and prior_id is None:
            errors.append(
                f"{prefix}: new finding_id does not match stable identity fields"
            )
    finding_by_id = {
        finding.get("finding_id"): finding
        for finding in findings
        if isinstance(finding, dict)
        and _is_finding_id(finding.get("finding_id"))
    }
    for finding_id, finding in finding_by_id.items():
        prefix = f"finding-ledger: finding[{finding_id}]"
        provenance = finding.get("provenance")
        if not isinstance(provenance, dict):
            continue
        adjudication = finding.get("adjudication_status")
        merged_from = provenance.get("merged_from_ids", [])
        merged_into = provenance.get("merged_into_finding_id")
        if adjudication != "merged" and merged_into is not None:
            errors.append(
                f"{prefix}: non-merged row cannot have merged_into_finding_id"
            )
        if adjudication not in {"merged", "retained", "unresolved"} and merged_from:
            errors.append(
                f"{prefix}: merged_from_ids are forbidden for this disposition"
            )
        if adjudication in {"retained", "unresolved"}:
            for source_id in merged_from:
                source = finding_by_id.get(source_id)
                if not isinstance(source, dict) or source.get(
                    "adjudication_status"
                ) != "merged":
                    errors.append(
                        f"{prefix}: merged_from_ids references a nonexistent "
                        f"or non-merged source: {source_id}"
                    )
                    continue
                if source.get("provenance", {}).get(
                    "merged_into_finding_id"
                ) != finding_id:
                    errors.append(
                        f"{prefix}: merged_from_ids source does not reciprocally "
                        f"target this finding: {source_id}"
                    )
        if adjudication == "merged":
            target = finding_by_id.get(merged_into)
            if not isinstance(target, dict) or target.get(
                "adjudication_status"
            ) not in {"retained", "unresolved"}:
                errors.append(
                    f"{prefix}: merge target does not exist as a canonical "
                    f"surviving row: {merged_into}"
                )
            elif finding_id not in target.get("provenance", {}).get(
                "merged_from_ids", []
            ):
                errors.append(
                    f"{prefix}: merge target does not reciprocally record "
                    f"source {finding_id}"
                )
    if any(
        _contains_positive_acceptance_prediction(text)
        for text in _string_leaves(data)
    ):
        errors.append(
            "finding-ledger: acceptance prediction is forbidden anywhere in "
            "the canonical ledger"
        )
    if _contains_count_based_confidence(data):
        errors.append(
            "finding-ledger: reviewer, agent, or task count cannot establish "
            "scientific confidence"
        )
    return sorted(set(errors))


def _load_bound_json_receipt(
    evidence_root: pathlib.Path,
    locator: Any,
    expected_sha256: Any,
    label: str,
) -> tuple[dict | None, str | None, list[str]]:
    errors: list[str] = []
    if not _is_canonical_relative_locator(locator):
        return (
            None,
            None,
            [f"{label}: evidence locator must be canonical and relative"],
        )
    if not _is_sha256(expected_sha256):
        return None, None, [f"{label}: evidence SHA-256 is required"]
    try:
        path = _safe_bundle_file(evidence_root, locator)
    except ValueError as exc:
        return None, None, [f"{label}: evidence locator is invalid: {exc}"]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, [f"{label}: evidence is unreadable: {exc}"]
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        errors.append(f"{label}: evidence hash mismatch")
    try:
        receipt = _load_json_object(path, f"{label} evidence")
    except ValueError as exc:
        errors.append(f"{label}: {exc}")
        return None, actual_sha256, errors
    if raw != _canonical_json_bytes(receipt):
        errors.append(f"{label}: evidence is not canonical JSON")
    return receipt, actual_sha256, errors


def _validate_validation_state(
    value: Any,
    prefix: str,
    *,
    bundle_root: pathlib.Path,
    evidence_root: pathlib.Path,
    subject_kind: str,
    subject_id: str,
    control: str,
    requested_value: str,
    configuration_proof_locator: str | None,
    configuration_proof_sha256: str | None,
    configuration_receipt: dict | None,
    require_passed: bool,
    observed_times: list[datetime] | None = None,
) -> list[str]:
    if not isinstance(value, dict):
        return [f"{prefix}: validation state must be an object"]
    errors: list[str] = []
    status = value.get("status")
    if status not in {"passed", "failed", "not_run"}:
        errors.append(f"{prefix}: status is invalid")
    locator = value.get("evidence_locator")
    digest = value.get("sha256")
    if status in {"passed", "failed"}:
        if not isinstance(locator, str) or not locator:
            errors.append(
                f"{prefix}: {status} validation requires evidence locator"
            )
        if not _is_sha256(digest):
            errors.append(f"{prefix}: {status} validation requires SHA-256")
        receipt, _, receipt_errors = _load_bound_json_receipt(
            evidence_root,
            locator,
            digest,
            f"{prefix} validation",
        )
        errors.extend(receipt_errors)
        if isinstance(receipt, dict):
            structural_errors = validate_json_schema_document(
                receipt,
                bundle_root,
                "schemas/runtime-evidence-receipt.schema.json",
                f"{prefix} validation receipt",
            )
            errors.extend(structural_errors)
            if not structural_errors:
                validation_time = _parse_rfc3339_datetime(
                    receipt.get("recorded_at")
                )
                configuration_time = (
                    _parse_rfc3339_datetime(
                        configuration_receipt.get("recorded_at")
                    )
                    if isinstance(configuration_receipt, dict)
                    else None
                )
                if validation_time is not None and observed_times is not None:
                    observed_times.append(validation_time)
                if (
                    validation_time is None
                    or (
                        configuration_time is not None
                        and validation_time < configuration_time
                    )
                ):
                    errors.append(
                        f"{prefix}: validation receipt chronology must follow "
                        "its configuration receipt"
                    )
                configured_value = (
                    configuration_receipt.get(
                        {
                            "model": "configured_model",
                            "mode": "configured_mode",
                            "sandbox": "configured_sandbox",
                        }[control]
                    )
                    if isinstance(configuration_receipt, dict)
                    else None
                )
                expected_fields = {
                    "schema_version": "1.0.0",
                    "receipt_kind": "control_validation",
                    "subject_kind": subject_kind,
                    "subject_id": subject_id,
                    "control": control,
                    "expected_value": requested_value,
                    "configured_value": configured_value,
                    "result": status,
                    "configuration_receipt_locator":
                        configuration_proof_locator,
                    "configuration_receipt_sha256":
                        configuration_proof_sha256,
                    "validator": "adapter-conformance-suite",
                }
                for field, expected in expected_fields.items():
                    if receipt.get(field) != expected:
                        errors.append(
                            f"{prefix}: validation receipt {field} does not bind "
                            "the requested subject and configuration receipt"
                        )
                derived_status = (
                    "passed"
                    if configured_value == requested_value
                    else "failed"
                )
                if status != derived_status:
                    errors.append(
                        f"{prefix}: validation result is inconsistent with "
                        "configured and expected values"
                    )
    elif locator is not None or digest is not None:
        errors.append(
            f"{prefix}: not_run validation must not claim evidence"
        )
    if require_passed and status != "passed":
        errors.append(f"{prefix}: validation did not pass")
    return errors


def _validate_configuration_proof(
    value: Any,
    prefix: str,
    subject_kind: str,
    subject_id: str,
    *,
    bundle_root: pathlib.Path,
    evidence_root: pathlib.Path,
    requested_model: str,
    requested_mode: str,
    requested_sandbox: str | None,
    agent_or_task_identifier: str | None,
    fork_policy: str | None,
    leaf_only: bool | None,
    input_artifact_ids: list[str] | None,
    dependency_task_ids: list[str] | None,
    bundle_input_artifacts: list[dict] | None,
    input_records: list[dict] | None,
    input_snapshot_sha256: str | None,
    task_effects: list[str] | None,
    report_contract: str | None,
    stop_condition: str | None,
    configuration_source: str,
    fallback_policy: str,
    surface: str,
    host_build: str,
    adapter_sha256: str,
    compatibility_payload_sha256: str,
    selected_candidate_id: str | None,
    promotion_record_sha256: str | None,
    trigger: str | None,
    assigned_criterion_ids: list[str] | None,
    required: bool,
) -> tuple[list[str], str | None, dict | None]:
    if value is None and not required:
        return [], None, None
    if not isinstance(value, dict):
        return (
            [f"{prefix}: configuration proof must be an object"],
            None,
            None,
        )
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
    receipt, actual_sha256, receipt_errors = _load_bound_json_receipt(
        evidence_root,
        value.get("locator"),
        value.get("sha256"),
        f"{prefix} configuration proof",
    )
    errors.extend(receipt_errors)
    if isinstance(receipt, dict):
        structural_errors = validate_json_schema_document(
            receipt,
            bundle_root,
            "schemas/runtime-evidence-receipt.schema.json",
            f"{prefix} configuration receipt",
        )
        errors.extend(structural_errors)
        if not structural_errors:
            expected_fields = {
                "schema_version": "1.0.0",
                "receipt_kind": "configuration",
                "subject_kind": subject_kind,
                "subject_id": subject_id,
                "requested_model": requested_model,
                "requested_mode": requested_mode,
                "requested_sandbox": requested_sandbox,
                "agent_or_task_identifier": agent_or_task_identifier,
                "fork_policy": fork_policy,
                "leaf_only": leaf_only,
                "input_artifact_ids": input_artifact_ids,
                "dependency_task_ids": dependency_task_ids,
                "bundle_input_artifacts": bundle_input_artifacts,
                "inputs": input_records,
                "input_snapshot_sha256": input_snapshot_sha256,
                "task_effects": task_effects,
                "report_contract": report_contract,
                "stop_condition": stop_condition,
                "configuration_source": configuration_source,
                "proof_kind": value.get("proof_kind"),
                "surface": surface,
                "host_build": host_build,
                "adapter_sha256": adapter_sha256,
                "compatibility_payload_sha256":
                    compatibility_payload_sha256,
                "selected_candidate_id": selected_candidate_id,
                "promotion_record_sha256": promotion_record_sha256,
                "trigger": trigger,
                "assigned_criterion_ids": assigned_criterion_ids,
                "fallback_policy": fallback_policy,
            }
            for field, expected in expected_fields.items():
                if receipt.get(field) != expected:
                    errors.append(
                        f"{prefix}: configuration proof receipt {field} does not "
                        "bind the requested subject and controls"
                    )
    return errors, actual_sha256, receipt


def _task_input_snapshot_sha256(records: list[dict]) -> str:
    return _json_sha256(
        {
            "schema_version": "1.0.0",
            "inputs": records,
        }
    )


def _build_task_input_records(
    task: dict,
    artifact_by_id: dict[str, dict],
    task_by_id: dict[str, dict],
    bundle_root: pathlib.Path,
) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    records: list[dict] = []
    task_id = task.get("task_id")
    for artifact_id in sorted(task.get("input_artifact_ids", [])):
        artifact = artifact_by_id.get(artifact_id)
        if not isinstance(artifact, dict) or artifact.get("state") != "frozen":
            continue
        records.append(
            {
                "input_id": f"run:{artifact_id}",
                "kind": "run_input",
                "source_id": artifact_id,
                "locator": artifact.get("locator"),
                "sha256": artifact.get("sha256"),
                "lineage_id": artifact.get("lineage_id"),
                "source_kind": artifact.get("kind"),
                "state": artifact.get("state"),
            }
        )
    dependency_ids = task.get("dependency_task_ids", [])
    if not isinstance(dependency_ids, list):
        dependency_ids = []
    for dependency_id in sorted(dependency_ids):
        if dependency_id == task_id:
            errors.append(
                f"task {task_id}: dependency task cannot reference itself"
            )
            continue
        dependency = task_by_id.get(dependency_id)
        if not isinstance(dependency, dict):
            errors.append(
                f"task {task_id}: dependency task is unknown: {dependency_id}"
            )
            continue
        if dependency.get("status") != "completed":
            errors.append(
                f"task {task_id}: dependency task is not completed: "
                f"{dependency_id}"
            )
            continue
        if not _is_canonical_relative_locator(
            dependency.get("report_artifact")
        ) or not _is_sha256(dependency.get("report_sha256")):
            errors.append(
                f"task {task_id}: dependency task report is not byte-bound: "
                f"{dependency_id}"
            )
            continue
        records.append(
            {
                "input_id": f"task:{dependency_id}",
                "kind": "task_report",
                "source_id": dependency_id,
                "locator": dependency.get("report_artifact"),
                "sha256": dependency.get("report_sha256"),
                "lineage_id": None,
                "source_kind": None,
                "state": None,
            }
        )
    bundle_inputs = task.get("bundle_input_artifacts", [])
    if not isinstance(bundle_inputs, list):
        bundle_inputs = []
    for item in sorted(
        (item for item in bundle_inputs if isinstance(item, dict)),
        key=lambda item: str(item.get("locator")),
    ):
        locator = item.get("locator")
        digest = item.get("sha256")
        try:
            path = _safe_bundle_file(bundle_root, locator)
        except ValueError as exc:
            errors.append(
                f"task {task_id}: bundle input is invalid: {locator}: {exc}"
            )
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != actual:
            errors.append(
                f"task {task_id}: bundle input hash mismatch: {locator}"
            )
        records.append(
            {
                "input_id": f"bundle:{locator}",
                "kind": "bundle_file",
                "source_id": locator,
                "locator": locator,
                "sha256": digest,
                "lineage_id": None,
                "source_kind": None,
                "state": None,
            }
        )
    records.sort(key=lambda record: record["input_id"])
    input_ids = [record["input_id"] for record in records]
    if len(input_ids) != len(set(input_ids)):
        errors.append(f"task {task_id}: input snapshot has duplicate input IDs")
    return records, errors


def _validate_task_dependency_graph(tasks: list[dict]) -> list[str]:
    graph = {
        task.get("task_id"): list(task.get("dependency_task_ids", []))
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            errors.append(
                f"run-manifest: delegated task dependency cycle at {task_id}"
            )
            return
        visiting.add(task_id)
        for dependency_id in graph.get(task_id, []):
            if dependency_id in graph:
                visit(dependency_id)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in sorted(graph):
        visit(task_id)
    return sorted(set(errors))


def _validate_task_dependency_chronology(
    tasks: list[dict],
    task_configuration_time_by_id: dict[str, datetime],
    task_report_time_by_id: dict[str, datetime],
) -> list[str]:
    task_by_id = {
        task.get("task_id"): task
        for task in tasks
        if isinstance(task, dict)
        and isinstance(task.get("task_id"), str)
    }
    errors: list[str] = []
    for task in tasks:
        if (
            not isinstance(task, dict)
            or task.get("status") != "completed"
            or not isinstance(task.get("task_id"), str)
        ):
            continue
        task_id = task["task_id"]
        child_configuration_time = task_configuration_time_by_id.get(
            task_id
        )
        child_report_time = task_report_time_by_id.get(task_id)
        for dependency_id in task.get("dependency_task_ids", []):
            dependency = task_by_id.get(dependency_id)
            dependency_report_time = task_report_time_by_id.get(
                dependency_id
            )
            if (
                not isinstance(dependency, dict)
                or dependency.get("status") != "completed"
                or dependency_report_time is None
                or child_configuration_time is None
                or child_report_time is None
                or not (
                    dependency_report_time
                    <= child_configuration_time
                    <= child_report_time
                )
            ):
                errors.append(
                    "run-manifest: task dependency chronology requires the "
                    "dependency report before child configuration and report: "
                    f"{dependency_id} -> {task_id}"
                )
    return sorted(set(errors))


def _validate_delegation_terminal_inventory(
    value: Any,
    run_id: Any,
    run_created_at: Any,
    run_finalized_at: Any,
    tasks: list[dict],
    task_report_times: list[datetime],
    assurance_times: list[datetime],
    *,
    bundle_root: pathlib.Path,
    evidence_root: pathlib.Path,
) -> list[str]:
    prefix = "run-manifest: delegation terminal inventory"
    if not isinstance(value, dict):
        return [f"{prefix} must be a bound receipt"]
    receipt, _, errors = _load_bound_json_receipt(
        evidence_root,
        value.get("locator"),
        value.get("sha256"),
        prefix,
    )
    if not isinstance(receipt, dict):
        return errors
    structural_errors = validate_json_schema_document(
        receipt,
        bundle_root,
        "schemas/runtime-evidence-receipt.schema.json",
        "delegation-terminal-inventory",
    )
    errors.extend(structural_errors)
    if structural_errors:
        return errors
    if receipt.get("receipt_kind") != "delegation_terminal_inventory":
        errors.append(f"{prefix}: receipt_kind mismatch")
    if receipt.get("run_id") != run_id:
        errors.append(f"{prefix}: run_id mismatch")
    inventory_time = _parse_rfc3339_datetime(receipt.get("recorded_at"))
    run_time = _parse_rfc3339_datetime(run_created_at)
    finalized_time = _parse_rfc3339_datetime(run_finalized_at)
    if (
        inventory_time is None
        or run_time is None
        or finalized_time is None
        or inventory_time < run_time
        or inventory_time > finalized_time
        or any(report_time > inventory_time for report_time in task_report_times)
        or any(
            assurance_time > inventory_time
            for assurance_time in assurance_times
        )
    ):
        errors.append(
            f"{prefix}: inventory chronology must follow the run and every "
            "completed task report"
        )
    expected_tasks = [
        {
            "task_id": task.get("task_id"),
            "agent_or_task_identifier": task.get(
                "agent_or_task_identifier"
            ),
            "status": task.get("status"),
            "report_artifact": task.get("report_artifact"),
            "report_sha256": task.get("report_sha256"),
            "descendant_state": task.get("descendant_state"),
            "terminal_reason": task.get("terminal_reason"),
        }
        for task in sorted(
            (task for task in tasks if isinstance(task, dict)),
            key=lambda task: str(task.get("task_id")),
        )
    ]
    if receipt.get("tasks") != expected_tasks:
        errors.append(
            f"{prefix}: receipt does not exactly match the terminal task inventory"
        )
    return errors


def _coverage_ids(matrix: dict) -> list[str]:
    criteria = matrix.get("criteria", []) if isinstance(matrix, dict) else []
    return [
        row.get("criterion_id")
        for row in criteria
        if isinstance(row, dict) and isinstance(row.get("criterion_id"), str)
    ]


def _venue_rule_authority_projection(
    collection: str,
    rule: dict,
) -> dict:
    if collection == "criteria":
        return {
            "rule_id": rule.get("rule_id"),
            "statement": rule.get("statement"),
        }
    return {
        field: rule.get(field)
        for field in (
            "field_id",
            "role",
            "field_type",
            "minimum",
            "maximum",
            "allowed_labels",
            "anchors",
            "direction",
        )
    }


def _normalised_support_text(value: Any) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(value)).casefold().split()
    )


def _venue_source_atom_present(value: Any, text: str) -> bool:
    value_text = _normalised_support_text(value)
    if not value_text:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(
            re.search(
                rf"(?<![0-9.]){re.escape(value_text)}(?![0-9.])",
                text,
            )
        )
    if re.fullmatch(r"[\w ]+", value_text, flags=re.UNICODE):
        return bool(
            re.search(
                rf"(?<!\w){re.escape(value_text)}(?!\w)",
                text,
                flags=re.UNICODE,
            )
        )
    return value_text in text


def _validate_venue_claim_support(
    claim: dict,
    excerpts: dict[str, str],
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    excerpt_ids = claim.get("excerpt_ids", [])
    unknown_excerpt_ids = [
        excerpt_id
        for excerpt_id in excerpt_ids
        if excerpt_id not in excerpts
    ]
    for excerpt_id in unknown_excerpt_ids:
        errors.append(
            f"{prefix}: claim references unknown verbatim excerpt ID: "
            f"{excerpt_id}"
        )
    bound_excerpt_text = " ".join(
        excerpts[excerpt_id]
        for excerpt_id in excerpt_ids
        if excerpt_id in excerpts
    )
    projection_text = _normalised_support_text(
        json.dumps(
            claim.get("projection"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    excerpt_text = _normalised_support_text(bound_excerpt_text)
    errors.extend(
        f"{prefix}: claim support term is absent from the bound verbatim "
        f"excerpt or typed projection: {term}"
        for term in claim.get("support_terms", [])
        if (
            not _normalised_support_text(term)
            or _normalised_support_text(term) not in excerpt_text
            or _normalised_support_text(term) not in projection_text
        )
    )
    projection = claim.get("projection")
    if (
        claim.get("claim_kind") == "native_field"
        and isinstance(projection, dict)
    ):
        field_type = projection.get("field_type")
        required_transcriptions: list[Any] = []
        if field_type == "categorical":
            required_transcriptions.extend(
                projection.get("allowed_labels", [])
            )
        elif field_type in {"integer_scale", "numeric_scale"}:
            required_transcriptions.extend(
                [
                    projection.get("minimum"),
                    projection.get("maximum"),
                ]
            )
            for anchor in projection.get("anchors", []):
                if isinstance(anchor, dict):
                    required_transcriptions.extend(
                        [anchor.get("value"), anchor.get("label")]
                    )
        for value in required_transcriptions:
            if not _normalised_support_text(value):
                continue
            if not _venue_source_atom_present(value, excerpt_text):
                errors.append(
                    f"{prefix}: native field transcription is absent from "
                    f"its bound verbatim excerpts: {value}"
                )
        if field_type in {"integer_scale", "numeric_scale"}:
            bound_excerpt_values = [
                _normalised_support_text(excerpts[excerpt_id])
                for excerpt_id in excerpt_ids
                if excerpt_id in excerpts
            ]
            for anchor in projection.get("anchors", []):
                if not isinstance(anchor, dict):
                    continue
                if not any(
                    _venue_source_atom_present(
                        anchor.get("value"), candidate
                    )
                    and _venue_source_atom_present(
                        anchor.get("label"), candidate
                    )
                    for candidate in bound_excerpt_values
                ):
                    errors.append(
                        f"{prefix}: native scale value-label pair is absent "
                        "from one bound verbatim excerpt: "
                        f"{anchor.get('value')} / {anchor.get('label')}"
                    )
    return errors


def _validate_venue_profile_binding(
    target: Any,
    profile: Any,
    bundle_root: pathlib.Path,
    completion: Any,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(target, dict) or not (
        isinstance(target.get("venue"), str) and target.get("venue").strip()
    ):
        return [
            "run-manifest: target venue must be explicit, including unknown"
        ]
    if not isinstance(profile, dict):
        return ["run-manifest: venue_profile must be an object"]

    venue = target.get("venue")
    target_tuple = (venue, target.get("year"), target.get("track"))
    nullable_fields = (
        "profile_id",
        "profile_version",
        "venue",
        "year",
        "track",
        "profile_locator",
        "profile_sha256",
        "source_manifest_locator",
        "source_sha256",
    )
    if venue == "unknown":
        if target.get("year") is not None or target.get("track") is not None:
            errors.append(
                "run-manifest: unknown venue requires null year and track"
            )
        if profile.get("status") != "unknown":
            errors.append(
                "run-manifest: unknown venue requires unknown profile state"
            )
        for field in nullable_fields:
            if profile.get(field) is not None:
                errors.append(
                    f"run-manifest: unknown venue profile requires null {field}"
                )
        if profile.get("blocked_reason") is not None:
            errors.append(
                "run-manifest: unknown venue profile cannot claim a blocker"
            )
        return errors

    status = profile.get("status")
    if status == "blocked":
        if completion == "complete":
            errors.append(
                "run-manifest: blocked known-venue profile requires partial "
                "or blocked completion"
            )
        if not (
            isinstance(profile.get("blocked_reason"), str)
            and profile.get("blocked_reason").strip()
        ):
            errors.append(
                "run-manifest: blocked venue profile requires a reason"
            )
        if (
            profile.get("venue"),
            profile.get("year"),
            profile.get("track"),
        ) != target_tuple:
            errors.append(
                "run-manifest: blocked venue profile tuple differs from target"
            )
        for field in (
            "profile_id",
            "profile_version",
            "profile_locator",
            "profile_sha256",
            "source_manifest_locator",
            "source_sha256",
        ):
            if profile.get(field) is not None:
                errors.append(
                    f"run-manifest: blocked venue profile requires null {field}"
                )
        return errors
    if status != "loaded":
        return [
            "run-manifest: known venue requires a loaded or explicitly blocked "
            "versioned profile"
        ]
    if profile.get("blocked_reason") is not None:
        errors.append(
            "run-manifest: loaded venue profile cannot retain blocked_reason"
        )
    if (
        profile.get("venue"),
        profile.get("year"),
        profile.get("track"),
    ) != target_tuple:
        errors.append(
            "run-manifest: loaded venue profile tuple differs from target"
        )
    if not (
        isinstance(profile.get("profile_id"), str)
        and profile.get("profile_id").strip()
    ):
        errors.append("run-manifest: loaded venue profile requires profile_id")
    if not (
        isinstance(profile.get("profile_version"), str)
        and re.fullmatch(
            r"[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?",
            profile.get("profile_version"),
        )
    ):
        errors.append(
            "run-manifest: loaded venue profile requires semantic profile_version"
        )

    profile_receipt, _, profile_errors = _load_bound_json_receipt(
        bundle_root,
        profile.get("profile_locator"),
        profile.get("profile_sha256"),
        "run-manifest: venue profile",
    )
    errors.extend(profile_errors)
    if any("hash mismatch" in item for item in profile_errors):
        errors.append("run-manifest: venue profile hash mismatch")
    source_receipt, _, source_errors = _load_bound_json_receipt(
        bundle_root,
        profile.get("source_manifest_locator"),
        profile.get("source_sha256"),
        "run-manifest: venue source manifest",
    )
    errors.extend(source_errors)
    source_ids: set[str] = set()
    source_sections: dict[str, set[str]] = {}
    source_claims: dict[str, dict] = {}
    source_claim_locations: dict[str, tuple[str, str]] = {}
    referenced_source_claim_ids: set[str] = set()
    if isinstance(profile_receipt, dict):
        if any(
            _contains_positive_acceptance_prediction(text)
            for text in _string_leaves(profile_receipt)
        ):
            errors.append(
                "run-manifest: venue profile cannot contain an acceptance "
                "prediction"
            )
        profile_structural_errors = validate_json_schema_document(
            profile_receipt,
            bundle_root,
            "schemas/venue-profile.schema.json",
            "venue-profile",
        )
        errors.extend(profile_structural_errors)
        if not profile_structural_errors:
            required_binding = {
                "schema_version": "1.0.0",
                "profile_id": profile.get("profile_id"),
                "profile_version": profile.get("profile_version"),
                "venue": venue,
                "year": target.get("year"),
                "track": target.get("track"),
                "source_manifest_locator": profile.get(
                    "source_manifest_locator"
                ),
                "source_sha256": profile.get("source_sha256"),
            }
            for field, expected in required_binding.items():
                if profile_receipt.get(field) != expected:
                    errors.append(
                        f"run-manifest: venue profile artifact {field} mismatch"
                    )
    if isinstance(source_receipt, dict):
        source_structural_errors = validate_json_schema_document(
            source_receipt,
            bundle_root,
            "schemas/venue-source-manifest.schema.json",
            "venue-source-manifest",
        )
        errors.extend(source_structural_errors)
        if not source_structural_errors:
            registry_locator = source_receipt.get(
                "authority_registry_locator"
            )
            registry: dict | None = None
            try:
                registry_path = _safe_bundle_file(
                    bundle_root, registry_locator
                )
                registry = _load_json_object(
                    registry_path, "venue authority registry"
                )
            except (ValueError, OSError) as exc:
                errors.append(
                    f"run-manifest: venue authority registry is invalid: {exc}"
                )
            else:
                if (
                    source_receipt.get("authority_registry_id")
                    != registry.get("registry_id")
                ):
                    errors.append(
                        "run-manifest: venue authority registry identity mismatch"
                    )
                registry_errors = validate_json_schema_document(
                    registry,
                    bundle_root,
                    "schemas/venue-authority-registry.schema.json",
                    "venue-authority-registry",
                )
                errors.extend(registry_errors)
            for field, expected in (
                ("schema_version", "1.0.0"),
                ("venue", venue),
                ("year", target.get("year")),
                ("track", target.get("track")),
                ("authority", "official-first-party"),
            ):
                if source_receipt.get(field) != expected:
                    errors.append(
                        f"run-manifest: venue source manifest {field} mismatch"
                    )
            trusted_hosts: set[str] = set()
            if isinstance(registry, dict):
                matching_registry_rows = [
                    row
                    for row in registry.get("venues", [])
                    if isinstance(row, dict) and row.get("venue") == venue
                ]
                if len(matching_registry_rows) != 1:
                    errors.append(
                        "run-manifest: venue authority registry requires "
                        "exactly one target entry"
                    )
                else:
                    registry_venue_row = matching_registry_rows[0]
                    trusted_hosts = {
                        host.casefold()
                        for host in registry_venue_row.get(
                            "official_hosts", []
                        )
                        if isinstance(host, str)
                    }
                    matching_profiles = [
                        row
                        for row in registry_venue_row.get("profiles", [])
                        if isinstance(row, dict)
                        and row.get("year") == target.get("year")
                        and row.get("track") == target.get("track")
                        and row.get("profile_id")
                        == profile.get("profile_id")
                        and row.get("profile_version")
                        == profile.get("profile_version")
                    ]
                    expected_profile_authority = {
                        "profile_id": profile.get("profile_id"),
                        "profile_version": profile.get("profile_version"),
                        "year": target.get("year"),
                        "track": target.get("track"),
                        "profile_locator": profile.get("profile_locator"),
                        "profile_sha256": profile.get("profile_sha256"),
                        "source_manifest_locator":
                            profile.get("source_manifest_locator"),
                        "source_sha256": profile.get("source_sha256"),
                    }
                    if (
                        len(matching_profiles) != 1
                        or matching_profiles[0]
                        != expected_profile_authority
                    ):
                        errors.append(
                            "run-manifest: loaded venue profile is not the "
                            "exact release-governed tuple and byte set"
                        )
            source_id_list = [
                source.get("source_id")
                for source in source_receipt.get("sources", [])
                if isinstance(source, dict)
                and isinstance(source.get("source_id"), str)
            ]
            source_ids = set(source_id_list)
            if len(source_id_list) != len(source_ids):
                errors.append(
                    "run-manifest: venue source IDs must be unique"
                )
            for source in source_receipt.get("sources", []):
                if not isinstance(source, dict):
                    continue
                source_id = source.get("source_id")
                source_evidence, _, source_evidence_errors = (
                    _load_bound_json_receipt(
                        bundle_root,
                        source.get("content_locator"),
                        source.get("content_sha256"),
                        "run-manifest: venue source evidence",
                    )
                )
                errors.extend(source_evidence_errors)
                source_evidence_schema_errors: list[str] = []
                if isinstance(source_evidence, dict):
                    source_evidence_schema_errors = (
                        validate_json_schema_document(
                            source_evidence,
                            bundle_root,
                            "schemas/venue-source-evidence.schema.json",
                            "venue-source-evidence",
                        )
                    )
                    errors.extend(source_evidence_schema_errors)
                if (
                    isinstance(source_evidence, dict)
                    and not source_evidence_schema_errors
                ):
                    for field, expected in (
                        ("source_id", source_id),
                        ("url", source.get("url")),
                        ("title", source.get("title")),
                        ("retrieved_at", source_receipt.get("retrieved_at")),
                    ):
                        if source_evidence.get(field) != expected:
                            errors.append(
                                "run-manifest: venue source evidence "
                                f"{field} mismatch"
                            )
                    source_capture, _, capture_errors = (
                        _load_bound_json_receipt(
                            bundle_root,
                            source_evidence.get("capture_locator"),
                            source_evidence.get("capture_sha256"),
                            "run-manifest: venue source capture",
                        )
                    )
                    errors.extend(capture_errors)
                    source_capture_schema_errors: list[str] = []
                    if isinstance(source_capture, dict):
                        source_capture_schema_errors = (
                            validate_json_schema_document(
                                source_capture,
                                bundle_root,
                                "schemas/venue-source-capture.schema.json",
                                "venue-source-capture",
                            )
                        )
                        errors.extend(source_capture_schema_errors)
                    captured_text: str | None = None
                    if (
                        isinstance(source_capture, dict)
                        and not source_capture_schema_errors
                    ):
                        for field, expected in (
                            ("source_id", source_id),
                            ("url", source.get("url")),
                            (
                                "captured_at",
                                source_evidence.get("retrieved_at"),
                            ),
                        ):
                            if source_capture.get(field) != expected:
                                errors.append(
                                    "run-manifest: venue source capture "
                                    f"{field} mismatch"
                                )
                        if isinstance(
                            source_capture.get("captured_text"), str
                        ):
                            captured_text = source_capture["captured_text"]
                    evidence_sections = source_evidence.get("sections", [])
                    evidence_anchors = [
                        section.get("section_anchor")
                        for section in evidence_sections
                        if isinstance(section, dict)
                    ]
                    if (
                        len(evidence_anchors) != len(set(evidence_anchors))
                        or evidence_anchors
                        != source.get("retrieved_section_anchors", [])
                    ):
                        errors.append(
                            "run-manifest: venue source evidence sections do "
                            "not exactly bind the manifest anchors"
                        )
                    source_excerpt_ids: list[str] = []
                    source_locators: list[str] = []
                    for section in evidence_sections:
                        if not isinstance(section, dict):
                            continue
                        verification = section.get("source_verification")
                        if isinstance(verification, dict):
                            verified_at = _parse_rfc3339_datetime(
                                verification.get("verified_at")
                            )
                            retrieved_at = _parse_rfc3339_datetime(
                                source_evidence.get("retrieved_at")
                            )
                            if (
                                isinstance(verified_at, datetime)
                                and isinstance(retrieved_at, datetime)
                                and verified_at < retrieved_at
                            ):
                                errors.append(
                                    "run-manifest: venue source verification "
                                    "cannot predate source retrieval"
                                )
                        excerpts: dict[str, str] = {}
                        excerpt_id_list: list[str] = []
                        for excerpt in section.get(
                            "verbatim_excerpts", []
                        ):
                            if not isinstance(excerpt, dict):
                                continue
                            excerpt_id = excerpt.get("excerpt_id")
                            excerpt_id_list.append(excerpt_id)
                            source_excerpt_ids.append(excerpt_id)
                            source_locators.append(
                                excerpt.get("source_locator")
                            )
                            text = excerpt.get("text")
                            if (
                                not isinstance(text, str)
                                or hashlib.sha256(
                                    text.encode("utf-8")
                                ).hexdigest()
                                != excerpt.get("sha256")
                            ):
                                errors.append(
                                    "run-manifest: venue verbatim excerpt "
                                    f"hash mismatch: {excerpt_id}"
                                )
                                continue
                            if isinstance(captured_text, str):
                                capture_bytes = captured_text.encode("utf-8")
                                text_bytes = text.encode("utf-8")
                                start = excerpt.get("capture_start_byte")
                                end = excerpt.get("capture_end_byte")
                                occurrence = excerpt.get(
                                    "capture_occurrence"
                                )
                                if (
                                    not isinstance(start, int)
                                    or isinstance(start, bool)
                                    or not isinstance(end, int)
                                    or isinstance(end, bool)
                                    or not 0 <= start < end <= len(
                                        capture_bytes
                                    )
                                    or capture_bytes[start:end] != text_bytes
                                ):
                                    errors.append(
                                        "run-manifest: venue verbatim "
                                        "excerpt does not match its frozen "
                                        f"capture byte span: {excerpt_id}"
                                    )
                                elif occurrence != (
                                    capture_bytes[:start].count(text_bytes) + 1
                                ):
                                    errors.append(
                                        "run-manifest: venue verbatim "
                                        "excerpt occurrence does not match "
                                        f"its frozen capture: {excerpt_id}"
                                    )
                            normalised_text = _normalised_support_text(text)
                            if normalised_text in {
                                _normalised_support_text(
                                    section.get("section_anchor")
                                ),
                                _normalised_support_text(
                                    source_evidence.get("title")
                                ),
                                _normalised_support_text(
                                    excerpt.get("source_locator")
                                ),
                            }:
                                errors.append(
                                    "run-manifest: venue verbatim excerpt "
                                    "must contain supporting text, not only "
                                    f"a heading: {excerpt_id}"
                                )
                            if isinstance(excerpt_id, str):
                                excerpts[excerpt_id] = text
                        if (
                            len(excerpt_id_list) != len(set(excerpt_id_list))
                        ):
                            errors.append(
                                "run-manifest: venue verbatim excerpt IDs "
                                "must be unique within a source section"
                            )
                        referenced_excerpt_ids: set[str] = set()
                        for claim in section.get("claims", []):
                            if not isinstance(claim, dict):
                                continue
                            claim_id = claim.get("claim_id")
                            if not isinstance(claim_id, str):
                                continue
                            if claim_id in source_claims:
                                errors.append(
                                    "run-manifest: venue source claim IDs "
                                    f"must be globally unique: {claim_id}"
                                )
                                continue
                            source_claims[claim_id] = claim
                            source_claim_locations[claim_id] = (
                                source_id,
                                section.get("section_anchor"),
                            )
                            referenced_excerpt_ids.update(
                                excerpt_id
                                for excerpt_id in claim.get(
                                    "excerpt_ids", []
                                )
                                if isinstance(excerpt_id, str)
                            )
                            errors.extend(
                                _validate_venue_claim_support(
                                    claim,
                                    excerpts,
                                    "run-manifest: venue source evidence",
                                )
                            )
                        if referenced_excerpt_ids != set(excerpts):
                            errors.append(
                                "run-manifest: venue source claims must "
                                "reference every and only verbatim excerpt "
                                "in their source section"
                            )
                    if len(source_excerpt_ids) != len(
                        set(source_excerpt_ids)
                    ):
                        errors.append(
                            "run-manifest: venue verbatim excerpt IDs must "
                            "be unique within one official source"
                        )
                    if len(source_locators) != len(set(source_locators)):
                        errors.append(
                            "run-manifest: venue verbatim source locators "
                            "must be unique within one official source"
                        )
                if isinstance(source_id, str):
                    source_sections[source_id] = {
                        anchor
                        for anchor in source.get(
                            "retrieved_section_anchors", []
                        )
                        if isinstance(anchor, str)
                    }
                try:
                    parsed = urlsplit(source.get("url"))
                    port = parsed.port
                except (TypeError, ValueError):
                    parsed = None
                    port = None
                host = (
                    parsed.hostname.casefold()
                    if parsed is not None
                    and isinstance(parsed.hostname, str)
                    else None
                )
                if (
                    parsed is None
                    or parsed.scheme != "https"
                    or not host
                    or host not in trusted_hosts
                    or parsed.username is not None
                    or parsed.password is not None
                    or port not in {None, 443}
                    or parsed.netloc.casefold()
                    not in {host, f"{host}:443"}
                ):
                    errors.append(
                        "run-manifest: venue source URL has invalid HTTPS "
                        "authority or is not approved by the release authority "
                        "registry: "
                        f"{source.get('url')}"
                    )
    if isinstance(profile_receipt, dict) and source_ids:
        rule_ids: list[str] = []
        for collection in ("criteria", "native_assessment_fields"):
            for rule in profile_receipt.get(collection, []):
                if not isinstance(rule, dict):
                    continue
                rule_id = (
                    rule.get("rule_id")
                    if collection == "criteria"
                    else rule.get("field_id")
                )
                if isinstance(rule_id, str):
                    rule_ids.append(rule_id)
                portable_criterion_ids = rule.get(
                    "portable_criterion_ids", []
                )
                unknown_criteria = set(portable_criterion_ids) - set(
                    _CANONICAL_CRITERIA
                )
                if unknown_criteria or not portable_criterion_ids:
                    errors.append(
                        "run-manifest: venue profile rule must map to known "
                        f"portable criteria: {rule_id}"
                    )
                unknown_sources = set(rule.get("source_ids", [])) - source_ids
                for unknown in sorted(unknown_sources):
                    errors.append(
                        "run-manifest: venue profile rule references unknown "
                        f"source ID: {unknown}"
                    )
                source_anchors = rule.get("source_anchors", [])
                anchored_source_ids = {
                    anchor.get("source_id")
                    for anchor in source_anchors
                    if isinstance(anchor, dict)
                }
                if anchored_source_ids != set(rule.get("source_ids", [])):
                    errors.append(
                        "run-manifest: venue profile rule source anchors must "
                        "cover every and only declared source ID"
                    )
                for anchor in source_anchors:
                    if not isinstance(anchor, dict):
                        continue
                    if anchor.get("section_anchor") not in source_sections.get(
                        anchor.get("source_id"), set()
                    ):
                        errors.append(
                            "run-manifest: venue profile rule section anchor "
                            "is absent from the retrieved source boundary"
                        )
                source_claim_ids = rule.get("source_claim_ids", [])
                referenced_source_claim_ids.update(
                    claim_id
                    for claim_id in source_claim_ids
                    if isinstance(claim_id, str)
                )
                expected_projection = _venue_rule_authority_projection(
                    collection,
                    rule,
                )
                expected_claim_kind = (
                    "criterion"
                    if collection == "criteria"
                    else "native_field"
                )
                claim_locations: set[tuple[str, str]] = set()
                for claim_id in source_claim_ids:
                    claim = source_claims.get(claim_id)
                    if not isinstance(claim, dict):
                        errors.append(
                            "run-manifest: venue profile rule references "
                            f"unknown source claim ID: {claim_id}"
                        )
                        continue
                    if (
                        claim.get("claim_kind") != expected_claim_kind
                        or claim.get("projection") != expected_projection
                    ):
                        errors.append(
                            "run-manifest: venue profile rule differs from "
                            f"its typed source claim projection: {rule_id}"
                        )
                    location = source_claim_locations.get(claim_id)
                    if isinstance(location, tuple):
                        claim_locations.add(location)
                declared_locations = {
                    (
                        anchor.get("source_id"),
                        anchor.get("section_anchor"),
                    )
                    for anchor in source_anchors
                    if isinstance(anchor, dict)
                }
                if claim_locations != declared_locations:
                    errors.append(
                        "run-manifest: venue source claims must exactly bind "
                        f"the declared source anchors: {rule_id}"
                    )
                if collection == "native_assessment_fields":
                    if any(
                        _contains_acceptance_metric_request(
                            rule.get(field, "")
                        )
                        for field in ("field_id", "prompt")
                    ):
                        errors.append(
                            "run-manifest: venue native field cannot request "
                            "an acceptance prediction"
                        )
                    field_type = rule.get("field_type")
                    minimum = rule.get("minimum")
                    maximum = rule.get("maximum")
                    labels = rule.get("allowed_labels", [])
                    anchors = rule.get("anchors", [])
                    if field_type == "categorical":
                        if (
                            not labels
                            or minimum is not None
                            or maximum is not None
                            or rule.get("direction") != "not_ordered"
                            or [
                                anchor.get("value")
                                for anchor in anchors
                                if isinstance(anchor, dict)
                            ]
                            != labels
                        ):
                            errors.append(
                                "run-manifest: categorical native field "
                                "requires exact label anchors, not-ordered "
                                "direction, and null numeric bounds"
                            )
                    elif field_type in {"integer_scale", "numeric_scale"}:
                        if (
                            not isinstance(minimum, (int, float))
                            or isinstance(minimum, bool)
                            or not isinstance(maximum, (int, float))
                            or isinstance(maximum, bool)
                            or minimum >= maximum
                            or labels
                            or len(anchors) < 2
                            or len(
                                {
                                    anchor.get("value")
                                    for anchor in anchors
                                    if isinstance(anchor, dict)
                                }
                            ) != len(anchors)
                            or {
                                minimum,
                                maximum,
                            }
                            - {
                                anchor.get("value")
                                for anchor in anchors
                                if isinstance(anchor, dict)
                            }
                            or rule.get("direction")
                            not in {
                                "higher_better",
                                "higher_worse",
                                "higher_more_favourable",
                                "higher_more_certain",
                            }
                        ):
                            errors.append(
                                "run-manifest: numeric native field requires "
                                "ordered bounds, endpoint anchors, explicit "
                                "direction, and no categorical labels"
                            )
                        if field_type == "integer_scale" and (
                            not isinstance(minimum, (int, float))
                            or isinstance(minimum, bool)
                            or not float(minimum).is_integer()
                            or not isinstance(maximum, (int, float))
                            or isinstance(maximum, bool)
                            or not float(maximum).is_integer()
                        ):
                            errors.append(
                                "run-manifest: integer native field bounds "
                                "must be integral"
                            )
                        for anchor in anchors:
                            value = (
                                anchor.get("value")
                                if isinstance(anchor, dict)
                                else None
                            )
                            if not isinstance(value, (int, float)) or isinstance(
                                value, bool
                            ) or (
                                isinstance(minimum, (int, float))
                                and isinstance(maximum, (int, float))
                                and not minimum <= value <= maximum
                            ):
                                errors.append(
                                    "run-manifest: numeric native field anchor "
                                    "must lie within its scale"
                                )
                            elif field_type == "integer_scale" and not float(
                                value
                            ).is_integer():
                                errors.append(
                                    "run-manifest: integer native field anchor "
                                    "must be integral"
                                )
                    elif field_type == "text" and (
                        minimum is not None
                        or maximum is not None
                        or labels
                        or anchors
                        or rule.get("direction") != "not_applicable"
                    ):
                        errors.append(
                            "run-manifest: text native field cannot declare "
                            "numeric or categorical scale metadata"
                        )
        if len(rule_ids) != len(set(rule_ids)):
            errors.append("run-manifest: venue profile rule IDs must be unique")
        if referenced_source_claim_ids != set(source_claims):
            errors.append(
                "run-manifest: venue profile must reference every and only "
                "typed claim in its source manifest"
            )
    return errors


def _validate_venue_assessment(
    target: Any,
    profile: Any,
    assessment: Any,
    coverage: Any,
    bundle_root: pathlib.Path,
    completion: Any,
) -> list[str]:
    prefix = "run-manifest: venue assessment"
    if not isinstance(assessment, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    if any(
        _contains_positive_acceptance_prediction(text)
        for text in _string_leaves(assessment)
    ):
        errors.append(
            f"{prefix}: assessment cannot contain an acceptance prediction"
        )
    venue = target.get("venue") if isinstance(target, dict) else None
    profile_status = profile.get("status") if isinstance(profile, dict) else None
    status = assessment.get("status")
    if venue == "unknown":
        if assessment != {
            "status": "not_applicable",
            "profile_id": None,
            "criteria": [],
            "native_fields": [],
            "limitations": [],
        }:
            errors.append(
                f"{prefix}: unknown venue requires an exact not-applicable "
                "assessment"
            )
        return errors
    if profile_status == "blocked":
        if (
            status != "blocked"
            or assessment.get("profile_id") is not None
            or assessment.get("criteria") != []
            or assessment.get("native_fields") != []
            or not assessment.get("limitations")
        ):
            errors.append(
                f"{prefix}: blocked venue profile requires a blocked empty "
                "assessment with an explicit limitation"
            )
        return errors
    if profile_status != "loaded":
        errors.append(
            f"{prefix}: known venue assessment requires a loaded or blocked "
            "profile"
        )
        return errors
    profile_receipt, _, profile_errors = _load_bound_json_receipt(
        bundle_root,
        profile.get("profile_locator"),
        profile.get("profile_sha256"),
        f"{prefix} profile",
    )
    errors.extend(profile_errors)
    if not isinstance(profile_receipt, dict):
        return errors
    if assessment.get("profile_id") != profile_receipt.get("profile_id"):
        errors.append(f"{prefix}: profile_id does not bind the loaded profile")
    if status not in {"completed", "blocked"}:
        errors.append(f"{prefix}: loaded profile requires completed or blocked")
    if status == "blocked" and (
        completion == "complete" or not assessment.get("limitations")
    ):
        errors.append(
            f"{prefix}: blocked venue assessment prevents complete status and "
            "requires a limitation"
        )
    has_blocked_component = False

    profile_criteria = {
        rule.get("rule_id"): rule
        for rule in profile_receipt.get("criteria", [])
        if isinstance(rule, dict)
    }
    coverage_rows = (
        coverage.get("criteria", [])
        if isinstance(coverage, dict)
        else []
    )
    coverage_by_id = {
        row.get("criterion_id"): row
        for row in coverage_rows
        if isinstance(row, dict)
        and isinstance(row.get("criterion_id"), str)
    }
    criterion_rows = assessment.get("criteria", [])
    criterion_ids = [
        row.get("rule_id") for row in criterion_rows if isinstance(row, dict)
    ]
    if (
        len(criterion_ids) != len(set(criterion_ids))
        or set(criterion_ids) != set(profile_criteria)
    ):
        errors.append(
            f"{prefix}: criteria must exactly cover every loaded venue rule"
        )
    for row in criterion_rows:
        if not isinstance(row, dict):
            continue
        row_status = row.get("assessment")
        finding_ids = row.get("finding_ids", [])
        profile_rule = profile_criteria.get(row.get("rule_id"), {})
        allowed_criteria = set(
            profile_rule.get("portable_criterion_ids", [])
            if isinstance(profile_rule, dict)
            else []
        )
        mapped_unresolved_findings = {
            finding_id
            for criterion_id in allowed_criteria
            for finding_id in coverage_by_id.get(
                criterion_id, {}
            ).get("finding_ids", [])
            if isinstance(finding_id, str)
        }
        mapped_unresolved_states = {
            coverage_by_id.get(criterion_id, {}).get("disposition")
            for criterion_id in allowed_criteria
        } & {"finding_linked", "needs_verification", "blocked"}
        evidence_finding_ids: set[str] = set()
        evidence_criterion_ids: set[str] = set()
        for evidence_ref in row.get("evidence", []):
            if not isinstance(evidence_ref, dict):
                continue
            criterion_id = evidence_ref.get("criterion_id")
            coverage_row = coverage_by_id.get(criterion_id)
            if criterion_id not in allowed_criteria:
                errors.append(
                    f"{prefix}: venue evidence exceeds the rule's portable "
                    f"criterion mapping: {row.get('rule_id')}"
                )
            if not isinstance(coverage_row, dict):
                errors.append(
                    f"{prefix}: venue evidence references unknown canonical "
                    f"criterion: {criterion_id}"
                )
                continue
            if isinstance(criterion_id, str):
                evidence_criterion_ids.add(criterion_id)
            if evidence_ref.get("reference_kind") == "coverage_evidence":
                index = evidence_ref.get("evidence_index")
                evidence_items = coverage_row.get("evidence", [])
                if (
                    not isinstance(index, int)
                    or isinstance(index, bool)
                    or index < 0
                    or index >= len(evidence_items)
                ):
                    errors.append(
                        f"{prefix}: venue evidence index does not resolve to "
                        f"canonical coverage: {criterion_id}"
                    )
            elif evidence_ref.get("reference_kind") == "finding":
                finding_id = evidence_ref.get("finding_id")
                if finding_id not in coverage_row.get("finding_ids", []):
                    errors.append(
                        f"{prefix}: venue finding reference is not linked by "
                        f"canonical coverage: {finding_id}"
                    )
                elif isinstance(finding_id, str):
                    evidence_finding_ids.add(finding_id)
        expected_row_status = (
            "blocked"
            if "blocked" in mapped_unresolved_states
            else (
                "needs_verification"
                if "needs_verification" in mapped_unresolved_states
                else (
                    "concern"
                    if mapped_unresolved_findings
                    else "satisfied"
                )
            )
        )
        if row_status == "satisfied" and finding_ids:
            errors.append(
                f"{prefix}: satisfied venue rule cannot link a finding"
            )
        if row_status == "satisfied" and expected_row_status != "satisfied":
            errors.append(
                f"{prefix}: additive venue overlay cannot mark a mapped "
                "portable concern as satisfied"
            )
        if row_status != expected_row_status:
            errors.append(
                f"{prefix}: additive venue status does not derive from the "
                f"mapped portable coverage: {row.get('rule_id')}"
            )
        if set(finding_ids) != mapped_unresolved_findings:
            errors.append(
                f"{prefix}: venue rule must exactly account for every mapped "
                f"portable finding: {row.get('rule_id')}"
            )
        if evidence_finding_ids != mapped_unresolved_findings:
            errors.append(
                f"{prefix}: venue evidence must exactly reference every mapped "
                f"portable finding: {row.get('rule_id')}"
            )
        if evidence_criterion_ids != allowed_criteria:
            errors.append(
                f"{prefix}: venue evidence must exactly cover every mapped "
                f"portable criterion: {row.get('rule_id')}"
            )
        if expected_row_status in {"needs_verification", "blocked"}:
            if status == "completed":
                errors.append(
                    f"{prefix}: completed status cannot hide an unresolved "
                    "venue rule"
                )
            has_blocked_component = True

    profile_fields = {
        field.get("field_id"): field
        for field in profile_receipt.get("native_assessment_fields", [])
        if isinstance(field, dict)
    }
    native_rows = assessment.get("native_fields", [])
    native_ids = [
        row.get("field_id") for row in native_rows if isinstance(row, dict)
    ]
    if (
        len(native_ids) != len(set(native_ids))
        or set(native_ids) != set(profile_fields)
    ):
        errors.append(
            f"{prefix}: native fields must exactly cover the loaded venue form"
        )
    for row in native_rows:
        if not isinstance(row, dict):
            continue
        field_id = row.get("field_id")
        field = profile_fields.get(field_id)
        if not isinstance(field, dict):
            continue
        if row.get("role") != field.get("role"):
            errors.append(
                f"{prefix}: native field role differs from profile: {field_id}"
            )
        expected_views = (
            ["reviewer_report", "ae_assessment", "review_summary"]
            if field.get("role") == "reviewer"
            else ["ae_assessment", "review_summary"]
        )
        if row.get("reported_in") != expected_views:
            errors.append(
                f"{prefix}: native field is not bound to the required human "
                f"views: {field_id}"
            )
        result_status = row.get("status")
        value = row.get("value")
        basis = row.get("basis", {})
        basis_kind = basis.get("kind") if isinstance(basis, dict) else None
        basis_criteria = (
            basis.get("criterion_ids", [])
            if isinstance(basis, dict)
            else []
        )
        basis_findings = (
            basis.get("finding_ids", [])
            if isinstance(basis, dict)
            else []
        )
        mapped_criteria = set(field.get("portable_criterion_ids", []))
        mapped_findings = {
            finding_id
            for criterion_id in mapped_criteria
            for finding_id in coverage_by_id.get(
                criterion_id, {}
            ).get("finding_ids", [])
            if isinstance(finding_id, str)
        }
        mapped_unresolved_dispositions = {
            coverage_by_id.get(criterion_id, {}).get("disposition")
            for criterion_id in mapped_criteria
        } & {"needs_verification", "blocked"}
        if (
            result_status in {"provided", "blocked"}
            and set(basis_criteria) != mapped_criteria
        ):
            errors.append(
                f"{prefix}: native field basis must exactly cover its portable "
                f"criterion mapping: {field_id}"
            )
        for finding_id in basis_findings:
            if not any(
                finding_id in coverage_by_id.get(criterion_id, {}).get(
                    "finding_ids", []
                )
                for criterion_id in basis_criteria
            ):
                errors.append(
                    f"{prefix}: native field basis finding is not linked by "
                    f"canonical coverage: {field_id}/{finding_id}"
                )
        if (
            result_status in {"provided", "blocked"}
            and set(basis_findings) != mapped_findings
        ):
            errors.append(
                f"{prefix}: native field basis must exactly account for mapped "
                f"portable findings: {field_id}"
            )
        if (
            field.get("required") is True
            and result_status != "provided"
            and not (status == "blocked" and result_status == "blocked")
        ):
            errors.append(
                f"{prefix}: required native field is not provided: {field_id}"
            )
        if result_status != "provided":
            if value is not None:
                errors.append(
                    f"{prefix}: unprovided native field must have null value: "
                    f"{field_id}"
                )
            if result_status == "blocked" and status == "completed":
                errors.append(
                    f"{prefix}: completed status cannot hide blocked native "
                    f"field: {field_id}"
                )
            if result_status == "blocked":
                if not mapped_unresolved_dispositions:
                    errors.append(
                        f"{prefix}: blocked native field requires mapped "
                        f"unresolved portable coverage: {field_id}"
                    )
                has_blocked_component = True
            expected_basis_kind = (
                "blocked"
                if result_status == "blocked"
                else "not_applicable"
            )
            if (
                basis_kind != expected_basis_kind
                or (
                    result_status == "not_applicable"
                    and (basis_criteria or basis_findings)
                )
            ):
                errors.append(
                    f"{prefix}: unprovided native field has inconsistent "
                    f"basis: {field_id}"
                )
            continue
        if (
            basis_kind not in {"portable_evidence", "bounded_judgement"}
            or not basis_criteria
        ):
            errors.append(
                f"{prefix}: provided native field requires a typed portable "
                f"evidence or bounded-judgement basis: {field_id}"
            )
        if basis_kind == "portable_evidence" and not any(
            coverage_by_id.get(criterion_id, {}).get("evidence")
            or coverage_by_id.get(criterion_id, {}).get("finding_ids")
            for criterion_id in basis_criteria
        ):
            errors.append(
                f"{prefix}: portable-evidence native basis does not resolve "
                f"to canonical evidence: {field_id}"
            )
        field_type = field.get("field_type")
        if field_type == "categorical":
            if value not in field.get("allowed_labels", []):
                errors.append(
                    f"{prefix}: categorical native value is outside the "
                    f"profile labels: {field_id}"
                )
        elif field_type in {"integer_scale", "numeric_scale"}:
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not isinstance(field.get("minimum"), (int, float))
                or not isinstance(field.get("maximum"), (int, float))
                or not field.get("minimum") <= value <= field.get("maximum")
            ):
                errors.append(
                    f"{prefix}: numeric native value is outside the profile "
                    f"scale: {field_id}"
                )
            elif field_type == "integer_scale" and not float(value).is_integer():
                errors.append(
                    f"{prefix}: integer native value must be integral: {field_id}"
                )
        elif field_type == "text" and not _is_nonblank_string(value):
            errors.append(
                f"{prefix}: text native value must be nonblank: {field_id}"
            )
    if status == "blocked" and not has_blocked_component:
        errors.append(
            f"{prefix}: blocked status requires an actually blocked rule or "
            "native field"
        )
    return errors


def validate_run_manifest(
    data: dict,
    coverage_matrix: dict,
    bundle_root: pathlib.Path,
    *,
    evidence_root: pathlib.Path,
) -> list[str]:
    structural_errors = validate_json_schema_document(
        data,
        bundle_root,
        "schemas/run-manifest.schema.json",
        "run-manifest",
    )
    if structural_errors:
        return structural_errors
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["run-manifest: must be an object"]
    required = {
        "schema_version",
        "run_id",
        "created_at",
        "finalized_at",
        "review_goal",
        "review_kind",
        "authorisation",
        "confidentiality",
        "review_only",
        "input_artifacts",
        "source_pdf_alignment",
        "target",
        "venue_profile",
        "venue_assessment",
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
    run_created_time = _parse_rfc3339_datetime(data.get("created_at"))
    run_finalized_time = _parse_rfc3339_datetime(data.get("finalized_at"))
    if (
        run_created_time is None
        or run_finalized_time is None
        or run_finalized_time < run_created_time
        or (
            completion == "complete"
            and run_finalized_time == run_created_time
        )
    ):
        errors.append(
            "run-manifest: finalization chronology must follow run creation"
        )

    authorisation = data.get("authorisation")
    authority_gate_open = (
        isinstance(authorisation, dict)
        and authorisation.get("authorised") is True
        and authorisation.get("policy_status") == "permitted"
    )
    if not isinstance(authorisation, dict):
        errors.append("run-manifest: authorisation must be an object")
    elif not authority_gate_open and completion != "blocked":
        errors.append(
            "run-manifest: absent authority or non-permitted policy requires "
            "a blocked preflight stop"
        )
    elif authority_gate_open and authorisation.get("capacity") == "unknown":
        errors.append(
            "run-manifest: authorised execution requires a known review "
            "capacity"
        )
    confidentiality = data.get("confidentiality")
    if not isinstance(confidentiality, dict):
        errors.append("run-manifest: confidentiality must be an object")
    else:
        if confidentiality.get("classification") not in {
            "unknown",
            "public",
            "author_owned_draft",
            "official_confidential_submission",
        }:
            errors.append("run-manifest: confidentiality classification is invalid")
        if (
            authority_gate_open
            and confidentiality.get("classification") == "unknown"
        ):
            errors.append(
                "run-manifest: authorised execution requires a known "
                "confidentiality classification"
            )
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
    if authority_gate_open and any(
        re.search(
            r"\b(?:replace[- ]with|replace\s+template|template\s+only)\b",
            value,
            re.IGNORECASE,
        )
        for value in _string_leaves(data)
    ):
        errors.append(
            "run-manifest: authorised execution cannot retain template "
            "sentinels"
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

    root = _normalise_root(bundle_root)
    run_evidence_root = _normalise_root(evidence_root)
    uses_evidence_bytes = False
    input_artifacts = data.get("input_artifacts", [])
    artifact_id_list = [
        artifact.get("artifact_id")
        for artifact in input_artifacts
        if isinstance(artifact, dict)
        and isinstance(artifact.get("artifact_id"), str)
    ]
    artifact_by_id = {
        artifact.get("artifact_id"): artifact
        for artifact in input_artifacts
        if isinstance(artifact, dict)
        and isinstance(artifact.get("artifact_id"), str)
    }
    artifact_ids = set(artifact_id_list)
    if len(artifact_id_list) != len(artifact_ids):
        errors.append("run-manifest: duplicate artifact_id")
    input_file_identities: dict[tuple[int, int], str] = {}
    for index, artifact in enumerate(input_artifacts):
        prefix = f"run-manifest: input_artifact[{index}]"
        if not isinstance(artifact, dict):
            continue
        if artifact.get("state") == "declared":
            if completion == "complete":
                errors.append(
                    f"{prefix}: declared input is not frozen and prevents "
                    "complete status"
                )
            continue
        uses_evidence_bytes = True
        locator = artifact.get("locator")
        digest = artifact.get("sha256")
        try:
            path = _safe_bundle_file(run_evidence_root, locator)
        except ValueError as exc:
            errors.append(f"{prefix}: frozen input locator is invalid: {exc}")
            continue
        try:
            raw = path.read_bytes()
            stat = path.stat()
        except OSError as exc:
            errors.append(f"{prefix}: frozen input is unreadable: {exc}")
            continue
        if not raw:
            errors.append(f"{prefix}: frozen input cannot be empty")
        identity = (stat.st_dev, stat.st_ino)
        if identity in input_file_identities:
            errors.append(
                f"{prefix}: frozen input aliases artifact "
                f"{input_file_identities[identity]}"
            )
        else:
            input_file_identities[identity] = str(artifact.get("artifact_id"))
        actual = hashlib.sha256(raw).hexdigest()
        if actual != digest:
            errors.append(f"{prefix}: frozen input hash mismatch")

    delta_input_kinds = {
        "prior_run",
        "prior_ledger",
        "prior_source",
        "author_response",
    }
    delta_inputs_by_kind = {
        input_kind: [
            artifact
            for artifact in input_artifacts
            if isinstance(artifact, dict)
            and artifact.get("kind") == input_kind
        ]
        for input_kind in delta_input_kinds
    }
    if kind == "delta":
        for input_kind in sorted(delta_input_kinds):
            artifacts = delta_inputs_by_kind[input_kind]
            label = input_kind.replace("_", "-")
            if len(artifacts) != 1:
                errors.append(
                    "run-manifest: delta review requires exactly one "
                    f"{label} frozen input artifact"
                )
            elif artifacts[0].get("state") != "frozen":
                errors.append(
                    f"run-manifest: delta {label} must be a frozen input"
                )
    elif any(delta_inputs_by_kind.values()):
        errors.append(
            "run-manifest: initial review cannot claim prior-run, prior-ledger, "
            "prior-source, or author-response inputs"
        )

    frozen_sources = [
        artifact
        for artifact in input_artifacts
        if isinstance(artifact, dict)
        and artifact.get("kind") == "source"
        and artifact.get("state") == "frozen"
    ]
    frozen_pdfs = [
        artifact
        for artifact in input_artifacts
        if isinstance(artifact, dict)
        and artifact.get("kind") == "pdf"
        and artifact.get("state") == "frozen"
    ]
    alignment_receipt_valid = False
    parsed_pdf_page_count: int | None = None
    if isinstance(alignment, dict):
        if alignment.get("status") == "matched":
            if len(frozen_sources) != 1 or len(frozen_pdfs) != 1:
                errors.append(
                    "run-manifest: matched alignment requires a unique "
                    "source/PDF pair"
                )
            shared_lineages = {
                artifact.get("lineage_id") for artifact in frozen_sources
            } & {artifact.get("lineage_id") for artifact in frozen_pdfs}
            if not shared_lineages:
                errors.append(
                    "run-manifest: matched source/PDF status requires frozen "
                    "source and PDF bytes with a shared lineage"
                )
            if (
                len(frozen_sources) == 1
                and len(frozen_pdfs) == 1
                and frozen_sources[0].get("sha256")
                == frozen_pdfs[0].get("sha256")
            ):
                errors.append(
                    "run-manifest: source and PDF content must be distinct"
                )
            if len(frozen_pdfs) == 1:
                try:
                    pdf_path = _safe_bundle_file(
                        run_evidence_root, frozen_pdfs[0].get("locator")
                    )
                    pdf_raw = pdf_path.read_bytes()
                except (ValueError, OSError):
                    pdf_raw = b""
                    pdf_path = None
                if not pdf_raw.startswith(b"%PDF-"):
                    errors.append(
                        "run-manifest: PDF artifact does not have a valid PDF "
                        "header"
                    )
                if pdf_path is not None:
                    (
                        parsed_pdf_page_count,
                        pdf_parse_error,
                    ) = _parsed_pdf_page_count(pdf_path)
                    if pdf_parse_error is not None:
                        errors.append(
                            "run-manifest: PDF parser could not verify the "
                            f"frozen PDF: {pdf_parse_error}"
                        )
            source_id = alignment.get("source_artifact_id")
            pdf_id = alignment.get("pdf_artifact_id")
            if (
                len(frozen_sources) == 1
                and source_id != frozen_sources[0].get("artifact_id")
            ):
                errors.append(
                    "run-manifest: alignment source_artifact_id does not bind "
                    "the unique frozen source"
                )
            if (
                len(frozen_pdfs) == 1
                and pdf_id != frozen_pdfs[0].get("artifact_id")
            ):
                errors.append(
                    "run-manifest: alignment pdf_artifact_id does not bind "
                    "the unique frozen PDF"
                )
            receipt, _, receipt_errors = _load_bound_json_receipt(
                run_evidence_root,
                alignment.get("receipt_locator"),
                alignment.get("receipt_sha256"),
                "run-manifest: source/PDF alignment receipt",
            )
            errors.extend(receipt_errors)
            if isinstance(receipt, dict):
                receipt_structural_errors = validate_json_schema_document(
                    receipt,
                    root,
                    "schemas/source-pdf-alignment-receipt.schema.json",
                    "run-manifest: source/PDF alignment receipt",
                )
                errors.extend(receipt_structural_errors)
                check_ids = [
                    check.get("check_id")
                    for check in receipt.get("checks", [])
                    if isinstance(check, dict)
                ]
                if (
                    len(check_ids) != len(set(check_ids))
                    or not {"title", "section_sequence"}.issubset(
                        set(check_ids)
                    )
                ):
                    errors.append(
                        "run-manifest: alignment receipt check IDs must be "
                        "unique and include title plus section_sequence"
                    )
                if (
                    kind == "delta"
                    and completion == "complete"
                    and "revision_marker" not in check_ids
                ):
                    errors.append(
                        "run-manifest: delta alignment requires a "
                        "revision_marker"
                    )
                source_evidence_keys = [
                    (
                        check.get("source_start_byte"),
                        check.get("source_end_byte"),
                        check.get("source_occurrence"),
                    )
                    for check in receipt.get("checks", [])
                    if isinstance(check, dict)
                ]
                pdf_evidence_keys = [
                    (
                        check.get("pdf_page"),
                        check.get("pdf_excerpt_sha256"),
                        check.get("pdf_occurrence"),
                    )
                    for check in receipt.get("checks", [])
                    if isinstance(check, dict)
                ]
                normalised_excerpts = [
                    _normalised_alignment_excerpt(
                        check.get("source_excerpt")
                    )
                    for check in receipt.get("checks", [])
                    if isinstance(check, dict)
                ]
                if (
                    len(source_evidence_keys) != len(
                        set(source_evidence_keys)
                    )
                    or len(pdf_evidence_keys) != len(set(pdf_evidence_keys))
                    or len(normalised_excerpts)
                    != len(set(normalised_excerpts))
                ):
                    errors.append(
                        "run-manifest: alignment checks must use distinct "
                        "evidence"
                    )
                alignment_recorded_time = _parse_rfc3339_datetime(
                    receipt.get("recorded_at")
                )
                if (
                    alignment_recorded_time is None
                    or run_created_time is None
                    or run_finalized_time is None
                    or alignment_recorded_time < run_created_time
                    or alignment_recorded_time > run_finalized_time
                ):
                    errors.append(
                        "run-manifest: alignment receipt chronology must "
                        "fall within the run"
                    )
                pdf_integrity = receipt.get("pdf_integrity")
                alignment_check_errors = False
                if isinstance(pdf_integrity, dict):
                    if (
                        pdf_integrity.get("method") != "parsed"
                        or pdf_integrity.get("tool") != "pdfinfo"
                    ):
                        errors.append(
                            "run-manifest: alignment receipt must record the "
                            "validator-owned PDF parser"
                        )
                    if (
                        parsed_pdf_page_count is not None
                        and pdf_integrity.get("page_count")
                        != parsed_pdf_page_count
                    ):
                        errors.append(
                            "run-manifest: alignment receipt page count does "
                            "not match the PDF parser"
                        )
                    for check in receipt.get("checks", []):
                        if not isinstance(check, dict):
                            continue
                        page = check.get("pdf_page")
                        occurrence = check.get("pdf_occurrence")
                        anchor = check.get("pdf_anchor")
                        if (
                            not isinstance(page, int)
                            or isinstance(page, bool)
                            or not isinstance(occurrence, int)
                            or isinstance(occurrence, bool)
                            or anchor
                            != f"pdf:page-{page};occurrence:{occurrence}"
                            or parsed_pdf_page_count is None
                            or page > parsed_pdf_page_count
                        ):
                            alignment_check_errors = True
                            errors.append(
                                "run-manifest: alignment receipt PDF anchor "
                                "does not resolve to a parsed page"
                            )
                            continue
                        source_excerpt = check.get("source_excerpt")
                        source_verification = {
                            "excerpt": source_excerpt,
                            "start_byte": check.get("source_start_byte"),
                            "end_byte": check.get("source_end_byte"),
                            "occurrence": check.get("source_occurrence"),
                        }
                        source_evidence = {
                            "source_anchor": check.get("source_anchor")
                        }
                        try:
                            source_path = _safe_bundle_file(
                                run_evidence_root,
                                frozen_sources[0].get("locator"),
                            )
                            source_bytes = source_path.read_bytes()
                            source_bytes.decode("utf-8")
                        except (
                            IndexError,
                            ValueError,
                            OSError,
                            UnicodeDecodeError,
                        ) as exc:
                            alignment_check_errors = True
                            errors.append(
                                "run-manifest: alignment source bytes are "
                                f"unavailable: {exc}"
                            )
                        else:
                            source_span_errors, _ = (
                                _validate_exact_span_against_source(
                                    source_evidence,
                                    source_verification,
                                    source_bytes,
                                    "run-manifest: alignment source anchor",
                                )
                            )
                            if (
                                source_span_errors
                                or not _is_nonblank_string(source_excerpt)
                                or check.get("source_excerpt_sha256")
                                != hashlib.sha256(
                                    str(source_excerpt).encode("utf-8")
                                ).hexdigest()
                            ):
                                alignment_check_errors = True
                                errors.extend(source_span_errors)
                                errors.append(
                                    "run-manifest: alignment source anchor "
                                    "is not recomputable"
                                )
                        if pdf_path is None:
                            alignment_check_errors = True
                            continue
                        page_text, extraction_error = (
                            _extracted_pdf_page_text(pdf_path, page)
                        )
                        if extraction_error is not None or page_text is None:
                            alignment_check_errors = True
                            errors.append(
                                "run-manifest: alignment PDF text extraction "
                                f"failed: {extraction_error}"
                            )
                            continue
                        pdf_excerpt = check.get("pdf_excerpt")
                        pdf_excerpt_bytes = str(pdf_excerpt).encode("utf-8")
                        page_text_bytes = page_text.encode("utf-8")
                        pdf_offsets = _exact_occurrence_offsets(
                            page_text_bytes,
                            pdf_excerpt_bytes,
                        )
                        if (
                            not _is_nonblank_string(pdf_excerpt)
                            or len("".join(str(pdf_excerpt).split())) < 4
                            or check.get("pdf_excerpt_sha256")
                            != hashlib.sha256(
                                pdf_excerpt_bytes
                            ).hexdigest()
                            or check.get("pdf_page_text_sha256")
                            != hashlib.sha256(
                                page_text_bytes
                            ).hexdigest()
                            or occurrence > len(pdf_offsets)
                        ):
                            alignment_check_errors = True
                            errors.append(
                                "run-manifest: alignment PDF anchor is not "
                                "recomputable from extracted page text"
                            )
                        if (
                            _normalised_alignment_excerpt(source_excerpt)
                            != _normalised_alignment_excerpt(pdf_excerpt)
                        ):
                            alignment_check_errors = True
                            errors.append(
                                "run-manifest: alignment source and PDF "
                                "excerpts do not establish the same check"
                            )
                expected_alignment = {
                    "source_artifact_id": source_id,
                    "pdf_artifact_id": pdf_id,
                    "source_sha256":
                        frozen_sources[0].get("sha256")
                        if len(frozen_sources) == 1
                        else None,
                    "pdf_sha256":
                        frozen_pdfs[0].get("sha256")
                        if len(frozen_pdfs) == 1
                        else None,
                    "result": "matched",
                }
                binding_errors = False
                for field, expected in expected_alignment.items():
                    if receipt.get(field) != expected:
                        binding_errors = True
                        errors.append(
                            "run-manifest: source/PDF alignment receipt "
                            f"{field} does not bind the frozen pair"
                        )
                alignment_receipt_valid = (
                    not receipt_errors
                    and not receipt_structural_errors
                    and not binding_errors
                    and not alignment_check_errors
                    and alignment.get("verified") is True
                )
        elif alignment.get("status") == "source_only_verified":
            if (
                len(frozen_sources) != 1
                or alignment.get("source_artifact_id")
                != (
                    frozen_sources[0].get("artifact_id")
                    if len(frozen_sources) == 1
                    else None
                )
                or bool(frozen_pdfs)
                or alignment.get("pdf_artifact_id") is not None
                or alignment.get("receipt_locator") is not None
                or alignment.get("receipt_sha256") is not None
            ):
                errors.append(
                    "run-manifest: source-only alignment must bind exactly one "
                    "frozen source and cannot claim a PDF receipt"
                )
        elif any(
            alignment.get(field) is not None
            for field in (
                "source_artifact_id",
                "pdf_artifact_id",
                "receipt_locator",
                "receipt_sha256",
            )
        ):
            errors.append(
                "run-manifest: unmatched alignment cannot claim bound source/PDF "
                "receipt fields"
            )

    output_artifacts = data.get("output_artifacts", {})
    produced_output_paths: dict[str, pathlib.Path] = {}
    output_file_identities: dict[tuple[int, int], str] = {}
    if isinstance(output_artifacts, dict):
        protected_output_hashes: dict[str, str] = {}
        for name, artifact in output_artifacts.items():
            prefix = f"run-manifest: output_artifact[{name}]"
            if not isinstance(artifact, dict):
                continue
            if artifact.get("status") == "not_produced":
                if completion == "complete":
                    errors.append(
                        f"{prefix}: missing canonical output prevents complete "
                        "status"
                    )
                continue
            uses_evidence_bytes = True
            locator = artifact.get("locator")
            digest = artifact.get("sha256")
            try:
                path = _safe_bundle_file(run_evidence_root, locator)
            except ValueError as exc:
                errors.append(
                    f"{prefix}: produced output locator is invalid: {exc}"
                )
                continue
            try:
                raw = path.read_bytes()
                stat = path.stat()
            except OSError as exc:
                errors.append(f"{prefix}: produced output is unreadable: {exc}")
                continue
            if hashlib.sha256(raw).hexdigest() != digest:
                errors.append(f"{prefix}: produced output hash mismatch")
            if name in _HUMAN_OUTPUT_HEADINGS and _is_sha256(digest):
                previous_name = protected_output_hashes.get(digest)
                if previous_name is not None:
                    errors.append(
                        f"{prefix}: human output content is reused across "
                        f"distinct roles ({previous_name}, {name})"
                    )
                else:
                    protected_output_hashes[digest] = name
            if not raw.strip():
                errors.append(f"{prefix}: produced output cannot be empty")
            identity = (stat.st_dev, stat.st_ino)
            if identity in input_file_identities:
                errors.append(
                    f"{prefix}: produced output aliases frozen input "
                    f"{input_file_identities[identity]}"
                )
            if identity in output_file_identities:
                errors.append(
                    f"{prefix}: produced output aliases output "
                    f"{output_file_identities[identity]}"
                )
            else:
                output_file_identities[identity] = name
            if name in _HUMAN_OUTPUT_HEADINGS:
                errors.extend(
                    _validate_human_output(
                        name,
                        raw,
                        run_id,
                        completion,
                    )
                )
            produced_output_paths[name] = path

    if uses_evidence_bytes and _roots_overlap(root, run_evidence_root):
        errors.append(
            "run-manifest: evidence root must be physically separate from the "
            "portable bundle root"
        )
    evidence_role_by_locator: dict[str, str] = {}

    def register_evidence_locator(locator: Any, role: str) -> None:
        if not _is_canonical_relative_locator(locator):
            return
        previous = evidence_role_by_locator.get(locator)
        if previous is not None and previous != role:
            errors.append(
                "run-manifest: evidence locator is reused across roles: "
                f"{locator} ({previous}, {role})"
            )
        else:
            evidence_role_by_locator[locator] = role

    for artifact in input_artifacts:
        if isinstance(artifact, dict) and artifact.get("state") == "frozen":
            register_evidence_locator(
                artifact.get("locator"),
                f"input:{artifact.get('artifact_id')}",
            )
    for name, artifact in output_artifacts.items():
        if isinstance(artifact, dict) and artifact.get("status") == "produced":
            register_evidence_locator(
                artifact.get("locator"),
                f"output:{name}",
            )
    if (
        isinstance(alignment, dict)
        and alignment.get("status") == "matched"
    ):
        register_evidence_locator(
            alignment.get("receipt_locator"),
            "source-pdf-alignment-receipt",
        )
    errors.extend(
        _validate_venue_profile_binding(
            data.get("target"),
            data.get("venue_profile"),
            root,
            completion,
        )
    )
    errors.extend(
        _validate_venue_assessment(
            data.get("target"),
            data.get("venue_profile"),
            data.get("venue_assessment"),
            data.get("coverage"),
            root,
            completion,
        )
    )
    try:
        canonical_coverage = load_review_coverage(root)
    except ValueError as exc:
        errors.append(f"run-manifest: canonical coverage unavailable: {exc}")
        canonical_coverage = {}
    if coverage_matrix != canonical_coverage:
        errors.append("run-manifest: supplied coverage matrix is not canonical")
    coverage = data.get("coverage")
    canonical_ids = _coverage_ids(canonical_coverage)
    canonical_rows = {
        row.get("criterion_id"): row
        for row in canonical_coverage.get("criteria", [])
        if isinstance(row, dict)
        and isinstance(row.get("criterion_id"), str)
    }
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
            elif applicability not in canonical_rows.get(
                row.get("criterion_id"), {}
            ).get("applicability_states", []):
                errors.append(
                    f"{prefix}: applicability is forbidden by the canonical "
                    "criterion contract"
                )
            if row.get("criterion_id") == "RC-DELTA-LINEAGE":
                expected_applicability = (
                    "applicable" if kind == "delta" else "inapplicable"
                )
                if applicability != expected_applicability:
                    errors.append(
                        f"{prefix}: delta-lineage applicability disagrees with "
                        f"{kind} review kind"
                    )
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
            if disposition in {
                "needs_verification",
                "blocked",
            } and completion == "complete":
                errors.append(
                    f"{prefix}: unresolved criterion disposition requires "
                    "partial or blocked completion"
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

    runtime_value = data.get("runtime_profile")
    adapter_active = isinstance(runtime_value, dict)
    runtime = runtime_value if adapter_active else {}
    manifest: dict = {}
    if adapter_active:
        try:
            manifest = load_adapter_manifest(root)
        except ValueError as exc:
            errors.append(f"run-manifest: adapter manifest unavailable: {exc}")
        else:
            errors.extend(validate_adapter_manifest(manifest, root))
    claim = runtime.get("compatibility_claim")
    configured_claim = claim in {
        "evaluation_pending",
        "configured-and-evaluated",
        "runtime-attested",
    }
    if adapter_active and (
        runtime.get("configuration_proof") is not None
        or runtime.get("model_validation", {}).get("status") != "not_run"
        or runtime.get("mode_validation", {}).get("status") != "not_run"
    ) and _roots_overlap(root, run_evidence_root):
        errors.append(
            "run-manifest: runtime evidence root must be physically separate "
            "from the portable bundle root"
        )
    root_proof_sha256: str | None = None
    root_configuration_receipt: dict | None = None
    assurance_times: list[datetime] = []
    if adapter_active:
        root_proof = runtime.get("configuration_proof")
        if isinstance(root_proof, dict):
            register_evidence_locator(
                root_proof.get("locator"), "root:configuration"
            )
        for control in ("model", "mode"):
            state = runtime.get(f"{control}_validation")
            if isinstance(state, dict):
                register_evidence_locator(
                    state.get("evidence_locator"),
                    f"root:{control}-validation",
                )
        (
            root_proof_errors,
            root_proof_sha256,
            root_configuration_receipt,
        ) = _validate_configuration_proof(
            runtime.get("configuration_proof"),
            "run-manifest: root",
            "root",
            run_id if isinstance(run_id, str) else "",
            bundle_root=root,
            evidence_root=run_evidence_root,
            requested_model=runtime.get("requested_model"),
            requested_mode=runtime.get("requested_mode"),
            requested_sandbox=None,
            agent_or_task_identifier=None,
            fork_policy=None,
            leaf_only=None,
            input_artifact_ids=None,
            dependency_task_ids=None,
            bundle_input_artifacts=None,
            input_records=None,
            input_snapshot_sha256=None,
            task_effects=None,
            report_contract=None,
            stop_condition=None,
            configuration_source=runtime.get("configuration_source"),
            fallback_policy=runtime.get("adapter_controlled_fallback"),
            surface=runtime.get("surface"),
            host_build=runtime.get("host_build"),
            adapter_sha256=runtime.get("adapter_sha256"),
            compatibility_payload_sha256=runtime.get(
                "compatibility_payload_sha256"
            ),
            selected_candidate_id=runtime.get("selected_candidate_id"),
            promotion_record_sha256=runtime.get(
                "promotion_record_sha256"
            ),
            trigger=None,
            assigned_criterion_ids=None,
            required=configured_claim,
        )
        errors.extend(root_proof_errors)
        root_configuration_time = (
            _parse_rfc3339_datetime(
                root_configuration_receipt.get("recorded_at")
            )
            if isinstance(root_configuration_receipt, dict)
            else None
        )
        run_created_time = _parse_rfc3339_datetime(data.get("created_at"))
        if root_configuration_time is not None:
            assurance_times.append(root_configuration_time)
        if (
            root_configuration_time is not None
            and run_created_time is not None
            and root_configuration_time < run_created_time
        ):
            errors.append(
                "run-manifest: root configuration chronology must follow "
                "run creation"
            )
        for control, value, label in (
            ("model", "gpt-5.6-sol", "model"),
            ("mode", "ultra", "mode"),
        ):
            errors.extend(
                _validate_validation_state(
                    runtime.get(f"{control}_validation"),
                    f"run-manifest: root {label}",
                    bundle_root=root,
                    evidence_root=run_evidence_root,
                    subject_kind="root",
                    subject_id=run_id if isinstance(run_id, str) else "",
                    control=control,
                    requested_value=value,
                    configuration_proof_locator=(
                        runtime.get("configuration_proof", {}).get("locator")
                        if isinstance(runtime.get("configuration_proof"), dict)
                        else None
                    ),
                    configuration_proof_sha256=root_proof_sha256,
                    configuration_receipt=root_configuration_receipt,
                    require_passed=configured_claim,
                    observed_times=assurance_times,
                )
            )
    if configured_claim:
        if not adapter_active:
            errors.append(
                "run-manifest: compatibility claim requires an activated adapter"
            )
        elif runtime.get("requested_model") != "gpt-5.6-sol" or (
            runtime.get("requested_mode") != "ultra"
        ):
            errors.append(
                "run-manifest: adapter root must request gpt-5.6-sol + ultra"
            )
        if adapter_active and (
            runtime.get("configuration_source")
            != "adapter-controlled root dispatch"
        ):
            errors.append(
                "run-manifest: root configuration source must be the "
                "adapter-controlled dispatch record"
            )
        if adapter_active and (
            runtime.get("adapter_controlled_fallback")
            != "prohibited_and_checked"
        ):
            errors.append(
                "run-manifest: root fallback must be prohibited and checked"
            )
    if adapter_active and runtime.get("adapter_sha256") != manifest.get(
        "adapter_payload_sha256"
    ):
        errors.append("run-manifest: adapter SHA does not match adapter manifest")
    if adapter_active and runtime.get(
        "compatibility_payload_sha256"
    ) != manifest.get("compatibility_payload_sha256"):
        errors.append(
            "run-manifest: compatibility payload SHA does not match "
            "adapter manifest"
        )
    if adapter_active and runtime.get("selected_candidate_id") != manifest.get(
        "selected_candidate_id"
    ):
        errors.append("run-manifest: selected candidate disagrees with manifest")
    if adapter_active and runtime.get(
        "promotion_record_sha256"
    ) != manifest.get("promotion_record_sha256"):
        errors.append(
            "run-manifest: promotion record SHA disagrees with manifest"
        )

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
        terminal_inventory_value = delegation.get("terminal_inventory")
        if isinstance(terminal_inventory_value, dict):
            register_evidence_locator(
                terminal_inventory_value.get("locator"),
                "delegation:terminal-inventory",
            )
    task_ids: set[str] = set()
    task_by_id_for_inputs = {
        task.get("task_id"): task
        for task in tasks
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }
    errors.extend(_validate_task_dependency_graph(tasks))
    run_coverage_by_id = {
        row.get("criterion_id"): row
        for row in coverage_rows_for_links
        if isinstance(row, dict)
    }
    assigned_criteria_by_task: dict[str, set[str]] = {}
    if isinstance(delegation, dict):
        for risk_row in delegation.get("coverage_risk_map", []):
            if not isinstance(risk_row, dict):
                continue
            for assigned_task_id in risk_row.get("task_ids", []):
                if isinstance(assigned_task_id, str):
                    assigned_criteria_by_task.setdefault(
                        assigned_task_id, set()
                    ).add(risk_row.get("criterion_id"))
    task_report_receipts: list[tuple[str, dict]] = []
    task_assessments_by_key: dict[tuple[str, str], dict] = {}
    task_report_times: list[datetime] = []
    task_configuration_time_by_id: dict[str, datetime] = {}
    task_report_time_by_id: dict[str, datetime] = {}
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
        task_status = task.get("status")
        assigned_criterion_ids = task.get("assigned_criterion_ids")
        expected_assigned_criteria = sorted(
            item
            for item in assigned_criteria_by_task.get(task_id, set())
            if isinstance(item, str)
        )
        if assigned_criterion_ids != expected_assigned_criteria:
            errors.append(
                f"{prefix}: assigned_criterion_ids must exactly bind the "
                "coverage risk map"
            )
        terminal_reason = task.get("terminal_reason")
        if task_status == "completed" and terminal_reason is not None:
            errors.append(
                f"{prefix}: completed task requires null terminal_reason"
            )
        if task_status in {"failed", "cancelled"}:
            if not _is_nonblank_string(terminal_reason):
                errors.append(
                    f"{prefix}: {task_status} task requires terminal_reason"
                )
            elif terminal_reason not in data.get("limitations", []):
                errors.append(
                    f"{prefix}: terminal_reason is not propagated to run "
                    "limitations"
                )
        task_requires_assurance = (
            adapter_active and task_status == "completed"
        )
        task_configuration_receipt: dict | None = None
        task_effects = task.get("task_effects")
        proof_value = task.get("configuration_proof")
        if isinstance(proof_value, dict):
            register_evidence_locator(
                proof_value.get("locator"),
                f"task:{task_id}:configuration",
            )
        for control in ("model", "mode", "sandbox"):
            state = task.get(f"{control}_validation")
            if isinstance(state, dict):
                register_evidence_locator(
                    state.get("evidence_locator"),
                    f"task:{task_id}:{control}-validation",
                )
        if task_status == "completed":
            register_evidence_locator(
                task.get("report_artifact"),
                f"task:{task_id}:report",
            )
        bounded_input_ids = task.get("input_artifact_ids")
        if not isinstance(bounded_input_ids, list):
            errors.append(f"{prefix}: bounded input artifact IDs must be a list")
            bounded_input_ids = []
        for artifact_id in bounded_input_ids:
            artifact = artifact_by_id.get(artifact_id)
            if not isinstance(artifact, dict):
                errors.append(
                    f"{prefix}: bounded input references unknown artifact "
                    f"{artifact_id}"
                )
            elif artifact.get("state") != "frozen":
                errors.append(
                    f"{prefix}: bounded task input must be frozen: {artifact_id}"
                )
        input_records, input_record_errors = _build_task_input_records(
            task,
            artifact_by_id,
            task_by_id_for_inputs,
            root,
        )
        errors.extend(f"{prefix}: {error}" for error in input_record_errors)
        derived_snapshot_sha256 = _task_input_snapshot_sha256(input_records)
        if task.get("input_snapshot_sha256") != derived_snapshot_sha256:
            errors.append(
                f"{prefix}: input_snapshot_sha256 does not bind exact task inputs"
            )
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
        if task.get("substantive") is True or task_requires_assurance:
            task_assurance_times: list[datetime] = []
            (
                task_proof_errors,
                task_proof_sha256,
                task_configuration_receipt,
            ) = (
                _validate_configuration_proof(
                    task.get("configuration_proof"),
                    prefix,
                    "task",
                    task_id,
                    bundle_root=root,
                    evidence_root=run_evidence_root,
                    requested_model=task.get("requested_model"),
                    requested_mode=task.get("requested_mode"),
                    requested_sandbox=task.get("requested_sandbox"),
                    agent_or_task_identifier=task.get(
                        "agent_or_task_identifier"
                    ),
                    fork_policy=task.get("fork_policy"),
                    leaf_only=task.get("leaf_only"),
                    input_artifact_ids=task.get("input_artifact_ids"),
                    dependency_task_ids=task.get("dependency_task_ids"),
                    bundle_input_artifacts=task.get(
                        "bundle_input_artifacts"
                    ),
                    input_records=input_records,
                    input_snapshot_sha256=task.get(
                        "input_snapshot_sha256"
                    ),
                    task_effects=task.get("task_effects"),
                    report_contract=task.get("report_contract"),
                    stop_condition=task.get("stop_condition"),
                    configuration_source=task.get("configuration_source"),
                    fallback_policy=task.get("adapter_controlled_fallback"),
                    surface=runtime.get("surface"),
                    host_build=runtime.get("host_build"),
                    adapter_sha256=runtime.get("adapter_sha256"),
                    compatibility_payload_sha256=runtime.get(
                        "compatibility_payload_sha256"
                    ),
                    selected_candidate_id=runtime.get(
                        "selected_candidate_id"
                    ),
                    promotion_record_sha256=runtime.get(
                        "promotion_record_sha256"
                    ),
                    trigger=task.get("trigger"),
                    assigned_criterion_ids=task.get(
                        "assigned_criterion_ids"
                    ),
                    required=task_requires_assurance,
                )
            )
            errors.extend(task_proof_errors)
            task_configuration_time = (
                _parse_rfc3339_datetime(
                    task_configuration_receipt.get("recorded_at")
                )
                if isinstance(task_configuration_receipt, dict)
                else None
            )
            run_created_time = _parse_rfc3339_datetime(data.get("created_at"))
            if task_configuration_time is not None:
                task_assurance_times.append(task_configuration_time)
                assurance_times.append(task_configuration_time)
                task_configuration_time_by_id[task_id] = (
                    task_configuration_time
                )
            if (
                task_configuration_time is not None
                and run_created_time is not None
                and task_configuration_time < run_created_time
            ):
                errors.append(
                    f"{prefix}: task configuration chronology must follow "
                    "run creation"
                )
            for control, requested_value in (
                ("model", "gpt-5.6-sol"),
                ("mode", "ultra"),
                ("sandbox", "read-only"),
            ):
                errors.extend(
                    _validate_validation_state(
                        task.get(f"{control}_validation"),
                        f"{prefix} {control}",
                        bundle_root=root,
                        evidence_root=run_evidence_root,
                        subject_kind="task",
                        subject_id=task_id,
                        control=control,
                        requested_value=requested_value,
                        configuration_proof_locator=(
                            task.get("configuration_proof", {}).get("locator")
                            if isinstance(
                                task.get("configuration_proof"), dict
                            )
                            else None
                        ),
                        configuration_proof_sha256=task_proof_sha256,
                        configuration_receipt=task_configuration_receipt,
                        require_passed=task_requires_assurance,
                        observed_times=task_assurance_times,
                    )
                )
            assurance_times.extend(
                time
                for time in task_assurance_times
                if time not in assurance_times
            )
            if task_requires_assurance:
                if (
                    task.get("requested_model") != "gpt-5.6-sol"
                    or task.get("requested_mode") != "ultra"
                    or task.get("requested_sandbox") != "read-only"
                ):
                    errors.append(
                        f"{prefix}: completed adapter task must request "
                        "gpt-5.6-sol + ultra in a read-only sandbox"
                    )
                if (
                    task.get("adapter_controlled_fallback")
                    != "prohibited_and_checked"
                ):
                    errors.append(
                        f"{prefix}: completed adapter task fallback is not controlled"
                    )
                if (
                    task.get("configuration_source")
                    != "adapter-controlled dispatch"
                ):
                    errors.append(
                        f"{prefix}: completed adapter task configuration source must be "
                        "the adapter-controlled dispatch record"
                    )
                if task.get("leaf_only") is not True:
                    errors.append(
                        f"{prefix}: completed adapter task must be leaf-only"
                    )
                if task.get("fork_policy") != "none":
                    errors.append(
                        f"{prefix}: completed adapter task must use fork_policy none "
                        "to preserve independent context"
                    )
            if (
                task.get("status") == "completed"
                and task.get("descendant_state") != "none"
            ):
                errors.append(
                    f"{prefix}: completed adapter task descendant state "
                    "must be none"
                )
            if task.get("descendant_state") != "none" and completion == "complete":
                errors.append(
                    f"{prefix}: unknown descendant state requires partial or blocked "
                    "completion"
                )
        if not adapter_active:
            portable_adapter_fields = {
                "requested_model": None,
                "requested_mode": None,
                "requested_sandbox": None,
                "configuration_source": None,
                "configuration_proof": None,
                "adapter_controlled_fallback": "not_applicable",
                "fork_policy": "not_applicable",
            }
            for field, expected in portable_adapter_fields.items():
                if task.get(field) != expected:
                    errors.append(
                        f"{prefix}: portable task requires {field}={expected!r}"
                    )
            for control in ("model", "mode", "sandbox"):
                if task.get(f"{control}_validation", {}).get(
                    "status"
                ) != "not_run":
                    errors.append(
                        f"{prefix}: portable task cannot claim adapter "
                        f"{control} validation"
                    )
        if completion == "complete" and task.get("descendant_state") != "none":
            errors.append(
                f"{prefix}: unsettled descendant state prevents complete run "
                "status"
            )
        if completion == "complete" and task_status != "completed":
            errors.append(
                f"{prefix}: task status {task_status} prevents complete run status"
            )
        if task_status == "completed":
            report_locator = task.get("report_artifact")
            report_sha256 = task.get("report_sha256")
            if task.get("substantive") is True and not (
                isinstance(task.get("agent_or_task_identifier"), str)
                and task.get("agent_or_task_identifier").strip()
            ):
                errors.append(
                    f"{prefix}: completed substantive task requires a runtime "
                    "agent or task identifier"
                )
            if not _is_canonical_relative_locator(report_locator):
                errors.append(
                    f"{prefix}: completed task report locator must be canonical "
                    "and relative"
                )
            if not _is_sha256(report_sha256):
                errors.append(
                    f"{prefix}: completed task report SHA-256 is required"
                )
            if (
                _is_canonical_relative_locator(report_locator)
                and _is_sha256(report_sha256)
            ):
                report, _, report_errors = _load_bound_json_receipt(
                    run_evidence_root,
                    report_locator,
                    report_sha256,
                    f"{prefix}: completed task report",
                )
                errors.extend(report_errors)
                if isinstance(report, dict):
                    if any(
                        _contains_positive_acceptance_prediction(text)
                        for text in _string_leaves(report)
                    ):
                        errors.append(
                            f"{prefix}: task report cannot contain an "
                            "acceptance prediction"
                        )
                    if _contains_count_based_confidence(report):
                        errors.append(
                            f"{prefix}: task report cannot derive scientific "
                            "confidence from reviewer, agent, or task count"
                        )
                    structural_errors = validate_json_schema_document(
                        report,
                        root,
                        "schemas/task-report.schema.json",
                        f"{prefix} task report",
                    )
                    errors.extend(structural_errors)
                    if not structural_errors:
                        report_time = _parse_rfc3339_datetime(
                            report.get("reported_at")
                        )
                        run_time = _parse_rfc3339_datetime(
                            data.get("created_at")
                        )
                        configuration_time = (
                            _parse_rfc3339_datetime(
                                task_configuration_receipt.get("recorded_at")
                            )
                            if isinstance(task_configuration_receipt, dict)
                            else None
                        )
                        if report_time is not None:
                            task_report_times.append(report_time)
                            task_report_time_by_id[task_id] = report_time
                        if (
                            report_time is None
                            or run_time is None
                            or report_time < run_time
                            or (
                                configuration_time is not None
                                and report_time < configuration_time
                            )
                            or any(
                                assurance_time > report_time
                                for assurance_time in task_assurance_times
                            )
                        ):
                            errors.append(
                                f"{prefix}: task report chronology must "
                                "follow the run and task configuration"
                            )
                        expected_fields = {
                            "run_id": run_id,
                            "task_id": task_id,
                            "agent_or_task_identifier":
                                task.get("agent_or_task_identifier"),
                            "status": "completed",
                            "task_effects": task_effects,
                            "input_snapshot_sha256":
                                task.get("input_snapshot_sha256"),
                            "configuration_receipt_sha256":
                                task.get("configuration_proof", {}).get(
                                    "sha256"
                                )
                                if isinstance(
                                    task.get("configuration_proof"), dict
                                )
                                else None,
                        }
                        for field, expected in expected_fields.items():
                            if report.get(field) != expected:
                                errors.append(
                                    f"{prefix}: task report {field} does not "
                                    "bind the completed task"
                                )
                        if task.get("substantive") is True and not report.get(
                            "evidence"
                        ):
                            errors.append(
                                f"{prefix}: substantive task report requires "
                                "bounded evidence"
                            )
                        input_record_by_id = {
                            record.get("input_id"): record
                            for record in input_records
                            if isinstance(record, dict)
                        }
                        for evidence in report.get("evidence", []):
                            if not isinstance(evidence, dict):
                                continue
                            record = input_record_by_id.get(
                                evidence.get("input_id")
                            )
                            if (
                                not isinstance(record, dict)
                                or evidence.get("artifact_id")
                                != record.get("source_id")
                            ):
                                errors.append(
                                    f"{prefix}: task report evidence exceeds "
                                    "the exact mixed-input snapshot"
                                )
                        for limitation in report.get("limitations", []):
                            if limitation not in data.get("limitations", []):
                                errors.append(
                                    f"{prefix}: task report limitation is not "
                                    f"propagated to run limitations: {limitation}"
                                )
                        assessments = report.get(
                            "coverage_assessments", []
                        )
                        assessment_ids = [
                            assessment.get("criterion_id")
                            for assessment in assessments
                            if isinstance(assessment, dict)
                        ]
                        assigned_criteria = assigned_criteria_by_task.get(
                            task_id, set()
                        )
                        if (
                            len(assessment_ids) != len(set(assessment_ids))
                            or set(assessment_ids) != assigned_criteria
                        ):
                            errors.append(
                                f"{prefix}: task report coverage assessments "
                                "must exactly cover assigned criteria"
                            )
                        for assessment in assessments:
                            if not isinstance(assessment, dict):
                                continue
                            criterion_id = assessment.get("criterion_id")
                            if (
                                isinstance(task_id, str)
                                and isinstance(criterion_id, str)
                            ):
                                task_assessments_by_key[
                                    (task_id, criterion_id)
                                ] = assessment
                            applicability = assessment.get("applicability")
                            disposition = assessment.get("disposition")
                            assessment_evidence = assessment.get(
                                "evidence", []
                            )
                            if applicability == "applicable" and (
                                disposition
                                not in {
                                    "assessed_no_finding",
                                    "finding_linked",
                                    "needs_verification",
                                    "blocked",
                                }
                                or not assessment_evidence
                            ):
                                errors.append(
                                    f"{prefix}: task report applicable "
                                    "assessment is incomplete"
                                )
                            if applicability == "inapplicable" and (
                                disposition != "not_applicable"
                                or assessment.get("finding_ids")
                            ):
                                errors.append(
                                    f"{prefix}: task report inapplicable "
                                    "assessment is inconsistent"
                                )
                            if applicability == "uncertain" and disposition not in {
                                "needs_verification",
                                "blocked",
                            }:
                                errors.append(
                                    f"{prefix}: task report uncertain "
                                    "assessment must remain unresolved"
                                )
                            assessment_finding_ids = assessment.get(
                                "finding_ids", []
                            )
                            if (
                                disposition == "finding_linked"
                                and not assessment_finding_ids
                            ):
                                errors.append(
                                    f"{prefix}: finding_linked assessment "
                                    "requires finding IDs"
                                )
                            if (
                                disposition
                                in {
                                    "assessed_no_finding",
                                    "not_applicable",
                                    "needs_verification",
                                    "blocked",
                                }
                                and assessment_finding_ids
                            ):
                                errors.append(
                                    f"{prefix}: {disposition} cannot link findings"
                                )
                            if disposition in {
                                "needs_verification",
                                "blocked",
                            }:
                                canonical_row = run_coverage_by_id.get(
                                    assessment.get("criterion_id")
                                )
                                if (
                                    completion == "complete"
                                    or not isinstance(canonical_row, dict)
                                    or canonical_row.get("disposition")
                                    not in {
                                        "needs_verification",
                                        "blocked",
                                    }
                                ):
                                    errors.append(
                                        f"{prefix}: unresolved task assessment "
                                        "must propagate to canonical coverage "
                                        "and completion"
                                    )
                            canonical_row = run_coverage_by_id.get(
                                assessment.get("criterion_id")
                            )
                            if isinstance(canonical_row, dict):
                                task_tuple = (
                                    assessment.get("applicability"),
                                    assessment.get("disposition"),
                                    assessment.get("finding_ids", []),
                                )
                                canonical_tuple = (
                                    canonical_row.get("applicability"),
                                    canonical_row.get("disposition"),
                                    canonical_row.get("finding_ids", []),
                                )
                                if task_tuple != canonical_tuple:
                                    matching = [
                                        item
                                        for item in canonical_row.get(
                                            "task_reconciliations", []
                                        )
                                        if isinstance(item, dict)
                                        and item.get("task_id") == task_id
                                        and (
                                            item.get("task_applicability"),
                                            item.get("task_disposition"),
                                            item.get("task_finding_ids"),
                                        )
                                        == task_tuple
                                        and (
                                            item.get(
                                                "canonical_applicability"
                                            ),
                                            item.get(
                                                "canonical_disposition"
                                            ),
                                            item.get(
                                                "canonical_finding_ids"
                                            ),
                                        )
                                        == canonical_tuple
                                    ]
                                    if len(matching) != 1:
                                        errors.append(
                                            f"{prefix}: task/canonical coverage "
                                            "difference requires one exact "
                                            "typed reconciliation"
                                        )
                                    elif (
                                        matching[0].get("outcome")
                                        == "unresolved"
                                        or matching[0].get("dissent_state")
                                        == "unresolved"
                                    ) and completion == "complete":
                                        errors.append(
                                            f"{prefix}: unresolved task coverage "
                                            "dissent prevents complete status"
                                        )
                            for item in assessment_evidence:
                                record = (
                                    input_record_by_id.get(
                                        item.get("input_id")
                                    )
                                    if isinstance(item, dict)
                                    else None
                                )
                                if (
                                    not isinstance(item, dict)
                                    or not isinstance(record, dict)
                                    or item.get("artifact_id")
                                    != record.get("source_id")
                                ):
                                    errors.append(
                                        f"{prefix}: task report assessment "
                                        "evidence exceeds the exact mixed-input "
                                        "snapshot"
                                    )
                        contributions = report.get(
                            "finding_contributions", []
                        )
                        contribution_ids = [
                            contribution.get("finding_id")
                            for contribution in contributions
                            if isinstance(contribution, dict)
                        ]
                        if (
                            contribution_ids != report.get("finding_ids")
                            or len(contribution_ids)
                            != len(set(contribution_ids))
                        ):
                            errors.append(
                                f"{prefix}: finding contribution IDs must "
                                "exactly equal the report finding_ids index"
                            )
                        declared_effects = set(task_effects)
                        for contribution in contributions:
                            if not isinstance(contribution, dict):
                                continue
                            if contribution.get("effect") not in declared_effects:
                                errors.append(
                                    f"{prefix}: finding contribution effect "
                                    "was not assigned to the task"
                                )
                            if contribution.get("artifact_id") not in set(
                                bounded_input_ids
                            ):
                                errors.append(
                                    f"{prefix}: finding contribution exceeds "
                                    "bounded input set"
                                )
                            if contribution.get("criterion") not in (
                                assigned_criteria
                            ):
                                errors.append(
                                    f"{prefix}: finding contribution criterion "
                                    "exceeds the task's assigned criteria"
                                )
                        finding_effects = {
                            "add_finding",
                            "verify_finding",
                            "remove_finding",
                            "adjudicate_finding",
                            "rank_finding",
                            "synthesise_findings",
                        }
                        if not declared_effects & finding_effects and contributions:
                            errors.append(
                                f"{prefix}: non-finding task cannot report "
                                "finding contributions"
                            )
                        task_report_receipts.append((prefix, report))
        elif (
            task.get("report_artifact") is not None
            or task.get("report_sha256") is not None
        ):
            errors.append(
                f"{prefix}: non-completed task cannot claim a completed report"
            )

    errors.extend(
        _validate_task_dependency_chronology(
            tasks,
            task_configuration_time_by_id,
            task_report_time_by_id,
        )
    )

    completed_task_ids = {
        task.get("task_id")
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") == "completed"
        and isinstance(task.get("task_id"), str)
    }
    for row in coverage_rows_for_links:
        if not isinstance(row, dict):
            continue
        criterion_id = row.get("criterion_id")
        canonical_tuple = (
            row.get("applicability"),
            row.get("disposition"),
            row.get("finding_ids", []),
        )
        reconciliations = row.get("task_reconciliations", [])
        reconciliation_task_ids = [
            item.get("task_id")
            for item in reconciliations
            if isinstance(item, dict)
        ]
        if len(reconciliation_task_ids) != len(
            set(reconciliation_task_ids)
        ):
            errors.append(
                "run-manifest: task reconciliation task IDs must be unique "
                f"for criterion {criterion_id}"
            )
        for reconciliation in reconciliations:
            if not isinstance(reconciliation, dict):
                continue
            reconciliation_task_id = reconciliation.get("task_id")
            assessment = task_assessments_by_key.get(
                (reconciliation_task_id, criterion_id)
            )
            if (
                reconciliation.get("outcome") == "unresolved"
                or reconciliation.get("dissent_state") == "unresolved"
            ) and completion == "complete":
                errors.append(
                    "run-manifest: unresolved task reconciliation prevents "
                    "complete status"
                )
            if (
                reconciliation_task_id not in completed_task_ids
                or not isinstance(assessment, dict)
            ):
                errors.append(
                    "run-manifest: task reconciliation must bind one completed "
                    f"task assessment: {criterion_id}/{reconciliation_task_id}"
                )
                continue
            task_tuple = (
                assessment.get("applicability"),
                assessment.get("disposition"),
                assessment.get("finding_ids", []),
            )
            recorded_task_tuple = (
                reconciliation.get("task_applicability"),
                reconciliation.get("task_disposition"),
                reconciliation.get("task_finding_ids", []),
            )
            recorded_canonical_tuple = (
                reconciliation.get("canonical_applicability"),
                reconciliation.get("canonical_disposition"),
                reconciliation.get("canonical_finding_ids", []),
            )
            if (
                task_tuple != recorded_task_tuple
                or canonical_tuple != recorded_canonical_tuple
            ):
                errors.append(
                    "run-manifest: task reconciliation does not bind the exact "
                    f"task and canonical tuples: {criterion_id}/"
                    f"{reconciliation_task_id}"
                )
            if task_tuple == canonical_tuple:
                errors.append(
                    "run-manifest: task reconciliation is forbidden when task "
                    f"and canonical coverage agree: {criterion_id}/"
                    f"{reconciliation_task_id}"
                )
    if isinstance(delegation, dict):
        errors.extend(
            _validate_delegation_terminal_inventory(
                delegation.get("terminal_inventory"),
                run_id,
                data.get("created_at"),
                data.get("finalized_at"),
                tasks,
                task_report_times,
                assurance_times,
                bundle_root=root,
                evidence_root=run_evidence_root,
            )
        )
    if run_finalized_time is not None and any(
        observed_time > run_finalized_time
        for observed_time in assurance_times + task_report_times
    ):
        errors.append(
            "run-manifest: receipt chronology cannot postdate run "
            "finalization"
        )
    for prefix, report in task_report_receipts:
        for evidence in report.get("evidence", []):
            if (
                not isinstance(evidence, dict)
                or evidence.get("artifact_id") not in artifact_ids
            ):
                errors.append(
                    f"{prefix}: task report evidence references unknown artifact"
                )
    risk_rows = (
        delegation.get("coverage_risk_map", [])
        if isinstance(delegation, dict)
        else []
    )
    risk_criterion_ids: list[str] = []
    risk_task_ids: set[str] = set()
    coverage_tasks_by_criterion = {
        row.get("criterion_id"): set(row.get("task_ids", []))
        for row in coverage_rows_for_links
        if isinstance(row.get("task_ids"), list)
    }
    for index, risk_row in enumerate(risk_rows):
        if not isinstance(risk_row, dict):
            continue
        prefix = f"run-manifest: coverage_risk_map[{index}]"
        criterion_id = risk_row.get("criterion_id")
        risk_criterion_ids.append(criterion_id)
        if criterion_id not in set(canonical_ids):
            errors.append(f"{prefix}: criterion_id is not canonical")
        referenced_tasks = set(risk_row.get("task_ids", []))
        for unknown in sorted(referenced_tasks - task_ids):
            errors.append(f"{prefix}: unknown delegated task ID: {unknown}")
        decision = risk_row.get("delegation_decision")
        if decision == "delegate" and not referenced_tasks:
            errors.append(f"{prefix}: delegate decision requires task IDs")
        if decision in {"root_covers", "blocked"} and referenced_tasks:
            errors.append(
                f"{prefix}: {decision} decision cannot reference task IDs"
            )
        if decision == "blocked" and completion == "complete":
            errors.append(
                f"{prefix}: blocked coverage risk prevents complete status"
            )
        coverage_row = next(
            (
                row
                for row in coverage_rows_for_links
                if row.get("criterion_id") == criterion_id
            ),
            None,
        )
        if decision == "blocked" and (
            not isinstance(coverage_row, dict)
            or coverage_row.get("disposition") != "blocked"
        ):
            errors.append(
                f"{prefix}: blocked risk requires blocked coverage for the "
                "same criterion"
            )
        referenced_task_rows = [
            task
            for task in tasks
            if isinstance(task, dict)
            and task.get("task_id") in referenced_tasks
        ]
        unsettled_task_rows = [
            task
            for task in referenced_task_rows
            if task.get("status") != "completed"
        ]
        if unsettled_task_rows and (
            not isinstance(coverage_row, dict)
            or coverage_row.get("disposition")
            not in {"needs_verification", "blocked"}
        ):
            errors.append(
                f"{prefix}: failed delegated task or other unsettled task "
                "requires unresolved coverage"
            )
        if any(
            task.get("status") in {"failed", "cancelled"}
            for task in unsettled_task_rows
        ) and not data.get("limitations"):
            errors.append(
                f"{prefix}: failed delegated task requires a propagated "
                "run limitation"
            )
        if referenced_tasks != coverage_tasks_by_criterion.get(
            criterion_id, set()
        ):
            errors.append(
                f"{prefix}: risk-map task IDs differ from coverage task IDs"
            )
        risk_task_ids.update(referenced_tasks)
    if len(risk_criterion_ids) != len(set(risk_criterion_ids)):
        errors.append("run-manifest: duplicate coverage-risk criterion")
    if adapter_active and set(risk_criterion_ids) != set(canonical_ids):
        errors.append(
            "run-manifest: adapter-active coverage risk map must exactly cover "
            "all canonical criteria"
        )
    for unowned_task in sorted(task_ids - risk_task_ids):
        errors.append(
            f"run-manifest: delegated task is absent from coverage risk map: "
            f"{unowned_task}"
        )
    stage_id_list = [
        stage.get("stage_id")
        for stage in data.get("stages", [])
        if isinstance(stage, dict) and isinstance(stage.get("stage_id"), str)
    ]
    stage_ids = set(stage_id_list)
    if len(stage_id_list) != len(set(stage_id_list)):
        errors.append("run-manifest: duplicate stage_id")
    completed_task_ids = {
        task.get("task_id")
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") == "completed"
        and isinstance(task.get("task_id"), str)
    }
    allowed_run_field_evidence = {
        "authorisation",
        "confidentiality",
        "coverage_matrix",
        "limitations",
    }
    if adapter_active:
        allowed_run_field_evidence.add("runtime_profile")
    if data.get("venue_profile", {}).get("status") == "loaded":
        allowed_run_field_evidence.add("venue_profile")
    for index, stage in enumerate(data.get("stages", [])):
        if not isinstance(stage, dict):
            continue
        stage_status = stage.get("status")
        if completion == "complete" and stage_status != "complete":
            errors.append(
                f"run-manifest: stage[{index}] status {stage_status} "
                "prevents complete run status"
            )
        if stage_status == "complete" and not stage.get("evidence"):
            errors.append(
                f"run-manifest: stage[{index}] complete status requires evidence"
            )
        for evidence_index, evidence in enumerate(stage.get("evidence", [])):
            prefix = (
                f"run-manifest: stage[{index}].evidence[{evidence_index}]"
            )
            if not isinstance(evidence, dict):
                continue
            stage_evidence_kind = evidence.get("kind")
            reference = evidence.get("reference")
            if stage_evidence_kind == "input_artifact":
                artifact = artifact_by_id.get(reference)
                if not isinstance(artifact, dict) or artifact.get(
                    "state"
                ) != "frozen":
                    errors.append(
                        f"{prefix}: input evidence does not resolve to a "
                        "frozen artifact"
                    )
            elif stage_evidence_kind == "output_artifact":
                if reference not in produced_output_paths:
                    errors.append(
                        f"{prefix}: output evidence does not resolve to a "
                        "produced output"
                    )
            elif stage_evidence_kind == "task_report":
                if reference not in completed_task_ids:
                    errors.append(
                        f"{prefix}: task evidence does not resolve to a "
                        "completed report"
                    )
            elif stage_evidence_kind == "run_field":
                if reference not in allowed_run_field_evidence:
                    errors.append(
                        f"{prefix}: run-field evidence is unavailable or unknown"
                    )
    canonical_owners = {
        row.get("criterion_id"): row.get("primary_stage_owner")
        for row in canonical_coverage.get("criteria", [])
        if isinstance(row, dict)
    }
    run_record_subjects = {
        "RC-AUTHORISATION": "authorisation",
        "RC-INPUT-LINEAGE": "input_artifacts",
        "RC-CRITERIA-AUTHORITY": "venue_profile",
        "RC-COVERAGE-ACCOUNTING": "coverage",
        "RC-DEDUP-DISPOSITION": "finding_ledger",
        "RC-DISSENT-PRESERVATION": "finding_ledger",
        "RC-REQUIREMENT-LEGITIMACY": "finding_ledger",
        "RC-RISK-CLASS-SEPARATION": "finding_ledger",
        "RC-COMPLETION-TRUTH": "completion",
        "RC-LEDGER-CONSISTENCY": "finding_ledger",
    }
    text_evidence_uses: dict[tuple[str, str], list[str]] = {}
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
            if not isinstance(evidence, dict):
                continue
            evidence_kind = evidence.get("evidence_kind")
            method = evidence.get("verification_method")
            excerpt = evidence.get("excerpt")
            excerpt_sha256 = evidence.get("excerpt_sha256")
            expected_method = {
                "text_exact": "utf8_exact_excerpt",
                "rendered": "rendered_receipt",
                "run_record": "canonical_run_field",
                "alignment_receipt": "alignment_receipt",
                "prior_record": "prior_record_binding",
            }.get(evidence_kind)
            if method != expected_method:
                errors.append(
                    f"{prefix}: evidence kind and verification method disagree"
                )
            if evidence_kind == "run_record":
                expected_subject = run_record_subjects.get(criterion_id)
                expected_artifact_id = (
                    f"run:{expected_subject}"
                    if expected_subject is not None
                    else None
                )
                expected_source_anchor = (
                    f"run-manifest:{expected_subject}"
                    if expected_subject is not None
                    else None
                )
                if (
                    expected_subject is None
                    or evidence.get("artifact_id") != expected_artifact_id
                    or evidence.get("source_anchor")
                    != expected_source_anchor
                ):
                    errors.append(
                        f"{prefix}: run-record evidence is not authorised for "
                        "this criterion"
                    )
                elif expected_subject == "finding_ledger":
                    output_artifacts = data.get("output_artifacts")
                    if (
                        not isinstance(output_artifacts, dict)
                        or not isinstance(
                            output_artifacts.get("finding_ledger"), dict
                        )
                    ):
                        errors.append(
                            f"{prefix}: canonical run field is unavailable"
                        )
                elif data.get(expected_subject) is None:
                    errors.append(
                        f"{prefix}: canonical run field is unavailable"
                    )
                if excerpt is not None or excerpt_sha256 is not None:
                    errors.append(
                        f"{prefix}: run-record evidence cannot claim a source excerpt"
                    )
            elif evidence_kind == "alignment_receipt":
                if (
                    criterion_id
                    not in {"RC-INPUT-ALIGNMENT", "RC-INPUT-VERIFIABILITY"}
                    or evidence.get("artifact_id") != "alignment:source-pdf"
                    or not alignment_receipt_valid
                ):
                    errors.append(
                        f"{prefix}: alignment evidence does not resolve to the "
                        "verified byte-bound receipt"
                    )
                if excerpt is not None or excerpt_sha256 is not None:
                    errors.append(
                        f"{prefix}: alignment evidence cannot claim a source excerpt"
                    )
            elif evidence_kind == "rendered":
                artifact = artifact_by_id.get(evidence.get("artifact_id"))
                if (
                    criterion_id != "RC-VISUAL-INTEGRITY"
                    or not isinstance(artifact, dict)
                    or artifact.get("kind") != "pdf"
                    or artifact.get("state") != "frozen"
                    or not alignment_receipt_valid
                ):
                    errors.append(
                        f"{prefix}: rendered evidence must resolve to the matched "
                        "frozen PDF"
                    )
                if excerpt is not None or excerpt_sha256 is not None:
                    errors.append(
                        f"{prefix}: rendered evidence cannot claim a text excerpt"
                    )
                if isinstance(artifact, dict):
                    rendered_errors, _ = _validate_rendered_evidence_receipt(
                        verification=evidence,
                        evidence=evidence,
                        artifact=artifact,
                        evidence_root=run_evidence_root,
                        schema_root=root,
                        subject_id=str(criterion_id),
                        prefix=f"{prefix}: rendered criterion receipt",
                        run_created_at=data.get("created_at"),
                        run_finalized_at=data.get("finalized_at"),
                    )
                    errors.extend(rendered_errors)
            elif evidence_kind == "prior_record":
                artifact = artifact_by_id.get(evidence.get("artifact_id"))
                if (
                    criterion_id != "RC-DELTA-LINEAGE"
                    or kind != "delta"
                    or not isinstance(artifact, dict)
                    or artifact.get("kind")
                    not in {
                        "prior_run",
                        "prior_ledger",
                        "prior_source",
                        "author_response",
                    }
                    or artifact.get("state") != "frozen"
                ):
                    errors.append(
                        f"{prefix}: prior-record evidence must resolve to a "
                        "frozen delta predecessor"
                    )
                if excerpt is not None or excerpt_sha256 is not None:
                    errors.append(
                        f"{prefix}: prior-record evidence cannot claim a text excerpt"
                    )
            elif evidence_kind == "text_exact":
                artifact = artifact_by_id.get(evidence.get("artifact_id"))
                if not isinstance(artifact, dict):
                    errors.append(f"{prefix}: evidence references unknown artifact")
                    continue
                if (
                    artifact.get("state") != "frozen"
                    or artifact.get("kind") != "source"
                ):
                    errors.append(
                        f"{prefix}: exact-text evidence must resolve to the "
                        "frozen current source artifact"
                    )
                    continue
                if not _is_nonblank_string(excerpt):
                    errors.append(
                        f"{prefix}: exact-text evidence requires a bounded excerpt"
                    )
                    continue
                actual_excerpt_sha256 = hashlib.sha256(
                    excerpt.encode("utf-8")
                ).hexdigest()
                if excerpt_sha256 != actual_excerpt_sha256:
                    errors.append(
                        f"{prefix}: exact-text evidence excerpt hash mismatch"
                    )
                try:
                    source_path = _safe_bundle_file(
                        run_evidence_root, artifact.get("locator")
                    )
                    source_bytes = source_path.read_bytes()
                    source_bytes.decode("utf-8")
                except (ValueError, OSError, UnicodeDecodeError) as exc:
                    errors.append(
                        f"{prefix}: exact-text evidence source is unreadable: {exc}"
                    )
                else:
                    span_errors, _ = _validate_exact_span_against_source(
                        evidence,
                        evidence,
                        source_bytes,
                        f"{prefix}: exact-text evidence span",
                    )
                    errors.extend(span_errors)
                    if excerpt.encode("utf-8") not in source_bytes:
                        errors.append(
                            f"{prefix}: exact-text evidence excerpt is absent "
                            "from the frozen source"
                        )
                signature = (
                    str(evidence.get("artifact_id")),
                    actual_excerpt_sha256,
                )
                text_evidence_uses.setdefault(signature, []).append(
                    str(criterion_id)
                )
            else:
                errors.append(f"{prefix}: evidence kind is unsupported")
        if criterion_id == "RC-DELTA-LINEAGE" and kind == "delta":
            expected_delta_artifact_ids = {
                artifacts[0].get("artifact_id")
                for artifacts in delta_inputs_by_kind.values()
                if len(artifacts) == 1
            }
            recorded_delta_artifact_ids = {
                evidence.get("artifact_id")
                for evidence in row.get("evidence", [])
                if isinstance(evidence, dict)
                and evidence.get("evidence_kind") == "prior_record"
            }
            if recorded_delta_artifact_ids != expected_delta_artifact_ids:
                errors.append(
                    f"{prefix}: delta lineage evidence must bind the exact "
                    "prior run, prior ledger, prior source, and author response"
                )
    for (_, _), criterion_ids in text_evidence_uses.items():
        if len(criterion_ids) > 3:
            errors.append(
                "run-manifest: one exact source excerpt is reused across too "
                "many distinct criteria"
            )
    visual_row = next(
        (
            row
            for row in coverage_rows_for_links
            if row.get("criterion_id") == "RC-VISUAL-INTEGRITY"
        ),
        None,
    )
    if (
        isinstance(alignment, dict)
        and alignment.get("status") != "matched"
        and isinstance(visual_row, dict)
        and visual_row.get("applicability") == "applicable"
        and visual_row.get("disposition")
        in {"assessed_no_finding", "finding_linked"}
    ):
        errors.append(
            "run-manifest: visual integrity cannot be settled without a "
            "matched frozen rendering"
        )

    if adapter_active and claim not in {
        "blocked",
        "evaluation_pending",
        "configured-and-evaluated",
        "runtime-attested",
    }:
        errors.append("run-manifest: compatibility_claim is invalid")
    if (
        adapter_active
        and manifest.get("selected_candidate_id") is not None
        and claim not in {"configured-and-evaluated", "runtime-attested"}
    ):
        errors.append(
            "run-manifest: selected adapter requires configured-and-evaluated "
            "compatibility"
        )
    if (
        adapter_active
        and manifest.get("selected_candidate_id") is None
        and claim in {"configured-and-evaluated", "runtime-attested"}
    ):
        errors.append(
            "run-manifest: configured-and-evaluated compatibility requires a "
            "selected adapter"
        )
    if adapter_active and claim == "blocked" and completion == "complete":
        errors.append(
            "run-manifest: blocked adapter compatibility prevents complete "
            "run status; record a portable run without the adapter instead"
        )
    if adapter_active and claim in {
        "configured-and-evaluated",
        "runtime-attested",
    }:
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
            if promotion_ref.get("candidate_id") != manifest.get(
                "selected_candidate_id"
            ):
                errors.append(
                    "run-manifest: promotion candidate does not match adapter "
                    "manifest"
                )
            if promotion_ref.get("adapter_sha256") != manifest.get(
                "adapter_payload_sha256"
            ):
                errors.append(
                    "run-manifest: promotion adapter SHA does not match adapter "
                    "manifest"
                )
            if promotion_ref.get(
                "compatibility_payload_sha256"
            ) != manifest.get("compatibility_payload_sha256"):
                errors.append(
                    "run-manifest: promotion compatibility payload SHA does "
                    "not match adapter manifest"
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
                    "compatibility_payload_sha256",
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
            if task.get("sandbox_validation", {}).get("status") != "passed":
                errors.append(
                    f"run-manifest: substantive task {task.get('task_id')} "
                    "read-only sandbox validation did not pass"
                )
    elif adapter_active and runtime.get("promotion_evaluation_record") is not None:
        errors.append(
            f"run-manifest: {claim} must not claim a promotion record"
        )

    if adapter_active and claim == "runtime-attested":
        if (
            runtime.get("effective_telemetry") != "surfaced_and_verified"
            or runtime.get("resolved_model") != "gpt-5.6-sol"
            or runtime.get("resolved_mode") != "ultra"
        ):
            errors.append(
                "run-manifest: runtime attestation requires surfaced matching telemetry"
            )
        errors.append(
            "run-manifest: offline validator cannot verify runtime attestation; "
            "the state is reserved until a trusted host telemetry verifier is "
            "available"
        )
    telemetry = runtime.get("effective_telemetry")
    resolved_model = runtime.get("resolved_model")
    resolved_mode = runtime.get("resolved_mode")
    if adapter_active and telemetry == "not_surfaced":
        if runtime.get("resolved_model") is not None or runtime.get(
            "resolved_mode"
        ) is not None:
            errors.append(
                "run-manifest: absent telemetry requires null resolved model/mode"
            )
    elif adapter_active and telemetry == "surfaced_unverified":
        if not (
            isinstance(resolved_model, str)
            and resolved_model.strip()
            and isinstance(resolved_mode, str)
            and resolved_mode.strip()
        ):
            errors.append(
                "run-manifest: surfaced unverified telemetry requires recorded "
                "model and mode values"
            )
        elif (
            resolved_model != "gpt-5.6-sol" or resolved_mode != "ultra"
        ) and claim != "blocked":
            errors.append(
                "run-manifest: surfaced telemetry mismatch requires blocked "
                "compatibility"
            )
    elif adapter_active and telemetry == "surfaced_and_verified":
        errors.append(
            "run-manifest: surfaced_and_verified telemetry is unavailable "
            "without a trusted host telemetry verifier"
        )

    # Retained for validate_run_pair without trusting a parallel field.
    data_finding_ids = data.get("_coverage_finding_ids")
    if data_finding_ids is not None:
        errors.append("run-manifest: private coverage helper field is forbidden")
    if not authority_gate_open:
        if any(
            isinstance(artifact, dict) and artifact.get("state") == "frozen"
            for artifact in input_artifacts
        ):
            errors.append(
                "run-manifest: authority/policy preflight stop cannot freeze "
                "protected inputs"
            )
        if tasks:
            errors.append(
                "run-manifest: authority/policy preflight stop cannot dispatch tasks"
            )
        if any(
            isinstance(stage, dict)
            and stage.get("status") in {"complete", "partial"}
            for stage in data.get("stages", [])
        ):
            errors.append(
                "run-manifest: authority/policy preflight stop cannot complete "
                "substantive stages"
            )
        if any(
            isinstance(row, dict)
            and row.get("disposition")
            in {"assessed_no_finding", "finding_linked"}
            for row in coverage_rows_for_links
        ):
            errors.append(
                "run-manifest: authority/policy preflight stop cannot record "
                "settled scientific coverage"
            )
        for row in coverage_rows_for_links:
            if not isinstance(row, dict):
                continue
            criterion_id = row.get("criterion_id")
            if criterion_id == "RC-AUTHORISATION":
                valid_preflight_state = (
                    row.get("applicability")
                    in {"applicable", "uncertain"}
                    and row.get("disposition") == "blocked"
                )
            elif (
                criterion_id == "RC-DELTA-LINEAGE"
                and kind == "initial"
            ):
                valid_preflight_state = (
                    row.get("applicability") == "inapplicable"
                    and row.get("disposition") == "not_applicable"
                )
            else:
                valid_preflight_state = (
                    row.get("applicability") == "uncertain"
                    and row.get("disposition") == "blocked"
                )
            if not valid_preflight_state:
                errors.append(
                    "run-manifest: authority/policy preflight stop cannot "
                    "classify scientific criterion outside the blocked "
                    f"administrative state: {criterion_id}"
                )
        if any(
            isinstance(output, dict) and output.get("status") == "produced"
            for output in output_artifacts.values()
        ):
            errors.append(
                "run-manifest: authority/policy preflight stop cannot produce "
                "scientific review outputs"
            )
        if not isinstance(alignment, dict) or alignment.get("status") != "blocked":
            errors.append(
                "run-manifest: authority/policy preflight stop requires blocked "
                "input alignment"
            )
        if not data.get("limitations"):
            errors.append(
                "run-manifest: authority/policy preflight stop requires a "
                "recorded limitation"
            )

    terminal_tasks = [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("status") in {"pending", "running"}
    ]
    if terminal_tasks:
        errors.append(
            "run-manifest: terminal run cannot retain pending or running tasks"
        )
    unresolved_coverage = [
        row
        for row in coverage_rows_for_links
        if row.get("disposition") in {"needs_verification", "blocked"}
    ]
    partial_or_blocked_stages = [
        stage
        for stage in data.get("stages", [])
        if isinstance(stage, dict)
        and stage.get("status") in {"partial", "blocked"}
    ]
    if completion == "partial" and (
        not data.get("limitations")
        or not (
            unresolved_coverage
            or partial_or_blocked_stages
            or alignment.get("status") != "matched"
            or any(
                isinstance(task, dict)
                and task.get("status") in {"failed", "cancelled"}
                for task in tasks
            )
        )
    ):
        errors.append(
            "run-manifest: partial completion requires an unresolved "
            "responsibility and explicit limitation"
        )
    if completion == "blocked" and (
        not data.get("limitations")
        or not (
            any(row.get("disposition") == "blocked" for row in unresolved_coverage)
            or any(
                stage.get("status") == "blocked"
                for stage in partial_or_blocked_stages
            )
            or not authority_gate_open
            or alignment.get("status") == "blocked"
            or claim == "blocked"
        )
    ):
        errors.append(
            "run-manifest: blocked completion requires a concrete blocked "
            "responsibility and explicit limitation"
        )
    if any(
        _contains_positive_acceptance_prediction(text)
        for text in _string_leaves(data)
    ):
        errors.append(
            "run-manifest: acceptance prediction is forbidden anywhere in "
            "the canonical run record"
        )
    if _contains_count_based_confidence(data):
        errors.append(
            "run-manifest: reviewer, agent, or task count cannot establish "
            "scientific confidence"
        )
    return sorted(set(errors))


def validate_run_pair(
    run: dict,
    ledger: dict,
    coverage_matrix: dict,
    bundle_root: pathlib.Path,
    *,
    evidence_root: pathlib.Path,
) -> list[str]:
    run_errors = validate_run_manifest(
        run,
        coverage_matrix,
        bundle_root,
        evidence_root=evidence_root,
    )
    ledger_errors = validate_finding_ledger(ledger, bundle_root)
    errors = [*run_errors, *ledger_errors]
    if any(
        error.startswith(("schema:", "schema-audit:"))
        for error in (*run_errors, *ledger_errors)
    ):
        return sorted(set(errors))
    if isinstance(run, dict) and isinstance(ledger, dict):
        if run.get("run_id") != ledger.get("run_id"):
            errors.append("run-pair: run_id mismatch")
        if run.get("review_kind") != ledger.get("review_kind"):
            errors.append("run-pair: review_kind mismatch")
        if run.get("completion") != ledger.get("completion"):
            errors.append("run-pair: completion mismatch")
        finding_output = run.get("output_artifacts", {}).get(
            "finding_ledger"
        )
        if (
            isinstance(finding_output, dict)
            and finding_output.get("status") == "produced"
        ):
            try:
                output_path = _safe_bundle_file(
                    evidence_root, finding_output.get("locator")
                )
                recorded_ledger = _load_json_object(
                    output_path, "run-pair finding-ledger output"
                )
            except ValueError as exc:
                errors.append(f"run-pair: finding-ledger output is invalid: {exc}")
            else:
                if recorded_ledger != ledger:
                    errors.append(
                        "run-pair: supplied ledger differs from the byte-bound "
                        "finding-ledger output"
                    )
        ledger_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
        }
        ledger_by_id = {
            finding.get("finding_id"): finding
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and isinstance(finding.get("finding_id"), str)
        }
        surviving_decision_findings = [
            finding
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status")
            in {"retained", "unresolved"}
            and finding.get("decision_impact")
            in {"fundamental", "material", "limited"}
        ]
        for row in run.get("venue_assessment", {}).get("criteria", []):
            if not isinstance(row, dict):
                continue
            for finding_id in row.get("finding_ids", []):
                if finding_id not in ledger_ids:
                    errors.append(
                        "run-pair: venue assessment references unknown finding "
                        f"ID: {finding_id}"
                    )
                elif (
                    row.get("assessment") == "concern"
                    and ledger_by_id[finding_id].get("adjudication_status")
                    not in {"retained", "unresolved"}
                ):
                    errors.append(
                        "run-pair: venue concern must link a surviving "
                        f"canonical finding: {finding_id}"
                    )
        for row in run.get("venue_assessment", {}).get("native_fields", []):
            if not isinstance(row, dict):
                continue
            basis = row.get("basis")
            if not isinstance(basis, dict):
                continue
            for finding_id in basis.get("finding_ids", []):
                finding = ledger_by_id.get(finding_id)
                if not isinstance(finding, dict):
                    errors.append(
                        "run-pair: venue native basis references unknown "
                        f"finding ID: {finding_id}"
                    )
                elif finding.get("adjudication_status") not in {
                    "retained",
                    "unresolved",
                }:
                    errors.append(
                        "run-pair: venue native basis must link a surviving "
                        f"canonical finding: {finding_id}"
                    )
        human_outputs: dict[str, str] = {}
        for name in ("reviewer_report", "ae_assessment", "review_summary"):
            output = run.get("output_artifacts", {}).get(name)
            if not isinstance(output, dict) or output.get("status") != "produced":
                continue
            try:
                path = _safe_bundle_file(
                    evidence_root, output.get("locator")
                )
                human_outputs[name] = path.read_text(encoding="utf-8")
            except (ValueError, OSError, UnicodeDecodeError):
                continue
        for name, text in human_outputs.items():
            prefix = f"run-pair: {name}"
            binding, binding_errors = _extract_machine_binding(text, prefix)
            errors.extend(binding_errors)
            expected_binding = human_machine_binding(
                name,
                run,
                ledger,
                bundle_root,
            )
            if isinstance(binding, dict) and binding != expected_binding:
                errors.append(
                    f"{prefix} machine binding differs from the canonical "
                    "run, coverage, finding, limitation, or venue state"
                )
            expected_text = render_human_view(
                name,
                run,
                ledger,
                bundle_root,
            )
            if text != expected_text:
                errors.append(
                    f"{prefix} differs from the deterministic canonical "
                    "human view"
                )
            mentioned_ids = set(
                re.findall(
                    r"(?<![A-Za-z0-9-])F-[0-9a-f]{16}(?![A-Za-z0-9-])",
                    text,
                )
            )
            for unknown in sorted(mentioned_ids - ledger_ids):
                errors.append(
                    f"run-pair: {name} introduces unknown finding ID: {unknown}"
                )
            if surviving_decision_findings and re.search(
                r"\b(?:no\s+(?:scientific\s+)?findings?"
                r"|(?:every|all)\s+claims?\s+(?:(?:is|are)\s+)?"
                r"fully\s+supported)\b",
                text,
                re.I,
            ):
                errors.append(
                    f"{prefix} narrative contradicts retained findings"
                )
            for line in text.splitlines():
                lowered_line = line.casefold()
                blocker_match = re.search(
                    r"\b(?:fatal|blocker)\b", lowered_line
                )
                negated_blocker = bool(
                    blocker_match
                    and re.search(
                        r"\b(?:no|not|never|without|does\s+not)\b.{0,35}$",
                        lowered_line[:blocker_match.start()],
                    )
                )
                if blocker_match and not negated_blocker and not (
                    re.search(
                        r"(?<![A-Za-z0-9-])F-[0-9a-f]{16}"
                        r"(?![A-Za-z0-9-])",
                        line,
                    )
                ):
                    errors.append(
                        f"{prefix} asserts a fatal or blocker outcome without "
                        "a canonical finding ID"
                    )
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
        artifact_by_id = {
            artifact.get("artifact_id"): artifact
            for artifact in run.get("input_artifacts", [])
            if isinstance(artifact, dict)
            and isinstance(artifact.get("artifact_id"), str)
        }
        artifact_ids = set(artifact_by_id)
        task_ids = {
            task.get("task_id")
            for task in run.get("delegation", {}).get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("task_id"), str)
        }
        task_by_id = {
            task.get("task_id"): task
            for task in run.get("delegation", {}).get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("task_id"), str)
        }
        finding_by_id = {
            finding.get("finding_id"): finding
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and isinstance(finding.get("finding_id"), str)
        }
        surviving_for_narrative = {
            finding_id
            for finding_id, finding in finding_by_id.items()
            if finding.get("adjudication_status") in {"retained", "unresolved"}
        }
        for name, text in human_outputs.items():
            for line in text.splitlines():
                if not re.search(r"\breject(?:ed|ion)?\b", line.casefold()):
                    continue
                for finding_id in surviving_for_narrative:
                    if re.search(
                        rf"(?<![A-Za-z0-9-]){re.escape(finding_id)}"
                        r"(?![A-Za-z0-9-])",
                        line,
                    ):
                        errors.append(
                            f"run-pair: {name} narratively rejects surviving "
                            f"finding: {finding_id}"
                        )
        finding_effects = {
            "add_finding",
            "verify_finding",
            "remove_finding",
            "adjudicate_finding",
            "rank_finding",
            "synthesise_findings",
        }
        report_finding_ids_by_task: dict[str, set[str]] = {}
        for task in run.get("delegation", {}).get("tasks", []):
            if not isinstance(task, dict) or task.get("status") != "completed":
                continue
            try:
                report_path = _safe_bundle_file(
                    evidence_root, task.get("report_artifact")
                )
                report = _load_json_object(
                    report_path,
                    f"run-pair task report {task.get('task_id')}",
                )
            except ValueError:
                continue
            report_finding_ids = report.get("finding_ids", [])
            contributions_by_id = {
                contribution.get("finding_id"): contribution
                for contribution in report.get("finding_contributions", [])
                if isinstance(contribution, dict)
            }
            task_effects = set(task.get("task_effects", []))
            task_id = task.get("task_id")
            if isinstance(task_id, str):
                report_finding_ids_by_task[task_id] = {
                    item for item in report_finding_ids
                    if isinstance(item, str)
                }
            if not task_effects & finding_effects and report_finding_ids:
                errors.append(
                    "run-pair: non-finding task report cannot claim finding IDs: "
                    f"{task.get('task_id')}"
                )
            for finding_id in report_finding_ids:
                finding = finding_by_id.get(finding_id)
                if not isinstance(finding, dict):
                    errors.append(
                        "run-pair: task report references unknown finding ID: "
                        f"{finding_id}"
                    )
                    continue
                contribution = contributions_by_id.get(finding_id)
                if not isinstance(contribution, dict):
                    errors.append(
                        "run-pair: task report finding lacks semantic "
                        f"contribution: {finding_id}"
                    )
                    continue
                finding_evidence = finding.get("evidence", {})
                immutable_pairs = (
                    (
                        "criterion",
                        contribution.get("criterion"),
                        finding.get("criterion"),
                    ),
                    (
                        "normalised claim",
                        _normalised_claim(contribution.get("claim")),
                        _normalised_claim(finding.get("claim")),
                    ),
                    (
                        "artifact",
                        contribution.get("artifact_id"),
                        finding_evidence.get("artifact_id")
                        if isinstance(finding_evidence, dict)
                        else None,
                    ),
                    (
                        "source anchor",
                        contribution.get("source_anchor"),
                        finding_evidence.get("source_anchor")
                        if isinstance(finding_evidence, dict)
                        else None,
                    ),
                    (
                        "semantic anchor",
                        contribution.get("semantic_anchor"),
                        finding_evidence.get("semantic_anchor")
                        if isinstance(finding_evidence, dict)
                        else None,
                    ),
                    (
                        "observation",
                        contribution.get("observation"),
                        finding_evidence.get("observation")
                        if isinstance(finding_evidence, dict)
                        else None,
                    ),
                )
                for label, reported, canonical in immutable_pairs:
                    if reported != canonical:
                        errors.append(
                            "run-pair: task finding contribution changes "
                            f"{label}: {finding_id}"
                        )
                for field, canonical in (
                    ("evidence_state", finding.get("evidence_state")),
                    ("dissent", finding.get("dissent")),
                ):
                    if contribution.get(field) != canonical:
                        errors.append(
                            "run-pair: task finding contribution changes "
                            f"{field}: {finding_id}"
                        )
                if (
                    contribution.get("effect")
                    not in {
                        "remove_finding",
                        "adjudicate_finding",
                        "rank_finding",
                        "synthesise_findings",
                    }
                    and contribution.get("decision_impact")
                    != finding.get("decision_impact")
                ):
                    contribution_dissent = contribution.get("dissent")
                    if (
                        not isinstance(contribution_dissent, dict)
                        or contribution_dissent.get("state")
                        not in {"recorded", "unresolved"}
                    ):
                        errors.append(
                            "run-pair: non-adjudicating task changes "
                            "decision_impact without preserved dissent: "
                            f"{finding_id}"
                        )
                if contribution.get("effect") in {
                    "remove_finding",
                    "adjudicate_finding",
                    "rank_finding",
                    "synthesise_findings",
                }:
                    for field, canonical in (
                        ("decision_impact", finding.get("decision_impact")),
                        (
                            "adjudication_status",
                            finding.get("adjudication_status"),
                        ),
                        (
                            "rationale",
                            finding.get("adjudication_rationale"),
                        ),
                    ):
                        if contribution.get(field) != canonical:
                            errors.append(
                                "run-pair: adjudicating task contribution "
                                f"changes {field}: {finding_id}"
                            )
                elif contribution.get("adjudication_status") not in {
                    "candidate",
                    finding.get("adjudication_status"),
                }:
                    shared_dissent = contribution.get("dissent")
                    canonical_dissent = finding.get("dissent")
                    if (
                        not isinstance(shared_dissent, dict)
                        or shared_dissent != canonical_dissent
                        or shared_dissent.get("state")
                        not in {"recorded", "unresolved"}
                    ):
                        errors.append(
                            "run-pair: non-adjudicating task disposition "
                            "conflicts with canonical finding without "
                            f"preserved dissent: {finding_id}"
                        )
                originating = finding.get("provenance", {}).get(
                    "originating_task_ids", []
                )
                if task.get("task_id") not in originating:
                    errors.append(
                        "run-pair: task report finding is not attributed to "
                        f"originating task {task.get('task_id')}: {finding_id}"
                    )
                finding_evidence = finding.get("evidence")
                report_evidence_pairs = {
                    (
                        evidence.get("artifact_id"),
                        evidence.get("source_anchor"),
                    )
                    for evidence in report.get("evidence", [])
                    if isinstance(evidence, dict)
                }
                if isinstance(finding_evidence, dict) and (
                    finding_evidence.get("artifact_id"),
                    finding_evidence.get("source_anchor"),
                ) not in report_evidence_pairs:
                    errors.append(
                        "run-pair: task report evidence does not bind finding "
                        f"artifact and anchor: {finding_id}"
                    )
            report_contribution_ids = set(contributions_by_id)
            for assessment in report.get("coverage_assessments", []):
                if not isinstance(assessment, dict):
                    continue
                for finding_id in assessment.get("finding_ids", []):
                    if finding_id not in report_contribution_ids:
                        errors.append(
                            "run-pair: task coverage assessment references a "
                            "finding absent from semantic contributions: "
                            f"{finding_id}"
                        )
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
                continue
            provenance = finding.get("provenance")
            artifact = (
                artifact_by_id.get(evidence.get("artifact_id"))
                if isinstance(evidence, dict)
                else None
            )
            anchor_verified = False
            if isinstance(provenance, dict) and isinstance(artifact, dict):
                if artifact.get("kind") not in {"source", "pdf"}:
                    label = (
                        "current delta finding"
                        if run.get("review_kind") == "delta"
                        else "current finding"
                    )
                    errors.append(
                        f"run-pair: {label} must anchor the current source or "
                        "matched current PDF"
                    )
                if artifact.get("state") != "frozen":
                    errors.append(
                        "run-pair: finding evidence must resolve to a frozen "
                        f"artifact: {evidence.get('artifact_id')}"
                    )
                if provenance.get(
                    "primary_artifact_lineage_id"
                ) != artifact.get("lineage_id"):
                    errors.append(
                        "run-pair: finding provenance lineage does not match "
                        f"artifact {evidence.get('artifact_id')}"
                    )
                originating = provenance.get("originating_task_ids")
                if isinstance(originating, list):
                    unknown_origins = set(originating) - task_ids - {"root"}
                    for unknown in sorted(unknown_origins):
                        errors.append(
                            "run-pair: finding provenance references unknown "
                            f"originating task: {unknown}"
                        )
                    for origin in sorted(set(originating) - {"root"}):
                        origin_task = task_by_id.get(origin)
                        if (
                            not isinstance(origin_task, dict)
                            or origin_task.get("status") != "completed"
                            or not (
                                set(origin_task.get("task_effects", []))
                                & finding_effects
                            )
                        ):
                            errors.append(
                                "run-pair: finding origin is not a "
                                "finding-effect task with completed report: "
                                f"{origin}"
                            )
                        elif finding.get("finding_id") not in (
                            report_finding_ids_by_task.get(origin, set())
                        ):
                            errors.append(
                                "run-pair: finding provenance is absent from "
                                f"completed task report {origin}: "
                                f"{finding.get('finding_id')}"
                            )
                verification = evidence.get("anchor_verification")
                if isinstance(verification, dict):
                    method = verification.get("method")
                    if method == "utf8_exact_excerpt":
                        excerpt = verification.get("excerpt")
                        digest = verification.get("excerpt_sha256")
                        if artifact.get("kind") not in {
                            "source",
                            "prior_source",
                        }:
                            errors.append(
                                "run-pair: exact finding anchor must reference "
                                f"source bytes: {finding.get('finding_id')}"
                            )
                        elif not _is_nonblank_string(excerpt):
                            errors.append(
                                "run-pair: exact finding anchor requires a "
                                f"bounded excerpt: {finding.get('finding_id')}"
                            )
                        elif digest != hashlib.sha256(
                            excerpt.encode("utf-8")
                        ).hexdigest():
                            errors.append(
                                "run-pair: finding anchor excerpt hash mismatch: "
                                f"{finding.get('finding_id')}"
                            )
                        else:
                            try:
                                artifact_path = _safe_bundle_file(
                                    evidence_root, artifact.get("locator")
                                )
                                artifact_bytes = artifact_path.read_bytes()
                                artifact_bytes.decode("utf-8")
                            except (
                                ValueError,
                                OSError,
                                UnicodeDecodeError,
                            ) as exc:
                                errors.append(
                                    "run-pair: finding anchor source is "
                                    f"unreadable: {exc}"
                                )
                            else:
                                span_errors, anchor_verified = (
                                    _validate_exact_span_against_source(
                                        evidence,
                                        verification,
                                        artifact_bytes,
                                        "run-pair",
                                    )
                                )
                                errors.extend(span_errors)
                                if (
                                    excerpt.encode("utf-8")
                                    not in artifact_bytes
                                ):
                                    errors.append(
                                        "run-pair: finding anchor excerpt is "
                                        "absent from frozen source: "
                                        f"{finding.get('finding_id')}"
                                    )
                    elif method == "rendered_receipt":
                        alignment = run.get("source_pdf_alignment", {})
                        if (
                            artifact.get("kind") != "pdf"
                            or alignment.get("status") != "matched"
                            or alignment.get("verified") is not True
                            or alignment.get("pdf_artifact_id")
                            != artifact.get("artifact_id")
                        ):
                            errors.append(
                                "run-pair: rendered finding anchor is not bound "
                                "to the matched frozen PDF: "
                                f"{finding.get('finding_id')}"
                            )
                        else:
                            receipt_errors, anchor_verified = (
                                _validate_rendered_evidence_receipt(
                                    verification=verification,
                                    evidence=evidence,
                                    artifact=artifact,
                                    evidence_root=evidence_root,
                                    schema_root=bundle_root,
                                    subject_id=str(
                                        finding.get("finding_id")
                                    ),
                                    prefix="run-pair",
                                    run_created_at=run.get("created_at"),
                                    run_finalized_at=run.get("finalized_at"),
                                )
                            )
                            errors.extend(receipt_errors)
                if (
                    finding.get("evidence_state") == "verified"
                    and finding.get("decision_impact")
                    in {"fundamental", "material", "limited"}
                    and not anchor_verified
                ):
                    errors.append(
                        "run-pair: verified decision-relevant finding lacks a "
                        "successful byte-bound anchor verification: "
                        f"{finding.get('finding_id')}"
                    )
        if run.get("review_kind") == "delta":
            prior_run_artifacts = [
                artifact
                for artifact in run.get("input_artifacts", [])
                if isinstance(artifact, dict)
                and artifact.get("kind") == "prior_run"
                and artifact.get("state") == "frozen"
            ]
            prior_artifacts = [
                artifact
                for artifact in run.get("input_artifacts", [])
                if isinstance(artifact, dict)
                and artifact.get("kind") == "prior_ledger"
                and artifact.get("state") == "frozen"
            ]
            prior_source_artifacts = [
                artifact
                for artifact in run.get("input_artifacts", [])
                if isinstance(artifact, dict)
                and artifact.get("kind") == "prior_source"
                and artifact.get("state") == "frozen"
            ]
            author_response_artifacts = [
                artifact
                for artifact in run.get("input_artifacts", [])
                if isinstance(artifact, dict)
                and artifact.get("kind") == "author_response"
                and artifact.get("state") == "frozen"
            ]
            prior_run_record: dict | None = None
            author_response_record: dict | None = None
            if len(prior_run_artifacts) == 1:
                try:
                    prior_run_path = _safe_bundle_file(
                        evidence_root,
                        prior_run_artifacts[0].get("locator"),
                    )
                    prior_run_raw = prior_run_path.read_bytes()
                    prior_run_record = _load_json_object(
                        prior_run_path, "run-pair prior run"
                    )
                except (ValueError, OSError) as exc:
                    errors.append(f"run-pair: prior run is invalid: {exc}")
                else:
                    if prior_run_raw != _canonical_json_bytes(prior_run_record):
                        errors.append(
                            "run-pair: prior run must be canonical JSON"
                        )
                    prior_run_errors = validate_json_schema_document(
                        prior_run_record,
                        bundle_root,
                        "schemas/run-manifest.schema.json",
                        "run-pair prior run",
                    )
                    errors.extend(prior_run_errors)
                    if prior_run_record.get("review_kind") != "initial":
                        errors.append(
                            "run-pair: prior run must be an initial review"
                        )
                    prior_run_sources = [
                        artifact
                        for artifact in prior_run_record.get(
                            "input_artifacts", []
                        )
                        if isinstance(artifact, dict)
                        and artifact.get("kind") == "source"
                        and artifact.get("state") == "frozen"
                    ]
                    if (
                        len(prior_run_sources) != 1
                        or len(prior_source_artifacts) != 1
                    ):
                        errors.append(
                            "run-pair: prior run and current delta must bind "
                            "exactly one predecessor source"
                        )
                    else:
                        prior_run_source = prior_run_sources[0]
                        prior_source = prior_source_artifacts[0]
                        for field in ("lineage_id", "locator", "sha256"):
                            if prior_run_source.get(field) != prior_source.get(
                                field
                            ):
                                errors.append(
                                    "run-pair: prior run source does not bind "
                                    f"the frozen prior_source {field}"
                                )
                        current_sources = [
                            artifact
                            for artifact in run.get("input_artifacts", [])
                            if isinstance(artifact, dict)
                            and artifact.get("kind") == "source"
                            and artifact.get("state") == "frozen"
                        ]
                        if (
                            len(current_sources) == 1
                            and (
                                current_sources[0].get("sha256")
                                == prior_source.get("sha256")
                                or current_sources[0].get("locator")
                                == prior_source.get("locator")
                            )
                        ):
                            errors.append(
                                "run-pair: delta predecessor source must be "
                                "byte-distinct from the revised source"
                            )
                        if (
                            len(current_sources) == 1
                            and current_sources[0].get("lineage_id")
                            != prior_source.get("lineage_id")
                        ):
                            errors.append(
                                "run-pair: delta source lineage differs from "
                                "the prior manuscript; use a new initial review"
                            )
                        prior_run_pdfs = [
                            artifact
                            for artifact in prior_run_record.get(
                                "input_artifacts", []
                            )
                            if isinstance(artifact, dict)
                            and artifact.get("kind") == "pdf"
                            and artifact.get("state") == "frozen"
                        ]
                        current_pdfs = [
                            artifact
                            for artifact in run.get("input_artifacts", [])
                            if isinstance(artifact, dict)
                            and artifact.get("kind") == "pdf"
                            and artifact.get("state") == "frozen"
                        ]
                        if (
                            len(current_sources) == 1
                            and current_sources[0].get("sha256")
                            != prior_source.get("sha256")
                            and len(prior_run_pdfs) == 1
                            and len(current_pdfs) == 1
                            and prior_run_pdfs[0].get("sha256")
                            == current_pdfs[0].get("sha256")
                        ):
                            errors.append(
                                "run-pair: revised source cannot reuse the "
                                "predecessor PDF as a matched rendering"
                            )
                        current_alignment_record, _, current_alignment_errors = (
                            _load_bound_json_receipt(
                                evidence_root,
                                run.get("source_pdf_alignment", {}).get(
                                    "receipt_locator"
                                ),
                                run.get("source_pdf_alignment", {}).get(
                                    "receipt_sha256"
                                ),
                                "run-pair: current delta alignment",
                            )
                        )
                        prior_alignment_record, _, prior_alignment_errors = (
                            _load_bound_json_receipt(
                                evidence_root,
                                prior_run_record.get(
                                    "source_pdf_alignment", {}
                                ).get("receipt_locator"),
                                prior_run_record.get(
                                    "source_pdf_alignment", {}
                                ).get("receipt_sha256"),
                                "run-pair: prior delta alignment",
                            )
                        )
                        errors.extend(current_alignment_errors)
                        errors.extend(prior_alignment_errors)

                        def revision_marker(
                            receipt: Any,
                        ) -> dict | None:
                            if not isinstance(receipt, dict):
                                return None
                            matches = [
                                check
                                for check in receipt.get("checks", [])
                                if isinstance(check, dict)
                                and check.get("check_id")
                                == "revision_marker"
                            ]
                            return matches[0] if len(matches) == 1 else None

                        current_marker = revision_marker(
                            current_alignment_record
                        )
                        prior_marker = revision_marker(
                            prior_alignment_record
                        )
                        if run.get("completion") == "complete":
                            if (
                                current_marker is None
                                or prior_marker is None
                            ):
                                errors.append(
                                    "run-pair: delta alignment requires a "
                                    "revision_marker in both versions"
                                )
                            elif (
                                _normalised_alignment_excerpt(
                                    current_marker.get("source_excerpt")
                                )
                                == _normalised_alignment_excerpt(
                                    prior_marker.get("source_excerpt")
                                )
                                or current_marker.get(
                                    "pdf_page_text_sha256"
                                )
                                == prior_marker.get(
                                    "pdf_page_text_sha256"
                                )
                            ):
                                errors.append(
                                    "run-pair: delta revision markers must "
                                    "prove a visible text change across "
                                    "source and PDF"
                                )

                        def visual_receipt(
                            run_record: dict,
                        ) -> tuple[dict | None, dict | None]:
                            visual = next(
                                (
                                    row
                                    for row in run_record.get(
                                        "coverage", {}
                                    ).get("criteria", [])
                                    if isinstance(row, dict)
                                    and row.get("criterion_id")
                                    == "RC-VISUAL-INTEGRITY"
                                ),
                                None,
                            )
                            if (
                                not isinstance(visual, dict)
                                or visual.get("applicability")
                                != "applicable"
                                or visual.get("disposition")
                                not in {
                                    "assessed_no_finding",
                                    "finding_linked",
                                }
                                or len(visual.get("evidence", [])) != 1
                            ):
                                return visual, None
                            visual_evidence = visual["evidence"][0]
                            if not isinstance(visual_evidence, dict):
                                return visual, None
                            receipt, _, receipt_errors = (
                                _load_bound_json_receipt(
                                    evidence_root,
                                    visual_evidence.get(
                                        "rendered_receipt_locator"
                                    ),
                                    visual_evidence.get(
                                        "rendered_receipt_sha256"
                                    ),
                                    "run-pair: delta visual receipt",
                                )
                            )
                            errors.extend(receipt_errors)
                            return visual, receipt

                        current_visual, current_visual_receipt = (
                            visual_receipt(run)
                        )
                        prior_visual, prior_visual_receipt = visual_receipt(
                            prior_run_record
                        )
                        if run.get("completion") == "complete":
                            if (
                                not isinstance(
                                    current_visual_receipt, dict
                                )
                                or not isinstance(
                                    prior_visual_receipt, dict
                                )
                            ):
                                errors.append(
                                    "run-pair: complete delta requires settled "
                                    "visual evidence for both versions"
                                )
                            elif (
                                current_visual_receipt.get(
                                    "rendered_artifact_sha256"
                                )
                                == prior_visual_receipt.get(
                                    "rendered_artifact_sha256"
                                )
                                or (
                                    isinstance(current_marker, dict)
                                    and current_visual_receipt.get("page")
                                    != current_marker.get("pdf_page")
                                )
                                or (
                                    isinstance(prior_marker, dict)
                                    and prior_visual_receipt.get("page")
                                    != prior_marker.get("pdf_page")
                                )
                            ):
                                errors.append(
                                    "run-pair: delta visual receipts must "
                                    "cover and distinguish the revised pages"
                                )
                    for field in ("review_goal", "target", "venue_profile"):
                        if prior_run_record.get(field) != run.get(field):
                            errors.append(
                                "run-pair: delta review scope changed "
                                f"({field}); use a new initial review"
                            )
                    if prior_run_record.get("coverage", {}).get(
                        "matrix_sha256"
                    ) != run.get("coverage", {}).get("matrix_sha256"):
                        errors.append(
                            "run-pair: delta coverage authority changed; use "
                            "a new initial review"
                        )
            if len(author_response_artifacts) == 1:
                try:
                    response_path = _safe_bundle_file(
                        evidence_root,
                        author_response_artifacts[0].get("locator"),
                    )
                    response_raw = response_path.read_bytes()
                    author_response = _load_json_object(
                        response_path, "run-pair author response"
                    )
                except (ValueError, OSError) as exc:
                    errors.append(f"run-pair: author response is invalid: {exc}")
                else:
                    if response_raw != _canonical_json_bytes(author_response):
                        errors.append(
                            "run-pair: author response must be canonical JSON"
                        )
                    response_schema_errors = validate_json_schema_document(
                        author_response,
                        bundle_root,
                        "schemas/author-response.schema.json",
                        "run-pair author response",
                    )
                    errors.extend(response_schema_errors)
                    if not response_schema_errors:
                        author_response_record = author_response
                    prior_finalized_time = (
                        _parse_rfc3339_datetime(
                            prior_run_record.get("finalized_at")
                        )
                        if isinstance(prior_run_record, dict)
                        else None
                    )
                    response_time = _parse_rfc3339_datetime(
                        author_response.get("recorded_at")
                    )
                    current_created_time = _parse_rfc3339_datetime(
                        run.get("created_at")
                    )
                    current_finalized_time = _parse_rfc3339_datetime(
                        run.get("finalized_at")
                    )
                    if (
                        prior_finalized_time is None
                        or response_time is None
                        or current_created_time is None
                        or current_finalized_time is None
                        or not (
                            prior_finalized_time
                            < response_time
                            <= current_created_time
                            < current_finalized_time
                        )
                    ):
                        errors.append(
                            "run-pair: delta chronology must satisfy prior "
                            "finalization < response <= current creation < "
                            "current finalization"
                        )
                    if (
                        isinstance(prior_run_record, dict)
                        and author_response.get("prior_run_id")
                        != prior_run_record.get("run_id")
                    ):
                        errors.append(
                            "run-pair: author response does not bind prior run"
                        )
                    current_sources = [
                        artifact
                        for artifact in run.get("input_artifacts", [])
                        if isinstance(artifact, dict)
                        and artifact.get("kind") == "source"
                        and artifact.get("state") == "frozen"
                    ]
                    expected_response_hashes = {
                        "prior_run_sha256":
                            prior_run_artifacts[0].get("sha256")
                            if len(prior_run_artifacts) == 1
                            else None,
                        "prior_ledger_sha256":
                            prior_artifacts[0].get("sha256")
                            if len(prior_artifacts) == 1
                            else None,
                        "prior_source_sha256":
                            prior_source_artifacts[0].get("sha256")
                            if len(prior_source_artifacts) == 1
                            else None,
                        "revised_source_sha256":
                            current_sources[0].get("sha256")
                            if len(current_sources) == 1
                            else None,
                    }
                    for field, expected in expected_response_hashes.items():
                        if author_response.get(field) != expected:
                            errors.append(
                                "run-pair: author response does not bind the "
                                f"exact {field.replace('_sha256', '').replace('_', ' ')}"
                            )
            if len(prior_artifacts) == 1:
                try:
                    prior_path = _safe_bundle_file(
                        evidence_root, prior_artifacts[0].get("locator")
                    )
                    prior_ledger = _load_json_object(
                        prior_path, "run-pair prior ledger"
                    )
                except ValueError as exc:
                    errors.append(f"run-pair: prior ledger is invalid: {exc}")
                else:
                    prior_errors = validate_finding_ledger(
                        prior_ledger, bundle_root
                    )
                    errors.extend(
                        f"run-pair: prior ledger: {error}"
                        for error in prior_errors
                    )
                    if not prior_errors:
                        if isinstance(prior_run_record, dict):
                            if (
                                prior_run_record.get("run_id")
                                != prior_ledger.get("run_id")
                                or prior_run_record.get("run_id")
                                == run.get("run_id")
                            ):
                                errors.append(
                                    "run-pair: prior run and prior ledger must "
                                    "share a non-current run_id"
                                )
                            prior_output = prior_run_record.get(
                                "output_artifacts", {}
                            ).get("finding_ledger")
                            if (
                                not isinstance(prior_output, dict)
                                or prior_output.get("status") != "produced"
                                or prior_output.get("locator")
                                != prior_artifacts[0].get("locator")
                                or prior_output.get("sha256")
                                != prior_artifacts[0].get("sha256")
                            ):
                                errors.append(
                                    "run-pair: prior run finding-ledger output "
                                    "does not bind the frozen prior ledger"
                                )
                            prior_time = _parse_rfc3339_datetime(
                                prior_run_record.get("created_at")
                            )
                            current_time = _parse_rfc3339_datetime(
                                run.get("created_at")
                            )
                            if (
                                prior_time is not None
                                and current_time is not None
                                and prior_time >= current_time
                            ):
                                errors.append(
                                    "run-pair: prior run must precede the "
                                    "current delta run"
                                )
                            prior_pair_errors = validate_run_pair(
                                prior_run_record,
                                prior_ledger,
                                coverage_matrix,
                                bundle_root,
                                evidence_root=evidence_root,
                            )
                            errors.extend(
                                "run-pair: prior run semantic validation: "
                                f"{error}"
                                for error in prior_pair_errors
                            )
                            prior_input_by_id = {
                                artifact.get("artifact_id"): artifact
                                for artifact in prior_run_record.get(
                                    "input_artifacts", []
                                )
                                if isinstance(artifact, dict)
                                and isinstance(
                                    artifact.get("artifact_id"), str
                                )
                            }
                            for prior_finding in prior_ledger.get(
                                "findings", []
                            ):
                                if not isinstance(prior_finding, dict):
                                    continue
                                prior_evidence = prior_finding.get(
                                    "evidence", {}
                                )
                                prior_provenance = prior_finding.get(
                                    "provenance", {}
                                )
                                prior_input = (
                                    prior_input_by_id.get(
                                        prior_evidence.get("artifact_id")
                                    )
                                    if isinstance(prior_evidence, dict)
                                    else None
                                )
                                if (
                                    not isinstance(prior_input, dict)
                                    or prior_input.get("state") != "frozen"
                                ):
                                    errors.append(
                                        "run-pair: prior finding evidence does "
                                        "not resolve to a frozen prior-run "
                                        "artifact: "
                                        f"{prior_finding.get('finding_id')}"
                                    )
                                    continue
                                if (
                                    not isinstance(prior_provenance, dict)
                                    or prior_provenance.get(
                                        "primary_artifact_lineage_id"
                                    )
                                    != prior_input.get("lineage_id")
                                ):
                                    errors.append(
                                        "run-pair: prior finding lineage does "
                                        "not bind its prior-run artifact: "
                                        f"{prior_finding.get('finding_id')}"
                                    )
                                verification = prior_evidence.get(
                                    "anchor_verification", {}
                                )
                                excerpt = (
                                    verification.get("excerpt")
                                    if isinstance(verification, dict)
                                    else None
                                )
                                if not isinstance(verification, dict):
                                    errors.append(
                                        "run-pair: prior finding lacks "
                                        "anchor verification: "
                                        f"{prior_finding.get('finding_id')}"
                                    )
                                elif (
                                    verification.get("method")
                                    == "utf8_exact_excerpt"
                                    and prior_input.get("kind") == "source"
                                ):
                                    if (
                                        not _is_nonblank_string(excerpt)
                                        or verification.get("excerpt_sha256")
                                        != hashlib.sha256(
                                            str(excerpt).encode("utf-8")
                                        ).hexdigest()
                                    ):
                                        errors.append(
                                            "run-pair: prior finding lacks "
                                            "exact anchor verification: "
                                            f"{prior_finding.get('finding_id')}"
                                        )
                                        continue
                                    try:
                                        prior_source_path = _safe_bundle_file(
                                            evidence_root,
                                            prior_input.get("locator"),
                                        )
                                        prior_source_bytes = (
                                            prior_source_path.read_bytes()
                                        )
                                        prior_source_bytes.decode("utf-8")
                                    except (
                                        ValueError,
                                        OSError,
                                        UnicodeDecodeError,
                                    ) as exc:
                                        errors.append(
                                            "run-pair: prior finding source is "
                                            f"unreadable: {exc}"
                                        )
                                    else:
                                        span_errors, _ = (
                                            _validate_exact_span_against_source(
                                                prior_evidence,
                                                verification,
                                                prior_source_bytes,
                                                "run-pair: prior finding "
                                                "exact anchor span",
                                            )
                                        )
                                        errors.extend(span_errors)
                                        if (
                                            excerpt.encode("utf-8")
                                            not in prior_source_bytes
                                        ):
                                            errors.append(
                                                "run-pair: prior finding anchor "
                                                "is absent from prior source: "
                                                f"{prior_finding.get('finding_id')}"
                                            )
                                elif (
                                    verification.get("method")
                                    == "rendered_receipt"
                                    and prior_input.get("kind") == "pdf"
                                    and prior_run_record.get(
                                        "source_pdf_alignment", {}
                                    ).get("status") == "matched"
                                    and prior_run_record.get(
                                        "source_pdf_alignment", {}
                                    ).get("verified") is True
                                    and prior_run_record.get(
                                        "source_pdf_alignment", {}
                                    ).get("pdf_artifact_id")
                                    == prior_input.get("artifact_id")
                                ):
                                    rendered_errors, rendered_verified = (
                                        _validate_rendered_evidence_receipt(
                                            verification=verification,
                                            evidence=prior_evidence,
                                            artifact=prior_input,
                                            evidence_root=evidence_root,
                                            schema_root=bundle_root,
                                            subject_id=str(
                                                prior_finding.get("finding_id")
                                            ),
                                            prefix=(
                                                "run-pair: prior finding "
                                                "rendered anchor"
                                            ),
                                            run_created_at=(
                                                prior_run_record.get(
                                                    "created_at"
                                                )
                                            ),
                                            run_finalized_at=(
                                                prior_run_record.get(
                                                    "finalized_at"
                                                )
                                            ),
                                        )
                                    )
                                    errors.extend(rendered_errors)
                                    if not rendered_verified:
                                        errors.append(
                                            "run-pair: prior finding rendered "
                                            "anchor is not verified: "
                                            f"{prior_finding.get('finding_id')}"
                                        )
                                else:
                                    errors.append(
                                        "run-pair: prior finding evidence "
                                        "method does not match its prior-run "
                                        f"artifact: {prior_finding.get('finding_id')}"
                                    )
                        if prior_ledger.get("run_id") == run.get("run_id"):
                            errors.append(
                                "run-pair: prior ledger run_id must differ from "
                                "the current run"
                            )
                        prior_ids = {
                            finding.get("finding_id")
                            for finding in prior_ledger.get("findings", [])
                            if isinstance(finding, dict)
                        }
                        prior_surviving = {
                            finding.get("finding_id")
                            for finding in prior_ledger.get("findings", [])
                            if isinstance(finding, dict)
                            and finding.get("adjudication_status")
                            not in {"merged", "rejected"}
                        }
                        if isinstance(author_response_record, dict):
                            transitions = author_response_record.get(
                                "transitions", []
                            )
                            transition_ids = [
                                row.get("prior_finding_id")
                                for row in transitions
                                if isinstance(row, dict)
                            ]
                            if (
                                len(transition_ids) != len(
                                    set(transition_ids)
                                )
                                or set(transition_ids) != prior_surviving
                            ):
                                errors.append(
                                    "run-pair: author response transitions "
                                    "must exactly account for every surviving "
                                    "prior finding"
                                )
                        carried_ids = [
                            finding.get("prior_finding_id")
                            for finding in ledger.get("findings", [])
                            if isinstance(finding, dict)
                            and finding.get("delta_status") != "new"
                        ]
                        for missing in sorted(
                            prior_surviving - set(carried_ids)
                        ):
                            errors.append(
                                "run-pair: prior surviving finding is not "
                                f"accounted for: {missing}"
                            )
                        for unknown in sorted(
                            set(carried_ids) - prior_surviving
                        ):
                            errors.append(
                                "run-pair: carried finding does not reference a "
                                f"prior surviving finding: {unknown}"
                            )
                        if len(carried_ids) != len(set(carried_ids)):
                            errors.append(
                                "run-pair: prior finding is accounted for more "
                                "than once"
                            )
                        for resurrected in sorted(
                            {
                                finding.get("finding_id")
                                for finding in ledger.get("findings", [])
                                if isinstance(finding, dict)
                                and finding.get("delta_status") == "new"
                            }
                            & prior_ids
                        ):
                            errors.append(
                                "run-pair: new finding ID already exists in "
                                f"prior ledger: {resurrected}"
                            )
                        prior_by_id = {
                            finding.get("finding_id"): finding
                            for finding in prior_ledger.get("findings", [])
                            if isinstance(finding, dict)
                        }
                        prior_run_for_coverage = (
                            prior_run_record
                            if isinstance(prior_run_record, dict)
                            else {}
                        )
                        prior_coverage_by_id = {
                            row.get("criterion_id"): row
                            for row in prior_run_for_coverage.get(
                                "coverage", {}
                            ).get("criteria", [])
                            if isinstance(row, dict)
                            and isinstance(
                                row.get("criterion_id"), str
                            )
                        }
                        current_coverage_by_id = {
                            row.get("criterion_id"): row
                            for row in run.get("coverage", {}).get(
                                "criteria", []
                            )
                            if isinstance(row, dict)
                            and isinstance(
                                row.get("criterion_id"), str
                            )
                        }
                        response_id = (
                            author_response_record.get("response_id")
                            if isinstance(author_response_record, dict)
                            else None
                        )
                        for criterion_id in sorted(
                            set(prior_coverage_by_id)
                            | set(current_coverage_by_id)
                        ):
                            prior_row = prior_coverage_by_id.get(
                                criterion_id, {}
                            )
                            current_row = current_coverage_by_id.get(
                                criterion_id, {}
                            )
                            prior_applicability = prior_row.get(
                                "applicability"
                            )
                            current_applicability = current_row.get(
                                "applicability"
                            )
                            reconciliation = current_row.get(
                                "delta_applicability_reconciliation"
                            )
                            if (
                                prior_applicability
                                != current_applicability
                            ):
                                if not isinstance(reconciliation, dict):
                                    errors.append(
                                        "run-pair: delta applicability "
                                        "change requires explicit "
                                        f"reconciliation: {criterion_id}"
                                    )
                                    continue
                                expected_reconciliation = {
                                    "prior_applicability":
                                        prior_applicability,
                                    "current_applicability":
                                        current_applicability,
                                    "author_response_id": response_id,
                                }
                                if any(
                                    reconciliation.get(field) != value
                                    for field, value
                                    in expected_reconciliation.items()
                                ):
                                    errors.append(
                                        "run-pair: delta applicability "
                                        "reconciliation does not bind the "
                                        f"actual transition: {criterion_id}"
                                    )
                                evidence_ids = reconciliation.get(
                                    "evidence_artifact_ids", []
                                )
                                if (
                                    not isinstance(evidence_ids, list)
                                    or not evidence_ids
                                    or not set(evidence_ids).issubset(
                                        artifact_ids
                                    )
                                ):
                                    errors.append(
                                        "run-pair: delta applicability "
                                        "reconciliation lacks bound evidence "
                                        f"artifacts: {criterion_id}"
                                    )
                            elif reconciliation is not None:
                                errors.append(
                                    "run-pair: unchanged applicability "
                                    "cannot claim a delta reconciliation: "
                                    f"{criterion_id}"
                                )
                        current_by_prior_id = {
                            finding.get("prior_finding_id"): finding
                            for finding in ledger.get("findings", [])
                            if isinstance(finding, dict)
                            and finding.get("delta_status") != "new"
                        }
                        transition_by_id = {
                            row.get("prior_finding_id"): row
                            for row in (
                                author_response_record.get("transitions", [])
                                if isinstance(author_response_record, dict)
                                else []
                            )
                            if isinstance(row, dict)
                        }
                        for prior_id, current in current_by_prior_id.items():
                            prior = prior_by_id.get(prior_id)
                            if not isinstance(prior, dict):
                                continue
                            current_evidence = current.get("evidence", {})
                            prior_evidence = prior.get("evidence", {})
                            identity_pairs = (
                                (
                                    "criterion",
                                    current.get("criterion"),
                                    prior.get("criterion"),
                                ),
                                (
                                    "normalised claim",
                                    _normalised_claim(current.get("claim")),
                                    _normalised_claim(prior.get("claim")),
                                ),
                                (
                                    "semantic anchor",
                                    current_evidence.get("semantic_anchor")
                                    if isinstance(current_evidence, dict)
                                    else None,
                                    prior_evidence.get("semantic_anchor")
                                    if isinstance(prior_evidence, dict)
                                    else None,
                                ),
                                (
                                    "primary artifact lineage",
                                    current.get("provenance", {}).get(
                                        "primary_artifact_lineage_id"
                                    ),
                                    prior.get("provenance", {}).get(
                                        "primary_artifact_lineage_id"
                                    ),
                                ),
                            )
                            for label, current_value, prior_value in identity_pairs:
                                if current_value != prior_value:
                                    errors.append(
                                        "run-pair: carried finding semantic "
                                        f"identity changed ({label}): {prior_id}"
                                    )
                            effective_current = current.get("decision_impact")
                            if current.get("adjudication_status") == "rejected":
                                effective_current = "none"
                            current_rank = _DECISION_IMPACT_RANK.get(
                                effective_current
                            )
                            prior_rank = _DECISION_IMPACT_RANK.get(
                                prior.get("decision_impact")
                            )
                            if (
                                isinstance(current_rank, int)
                                and isinstance(prior_rank, int)
                            ):
                                derived_change = (
                                    "unchanged"
                                    if current_rank == prior_rank
                                    else (
                                        "upgraded"
                                        if current_rank > prior_rank
                                        else "downgraded"
                                    )
                                )
                                if current.get(
                                    "impact_change"
                                ) != derived_change:
                                    errors.append(
                                        "run-pair: carried finding "
                                        "impact_change is not the derived "
                                        f"impact_change: {prior_id}"
                                    )
                            transition = transition_by_id.get(prior_id)
                            successor_evidence: dict | None = None
                            successor_verified = False
                            if isinstance(transition, dict):
                                if (
                                    transition.get("criterion_id")
                                    != prior.get("criterion")
                                ):
                                    errors.append(
                                        "run-pair: author response transition "
                                        "criterion does not bind the prior "
                                        f"finding: {prior_id}"
                                    )
                                expected_prior_claim_sha256 = hashlib.sha256(
                                    str(prior.get("claim", "")).encode("utf-8")
                                ).hexdigest()
                                if (
                                    transition.get("prior_claim_sha256")
                                    != expected_prior_claim_sha256
                                ):
                                    errors.append(
                                        "run-pair: author response transition "
                                        "claim hash does not bind the prior "
                                        f"finding: {prior_id}"
                                    )
                                candidate_successor = transition.get(
                                    "successor_evidence"
                                )
                                if isinstance(candidate_successor, dict):
                                    successor_evidence = candidate_successor
                                    errors.extend(
                                        _validate_evidence(
                                            successor_evidence,
                                            "run-pair: author response "
                                            f"successor evidence {prior_id}",
                                            material=True,
                                        )
                                    )
                                    if (
                                        successor_evidence.get(
                                            "semantic_anchor"
                                        )
                                        != prior_evidence.get(
                                            "semantic_anchor"
                                        )
                                    ):
                                        errors.append(
                                            "run-pair: author response "
                                            "successor semantic anchor does "
                                            "not bind the prior finding: "
                                            f"{prior_id}"
                                        )
                                    successor_artifact = artifact_by_id.get(
                                        successor_evidence.get("artifact_id")
                                    )
                                    successor_verification = (
                                        successor_evidence.get(
                                            "anchor_verification", {}
                                        )
                                    )
                                    if (
                                        not isinstance(successor_artifact, dict)
                                        or successor_artifact.get("kind")
                                        not in {"source", "pdf"}
                                        or successor_artifact.get("state")
                                        != "frozen"
                                    ):
                                        errors.append(
                                            "run-pair: author response "
                                            "successor must bind the current "
                                            f"source or PDF: {prior_id}"
                                        )
                                    elif (
                                        isinstance(
                                            successor_verification, dict
                                        )
                                        and successor_verification.get(
                                            "method"
                                        )
                                        == "utf8_exact_excerpt"
                                        and successor_artifact.get("kind")
                                        == "source"
                                    ):
                                        try:
                                            successor_path = (
                                                _safe_bundle_file(
                                                    evidence_root,
                                                    successor_artifact.get(
                                                        "locator"
                                                    ),
                                                )
                                            )
                                            successor_bytes = (
                                                successor_path.read_bytes()
                                            )
                                            successor_bytes.decode("utf-8")
                                        except (
                                            ValueError,
                                            OSError,
                                            UnicodeDecodeError,
                                        ) as exc:
                                            errors.append(
                                                "run-pair: author response "
                                                "successor source is "
                                                f"unreadable: {exc}"
                                            )
                                        else:
                                            (
                                                successor_errors,
                                                successor_verified,
                                            ) = (
                                                _validate_exact_span_against_source(
                                                    successor_evidence,
                                                    successor_verification,
                                                    successor_bytes,
                                                    "run-pair: author "
                                                    "response successor",
                                                )
                                            )
                                            errors.extend(successor_errors)
                                    elif (
                                        isinstance(
                                            successor_verification, dict
                                        )
                                        and successor_verification.get(
                                            "method"
                                        )
                                        == "rendered_receipt"
                                        and successor_artifact.get("kind")
                                        == "pdf"
                                    ):
                                        (
                                            successor_errors,
                                            successor_verified,
                                        ) = _validate_rendered_evidence_receipt(
                                            verification=(
                                                successor_verification
                                            ),
                                            evidence=successor_evidence,
                                            artifact=successor_artifact,
                                            evidence_root=evidence_root,
                                            schema_root=bundle_root,
                                            subject_id=str(prior_id),
                                            prefix=(
                                                "run-pair: author response "
                                                "successor"
                                            ),
                                            run_created_at=run.get(
                                                "created_at"
                                            ),
                                            run_finalized_at=run.get(
                                                "finalized_at"
                                            ),
                                        )
                                        errors.extend(successor_errors)
                                    prior_verification = (
                                        prior_evidence.get(
                                            "anchor_verification", {}
                                        )
                                        if isinstance(prior_evidence, dict)
                                        else {}
                                    )
                                    if (
                                        isinstance(
                                            successor_verification, dict
                                        )
                                        and isinstance(
                                            prior_verification, dict
                                        )
                                        and successor_verification.get(
                                            "excerpt_sha256"
                                        )
                                        == prior_verification.get(
                                            "excerpt_sha256"
                                        )
                                        and successor_evidence.get(
                                            "source_anchor"
                                        )
                                        == prior_evidence.get(
                                            "source_anchor"
                                        )
                                    ):
                                        successor_verified = False
                                        errors.append(
                                            "run-pair: author response "
                                            "successor cannot reuse the prior "
                                            f"finding evidence: {prior_id}"
                                        )
                                if (
                                    transition.get("disposition")
                                    in {
                                        "addressed",
                                        "partially_addressed",
                                    }
                                    and not successor_verified
                                ):
                                    errors.append(
                                        "run-pair: addressed author response "
                                        "requires verified typed successor "
                                        f"evidence: {prior_id}"
                                    )
                            expected_transition = {
                                "resolved": {"addressed"},
                                "partially_resolved": {
                                    "partially_addressed",
                                    "addressed",
                                },
                                "still_open": {
                                    "not_addressed",
                                    "disputed",
                                },
                                "made_worse": {
                                    "not_addressed",
                                    "partially_addressed",
                                },
                            }.get(current.get("delta_status"), set())
                            if (
                                isinstance(transition, dict)
                                and transition.get("disposition")
                                not in expected_transition
                            ):
                                errors.append(
                                    "run-pair: author response transition "
                                    "contradicts the current delta status: "
                                    f"{prior_id}"
                                )
                            current_criterion_row = (
                                current_coverage_by_id.get(
                                    current.get("criterion"), {}
                                )
                            )
                            if (
                                isinstance(transition, dict)
                                and current_criterion_row.get(
                                    "applicability"
                                )
                                == "inapplicable"
                                and (
                                    transition.get("disposition")
                                    != "disputed"
                                    or current.get(
                                        "adjudication_status"
                                    )
                                    != "rejected"
                                    or current.get(
                                        "closure_requirement", {}
                                    ).get("state")
                                    != "not_applicable"
                                )
                            ):
                                errors.append(
                                    "run-pair: an inapplicable carried issue "
                                    "must be explicitly disputed, rejected, "
                                    f"and non-obligating: {prior_id}"
                                )
                            if (
                                current.get("delta_status") == "resolved"
                                and current.get("adjudication_status")
                                not in {"merged", "rejected"}
                            ):
                                closure = current.get(
                                    "closure_requirement", {}
                                )
                                resolution = (
                                    closure.get("resolution_evidence")
                                    if isinstance(closure, dict)
                                    else None
                                )
                                if not isinstance(resolution, dict):
                                    errors.append(
                                        "run-pair: resolved delta requires "
                                        "typed current byte-bound resolution "
                                        f"evidence: {prior_id}"
                                    )
                                    continue
                                if (
                                    not isinstance(
                                        author_response_record, dict
                                    )
                                    or resolution.get("author_response_id")
                                    != author_response_record.get(
                                        "response_id"
                                    )
                                    or resolution.get("prior_finding_id")
                                    != prior_id
                                    or not isinstance(transition, dict)
                                    or transition.get("disposition")
                                    != "addressed"
                                ):
                                    errors.append(
                                        "run-pair: resolution evidence does "
                                        "not bind an addressed author-response "
                                        f"transition: {prior_id}"
                                    )
                                resolution_core = {
                                    key: resolution.get(key)
                                    for key in (
                                        "artifact_id",
                                        "source_anchor",
                                        "semantic_anchor",
                                        "observation",
                                        "anchor_verification",
                                    )
                                }
                                if (
                                    not isinstance(
                                        successor_evidence, dict
                                    )
                                    or not successor_verified
                                    or resolution_core
                                    != successor_evidence
                                ):
                                    errors.append(
                                        "run-pair: resolution evidence must "
                                        "exactly bind the author-response "
                                        f"successor evidence: {prior_id}"
                                    )
                                resolution_artifact = artifact_by_id.get(
                                    resolution.get("artifact_id")
                                )
                                if (
                                    not isinstance(
                                        resolution_artifact, dict
                                    )
                                    or resolution_artifact.get("kind")
                                    not in {"source", "pdf"}
                                    or resolution_artifact.get("state")
                                    != "frozen"
                                ):
                                    errors.append(
                                        "run-pair: resolution evidence must "
                                        "bind the current source or matched "
                                        f"current PDF: {prior_id}"
                                    )
                                    continue
                                resolution_verification = resolution.get(
                                    "anchor_verification", {}
                                )
                                resolution_verified = False
                                if (
                                    isinstance(
                                        resolution_verification, dict
                                    )
                                    and resolution_verification.get("method")
                                    == "utf8_exact_excerpt"
                                    and resolution_artifact.get("kind")
                                    == "source"
                                ):
                                    try:
                                        resolution_path = _safe_bundle_file(
                                            evidence_root,
                                            resolution_artifact.get(
                                                "locator"
                                            ),
                                        )
                                        resolution_bytes = (
                                            resolution_path.read_bytes()
                                        )
                                        resolution_bytes.decode("utf-8")
                                    except (
                                        ValueError,
                                        OSError,
                                        UnicodeDecodeError,
                                    ) as exc:
                                        errors.append(
                                            "run-pair: resolution source is "
                                            f"unreadable: {exc}"
                                        )
                                    else:
                                        resolution_errors, (
                                            resolution_verified
                                        ) = _validate_exact_span_against_source(
                                            resolution,
                                            resolution_verification,
                                            resolution_bytes,
                                            "run-pair: resolution evidence",
                                        )
                                        errors.extend(resolution_errors)
                                        prior_excerpt = (
                                            prior_evidence.get(
                                                "anchor_verification", {}
                                            ).get("excerpt")
                                            if isinstance(
                                                prior_evidence, dict
                                            )
                                            else None
                                        )
                                        if (
                                            resolution_verification.get(
                                                "excerpt"
                                            )
                                            == prior_excerpt
                                        ):
                                            resolution_verified = False
                                            errors.append(
                                                "run-pair: resolution "
                                                "evidence cannot merely repeat "
                                                "the prior finding excerpt"
                                            )
                                elif (
                                    isinstance(
                                        resolution_verification, dict
                                    )
                                    and resolution_verification.get("method")
                                    == "rendered_receipt"
                                    and resolution_artifact.get("kind")
                                    == "pdf"
                                ):
                                    (
                                        resolution_errors,
                                        resolution_verified,
                                    ) = _validate_rendered_evidence_receipt(
                                        verification=resolution_verification,
                                        evidence=resolution,
                                        artifact=resolution_artifact,
                                        evidence_root=evidence_root,
                                        schema_root=bundle_root,
                                        subject_id=str(prior_id),
                                        prefix=(
                                            "run-pair: resolution evidence"
                                        ),
                                        run_created_at=run.get("created_at"),
                                        run_finalized_at=run.get(
                                            "finalized_at"
                                        ),
                                    )
                                    errors.extend(resolution_errors)
                                if not resolution_verified:
                                    errors.append(
                                        "run-pair: resolved delta lacks "
                                        "successful current byte-bound "
                                        f"resolution evidence: {prior_id}"
                                    )
        coverage_ids: set[str] = set()
        coverage_criteria_by_finding: dict[str, set[str]] = {}
        coverage = run.get("coverage")
        if isinstance(coverage, dict):
            for row in coverage.get("criteria", []):
                if isinstance(row, dict):
                    ids = row.get("finding_ids")
                    if isinstance(ids, list):
                        for item in ids:
                            if not isinstance(item, str):
                                continue
                            coverage_ids.add(item)
                            coverage_criteria_by_finding.setdefault(
                                item, set()
                            ).add(row.get("criterion_id"))
        for unknown in sorted(coverage_ids - ledger_ids):
            errors.append(
                f"run-pair: coverage references unknown finding_id: {unknown}"
            )
        surviving_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status")
            in {"retained", "unresolved"}
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
        ae_text = human_outputs.get("ae_assessment", "")
        if "ae_assessment" in human_outputs:
            for missing in sorted(surviving_ids - set(
                re.findall(r"F-[0-9a-f]{16}", ae_text)
            )):
                errors.append(
                    f"run-pair: AE assessment omits surviving finding: {missing}"
                )
            for criterion_id in _coverage_ids(coverage_matrix):
                if criterion_id not in ae_text:
                    errors.append(
                        "run-pair: AE assessment omits canonical criterion: "
                        f"{criterion_id}"
                    )
        summary_required_ids = {
            finding.get("finding_id")
            for finding in ledger.get("findings", [])
            if isinstance(finding, dict)
            and finding.get("adjudication_status") in {"retained", "unresolved"}
            and finding.get("decision_impact")
            in {"fundamental", "material", "limited"}
        }
        summary_text = human_outputs.get("review_summary", "")
        if "review_summary" in human_outputs:
            for missing in sorted(summary_required_ids - set(
                re.findall(r"F-[0-9a-f]{16}", summary_text)
            )):
                errors.append(
                    f"run-pair: review summary omits decision-relevant finding: "
                    f"{missing}"
                )
            for limitation in run.get("limitations", []):
                if limitation not in summary_text:
                    errors.append(
                        "run-pair: review summary omits run limitation: "
                        f"{limitation}"
                    )
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
            else:
                target_row = next(
                    (
                        item
                        for item in ledger.get("findings", [])
                        if isinstance(item, dict)
                        and item.get("finding_id") == target
                    ),
                    None,
                )
                if not isinstance(target_row, dict) or target_row.get(
                    "adjudication_status"
                ) not in {"retained", "unresolved"}:
                    errors.append(
                        f"run-pair: merge target is not canonical: {target}"
                    )
                else:
                    target_sources = target_row.get("provenance", {}).get(
                        "merged_from_ids", []
                    )
                    if finding.get("finding_id") not in target_sources:
                        errors.append(
                            "run-pair: merge target does not reciprocally "
                            f"record source: {finding.get('finding_id')}"
                        )
        for finding in ledger.get("findings", []):
            if not isinstance(finding, dict):
                continue
            finding_id = finding.get("finding_id")
            if finding_id not in coverage_criteria_by_finding:
                continue
            allowed_criteria = {
                finding.get("criterion"),
                *(
                    finding.get("related_criteria")
                    if isinstance(finding.get("related_criteria"), list)
                    else []
                ),
            }
            for criterion_id in sorted(
                coverage_criteria_by_finding[finding_id] - allowed_criteria
            ):
                errors.append(
                    "run-pair: coverage criterion does not match finding "
                    f"{finding_id}: {criterion_id}"
                )
        for missing in sorted(surviving_ids - coverage_ids):
            errors.append(
                f"run-pair: surviving finding missing from coverage: {missing}"
            )
        authority = run.get("authorisation")
        if isinstance(authority, dict) and (
            authority.get("authorised") is not True
            or authority.get("policy_status") != "permitted"
        ) and ledger.get("findings"):
            errors.append(
                "run-pair: authority/policy preflight stop requires an empty "
                "finding ledger"
            )
    return sorted(set(errors))
