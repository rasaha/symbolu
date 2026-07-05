# B1.1 Local Lexical / Phrase-Similarity Audit — REPORT (interim fallback)

## 1. Scope and non-claims
Local surface-overlap screen over all **34** resolved counter-poles. **Interim WEAKER fallback** for the
blocked embedding gate — detects shared tokens / character n-grams / templates, **NOT** deep paraphrase
synonymy. Does not modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B
(**BLOCKED**). No ontology / Sanskrit privilege / semantic-truth claim. **Structure, not validated meaning.**

## 2. Why this is weaker than the embedding gate
The real embedding gate (`all-MiniLM-L6-v2` cosine) is `BLOCKED_DEPENDENCY_UNAVAILABLE` (huggingface.co
egress-denied). This lexical audit sees **surface form only**: two operations can share almost no words yet
mean nearly the same thing — this screen is blind to that. **`PASS_LOCAL_SURFACE_ONLY` does NOT mean the
embedding gate passed.**

## 3. Inputs
- `b1_1_experimental_contrastive_lexicon_draft.json` (sha256 `434f33440be8452789cd0a41c7119348963d7ee06ea788dd0e0ba3e5ff9f6fdc`)
- fields: liberating_expression, functional_operation (primary) · combined (diagnostic) · contrast_boundary NOT a target
- entries: 34 · no deferrals · vowels excluded

## 4. Methods and thresholds
exact-dup · token Jaccard (hard ≥0.55, soft ≥0.4) · char 3-gram & 4-gram Jaccard (hard ≥0.7,
soft ≥0.55) · LCS ratio (soft ≥0.5) · repeated head phrase (first 3 tokens across ≥3) ·
generic-term df (report ≥6). Normalization: lowercase, strip punctuation, collapse whitespace;
stopwords removed for token-overlap (content/retain terms kept). Thresholds frozen before running.

## 5. Exact duplicate results
- liberating_expression: NONE
- functional_operation: NONE
- result: **PASS (no exact duplicates)**

## 6. Pairwise flag summary
- pairs evaluated: 1122 (561 pairs × 2 primary fields)
- **hard flags: 0** · **soft pair-flags: 2** · repeated-head groups: 0

## 7. Hard flags
_none_

## 8. Soft flags
| A | B | field | metric | score | text A | text B | action |
|---|---|---|---|---|---|---|---|
| Ka | Sa | liberating_expression | lcs_ratio | 0.6216 | forward-orientation held without attachment to t | clarity without attachment to clarity | accept-with-rationale-or-leave-for-embedding-gate |
| Ḍha | La | functional_operation | lcs_ratio | 0.5088 | turns malice-energy toward protecting the malign | turns harming-energy toward protecting the physi | accept-with-rationale-or-leave-for-embedding-gate |

## 9. Repeated head phrases / repeated generic terms
Repeated head phrases (≥3 entries): _none_

Repeated generic terms (df ≥ 6, report-only): _none_

## 10. Gate status
**`SOFT_REVIEW_REQUIRED`** — review required.
Even PASS_LOCAL_SURFACE_ONLY is a **surface** pass only, NOT a contrastivity/embedding pass.

## 11. Relationship to the blocked embedding gate
The real embedding gate remains **owed**. Before B1.1 freeze: either (A) run the real embedding gate and
pass, or (B) the prereg explicitly records that the embedding gate was unavailable (egress-denied) and this
weaker lexical audit was used as fallback, with the elevated risk documented.

## 12. Bridge-generation warning
**Bridge-pool generation remains BLOCKED by default** until the real embedding gate runs. If the owner
proceeds on the local fallback only, the **B1.1 prereg MUST explicitly state** the weaker fallback and the
**elevated risk that R remains strong due to deep synonymy** this audit cannot detect.

## 13. Next recommended gate
`B1_1_LOCAL_LEXICAL_FLAG_ADJUDICATION` (flags to resolve)

## Final status
```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             LOCAL LEXICAL AUDIT (interim, weaker)
Embedding run:         NO (still BLOCKED: model-host egress denial)
Model run:             NO
Bridge pool generated: NO
Generation/scoring/judging: NO
Gate status:           SOFT_REVIEW_REQUIRED
```
**Structure, not validated meaning.** Weaker surface screen; the embedding gate is still owed.
