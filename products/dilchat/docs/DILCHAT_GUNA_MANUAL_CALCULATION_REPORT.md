# DilChat Guna Milan — Manual Calculation Report

**Status: `DOMAIN_REVIEW_PENDING`. Coverage is STRUCTURAL ONLY. NO case is verified.**

This report summarizes the 24 draft manual-validation cases in
`rules/fixtures/guna_manual_cases.json` (fixture `guna_manual_cases_draft_v2`) for the rule pack
`ashtakoota_muhurta_chintamani_raman_v1`, and their mapping to the 22 Section-10 required
manual-case categories.

> **Honesty statement — read first.**
> - Every case is `DRAFT_MANUAL_VALIDATION_CASE` with `reviewer_status: PENDING_DOMAIN_REVIEW`.
> - Every expected value is a **"manual (unverified)"** string. None has been recomputed against a
>   frozen edition. Matching an astrology website does **not** verify a case.
> - **No case is `MANUAL_VERIFIED` or `MANUAL_VERIFIED_WITH_LIMITATION`.** A qualified reviewer must
>   independently recompute each expected raw and final score against a **frozen** edition before it
>   may become a golden fixture.
> - Coverage of the 22 categories is **structural** (the case exists and exercises the feature); it is
>   **not** evidence that any number is correct.
> - **Direction-dependent** cases (OQ-2 bride/groom mapping unconfirmed) and **source-conflict** cases
>   record **multiple candidate outcomes** and are **NOT resolved** here.
> - Inputs are illustrative. Where a case targets one koota, the other per-koota values are plausible
>   standard classifications, **not** independently verified.

Index conventions follow the pack manifest: `nakshatra` 0..26, `rashi` 0..11, `pada` 1..4.
Role ordering (`seeker`/`partner` → bride/groom) is **PENDING OQ-2 for every case** (`confirmed:false`).

---

## 1. Status vocabulary used in this report

Statuses are drawn from `{MANUAL_VERIFIED, MANUAL_VERIFIED_WITH_LIMITATION, PENDING_DOMAIN_REVIEW,
SOURCE_CONFLICT, EXCLUDED_CASE}`. In this phase **only two occur**:

| Status | Meaning | Count |
|---|---|---|
| `PENDING_DOMAIN_REVIEW` | Draft case; expected values manual & unverified; awaiting reviewer recomputation against a frozen edition. | 23 |
| `SOURCE_CONFLICT` | The case's outcome depends on an unresolved source conflict; two candidate totals recorded, not resolved. | 1 |
| `MANUAL_VERIFIED` | *Not reached.* No case is verified. | 0 |
| `MANUAL_VERIFIED_WITH_LIMITATION` | *Not reached.* | 0 |
| `EXCLUDED_CASE` | *Not used.* (Regional and Mangal exclusions are represented as in-scope flag cases, not dropped cases.) | 0 |

A further **four** cases carry a `SOURCE_CONFLICT`- or `BLOCKED`-tainted *cell* inside an otherwise
`PENDING_DOMAIN_REVIEW` case (annotated in the table): `GUNA-KOOTA-VASHYA-NONMAX` (vashya cell,
12×12-vs-5×5 conflict), `GUNA-KOOTA-YONI-NONMAX` (yoni gradation BLOCKED), `GUNA-KOOTA-GANA-NONMAX`
(Deva×Rakshasa 0-vs-1 conflict), and `GUNA-BHAKOOT-CANCELLATION` (parihara ships disabled; two
candidate totals). These stay `PENDING_DOMAIN_REVIEW` overall.

---

## 2. The 24 manual cases

Columns: **Raw** and **Final** are quoted **verbatim** from the fixture. `S` = seeker, `P` = partner,
shown as `(rashi, nakshatra, pada)`.

| Case ID | Cat. | Targeted koota / feature | Input (roles; r,n,p) | Expected raw (verbatim) | Expected final (verbatim) | Dosha / parihara evaluated | Status |
|---|---|---|---|---|---|---|---|
| `GUNA-FULL-FRIENDLY` | 1 | All 8 kootas maximal (reference 36/36) | S bride (3,7,1) · P groom (3,4,2) | `36 (manual, unverified)` | `36 (manual, unverified)` | none | `PENDING_DOMAIN_REVIEW` |
| `GUNA-LOW-SCORE` | 2 | Low total, multiple doshas/mismatches | S bride (2,2,1) · P groom (6,9,3) | `1.5 (manual, unverified)` | `1.5 (manual, unverified)` | multiple doshas (bhakoot 0, nadi 0, yoni 0) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-VARNA-NONMAX` | 3 | Varna non-maximal (groom rank < bride) → 0 | S bride Brahmin/Cancer (3,7,1) · P groom Shudra/Gemini (2,4,2) | `35 (manual, unverified)` | `35 (manual, unverified)` | none (Varna directional, OQ-2) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-VASHYA-NONMAX` | 4 | Vashya non-maximal (diff groups) → 1 | S bride (0,7,1) · P groom (2,4,2) | `35 (manual, unverified; vashya cell SOURCE_CONFLICT)` | `35 (manual, unverified)` | none; **vashya cell SOURCE_CONFLICT (12×12 vs 5×5)** | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-TARA-NONMAX` | 5 | Tara non-maximal (one direction inauspicious) → 1.5 | S bride (3,0,1) · P groom (3,2,2); **direction matters** | `34.5 (manual, unverified)` | `34.5 (manual, unverified)` | none (Tara directional, OQ-2) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-YONI-SAME-ANIMAL` | 6 | Yoni same animal (Horse×Horse) → 4 diagonal | S bride Ashwa (0,0,1) · P groom Ashwa (10,23,2) | `36 (manual, unverified; yoni diagonal cell = 4 is certain)` | `36 (manual, unverified)` | none | `PENDING_DOMAIN_REVIEW` |
| `GUNA-YONI-MORTAL-ENEMY` | 7 | Yoni mortal-enemy (Cat×Rat) → 0 (certain cell) | S bride Marjara/Cat (3,6,1) · P groom Mushaka/Rat (3,9,2) | `32 (manual, unverified)` | `32 (manual, unverified)` | none | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-YONI-NONMAX` | 8 | Yoni intermediate gradation (placeholder) → 2 | S bride (3,0,1) · P groom (3,1,2) | `34 (manual, unverified; yoni cell BLOCKED)` | `34 (manual, unverified)` | none; **yoni gradation BLOCKED_DOMAIN_SOURCE** | `PENDING_DOMAIN_REVIEW` |
| `GUNA-GRAHAMAITRI-SAME-LORD` | 9 | Graha Maitri same lord (Mars/Aries×Mars/Scorpio) → 5 | S bride Mars/Aries (0,0,1) · P groom Mars/Scorpio (7,16,2) | `36 (manual, unverified; same-lord graha cell = 5)` | `36 (manual, unverified) — same rashi lord (Mars) => friend+friend => 5` | none | `PENDING_DOMAIN_REVIEW` |
| `GUNA-MIXED-GRAHAMAITRI` | 10 | Graha Maitri mixed (friend one way + enemy other) → 1 | S bride Sun/Leo (4,9,1) · P groom Venus/Libra (6,13,2) | `30 (manual, unverified)` | `30 (manual, unverified) — Sun<->Venus = friend+enemy compound` | none | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-GANA-NONMAX` | 11 | Gana Deva×Rakshasa (Raman candidate = 1) → 1 | S bride Deva (3,0,1) · P groom Rakshasa (7,8,2); **direction matters** | `31 (manual, unverified; gana cell SOURCE_CONFLICT 0 vs 1)` | `31 (manual, unverified)` | none; **gana cell SOURCE_CONFLICT (0 vs 1)** | `PENDING_DOMAIN_REVIEW` |
| `GUNA-BHAKOOT-DOSHA` | 12 | Bhakoot 2/12 (Dwir-Dwadasha) dosha → 0, no cancel | S bride (0,0,1) · P groom (1,3,2) | `22 (manual, unverified)` | `22 (manual, unverified) — Bhakoot DOSHA_PRESENT` | Bhakoot dosha `DOSHA_PRESENT` (different lords, no parihara) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-BHAKOOT-5-9` | 13 | Bhakoot 5/9 (Nava-Pancham) dosha → 0 | S bride (0,0,1) · P groom (4,9,2) | `29 (manual, unverified) — Nava-Pancham 5/9 Bhakoot dosha` | `29 (manual, unverified) — Bhakoot DOSHA_PRESENT (5/9)` | Bhakoot dosha `DOSHA_PRESENT` (5/9) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-BHAKOOT-NONMAX` | 14 | Bhakoot 6/8 (Shad-Ashtaka) dosha → 0 | S bride (0,0,1) · P groom (5,4,2) | `29 (manual, unverified)` | `29 (manual, unverified)` | Bhakoot dosha `DOSHA_PRESENT` (6/8) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-BHAKOOT-CANCELLATION` | 14, 16 | Bhakoot 6/8 with same rashi-lord (Mars) → cancellation candidate | S bride (0,0,1) · P groom (7,16,2) | `26 (manual, unverified; bhakoot 0 with parihara disabled)` | `26 default / 33 if cancellation enabled (manual, unverified) — DOSHA_CANCELLED when enabled` | parihara `bhakoot_cancel_same_rashi_lord` **DISABLED by default** (if enabled → bhakoot 7) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-BHAKOOT-ACCEPTED` | 15 | Bhakoot 7/7 accepted (Aries×Libra) → 7, no dosha | S bride (0,0,1) · P groom (6,14,2) | `36 (manual, unverified; 7/7 is an accepted Bhakoot relationship)` | `36 (manual, unverified) — Bhakoot NO_DOSHA (7/7 accepted)` | Bhakoot `NO_DOSHA` | `PENDING_DOMAIN_REVIEW` |
| `GUNA-NADI-DOSHA` | 17 | Nadi same category (Aadi) dosha → 0; constitutional only | S bride (0,0,1) · P groom (8,18,2) | `24 (manual, unverified)` | `24 (manual, unverified) — Nadi DOSHA_PRESENT (constitutional only)` | Nadi dosha `DOSHA_PRESENT`, no exception (DEC-021) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-NADI-NONMAX` | 17 | Nadi same category → 0 (koota-isolation case) | S bride (0,0,1) · P groom (1,5,2) | `28 (manual, unverified)` | `28 (manual, unverified)` | Nadi dosha `DOSHA_PRESENT` (DEC-021) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-NADI-DIFFERENT` | 18 | Nadi different category (Aadi vs Madhya) → 8, no dosha | S bride Aadi (0,0,1) · P groom Madhya (0,1,2) | `34 (manual, unverified) — different nadi => full 8, NO Nadi dosha` | `34 (manual, unverified) — Nadi NO_DOSHA (constitutional only)` | Nadi `NO_DOSHA` (DEC-021) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-NADI-EXCEPTION` | 19 | Nadi dosha, same rashi diff nakshatra → exception candidate | S bride (0,0,1) · P groom (0,5,2) | `26 (manual, unverified; nadi 0 with parihara disabled)` | `26 default / 34 if exception enabled (manual, unverified) — DOSHA_CANCELLED when enabled` | parihara `nadi_cancel_same_rashi_diff_nakshatra` **DISABLED by default** (if enabled → nadi 8) | `PENDING_DOMAIN_REVIEW` |
| `GUNA-DIRECTION-REVERSAL-GANA` | 20 | Bride/groom reversal (Gana Deva×Manushya) → 6 vs 5 | S Deva/Ashwini (3,0,1) · P Manushya/Bharani (2,1,2); **direction matters** | `DIRECTION-DEPENDENT: gana = 6 or 5 (manual, unverified) — resolves only after OQ-2` | `PENDING OQ-2 (manual, unverified)` | none; **direction-dependent (OQ-2), unresolved** | `PENDING_DOMAIN_REVIEW` |
| `GUNA-SOURCE-CONFLICT-GANA` | 11, 21 | Source conflict: Gana Deva×Rakshasa MC=0 vs Raman=1 | S bride Deva (3,0,1) · P groom Rakshasa (7,8,2); **direction matters** | `SOURCE_CONFLICT: 28 (MC gana=0) OR 29 (Raman gana=1) (manual, unverified)` | `SOURCE_CONFLICT — outcome SOURCE_CONFLICT; NOT silently resolved` | none; **two candidate totals recorded, NOT resolved** | `SOURCE_CONFLICT` |
| `GUNA-REGIONAL-RULE-EXCLUSION` | 22 | Regional exclusion: South-Indian Dashakoota variant NOT applied | S bride (3,7,1) · P groom (3,4,2) | `36 (manual, unverified; north_indian only)` | `36 (manual, unverified) — regional variant excluded and flagged, not applied` | `REGIONAL_EXCLUSION` (out of scope, OQ-1) — flagged, not applied | `PENDING_DOMAIN_REVIEW` |
| `GUNA-KOOTA-GRAHAMAITRI-NONMAX` | — (supplementary) | Graha Maitri neutral+neutral → 3 (koota-isolation) | S bride (3,7,1) · P groom (0,4,2) | `34 (manual, unverified)` | `34 (manual, unverified)` | none | `PENDING_DOMAIN_REVIEW` |

**Row count: 24.** The final row (`GUNA-KOOTA-GRAHAMAITRI-NONMAX`) is a supplementary koota-isolation
case; it is not bound to a distinct required category because categories 9 and 10 are already covered
by `GUNA-GRAHAMAITRI-SAME-LORD` and `GUNA-MIXED-GRAHAMAITRI`. It is retained for per-koota isolation
completeness.

---

## 3. Section-10 required category coverage (all 22 confirmed present)

Mapping is taken verbatim from `required_category_coverage` in the fixture. The rule-pack validator
(`scripts/validate_rule_pack.py`) checks that every category is covered. **Coverage is structural and
does NOT imply verification.**

| # | Category | Covering case(s) |
|---|---|---|
| 1 | `max_or_near_max` | `GUNA-FULL-FRIENDLY` |
| 2 | `low_total` | `GUNA-LOW-SCORE` |
| 3 | `varna_nonmax` | `GUNA-KOOTA-VARNA-NONMAX` |
| 4 | `vashya_nonmax` | `GUNA-KOOTA-VASHYA-NONMAX` |
| 5 | `tara_directional` | `GUNA-KOOTA-TARA-NONMAX` |
| 6 | `yoni_same_animal` | `GUNA-YONI-SAME-ANIMAL` |
| 7 | `yoni_mortal_enemy` | `GUNA-YONI-MORTAL-ENEMY` |
| 8 | `yoni_intermediate_gradation` | `GUNA-KOOTA-YONI-NONMAX` |
| 9 | `graha_maitri_same_lord` | `GUNA-GRAHAMAITRI-SAME-LORD` |
| 10 | `graha_maitri_mixed` | `GUNA-MIXED-GRAHAMAITRI` |
| 11 | `gana_deva_rakshasa` | `GUNA-KOOTA-GANA-NONMAX`, `GUNA-SOURCE-CONFLICT-GANA` |
| 12 | `bhakoot_2_12` | `GUNA-BHAKOOT-DOSHA` |
| 13 | `bhakoot_5_9` | `GUNA-BHAKOOT-5-9` |
| 14 | `bhakoot_6_8` | `GUNA-KOOTA-BHAKOOT-NONMAX`, `GUNA-BHAKOOT-CANCELLATION` |
| 15 | `bhakoot_accepted` | `GUNA-BHAKOOT-ACCEPTED` |
| 16 | `bhakoot_relief_candidate` | `GUNA-BHAKOOT-CANCELLATION` |
| 17 | `nadi_same_category_dosha` | `GUNA-NADI-DOSHA`, `GUNA-KOOTA-NADI-NONMAX` |
| 18 | `nadi_different_category` | `GUNA-NADI-DIFFERENT` |
| 19 | `nadi_exception_candidate` | `GUNA-NADI-EXCEPTION` |
| 20 | `bride_groom_reversal` | `GUNA-DIRECTION-REVERSAL-GANA` |
| 21 | `source_conflict` | `GUNA-SOURCE-CONFLICT-GANA` |
| 22 | `regional_exclusion` | `GUNA-REGIONAL-RULE-EXCLUSION` |

**All 22 categories are covered.** 23 of the 24 cases are bound to a required category; the 24th
(`GUNA-KOOTA-GRAHAMAITRI-NONMAX`) is supplementary.

---

## 4. Direction-dependent and source-conflict cases are NOT resolved

- **Direction-dependent (OQ-2 unconfirmed).** `GUNA-DIRECTION-REVERSAL-GANA` records **both**
  candidate outcomes (gana = 6 if seeker is groom, 5 if seeker is bride) and resolves to neither.
  `GUNA-KOOTA-VARNA-NONMAX`, `GUNA-KOOTA-TARA-NONMAX`, `GUNA-KOOTA-GANA-NONMAX`, and
  `GUNA-SOURCE-CONFLICT-GANA` also depend on the bride/groom mapping. Until OQ-2 is confirmed, the
  role assignment for these cases is a **default, not a decision**.
- **Source conflict.** `GUNA-SOURCE-CONFLICT-GANA` records **two** candidate totals — 28 (MC gana=0)
  or 29 (Raman gana=1) — and carries report status `SOURCE_CONFLICT`. It is **not silently
  resolved**. Additional cases carry a conflict- or BLOCKED-tainted cell (vashya 12×12-vs-5×5, yoni
  gradation, gana 0-vs-1), noted inline in the table.
- **Parihara-dependent.** `GUNA-BHAKOOT-CANCELLATION` and `GUNA-NADI-EXCEPTION` show a default total
  (parihara **disabled**) and a second total *if* the parihara were enabled. All six parihara rules
  ship **disabled**; enabling any is a domain-review + founder decision.

---

## 5. What must happen before any case becomes a golden fixture

1. The relevant editions must be **acquired and frozen** (currently all `PENDING_ACQUISITION`; see
   the Source Acquisition Report and `GUNA_SOURCE_MANIFEST.json`).
2. A **qualified reviewer** (Jyotisha + Muhurta/Melapaka + Sanskrit, or Sanskrit collaborator +
   traditional marriage-matching + regional-variation competence) must **independently recompute**
   each expected raw and final score against the frozen edition, recording chapter/verse/page.
3. **OQ-2** (bride/groom mapping) must be confirmed before any directional case is fixed.
4. Each **source conflict** must be resolved with a cited decision (or the case kept as an explicit
   `SOURCE_CONFLICT` fixture with both candidates).
5. Only then may a subset be promoted to **golden** (locked) fixtures. Proposed candidates (post
   sign-off only): `GUNA-FULL-FRIENDLY`, `GUNA-YONI-MORTAL-ENEMY`, `GUNA-BHAKOOT-DOSHA`,
   `GUNA-NADI-DOSHA`, one directional case (`GUNA-DIRECTION-REVERSAL-GANA`), one resolved-conflict
   case (`GUNA-SOURCE-CONFLICT-GANA`). **None may be promoted before sign-off.**

**No case in this report is verified. The pack remains `draft: true`, `executable: false`,
`authority_gate: BLOCKED`.**

---

## 6. Related artifacts

- `rules/fixtures/guna_manual_cases.json` — the machine-readable draft cases (source of truth).
- `rules/ashtakoota_muhurta_chintamani_raman_v1/pack_control.json` — counts: 24 manual cases, 0 verified.
- `scripts/validate_rule_pack.py` — category-coverage and invariant validator.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md` — reviewer package (this report is item §10 there).
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — per-rule source mapping.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_RECORD.md` — blank reviewer sign-off record.
