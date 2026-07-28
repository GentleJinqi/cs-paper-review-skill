# Candidate: Minimal Settled Set

Status: inactive and evaluation-only.

The root assigns each dispatch a canonical task ID and maintains an in-memory
set of terminal task IDs. Dispatch is idempotent by task ID. Children return
read-only report artifacts; only the root reconciles them into canonical
state.

Before synthesis, the root compares the dispatch set, terminal set, report
inventory, descendant state, and coverage obligations. Completion is blocked
when any element is missing or inconsistent. A final reconciliation catches a
late report before the ledger is frozen.

The candidate minimises orchestration state and repeated instructions. Its
main evaluation risk is loss of lifecycle memory across interruption or
context compaction. Promotion requires demonstrated recovery without
duplicate dispatch, report loss, or unsupported completion.

