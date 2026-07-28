# Delta Review

A delta review tests a revised artifact against a frozen earlier assessment.
It is not a fresh review with similar prose.

## Freeze

Freeze:

- the prior run and finding-ledger bytes;
- the earlier and revised artifact lineage;
- the author response or change record when supplied;
- the review goal and any change in external criteria.

Keep the original assessment snapshot immutable. New evidence may change the
current conclusion without rewriting what the earlier review concluded.

## Trace prior findings

Account for every prior surviving finding by the same identifier. Trace it to
the response, revised semantic anchor, and verification evidence. Record:

- `resolved`;
- `partially_resolved`;
- `still_open`;
- `made_worse`.

For a carried finding, record impact as `unchanged`, `upgraded`, or
`downgraded`. Adjudication remains a separate axis: a historically rejected
record stays rejected, and an unresolved verification need does not become a
delta state.

## Check introduced risk

Inspect revised regions, affected dependencies, claims, results, figures,
tables, references, and packaging for regressions or newly exposed issues. A
new issue receives a new stable identifier, `prior_finding_id: null`,
`delta_status: new`, and `impact_change: not_applicable`.

## Completion

A delta review cannot be complete until:

- every prior finding is accounted for;
- every carried identifier is preserved;
- introduced risks receive their own check;
- all merges retain source and target lineage;
- unresolved evidence and blocked verification are reported;
- the current conclusion is derived from the current ledger without erasing
  the earlier snapshot.

