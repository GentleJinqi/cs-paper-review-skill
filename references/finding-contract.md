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
Adjudication may retain, merge, downgrade, reject, or leave it unresolved.
Every result needs a rationale. A merged record points to one canonical target
and preserves all unique source IDs. A downgraded record states which evidence
reduced its impact. A rejected record remains auditable but cannot satisfy
coverage or appear as a surviving obligation.

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
from the revised location.

## Human views

`templates/reviewer-report.md` may contain candidates. Only
`templates/ae-assessment.md` adjudicates them.
`templates/review-summary.md` reports surviving findings and limitations from
the canonical ledger. No human view may introduce an untracked material
finding.

