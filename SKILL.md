---
name: cs-paper-review-protocol
description: Use when reviewing CS, ML, CV, NLP, or related manuscripts before submission, especially with a target venue, LaTeX source, PDF layout, subagent-driven review, official venue rubric, issue ledger, or AE-style adjudication.
---

# CS Paper Review Protocol

Use this skill to run a manuscript review, not a manuscript edit. Stop before changing the paper unless the user explicitly asks for a separate revision pass.

## Defaults

- Default venue: `TMLR`.
- Default tier: `strict`.
- Default execution: subagent-driven.
- Default source priority: LaTeX for scientific content, PDF for layout and reading experience.
- Default artifact root: `.paper-review/runs/<date>-<venue>-<tier>-NN/`, unless the user or repo instructions require another location.

## Required First Pass

1. Read user instructions and repo instructions such as `AGENTS.md`.
2. Discover manuscript inputs from user paths first, then repo instructions, then likely manuscript roots such as `main.tex`, `paper.tex`, `latex/`, `overleaf/`, `paper/`, and nearby PDFs. Compare LaTeX/PDF title and section anchors when both exist, and ask the user if multiple plausible manuscripts remain.
3. Freeze selected LaTeX and PDF inputs in `frozen-inputs.md`.
4. Build `official-rubric.md` from official venue sources before reviewer dispatch.
5. Generate `review-run-contract.md` as the internal spec and plan for the run.
6. Self-check the contract. Start review only after source paths, venue, tier, placeholder policy, output directory, subagent plan, and review-only boundary are explicit.

Read `references/venue-refresh.md`, `references/review-workspace-protocol.md`, `references/subagent-architecture.md`, `references/issue-schema.md`, and `references/placeholder-policy.md` before dispatching reviewers. Read `references/tmlr-profile.md` when the venue is TMLR or unspecified. Read `references/source-influences.md` only when explaining provenance or preparing a public release.

Use the matching files under `templates/` when creating run artifacts such as `official-rubric.md`, `review-run-contract.md`, `frozen-inputs.md`, `issue-ledger.md`, reviewer reports, AE adjudication, rejected suggestions, review summary, and subagent cleanup.

## Review Flow

1. Dispatch blind holistic reviewers before process auditors.
2. Keep real reviewer agents separate from process agents.
3. Run AE-style adjudication after blind reports are frozen.
4. Run regression, new-risk, style, terminology, layout, benchmark, or special-topic audits only when the tier and preflight warrant them.
5. Merge findings into `issue-ledger.md`; do not silently drop supported issues.
6. Record rejected or downgraded findings in `rejected-suggestions.md`.
7. Write `review-summary.md` with venue-aware recommendation context.
8. Write `subagent-cleanup.md` and close completed subagents when the host exposes a close operation.
9. Stop without editing manuscript files.

## Tier Selection

Use strict tier unless the user requests standard tier or token limits require a smaller run.

- Strict: 3 or 4 blind holistic reviewers plus process agents for coverage, AE adjudication, regression/new-risk when relevant, special topic, style/AI writing, terminology/math, layout/PDF, benchmark/meta calibration, and final meta-adjudication.
- Standard: 3 blind holistic reviewers, 1 blind AE adjudicator, 1 combined regression/new-risk/meta reviewer when prior ledgers exist, and an optional style/layout reviewer when risk is detected.

If the subagent cap is lower than the tier asks for, batch reviewers and close completed agents before dispatching the next batch.

## Boundaries

- Do not edit the manuscript during review mode.
- Do not run experiments. The review may recommend experiments or mark them as gates, but execution belongs to a separate user-approved workflow.
- Do not invent numerical results, citations, datasets, figure contents, or author decisions.
- Treat missing numbers, missing figure assets, and red revision markup according to `references/placeholder-policy.md`.
- Prefer official venue guidance. Use non-official sources only as labeled field-norm calibration.
- Respect repo artifact placement rules and never write review artifacts into manuscript source directories unless the user explicitly asks.
