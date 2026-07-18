# B1.2 V(word) Function Binding Spec

## 0. Scope

Binds the **existing** B1.1 varṇa machinery into B1.2 as the `V(word)` prediction pipeline. Per the completed
audit (`B1_2_EXISTING_V_FUNCTION_AUDIT.md` → **`EXISTING_V_FUNCTION_SUFFICIENT`**), **no V feasibility is
re-audited here and no new V logic is designed** — this document only pins which existing files, functions,
configs, and hashes constitute V, and how each ablation maps to an existing `ArmBuilder` method. Binding only:
no implementation, no models, no scoring, no B1.1 artifact modified, no rescue, no verdict change.

**Two pipelines, kept independent:**

- **V** = the **varṇa-derived prediction** pipeline (phoneme skeleton → frozen gloss table → composition).
- **G** = the **dictionary-derived answer-key** pipeline (target + ≥10 synonyms → shared-feature subtraction).
- **V and G must remain fully independent until alignment scoring** — V never reads a dictionary definition
  or any `G(word)`; G never reads varṇa. This non-circularity is the whole basis of the test.

**Structure, not validated meaning.**

## 1. Ablation → existing function binding

| B1.2 role | existing function | file | notes |
|---|---|---|---|
| **V_real** | `ArmBuilder.core_A` | `run_b1_1_generation.py` | real G2P→varṇa→pole→frozen-pool composition; deterministic |
| **V_scrambled** | `ArmBuilder.core_S` | `run_b1_1_generation.py` | word's own varṇa bridges, seeded order scramble (forces real order-derangement) |
| **V_deranged** | `ArmBuilder.core_R_deranged` | `run_b1_1_generation.py` | seeded derangement π (π(w)≠w); word gets another word's real `core_A` |
| **V_removed / dictionary-only** | `ArmBuilder.core_D` (+ `core_X` bare/no-varṇa) | `run_b1_1_generation.py` → `b1_real_conditioning.py` | §12a ceiling + mechanism probe; dictionary table, **must be frozen for B1.2** (§4) |
| **V_random** *(optional)* | `ArmBuilder.core_R_same` | `run_b1_1_generation.py` | seeded random same-pool bridges excluding the word's own varṇas |

**No new V logic is introduced.** Each B1.2 ablation is exactly one existing method, invoked unchanged.

## 2. Exact source files, functions, configs

**Code (committed; not frozen artifacts — pinned by referenced hash):**

- `varna_lens/varna_lens.py` — `phonemes_cmudict(word)` (G2P→varṇa skeleton), `read_op` (pole rule, zero
  free choices).
- `experiments/primitive_sequence_recovery/run_b1_1_generation.py` — `ArmBuilder.core_A / core_S /
  core_R_deranged / core_R_same / core_D / core_X`, `varna_poles`, `_compose`, `_build_derangement`.
- `experiments/primitive_sequence_recovery/b1_real_conditioning.py` — `_core_D` (dictionary sense + synonyms
  table) backing V_removed.

**Frozen data artifacts (sha256, from `b1_1_freeze_manifest.json`), reused byte-identically in this folder:**

| artifact | B1.1 source | B1.2 copy (this folder) | sha256 |
|---|---|---|---|
| varṇa source lexicon | `../b1_1_experimental_contrastive_lexicon_draft.json` | `b1_2_varna_source_lexicon.json` | `e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7` |
| bridge pool (varṇa→gloss) | `../b1_1_bridge_pool_draft.json` | `b1_2_varna_bridge_pool.json` | `1ce2ae14b563621ac495381e8397796e6791aba740978bb817544935c6ba8c15` |

**Config artifacts to bind (B1.1 sha256; to be re-pinned under the new B1.2 freeze):**

| config | path | sha256 | supplies |
|---|---|---|---|
| arm-construction (composition policy G1) | `../b1_1_arm_construction_config.json` | `167343c28fe15dc88c2b4aa87c03b7a9e0291a09b0f5f6b45a292b99e9769a11` | pole rule, separator, no-cap |
| seeds | `../b1_1_seeds_config.json` | `1c044278ff1ee064c35d1ebacfa0ef5b7fea4cc782d020654ee15200c07730c0` | ablation seeds (below) |

**Bound seeds (from `b1_1_seeds_config.json`):**

- `arm_construction_seed = 70101` → V_scrambled order scramble
- `r_deranged_assignment_seed = 70307` → V_deranged derangement π
- `r_same_sample_seed = 70211` → V_random same-pool sample

**Composition policy (V_real, from the arm-construction config):** G2P source =
`varna_lens.phonemes_cmudict` (routing only, **not** a meaning source); meaning source = the bridge pool's
`binding_bridge` / `liberating_bridge` **only** (derived from the source lexicon), **never** the varna_lens
meaning lexicon; consonants only; pole rule = vowel-attachment (`read_op`): word-first consonant → binding;
onset (vowel follows) → liberating; bare/coda → binding; doubled 1st → liberating, 2nd → binding.

## 3. Independence guarantee (V ⟂ G)

- V (`core_A/S/R_deranged/R_same`) reads **only** the phoneme skeleton + the frozen bridge pool. It never
  consults a dictionary definition, a synonym set, or any `G(word)`.
- The one dictionary-based binding, **V_removed / `core_D`**, is *intentionally* dictionary-derived — it is
  the ceiling/mechanism probe, not part of the varṇa prediction, and it must not feed `V_real`.
- G(word) is built by a **separate** lexical pipeline (not specified here; see the prereg §10). V and G are
  computed independently and only meet at the alignment-scoring step.
- Consequence: "does V(target) align with G(target)" is a genuine, non-circular test — neither pipeline can
  see the other's output.

## 4. Residual binding tasks closed / carried to the freeze

1. **Format-matching (carried to freeze/build).** `core_A` emits generation-conditioning bridge prose. For
   alignment against G it must be rendered to a compact, length/register/format-matched signature. This is a
   **rendering wrapper over unchanged V output** — no change to the derivation. Pinned as a freeze-time task.
2. **Freeze the dictionary-only ablation.** `core_D`'s D-table (`b1_real_conditioning.py` +
   `b1_eval_dtable.json`) is committed-not-frozen; it **must** be pinned into the new B1.2 manifest so
   V_removed is reproducible.
3. **Role reassignment.** In B1.1 code, `core_R_same` / `core_R_domain` were *prediction-side* arms; in B1.2
   `R_same` / `R_domain` are **Axis-1 answer-key (G-side) distractors**. The V-side ablation set is therefore
   `core_A / core_S / core_R_deranged / core_D` (+ optional `core_R_same` as V_random). Labeling only.
4. **New B1.2 manifest.** All artifacts above are bound under a **new** B1.2 freeze; the B1.1 manifest is
   **provenance, not authorization**. B1.1 hashes carry over as identity checks, not as a B1.2 grant.

## 5. What this spec does and does not authorize

- **Does:** fix, by reference and hash, which existing files/functions/configs/seeds constitute `V(word)` and
  its ablations for B1.2, reusing them unchanged.
- **Does NOT:** design new V logic; build `G(word)`; format-render, run, judge, or score anything; create the
  B1.2 freeze; authorize generation.

**B1.2 is not authorized to run until a new freeze** binds V (this spec) + `G(word)` + tiering + configs, and
the prereg-review gate passes.

## 6. Final status block

```
document:                   B1.2 V-function BINDING SPEC (binding only; nothing built/run)
audit result used:          EXISTING_V_FUNCTION_SUFFICIENT (no re-audit, no new V logic)
V_real:                     ArmBuilder.core_A
V_scrambled:                ArmBuilder.core_S            (seed 70101)
V_deranged:                 ArmBuilder.core_R_deranged   (seed 70307)
V_removed/dictionary-only:  ArmBuilder.core_D (+core_X)  (D-table to be frozen for B1.2)
V_random (optional):        ArmBuilder.core_R_same       (seed 70211)
varṇa source lexicon:       b1_2_varna_source_lexicon.json  (e8aeb105…, byte-identical to B1.1)
bridge pool:                b1_2_varna_bridge_pool.json     (1ce2ae14…, byte-identical to B1.1)
V ⟂ G independence:         REQUIRED until alignment scoring
new V logic:                NONE
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
only allowed positive:      MAPPING_FIDELITY_SIGNAL
ontology / Sanskrit / truth: NONE
authorized to run:          NO — requires new B1.2 freeze + prereg review
next gate:                  B1_2_G_FUNCTION_SPEC (dictionary-differential answer-key builder), then freeze
```

**Structure, not validated meaning.** The varṇa prediction pipeline is bound from existing, hash-verified
B1.1 machinery with no new logic; V and G remain independent; the B1.1 verdict stands, Track B remains
BLOCKED, and B1.2 cannot run until a new freeze.
