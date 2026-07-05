# B1.1 Local Lexical / Phrase-Similarity Audit — SPECIFICATION (interim fallback, spec only)

## 1. Scope and non-claims

**Interim fallback screen only.** Defines a local, no-network, no-model lexical/phrase-similarity audit over
the 34 resolved counter-poles. It is **explicitly weaker** than the sentence-embedding gate: it detects
**surface** overlap (shared tokens, character n-grams, repeated templates), **not deep semantic synonymy**.
It **does NOT replace** `B1_1_NON_SYNONYM_EMBEDDING_GATE` and **does NOT** permit treating that gate as
passed. Spec only — implements nothing. Does **not** modify B1, change the verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology validation, Sanskrit
privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Why this fallback exists

- The **real embedding gate could not run**: the model host `huggingface.co` is denied by the organization
  egress policy (403 CONNECT), so `all-MiniLM-L6-v2` cannot be downloaded (commit `21cf72c`,
  `BLOCKED_DEPENDENCY_UNAVAILABLE`). Cosine similarity **did not run**.
- **Exact duplicates already passed** (no identical `liberating_expression` / `functional_operation`
  strings across the 34).
- A **local lexical audit** can still catch surface overlap, repeated templates, shared phrases, and
  near-copying — useful for cleaning wording before bridge generation.
- **But it cannot prove semantic contrastivity.** Two operations can share almost no tokens yet mean nearly
  the same thing (paraphrase); only an embedding/semantic check catches that. This audit is a hygiene pass,
  not the contrastivity gate.

## 3. Inputs

- **File:** `experiments/primitive_sequence_recovery/b1_1_experimental_contrastive_lexicon_draft.json`.
- **Scope:** all **34** resolved entries (no deferrals).
- **Fields:**
  - `liberating_expression` — primary
  - `functional_operation` — primary
  - optional combined: `liberating_expression + " — " + functional_operation` (diagnostic)
  - `contrast_boundary` — **not** a primary target (shares "not X, not Y" grammar by design; supporting
    context only).

## 4. Methods (local / no-network)

1. **Exact-duplicate check** (already passing; re-asserted).
2. **Normalized token Jaccard** similarity — |A∩B| / |A∪B| over content tokens.
3. **Character 3-gram or 4-gram similarity** — Jaccard (or Dice) over character n-gram sets; catches shared
   phrasing that token-Jaccard misses.
4. **Longest common substring (LCS) ratio** — LCS length / min(len A, len B); catches copied spans.
5. **Repeated-head-phrase check** — identical leading phrase (first N tokens) shared across entries.
6. **Repeated abstract-noun / generic-term count** — frequency of generic terms (e.g. "release",
   "without", "ownership", "attachment", "action", "knowledge") to surface over-reliance on a few words.
7. **Optional local stemming/lemmatization** — only if a local stemmer (e.g. a bundled Porter/Snowball, or
   `nltk` if already installed) is available; **otherwise skip** (do NOT download resources).

All pure-Python / stdlib where possible; numpy allowed (already present). No network, no model.

## 5. Normalization

- lowercase
- strip punctuation
- normalize whitespace (collapse runs, trim)
- **for the token-overlap check only:** remove a small closed stopword set (the, a, an, of, to, into, and,
  or, by, it, its, one, without, that, would, from, "—")
- **retain important content terms** even if frequent: *binding, release, ownership, attachment, knowledge,
  action, truth, discernment, clarity, identity, compassion, force, energy, order* (these carry the
  operational meaning; removing them would hide real overlap).
- character-n-gram and LCS checks run on the punctuation-stripped, lowercased text **without** stopword
  removal (structure matters there).

## 6. Proposed thresholds (PROPOSED until frozen)

| metric | condition | flag |
|---|---|---|
| exact duplicate string | any primary field | **FAIL** |
| token Jaccard | ≥ 0.55 | hard |
| token Jaccard | 0.40 – 0.55 | soft |
| char n-gram similarity | ≥ 0.70 | hard |
| char n-gram similarity | 0.55 – 0.70 | soft |
| LCS ratio | ≥ 0.50 | soft (unless only boilerplate, e.g. shared "not …, not …") |
| repeated identical head phrase | across 3+ entries | soft |

Thresholds are **heuristic** and must be **frozen before running** the implementation; record them in the
report. The headline per pair = the strongest (highest-severity) triggered metric.

## 7. Flag output

Each flagged pair records:
- `varna_a`, `varna_b`
- `lexicon_key_a`, `lexicon_key_b`
- `field_compared`
- `metric` (token_jaccard | char_ngram | lcs_ratio | repeated_head)
- `score`
- `text_a`, `text_b`
- `flag_level` (hard | soft)
- `suggested_action` (rewrite one/both | accept-with-rationale | **leave-for-embedding-gate**)
- `rationale` (`<TBD_HUMAN>` placeholder)

The report also records: frozen thresholds, normalization settings, input sha256, counts, and the
generic-term frequency table.

## 8. Pass/fail status

- **`PASS_LOCAL_SURFACE_ONLY`** — no exact duplicates, no hard flags, all soft flags reviewed. **This is a
  surface-hygiene pass, NOT a contrastivity pass.**
- **`SOFT_REVIEW_REQUIRED`** — soft flags exist.
- **`HARD_REVIEW_REQUIRED`** — hard flags exist.

**IMPORTANT:** even `PASS_LOCAL_SURFACE_ONLY` **does not permit treating the embedding gate as passed.** The
embedding gate remains `BLOCKED_DEPENDENCY_UNAVAILABLE` until it actually runs.

## 9. Relationship to the blocked embedding gate

- This audit can **help clean wording** before bridge generation (catch accidental copy/paste, template
  reuse, over-used generic words).
- It **cannot replace embedding cosine** — it is blind to paraphrase synonymy.
- **Before B1.1 freeze, one of:**
  - **A.** the real embedding gate runs and passes; **or**
  - **B.** the prereg **explicitly states** the embedding gate was unavailable (egress-denied) and the local
    lexical audit was used as a **weaker fallback**, with the elevated risk documented.
- **Preferred scientific path remains: run the real embedding gate when model access is possible** (A).

## 10. Bridge-generation policy

- Bridge-pool generation **should still wait for the real embedding gate** if feasible (network allow-list or
  a cached model).
- If the owner chooses to proceed on the **local fallback only**, the prereg **must** label the pipeline as
  using a weaker contrastivity screen and record the **higher risk that R remains strong due to deep
  synonymy** the lexical audit cannot detect. This is a documented scientific concession, not a silent
  downgrade.

## 11. Risks

- **Misses synonyms/paraphrases** — the core weakness; different words, same meaning slip through.
- **Over-flags** repeated *necessary* domain words (binding/release/ownership) — mitigated by the retain-list
  + human accept-with-rationale.
- **Under-flags** conceptually similar operations worded differently.
- **Heuristic thresholds** — no principled calibration; freeze-before-run guards against tuning-to-taste.
- **False confidence** — the biggest risk: mistaking a `PASS_LOCAL_SURFACE_ONLY` for a real contrastivity
  pass. The status name and §8/§9 exist to prevent exactly this.

## 12. Recommended next gate

**`B1_1_LOCAL_LEXICAL_SIMILARITY_AUDIT_IMPLEMENTATION`** — freeze thresholds + normalization, run the local
audit over the 34 entries, emit `B1_1_LOCAL_LEXICAL_SIMILARITY_REPORT.{json,md}`, route flags through
adjudication. **Do not implement yet.** The real embedding gate remains owed (path A/B of §9).

## Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             SPEC ONLY (interim fallback)
Embedding run:         NO (still BLOCKED: model-host egress denial)
Model run:             NO
Bridge pool generated: NO
Generation/scoring/judging: NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. This lexical audit is a
**surface hygiene screen, weaker than embedding cosine**; contrastivity repair remains **necessary but not
sufficient**, and `R_deranged` remains the crux.

**Structure, not validated meaning.** Spec only; the B1 verdict stands and Track B remains BLOCKED.
