# PSE Complementarity Report — Does phoneme→meaning beat the vritti_mapper approximation?

**Question (verbatim):** *Does using the existing PSE phoneme→meaning system make
the Symbol-U vector `U` more semantic and more complementary than the earlier
vritti_mapper backend?*

**Short answer:** **No, not meaningfully.** Wiring in the canonical PSE
phoneme→meaning system (`varna_lens` + `lexicon_authoritative.json`, 107 semantic
domain-tags) produces a *statistically detectable but practically negligible*
improvement in synonym invariance over `vritti_mapper` (index **+0.012 vs
+0.008**), and — decisively — **every PSE backend still clusters rhymes far more
strongly than synonyms** (pse_meaning: rhyme index **+0.169** vs synonym
**+0.012**). The phoneme→meaning layer tracks **sound, not meaning**, exactly as
the arbitrariness-of-the-sign argument predicts. Gate-0 (semantic validity) is
**not** cleared by PSE.

All work is isolated in `symbolu_neural/complementarity_probe/`. No older
detector file was modified or deleted. Measurement only — no fusion adapter, no
training, no generation changes.

---

## 1. Which PSE implementation was found

I searched for `PSE`, phoneme-semantic, phoneme-to-meaning, varna meaning,
resonance, acoustic/phonological semantic, Sanskrit phoneme, CSR. The canonical
phoneme→meaning system is:

| component | file | role |
|---|---|---|
| **PSE renderer** | `varna_lens/pse_renderer.py` | "Phoneme Semantic/Symbolic Engine" — a *rendering/authoring* layer over the engine below. **Not** the numeric meaning source. |
| **Varna Lens engine** (canonical) | `varna_lens/varna_lens.py` → `analyze(word, model="op")` | the real phoneme→meaning rule engine: word → varṇa decomposition → per-varṇa semantic state via a CV-attachment polarity rule. **This is the canonical source.** |
| **Authoritative lexicon** | `varna_lens/lexicon_authoritative.json` | per-varṇa semantics: `leading_vritti`/`counter_vritti` glosses, and `expanded_properties.domain_tags` (107 distinct meaning tags: *hope, creation, manifestation, …*). |
| (alternative) bridge map | `symbolu_core/formulas/varna_acoustic_mapper.py` + `data/varna_bridge_map_v1.json` | a coarser varṇa→`bridge_meaning` table (e.g. `hope_pressure`). Lower resolution than the lexicon; noted, not used. |
| (resonance metrics) | `symbolu_core/formulas/guna_kosha_resonance.py` | `compute_guna_resonance` / `kosha` indices — operate on *probability vectors*, not words; no varṇa→guna source exists, so not a word-level meaning source. |

**Fragmentation note (honest):** the system is somewhat fragmented. "PSE"
(`pse_renderer`) is an *authoring* layer; the actual phoneme→meaning mapping lives
in `varna_lens.analyze`; the richest semantic table is the lexicon's
`domain_tags`; and `symbolu_core.formulas` holds a *parallel, coarser* varṇa
bridge map plus phonological-only mappers (`vritti_mapper`, `acoustic_unit_mapper`).
I chose `varna_lens` as canonical because it is the documented rule engine with
the richest per-varṇa semantics and is torch-free.

## 2. How phoneme→meaning is computed (the chosen path)

`varna_lens.analyze(word, model="op")`:
1. **Word → varṇas.** g2p / IAST / literal routing yields an ordered varṇa
   sequence (e.g. `happy → ha, a, pa, ya`).
2. **Polarity rule (CV-attachment).** Each consonant gets a pole: a consonant
   with a following vowel (CV onset) → **liberating (+)** state (`counter_vritti`);
   a bare consonant (coda / pre-consonant) → **binding (−)** state
   (`leading_vritti`). Vowels carry their own liberating/binding state.
3. **Per-varṇa meaning.** Each varṇa maps (via the lexicon) to a semantic gloss
   and a set of `domain_tags`.

## 3. The four U backends (uniform interface)

All share `sentence → words → varṇa decomposition → word vector → mean-pooled
sentence vector U`. Code: `backends.py`.

| backend | dim | what `U` encodes |
|---|---|---|
| `vritti_mapper` | 12 | **original approximation.** char → SoundClass → Vritti energy histogram (5) ++ SoundClass histogram (7). Phonological. |
| `pse_meaning` | 131 | **PSE phoneme→meaning.** normalized histogram of consonant `domain_tags` (107) ++ vowel liberating/binding-state tokens (24). The semantic layer. |
| `pse_resonance` | 7 | **PSE polarity/valence "resonance".** liberating vs binding fractions, net valence, whole-word sign, emergent-lean one-hot. |
| `combined` | 150 | concat(`vritti_mapper`, `pse_meaning`, `pse_resonance`). |

**Word vectors:** `pse_meaning` accumulates each varṇa's domain-tags (consonants)
and vowel-state tokens, L1-normalized. **Sentence vectors:** mean-pool word
vectors. (Same shape for every backend.)

## 4. Results

Offline, deterministic, no LLM. 32 synonym groups / 214 words; 15 rhyme groups.
Reproduce: `python -m symbolu_neural.complementarity_probe.cli all`.

### 4.1 exp1 — synonym invariance (does `U` cluster by meaning?)

Invariance index = (between − within)/(between + within); ~0 ⇒ no clustering;
permutation p over 1000 shuffles. Higher = more meaning-invariant.

| backend | dim | within | between | **index** | p |
|---|---|---|---|---|---|
| vritti_mapper | 12 | 0.533 | 0.541 | **+0.008** | 0.093 |
| **pse_meaning** | 131 | 0.314 | 0.322 | **+0.012** | **0.004** |
| pse_resonance | 7 | 1.289 | 1.298 | +0.004 | 0.366 |
| combined | 150 | 1.493 | 1.506 | +0.004 | 0.271 |
| *(phonological null)* | — | 0.380 | 0.385 | +0.006 | — |

- **PSE meaning is the most synonym-invariant backend**, and its p=0.004 is
  significant — so PSE does capture a *real, non-random* sliver of meaning the
  vritti_mapper does not (whose p=0.093 is not significant).
- **But the magnitude is negligible:** index +0.012 means within-synonym
  distances are ~1.2% smaller than between — synonyms still essentially scatter.
  It barely exceeds the phonological null (+0.006). This is a *statistically
  detectable, practically meaningless* effect.

### 4.2 exp3 — phonological-vs-semantic dissociation (the decisive test)

Same metric on two groupings: **synonyms** (same meaning, different sound) vs
**rhymes** (same sound, different meaning). A semantic encoder clusters synonyms;
a phonological one clusters rhymes.

| backend | sem_idx (synonyms) | phon_idx (rhymes) | **dissociation** | leans |
|---|---|---|---|---|
| vritti_mapper | +0.008 | **+0.177** | −0.169 | phonological |
| pse_meaning | +0.012 | **+0.169** | −0.157 | **phonological** |
| pse_resonance | +0.004 | **+0.510** | −0.506 | phonological |
| combined | +0.004 | **+0.331** | −0.327 | phonological |

- **Every backend, including PSE meaning, clusters RHYMES ~14× more strongly
  than synonyms** (pse_meaning +0.169 vs +0.012, both p=0.001 for rhymes).
- *light / night / bright* (unrelated meanings) get near-identical `U`; *happy /
  glad / joyful* (same meaning) do not. **`U` is a function of sound.** The PSE
  phoneme→meaning layer does not change this — it inherits it, because its
  varṇa→tag lookup is still keyed by phoneme identity.

### 4.3 exp2 — incremental info `E` vs `E+U` vs nulls (pipeline only here)

`huggingface.co` is **blocked by this sandbox's network policy (403)**, so a real
semantic embedding `E` cannot be downloaded here. exp2 runs on the offline
`hashing` (non-semantic) backend → **INCONCLUSIVE by design** (E sits at the
3-class chance floor 0.333). Numbers validate the pipeline only; see §6 for the
exact RunPod commands to get a real verdict. Wiring verified for all four U
backends.

## 5. Direct answers to the brief

- **Does PSE improve synonym/paraphrase invariance?** Marginally and
  significantly (index +0.012 vs +0.008, p=0.004), but the effect is negligibly
  small — synonyms still scatter.
- **Does PSE separate semantic from phonological signal?** **No.** exp3 shows
  PSE meaning clusters rhymes (+0.169) ≫ synonyms (+0.012) — it is on the
  *phonological* side of the dissociation, like every other backend.
- **Does PSE add information beyond `E`?** Untestable here (HF blocked). Run §6.
  The prior is weak: a signal that fails synonym invariance and tracks rhyme is
  unlikely to survive partialling out a strong semantic `E`.
- **Does PSE beat null controls?** On exp1/exp3 it barely exceeds the
  phonological null and stays far below any "semantic" bar. exp2 vs the
  shuffled/random/surface/phonological nulls awaits the HF run.

## 6. Honest limitations & exact RunPod commands

**Limitations.** Distant/curated labels (not gold); small sets (214 words / 30
sentences / 15 rhyme groups); single seed for the headline numbers; `pse_meaning`
uses `domain_tags` (richest available) but a different lexicon field or a
syllable-level pooling could shift magnitudes slightly — though not the
direction, given the rhyme dissociation. The PSE→numeric vectorization is one
reasonable choice, not the only one.

**HF is unavailable in this environment** (network policy blocks `huggingface.co`;
verified via the proxy status — `connect_rejected 403` for `huggingface.co:443`).
To get the real exp2 verdict on a machine/RunPod with HF access:

```bash
# one-time
pip install torch transformers numpy

# real incremental-information test, per U backend, with a genuine semantic E:
export PYTHONPATH=$(pwd)
for UB in vritti_mapper pse_meaning pse_resonance combined; do
  python -m symbolu_neural.complementarity_probe.exp2_incremental \
      --embeddings hf \
      --model sentence-transformers/all-MiniLM-L6-v2 \
      --u-backend $UB --seed 0
done

# offline experiments (already runnable anywhere — the decisive ones here):
python -m symbolu_neural.complementarity_probe.cli exp1     # synonym invariance
python -m symbolu_neural.complementarity_probe.cli exp3     # phon-vs-sem dissociation
python symbolu_neural/complementarity_probe/tests/test_probe.py
```

Record the exp2 table in `RESULT_REPORT_TEMPLATE.md`. **Pass condition:** for some
U backend, `E+U > E` AND `E+U >` every `E+null`. Given §4, the honest expectation
is that `E+U ≈ E` (and any gain is matched by the surface/phonological nulls).

## 7. Bottom line for the migration decision

PSE is now available as a first-class backend (`pse_meaning`, `pse_resonance`,
`combined`) alongside `vritti_mapper`, all isolated in
`complementarity_probe/`. The stronger phoneme→**meaning** hypothesis was tested
and **does not rescue the semantic claim**: PSE `U` remains phonological. This
**does not yet justify deleting the older detector files** — the canonical
deletion gate (a real `hf`-backend exp2 result, per `MIGRATION_NOTE.md`) is still
open. Run §6 to close it. Until then, both paths coexist and the old detector
files remain canonical.
