# Venue corpus intelligence

This optional layer supplies evidence-graded context after the portable
scientific review and the official venue profile. It does not alter canonical
criteria, determine acceptance, or turn similarity to accepted papers into a
scientific-quality score.

Use two separately declared corpora when useful:

- `venue-background` records decision-status-verified papers for broad
  evidence-pattern calibration at the named venue, year, and track;
- `topic-near` records papers compared to the manuscript across problem,
  contribution type, mechanism, claim type, evidence structure, and
  modality/application. Topic proximity is multidimensional, not title or
  embedding proximity alone.

Every item keeps publication status separate from scientific content.
Evidence grade `A` is a directly verified official programme, proceedings, or
decision record. Grade `B` is a durable venue-authorised record with a
checkable official link. Grade `C` is an author or bibliographic record useful
for context but not decision calibration. Grade `D` is unverified discovery
material. Grades `C` and `D` are not eligible for material inference.

Corpus size is an observation, not a threshold. Continue search while an
honest, independently specified batch adds eligible papers or new cells across
the six declared topic dimensions. Mark `saturated` only when the latest
recorded batch adds neither. If access, status verification, or coverage is
uncertain, record `not-saturated` or `unknown`.

Manifests store metadata and hashes only. Do not copy manuscript, review, or
decision text into this bundle. Validate a manifest with:

```bash
python scripts/validate_venue_corpus.py venue-intelligence/examples/accepted-synthetic.json
```

The shipped examples are synthetic contract fixtures, not venue evidence.
