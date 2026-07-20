# LEAKAGE_VERIFICATION (pilot) — see also seed LEAKAGE_VERIFICATION.md

Extended leakage audit for the pilot (`leakage_pilot.py`). Resolver-facing
artifacts expose none of: capability, difficulty, lifecycle status, author/role,
template family, annotation confidence, ambiguity, gold graph size, governance
outcome, packet expectation, abstention reason, adjudication status.

## Checks — result: no findings
| Vector | Check | Result |
|---|---|---|
| ids | `^HP[0-9a-f]{10}$` content hashes (distinct `HP` prefix from seed `HX`) | pass |
| case fields | executable case exposes only `{id, question, documents}` | pass |
| doc fields | only `{doc_id, citation, order, text}` | pass |
| surface tokens | no capability name, no meta token (difficulty/lifecycle/author/annotator/adjudicat/template/confidence/ambiguity/governance/packet/abstention/quarantin/rejected/accepted/gold graph), no internal ref name | pass |
| difficulty markers | no word-bounded `L1..L5` in surface | pass |
| accepted-only | rejected/quarantined candidates are NOT loadable via the pilot corpus | pass |
| module surface | pilot corpus exposes no metadata accessor (callable) | pass |

Rejected and quarantined candidates cannot be loaded by the pilot executable
loader (`pilot_corpus.is_loadable` is False for every non-accepted candidate).

Opaque ids are content-derived and encode no label. Provenance, gold, difficulty,
and capability live only in `pilot_annotations.py` (evaluation-facing).
