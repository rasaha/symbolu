# B1.1 Local Lexical Audit — Soft-Flag Adjudication

## Scope and non-claims

Adjudicates the **two soft flags** from the local lexical similarity audit
(`B1_1_LOCAL_LEXICAL_SIMILARITY_REPORT`, commit `59b20ad`). Documentation only. Modifies **no** JSON,
**no** source lexicon, runs **no** model/embedding/generation/scoring/judge, generates **no** bridge pool.
Does **not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**).
No ontology / Sanskrit privilege / semantic-truth claim. **Structure, not validated meaning.**

The local audit is a **weaker surface screen** and does **not** replace the blocked embedding gate.

## Audit inputs

- exact duplicates: **0** (PASS) · hard flags: **0** · soft flags: **2** · repeated-head groups: **0** ·
  over-used generic terms (df≥6): **0**
- status before adjudication: `SOFT_REVIEW_REQUIRED`

## Soft flag 1 — Ka ~ Sa

- **Metric:** LCS ratio ≈ 0.62 on `liberating_expression`.
- **Reason:** shared **"without attachment to X"** surface template
  (Ka: *forward-orientation held without attachment to the outcome* · Sa: *clarity without attachment to
  clarity*).
- **Decision: `ACCEPT_WITH_RATIONALE`.**
- **Rationale:**
  - Ka concerns **hope / forward-orientation without grasping the outcome**.
  - Sa concerns **clarity / order without attachment to clarity itself**.
  - The repeated phrase is a **surface template, not semantic collapse** — the objects of non-attachment
    differ (an outcome vs clarity itself).
  - **No JSON rewrite required now.**
  - **Bridge-generation note:** if bridge phrasing would repeat the same template verbatim, the bridge
    generator should rephrase one side so the two bridge phrases are not near-identical.

## Soft flag 2 — Ḍha ~ La

- **Metric:** LCS ratio ≈ 0.51 on `functional_operation`.
- **Reason:** shared **"turns … energy toward protecting the …"** surface template
  (Ḍha: *turns malice-energy toward protecting the maligned* · La: *turns harming-energy toward protecting
  the physically weak*).
- **Decision: `ACCEPT_WITH_RATIONALE`.**
- **Rationale:**
  - Ḍha concerns **malice / social harm transformed into protection of the maligned**.
  - La concerns **physical harming / cruelty transformed into protection of the physically vulnerable**.
  - This is an **intended Karuṇā contrast-pair** with parallel structure but a **distinct object / domain**
    (social-harm vs physical-harm).
  - **No JSON rewrite required now.**
  - **Bridge-generation note:** the bridge generator should avoid making the two phrases identical or
    collapsed (keep the object distinct: *maligned* vs *physically weak*).

## Conclusions

- exact duplicates: **PASS**
- hard flags: **none**
- soft flags: **adjudicated** (both `ACCEPT_WITH_RATIONALE`)
- **local surface status after adjudication: `PASS_LOCAL_SURFACE_ONLY`**
- **no JSON rewrite required**
- the **real embedding gate remains `BLOCKED_DEPENDENCY_UNAVAILABLE`** (huggingface.co egress-denied) and is
  **still owed**
- **a local lexical pass does NOT equal an embedding pass**
- **bridge generation remains blocked** unless we explicitly accept the weaker local fallback in the B1.1
  prereg, or later obtain embedding access and run the real gate

## Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             ADJUDICATION ONLY (documentation)
JSON lexicon modified: NO
Source lexicon:        NOT modified
Embedding run:         NO (still BLOCKED)
Model/generation/scoring/judging: NO
Bridge pool generated: NO
Local surface status:  PASS_LOCAL_SURFACE_ONLY (weaker than embedding gate)
```
**Structure, not validated meaning.** Adjudication only; the embedding gate is still owed and Track B remains
BLOCKED.
