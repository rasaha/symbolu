# Symbol-U Complementarity Probe (experimental / isolated)

**Status: EXPERIMENTAL. This directory is a clean-room measurement harness. It
does not modify, replace, or import the older detector files. No deletion
decision is made here.**

This package answers the *first* scientific question from
[`../clean_softmax/SYMBOL_U_RESEARCH_STRATEGY.md`](../clean_softmax/SYMBOL_U_RESEARCH_STRATEGY.md):

> **Does the Symbol-U variable `U` carry semantic information that is
> *complementary* to — not already contained in — a modern Transformer sentence
> embedding `E`?**

It is **discovery, not deployment**. It *measures* whether the signal exists. It
does **not** build a fusion adapter, a controller, or any architecture to
*exploit* a signal (that comes only if discovery passes). Per the strategy memo,
the most sensitive detector for a weak signal is a direct incremental-information
probe, which needs no adapter.

---

## What it measures

| | Question | Needs an LLM? |
|---|---|---|
| **exp1 — invariance** | Do synonyms (same meaning, different sound) get *similar* `U`? Semantic ⇒ yes; phonological ⇒ no. | **No** (fully offline) |
| **exp3 — dissociation** | Does `U` cluster *rhymes* (sound) more than *synonyms* (meaning)? Phonological ⇒ yes. | **No** (fully offline) |
| **exp2 — incremental info** | Does `E + U` decode a semantic label better than `E` — and better than every null? | Yes (`E`) |

### U backends (`backends.py`) — swap how `U` is computed

| backend | dim | source |
|---|---|---|
| `vritti_mapper` | 12 | original: char → `SoundClass` → Vritti energy state (`symbolu_core.formulas.vritti_mapper`). Phonological. |
| `pse_meaning` | 131 | **PSE phoneme→meaning**: `varna_lens.analyze` + `lexicon_authoritative.json` semantic `domain_tags`. |
| `pse_resonance` | 7 | PSE polarity/valence "resonance" (liberating vs binding poles). |
| `combined` | 150 | concat of all three. |

All wrap the **real** mappers (not the lexicon approximation used by the older
clean_softmax detector). See `PSE_COMPLEMENTARITY_REPORT.md` for the head-to-head.

### Null controls (`U` must beat all of them — §7 of the memo)

- **shuffled_U** — `U` rows permuted (content vs capacity)
- **random** — Gaussian, matched dim (generic fusion capacity)
- **surface** — length, vowel/consonant counts, char-bigram hashing (spelling confound)
- **phonological** — SoundClass histogram only (raw sound *without* the Vritti ontology)

A real `E+U` win must exceed `E` **and** every `E+null`.

---

## Quick start

```bash
# fast end-to-end smoke (offline, no model download)
python -m symbolu_neural.complementarity_probe.cli smoke

# exp1: synonym invariance, all U backends — the cheapest kill switch (no LLM)
python -m symbolu_neural.complementarity_probe.exp1_invariance

# exp3: phonological-vs-semantic dissociation (rhymes vs synonyms, no LLM)
python -m symbolu_neural.complementarity_probe.exp3_dissociation

# exp2: incremental info. Default E backend is a NON-semantic offline stand-in.
# Pick the U backend with --u-backend; a real verdict requires a genuine encoder:
python -m symbolu_neural.complementarity_probe.exp2_incremental --embeddings hf --u-backend pse_meaning

# tests (machinery only, not the hypothesis)
python symbolu_neural/complementarity_probe/tests/test_probe.py
```

### Embedding backends

- `hashing` (default): deterministic, offline, **non-semantic** char-n-gram
  hashing. Exists so the harness/CI/smoke run with no network. **Numbers on this
  backend validate the pipeline, not the hypothesis** — the code says so loudly.
- `hf`: a real pretrained Transformer (`sentence-transformers/all-MiniLM-L6-v2`
  by default), mean-pooled. **The only backend whose results support a
  conclusion.** Requires Hugging Face hub access; in this sandbox `huggingface.co`
  is blocked by network policy, so run `--embeddings hf` on RunPod or any machine
  with HF access.

---

## Files

| file | role |
|---|---|
| `backends.py` | the four U backends (`vritti_mapper` / `pse_meaning` / `pse_resonance` / `combined`) with a uniform `encode` interface |
| `symbolu_engine.py` | deterministic `vritti_mapper` `U` over the **real** mappers |
| `embeddings.py` | `E` — `hf` (real) and `hashing` (offline fallback) backends |
| `nulls.py` | shuffled-U / random / surface / phonological null streams |
| `metrics.py` | invariance index + permutation p; CV linear probe (torch, no sklearn) |
| `exp1_invariance.py` | synonym invariance, all backends (offline) |
| `exp3_dissociation.py` | phonological-vs-semantic dissociation: rhymes vs synonyms (offline) |
| `exp2_incremental.py` | `E` vs `E+U` vs `E+null`, per U backend |
| `cli.py` | unified entry point (`exp1` / `exp3` / `exp2` / `smoke` / `all`) |
| `data/synonyms.jsonl` | 32 curated synonym groups (exp1, semantic axis) |
| `data/rhymes.jsonl` | 15 rhyme groups (exp3, phonological axis) |
| `data/sentences.jsonl` | 30 labeled sentences, 3-way sentiment (exp2 smoke) |
| `tests/test_probe.py` | machinery tests (determinism, shapes, controls, backends) |
| `PSE_COMPLEMENTARITY_REPORT.md` | PSE phoneme→meaning vs vritti_mapper findings |
| `RESULT_REPORT_TEMPLATE.md` | fill-in report for a real (`hf`) run |

---

## Decision criteria (pre-registered, from the strategy memo §9)

- **STOP** — `U` fails synonym invariance (exp1 ≈ 0), or `E+U ≈ E` and ties the
  nulls (exp2). Clean negative; the ontology adds nothing beyond `E`/sound.
- **PIVOT** — `U` helps only phonological tasks or is fully explained by surface /
  known taxonomies. Real but refutes the *semantic* thesis.
- **CONTINUE** — `U` is synonym-invariant **and** `E+U` beats `E` and all nulls,
  replicated across models. Only then climb to causality → utility → deployment.

### Current offline result (this sandbox)

- **exp1**: best backend is `pse_meaning` (index **+0.012**, p=0.004) — barely
  above `vritti_mapper` (+0.008) and the phonological null (+0.006). Synonyms
  still essentially scatter.
- **exp3**: **every** backend (incl. PSE meaning) clusters **rhymes ≫ synonyms**
  (pse_meaning +0.169 vs +0.012) → `U` tracks **sound, not meaning**.
- **exp2**: offline non-semantic backend → **INCONCLUSIVE by design**; a real
  verdict needs `--embeddings hf` (blocked here by network policy).

Full PSE-vs-vritti_mapper head-to-head: **`PSE_COMPLEMENTARITY_REPORT.md`**.
See also `RESULT_REPORT_TEMPLATE.md` and `MIGRATION_NOTE.md`.

---

## Migration note (read before touching the old files)

See [`MIGRATION_NOTE.md`](MIGRATION_NOTE.md). In short: **the older
`clean_softmax` detector files remain canonical.** This directory is the
experimental replacement candidate. No file outside this directory is changed.
Deletion of the old detector is **not** decided here and must wait for a real
`hf`-backend result.
