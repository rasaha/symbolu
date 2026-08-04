# DilChat Guna Milan — Rule Traceability Matrix

Human-readable view of
`rules/ashtakoota_muhurta_chintamani_raman_v1/source_traceability.json`.

**Pack:** `ashtakoota_muhurta_chintamani_raman_v1` · **Draft:** yes · **Executable:** no ·
**Authority gate:** `BLOCKED (pending edition freeze + domain review)`

> No rule is `DOMAIN_APPROVED`. No source is `FROZEN`. Every `chapter` / `verse` / page reference is
> `null` and `PENDING_ACQUISITION`. Where the normative source (Muhurta Chintamani) and the
> engineering source (B. V. Raman) are known to differ, the cell is `SOURCE_CONFLICT` with both
> candidate values recorded — never silently chosen.

**Source IDs:** `MC` = MC-NORMATIVE · `RAMAN` = RAMAN-ENGINEERING · `BPHS` = BPHS-XREF ·
`KALA` = KALAPRAKASIKA-XREF.

> **Editions are now IDENTIFIED but NOT frozen.** Real, externally-verifiable candidate editions
> (publisher / translator / ISBN / catalogue identifiers) are recorded in
> `rules/sources/GUNA_SOURCE_MANIFEST.json` — e.g. Raman *Muhurtha (Electional Astrology)*
> ISBN-13 978-8185674681 (UBSPD) and BPHS (tr. R. Santhanam) ISBN-13 978-8188230600. Their status is
> `EDITION_IDENTIFIED_NOT_ACQUIRED` and the overall status is still `PENDING_ACQUISITION`: no copy has
> been acquired, opened, paginated, or reviewer-confirmed here. Consequently every `chapter` /
> `verse` / `page` field remains **`null` / `PENDING`** and no value below is invented.

**Counts (from `pack_control.json`):** 23 traceability rules · 0 approved · 3 `BLOCKED_DOMAIN_SOURCE` ·
16 `PENDING_DOMAIN_REVIEW` · 6 conflict rule-entries across 4 conflict topics · 6 parihara rules, all
`enabled: false` · 24 manual cases, 0 verified.

---

## Varna (max 1) — directional

| Rule | Type | Source | Directionality | Review | Conflict | v1 |
|---|---|---|---|---|---|---|
| `varna.rashi_to_varna` | classification | MC | directional | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `varna.directional_scoring` | scoring | MC | directional (role ordering PENDING OQ-2) | PENDING_DOMAIN_REVIEW | NONE | PENDING |

## Vashya (max 2) — symmetric · **HIGH-RISK**

| Rule | Type | Source | Review | Conflict | v1 |
|---|---|---|---|---|---|
| `vashya.rashi_to_group` | classification | MC | SOURCE_CONFLICT | SOURCE_CONFLICT | BLOCKED_DOMAIN_SOURCE |
| `vashya.group_score_matrix_5x5` | score matrix (reduction) | MC | SOURCE_CONFLICT | SOURCE_CONFLICT | BLOCKED_DOMAIN_SOURCE |
| `vashya.rashi_pair_12x12_canonical` | score matrix (canonical) | MC | BLOCKED_DOMAIN_SOURCE | SOURCE_CONFLICT | BLOCKED_DOMAIN_SOURCE |

## Tara (max 3) — directional · **HIGH-RISK**

| Rule | Type | Source | Directionality | Review | Conflict | v1 |
|---|---|---|---|---|---|---|
| `tara.nakshatra_count_9fold` | counting | MC | bidirectional; from/to PENDING OQ-2 | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `tara.direction_convention` | scoring | MC | single-dir vs bidirectional PENDING | PENDING_DOMAIN_REVIEW | NONE | PENDING |

## Yoni (max 4) — symmetric · **HIGH-RISK**

| Rule | Type | Source | Review | Conflict | v1 |
|---|---|---|---|---|---|
| `yoni.nakshatra_to_yoni` | classification | MC | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `yoni.score_matrix_14x14` | score matrix | MC | BLOCKED_DOMAIN_SOURCE | SOURCE_CONFLICT | BLOCKED_DOMAIN_SOURCE |

Diagonal (same = 4) and the 7 mortal-enemy pairs (= 0) are reliable; **friendly(3)/unfriendly(1)
gradations are placeholder `2` and BLOCKED.**

## Graha Maitri (max 5) — symmetric · **HIGH-RISK**

| Rule | Type | Source | Review | Conflict | v1 |
|---|---|---|---|---|---|
| `graha_maitri.rashi_to_lord` | classification | MC | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `graha_maitri.naisargika_matrix` | friendship matrix | BPHS | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `graha_maitri.compound_table_6band` | score matrix | RAMAN | PENDING_DOMAIN_REVIEW | NONE | PENDING |

**Must use Naisargika (natural) friendship ONLY — exclude Tatkalika (temporary) and Panchadha.**

## Gana (max 6) — directional · **HIGH-RISK**

| Rule | Type | Source | Directionality | Review | Conflict | v1 |
|---|---|---|---|---|---|---|
| `gana.nakshatra_to_gana` | classification | MC | directional | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `gana.score_matrix_3x3` | score matrix | MC | groom-row/bride-column (PENDING OQ-2) | SOURCE_CONFLICT | SOURCE_CONFLICT | PENDING |

**Deva × Rakshasa = 0 (MC candidate) vs 1 (Raman candidate) — `SOURCE_CONFLICT`, not resolved.**

## Bhakoot (max 7) — symmetric · **HIGH-RISK**

| Rule | Type | Source | Review | Conflict | v1 |
|---|---|---|---|---|---|
| `bhakoot.count_pairs` | counting | MC | PENDING_DOMAIN_REVIEW | NONE | PENDING |

Dosha: {2,12}, {5,9}, {6,8} → 0. Cancellation handled in parihara.json (disabled).

## Nadi (max 8) — symmetric · **HIGH-RISK** · DEC-021

| Rule | Type | Source | Review | Conflict | v1 |
|---|---|---|---|---|---|
| `nadi.nakshatra_to_nadi` | classification | MC | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `nadi.scoring_rule` | scoring | MC | PENDING_DOMAIN_REVIEW | NONE | PENDING |

**Constitutional-temperament framing ONLY — never medical/genetic/fertility/health (DEC-021).**

## Parihara (dosha cancellation) — all DISABLED

| Rule | Koota | Source | Effect | Review | Conflict | v1 |
|---|---|---|---|---|---|---|
| `parihara.nadi_cancel_same_rashi_diff_nakshatra` | nadi | MC | cancel (numeric) | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `parihara.nadi_cancel_same_nakshatra_diff_pada` | nadi | MC | cancel (numeric) | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `parihara.nadi_relief_lords_friends` | nadi | RAMAN | interpretive relief | BLOCKED_DOMAIN_SOURCE | NONE | BLOCKED |
| `parihara.bhakoot_cancel_same_rashi_lord` | bhakoot | MC | cancel (numeric) | PENDING_DOMAIN_REVIEW | NONE | PENDING |
| `parihara.bhakoot_relief_lords_friends` | bhakoot | RAMAN | cancel vs relief | SOURCE_CONFLICT | SOURCE_CONFLICT | PENDING |
| `parihara.mangal_dosha_separate_flag` | external_mangal | RAMAN | separate flag (no numeric) | PENDING_DOMAIN_REVIEW | NONE | PENDING |

Mangal / Manglik dosha is **outside** the 36-point sum (DEC-019); a separate flag only.

---

## High-risk table index

| High-risk item | Rules | Status |
|---|---|---|
| Vashya rashi→category + gradations (12×12 canonical vs 5×5 reduction) | `vashya.*` | SOURCE_CONFLICT / BLOCKED |
| Tara directional counting | `tara.*` | PENDING (role ordering OQ-2) |
| Complete Yoni 0–4 matrix, friendly(3)/unfriendly(1) | `yoni.score_matrix_14x14` | BLOCKED_DOMAIN_SOURCE |
| Graha Maitri exclude Tatkalika = Naisargika only | `graha_maitri.*` | PENDING_DOMAIN_REVIEW |
| Gana Deva × Rakshasa (0 vs 1) | `gana.score_matrix_3x3` | SOURCE_CONFLICT |
| Bhakoot dosha + cancellation | `bhakoot.count_pairs`, `parihara.bhakoot_*` | PENDING / SOURCE_CONFLICT |
| Nadi classification + same-rashi/same-lord exceptions | `nadi.*`, `parihara.nadi_*` | PENDING / BLOCKED |
| Directional bride/groom ordering | `varna.directional_scoring`, `tara.direction_convention`, `gana.score_matrix_3x3` | PENDING (OQ-2) |
| Regional North/South differences | all | PENDING — pack is north_indian_ashtakoota; South-Indian Dashakoota out of scope (OQ-1) |

## Every source conflict (explicit)

1. **Vashya** — canonical 12×12 rashi-pair table vs 5×5 group reduction; off-diagonal gradations. `resolution: PENDING`.
2. **Yoni** — friendly(3) vs unfriendly(1) off-diagonal gradations. `resolution: PENDING`.
3. **Gana** — Deva × Rakshasa: MC = 0, Raman = 1 (both role orders). `resolution: PENDING`.
4. **Bhakoot parihara (friendly lords)** — full numeric cancellation vs interpretive relief only. `resolution: PENDING`.

## Per-koota status summary

| Koota | Status |
|---|---|
| Varna | `PENDING_DOMAIN_REVIEW` |
| Vashya | `SOURCE_CONFLICT` / `BLOCKED_DOMAIN_SOURCE` |
| Tara | `PENDING_DOMAIN_REVIEW` |
| Yoni | `BLOCKED_DOMAIN_SOURCE` |
| Graha Maitri | `PENDING_DOMAIN_REVIEW` |
| Gana | `SOURCE_CONFLICT` |
| Bhakoot | `PENDING_DOMAIN_REVIEW` |
| Nadi | `PENDING_DOMAIN_REVIEW` |
| Parihara | `PENDING_DOMAIN_REVIEW` (all disabled) |

**No koota is approved. The whole pack is blocked pending edition freeze + domain review.**
