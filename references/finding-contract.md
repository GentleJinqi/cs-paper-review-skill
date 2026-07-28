# Finding Contract

The JSON authority is `schemas/finding-ledger.schema.json`. Human reports are
views over that ledger, not independent issue stores.

## Required meaning

Each finding records:

- a stable identifier and review kind;
- primary and related scientific criteria;
- a precise claim about the paper;
- a frozen artifact, human-readable source anchor, stable semantic anchor, and
  observed evidence;
- exact-text or rendered-receipt anchor verification, including the excerpt
  digest when text is claimed;
- portable decision impact and confidence;
- adjudication, delta, impact-change, and evidence states as separate axes;
- why the issue matters and the kind of action that could close it;
- a structured closure owner and gate;
- dissent and provenance, including complete merge lineage.

Decision impact means:

- `fundamental`: the stated contribution or conclusion is not presently
  defensible;
- `material`: a substantial assessment concern that can affect the overall
  conclusion;
- `limited`: real but bounded to a claim, analysis, component, or presentation
  area;
- `advisory`: useful improvement without a current material obligation;
- `none`: rejected, merged-away, or otherwise non-obligating record.

## Promotion and adjudication

A candidate becomes an obligation only after evidence-based adjudication.
Adjudication may retain, merge, reject, or leave it unresolved. Every result
needs a rationale. A merged record points to one canonical target and preserves
all unique source IDs. Lower impact is expressed through `decision_impact` and,
for a delta finding, `impact_change: downgraded`; it is not an adjudication
state. A rejected record remains auditable but cannot satisfy coverage or
appear as a surviving obligation.

`schemas/finding-ledger.schema.json` is the normative structural contract.
Complete validity additionally requires the cross-file semantics in
`scripts/validate_run.py`, including artifact-lineage, criterion-coverage,
merge-target, task-report, and completion consistency. Passing the schema
alone is not a complete review claim.

Adjudication, delta status, impact change, evidence state, and closure are
independent axes with explicit consistency gates. In particular, rejecting or
merging a carried record does not force `delta_status: resolved`, and a delta
status alone never proves that a repair is closed.

Do not:

- emit a generic concern without a semantic anchor;
- treat duplicate wording or reviewer count as stronger consensus;
- invent a target requirement;
- prescribe a completed fix for author judgement, unavailable data, or a new
  experiment;
- silently delete a supported issue during synthesis;
- call structurally present evidence semantically verified.

## Stable identity

For a new finding, hash the canonical scientific criterion, normalised claim,
primary artifact-lineage ID, and semantic anchor. Reviewer identity, mutable
line numbers, confidence, impact wording, and status do not affect identity.
A carried delta finding keeps its prior identifier rather than recomputing it
from the revised location. Its criterion, normalised claim, semantic anchor,
and primary artifact lineage remain the same scientific identity; changing
one creates a new finding.

Rendered evidence binds the subject, exact PDF bytes, page, normalised region,
observation digest, and the reproducible 72-DPI `pdftoppm` PNG digest. A
convenient screenshot or unrelated image is not rendered verification. The
receipt time must also fall inside the run that owns the evidence.

## Human views

`templates/reviewer-report.md` may contain candidates. The root-owned,
validated finding ledger is the only adjudication authority; the AE assessment
is a human view over that decision, not a second issue store.
`templates/review-summary.md` reports surviving findings and limitations from
the canonical ledger. Every view contains one canonical JSON machine-binding
block derived from the run and ledger. Narrative prose is nonauthoritative: it
may not introduce an untracked material finding, silently reject a surviving
finding, invent a blocker, or contradict completion, coverage, limitations, or
venue results.
