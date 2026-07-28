# Delta Review

A delta review tests a revised artifact against a frozen earlier assessment.
It is not a fresh review with similar prose.

## Freeze

Freeze:

- exactly one validated `initial` prior run and its byte-bound finding-ledger
  output;
- exactly one prior source and the revised source as distinct frozen bytes;
- exactly one canonical record conforming to
  `schemas/author-response.schema.json`, bound to the prior run.

Keep the original assessment snapshot immutable. New evidence may change the
current conclusion without rewriting what the earlier review concluded.
The prior run ID, prior ledger run ID, prior source record, ledger output
locator/hash, and response predecessor ID must reconcile. A prior ledger alone
is insufficient. The review goal, target, venue profile, and coverage
authority must remain unchanged; otherwise start a new initial review. The
chronology is strict:

```text
prior finalized_at < response recorded_at <= current created_at < current finalized_at
```

A complete delta additionally needs matched prior and current renderings. Each
source/PDF alignment receipt must contain one distinct `revision_marker`
visible in both source and PDF, plus a distinct rendered-evidence receipt for
the page containing that marker. Reusing the current image or evidence as the
prior proof is invalid.

## Trace prior findings

Account for every prior surviving finding by the same identifier. The typed
author-response transitions must cover that set exactly and bind each
predecessor's criterion plus the SHA-256 of its original UTF-8 claim. Trace a
carried item to the response, the same stable semantic anchor at its current
source or rendered location, and current verification evidence. Record:

- `resolved`;
- `partially_resolved`;
- `still_open`;
- `made_worse`.

For a carried finding, record impact as `unchanged`, `upgraded`, or
`downgraded`. Adjudication, delta status, impact change, evidence state, and
closure remain separate axes. A current carried finding may be rejected or
merged without being forced to `resolved`; prior rejected or merged records
remain only in the immutable predecessor history.

`addressed` and `partially_addressed` transitions require typed, current,
verified `successor_evidence`. It cannot reuse predecessor evidence. When a
surviving finding is `resolved`, its closure evidence must match that successor
evidence field for field.

## Check introduced risk

Inspect revised regions, affected dependencies, claims, results, figures,
tables, references, and packaging for regressions or newly exposed issues. A
new issue receives a new stable identifier, `prior_finding_id: null`,
`delta_status: new`, and `impact_change: not_applicable`.

## Completion

A delta review cannot be complete until:

- every prior finding is accounted for;
- every carried identifier is preserved;
- carried scientific identity (criterion, normalised claim, semantic anchor,
  and primary artifact lineage) is preserved;
- every author-response transition binds the exact predecessor criterion and
  claim digest, and every claimed repair is supported by current typed
  evidence;
- prior/current visible revision markers and their distinct renderings verify
  that the reviewed source/PDF pairs actually differ;
- introduced risks receive their own check;
- all merges retain source and target lineage;
- unresolved evidence and blocked verification are reported;
- the current conclusion is derived from the current ledger without erasing
  the earlier snapshot.
