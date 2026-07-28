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
intended review. When authority is absent or the governing policy is unknown
or prohibitive, stop at administrative preflight before reading or freezing
protected bytes, dispatching tasks, or producing scientific outputs.

### `input-freeze`

Resolve ambiguity among candidate artifacts. Freeze identifiers, lineage,
hashes, and the relationship between editable source and rendering. Record a
missing, stale, mismatched, or unreadable artifact distinctly. Do not certify
rendered properties without a unique source/PDF pair and a typed, hash-bound
alignment receipt. That receipt records the comparison performed; it is not a
claim that the offline validator rebuilt the PDF.

### `criteria-freeze`

Record the target as a tuple when known, or explicitly record it as unknown.
Target-specific criteria may add a soft assessment overlay; they may not waive
the canonical scientific coverage. A loaded overlay binds a versioned profile,
source manifest, release-governed official-host registry, and exact
venue/year/track tuple by canonical locator and raw-byte SHA-256. The offline
validator verifies those local records and their internal links; release
governance remains responsible for actual official authority and currency.
`loaded` means that this local snapshot validates; it is not a live authority
or currency attestation. If a requested overlay is unavailable or stale,
record it as blocked and keep
the run partial or blocked; do not substitute another venue.

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
sources. Coverage evidence must declare whether it is an exact source excerpt,
matched rendering, canonical run field, alignment receipt, or predecessor
record, and pass the corresponding verification. Use targeted checks only
where they can change a material
disposition. Record inability to verify rather than filling gaps by
plausibility.

### `adjudication`

Compare candidate findings, evidence, duplicate meaning, conflicts, and
dissent. Retain, merge, reject, or leave each candidate unresolved with a
rationale. Record lower impact on the separate impact axis. Only adjudication
updates the canonical ledger.

### `synthesis`

Translate the canonical scientific assessment into the requested
target-conditioned form when a valid target profile exists. A native field is
valid only with its recorded reviewer role, field type, prompt, requiredness,
labels or range, anchors, and source links. Keep portable decision impact
separate from target-native labels. Do not predict acceptance probability.
The structured venue assessment accounts for every profile rule and native
field; its digest is bound into all three human views.

### `completion`

Require frozen inputs, typed evidence for every complete stage, settled
byte-bound JSON task reports, canonical produced outputs, reconciled findings
and limitations, and no unresolved dissent. Mark the run complete, partial, or
blocked from those evidence obligations, not from elapsed effort or
repetition. Apply the published JSON Schema structure and then the cross-file
semantic validator; neither check is optional. Markdown reports are
human-readable, nonauthoritative views over the machine records. Each carries
one canonical machine-binding block and may not contradict it. Stop without
modifying the manuscript.
