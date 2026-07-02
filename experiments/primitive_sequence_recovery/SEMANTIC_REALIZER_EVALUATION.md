# First Semantic Offline Realizer — Design Evaluation (docs only)

**This document evaluates and recommends; it implements nothing.**

- No implementation code, no schema change, no `manifest_v2`, no experiment run, no scores.
- No model download, no HuggingFace, no LLM/API, no network.
- `manifest.json` stays **NOT_READY**; the runner stays **NOT_RUN**; Stage A untouched.
- Every downstream step (asset acquisition, realizer code, concept resolver, `run_enabled`,
  `manifest_v2.json`) requires **separate explicit approval**.

Design basis: `REALIZER_IMPLEMENTATION_PLAN.md`, `REALIZATIONS_NOTE.md`, `DISTRACTORS_NOTE.md`,
`SCHEMA_SPECIFICATION.md`, `BASELINE_REALIZER.md`, `PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`.

---

## 0. What "realized" means for each frozen realization

The three realizations already fix the content each channel exposes; a semantic realizer must
consume exactly these:

| realization | `meaning_encoder.kind` | atom content | target (meaning ref) |
|---|---|---|---|
| `en_gloss` | `gloss_text` / en | English vṛtti gloss phrase | canonical English gloss |
| `sa_term` | `gloss_text` / sa | Sanskrit (IAST) vṛtti term | Sanskrit lexeme (spelling) |
| `concept_id` | `synset_id` / concept | opaque `svc:NN` | opaque `wmc:NNN` |

So two channels are **text** (English, Sanskrit) and one is **concept nodes**. This split
drives both the architecture (§4) and the family evaluation (§2).

**Hard environment constraint (shapes feasibility).** In this sandbox `huggingface.co` is
firewalled (CONNECT 403) and only PyPI is allow-listed; general asset hosts (Stanford GloVe,
fastText.cc, NLTK data, ConceptNet) are **not** reachable by default. Any asset acquisition is
gated on explicit approval from an allow-listed/immutable source. If no clean asset can be
obtained, the honest position is to **stay at the lexical baselines** rather than fabricate a
semantic realizer or its hash (cf. the B0 `T_embed` PINNED_UNVERIFIED precedent).

---

## 1. The central tension (state it before recommending)

- The **easiest** realizer to build is English static embeddings on `en_gloss`. It is also the
  **least evidentially valuable**: English-vs-English matching is the most leakage-prone
  channel, and an English-only positive is capped at `REALIZATION_ARTIFACT` by design.
- The **most valuable** component is the **concept resolver** for `concept_id` (the only
  channel that can agree with the text channels through *meaning* rather than *surface form*),
  and it is the **hardest** to build cleanly and the most exposed to **circularity**.

A good roadmap therefore builds the cheap text realizer first for plumbing + robustness, but
treats the concept resolver as the evidentially critical, must-be-non-circular component.

---

## 2. Candidate-family comparison

Legend: ✓ good / yes · ~ partial/conditional · ✗ bad / no. "Order" for every embedding family
is **supplied by the fixed composition operator `⊕`, not by the encoder** — the encoder itself
is order-agnostic.

| # dimension | A. Static word emb | B. Static sentence emb | C. WordNet/BabelNet | D. FastText subword | E. Concept graph (ConceptNet/hand) | F. Distributional (build-your-own) | G. Hybrid combo |
|---|---|---|---|---|---|---|---|
| 1 Deterministic | ✓ (fixed lookup) | ~ (version/HW-fragile) | ✓ (fixed DB+algo) | ✓ (fixed hashing) | ✓ (fixed graph) | ✓ if corpus+pipeline frozen | ✓ if weights fixed |
| 2 Fully offline | ✓ once asset local | ✗ usually needs framework/model | ✓ local DB | ✓ once asset local | ✓ local | ~ needs corpus | ~ per component |
| 3 Asset size | ~ 0.15–1 GB | large (GBs) | small (~30–60 MB) | ✗ large (few–7 GB) | ✗ large (GBs) or tiny (hand) | ~ corpus-dependent | sum of parts |
| 4 SHA256 pinning | ✓ single file | ~ weights+tokenizer+ver | ✓ data file | ✓ but heavy to verify | ✓ | ✓ (corpus+artifacts) | ~ multiple assets |
| 5 Order sensitivity | via ⊕ | encoder captures some, uncontrolled | via ⊕ | via ⊕ | via ⊕ | via ⊕ | via ⊕ |
| 6 Cross-realization compat | text (en/sa) | text | concept (+text→synset) | text (en/sa) | concept | text | any |
| 7 English bias | high (en model) | high | **high** (Princeton) | ~ (per-lang models) | ~ (multilingual-ish) | depends on corpus | mixed |
| 8 Sanskrit compat | ✗ most en models | ✗ | ✗ sparse IndoWordNet | ✓ subword + cc.sa model | ~ limited | ~ needs sa corpus | ~ |
| 9 Circularity risk | low | low | **high** if svc/wmc→synset from glosses | low | **high** if hand-built from glosses | ~ corpus-dependent | inherits worst part |
| 10 Concept-resolver compat | ✗ (text) | ✗ | ✓ **natural resolver** | ✗ | ✓ (is a resolver) | ✗ | ~ |
| 11 Compute cost | low | high | low–moderate | moderate | moderate | high (build) | highest |
| 12 Reproducibility | ✓ high | ~ fragile | ✓ high | ✓ (large asset burden) | ✓ | ~ | ~ |
| 13 Failure modes | OOV multiword glosses; no order alone | nondeterminism, leakage | coverage gaps, English-centric, mapping circularity | asset size/availability | circularity, coverage, author bias | corpus-choice DOF | tuning DOF, compounded failure |
| 14 Suitability for frozen pre-reg | ✓ text channels | ✗ (non-determinism) | ✓ **as concept resolver** | ✓ esp. sa channel | ~ alt resolver | ✗ (too many DOF) | ✗ first (tuning DOF) |
| 15 Maintainability | ✓ | ✗ (framework churn) | ✓ | ~ (huge asset) | ~ | ~ | ✗ |

Notes per family (nuances not in the table):

- **A. Static word embeddings** — the cleanest text realizer: deterministic, pinnable, gives
  *separate* `E_en` and `E_sa` spaces (genuine encoder independence). Adds real synonymy over
  the lexical baselines. Weakness: needs a per-language space for `sa` (see D) and a fixed
  composition for order.
- **B. Static sentence embeddings** — in practice transformer encoders: version/hardware float
  nondeterminism, HF-blocked here, dense English distributional bias, hard to pin. **Reject for
  the confirmatory role.**
- **C. WordNet/BabelNet** — the **natural concept resolver**: synsets *are* concept nodes, and
  path/Wu-Palmer similarity is deterministic and offline. But Princeton WordNet is English, so
  it only partially escapes English; and the `svc/wmc → synset` mapping is where **circularity**
  enters and must be audited (§5).
- **D. FastText subword** — best fit for the **Sanskrit** channel (subword handles IAST
  morphology and OOV; a `cc.sa` model gives a real non-English space). Main obstacle is asset
  size + gated download.
- **E. Concept graph (ConceptNet / hand-built)** — an alternative resolver. ConceptNet is large
  and English-heavy; a hand-built graph is tiny but injects author bias and is highly circular
  if drawn from the same glosses. Keep as a *robustness* resolver, not the first.
- **F. Build-your-own distributional vectors** — maximal control but the corpus choice is a
  large researcher degree of freedom; over-engineered for a first step. **Reject as first.**
- **G. Hybrid** — combining encoders introduces combination weights = tunable parameters
  (fitting risk) and compounds failure modes and multiple-comparison surface. **Reject as
  first/confirmatory**; only ever as pre-registered fixed-weight robustness.

---

## 3. Recommendations

- **Implement FIRST:** **A. static word embeddings** as the *text realizer* for `en_gloss` and
  `sa_term` (with `D. fastText subword` supplying the `sa` space, and optionally the `en` space
  too). Rationale: lowest-complexity encoder that adds genuine semantics (synonymy) over the
  lexical baselines, deterministic, offline, hash-pinnable, low circularity, and yields the
  separate en/sa spaces that make those two realizations genuinely independent. Pair it with a
  fixed, **pre-registered order-aware composition** so the `order_scramble` null is meaningful.
- **Primary confirmatory configuration:** there is **no single** confirmatory realizer — the
  pre-registered claim is **cross-realization invariance** across all three channels. The
  confirmatory configuration is *static embeddings on the text channels* **+** *a WordNet-based
  concept resolver on `concept_id`*, each applied only to its own realization, with the
  cross-realization decision (`decision.py`) as the verdict. `concept_id` is the decisive
  independence lever and must clear the circularity audit (§5) or the confirmatory claim is not
  earned.
- **Robustness realizers:** `D. fastText` as an *alternative* text encoder (to show a positive
  is not an artifact of one embedding); the Phase-1/2 **lexical/LCS baselines** as floors;
  optionally `E. ConceptNet` as an alternative concept resolver. A signal that survives a
  *different encoder of the same channel* is much stronger than one that does not.
- **Reject entirely (for the confirmatory role):** **B. static sentence embeddings**
  (nondeterminism, HF-blocked, leakage); **F. build-your-own distributional** (corpus DOF);
  **G. hybrid as the first/confirmatory method** (tuning DOF). B/F/G may only ever appear as
  explicitly pre-registered robustness checks, never as the primary.

---

## 4. Architectural question + recommended architecture

**Should the semantic realizer operate on (A) realized text, (B) realized concept IDs, (C)
both independently, (D) another representation?**

**Answer: (C) — both, independently.** The pre-registration requires scoring **all three**
realizations, and text-based vs concept-based encoders are fundamentally different (that
difference is the whole point of cross-realization invariance). They must never be mixed into a
single space, or the independence they provide collapses. So: a **text realizer** consumes
`en_gloss` + `sa_term`; a **concept resolver** consumes `concept_id`; results are combined only
at the *decision* layer, not the *representation* layer.

```
word ─ varna_sequence ─(τ)→ ordered OPAQUE atoms ─┐
                                                   │  (query side; ⊕ = fixed pre-registered,
   en_gloss:  atom → English gloss ───┐            │       order-aware composition)
   sa_term:   atom → Sanskrit term ───┤            │
                                      ▼            ▼
                              TEXT REALIZER   (E_en / E_sa static+subword spaces)
                              per-atom vectors → ⊕ → query_en , query_sa
   concept_id: atom → svc:NN ──▶ CONCEPT RESOLVER  (svc/wmc → node in an OFFLINE ontology;
                                 hash-pinned, authored INDEPENDENTLY of the English glosses)
                                 per-atom nodes → ⊕ → query_concept

targets (meaning_reference.realization_specific_reference[R_j]):
   en_gloss  → E_en(canonical gloss)   sa_term → E_sa(spelling)   concept_id → node(wmc:NNN)

per realization:  cosine/graph-sim(query, each of K frozen candidates) → rank → MRR/Top1
                  → assignment-scramble null  &  order-scramble null  → per-realization verdict
across realizations:  decision.py → ONTOLOGICAL_SIGNAL / REALIZATION_ARTIFACT / NO_SIGNAL / …
```

**Where the concept resolver fits:** *only* on the `concept_id` channel, as a separately-frozen,
hash-pinned asset = (the `svc/wmc → node` mapping) + (the offline ontology, e.g. WordNet) + (a
fixed node-similarity function). It never touches the text channels. Its output feeds the same
rank→MRR→null→decision path as the text realizers.

---

## 5. Explicit risks

- **English leakage.** `en_gloss` (English vs English) and any WordNet/ConceptNet resolver
  (English-derived) can align via English distributional structure regardless of the varṇa
  assignment. Mitigation: English-only positive capped at `REALIZATION_ARTIFACT`; keep `E_sa`
  and the concept space genuinely non-English; report per-channel results.
- **Concept-resolver circularity (the decisive risk).** If `svc/wmc → node` is derived from the
  same English glosses `en_gloss` uses, `concept_id` collapses into `en_gloss` and
  cross-realization agreement is *manufactured*. Mitigation: author the mapping by an
  independent principle; freeze + audit; **test invariance to English-gloss permutation**
  (permuting the glosses must not change concept-node similarities).
- **Realization dependence (shared source).** All three still trace to the same vṛtti table, so
  cross-realization agreement controls for the *encoder*, not the *concept assignment*.
  Necessary, not sufficient; state with any result.
- **Determinism / version drift.** Embedding/framework versions can silently change vectors.
  Mitigation: pin by immutable snapshot + a reproducibility probe (fixed string → expected
  vector hash); reject sentence encoders for confirmatory use.
- **Sanskrit coverage.** IAST OOV and sparse Sanskrit resources; the `sa` "—" gap (`atom_31`)
  from the freeze must use the pre-registered zero-vector handling.
- **Easy distractors + small N (107).** Class-agnostic distractors make MRR optimistic; power
  is limited. Report the chance baseline and CIs; do not over-read.
- **Asset availability.** Downloads are gated; a chosen family may be unbuildable here without
  approval. Do not fabricate an asset or hash to proceed.

---

## 6. Implementation roadmap (each step separately approved)

1. **Phase 3 — text realizer (family A + D).** Implement `StaticEmbeddingRealizer` behind the
   existing `Realizer` interface for `en_gloss` and `sa_term`; add the fixed, pre-registered
   order-aware composition; obtain + hash-pin `E_en` and `E_sa` (approval-gated). Tests:
   determinism, offline, hash-verify, reproducibility probe, order-sensitivity, `sa` gap
   handling. **No run.**
2. **Phase 4 — concept resolver (family C, audited).** Author + freeze the `svc/wmc → synset`
   mapping and the WordNet asset; implement graph similarity. **Circularity audit**
   (gloss-permutation invariance) and non-degeneracy test are gating. **No run.**
3. **Phase 5 — robustness realizers.** fastText alternative text encoder; ConceptNet alternative
   resolver; lexical/LCS floors wired in. **No run.**
4. **Phase 6 — readiness + execution.** Flip `realizer.json` to IMPLEMENTED with pinned assets;
   set `run_enabled=true` in `run_params.json`; create **`manifest_v2.json`** (never overwrite
   `manifest.json`); only then, with `check_readiness == READY`, execute the pre-registered
   protocol.

---

## 7. What evidence would justify choosing each approach

- **A. static word embeddings (first/text):** justified once a small, immutable, hash-pinnable
  vector file is obtainable offline and passes the reproducibility probe, and the composition
  passes the order-sensitivity test. Positive-signal evidence: real > assignment-scramble on
  `en_gloss`/`sa_term` with the effect surviving the fastText robustness encoder.
- **C. WordNet concept resolver (confirmatory concept channel):** justified only if the
  `svc/wmc → synset` mapping **passes the gloss-permutation invariance audit** (independence
  from English) and the concept space is non-degenerate (not all-equidistant). Absent that
  audit, do not use it for the confirmatory claim.
- **D. fastText (Sanskrit / robustness):** justified if the `cc.sa` asset can be obtained and
  pinned, and gives a `sa` space distinct from `E_en` (correlation of the two spaces low enough
  to count as independent).
- **E. ConceptNet / hand-built graph (robustness resolver):** justified only as a *second*
  resolver that also passes the circularity audit; a signal appearing under both resolvers is
  stronger.
- **B / F / G:** justified only as explicitly pre-registered robustness add-ons, and only after
  the primary configuration exists; never as the first or confirmatory method. B additionally
  requires a demonstrated deterministic, offline, pinnable variant — unlikely here.

---

## 8. Closing

No implementation, asset download, schema change, `manifest_v2`, READY transition, or run was
performed. `manifest.json` remains **NOT_READY**, the runner remains **NOT_RUN**, and Stage A is
untouched. Recommended first step: a hash-pinned, offline **static-embedding text realizer**
(family A, with fastText D for Sanskrit), paired later with an **audited WordNet concept
resolver** (family C) for the confirmatory cross-realization claim — each behind a separate
approval.

> structure, not validated meaning.
