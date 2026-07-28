---
name: cs-paper-review
description: Use for an author-side pre-submission or delta review of a CS, ML, CV, NLP, or related paper when evidence-grounded scientific findings, venue-conditioned assessment, or source/PDF verification are needed.
---

# CS Paper Review

Run a review, not a revision. The output is an evidence-bounded assessment and
finding ledger. Do not edit the manuscript, run experiments, or invent missing
facts unless the user separately authorises a later workflow.
This review-only boundary remains in force through completion.

## Intake

Before substantive review:

1. Establish the user's authority, review capacity, confidentiality class,
   governing AI policy, permitted processing, external-transmission authority,
   retention, and output boundary. Follow
   `references/privacy-and-authorisation.md`. Stop if authority or policy
   prohibits the intended use.
2. Record the review goal and `initial` or `delta` kind. Freeze exact source,
   PDF, supplement, prior-ledger, and response artifacts with hashes and
   lineage. Source governs scientific content; only a matching PDF governs
   rendered layout. Missing or mismatched evidence yields partial or blocked
   conclusions, never a guessed pass or defect.
3. Ask for target venue, year, and track. A target may remain `unknown`; do not
   substitute a venue. When a current first-party profile is available, freeze
   it as a soft assessment overlay. Do not infer acceptance probability.
4. Create the run manifest from `templates/run-manifest.json`, bind it to
   `references/review-coverage.json`, and keep `review_only: true`.

## Route

Read only what the run needs:

- always: `references/scientific-core.md`,
  `references/review-coverage.md`, `references/review-workflow.md`,
  `references/finding-contract.md`, and
  `references/privacy-and-authorisation.md`;
- delta review: `references/delta-review.md` and the frozen prior ledger;
- Codex Sol Ultra execution: `adapters/codex-gpt-5.6-sol-ultra.md` and
  `adapters/codex/adapter-manifest.json`;
- human views: `templates/reviewer-report.md`,
  `templates/ae-assessment.md`, and `templates/review-summary.md`.

The adapter's lifecycle candidates remain inactive until an evaluated
promotion record selects one. Until then, record compatibility as
`evaluation_pending`; never turn requested configuration into runtime
attestation.

## Execute

1. Build the criterion-by-criterion coverage and risk map.
2. Assess frozen inputs without prior-report contamination when independence
   is claimed.
3. Verify material candidates against exact artifacts and authorised sources.
4. Adjudicate evidence, semantic duplicates, conflicts, and dissent into one
   canonical finding ledger.
5. Apply a valid target profile only after the portable scientific assessment;
   keep native labels separate from portable decision impact.
6. Reconcile every criterion, finding, report, limitation, and late result.

Delegation is optional and quality-driven. It follows uncovered evidence risk,
not a roster or task quota. Only the root updates canonical artifacts.

## Outputs and stopping

Each canonical criterion receives exactly one recorded disposition, including
justified `inapplicable` and explicit `uncertain` states. Every material
finding needs artifact and semantic anchors, verification state, decision
impact, action type, closure gate, dissent, and provenance.

Use:

- `complete` only when all applicable obligations are evidence-settled;
- `partial` when the review remains useful but a responsibility is uncertain;
- `blocked` when authority, policy, input integrity, or a hard capability
  prevents a defensible review.

Validate the bundle and run contracts. Then stop without modifying manuscript
files. Revision requires a separate user-authorised task.
