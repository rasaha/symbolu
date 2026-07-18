# Varṇa Merged Lexicon v3 — ś/ṣ Sibilant-Swap Correction

Corrects the **ś/ṣ swap** data error to match the primary source. This changes the confirmatory consonant
backbone (unlike the v2 vowel additions), so it is a **correction**, not additions-only. Built on v2.

## Files & hashes

| File | SHA-256 | Status |
|---|---|---|
| `…merged_v1.json` | `af4c1f54…` | original (retained) |
| `…merged_v2.json` | `e7dd98c8…` | + 4 vowel additions (retained) |
| `…merged_v3.json` | `65116f371aca9f24ba2cce080c458a7a878f9af4ae50562d3f518567e681d33f` | **+ ś/ṣ correction (new current)** |

## The correction

Per the primary source (P.R. Sarkar, *"The Acoustic Roots of the Indo-Aryan Alphabet"*):
**Sha (ś) = rajoguṇa + artha**, **S'a (ṣ) = tamoguṇa + kāma**. The lexicon had them **inverted**. v3 swaps the
pole content back:

| Unit | v1/v2 (wrong) | v3 (corrected, primary source) |
|---|---|---|
| **ś** (श) | kāma / tamasic | **artha as possessive acquisition — rajasic grasping to acquire** |
| **ṣ** (ष) | artha / rajasic | **kāma — worldly/physical desire; the tamasic pull toward the crude** |

The atomic identities (unit, devanāgarī, IAST, aliases) stay fixed; only the **pole content + its provenance**
moved between the two rows, and both rows are re-sourced to the primary-source reconciliation
(`source_key`: ś=`sha`, ṣ=`s'a`).

## Verification

- v2 → v3 differ in **exactly two rows** (ś, ṣ); all other 49 rows identical.
- ś binding now contains *artha/rajasic*; ṣ binding now contains *kāma/tamasic*.
- The four v2 vowel additions (ṛ, ṝ, ḷ, ḹ) are retained unchanged.
- `consonant_pole_content_hash` recomputed (recipe recorded in-file);
  `consonant_pole_content_hash_matches_v31 = false` — v3 intentionally diverges from v3.1, which carries the swap.

## Provenance of the error (for the record)

The swap entered when `b1_2_varna_classical_verifications.json` mis-decoded Sarkar's romanization — reading "sha"
(palatal ś) as if it were IAST retroflex ṣ — and "corrected" the originally-correct source lexicon. It propagated
into v3.1 → the merged lexicon. v3 reverses it to the primary text. This **supersedes** the earlier
`VARNA_SHA_SWAP_PROVENANCE_AUDIT.md` verdict (`SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR`), which was wrong.

## Impact & adoption

- **Feature-lift dataset:** the 88-word set pins v1 and is unrun (no embeddings computed). Words containing ś or
  ṣ would now receive the corrected glosses. To run on corrected mappings, repoint the feature-lift extraction to
  v3 (`65116f37…`) — recommended, and harmless since nothing has been computed yet.
- **B1.12 / other consonant work:** still pins v1/v2 by hash; repoint to v3 when adopting the correction.
- v1 and v2 retained so their pinned hashes stay valid and auditable.

## Guardrails
Correction of a confirmed data error to match the primary source; only ś and ṣ pole content changed; vowel
additions retained; v1/v2 retained. The old "no data error" swap verdict is superseded. Structure, not validated
meaning.
