# Review Workspace Protocol

Keep review artifacts organized even in an empty or messy repository.

## Path Priority

1. User-specified review output path.
2. Repo instructions such as `AGENTS.md`.
3. Default artifact root: `.paper-review/runs/<date>-<venue>-<tier>-NN/`.

## Required Run Files

Every completed run must include:

- `frozen-inputs.md`;
- `official-rubric.md`;
- `review-run-contract.md`;
- `issue-ledger.md`;
- `review-summary.md`;
- `subagent-cleanup.md`.

Optional files may include reviewer reports, audits, regression ledgers, new-risk ledgers, rejected suggestions, benchmark calibration, and final meta-adjudication.

## Source Discipline

Use LaTeX as the content source of truth when available. Use PDF for layout, reading order, visual density, figures, tables, and submission readiness. If both exist, compare title and section anchors where practical and warn if the PDF appears stale.

Do not write artifacts into the manuscript source directory unless the user explicitly asks.
