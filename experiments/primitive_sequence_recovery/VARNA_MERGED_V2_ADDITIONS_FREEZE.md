# Varṇa Merged Lexicon v2 — Additions-Only Refreeze

Fills the **four previously-empty vocalic rows** (ṛ, ṝ, ḷ, ḹ) so the varṇa inventory is complete. **Additions
only** — no existing mapping was modified, and the 33-consonant confirmatory backbone is **byte-identical** to v1.
`DEVELOPMENT_ONLY` additions (the new rows are a resonance layer; the confirmatory backbone is unchanged).

## Files & hashes

| File | SHA-256 | Status |
|---|---|---|
| `frozen/varna_native_stage1_merged_v1.json` | `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96` | retained (still valid for every artifact that pins it) |
| `frozen/varna_native_stage1_merged_v2.json` | `e7dd98c82f32ace7791cf62a0c14e35d33fed920a28543192540be7f214a4a9a` | **new complete version (supersedes v1)** |

v1 is **not** deleted or mutated, so its pinned hash stays valid; v2 is the new superset.

## What changed (exactly four rows)

Programmatically verified: v1 vs v2 differ in **only** these four rows; all other 47 rows (incl. all 33
consonants) are identical.

| Unit | Liberating (core) | Binding (shadow) | Source |
|---|---|---|---|
| **ṛ** (ऋ) | freedom / liberation — the unbound, self-established state | rootlessness / escapism | resonance (*ṛta, ṛṣi, ṛddhi*) |
| **ṝ** (ॠ) | totality / oṃ (praṇava) | dissolution / self-loss | Sarkar (oṃ) |
| **ḷ** (ऌ, `l̥`) | arrangement / formation (√kḷp) | rigid contrivance / over-fitting | corpus (√kḷp) |
| **ḹ** (ॡ, `l̥̄`) | explosion / breakthrough (phaṭ) | destructive outburst / rashness | Sarkar (phaṭ) |

All four are `activation_scope=DEVELOPMENT_ONLY`, provenance `AUTHORED_PROVISIONAL`, `source_artifact =
varna_vocalic_resonance_tags.json`.

## Key note carried into the data

The `ṛ` row records: **ṛ (ऋ) ≠ Ra (र)**. Ra = annihilation (*sarvanāśa*); ṛ carries no such affliction — its
resonance is **freedom**. Ra's affliction is not inherited onto ṛ.

## Integrity guarantees

- **No existing mapping modified** (`no_existing_mapping_modified: true` in the v2 `supersedes` block).
- **Consonant backbone byte-identical** → `consonant_pole_content_hash` unchanged; any consonant-only study
  (incl. the feature-lift study, which is consonant-only) is computationally unaffected.
- **ś/ṣ untouched.** The separately-flagged ś/ṣ swap (`VARNA_PRIMARY_SOURCE_RECONCILIATION_AUDIT.md`) is **not**
  addressed here — this refreeze is additions-only and does not change any consonant.

## Adoption (optional follow-up)

Artifacts currently pin v1 by hash. Because the only delta is four development-only vowel rows, nothing
consonant-based changes if they keep pinning v1. To make v2 the operative file for B1.12 / future runs, repoint
those references from v1 to v2 (`…merged_v2.json`, `e7dd98c8…`) — a separate, mechanical step, done only when
desired.

## Guardrails
Additions-only versioned refreeze. v1 retained; no existing mapping or consonant row modified; ś/ṣ swap not
touched. New vowel rows are a development-only resonance layer. Structure, not validated meaning.
