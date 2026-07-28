"""Release-governed deterministic scorer for adapter evaluation outputs."""

from __future__ import annotations

from typing import Any


SCORER_ID = "codex-evaluation-harness"
SCORER_VERSION = "1.0.0"


def score_assertions(
    expected_by_id: dict[str, bool],
    observations: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Return a strict pass/fail result and bounded structural diagnostics."""

    observed_by_id = {
        item.get("assertion_id"): item.get("observed")
        for item in observations
        if isinstance(item, dict)
    }
    errors: list[str] = []
    if len(observations) != len(observed_by_id):
        errors.append("duplicate output assertion ID")
    if set(observed_by_id) != set(expected_by_id):
        errors.append("output does not exactly cover oracle")
    if errors:
        return "fail", errors
    if all(
        isinstance(observed_by_id[key], bool)
        and observed_by_id[key] is expected
        for key, expected in expected_by_id.items()
    ):
        return "pass", []
    return "fail", []
