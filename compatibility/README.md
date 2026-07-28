# Adapter compatibility evidence

Release `0.2.0` evaluates both lifecycle contracts on the same two
oracle-blind fixtures, freezes each candidate output before scoring, and uses
an independent semantic comparison across the six declared dimensions.

The promotion record selects `persisted-task-registry` by a two-to-one
strict-preference majority:

- persisted registry: preferred for compaction recovery and evidence
  retention;
- minimal settled set: preferred for lower complexity;
- late-result handling, duplicate-dispatch behaviour, and scientific review
  quality: genuine ties.

Both candidates passed the bounded quality and lifecycle assertions. The
persisted execution additionally created an atomic disk registry, reloaded its
pre-interruption state, reconciled the late report, and retained a single
dispatch. The execution receipt records the final raw registry digest and the
remaining limitations.

The candidate Markdown files are immutable evaluated contract bytes; their
pre-promotion status lines are retained so the execution hashes remain
truthful. Activation is represented only by
`adapters/codex/adapter-manifest.json` and its bound passing promotion record.
Requested Sol Ultra configuration is recorded, but host-effective model and
mode telemetry was not surfaced. The release therefore supports
`configured-and-evaluated`, not `runtime-attested`.
