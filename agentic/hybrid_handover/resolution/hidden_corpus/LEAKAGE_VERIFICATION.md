# LEAKAGE_VERIFICATION

Verifies that no hidden information can reach a resolver through the executable
view. Automated in `leakage.verify()`; result: **no findings**.

## Vectors checked
| Vector | Check | Result |
|---|---|---|
| Case ids | must match `^HX[0-9a-f]{10}$` (SHA-1 of executable content only) | pass — opaque, encode no answer/capability/difficulty |
| Case fields | executable case exposes ONLY `{id, question, documents}` | pass |
| Document fields | each document exposes ONLY `{doc_id, citation, order, text}` | pass |
| Surface tokens | no capability name / meta token (`gold graph`, `abstain`, `difficulty`, `capability_tag`, `negative_control`) and no internal `ref` name appears in ids, doc ids, citations, or text | pass |
| Difficulty markers | no word-bounded `L1..L5` in the executable surface | pass |
| Ordering | id-order difficulty sequence is neither ascending nor descending (order does not encode difficulty) | pass |
| Module surface | the executable module exposes no metadata **accessor** (callable named annotation/gold/expect/difficulty/capability) | pass |

## Structural guarantees
- Gold graph, governance, expectations, difficulty, and capability live only in
  `annotations.py`, imported by evaluation/audit code, never by a resolver.
- A resolver is invoked with `evidence_for(id)` (spans) or `executable_cases()`
  (id + question + documents). Neither carries any annotation.
- Ids are content hashes, so even the id cannot be decoded into a label.

## What leakage verification does NOT cover
- It cannot prevent a *caller* from choosing to import `annotations.py` and hand
  metadata to a resolver — that is a process discipline (GENERALIZATION_PROTOCOL.md),
  not a code guarantee. The code guarantees only that the sanctioned resolver-facing
  API is metadata-free.
- Filenames in this directory are descriptive (documentation), but the executable
  DATA and its ids carry no labels, which is the property that matters for a
  resolver reading the corpus programmatically.
