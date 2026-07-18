# B1.2 Existing V(word) Function Audit

## 0. Scope

Audits whether prior-track Symbol-U / varṇa machinery **already** provides the mechanical `V(word)`
prediction B1.2 needs, so that B1.2 **reuses** existing code rather than inventing a new function. Audit only:
no new V designed here, no implementation, no models, no scoring, no B1.1 artifact modified, no rescue of
B1.1, no verdict change. B1.1 stays `RANDOM_OR_SCRAMBLED_MATCHES`; Track B stays BLOCKED; no ontology /
Sanskrit / semantic-truth claim. **Structure, not validated meaning.**

Reminder of the requirement: **G(word)** = dictionary-derived differential answer key; **V(word)** =
varṇa-derived prediction. This audit concerns **V only** (G is a separate, not-yet-built lexical artifact).

## 1. Existing V artifacts found

The full varṇa→prediction pipeline exists and is exercised by the committed B1.1 runner.

| layer | artifact | role |
|---|---|---|
| word → varṇa skeleton | `varna_lens/varna_lens.py` → `phonemes_cmudict(word)` | G2P (cmudict/ARPABET) → phoneme/varṇa sequence |
| varṇa gloss table | `experiments/.../b1_1_bridge_pool_draft.json` (FROZEN) | per-varṇa binding/liberating gloss text (68 phrases) |
| lexicon / pole source | `experiments/.../b1_1_experimental_contrastive_lexicon_draft.json` (FROZEN); `varna_lens/lexicon_authoritative_varna.json` | consonant binding/liberating poles, vowel bridges |
| pole-selection rule | `varna_lens.py` → `read_op` / `ArmBuilder.varna_poles` | phonology-determined pole per varṇa, **zero free choices** |
| composition grammar | `ArmBuilder._compose` + `b1_1_arm_construction_config.json` (FROZEN, gap G1 pinned) | separator-joined gloss composition |
| prediction + ablations | `run_b1_1_generation.py` → `ArmBuilder.core_A / core_S / core_R_deranged / core_R_same / core_D` | V_real and its ablations (see §7) |
| seeds | `b1_1_seeds_config.json` (FROZEN) | arm/scramble/derangement seeds |
| freeze binding | `b1_1_freeze_manifest.json` — **12 bound artifacts**, sha256-pinned | binds lexicon, bridge pool, arm/seed/gen configs |

## 2. Exact V pipeline

`V_real(word)` = `ArmBuilder.core_A(word)`:

1. `V.phonemes_cmudict(word)` → phoneme/varṇa skeleton (G2P; word in → varṇa list out).
2. For each **consonant** varṇa, assign a pole by the phonology-determined `read_op` rule — **no free
   choices**: word's first consonant → binding (worldly seed); a vowel immediately follows (onset/CV) →
   liberating; bare (coda / pre-consonant / final) → binding; doubled consonant → 1st liberating, 2nd
   binding.
3. Look up each `(varṇa_key, pole)` in the **frozen** bridge pool and **compose** the gloss strings with the
   frozen separator (arm-construction config, gap G1).

- **Inputs:** the target word only.
- **Outputs:** the composed bridge text + metadata (`varna_sequence`, `n_varnas`, warnings).
- No randomness in `core_A`; fully deterministic given the frozen pool + rule.

## 3. Is it mechanical?

**Yes.** Every step is a fixed algorithm: G2P lookup → deterministic pole rule (explicitly "zero free
choices") → table lookup → deterministic composition. No human writes anything per word. The ablations that
need randomness (scramble, derangement, same-pool) draw from **frozen seeds**, so they are reproducible, not
hand-set.

## 4. Is it word-agnostic?

**Yes.** `core_A` (and every other `core_*`) is a single function applied identically to every word. There
are no per-word branches, no bespoke signatures, no curated exceptions. (The lexicon has manual roman
overrides for a few ambiguous spellings, but English words route through G2P uniformly.)

## 5. Does it use dictionary input?

**No — for the varṇa prediction.** `core_A` / `core_S` / `core_R_deranged` read **only** the phoneme
skeleton and the frozen varṇa gloss table. They never consult a dictionary definition, a synonym set, or any
`G(word)` answer key. Human meaning enters **once**, frozen, at the gloss-table (ontology) level — never
per-word, never from the answer key. This is exactly the clean provenance B1.2 requires: V and G would be
built by **independent** pipelines.

*(The one intentionally dictionary-based core is `core_D`, which is the dictionary-only ablation itself —
see §7.)*

## 6. Frozen / hash-bound?

**Yes, for the varṇa path.** `b1_1_freeze_manifest.json` sha256-pins 12 artifacts including the bridge pool,
the contrastive lexicon, and the arm/seed/generation configs; the runner re-verifies every hash and aborts
`INVALID_POSTHOC` on any mismatch. **Exception:** the dictionary D-table used by `core_D`
(`b1_real_conditioning.py` + `b1_eval_dtable.json`) is tracked in `referenced_source_hashes` but flagged in
code as "committed, **NOT frozen**." For B1.2 it must be pinned into a **new B1.2 freeze** (§9).

## 7. Ablation support — V_real / V_scrambled / V_deranged / V_removed

All four B1.2 prediction-ablation variants already exist as `ArmBuilder` methods:

| B1.2 ablation | existing method | mechanism | seed |
|---|---|---|---|
| **V_real** | `core_A(word)` | real G2P→varṇa→pole→frozen-pool composition | (deterministic) |
| **V_scrambled** | `core_S(word)` | the word's own varṇa bridges, **seeded order scramble** (forces a real order-derangement) | `arm_construction_seed` |
| **V_deranged** | `core_R_deranged(word)` | seeded derangement π (π(w)≠w); word receives **another word's real `core_A`** | `r_deranged_assignment_seed` |
| **V_removed / dictionary-only** | `core_D(word)` | dictionary sense + synonyms table (no varṇa) — the §12a ceiling/probe; also a bare no-varṇa/neutral core is trivially available (`core_X`) | (table) |
| **V_random** *(optional)* | `core_R_same(word,n)` | seeded random same-pool bridges **excluding the word's own varṇas** | `r_same_sample_seed` |

So the mechanism axis (Axis 2) is fully constructible from existing code. The `read_op` rule can be scrambled
(core_S) and deranged (core_R_deranged) **by rule**, satisfying the §22 requirement that the ablations be
mechanically specifiable.

## 8. Sufficiency assessment

**Provenance cleanliness:** ✓ V_real/S/deranged are varṇa-only; no per-word authoring; no `G` leakage; same
function for all words; frozen gloss table.

**Two-axis compatibility:** ✓ the prediction side (V and its ablations) is complete. Note a **role
clarification** (not a deficiency): in the B1.1 code `core_R_same` / `core_R_domain` were *prediction-side*
conditioning arms, but in B1.2's two-axis frame **R_same / R_domain are Axis-1 answer-key (G-side)
distractors**. The V-side ablation set is therefore `core_A / core_S / core_R_deranged / core_D`
(+ optional `core_R_same` as V_random). Reassigning R_same/R_domain to the G side is a binding-spec labeling
task, not a change to the V function.

**Residual binding tasks (belong in the binding spec, not new V logic):**

1. **Format-matching.** `core_A` emits *generation-conditioning bridge prose* (built to prompt an LLM), not a
   compact signature pre-formatted for alignment against a dictionary differential `G`. The binding spec must
   pin how V's output is rendered comparable to G (length/register/format matching), without changing the
   underlying derivation.
2. **Freeze the dictionary-only ablation.** `core_D`'s D-table is committed-not-frozen; pin it into the new
   B1.2 freeze so V_removed is reproducible.
3. **New B1.2 manifest.** B1.2 must bind these existing artifacts under its **own** freeze (the B1.1 manifest
   must not be reused as authorization); the B1.1 hashes carry over as provenance, not as a B1.2 grant.

None of these require **designing a new V function**. They are exactly the pinning/labeling work the
"if sufficient → binding spec" path is for.

## 9. Decision

```
STATUS: EXISTING_V_FUNCTION_SUFFICIENT
```

The mechanical, word-agnostic, varṇa-only `V(word)` and all four required ablations already exist in the
committed/frozen B1.1 machinery (`varna_lens.py` + `ArmBuilder.core_A/S/R_deranged/D`, bound by
`b1_1_freeze_manifest.json`). **Reuse it; do not design a new function.** The remaining work is a
**B1.2 V-function binding spec** that (a) pins these artifacts into a new B1.2 freeze, (b) format-matches V's
output to G, (c) fixes the R_same/R_domain role assignment, and (d) freezes the dictionary-only ablation.

This decision concerns **V only**. B1.2 still requires the separate `G(word)` dictionary-differential builder
(not audited here) and the two prereg/freeze gates before anything runs.

## 10. Final status block

```
document:                   B1.2 existing-V-function AUDIT (audit only; nothing built/run)
V(word) exists mechanically: YES (varna_lens.phonemes_cmudict + ArmBuilder.core_A)
mechanical:                 YES (zero free choices in the pole rule)
word-agnostic:              YES (one function, all words)
uses dictionary input:      NO (varṇa-only for V_real/S/deranged; core_D is the intended dict-only ablation)
V_real:                     core_A            ✓
V_scrambled:                core_S            ✓ (seeded)
V_deranged:                 core_R_deranged   ✓ (seeded π, π(w)≠w)
V_removed/dictionary-only:  core_D (+core_X)  ✓ (must be frozen for B1.2)
V_random (optional):        core_R_same       ✓ (seeded)
frozen/hash-bound:          YES for varṇa path (12 artifacts); core_D D-table committed-not-frozen
SUFFICIENCY:                EXISTING_V_FUNCTION_SUFFICIENT
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
only allowed positive:      MAPPING_FIDELITY_SIGNAL
ontology / Sanskrit / truth: NONE
next gate:                  B1_2_V_FUNCTION_BINDING_SPEC
```

**Structure, not validated meaning.** The varṇa prediction function already exists mechanically and is
sufficient for B1.2; reuse it under a new binding spec and a new freeze. The B1.1 verdict stands, no result
is rescued, and Track B remains BLOCKED.
