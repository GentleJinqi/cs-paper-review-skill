# Adjudicated Assessment

## Provenance

- Run ID:
- Canonical JSON task-report locator and SHA-256:
- Frozen report IDs and hashes:
- Frozen finding-ledger input:
- Coverage-matrix hash:
- Target profile ID or `unknown`:
- Adjudication task/configuration proof, when applicable:

## Candidate disposition

| Candidate ID | Result | Canonical target | Evidence and rationale | Decision impact | Dissent retained | Closure owner/gate |
|---|---|---|---|---|---|---|

Allowed adjudication results are retained, merged, rejected, and unresolved.
A lower delta impact is recorded separately as `impact_change: downgraded`.
Merged records preserve unique source IDs and one existing canonical target.
Rejected records remain auditable but are not obligations.

## Canonical coverage

| Criterion ID | Applicability | Disposition | Evidence | Stage/task IDs | Canonical finding IDs | Rationale |
|---|---|---|---|---|---|---|

Every canonical criterion appears exactly once. Repetition does not increase
consensus. Preserve evidence-backed minority concerns and explain unresolved
conflicts.

## Portable assessment

- Contribution and importance:
- Evidence-supported strengths:
- Fundamental findings:
- Material findings:
- Limited findings:
- Advisory observations:
- Author gates:
- Verification gaps:
- Submission-readiness gates:

## Target-conditioned assessment

- Profile/version:
- Mapping from portable evidence:
- Disabled fields due to missing or stale profile:

Complete only fields defined for the applicable area-chair or meta-reviewer
role by the validated exact-target profile. Record each value first in the
structured `venue_assessment`; this table is a nonauthoritative view.

| Field ID | Role | Required | Type and allowed scale/labels | Recorded value | Anchor and source IDs |
|---|---|---|---|---|---|

Target conditioning cannot waive core criteria or become acceptance
probability.

## Completion and non-claims

- Completion: complete / partial / blocked
- Unsettled evidence:
- Limitations:
- No invented findings:
- Mutation-verification evidence or limitation:

This file is a structural reference, not a fillable valid output. Generate the
complete document, including its exact machine-binding object, with
`scripts/render_human_binding.py`. Hand editing a generated view invalidates
its bound digest.
