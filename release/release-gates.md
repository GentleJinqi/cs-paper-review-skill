# Release gates for v0.2.1

The release may be tagged only when the exact candidate commit satisfies:

- the public README contains only the user-facing per-paper review pipeline;
  maintainer update/release orchestration remains outside the public README;
- the English and Chinese Mermaid graphs have the same nodes, branches, and
  feedback loops, with language-only differences;
- `SKILL.md`, scientific core, venue profiles, Sol Ultra adapter, schemas,
  validators, lifecycle selection, and evaluation artifacts remain
  byte-identical to `v0.2.0`;
- deterministic bundle, run-contract, corpus, fixture, closure, and release
  validators;
- a selected lifecycle candidate backed by two oracle-blind Sol Ultra
  executions and one independent semantic comparison, or an explicitly
  blocked compatibility release;
- a scope check confirming that project-manuscript review, manuscript
  revision, and experiment execution are absent from the release evidence;
- source/licence and copied-byte review;
- venue-profile byte/source authority checks;
- public-tree privacy, symlink, large-file, and fixed-topology scans;
- an exact remote PR-head independent review with no Critical or Important
  blocker;
- `VERSION`, changelog, version decision, manifest, merge commit, tag, and
  GitHub release identity agreement.

These gates do not transform requested model/mode into effective runtime
telemetry and do not claim acceptance prediction or universal review truth.
