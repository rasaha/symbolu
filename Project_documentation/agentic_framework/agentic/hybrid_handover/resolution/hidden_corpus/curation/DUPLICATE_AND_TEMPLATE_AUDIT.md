# DUPLICATE_AND_TEMPLATE_AUDIT

Five similarity signals (`duplicates.py`). Lexical similarity alone never rejects;
QUARANTINE requires a genuinely shared reasoning template (near-identical text AND
identical graph structure).

## Signals
1. exact normalised-text duplicate
2. character-3gram cosine similarity
3. token 3-shingle Jaccard similarity
4. structural graph signature (edge-type multiset + node-type multiset + degree sequence)
5. reasoning-template fingerprint (governance-operation set + abstain + governing count)

## Quarantine rule
`exact_text_dup`, OR (`char_ngram ≥ 0.9` AND `shingle ≥ 0.5` AND identical graph
signature). Sharing a single governance operation type across otherwise-different
cases is NOT a duplicate — that is the same capability with different content, and
is desirable.

## Findings
- Every accepted case is compared against the seed (22) and all other accepted
  cases. **Accepted quarantine hits after documented overrides: 0.**
- The one deliberately-planted near-duplicate (`quar_template_dup`, a one-word
  edit of an accepted case) IS detected and QUARANTINED — the detector works.
- Two accepted cases (`cr_harmful` / `cr_benign`) are a deliberate contrastive
  pair (identical cycle structure, opposite outcome). They trip the structural
  signal and are retained via a **documented adjudicator override**, not silently.

## Guidance
Lexical-only similarity is reported but never auto-rejects. A contrastive pair
(same structure, different decisive fact) is legitimate and requires an override
with rationale, keeping the corpus honest about why a near-structural match was
kept.
