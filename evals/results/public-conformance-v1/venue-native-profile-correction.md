# Venue-native fixture correction

The first oracle-blind candidate correctly produced the portable
claims-support finding and the TMLR claims/audience answers, but its dispatch
packet did not contain the exact TMLR reviewer-field profile. It therefore
omitted the required categorical reviewer recommendation while incorrectly
marking the fixture complete.

This was an evaluation-input defect, not a reason to rewrite the frozen
candidate after seeing the oracle. The base output and its independent
15-pass/1-fail adjudication remain immutable.

The fixture now carries a bounded `profile.json` with all required reviewer
field IDs and allowed labels. The delta fixture was also corrected from
`complete` to `partial`, because its short before/after texts do not contain
the typed predecessor, author-response, and matched-rendering evidence required
by the release contract.

Only the invalidated `venue-native` fixture was re-executed by a fresh,
oracle-blind configured Sol Ultra leaf. Its supplemental output uses canonical
public-ledger vocabulary and passes the deterministic native-field and hard
gates. `candidate-view.json` binds the unchanged 15 base fixtures and the one
supplemental fixture; it is the subject of the final independent semantic
adjudication.
