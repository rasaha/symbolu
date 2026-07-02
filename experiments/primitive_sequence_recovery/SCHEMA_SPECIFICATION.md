# Schema Specification — Frozen Artifacts for Primitive-Sequence Recovery

**Status:** Documentation only. No implementation, no JSON files, no code, no run, no real data, no embeddings/scores, no Stage A change, no pre-registration change. This document defines the exact schema **every** future artifact must satisfy before `manifest.status` may become `READY`.

**Design basis:** `varna_lens/CANONICAL_PRIMITIVE_REPRESENTATION.md`, `varna_lens/PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md`, `experiments/primitive_sequence_recovery/REAL_INPUT_FREEZE_PLAN.md`. Types below are described in words (JSON Schema draft 2020-12 is the intended encoding when schema files are later authored under `frozen/schemas/`).

**Conventions.** All IDs are strings unless noted. All hashes are lowercase sha256 hex. "frozen" = present, hash-listed in the manifest, immutable. Any field not listed for an artifact is **prohibited** (`additionalProperties: false`).

---

## 1. `assignment.json` — varṇa → opaque primitive atom

**Purpose:** the frozen mapping `τ: varṇa → opaque atom`. This is the ontology's only real content, and it is **deliberately semantics-free**.

```
{
  "schema_version": "1.0",
  "varnas":  [ "<varna_id>", ... ],          # ordered, unique
  "atoms":   [ "<atom_id>",  ... ],          # unique opaque identities
  "tau":     { "<varna_id>": "<atom_id>" }   # total over varnas
}
```
Each `tau` entry contains **only** `varna_id → atom_id`. **Prohibited anywhere in this file:** glosses, polarity, coordinates, vectors, embeddings, operators, phonetic features, realization text, or any human-readable meaning.

**Why assignment is intentionally semantics-free.** By the relabeling-invariance theorem (`CANONICAL_PRIMITIVE_REPRESENTATION.md` §3), the real-vs-scrambled contrast is invisible on the opaque sequence; the assignment's *content* becomes testable **only through a realization**. Keeping `assignment.json` free of any meaning guarantees that (a) the ontology object stays the pure opaque mapping, (b) content is supplied **only** by realizations (which can be varied and factored out), and (c) no meaning can leak into the assignment and pre-bias a run. Atoms are pure identities: `atom_id` strings must be arbitrary tokens (e.g. `a0`, `a1`), not words.

---

## 2. `realization_<name>.json` — one realization `R_j`

**Purpose:** attach **content** to opaque atoms (and, by reference, to meanings) so a sequence can be ranked. Content lives here, never in the assignment.

```
{
  "schema_version": "1.0",
  "realization_id": "<string>",              # unique across realizations
  "language":       "<BCP-47 | 'concept'>",  # e.g. "en","sa","concept"
  "source":         "<dataset/lexicon name>",
  "provenance":     "<citation/URL/derivation note>",
  "version":        "<string>",
  "atom_content":   { "<atom_id>": "<content_ref>" },  # total over atoms
  "meaning_encoder": {                          # how meanings enter the same space
      "kind": "<gloss_text | synset_id | qid | vector_ref>",
      "ref":  "<realizer-consumable reference>"
  }
}
```
`content_ref` is a realization-appropriate reference (a gloss string, a synset ID, a Q-ID, …) consumed by the frozen realizer (§6). 

**Independence requirements.** At least **3** realizations are required, and each pair must be **independent**: different `source` lexica/ontologies and different `language`/`kind`, so a shared bias cannot manufacture cross-realization agreement. Two English gloss sets drawn from the same dictionary are **not** independent. The manifest records the independence basis per pair. English is **one** realization, never privileged; an English-only positive is at most `REALIZATION_ARTIFACT`.

---

## 3. `word_list.json` — the words `W` (no meanings)

```
{
  "schema_version": "1.0",
  "words": [
    {
      "word_id":        "<string>",           # unique
      "spelling":       "<surface string>",
      "varna_sequence": [ "<varna_id>", ... ], # atoms via τ; must reference known varnas
      "family_id":      "<string>",            # shared-varṇa/etymological family
      "sense_id":       "<string>",            # fixed sense (polysemy control)
      "exclude_flag":   false
    }
  ]
}
```
**No meanings are stored here** (see §4). `varna_sequence` uses `varna_id`s only; the atom sequence is derived through `assignment.json` at load, keeping the word list decoupled from the (separately frozen) assignment.

---

## 4. `meaning_reference.json` — ground-truth meanings (separated)

```
{
  "schema_version": "1.0",
  "meanings": [
    {
      "word_id":          "<string>",          # references word_list
      "canonical_meaning":"<language-neutral meaning key + source>",
      "realization_specific_reference": {       # how the meaning enters each R_j's space
          "<realization_id>": "<content_ref>"
      }
    }
  ]
}
```
**Why meanings are separated from the word list.** (a) *Ontology hygiene:* `word_list.json` is form/structure (spelling, varṇa sequence, family, sense); meanings are the *target*, and mixing them invites leakage between the query side and the target side. (b) *Realization factoring:* each realization needs its own meaning encoding (`realization_specific_reference`); putting these in the word list would bloat it and couple it to realizations. (c) *Freeze independence:* the word list and the meanings can be authored, hashed, and audited separately, so a change to meanings does not silently alter the word-structure artifact.

---

## 5. `distractors.json` — frozen candidate sets

```
{
  "schema_version": "1.0",
  "K": 8,
  "match_keys": [ "frequency", "length", "category" ],
  "sampling_seed": <int>,
  "assignments": { "<word_id>": [ "<word_id>", ... ] }   # K candidates = true target (once) + K-1 distractors
}
```
**Why distractors must be frozen.** If candidate sets were sampled at run time, the difficulty (hence the score) would depend on an unfrozen random draw, and re-sampling after seeing scores would be a researcher degree of freedom that inflates false positives. Freezing the per-word candidate IDs with a fixed `sampling_seed` makes the ranking task **fully reproducible** and forbids post-hoc reshuffling. Distractors are matched on `match_keys` to remove trivial cues.

---

## 6. `realizer.json` — the deterministic scoring function (no results)

```
{
  "schema_version": "1.0",
  "realizer_id":        "<string>",
  "model":              "<asset/model name>",
  "version":            "<string>",
  "deterministic":      true,
  "offline":            true,
  "embedding_dimension":<int | null>,
  "similarity_metric":  "<cosine | wordnet_path | jaccard | ...>",
  "asset_sha256":       "<hash of the offline asset file>"
}
```
`deterministic` and `offline` **must** be `true` for a confirmatory run (no sampling, no network). LLM judges are excluded (non-deterministic, leakage). **No results/scores** appear in this file — only the fixed configuration and the pinned asset hash.

---

## 7. `manifest.json` — the readiness gate

```
{
  "schema_version":     "<string>",
  "design_doc_sha256":  "<hash of PREREG_PRIMITIVE_SEQUENCE_RECOVERY.md>",
  "assignment_hash":    "<sha256>",
  "realization_hashes": { "<realization_id>": "<sha256>" },   # >= 3
  "word_hash":          "<sha256>",
  "meaning_hash":       "<sha256>",
  "distractor_hash":    "<sha256>",
  "realizer_hash":      "<sha256>",
  "scramble_seed_hash": "<sha256>",   # of run_params (seeds, N_scram, thresholds)
  "independence_basis": { "<rid_a>|<rid_b>": "<reason>" },
  "status":             "NOT_READY" | "READY"
}
```
`status` is a closed enum: **only** `NOT_READY` or `READY`. The runner stays `NOT_RUN` unless the manifest exists **and** `status == "READY"`. No partial runs.

---

## Validation rules (every schema)

**Structural (per file):**
- `additionalProperties: false` everywhere — unknown fields reject.
- all required fields present; all IDs non-empty strings.

**assignment.json**
- `varnas` unique (no **duplicate varṇas**); `atoms` unique (no **duplicate atom IDs**).
- `tau` is **total** over `varnas` and its values ⊆ `atoms` (no **unknown IDs**).
- injective unless a kernel (shared atoms) is explicitly declared; declare and count collisions.
- **prohibited-content scan:** reject if any value is a natural-language word / vector / number-array (atoms must be opaque tokens).

**realization_*.json**
- `atom_content` **total** over the assignment's `atoms` (no **missing realization entries**).
- `realization_id` unique; `meaning_encoder.kind` in the allowed enum.
- ≥3 realizations overall; each pair independent (distinct `source` **and** `language`/`kind`) — else reject the set.

**word_list.json**
- `word_id` unique; every `varna_sequence` element ∈ assignment `varnas` (no **unknown IDs**).
- every word has a `family_id` (no **missing families**) and a `sense_id`.
- excluded words (`exclude_flag=true`) are dropped before counting; post-exclusion `N ≥ 100`.

**meaning_reference.json**
- exactly one meaning per `(word_id, sense_id)`; every non-excluded `word_id` has a meaning (no **missing meanings**).
- `realization_specific_reference` has a key for **every** `realization_id` (no **invalid references**).

**distractors.json**
- every `word_id` has a frozen candidate list of length `K` = the true target (exactly once) + `K-1` distinct distractors.
- all candidate IDs reference known words/meanings (no **unknown IDs**); `sampling_seed` present; assignments immutable.

**realizer.json**
- `deterministic == true` and `offline == true`; `asset_sha256` present and verifies against the on-disk asset (no **hash mismatch**).

**manifest.json**
- every `*_hash` matches the sha256 of the corresponding artifact on disk (no **hash mismatch**).
- `realization_hashes` has ≥3 entries; `independence_basis` covers every realization pair.
- `design_doc_sha256` matches the current pre-registration.
- cross-file referential integrity holds (word↔meaning↔distractor↔realization IDs all resolve).
- `status == "READY"` is permitted **only** when *all* the above pass; otherwise `NOT_READY`.

---

## Repository layout

```
experiments/primitive_sequence_recovery/
    frozen/
        assignment.json
        realization_en.json          # English gloss
        realization_sa.json          # Sanskrit term
        realization_concept.json     # language-neutral concept IDs
        word_list.json
        meaning_reference.json
        distractors.json
        realizer.json
        run_params.json              # seeds, N_scram, thresholds (hashed as scramble_seed_hash)
        manifest.json
    schemas/                          # the JSON Schema files (authored later; docs-only now)
        *.schema.json
```
Realizer assets (embedding files / WordNet dumps) live outside `frozen/` but are **hash-pinned** by `realizer.json.asset_sha256`. Nothing under `frozen/` is committed until hashed and listed in the manifest.

---

## Versioning

- Each artifact carries `schema_version`; the manifest carries its own `schema_version`.
- **Immutability:** a frozen artifact is never edited in place. A revision creates a **new file + new hash** (e.g. `assignment_v2.json`) and a **new manifest** (`manifest_v2.json` / `psr_freeze_v2`). Old manifests remain valid records of old runs.
- **Reproducibility:** a run is identified by its manifest hash; because every input hash is pinned there, re-running from the same manifest is bit-reproducible. Schema-version bumps require a migration note and MUST NOT retro-alter an existing frozen manifest.
- Backward-incompatible schema changes increment the major `schema_version`; loaders reject artifacts whose major version they do not support.

---

## Readiness checklist (NOT_READY → READY)

`manifest.status` may become `READY` **only** when **all** hold:

1. `assignment.json` present, hashed; varṇas unique, atoms unique, `tau` total & injective (or kernel declared); **prohibited-content scan passes** (fully semantics-free).
2. **≥3 realizations** present, hashed; `atom_content` total over atoms; every pair independent with a recorded `independence_basis`.
3. `word_list.json` present, hashed; IDs resolve; every word has `family_id` + `sense_id`; post-exclusion `N ≥ 100`; full atom coverage.
4. `meaning_reference.json` present, hashed; one meaning per non-excluded word; a `realization_specific_reference` for **every** realization.
5. `distractors.json` present, hashed; `K=8`; frozen per-word candidate sets of size `K` (true target once + `K-1` distractors); matched (or documented balanced-sampling limitation); `sampling_seed` fixed.
6. `realizer.json` present, hashed; `deterministic` & `offline` true; `asset_sha256` verifies against the asset.
7. `run_params` present, hashed (`scramble_seed_hash`); `n_scram ≥ 1000`, seeds + decision thresholds fixed; `require_all_realizations = true`.
8. `design_doc_sha256` matches the current pre-registration.
9. **Cross-file referential integrity** passes (all IDs resolve across assignment/words/meanings/distractors/realizations).
10. Every manifest `*_hash` verifies against on-disk files.

If **any** condition fails → `status = NOT_READY` and the runner returns `NOT_RUN`. No partial or single-realization confirmatory run is permitted.

> structure, not validated meaning.
