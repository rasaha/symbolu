# Stage A′ — Phoneme / G2P Operator-Layer Design

**Status:** Design memo (docs-only). A **separate versioned substitute** design for the L1 operator layer. Not
code, not a dataset, not a run, not a patch to frozen Stage A.
**Governed by:** `B1_4B_STAGE_A_DECOMPOSITION_COVERAGE_AUDIT.md` (`0e2a346`),
`PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `MILESTONE_A_CANDIDATE_F_SPEC.md`,
`SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**Frozen Stage A untouched. No meaning validated. B1.4b remains blocked. Track B remains blocked. Structure,
not validated meaning.**

Grounding (read-only, not modified): `symbolu_neural/structural_v1/{features,operators}.py`.

---

## 1. Purpose

Stage A′ is a **separate, versioned substitute** for the L1 operator layer, designed to expand **decomposition
coverage** so B1.4b is no longer blocked at L1. It is **not** a patch or edit to the frozen Stage A; the frozen
layer stays exactly as-is. This memo specifies the design only — it writes no code, builds no data, runs
nothing, and validates no meaning. Its deliverable is a design + coverage-target + risk statement, gated to a
future pre-registration.

---

## 2. Problem statement

The coverage audit (`0e2a346`) found the frozen Stage A operator layer supports **only 14 graphemes**
(`a b d g i k l m n p r s t z`; only vowels `a`, `i`). Measured on repo-local pools:

- Sanskrit pool: **15/107 fully decomposable (14.0%)**, ~69% character retention.
- English concrete-object pool: **9/92 fully decomposable (9.8%)**, ~64% character retention.
- ~85–90% of words decompose only **partially** (character-dropping).

Character-dropping is **invalid for a real B1.4b run**: F-3 computed on a truncated unit sequence describes a
mangled sub-word, not the word. The residual fully-decomposable set (~15/~9) is far below the ≥100 floor and
underpowered. Decision on record: `STAGE_A_PARTIAL_DECOMPOSITION_BLOCKS_REAL_RUN` /
`STAGE_A_COVERAGE_TOO_THIN`. **L1 coverage must be expanded before B1.4b can run faithfully.**

---

## 3. Frozen Stage A boundary

Frozen Stage A (`symbolu_neural/structural_v1`) **remains untouched** and is **not** modified, re-scored, or
deprecated by this memo. Its historical validity stands **only** as a **minimal structural testbed** (its own
source marks the 14-grapheme features "provisional… not validated… not meaning-carrying"; Stage A G1/G2/G3
pass, G4 not validated — all structural, not semantic). Stage A′ is a **new version alongside** it, not a
replacement of the frozen artifact. Any B1.4b use of Stage A′ is a **new versioned study**, never a silent
substitution into an existing frozen run.

---

## 4. Design principle

Stage A′ pipeline:

```
word
  → language-aware G2P / transliteration normalizer   (spelling → canonical phonemes)
  → phoneme sequence                                  (over a fixed phoneme inventory)
  → articulatory feature vector  f_σ                  (place / manner / voicing / sonority / vowel dims …)
  → operator sequence  M_σ = expm(Σ_j f_{σ,j} G_j)    (structural principle preserved)
```

The **structural principle is preserved unchanged**: each phoneme maps to a feature vector, and the operator is
the matrix exponential of a feature-weighted sum of fixed generators. Only the **front end** changes — a
phoneme inventory + G2P replaces the raw 14-grapheme chart.

---

## 5. Why phoneme-based rather than raw grapheme expansion

- **English spelling is not phonemic** — the same letter maps to many sounds (`a` in *cat/care/about*), and
  many sounds are multi-letter (`sh, th, ch, ng`). Expanding the *grapheme* chart would bake spelling
  inconsistency into the operators.
- **Sanskrit transliteration carries diacritics** (`ā, ṛ, ṣ, ś, ṇ, …`) that encode phonemic distinctions;
  dropping or ad-hoc-mapping them (as the 14-chart does) is lossy and arbitrary.
- **A phoneme layer normalizes both** to a shared articulatory space: `sh → /ʃ/`, `ā → /aː/`, etc. Coverage
  and faithfulness both improve, and the operator inputs become **articulatory features of sounds** rather than
  **accidents of orthography**. This is cleaner and more defensible than direct spelling expansion.

---

## 6. Language tracks

Two normalization tracks over a **shared articulatory feature space**, with **separate normalization rules**:

- **`A_PRIME_EN`** — English **G2P** phoneme layer (e.g. an ARPAbet/IPA-style phoneme set from a pronunciation
  lexicon or rule-based G2P).
- **`A_PRIME_SA`** — Sanskrit / IAST-transliteration **phoneme normalizer** (diacritics → canonical phonemes;
  aspiration and retroflex/dental distinctions preserved).

They **may share** the same articulatory feature schema and generator set (so operators are comparable), but
**must not share** normalization rules (English orthography ≠ IAST). A run uses **one** track; cross-track
mixing requires its own pre-registration. No track is privileged (no Sanskrit privilege): `A_PRIME_SA` is an
engineering normalizer, not a claim of special status.

---

## 7. Allowed inputs

Stage A′ may consume **only phonological/articulatory information**:

- phoneme inventory (identity of the phoneme),
- **place** of articulation,
- **manner** of articulation,
- **voicing**,
- **sonority**,
- **vowel height**,
- **vowel backness**,
- **vowel rounding**,
- **vowel length** (if needed),
- **aspiration** (if needed),
- **stress / prosody** — only if **separately justified** and pre-registered (default: excluded).

All features are properties of **sounds**, fixed before any run.

---

## 8. Forbidden inputs

Stage A′ may **never** consume:

- dictionary meaning,
- semantic categories,
- varṇa glosses,
- vṛtti meanings,
- four-sphere labels,
- polarity meanings,
- KCPR poles,
- the target `Y`,
- attribute tables,
- any **post-hoc additions based on test performance** (feature/inventory changes chosen after seeing
  results).

If any forbidden input touches the operator construction, the layer is invalid (`STAGE_A_PRIME_SEMANTIC_LEAKAGE_RISK`
→ blocked).

---

## 9. Phoneme inventory proposal (design only — NOT frozen)

A candidate inventory broad enough to cover English and Sanskrit/IAST faithfully (illustrative, to be fixed at
pre-registration):

- **Consonants:** stops (voiceless/voiced, with **aspirated** counterparts for Sanskrit: p pʰ b bʰ, t tʰ d dʰ,
  k kʰ g gʰ, and **retroflex** ṭ ṭʰ ḍ ḍʰ, **dental** vs **alveolar** where distinguished); affricates (t͡ʃ d͡ʒ,
  c cʰ j jʰ); fricatives (f v θ ð s z ʃ ʒ h; Sanskrit ś ṣ s h); nasals (m n ɳ ŋ ñ); liquids (l r ɭ);
  glides (j w/v).
- **Vowels:** i ɪ e ɛ æ a ɑ ɔ o ʊ u ə, with **length** (aː iː uː) for Sanskrit.
- **Diphthongs:** aɪ aʊ ɔɪ oʊ eɪ (English); e o ai au (Sanskrit e/o are long, ai/au diphthongs).
- **Distinctions used:** **aspiration** (Sanskrit), **retroflex/dental** (Sanskrit), vowel **length**.

This is **design only**, explicitly **not frozen**; the exact inventory, IPA choices, and merges are fixed at
pre-registration, not here.

---

## 10. Feature vector f_σ

Candidate feature dimensions (fixed, normalized to a bounded range, e.g. [−1, 1]):

- **Shared / consonant-relevant:** place_frontness (labial→velar/glottal), manner_openness
  (stop→fricative→approximant→vowel), voicing, sonority, aspiration, nasality, retroflexion.
- **Vowel-relevant:** height, backness, rounding, length.

Two representation options (to be chosen at pre-registration):

- **Single shared space** — one feature vector schema for all phonemes, with vowel-only dims set to a neutral
  value for consonants and consonant-only dims neutral for vowels (keeps operators comparable and generators
  shared).
- **Separate blocks** — a consonant block and a vowel block concatenated, with cross-block dims zeroed
  (cleaner semantics per class, more dimensions).

Preference for a **single shared space** to keep the generator algebra small and comparable to frozen Stage A;
the choice is pre-registered, not decided here.

---

## 11. Operator construction

The structural principle is **preserved exactly**:

```
M_σ = expm( Σ_j f_{σ,j} · G_j )
```

Generator options (to be pre-registered; **compared**, not assumed):

- **Reuse frozen Stage A generators** — the same skew-symmetric `G_A..G_D` (orthogonal `M_σ`), if the feature
  dimensionality is kept at k=4 (a reduced projection of the richer feature set). Maximally comparable to frozen
  Stage A.
- **Expand / version the generators** — a larger skew-symmetric generator set matched to a higher feature
  dimensionality (e.g. k = 6–10), a **new versioned** algebra with its own structural gates.
- **Compare alternatives** — run the reduced-reuse and expanded variants as pre-registered alternatives and
  report both.

**Orthogonality sanity checks are required** whenever skew-symmetric generators are used: verify `G_j = −G_jᵀ`
and `M_σ M_σᵀ = I` (norm-preserving), exactly as frozen Stage A asserts. Non-orthogonal generator choices, if
ever considered, must be separately justified and their norm behavior bounded.

---

## 12. Coverage targets (required before B1.4b can be unblocked)

Stage A′ must meet **all** of, on the candidate pools, before B1.4b's L1 block can be lifted:

- **≥ 95% character/phoneme retention** — near-zero dropping after G2P/normalization.
- **≥ 90% fully decomposable words** — the large majority of candidate words decompose with no unsupported
  units.
- **≥ 100 fully decomposable concepts overlapping an independent `Y`** — the faithful concept set that also has
  norm coverage clears the pre-registered floor.
- **No silent fallback** — every unsupported phoneme/character is reported, never coerced.
- **Unsupported units explicitly reported** — a per-run coverage log of any drops.

Failing any target → `STAGE_A_PRIME_BLOCKED` (coverage insufficient); B1.4b stays blocked at L1.

---

## 13. Validation tests for Stage A′ (non-semantic only)

Stage A′ is validated by **structural/engineering** tests **only** — no semantic validation:

- **Decomposition determinism** — same word → same phoneme sequence, every time.
- **Phoneme coverage** — fraction of words/characters mapped; unsupported inventory reported.
- **Round-trip / retention** — phoneme sequence accounts for (near) all of the input; retention metric.
- **Unsupported-unit reporting** — every drop surfaced with a warning; no silent coercion.
- **Operator construction** — `M_σ` builds for every inventory phoneme without error.
- **Orthogonality** — `M_σ M_σᵀ = I` (skew generators); numerical tolerance checked.
- **Reproducibility** — fixed seeds / deterministic G2P; identical outputs across runs.
- **Semantic-leakage audit** — static + provenance check that **no** forbidden input (§8) enters the feature
  chart or generators.

None of these tests touch meaning; passing them says the layer is a faithful, deterministic **phonological**
front end — nothing more.

---

## 14. Relation to B1.4b

- Stage A′ **only unblocks L1 coverage** if it passes §12/§13; it **does not validate meaning** and grants no
  semantic claim.
- B1.4b would require a **new version** (e.g. B1.4b′) that explicitly uses Stage A′ as L1 — **not** a silent
  substitution into the existing B1.4b artifacts (which stay as-is).
- The F-3 reversal-symmetry limitation (recorded in `7fd7b6e` / `0e2a346`) is **inherited** and must be carried
  into any Stage A′-based pre-registration; an oriented extension still needs separate pre-registration.

---

## 15. Baseline consequences

Because Stage A′ is **explicitly phonology-derived** (its operators are functions of articulatory features),
the **phonological baseline remains the decisive control — and likely becomes stronger**, since a richer,
faithful phoneme layer gives the plain-phonological predictor *more* signal too. Any later semantic/attribute
claim from an F-over-Stage-A′ latent must still **beat plain phonology** and the order baselines by the
pre-registered margin. Expanding coverage **raises** the phonology bar; it does not lower it. The expected
prior is unchanged: a faithful phonology front end makes `F_COLLAPSES_TO_PHONOLOGY → ⊥` *more* likely to be the
honest verdict, not less.

---

## 16. Risk analysis

- **Increased degrees of freedom** — a larger inventory + feature schema + generator choice adds researcher DoF;
  mitigated only by freezing everything at pre-registration and comparing pre-declared alternatives.
- **Language-specific normalization bias** — English vs Sanskrit G2P choices can shape results; tracks must be
  reported separately and never silently pooled.
- **Phonology-only ceiling** — Stage A′ is still bounded by phonology; it cannot manufacture semantic signal,
  only cover more words.
- **Overfitting to candidate word pools** — tuning the inventory to the repo-local pools; mitigated by fixing
  the inventory from linguistic standards, not from the test words.
- **Cross-language inconsistency** — a phoneme shared by both tracks may be normalized differently; the shared
  feature schema must be identical even where normalization rules differ.
- **Better engineering substrate without semantic signal** — the real risk: Stage A′ may succeed *as
  engineering* (great coverage) while B1.4b still returns `⊥`. That is an acceptable, expected outcome — a
  faithful substrate that honestly reports no semantic signal is a success of the substrate, not a failure to
  be rescued.

---

## 17. Terminal labels

- **`STAGE_A_PRIME_PHONEME_DESIGN_READY`** — the design (pipeline, tracks, inventory sketch, features,
  operators) is specified and internally consistent.
- **`STAGE_A_PRIME_COVERAGE_TARGETS_DEFINED`** — the §12 coverage targets are fixed as the unblock criteria.
- **`STAGE_A_PRIME_REQUIRES_PREREG`** — implementation must not begin until a Stage A′ pre-registration is
  approved.
- **`STAGE_A_PRIME_TOO_MANY_DEGREES_OF_FREEDOM`** — (guard) if the design cannot be constrained enough to avoid
  DoF abuse.
- **`STAGE_A_PRIME_SEMANTIC_LEAKAGE_RISK`** — (guard) if any forbidden input risks entering the layer.
- **`STAGE_A_PRIME_BLOCKED`** — (guard) coverage targets cannot be met / design not viable.
- **`STAGE_A_PRIME_INCONCLUSIVE`** — (guard) the design question cannot be resolved as specified.

**This memo emits:** `STAGE_A_PRIME_PHONEME_DESIGN_READY` + `STAGE_A_PRIME_COVERAGE_TARGETS_DEFINED` +
`STAGE_A_PRIME_REQUIRES_PREREG`. The DoF and leakage risks are **flagged** (§16/§8) as pre-registration
must-solves, not yet triggered.

---

## 18. Recommended next gate

The next step is a **Stage A′ pre-registration for coverage-only validation** — freezing the phoneme inventory,
feature schema, generator choice(s), G2P/normalization rules, coverage targets (§12), and the non-semantic test
suite (§13) — **not** implementation. Only after that pre-registration is approved, and the coverage-only tests
pass on the candidate pools, would a **new** B1.4b′ study (using Stage A′ as L1) be considered — under its own
separate authorization. No implementation, dataset, or run is authorized here.

---

## 19. Boundary statement

> Stage A′ phoneme/G2P operator-layer design completed. Frozen Stage A untouched. No meaning validated. No
> dataset built. Nothing run or scored. B1.4b remains blocked. Track B remains blocked. Structure, not
> validated meaning.
