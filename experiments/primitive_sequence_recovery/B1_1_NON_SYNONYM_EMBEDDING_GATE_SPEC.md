# B1.1 Non-Synonym Embedding Gate — SPECIFICATION (spec only)

## 1. Scope and non-claims

**Spec only.** Defines a future embedding-based near-synonym check over the 32 non-deferred experimental
counter-poles in `b1_1_experimental_contrastive_lexicon_draft.json`, to be run **before** any bridge-pool
generation. This document **implements nothing**: no embedding run, no bridge pool, no model generation, no
scoring, no LLM judge. It does **not** modify B1, change the B1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or
unblock Track B (**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim.
**Structure, not validated meaning.**

## 2. Why this gate exists

- **B1 failed because random resonance R matched A** (A_vs_R 0.5135, CI straddles 0.5) — the specific
  symbolic mapping carried no advantage over a random draw from the same pool.
- The **contrastivity audit** (`VARNA_GLOSS_CONTRASTIVITY_AUDIT.md`) traced this to **liberated/counter-pole
  convergence**: 4 exact-duplicate Sanskrit poles + 2 near-duplicate roots, and broad affect basins, so a
  random pick landed in the same neighborhood as the "correct" pick.
- The **JSON draft** removed *exact-string* duplicates (validator Tests 13–15), but **near-synonyms may
  remain** — two operations can be worded differently yet mean nearly the same thing, which would let R stay
  strong for the same reason as B1.
- Therefore a **non-synonym embedding gate** is required to catch residual near-synonymy **before** the
  bridge pool (which A and R both draw from) is generated.

**Necessary, not sufficient:** passing this gate removes one confound (synonym collapse). It does **not**
make A beat R — a contrastive pool with an arbitrary word→mapping link still yields A ≈ R (that is what the
`R_deranged` control tests, not this gate).

## 3. Inputs

- **File:** `experiments/primitive_sequence_recovery/b1_1_experimental_contrastive_lexicon_draft.json`.
- **Scope:** the **32 non-deferred** entries only — **exclude `Ra` and `Śa`** (deferred, null counter-poles).
- **Fields checked** per entry's `experimental_counter_pole`:
  - `english_rendering` — **primary**
  - `functional_operation` — **primary**
  - `contrast_boundary` — **supporting evidence only**, not a primary similarity target (boundary strings are
    structurally similar by design — "not X, not Y" — so high boundary similarity alone is not a flag).

## 4. Frozen embedding model decision

- **Preferred:** `sentence-transformers/all-MiniLM-L6-v2` (small, stable, widely mirrored, 384-dim).
- **Fallback (if unavailable):** `sentence-transformers/all-mpnet-base-v2` (768-dim, stronger, heavier).
- Rules:
  - the **model ID must be frozen before running** the gate;
  - the **model revision / commit hash must be recorded** in the report if the source exposes one;
  - **no LLM generation** is involved — this is an **embedding-similarity diagnostic, not a judge**;
  - the embedder runs locally/read-only; it produces vectors, not text.

## 5. Similarity metric

- **Cosine similarity over L2-normalized embeddings.**
- Compute pairwise similarity for all C(32,2)=496 pairs, per channel:
  - `english_rendering` vs `english_rendering`
  - `functional_operation` vs `functional_operation`
  - **optional combined text:** `english_rendering + " — " + functional_operation` (reported as a
    tie-breaker / corroborating channel).
- Report the **max** of the primary channels per pair as the pair's headline score; keep per-channel scores
  in the JSON output.

## 6. Threshold policy (PROPOSED until frozen)

| condition | action |
|---|---|
| exact duplicate string (any primary field) | **automatic FAIL** (already covered by validator Tests 13–14; re-asserted here) |
| cosine **≥ 0.88** | **hard flag** — must rewrite or explicitly justify |
| cosine **0.82 – 0.88** | **soft flag** — human review required |
| cosine **< 0.82** | pass, unless manually flagged as suspicious |

**τ (all three cut points) must be frozen before running the actual check** — no post-hoc tuning after
seeing scores. The values above are *proposed defaults*; the frozen values are recorded in the report and
hash-bound.

## 7. Human adjudication rule

For **every** flagged pair (hard or soft), exactly one of:
1. **rewrite** one or both counter-poles (then re-run the gate);
2. **justify** that they are operationally distinct despite embedding closeness (documented rationale);
3. **defer** one entry for human review;
4. **accept as exception** with an explicit rationale.

**No flagged pair may pass by mere synonym substitution** (swapping a word for a synonym without changing the
*operation*). A rewrite must change the operation/boundary, not just the surface wording.

## 8. Required output of the future implementation

- `B1_1_NON_SYNONYM_EMBEDDING_REPORT.json` (machine-readable)
- `B1_1_NON_SYNONYM_EMBEDDING_REPORT.md` (human-readable)

Each **flagged pair** records:
- `varna_a`, `varna_b`
- `field_compared` (english_rendering | functional_operation | combined)
- `similarity_score`
- `text_a`, `text_b`
- `flag_level` (hard | soft)
- `human_decision` (rewrite | accept-with-rationale | defer)
- `rationale`

The report also records: frozen model ID + revision, frozen τ values, number of pairs evaluated, counts of
hard/soft/pass, and the input JSON's sha256 (so the report is bound to the exact draft evaluated).

## 9. Pass/fail rule

The lexicon may proceed to **bridge-pool generation** only if **all** hold:
- **no exact duplicates** exist (primary fields);
- **all hard flags resolved** (rewritten or accepted-with-rationale);
- **all soft flags reviewed** (a human decision recorded for each);
- **Ra and Śa are either resolved** (counter-poles authored + re-checked) **or explicitly excluded/deferred**
  from bridge generation;
- a **final report is committed before** bridge generation.

## 10. Interaction with Ra and Śa

- **Ra and Śa are excluded** from the 32-entry non-synonym check because their counter-poles are deferred
  (null; `human_review_required: true`).
- Before B1.1 freeze, **one of**:
  - **A. resolve** Ra/Śa (author counter-poles) and **re-run** the non-synonym check **including** them (34
    entries), or
  - **B. pre-register their exclusion** from B1.1 generation (documented in the prereg).
- They **cannot silently enter bridge generation** without counter-pole resolution *and* a contrastivity
  check.

## 11. Interaction with the bridge pool

Bridge-pool generation must wait until **all** of:
- the JSON draft passes its validator (already true: 16/16);
- this **non-synonym embedding gate passes** (§9);
- **human adjudication is complete** (every flag has a decision);
- **Ra/Śa handling is finalized** (§10).

Only then is the bridge pool generated (one-to-one, no collapsed duplicates) and frozen inside the B1.1
freeze set.

## 12. Risks

- **Over-flagging:** embedding models may score related-but-operationally-distinct operations as close (e.g.
  the deliberate contrast-pairs Ha↔Kṣa, Ḍha↔La). Human adjudication rule 2 (justify distinctness) exists for
  exactly this.
- **Under-flagging:** small models may miss subtle spiritual near-synonyms that a human would catch;
  therefore soft-flag review is mandatory and a manual suspicious-pair override is allowed.
- **Threshold arbitrariness:** τ is a judgment call; mitigated by freezing τ *before* running and recording
  it. Consider reporting the full similarity distribution so the cut points are inspectable.
- **Documentation:** every human decision must be written down with rationale (no silent passes).
- **No H2 proof:** passing this gate **does not prove H2 validity**; it only **reduces the chance that R
  remains strong because of synonym collapse.** The decisive test remains `R_deranged`.

## 13. Recommended next gate

**`B1_1_NON_SYNONYM_EMBEDDING_GATE_IMPLEMENTATION`** — freeze the model ID + τ, run the local read-only
embedding diagnostic over the 32 non-deferred counter-poles, emit the two report files, and route every flag
through human adjudication. **Do not implement yet** — implementation is a separate, separately-approved
gate.

## Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             SPEC ONLY
Embedding run:         NO
Bridge pool generated: NO
Model generation:      NO
Scoring run:           NO
B1 artifacts modified: NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity /
non-synonymy repair is **necessary but not sufficient**; `R_deranged` remains the crux.

**Structure, not validated meaning.** Spec only; the B1 verdict stands and Track B remains BLOCKED.
