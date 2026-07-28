# Review Workflow

The workflow is an evidence-dependency graph. A stage may cover several
criteria, and a criterion may receive independent checks when that materially
improves evidence quality. Staffing is not part of the scientific contract.

## Stage graph

`scope-and-authorisation` → `input-freeze` → `criteria-freeze` →
`coverage-map` → `scientific-assessment` → `evidence-verification` →
`adjudication` → `synthesis` → `completion`

### `scope-and-authorisation`

Record the review goal and kind, authority to inspect the material,
confidentiality class, permitted processing, retention boundary, and
review-only constraint. Stop when authority or governing policy prohibits the
intended review.

### `input-freeze`

Resolve ambiguity among candidate artifacts. Freeze identifiers, lineage,
hashes, and the relationship between editable source and rendering. Record a
missing, stale, mismatched, or unreadable artifact distinctly. Do not certify
rendered properties without a matching rendering.

### `criteria-freeze`

Record the target as a tuple when known, or explicitly record it as unknown.
Freeze current first-party criteria before target-conditioned synthesis.
Target-specific criteria may add a soft assessment overlay; they may not waive
the canonical scientific coverage.

### `coverage-map`

Load `references/review-coverage.json`, assess the applicability of every
criterion, assign its canonical primary stage, and identify material
verification risks. Record inapplicable and uncertain rows rather than
dropping them.

### `scientific-assessment`

Perform an initial assessment against frozen inputs and the full applicable
coverage map. An assessment represented as independent must not receive prior
reports, author responses, or later synthesis. Candidate findings are
evidence-seeking hypotheses, not obligations.

### `evidence-verification`

Falsify or support candidate findings against exact artifacts and authorised
sources. Use targeted checks only where they can change a material
disposition. Record inability to verify rather than filling gaps by
plausibility.

### `adjudication`

Compare candidate findings, evidence, duplicate meaning, conflicts, and
dissent. Retain, merge, downgrade, reject, or leave unresolved with a
rationale. Only adjudication updates the canonical ledger.

### `synthesis`

Translate the canonical scientific assessment into the requested
target-conditioned form when a valid target profile exists. Keep portable
decision impact separate from target-native labels. Do not predict acceptance
probability.

### `completion`

Reconcile every criterion, task report, finding, dissent record, output
artifact, limitation, and late result. Mark the run complete, partial, or
blocked from evidence obligations, not from elapsed effort or repetition.
Stop without modifying the manuscript.

