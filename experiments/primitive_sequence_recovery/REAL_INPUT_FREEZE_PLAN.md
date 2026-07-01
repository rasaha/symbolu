# Real-Input Freeze Plan — Primitive-Sequence Recovery

**Status:** Design/plan only. No run, no real scores, no external embeddings, no LLM, no result artifacts, no Stage A change, no pre-registration change. Specifies *what must be frozen before any run* and the readiness gate that prevents accidental runs.

**Design docs:** `varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md`, `varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`. **Scaffold:** `experiments/primitive_sequence_recovery/` (synthetic-only; machinery already proven).

All real artifacts live under a single frozen directory:
`experiments/primitive_sequence_recovery/frozen/` (created only when real artifacts are assembled). Nothing there is committed until it is hashed and listed in the manifest.

---

## 1–2. Real artifact inventory (path · schema · provenance · freeze · readiness)

| # | artifact | path | schema (JSON unless noted) | provenance requirement | freeze | readiness condition |
|---|---|---|---|---|---|---|
| A1 | **varṇa→primitive-atom assignment `τ`** | `frozen/assignment.json` | `{ "varnas": [...], "atoms": [int...], "tau": {varṇa: atom_id} }` — atoms are **opaque ints**, no gloss here | derived from the source table; the mapping author + source cited; **no meaning content in this file** | sha256 | present, injective (or kernel declared), atoms opaque |
| A2 | **realizations `R_j` (≥3)** | `frozen/realizations/R_<name>.json` | `{ "name", "kind", "atom_content": {atom_id: <content ref>}, "meaning_encoder": <ref> }` (see §3) | each `R_j` independently authored/sourced; content source cited per realization | sha256 each | ≥3 present, mutually independent (§3), each covers all atoms |
| A3 | **word list `W`** | `frozen/words.json` | `[ { "word", "varna_seq": [...], "family_id", "sense_id" } ]` | corpus/source cited; single meaning-language declared | sha256 | N ≥ 100, full varṇa coverage, families assigned (§4) |
| A4 | **ground-truth meanings `M(w)`** | `frozen/meanings.json` | `{ word: { "gloss", "sense_id", "source" } }` | dictionary/source cited per word; sense fixed | sha256 | one meaning per (word,sense); no word missing |
| A5 | **distractor pool + sampling rule** | `frozen/distractors.json` | `{ "K", "pool": [meaning_ids], "match_keys": ["freq","len","category"], "seed", "assignments": {word: [meaning_ids]} }` | matching features sourced; **assignments precomputed & frozen** (no runtime sampling) | sha256 | K set, per-word candidate sets frozen, matched |
| A6 | **deterministic realizer/scoring fn** | `frozen/realizer.json` | `{ "kind": "lexical_overlap|wordnet|static_emb|sentence_emb", "id", "version", "params_sha256", "asset_sha256" }` | offline asset (dictionary/wordnet dump/embedding file) hash-pinned; **no network at run** | sha256 (+ asset sha256) | asset present & hash-verified; deterministic |
| A7 | **scramble seeds + Ns** | `frozen/run_params.json` | `{ "n_scram", "scram_seed", "bootstrap_n", "cv_seed", "n_realizers" }` | chosen in advance | sha256 | `n_scram ≥ 1000`, seeds fixed |
| A8 | **exclusion rules** | `frozen/exclusions.json` | `{ "rules": [...], "excluded_words": [...], "reason": {...} }` | rules declared before seeing scores | sha256 | rules frozen; exclusions applied to W before freeze |
| A9 | **decision thresholds** | `frozen/decision_rule.json` | `{ "delta_threshold", "scramble_pct", "ci_level", "require_all_realizations": true, "labels": {...} }` | matches PREREG §8–9 | sha256 | thresholds fixed; `require_all_realizations` true |
| — | **manifest** | `frozen/manifest.json` | see §7 | — | sha256 of all above | `status == "READY"` only when all verified |

**Rule:** every path is hashed; the manifest pins all sha256s; the design-doc hash (`PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`) is also pinned so the run is tied to the registered design.

---

## 3. Realization requirements (≥3 independent)

A realization `R_j` attaches **content** to opaque atoms so meanings can be ranked. It must supply: (a) `atom_content` — a content reference per atom, and (b) a `meaning_encoder` mapping candidate meanings into the same comparable space. The scorer (A6) consumes both. Build **≥3 mutually independent** realizations; recommended set:

1. **English gloss** (`kind: english_gloss`) — each atom → an English gloss; meanings embedded by the same English realizer.
2. **Sanskrit term** (`kind: sanskrit_term`) — each atom → the transliterated Sanskrit vṛtti term; meanings via a Sanskrit/transliteration-aware realizer.
3. **Language-neutral concept ID** (`kind: concept_id`) — each atom → a WordNet synset / Wikidata Q-ID; meanings → their own concept IDs; similarity via a graph/definition metric (no language surface).
4. *(optional)* **Alternate English paraphrase** (`kind: english_paraphrase`) — independent lexical choices, different from R₁.
5. *(optional)* **Third-language gloss** (`kind: other_lang`) — a non-English, non-Sanskrit gloss.

**Independence requirement:** realizations must not share their content source (e.g. R₁ and R₄ must use *different* English lexica, or they are not independent). Declare the independence basis per pair in the manifest.

**Why English-only is insufficient (from CANONICAL §3–4):** by the relabeling-invariance theorem, the real-vs-scramble contrast is invisible on the opaque sequence and appears *only through a realization*. A positive under a single realization is therefore indistinguishable from an artifact of that rendering (e.g. English embedding geometry). The **ontological** claim is the *cross-realization-invariant* advantage; it can only be assessed with ≥3 independent realizations, and English-only yields at most `REALIZATION_ARTIFACT`.

---

## 4. Word-list requirements

- **Language choice:** one meaning-language, declared in advance (e.g. Sanskrit native words, or English). Mixed-language lists are prohibited (translation confound).
- **Coverage:** every varṇa (atom) appears in ≥ some minimum number of words so the assignment is exercised; report per-atom counts; drop atoms with zero coverage or declare them out of scope.
- **Polysemy:** each entry carries a fixed `sense_id`; polysemous words are either sense-disambiguated (one entry per fixed sense) or excluded. No word may contribute multiple senses to the same run.
- **Family-aware grouping:** each word gets a `family_id` (shared-varṇa / etymological family). Families are the resampling unit for the family-aware bootstrap (PREREG §7). Family definition is frozen before scoring.
- **Minimum N:** `N ≥ 100` clean entries after exclusions (power target; MRR paired design).
- **Exclusion rules (frozen in A8):** words with uncovered varṇas; unresolved polysemy; missing ground-truth meaning; morphological duplicates that would leak across train/test family splits.

---

## 5. Distractor rules

- **K candidates:** `K = 8` (1 true + 7 distractors), fixed for all words.
- **Matched distractors:** sampled from other words' meanings, matched on frequency / length / semantic category (match keys in A5) to remove trivial cues.
- **Fixed seeds:** distractor assignment is computed once with a frozen seed and **stored per word** in `frozen/distractors.json`. The run reads assignments; it never samples.
- **No post-hoc sampling:** distractor sets may not be regenerated, reshuffled, or re-matched after any score is seen. Re-sampling invalidates the freeze.

---

## 6. Realizer / scoring options (compare; recommend; do not implement)

| option | determinism | offline | leakage risk | cost | notes |
|---|---|---|---|---|---|
| **lexical overlap** (token Jaccard, gloss↔meaning) | full | yes | low (no learned semantics) | trivial | weak; may floor; good sanity baseline |
| **WordNet similarity** (path/Wu-Palmer over synsets) | full | yes (dump) | low–med | low | natural fit for the **concept-ID** realization; language-neutral-ish |
| **static embeddings** (GloVe/word2vec, frozen file) | full | yes (file) | med (corpus co-occurrence) | low | deterministic; good primary for gloss realizations |
| **sentence embeddings** (frozen encoder) | full (fixed weights, CPU) | needs the model file offline | med–high | med | richer; heavier; must be hash-pinned & offline |
| **LLM judge** | no (sampling) | no | high (world-knowledge leakage) | high | **excluded** for confirmatory runs (non-deterministic, leakage) |

**Recommendation for the first real run:** **static embeddings (a frozen, offline word-vector file) as the primary realizer for the gloss realizations, plus WordNet similarity for the concept-ID realization.** Both are deterministic, offline, hash-pinnable, and carry no LLM/network dependency. Lexical overlap is retained as a sanity baseline. Sentence embeddings are a later robustness arm (heavier asset to freeze). LLM judges are excluded from confirmatory scoring. *No implementation now — this only fixes the choice to be frozen.*

---

## 7. Readiness gate

A manifest `frozen/manifest.json` governs runs:

```
{
  "id": "psr_freeze_v1",
  "design_doc": {"path": "varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md", "sha256": "..."},
  "artifacts": { "assignment": {"path","sha256"}, "words": {...}, "meanings": {...},
                 "distractors": {...}, "realizer": {"path","sha256","asset_sha256"},
                 "run_params": {...}, "exclusions": {...}, "decision_rule": {...} },
  "realizations": [ {"name","path","sha256","kind","independence_basis"}, ... (>=3) ],
  "checks": { "assignment_injective": bool, "coverage_ok": bool, "N>=100": bool,
              "realizations>=3": bool, "distractors_frozen": bool, "asset_verified": bool },
  "status": "NOT_READY" | "READY"
}
```

**Gate rules (to be enforced by a future loader, not built here):**
- `status == "READY"` **iff** every artifact path exists, every sha256 verifies, the realizer asset hash verifies, `realizations ≥ 3` with declared independence, and every `checks.*` is true.
- The runner (`run_primitive_recovery.py`) stays **NOT_RUN** unless the manifest is present **and** `status == "READY"`. Any missing/mismatched hash ⇒ NOT_RUN.
- **No partial run:** a run either loads a fully-READY manifest or does nothing. There is no per-artifact or per-realization partial mode; fewer than 3 verified realizations ⇒ NOT_RUN.
- The confirmatory statistic requires **all** realizations (A9 `require_all_realizations = true`); the gate refuses to run a single-realization confirmatory pass.

---

## 8. Risk register

| risk | description | mitigation (frozen in the plan) |
|---|---|---|
| **realization dependence** | signal appears only under one rendering | ≥3 independent realizations; confirmatory = cross-realization invariant; label `REALIZATION_ARTIFACT` |
| **English-gloss leakage** | English embedding geometry manufactures signal | English is one of ≥3; independence-basis declared; not privileged |
| **distractor difficulty** | too-easy inflates, too-hard floors | K=8, matched distractors, frozen per-word, sanity baseline (lexical overlap) |
| **polysemy** | multiple senses blur meaning | fixed `sense_id`; disambiguate or exclude |
| **family dependence (Galton)** | shared-varṇa/etymological families inflate significance | `family_id` frozen; family-aware bootstrap is the resampling unit |
| **realizer dependence** | a single encoder is idiosyncratic | ≥2 encoders per realization where feasible; `REALIZER_DEPENDENT` label; asset hash-pinned |
| **order weakly tested** | bag/aggregate rendering is near order-invariant | order-scramble is *secondary*; expect `ORDER_NULL`; do not claim the ordered clause from a bag realizer |
| **asset/network drift** | embedding/wordnet asset changes | offline asset hash-pinned in A6; run refuses on mismatch |

---

## 9. Final recommendation

**Order: B → C → A → (D only if needed).**

- **B (draft artifact schemas) — do first.** Cheap, docs-only, and it de-risks C by fixing exact JSON schemas + the manifest schema before any real data is touched. (This note already sketches them; B turns them into committed schema files/stubs.)
- **C (assemble real artifacts) — second.** The expensive, judgement-heavy step (word list, meanings, ≥3 independent realizations, distractor matching). Must follow B so artifacts conform to frozen schemas.
- **A (build freeze-manifest loader) — third.** Implement the readiness gate + hash verification (mirrors the B0 manifest loader pattern) once schemas exist; wire the runner to refuse unless `READY`.
- **D (revise pre-registration) — only if** assembling artifacts surfaces a design gap (e.g. the order clause needs an order-sensitive realizer). Do not revise pre-emptively.

**Do not** jump to a run. The next commit-worthy step is **B: draft the artifact + manifest schemas** (docs/schema-only), keeping the runner at NOT_RUN.

> structure, not validated meaning.
