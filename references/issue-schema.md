# Issue Schema

Every surviving issue in `issue-ledger.md` should include:

- issue id;
- short title;
- severity;
- review impact;
- venue criterion affected;
- manuscript anchor;
- evidence quote or source location;
- why it matters;
- placeholder status;
- recommended response;
- action type;
- source reviewer or audit;
- confidence.

## Review Impact

Use internal issue-level labels:

- `acceptance-critical`;
- `material-weakness`;
- `presentation-only`;
- `optional-strengthening`;
- `author-data-gate`;
- `final-packaging-gate`.

## Action Type

Use:

- `manuscript-only`;
- `author-data-gate`;
- `experiment-required`;
- `final-packaging-gate`;
- `presentation-polish`;
- `reject-no-fix`.

`experiment-required` means the review recommends or gates an experiment. It does not authorize running experiments, downloading model artifacts, generating model outputs, or writing experiment caches during review mode.

Do not silently drop a supported issue. Preserve it, downgrade it with rationale, mark it as an author-data gate, or reject it with evidence.
