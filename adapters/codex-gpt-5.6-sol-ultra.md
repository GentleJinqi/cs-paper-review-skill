# Codex GPT-5.6 Sol Ultra Adapter

This adapter binds the portable scientific core to one quality-first Codex
configuration. It does not change the scientific criteria.

## Activation contract

Activate this compatibility label only when all of the following are
controlled and recorded:

- surface: `Codex`;
- root requested model: `gpt-5.6-sol`;
- root requested mode: `ultra`;
- every completed adapter task, including every substantive task, explicitly
  requests `gpt-5.6-sol` and `ultra`;
- delegation owner: `root`;
- completed adapter-task topology: `leaf-only`;
- fallback policy: `no silent fallback`, recorded as
  `prohibited_and_checked`;
- review-only behaviour with zero manuscript mutation.

Custom agent files may pin `model` and `model_reasoning_effort`, and explicit
spawn values may override global child defaults. An installed example alone
does not prove that the host loaded it. The root and every completed adapter
task must therefore record an adapter-controlled dispatch receipt or
host-surfaced loaded-profile receipt. A static TOML hash or the task's prose
assertion is not configuration proof. Each receipt is a canonical JSON
regular file under the run's explicit evidence root. The run stores its
locator and raw-byte
SHA-256; validation reloads the file, rejects traversal, symlinks and
hardlinks, and binds the subject, requested controls, surface/build, adapter
digest, configuration source, and fallback policy. Model, mode and
configured-sandbox validation receipts separately bind that exact
configuration receipt. These are configuration controls, not proof of the
host's effective runtime permissions. A receipt labelled
`host_loaded_profile_receipt` records the supplied configuration evidence; the
offline validator does not authenticate that it was surfaced by the host.
Likewise, `fork_policy` and `leaf_only` are declared and cross-recorded
controls, not independently observed host topology.

If any required control is unavailable, the compatibility state is
`blocked`. The portable review can still report its separately determined
scientific result without this label, but it cannot silently substitute
another model or mode.

## Configuration versus telemetry

Requested configuration, validated configuration, and observed execution are
separate:

1. configuration proof identifies what the host was instructed or shown to
   load;
2. model and mode validation record whether those controls passed;
3. effective telemetry records what the host actually surfaced.

Use `effective_telemetry: not_surfaced` when trustworthy effective model/mode
telemetry is absent; then `resolved_model` and `resolved_mode` remain `null`.
The current offline validator has no trusted host telemetry verifier, so
`runtime-attested` is a reserved state that it always rejects. Do not derive
runtime attestation from a task label, UI appearance, agent report, matching
strings, or requested configuration.

Codex `ultra` combines maximum reasoning with proactive delegation. Codex
`max` is not equivalent to Ultra. API `reasoning.effort: max` is also a
different control and must not be translated into this product-mode label.
`gpt-5.6-terra` and any lower mode fail this adapter's completed-task contract
even if they are useful in other workflows.

## Quality-driven delegation

The root first maps every canonical criterion to evidence, uncertainty, and
material risk. It delegates only when at least one condition is true:

- an independent assessment can materially reduce correlated error;
- a distinct evidence or tool specialty is not otherwise covered;
- a material conflict needs isolated verification;
- source or rendering scale exceeds reliable single-context coverage;
- delta or target-profile evidence needs a bounded independent check.

The amount of delegation follows uncovered risk and expected evidence value.
Concurrency is a capacity limit, not a quality target. The run records
`task_count_as_runtime_observation` only after dispatch; that number is not a
rigor level.

Every dispatch records:

- a canonical task ID and the triggering coverage risk;
- bounded frozen inputs;
- an exact mixed-input snapshot covering run artifacts, dependency reports,
  and bundle contract files, with one derived digest;
- allowed `task_effects`;
- expected new evidence and report contract;
- explicit model, mode, and configuration source;
- configuration proof and validation state;
- context/fork policy;
- `leaf-only` and no-delegation instructions;
- stop condition, descendant state, and report artifact.

Any task that can add, verify, remove, adjudicate, rank, or synthesise a
finding, or alter completion, is substantive regardless of its label.
Its terminal machine result is canonical JSON conforming to
`schemas/task-report.schema.json`, with the exact run/task/agent identity,
effects, input-snapshot digest, criterion assessments, semantic finding
contributions, bounded evidence, summary, and limitations. A separate
byte-bound terminal inventory accounts for every dispatched task and its
terminal reason. Reviewer and AE Markdown documents are human views; they do
not replace those receipts.

## Context isolation

An assessment represented as independent receives only:

- frozen manuscript artifacts;
- the validated exact-target profile, if any;
- a bounded assessment delta;
- the output schema;
- privacy and review-only boundaries.

It does not receive prior reviewer reports, author responses, candidate
ledgers, or synthesis conclusions. Do not reuse an independent reviewer as the
adjudicator.

Every completed Codex adapter task record must request and cross-bind
`fork_turns="none"`. This is an adapter-required dispatch control, not a
task-count rule. The offline validator does not independently observe the
host's effective fork history. The root supplies only the bounded frozen
inputs required by the task; if isolation cannot be established to the level
needed by the claimed assessment, record the limitation or block the
independence claim.

Adjudication receives only frozen canonical reports, the coverage matrix, and
the finding contract. It may resolve evidence conflicts and update the ledger;
it may not invent a finding absent from the candidate/evidence record.

## Lifecycle and canonical writes

The root is the sole scheduler and the sole writer of canonical run,
coverage, ledger, and synthesis artifacts. The adapter requests read-only,
leaf-only children, rejects completed records with descendants, and requires
behavioural nonmutation. Configuration receipts establish those requested
controls; without trusted host telemetry they do not prove effective
permissions or historical topology.

The active manifest initially selects no lifecycle candidate. The two
inactive candidates are:

- `adapters/codex/candidates/minimal-settled-set.md`;
- `adapters/codex/candidates/persisted-task-registry.md`.

Neither is an active default. Until comparative evaluation selects one and
binds a canonical promotion record, compatibility is
`evaluation_pending`. Selection must demonstrate recovery from interruption
and compaction, no duplicate dispatch, no late-result omission, complete
evidence retention, and no quality regression. Promotion validation
deterministically compares typed, hash-bound candidate outputs with typed
oracles. Both candidates require distinct completed Sol Ultra execution
receipts over the same fixtures, and a third, independent Sol Ultra semantic
review compares compaction recovery, late-result handling, duplicate
dispatch, evidence retention, complexity, and review quality before selection.
The receipts prove internal byte integrity, recorded control consistency, and
oracle agreement; they do not authenticate the named people/agents, host, or
live execution. Trusted host telemetry remains a separate boundary.

A run settles only after every dispatched task has a terminal state, every
canonical JSON task report is resolved and byte-bound, descendant state is
known, and no late result can change the canonical ledger. A `complete` run
also requires frozen inputs, typed evidence for every complete stage,
canonical outputs, reconciled limitations, and every dispatched task to be
complete; failed, running, pending, missing, or tampered reports force a
non-complete state. Use current host lifecycle controls; do not encode a
historical close-operation name.

## Permission and stopping rules

The custom-agent examples request `sandbox_mode = "read-only"`, and the
offline contract verifies the byte-bound configured-sandbox request and its
control receipt. A live parent permission or sandbox override can take
precedence. The current run schema does not carry trusted
effective-permission telemetry, and frozen-byte/output checks cannot prove
historical nonmutation. When either fact is unavailable, record it as a
limitation. Behavioural nonmutation remains a hard gate even when the host
exposes broader permissions.

Stop with adapter state `blocked` when:

- Sol Ultra cannot be explicitly configured for root or a completed adapter
  task;
- configuration proof is missing or self-reported;
- fallback is uncontrolled;
- a completed adapter task can delegate or its descendants are unknown;
- independent context is contaminated;
- lifecycle selection or promotion evidence is absent for a promoted claim;
- active adapter bytes do not match the manifest digest;
- manuscript mutation occurs.
