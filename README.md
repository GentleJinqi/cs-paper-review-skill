# CS Paper Review

[中文说明](README.zh-CN.md)

`cs-paper-review` is an author-side, review-only workflow for
evidence-bounded assessment of CS, ML, CV, NLP, and related manuscripts. It
freezes the reviewed version, accounts for scientific responsibilities,
verifies material findings, and records uncertainty. It does not edit the
paper, run experiments, or manufacture missing evidence.

## Architecture

The release has three deliberately separate layers:

1. The portable scientific core defines review responsibilities,
   criterion-by-criterion coverage, evidence rules, adjudication, and truthful
   completion. Start with
   [scientific-core](references/scientific-core.md),
   [review-coverage](references/review-coverage.md), and
   [review-workflow](references/review-workflow.md).
2. An optional venue overlay may add venue-, year-, and track-specific
   criteria or native assessment fields. It activates only after a versioned
   profile, source manifest, and release-governed authority record resolve
   and their local bytes verify. This offline check proves the recorded
   tuple, host allowlist, and byte integrity; source authority and currency
   remain release/update governance obligations rather than live network
   attestations. An unspecified target remains `unknown`; no venue is
   substituted and no acceptance probability is predicted.
3. The optional
   [Codex GPT-5.6 Sol Ultra adapter](adapters/codex-gpt-5.6-sol-ultra.md)
   controls one execution environment. It cannot weaken or replace the
   scientific core.

An optional corpus-intelligence input sits behind the first two layers. It
keeps venue-background and topic-near sets separate, verifies decision-status
authority, and compares topic proximity across six scientific axes. Corpus
size and resemblance never determine acceptance or waive a core criterion.
See [venue conditioning](references/venue-conditioning.md).

## Use

Invoke `$cs-paper-review` and provide the manuscript source, matching PDF when
available, supplements, and the authority or confidentiality constraints that
govern processing. A delta review additionally requires the frozen prior
initial run, its finding ledger, the prior source, and a canonical typed
author-response record; the ledger alone is insufficient. A `complete` delta
also requires matched prior/current PDFs and distinct visible revision
evidence in both source and rendering.

Venue-neutral example:

```text
Use $cs-paper-review for an author-side pre-submission review. The target
venue is unknown. Freeze main.tex and its matching PDF, then report an
evidence-grounded finding ledger without changing the manuscript.
```

Target-conditioned example:

```text
Use $cs-paper-review for an ICML 2026 main-track review. Apply the venue
overlay only if the exact release-governed profile validates; otherwise keep
the scientific assessment venue-neutral and disclose the limitation.
```

Delta example:

```text
Use $cs-paper-review for a delta review against the frozen prior ledger.
Preserve stable finding identities and distinguish resolution from impact
change.
```

The target repository's instructions and the user's chosen output location
remain authoritative. This skill does not impose a global run directory.

## Execution footprint

Repository source discovery, upstream refresh, lifecycle-candidate comparison,
the unit suite, and release/rights review are maintenance-time work. They are
not rerun for each paper.

A paper review starts with one root and the portable criterion map. Delegation
is optional and only follows a distinct material evidence need; a root-only run
is valid when it can settle the coverage. The target overlay is loaded only
when the user names a target. `validate_run.py` is a local deterministic check,
not another model-review graph. Nothing in the runtime defines rigor by agent
count, repeated rounds, or token consumption.

## Evidence workflow

The workflow proceeds through scope and authorisation, input freeze, criteria
freeze, coverage mapping, scientific assessment, targeted verification,
adjudication, synthesis, and completion.

Editable source governs scientific content. Only a matching rendered artifact
can support layout or readability conclusions. Missing, stale, mismatched, or
unreadable inputs produce explicit uncertainty rather than guessed passes or
defects. A `matched` state is supported by a typed receipt that binds one
source and one distinct PDF plus explicit comparison checks; offline
validation does not rebuild the PDF or independently establish provenance.

Delegation is optional and follows uncovered evidence risk. The root remains
the sole owner of canonical run, coverage, finding, and synthesis artifacts.
Concurrency is a capacity constraint, not evidence of rigor.

## Canonical contracts

- [run manifest](templates/run-manifest.json): input lineage, authority,
  target/profile state, execution provenance, coverage, and completion;
- [finding ledger](templates/finding-ledger.json): stable findings,
  verification, delta axes, closure gates, dissent, and provenance;
- [task report schema](schemas/task-report.schema.json): the canonical,
  byte-bound JSON result of each completed delegated task;
- [reviewer report](templates/reviewer-report.md): evidence-bounded assessment;
- [adjudication assessment](templates/ae-assessment.md): disposition,
  conflicts, merges, and dissent;
- [review summary](templates/review-summary.md): portable conclusions,
  optional target overlay, limitations, and non-claims.

The JSON run manifest, ledger, and task reports are machine authorities.
Markdown reports are human-readable views and must agree with those records;
they cannot introduce or omit decision-relevant findings. Each view includes
one canonical JSON machine-binding block for completion, coverage, findings,
limitations, and structured venue results; the surrounding narrative is
nonauthoritative.

The shipped run template is deliberately fail-closed: it records unknown
authority/classification, no protected inputs, no tasks, no outputs, and a
blocked administrative preflight. Establish authority first; do not merely
flip the gate while leaving `replace-with-*` template sentinels.

`complete` requires all frozen inputs to validate, every applicable scientific
obligation to be settled, every dispatched task to be completed with a valid
byte-bound JSON report and no descendants, typed resolvable evidence for every
complete stage, all canonical outputs to be produced and bound, reconciled
limitations, no unresolved dissent, and run/ledger/human-view consistency.
`partial` preserves useful conclusions while naming unresolved
responsibilities. `blocked` records a hard authority, policy, input-integrity,
or capability barrier. A known target with no valid venue profile cannot be
reported as a complete target-conditioned review.

Venue-native fields are used only when the validated profile defines their
role, type, prompt, requiredness, labels or numeric range, anchors, and source
links. The run's structured venue assessment must account for every venue rule
and native field, validate each recorded value against its type/range/labels,
and bind its digest into all human views. Portable decision impact remains
separate and authoritative when no native field exists. A locally `loaded`
profile is a validated snapshot, not proof that an official page remains
current.

Each published source record binds a bounded manual capture of visible
first-party text, exact UTF-8 byte spans, and a human release review of the
bounded interpretation. The offline validator proves capture/excerpt,
claim/profile, manifest, and release-registry consistency. It does not fetch
the live page or machine-prove that a paraphrase is semantically entailed.
Profile prompts and simulation-required fields are local operational mappings,
not claims about official form requiredness. Refresh and human-audit the
official sources before relying on a target-conditioned live review.

Machine-contract entry points include the
[run schema](schemas/run-manifest.schema.json),
[ledger schema](schemas/finding-ledger.schema.json),
[task-report schema](schemas/task-report.schema.json),
[runtime-receipt schema](schemas/runtime-evidence-receipt.schema.json),
[source/PDF alignment schema](schemas/source-pdf-alignment-receipt.schema.json),
[rendered-evidence schema](schemas/rendered-evidence-receipt.schema.json),
[author-response schema](schemas/author-response.schema.json),
[venue profile](schemas/venue-profile.schema.json),
[venue source manifest](schemas/venue-source-manifest.schema.json),
[venue source evidence](schemas/venue-source-evidence.schema.json),
[venue source capture](schemas/venue-source-capture.schema.json),
[venue authority registry schema](schemas/venue-authority-registry.schema.json),
[venue corpus manifest](schemas/venue-corpus-manifest.schema.json),
[adapter manifest](adapters/codex/adapter-manifest.json), and
[promotion record schema](schemas/adapter-promotion.schema.json). Promotion
fixtures use the adjacent typed evaluation schemas, including separate
[candidate-execution](schemas/adapter-evaluation-execution-receipt.schema.json)
and
[independent semantic-review](schemas/adapter-semantic-review-receipt.schema.json)
receipts.

## Sol Ultra compatibility

The adapter requests `gpt-5.6-sol` with Codex `ultra` for the root and every
completed adapter task, including all substantive tasks. The root decides
whether independent or specialist work can materially improve evidence;
completed adapter-task records must request read-only, leaf-only,
context-isolated execution. Those are adapter-required, byte-cross-recorded
dispatch controls; the
offline validator does not independently observe effective permissions,
actual fork history, or host topology.
Incomplete or portable tasks use their separate non-adapter representation.
There is no execution roster or count-based review tier.

Requested configuration, byte-verified configuration receipts, validation
results, and effective runtime telemetry are distinct facts. A task name,
static agent file, or self-report is not configuration proof. The current
offline validator reserves but does not grant `runtime-attested`.
`configured-and-evaluated` is the highest state available without trusted
effective telemetry. Release `0.2.0` selects
`persisted-task-registry` through the exact
[adapter manifest](adapters/codex/adapter-manifest.json) and passing
[promotion record](compatibility/adapter-promotion.json). Both candidates
produced distinct configured Sol Ultra execution receipts over the same
oracle-blind fixtures; an independent configured Sol Ultra semantic comparison
selected persistence by a two-to-one strict-preference majority, with genuine
ties retained. This supports `configured-and-evaluated`, not
`runtime-attested`.

## Evaluation evidence

The frozen public conformance run initially passed 15 of 16 fixtures in an
independent semantic adjudication. The sole failure exposed a harness input
defect: the venue-native dispatch had not supplied the exact TMLR profile, so a
complete target-conditioned output was not justified. The original output and
failure remain published. After adding that exact public profile, only the
invalidated venue fixture was rerun behind the same oracle boundary. The final
adjudication passed 16 of 16 fixtures, matched all 10 required scientific
obligations, and retained no prohibited finding.

The complete public result, hashes, correction history, and limitations are
recorded in the
[evaluation aggregate](evals/results/public-conformance-v1/aggregate-result.json).
These bounded synthetic results do not establish universal review accuracy.
Project-manuscript review, revision, and experiment execution are outside this
release task and are not part of its evidence.

## Offline validation

Validate the installed bundle:

```bash
python scripts/validate_bundle.py .
```

Validate a completed run with separate bundle and run-evidence roots:

```bash
python scripts/validate_run.py \
  --bundle-root . \
  --evidence-root /absolute/path/to/review-run \
  /absolute/path/to/review-run/run-manifest.json \
  /absolute/path/to/review-run/finding-ledger.json
```

After every dispatch has a terminal record, generate the exact inventory from
the run manifest. `--recorded-at` must be the real observation time after every
bound task report and control receipt:

```bash
python scripts/build_terminal_inventory.py \
  --bundle-root . \
  --recorded-at 2026-07-28T14:30:00Z \
  /absolute/path/to/review-run/run-manifest.json \
  > /absolute/path/to/review-run/delegation-terminal-inventory.json
```

Record that file's raw-byte SHA-256 in the run manifest. Generate each complete
deterministic human view rather than hand-editing its narrative:

```bash
python scripts/render_human_binding.py \
  --bundle-root . \
  --role review_summary \
  /absolute/path/to/review-run/run-manifest.json \
  /absolute/path/to/review-run/finding-ledger.json \
  > /absolute/path/to/review-run/review-summary.md
```

Update that output's raw-byte SHA-256 and run the full validator above. Any
manual change to a generated human view is rejected.

The CLI applies the published JSON Schema structure first and then the
cross-file semantic checks. It runs offline, rejects traversal, symlinked or
hard-linked evidence, and recomputes referenced byte digests.

Deterministic policy guards reject venue-outcome forecasts in either direction
while preserving validated venue-native recommendation fields. They also
reject using reviewer/task count as a cause of scientific confidence.
Active Markdown and structured scalars are scanned independently after Unicode
normalisation and local polarity analysis; sibling fields are never joined,
and an active file that cannot be structurally parsed fails closed. These are
bounded guardrails, not a general semantic proof.

The promotion validator derives case results by comparing typed, hash-bound
outputs with typed oracles and cross-checks the execution and semantic-review
receipts. The release authority also pins the exact deterministic scorer
implementation. That proves supported schema, safe locators, hash equality,
cross-record consistency, scorer identity, and deterministic agreement. It
does not authenticate the model executor, semantic reviewer, host, live
invocation, scientific truth, official-source currency, build equivalence,
historical nonmutation, effective permissions, or sandbox enforcement.

## Boundaries and provenance

The review workflow is constrained to review-only behaviour: it must not
mutate manuscript files, transmit confidential material without recorded
authority, invent results or citations, or turn missing evidence into a
scientific conclusion. The offline validator checks frozen bytes, role
separation, receipts, and declared outputs; it cannot prove that no mutation
happened before those bytes were frozen or that a host enforced an effective
sandbox. Record such unavailable host evidence as a limitation.
Official-review use must also satisfy the governing venue policy.

The machine-readable venue boundary is defined by the
[profile schema](schemas/venue-profile.schema.json),
[source-manifest schema](schemas/venue-source-manifest.schema.json), and
[authority registry](references/venue-authorities.json).

The initial repository snapshot is preserved in
[legacy history](docs/legacy-2026-06-23.md). Current external-source pins,
licence routes, and mechanism-level adoption decisions are recorded under
[sources](sources/adoption-matrix.md); upstream style alone is not an adopted
mechanism.

Release history and reuse boundaries are recorded in
[CHANGELOG](CHANGELOG.md), [migration guidance](MIGRATION.md),
[source provenance](SOURCES.md), and
[third-party notices](THIRD_PARTY_NOTICES.md).
