# External Mechanism Adoption Matrix

Observed 2026-07-28. Every retained mechanism is routed, where eligible, to a
future independent reimplementation; `copied_bytes: 0`. None was implemented
or adopted in this source-audit stage. “Adopt after redesign” means eligible
for incremental conformance testing, not accepted into the release.

| Capability gap | Source mechanisms | Plan-1 disposition | Release condition |
|---|---|---|---|
| Frozen-source anchor validation and candidate-issue falsification | PaperJury anchor check; OpenJudge correctness→criticality; open-science quote cross-check | adopt after redesign / reference-only | One source-aware verifier must improve supported finding fidelity without adding unseeded findings. |
| Canonical ledger, closure evidence, deterministic synthesis, degradation | PaperJury ledger/closure; K-Dense claim validator; ARS synthesis/degradation | adopt after redesign | Missing/malformed data fails closed; one impact scale; every finding and failure has a terminal state. |
| Stable re-review/delta identity | Conrad delta protocol; ARS obligation re-review | adopt after redesign | All prior IDs accounted for; resolved/partial/made-worse/new states match a frozen oracle. |
| Confidentiality intake and safe local I/O | K-Dense intake/common I/O | adopt after redesign | Distinguish public, author-owned, and editorial-confidential material; unsafe or ambiguous transfer blocks. |
| PDF/input integrity and digest invalidation | existing source/PDF rule; ARS PDF preflight; AgentSociety digest recheck; roast evidence inventory | adopt after redesign | Stale, mismatched, malformed, missing, and changed inputs yield distinct correct outcomes. |
| Dissent and fairness | AgentSociety dissent; Meet-Reviewer fairness filter rebuilt from current official sources | adopt after redesign | Evidence-backed minority concern survives; illegitimate critique demotes without suppressing a real claim/evidence defect. |
| Hash-bound forward evaluation and neutral judge packet | Conrad forward runner/judge | adopt after redesign | Exact core/adapter/fixture/prompt/model/runner provenance; deterministic gates before a quote-validated judge. |
| Argument flow | Research-Paper-Writing reverse outline | adopt after redesign | Anchored orphan/evidence mapping adds value over the canonical ledger and does not edit the manuscript. |
| Bibliographic metadata automation | OpenJudge/roast metadata checkers; Conrad reference audit | evaluation-only | Zero false `verified`, mocked fallback/outage coverage, and no claim-support overstatement. |
| Content injection boundary | OpenJudge safety preflight | evaluation-only | Quoted research is not blocked; actual injected instructions and unavailable classifier fail safely. |
| Claim drift | ARS claim ladder/token conservation | evaluation-only | Independently authored fixtures and semantic, not token-only, evidence. |
| Targeted dropped-finding recall | PaperJury recall | evaluation-only | Demonstrated incremental supported recall without duplication or false consensus. |

## Rejected Or Deferred Patterns

- fixed reviewer/juror/persona counts, score-dispersion forcing, and
  loop-until-dry review;
- model-family tier downgrades or unverified effective-model claims;
- unsafe archive extraction and path traversal;
- file-existence validators presented as semantic completeness;
- mandatory OCR/live server as a core completion condition;
- rebuttal drafting or assigned confidential review without separate
  authorisation and venue-policy design;
- generic checklists/templates, style-only prompts, and unlicensed sources;
- corpus counts, vote counts, or historical acceptance outcomes as scientific
  evidence.

Licences and exact commits are recorded in `source-lock.json`. MIT or
Apache-2.0 availability does not make direct reuse desirable; CC BY-NC,
unclear, and derived-source material remains no-copy reference input.
