# Subagent Architecture

Subagent-driven review is the protocol's main quality control. Keep peer-review simulation separate from process auditing.

## Roles

Real reviewer agents simulate peer reviewers. They read the manuscript independently and write blind reports.

Process agents audit, adjudicate, merge, calibrate, or verify. Do not present process-agent outputs as independent peer-review reports.

## Strict Tier

Use strict tier by default:

- 3 or 4 blind holistic domain reviewers;
- coverage or anti-skim auditor;
- blind AE adjudicator reading only blind reports and the official rubric;
- regression reviewer when prior review ledgers exist;
- new-risk reviewer when prior repairs or revision history exist;
- special-topic reviewer when preflight identifies a high-risk issue;
- AI-writing and style reviewer;
- terminology, math, and notation reviewer;
- layout, PDF, and submission reviewer;
- benchmark or meta-calibration reviewer when venue fit is uncertain or requested;
- final meta-adjudicator.

Strict tier usually uses 10 to 13 subagent tasks. If capacity is lower, run in batches and close completed agents before dispatching more.

## Standard Tier

Use standard tier when the user requests a lighter pass:

- 3 blind holistic domain reviewers;
- 1 blind AE adjudicator;
- 1 combined regression, new-risk, and meta reviewer when prior ledgers exist;
- optional style or layout reviewer when risk is detected.

Standard tier usually uses 5 to 7 subagent tasks.

## Cleanup

Write `subagent-cleanup.md` with subagent label or identifier, role, status, close status, and any degradation caused by capacity limits. Close completed subagents before ending the run when the host supports it.
