# Realizer + Concept-Resolver Implementation Plan (design note only)

**This document is a design/specification note. It performs NO implementation.**

- **No implementation is done here.** No realizer code, no concept resolver, no assets.
- **No model is selected permanently here.** Model *options* are compared; the final choice
  is deferred to a separately approved step that pins a specific asset by hash.
- **No READY transition here.** Readiness stays NOT_READY.
- **No experiment is run here.** No scores, no embeddings, no retrieval, no network/LLM/API.
- **The existing `frozen/manifest.json` remains preserved as NOT_READY** and is not touched.
- **Implementation requires separate approval** (and, for any model download, explicit
  approval — see §5, environment constraints).

Design basis: `varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md`,
`varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`, `SCHEMA_SPECIFICATION.md`,
`REALIZATIONS_NOTE.md`, `DISTRACTORS_NOTE.md`, `REALIZER_FREEZE_NOTE.md`, `MANIFEST_NOTE.md`.

---

## Recap of the frozen contract the implementation must satisfy

- **Query side.** For a word, take its ordered `varna_sequence` → ordered **opaque atoms**
  via `assignment.tau`. Each realization `R_j` supplies `atom_content[atom]`. The realizer
  composes those contents (in order) into a query representation **in `R_j`'s space**.
- **Target side.** The word's meaning enters `R_j`'s space via
  `meaning_reference.realization_specific_reference[R_j]`.
- **Task.** Rank the true meaning among the **K = 8** frozen candidates
  (`distractors.assignments[word_id]`) by similarity; score with **MRR** (secondary **Top1**).
- **Nulls (`run_params`).** `assignment_scramble_enabled` and `order_scramble_enabled` are
  both true; `scramble_seeds = 1000`; `family_bootstrap = true`; `bootstrap_iterations =
  10000`; `paired_test = wilcoxon_signed_rank`; `alpha = 0.05`; `CI = 0.95`.
- **Decision.** Per-realization positive only if real beats both nulls; confirmatory label is
  **cross-realization invariance** (positive under *all* R_j → `ONTOLOGICAL_SIGNAL`; English-
  only → `REALIZATION_ARTIFACT`; etc., per `decision.py`).
- **Invariants that never change.** `deterministic = true`, `offline_only = true`; no LLM
  judges; no runtime sampling of distractors.

---

## Q1 — Minimal offline deterministic realizer compatible with the frozen artifacts

A realizer is the triple **(space, composition, similarity)**:

1. **Space** `E_j`: a fixed function mapping each realization's `content_ref` (a gloss string,
   a Sanskrit term, or a concept id) to a vector (or graph node). Fixed = same output every
   run; offline = loaded from a pinned local asset.
2. **Composition** `⊕`: an **order-sensitive**, deterministic map from the ordered list of
   atom-content vectors to a single query vector. Order-sensitivity is **mandatory** — the
   theory's claim is about the *ordered* sequence, and `order_scramble` must be able to move
   the score, else the order channel is untestable (see Q10). The composition must be fixed
   and pre-registered (no learned/random weights).
3. **Similarity** `sim`: fixed metric (cosine on unit-normalized vectors, as already frozen in
   `realizer.json`: `similarity_metric = cosine`, `normalization = unit_norm_l2`), or a graph
   similarity for the concept channel.

**Minimal viable realizer** = static per-token vectors + a *fixed, pre-registered
order-sensitive composition* + cosine. No training, no sampling, no network. Candidate
compositions (pick and pre-register ONE primary, keep others as robustness variants):
- **position-decay weighted mean** — weight position *i* by `w_i` with a fixed decay;
- **first-dominant weighting** — heavier weight on the first atom, lighter on the rest
  (theory-motivated: the user's "first consonant is the driver, the rest are passengers");
- **ordered n-gram pooling** — sum of fixed vectors for adjacent atom pairs.
A plain bag-of-atoms sum is **disqualified** (order-invariant).

---

## Q2 — Which realizer first? (lexical / WordNet / static / sentence / multiple)

| option | offline & deterministic? | order-aware? | works for `concept_id`? | English-leakage risk | verdict |
|---|---|---|---|---|---|
| **Lexical overlap** (Jaccard on tokens) | yes, no asset | only via ordered n-grams | **no** (opaque ids share no tokens) | high (compares English words to English words) | **floor baseline only** |
| **WordNet** (path/Wu-Palmer on synsets) | yes, pinned WordNet DB | via composition | **yes** — synsets are concept nodes | medium–high (WordNet is English) | **concept-channel realizer + robustness** |
| **Static embeddings** (per-token vectors) | yes, pinned matrix | via composition | no (needs concept map) | medium; separable en/sa spaces | **recommended primary for en/sa** |
| **Sentence embeddings** (transformer encoder) | **weakly** (version drift), large | yes | no | **high** (dense English distributional bias) | **avoid first** |
| **Multiple realizers** | — | — | — | — | **yes, by design** |

**Recommendation.** Do **not** start with sentence encoders (non-determinism across
versions, heavy English bias, and huggingface.co is firewalled in this environment — §5).
Instead:
- **Primary realizer** for `en_gloss` and `sa_term`: **static token embeddings** with a fixed
  order-sensitive composition, using **separate** en and sa embedding spaces so those two
  realizations are scored in genuinely different spaces (real independence, not a shared
  encoder).
- **Concept realizer** for `concept_id`: a **concept-graph resolver** (Q4), *not* a text
  embedder. WordNet is the natural offline candidate.
- **Robustness realizers** (`robustness_realizers` in `realizer.json`): at least one
  alternative scoring function per channel (e.g., WordNet similarity as an alternative to
  static embeddings for en; lexical-overlap as a floor), so we can separate **realization**
  independence (content source) from **realizer** independence (scoring function). A signal
  that survives both is far stronger.

Crucial distinction to keep straight: the pre-registration's ≥3 **realizations** vary the
*content source*; **robustness realizers** vary the *scoring function*. Both should be varied.

---

## Q3 — How each realization is scored

All three share the pipeline *(compose ordered atom contents → query; embed the candidate
meaning refs; cosine; rank true among K=8; MRR/Top1; assignment- and order-scramble nulls)*.
They differ only in space and content:

- **`en_gloss`** — atom content = English vṛtti gloss string; `E_en` = static English
  embedding of that phrase; query = `⊕` over the ordered atom-gloss vectors; target =
  `E_en(canonical_meaning)`. This channel is the **most leakage-prone** (English vs English).
- **`sa_term`** — atom content = Sanskrit IAST vṛtti term; `E_sa` = a **separate** Sanskrit/
  multilingual static space; target = `E_sa(spelling)` (the word's Sanskrit lexeme). Handle
  the frozen **`atom_31` = "—" gap** (`sa` has no binding-pole term) by a **pre-registered**
  rule — recommended: contribute a **zero vector** for that atom (documented as reducing
  effective sequence length for `sa`-containing words), never a fabricated term.
- **`concept_id`** — atom content = `svc:NN`; target = `wmc:NNN`; similarity is computed by
  the **concept resolver** (Q4), e.g. graph distance between the concept nodes, composed in
  order. **No text embedder** on this channel — that is the whole point of having it.

Report per channel: real MRR/Top1, assignment-scramble null distribution + percentile,
order-scramble null distribution + percentile, family-bootstrap CI, and the paired test.

---

## Q4 — What the concept resolver must do for `concept_id`

The resolver turns the opaque ids into a **language-neutral, non-degenerate, deterministic**
similarity structure:

1. **Freeze a mapping** `svc:NN → concept node` and `wmc:NNN → concept node` in an offline
   ontology (candidate: WordNet synset offsets; alternative: a small hand-built, audited
   concept graph). This mapping is itself a **frozen, hash-pinned asset**, authored under
   separate approval.
2. **Define similarity** between nodes (e.g., WordNet path / Wu-Palmer, or a frozen node
   embedding). Must be **non-degenerate** — not all-pairs-equidistant, or the channel is
   vacuous (this is the current placeholder state flagged in `REALIZATIONS_NOTE.md`).
3. **Guarantee independence from English glosses** (anti-circularity, Q10): the concept map
   must **not** be a mechanical function of the `en_gloss` strings. If it is, `concept_id`
   collapses into `en_gloss` and cross-realization agreement is manufactured. Author it by an
   independent principle and **test** invariance to English-gloss permutation (Q9).
4. Be **deterministic and offline**; expose only rankings, never scores of its own.

Honest note: WordNet is English-derived, so a WordNet-based resolver only *partially* escapes
English. A hand-built concept graph escapes English but injects author bias. Neither is
clean; whichever is chosen must be frozen, audited, and its limitation stated.

---

## Q5 — Local/offline assets required

- **English static-embedding matrix** (`E_en`) — a fixed vector file + vocabulary.
- **Sanskrit/multilingual static-embedding matrix** (`E_sa`) — **distinct** from `E_en`.
- **WordNet database** (for the concept resolver and/or the WordNet robustness realizer).
- **Frozen concept-map file** `svc/wmc → node` (authored locally; part of the resolver asset).
- Optionally, **fixed reproducibility-probe vectors** (expected embeddings of a few probe
  strings) to detect silent asset/version drift.

**Environment constraint (must be surfaced, not glossed over).** In this sandbox,
`huggingface.co` is firewalled (CONNECT 403) and only PyPI is allow-listed; some corpora
(e.g. NLTK WordNet data, embedding binaries) are not reachable by default and PanPhon was
uninstallable in earlier steps. Therefore **any asset download is gated on explicit
approval** and must come from an allow-listed/mirrored, immutable source. If no offline asset
can be obtained, the honest fallback is the **lexical-overlap** floor realizer (no asset) for
en/sa and a **hand-built concept graph** for concept_id — with the reduced power stated
plainly. Do not fabricate a model or its hash (cf. the B0 `T_embed` PINNED_UNVERIFIED
precedent — record provenance honestly rather than invent it).

---

## Q6 — How assets are pinned by sha256

- Compute `sha256` of **each** asset file (embedding matrix, WordNet dump, concept-map file)
  and record it in `realizer.json` (`model_sha256` for the primary; per-asset hashes for the
  resolver and robustness realizers — may require a small schema addition, Q7/Q8).
- **Pin by immutable snapshot/version, never "latest"/`main`** (the pin must not move).
- The loader **verifies on-disk hash == pinned hash before any scoring**; mismatch → refuse
  (NOT_READY / NOT_RUN). The gate already treats a null/missing `model_sha256` as a blocker.
- Add a **reproducibility sanity check**: embed a fixed probe string and compare to a stored
  expected-vector hash, so a same-named-but-different asset is caught (mirrors the B0 runbook).
- Record exact provenance (source URL/snapshot, version, dimension, date) alongside the hash.

---

## Q7 — Exact fields to change in `realizer.json` at implementation

| field | now | at implementation |
|---|---|---|
| `status` | `NOT_IMPLEMENTED` | `IMPLEMENTED` |
| `implementation_present` | `false` | `true` |
| `execution_allowed` | `false` | `true` (only after review) |
| `model_asset` | `null` | path/name of the pinned primary asset |
| `model_sha256` | `null` | sha256 of that asset |
| `concept_resolver` | `null` | id/path of the frozen resolver asset |
| `concept_resolver_status` | `NOT_IMPLEMENTED` | `IMPLEMENTED` |
| `robustness_realizers` | `[]` | list of alternative realizer specs (each with its own asset + hash) |
| `deterministic`, `offline_only` | `true` | **stay `true`** |
| `similarity_metric`, `normalization` | `cosine`, `unit_norm_l2` | unchanged (or per-realizer metric) |

Because `realizer.schema.json` is `additionalProperties: false`, per-asset hashes for the
resolver / robustness realizers will require a **small, separately-approved schema addition**
(e.g. an `assets: { "<id>": "<sha256>" }` map). That is a schema change, so it is out of
scope here and must be done with the implementation.

---

## Q8 — The new manifest (later)

- Create **`frozen/manifest_v2.json`** — **do not overwrite** `manifest.json` (immutability
  rule, `SCHEMA_SPECIFICATION.md` §Versioning). The NOT_READY `manifest.json` stays as the
  historical record.
- `manifest_v2.json` re-hashes **every** artifact whose bytes changed — at minimum
  `realizer.json` (new fields → new `realizer_hash`) and `run_params.json` (`run_enabled →
  true` → new `scramble_seed_hash`) — plus hashes for the new assets (via the schema
  addition), and `design_doc_sha256` of the then-current pre-registration.
- Set `status = READY` **only** when `check_readiness` returns READY with all blockers
  cleared. A run is identified by its manifest hash; re-running from `manifest_v2` is
  bit-reproducible.

---

## Q9 — Tests to add before enabling READY

1. **Determinism** — identical rankings/MRR across two runs and two processes.
2. **Offline** — assert no network egress during scoring (socket guard).
3. **Asset-hash verification** — tamper an asset → gate refuses (NOT_READY/NOT_RUN).
4. **Reproducibility probe** — fixed probe string → expected embedding-vector hash (catches
   silent model/version drift).
5. **Order-sensitivity** — order-scrambling a word's atoms changes the query vector; confirm
   the composition is *not* order-invariant (else the order channel is untestable).
6. **Null calibration** — on synthetic null data (scrambled assignment / random content), MRR
   ≈ chance and the scramble-null false-positive rate ≈ `alpha` (the test is well-calibrated).
7. **Concept-resolver independence / non-degeneracy** — permuting the English glosses does
   **not** change concept-node similarities (anti-circularity); concept space is not
   all-equidistant.
8. **Distractor difficulty** — report chance MRR and its distribution; flag if the frozen
   (class-agnostic) distractors make the task trivially easy (`DISTRACTORS_NOTE.md` limitation).
9. **Leakage probe** — detect words whose meaning string trivially equals one of their atom
   glosses (guaranteed en_gloss hit unrelated to sequence signal); quantify/exclude.
10. **Gate integration** — full `check_readiness(frozen/…v2)` returns READY **only** when all
    of the above pass; and the runner produces the pre-registered decision labels on
    real-shaped inputs (extend the existing synthetic scaffold tests).

READY must not be enabled until **all** pass.

## Q10 — Risks that remain (and mitigations)

- **Realization dependence.** All three realizations trace to the *same* vṛtti table, so
  cross-realization agreement controls for the *encoder*, not for the *concept assignment*.
  Cross-realization invariance is **necessary, not sufficient**. Mitigation: seek a genuinely
  independent second meaning source; treat `concept_id` as the key independence lever; state
  the caveat with any result.
- **English leakage.** `en_gloss` (English vs English) — and WordNet/concept resolvers, which
  are English-derived — can align via English distributional structure regardless of the
  assignment. Mitigation: English-only positive is capped at `REALIZATION_ARTIFACT` (already
  in `decision.py`); keep `E_sa` and the concept space genuinely non-English; audit the
  concept map for English derivation.
- **Concept-resolver circularity.** If `svc/wmc → node` is derived from the English glosses,
  `concept_id` collapses into `en_gloss` and agreement is manufactured. Mitigation: author the
  map by an independent principle; freeze + audit; test invariance to English-gloss permutation
  (Q9.7).
- **Easy distractors.** Class-agnostic random-balanced distractors make MRR optimistic and
  difficulty uneven. Mitigation: report the chance baseline and interpret effect sizes
  relative to it; if a semantic-class field is later added, re-freeze hard negatives (new
  seed, new file).
- **Order-insensitivity.** An order-invariant composition leaves the core "ordered sequence"
  claim untested; an over-tuned one manufactures signal. Mitigation: pre-register a single
  fixed composition; require the order-scramble null; report order-scramble effect separately
  from assignment-scramble effect.
- **Other.** Small N = 107 (limited power; report CIs, don't over-read); multiple comparisons
  across channels × realizers (control `alpha`, pre-register the family); the `sa` "—" gap
  (pre-register the zero-vector handling); asset/version drift (hash + probe).

---

## Explicit closing statement

No implementation, model selection, READY transition, or experiment run was performed in
producing this note. `frozen/manifest.json` remains **NOT_READY** and untouched. Every step
above — realizer implementation, concept-resolver construction, any asset download, the schema
addition, `run_enabled = true`, and the creation of `manifest_v2.json` — **requires separate
explicit approval** before it is carried out.

> structure, not validated meaning.
