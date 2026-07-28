# Public conformance fixtures

These short, project-authored synthetic fixtures test review behaviour without
publishing a real manuscript or review. Inputs and oracles are stored
separately. A candidate executor receives the input and evaluation contract,
not the oracle answer. The deterministic evaluator checks hard gates before
reporting diagnostic metrics; a better score cannot cancel a privacy,
scientific-integrity, topology, or completion failure.

The fixture set covers every canonical criterion, a clean negative control,
source/rendering separation, delta identity, supported dissent, prompt
injection, venue-native and unknown-target paths, and lifecycle recovery.
Passing these contracts is necessary but not sufficient for scientific
quality. This release evaluation does not review a project manuscript, revise
one, or run its experiments.

The deterministic scorer treats exact canonical finding identity as a strict
diagnostic. A frozen free-form reviewer output may use a scientifically
equivalent split, merge, anchor, or semantic key. Such a release result needs
a separate, typed independent semantic adjudication conforming to
`evals/semantic-adjudication.schema.json`; the adjudicator sees the frozen
candidate and oracle only after output freeze. It cannot repair the candidate
or turn an oracle/contract inconsistency into a pass.

Run:

```bash
python -m unittest tests.test_evaluator
python evals/score_run.py
```
