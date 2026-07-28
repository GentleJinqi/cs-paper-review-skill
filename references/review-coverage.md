# Review Coverage

`references/review-coverage.json` is the canonical criterion set. This file
explains how to apply it; it cannot add or rename a criterion.

For every run, record each ID exactly once with:

- applicability: `applicable`, `inapplicable`, or `uncertain`;
- disposition: `assessed_no_finding`, `finding_linked`,
  `not_applicable`, `needs_verification`, or `blocked`;
- artifact-bounded evidence and the canonical primary stage;
- any task and finding IDs;
- a paper-specific rationale.

Inapplicable is a justified result, never an omission. Uncertain and blocked
rows prevent complete status. A single finding may satisfy several rows when
it has one primary criterion and lists the others as related criteria.

## Canonical criteria

| Criterion ID | Primary stage | Responsibility |
|---|---|---|
| `RC-AUTHORISATION` | `scope-and-authorisation` | Authority, confidentiality, policy, processing, retention, and review-only scope |
| `RC-INPUT-LINEAGE` | `input-freeze` | Binding artifact identity, hash, version, and lineage |
| `RC-INPUT-ALIGNMENT` | `input-freeze` | Source/rendering match and evidentiary roles |
| `RC-INPUT-VERIFIABILITY` | `input-freeze` | Read integrity and sufficient inputs for the requested scope |
| `RC-CRITERIA-AUTHORITY` | `criteria-freeze` | Current first-party requirements separated from calibration |
| `RC-COVERAGE-ACCOUNTING` | `coverage-map` | One evidence-bounded disposition for every canonical responsibility |
| `RC-DELTA-LINEAGE` | `coverage-map` | Prior-ledger and revised-artifact traceability when applicable |
| `RC-PROBLEM-FORMULATION` | `scientific-assessment` | Problem, assumptions, scope, and task identity |
| `RC-CONTRIBUTION-IDENTITY` | `scientific-assessment` | Contribution type, distinctness, and importance |
| `RC-CLAIM-EVIDENCE` | `scientific-assessment` | Claim support, strength, and tested scope |
| `RC-RELATED-WORK` | `scientific-assessment` | Originality, prior-work positioning, and citation coverage |
| `RC-FORMAL-CORRECTNESS` | `scientific-assessment` | Definitions, assumptions, equations, derivations, and guarantees |
| `RC-METHOD-SOUNDNESS` | `scientific-assessment` | Objective, algorithm, implementation, training, and inference coherence |
| `RC-DATA-VALIDITY` | `scientific-assessment` | Provenance, quality, sampling, preprocessing, splits, leakage, and representation |
| `RC-MEASUREMENT-VALIDITY` | `scientific-assessment` | Metric meaning, aggregation, thresholding, and comparison unit |
| `RC-EXPERIMENT-DESIGN` | `scientific-assessment` | Controls, experimental unit, confounds, and ablations |
| `RC-STATISTICAL-VALIDITY` | `scientific-assessment` | Sampling, dependence, uncertainty, effect size, testing, and multiplicity |
| `RC-COMPARISON-FAIRNESS` | `scientific-assessment` | Baseline relevance and protocol, tuning, data, metric, and resource parity |
| `RC-ROBUSTNESS-SCOPE` | `scientific-assessment` | Robustness, generalisation, failure cases, and claim boundaries |
| `RC-REPRODUCIBILITY` | `scientific-assessment` | Sufficient method, data, configuration, protocol, and artefact detail |
| `RC-RESOURCE-CLAIMS` | `scientific-assessment` | Compute, efficiency, latency, memory, energy, hardware, and cost claims |
| `RC-WRITING-CLARITY` | `scientific-assessment` | Argument flow and terminology where scientific meaning is affected |
| `RC-VISUAL-INTEGRITY` | `scientific-assessment` | Figures, tables, captions, reading order, legibility, and rendered layout |
| `RC-LIMITATIONS` | `scientific-assessment` | Material boundaries, failures, and negative evidence |
| `RC-RESPONSIBLE-RESEARCH` | `scientific-assessment` | Applicable ethics, safety, privacy, consent, licensing, dual-use, impact, and integrity |
| `RC-CITATION-SUPPORT` | `evidence-verification` | Source identity and support for material attributed claims |
| `RC-FINDING-EVIDENCE` | `evidence-verification` | Exact evidence for each material candidate finding |
| `RC-CONFLICT-VERIFICATION` | `evidence-verification` | Targeted resolution of conflicting observations |
| `RC-DEDUP-DISPOSITION` | `adjudication` | Semantic deduplication and auditable disposition of every candidate |
| `RC-DISSENT-PRESERVATION` | `adjudication` | Evidence-backed minority concern without vote inflation |
| `RC-REQUIREMENT-LEGITIMACY` | `adjudication` | Paper-specific justification for requested work or changes |
| `RC-RISK-CLASS-SEPARATION` | `synthesis` | Scientific defects, author gates, verification gaps, and readiness gates |
| `RC-COMPLETION-TRUTH` | `completion` | Honest complete, partial, or blocked state |
| `RC-LEDGER-CONSISTENCY` | `completion` | Cross-record agreement, lineage, and no silent finding loss |

The full review question, required evidence, conditional specialist trigger,
and required uncertain/inapplicable output for each ID are defined only in the
JSON companion.
