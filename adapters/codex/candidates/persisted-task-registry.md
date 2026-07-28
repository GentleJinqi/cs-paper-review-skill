# Candidate: Persisted Task Registry

Status: inactive and evaluation-only.

The root maintains an atomic, disk-backed registry keyed by canonical task ID.
Each entry records dispatch proof, bounded input hashes, expected report,
status, descendant state, and terminal receipt. Children remain read-only and
return reports through unique pointers; only the root writes registry and
canonical review state.

A settled barrier compares the registry, report inventory, coverage
obligations, and canonical ledger before synthesis. Recovery reloads the
registry, revalidates receipts and report hashes, and dispatches only a task
whose canonical ID lacks a valid terminal record.

The candidate provides stronger interruption and compaction recovery evidence
at the cost of more state, validation, and corruption surface. Promotion
requires that this complexity materially improves lifecycle fidelity without
reducing review quality or duplicating work.

