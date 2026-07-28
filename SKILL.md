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
   prohibits the intended use. A denied, absent, or materially unknown gate is
   a preflight-only blocked record: do not inspect or freeze protected
   content, dispatch review tasks, assess scientific criteria, or produce
   scientific review outputs.
2. Record the review goal and `initial` or `delta` kind. Freeze exact source,
   PDF, and supplement artifacts with hashes and lineage. A delta review also
   freezes exactly one prior run, prior ledger, prior source, and author
   response conforming to `schemas/author-response.schema.json`, with
   cross-bindings among them. Source governs
   scientific content; only a PDF bound by a typed alignment receipt governs
   rendered layout. Missing or mismatched evidence yields partial or blocked
   conclusions, never a guessed pass or defect.
3. Ask for target venue, year, and track. A target may remain `unknown`; do not
   substitute a venue. Apply a soft assessment overlay only when its exact
   versioned profile, source manifest, release-governed authority entry, and
   target tuple validate. Offline validation does not independently prove
   live source currency or semantic entailment. Treat the bounded source
   capture and its claim projection as human-release-reviewed evidence;
   refresh the live official page before material target-conditioned use.
   Operational prompts and simulation-required fields are local mappings, not
   claims about official requiredness. Do not infer acceptance probability.
   If a comparison corpus is requested, keep venue-background and topic-near
   corpora separate and follow `references/venue-conditioning.md`. Use only
   evidence-graded metadata, not paper counts or similarity alone, for
   contextual calibration.
4. Create the run manifest from `templates/run-manifest.json`, bind it to
   `references/review-coverage.json`, and keep `review_only: true`.

## Route

Read only what the run needs:

- always: `references/scientific-core.md`,
  `references/review-coverage.md`, `references/review-workflow.md`,
  `references/finding-contract.md`, and
  `references/privacy-and-authorisation.md`;
- delta review: `references/delta-review.md` and the frozen prior initial run,
  ledger, source, and typed author-response record;
- Codex Sol Ultra execution: `adapters/codex-gpt-5.6-sol-ultra.md` and
  `adapters/codex/adapter-manifest.json`;
- machine records: `schemas/run-manifest.schema.json`,
  `schemas/finding-ledger.schema.json`, `schemas/task-report.schema.json`, and
  `schemas/runtime-evidence-receipt.schema.json`, plus
  `schemas/source-pdf-alignment-receipt.schema.json`,
  `schemas/rendered-evidence-receipt.schema.json`, and
  `schemas/author-response.schema.json`;
- target overlay: `schemas/venue-profile.schema.json`,
  `schemas/venue-source-manifest.schema.json`,
  `schemas/venue-source-evidence.schema.json`,
  `schemas/venue-authority-registry.schema.json`, and
  `references/venue-authorities.json`;
- optional comparison corpus: `references/venue-conditioning.md`,
  `schemas/venue-corpus-manifest.schema.json`, and
  `venue-intelligence/README.md`;
- lifecycle promotion: `schemas/adapter-promotion.schema.json`,
  `schemas/adapter-evaluation-fixture-manifest.schema.json`,
  `schemas/adapter-evaluation-input.schema.json`,
  `schemas/adapter-evaluation-oracle.schema.json`,
  `schemas/adapter-evaluation-output.schema.json`, and
  `schemas/adapter-evaluation-report.schema.json`,
  `schemas/adapter-evaluation-execution-receipt.schema.json`, and
  `schemas/adapter-semantic-review-receipt.schema.json`;
- human views: `templates/reviewer-report.md`,
  `templates/ae-assessment.md`, and `templates/review-summary.md`.

Treat `adapters/codex/adapter-manifest.json` as the sole lifecycle authority.
A candidate is active only when that manifest binds a passing promotion
record and the exact candidate bytes. A null selection requires
`evaluation_pending`; never turn requested configuration into runtime
attestation.

## Execute

1. Build the criterion-by-criterion coverage and risk map.
2. Assess frozen inputs without prior-report contamination when independence
   is claimed.
3. Verify coverage and material candidates against exact frozen bytes,
   typed run records, alignment receipts, or predecessor records. A locator or
   prose assertion alone is not verification.
4. Adjudicate evidence, semantic duplicates, conflicts, and dissent into one
   canonical finding ledger.
5. Apply a valid target profile only after the portable scientific assessment.
   Record every sourced venue rule and every native field in the structured
   `venue_assessment`; keep native labels separate from portable decision
   impact.
6. Reconcile every criterion, finding, report, limitation, and late result.
   For a complete delta, also prove a visible prior/current source-and-PDF
   revision, exact predecessor-transition coverage, and current typed
   successor evidence under the chronology in `references/delta-review.md`.
7. After every dispatch has a terminal record, generate the exact task-ID-
   ordered inventory with `scripts/build_terminal_inventory.py`, supplying the
   actual observation time after all bound reports and control receipts. Bind
   its raw-byte hash in the run manifest. Generate each complete deterministic
   Markdown view with `scripts/render_human_binding.py`, then bind its raw-byte
   hash without manual narrative edits.

Delegation is optional and quality-driven. It follows uncovered evidence risk,
not a roster or task quota. Only the root updates canonical artifacts. Every
completed delegated task returns a canonical JSON report conforming to
`schemas/task-report.schema.json`; Markdown reports are human views, not task
receipts.

## Outputs and stopping

Each canonical criterion receives exactly one recorded disposition, including
justified `inapplicable` and explicit `uncertain` states. Every material
finding needs artifact and semantic anchors, verification state, decision
impact, action type, closure gate, dissent, provenance, and a byte-checkable
anchor verification. Each Markdown output contains one canonical
machine-binding block derived from the run and ledger; its surrounding prose
is nonauthoritative and cannot add, omit, or contradict findings, coverage,
limitations, completion, or venue results.

Use:

- `complete` only when all applicable obligations are evidence-settled;
- `partial` when the review remains useful but a responsibility is uncertain;
- `blocked` when authority, policy, input integrity, or a hard capability
  prevents a defensible review.

Validate the bundle and run contracts. Treat review-only as a required
behavioural boundary: the offline checks bind frozen bytes and declared
outputs. They prove only supported schema, safe locators, hash equality,
cross-record consistency, and deterministic oracle agreement. They do not
prove scientific truth, official-source currency, build equivalence,
historical nonmutation, host identity, permissions, sandbox enforcement, or
live execution. Record any unavailable proof as a limitation. Then stop
without modifying manuscript files. Revision requires a separate
user-authorised task.
