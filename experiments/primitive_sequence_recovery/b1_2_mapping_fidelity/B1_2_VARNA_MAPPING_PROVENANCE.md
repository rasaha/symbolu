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
