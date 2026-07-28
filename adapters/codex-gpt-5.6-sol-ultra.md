# Codex GPT-5.6 Sol Ultra Adapter

This adapter binds the portable scientific core to one quality-first Codex
configuration. It does not change the scientific criteria.

## Activation contract

Activate this compatibility label only when all of the following are
controlled and recorded:

- surface: `Codex`;
- root requested model: `gpt-5.6-sol`;
- root requested mode: `ultra`;
- every substantive child explicitly requests `gpt-5.6-sol` and `ultra`;
- delegation owner: `root`;
- substantive child topology: `leaf-only`;
- fallback policy: `no silent fallback`, recorded as
  `prohibited_and_checked`;
- zero manuscript mutation.

Custom agent files may pin `model` and `model_reasoning_effort`, and explicit
spawn values may override global child defaults. An installed example alone
does not prove that the host loaded it. Each root and substantive child must
therefore record an adapter-controlled dispatch receipt or host-surfaced
loaded-profile receipt. A static TOML hash or the child's prose assertion is
not configuration proof.

If any required control is unavailable, the adapter is `blocked`. The
portable review can report its scientific result without this compatibility
label, but it cannot silently substitute another model or mode.

## Configuration versus telemetry

Requested configuration, validated configuration, and observed execution are
separate:

1. configuration proof identifies what the host was instructed or shown to
   load;
2. model and mode validation record whether those controls passed;
3. effective telemetry records what the host actually surfaced.

Use `effective_telemetry: not_surfaced` when trustworthy effective model/mode
telemetry is absent; then `resolved_model` and `resolved_mode` remain `null`.
Do not claim runtime attestation from a task label, UI appearance, agent
report, or requested configuration.

Codex `ultra` combines maximum reasoning with proactive delegation. Codex
`max` is not equivalent to Ultra. API `reasoning.effort: max` is also a
different control and must not be translated into this product-mode label.
`gpt-5.6-terra` and any lower mode fail this adapter's substantive-task
contract even if they are useful in other workflows.

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
- allowed `task_effects`;
- expected new evidence and report contract;
- explicit model, mode, and configuration source;
- configuration proof and validation state;
- context/fork policy;
- `leaf-only` and no-delegation instructions;
- stop condition, descendant state, and report artifact.

Any task that can add, verify, remove, adjudicate, rank, or synthesise a
finding, or alter completion, is substantive regardless of its label.

## Context isolation

An assessment represented as independent receives only:

- frozen manuscript artifacts;
- the applicable official profile, if any;
- a bounded assessment delta;
- the output schema;
- privacy and review-only boundaries.

It does not receive prior reviewer reports, author responses, candidate
ledgers, or synthesis conclusions. Do not reuse an independent reviewer as the
adjudicator.

For an independent child, `fork_turns="none"` is an evaluation hypothesis
because it can combine explicit child configuration with conversational
blindness. It is not active merely because it is documented here. A bounded
positive-history fork must prove that it contains no prohibited prior
context. A full-history fork cannot be represented as independent.

Adjudication receives only frozen canonical reports, the coverage matrix, and
the finding contract. It may resolve evidence conflicts and update the ledger;
it may not invent a finding absent from the candidate/evidence record.

## Lifecycle and canonical writes

The root is the sole scheduler and the sole writer of canonical run,
coverage, ledger, and synthesis artifacts. Children are read-only, leaf-only,
and write no canonical state.

The active manifest initially selects no lifecycle candidate. The two
inactive candidates are:

- `adapters/codex/candidates/minimal-settled-set.md`;
- `adapters/codex/candidates/persisted-task-registry.md`.

Neither is an active default. Until comparative evaluation selects one and
binds a canonical promotion record, compatibility is
`evaluation_pending`. Selection must demonstrate recovery from interruption
and compaction, no duplicate dispatch, no late-result omission, complete
evidence retention, and no quality regression.

A run settles only after every dispatched task has a terminal state, every
report artifact is reconciled, descendant state is known, and no late result
can change the canonical ledger. Use current host lifecycle controls; do not
encode a historical close-operation name.

## Permission and stopping rules

The custom-agent examples request `sandbox_mode = "read-only"`. A live parent
permission or sandbox override can take precedence, so record effective
permissions when surfaced. Behavioural nonmutation remains a hard gate even
when the host exposes broader permissions.

Stop with adapter state `blocked` when:

- Sol Ultra cannot be explicitly configured for root or a substantive child;
- configuration proof is missing or self-reported;
- fallback is uncontrolled;
- a substantive child can delegate or its descendants are unknown;
- independent context is contaminated;
- lifecycle selection or promotion evidence is absent for a promoted claim;
- active adapter bytes do not match the manifest digest;
- manuscript mutation occurs.

