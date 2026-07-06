# B1.2 Varṇa Mapping — Provenance (reused from B1.1, byte-identical)

B1.2 reuses the **same** varṇa mapping as B1.1 (per the existing-V-function audit: *reuse, do not design a
new function*). These are **byte-identical copies** of the B1.1 frozen artifacts, placed here so the B1.2
mapping is self-contained and self-verifying. The B1.1 originals are **unchanged** and remain hash-bound in
`b1_1_freeze_manifest.json`.

## Files copied into this folder

| B1.2 copy | source (B1.1, unchanged) | sha256 | role |
|---|---|---|---|
| `b1_2_varna_source_lexicon.json` | `../b1_1_experimental_contrastive_lexicon_draft.json` | `e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7` | **the authoritative varṇa mapping used in B1.1** — human-authored source lexicon (binding/liberating poles; the `artha` leak fix is included) |
| `b1_2_varna_bridge_pool.json` | `../b1_1_bridge_pool_draft.json` | `1ce2ae14b563621ac495381e8397796e6791aba740978bb817544935c6ba8c15` | the bridge pool **derived** from that lexicon (34 varṇas × 2 poles = 68 phrases); this is what `core_A` / `V(word)` composes from |

## Reused rule/config/data artifacts (added by the rule-artifact copy audit)

Byte-identical copies of the small B1.1 config/data files that define **how** the mapping is used by `V(word)`
(see `B1_2_RULE_ARTIFACT_COPY_AUDIT.md`). Source code (`varna_lens.py`, `run_b1_1_generation.py`,
`b1_real_conditioning.py`) is **referenced by commit/path/function + hash**, not copied.

| B1.2 copy | source (B1.1, unchanged) | sha256 | supplies |
|---|---|---|---|
| `b1_2_arm_construction_config.reused_from_b1_1.json` | `../b1_1_arm_construction_config.json` | `167343c28fe15dc88c2b4aa87c03b7a9e0291a09b0f5f6b45a292b99e9769a11` | composition policy (G1), separator, pole-rule text |
| `b1_2_seeds_config.reused_from_b1_1.json` | `../b1_1_seeds_config.json` | `1c044278ff1ee064c35d1ebacfa0ef5b7fea4cc782d020654ee15200c07730c0` | V_scrambled/V_deranged/V_random seeds |
| `b1_2_eval_dtable.reused_from_b1_1.json` | `../b1_eval_dtable.json` | `958df144c5e0302ba8a15d158b42fe1a251d842bf227e8805b2a8fb508c61434` | core_D / V_removed dictionary table |
| `b1_2_eval_wordlist.reused_from_b1_1.json` | `../b1_eval_wordlist.json` | `9c2728b9c4ba6887cb87212f7c6a4702b52477d2ec0f1a872aef0c196cb14020` | core_D word list |

## Source → derived relationship

- `b1_2_varna_source_lexicon.json` is the **source of truth** (the varṇa→meaning lexicon).
- `b1_2_varna_bridge_pool.json` is **rendered from** it; its internal field
  `source_lexicon_sha256 = e8aeb105…` equals the lexicon's hash above, so the pair is internally consistent
  and remains so in this copy.
- The B1.2 prediction `V(word)` (audit: `ArmBuilder.core_A`) consumes the **bridge pool**; the bridge pool
  derives from the **lexicon**. Copying both keeps that chain verifiable without reaching back into B1.1.

## Integrity statements

- **Byte-identical:** each copy's sha256 equals the B1.1 frozen artifact's sha256 (verified above).
- **Originals untouched:** no B1.1 artifact was modified, moved, or re-frozen; the B1.1 freeze manifest is
  unchanged.
- **Not yet a B1.2 freeze:** these copies are staged material for reuse. They are **not** authorized or
  frozen for B1.2 — the actual B1.2 freeze (binding the mapping + `G(word)` builder + configs under a new
  manifest) happens at the `B1_2_V_FUNCTION_BINDING_SPEC` gate. Nothing here authorizes generation, judging,
  or scoring.
- **No rescue / no new claims:** B1.1 verdict remains `RANDOM_OR_SCRAMBLED_MATCHES`; Track B remains BLOCKED;
  Track G / Track F negatives preserved; no ontology validation, Sanskrit privilege, or semantic-truth claim.

**Structure, not validated meaning.**
