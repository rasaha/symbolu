# DilChat Guna Milan — Domain Review Package

**Status: `DOMAIN_REVIEW_PENDING`.** This is a bounded package a qualified Jyotisha + Sanskrit
reviewer can inspect **without reading any backend code**. It contains only the rule scaffolding,
source intentions, conflicts, exclusions, and sample calculations.

> No reviewer has inspected or approved this package. No approval, name, qualification, edition, or
> signature below is filled in — those slots are for the reviewer to complete. Nothing here is
> `DOMAIN_APPROVED`; no source is `FROZEN`.

---

## 1. Tradition scope

- **Tradition:** North-Indian Ashtakoota (Guna Milan), eight kootas, 36-point maximum.
- **Ayanamsa / zodiac:** Lahiri, sidereal.
- **Assumed default** per DEC-009; **not** yet founder- or domain-confirmed.
- **Out of scope pending confirmation (OQ-1):** South-Indian Dashakoota variants and any additional
  regional kootas.
- **Directional role mapping (OQ-2):** seeker→bride, partner→groom is a *default* and is
  **unconfirmed**; it affects Varna, Tara, and Gana.

## 2. Selected editions (PENDING)

All `PENDING_ACQUISITION`; see `docs/DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md`.

| Source | Title | Author/translator | Edition | Status |
|---|---|---|---|---|
| `MC-NORMATIVE` | Muhurta Chintamani (Melapaka Prakarana) | Rama Daivajna | **PENDING** | PENDING_ACQUISITION |
| `RAMAN-ENGINEERING` | Muhurtha (Electional Astrology) | B. V. Raman | **PENDING** | PENDING_ACQUISITION |
| `BPHS-XREF` | Brihat Parashara Hora Shastra | attr. Parashara | **PENDING** | PENDING_ACQUISITION |
| `KALAPRAKASIKA-XREF` | Kalaprakasika | tr. N. P. Subramania Iyer | **PENDING** | PENDING_ACQUISITION |

## 3. Source hierarchy

`MC-NORMATIVE` (normative) → `RAMAN-ENGINEERING` (engineering) → `BPHS-XREF` (Naisargika friendship
only) → `KALAPRAKASIKA-XREF` (supplementary, only with exact page/verse). Where MC and Raman are
known to differ, the difference is preserved as `SOURCE_CONFLICT` with both candidates; it is never
silently resolved.

## 4. The eight koota summaries

| # | Koota | Max | Keyed by | Directional | Review status |
|---|---|---|---|---|---|
| 1 | Varna | 1 | rashi | yes (role PENDING) | PENDING_DOMAIN_REVIEW |
| 2 | Vashya | 2 | rashi | no | SOURCE_CONFLICT / BLOCKED |
| 3 | Tara | 3 | nakshatra | yes (role PENDING) | PENDING_DOMAIN_REVIEW |
| 4 | Yoni | 4 | nakshatra | no | BLOCKED_DOMAIN_SOURCE |
| 5 | Graha Maitri | 5 | rashi | no | PENDING_DOMAIN_REVIEW |
| 6 | Gana | 6 | nakshatra | yes (role PENDING) | SOURCE_CONFLICT |
| 7 | Bhakoot | 7 | rashi | no | PENDING_DOMAIN_REVIEW |
| 8 | Nadi | 8 | nakshatra | no | PENDING_DOMAIN_REVIEW |
| | **Total** | **36** | | | |

- **Varna** — Moon-rashi element → varna (water=Brahmin, fire=Kshatriya, earth=Vaishya, air=Shudra); groom rank ≥ bride rank → 1.
- **Vashya** — 5 vashya groups; **canonical form is a 12×12 rashi-pair table** (the 5×5 group matrix is a reduction — HIGH-RISK).
- **Tara** — 9-fold count between janma nakshatras; auspicious taras {2,4,6,8,9}; bidirectional combine (3/1.5/0). Counting direction HIGH-RISK.
- **Yoni** — 14 animal yonis; same=4, mortal-enemy=0 reliable; **friendly(3)/unfriendly(1) gradations BLOCKED**.
- **Graha Maitri** — rashi lords + **Naisargika (natural) friendship only**; exclude Tatkalika/Panchadha; 6-band compound (5/4/3/1/0.5/0).
- **Gana** — Deva/Manushya/Rakshasa; directional 3×3; **Deva×Rakshasa = 0 vs 1 SOURCE_CONFLICT**.
- **Bhakoot** — rashi count-pairs {2,12}/{5,9}/{6,8} → 0 dosha, else 7; cancellation in parihara.json.
- **Nadi** — Aadi/Madhya/Antya; same nadi → 0 dosha; **constitutional only (DEC-021)**.

## 5. Directional rules (PENDING OQ-2)

| Koota | Asymmetry | What flips if mapping reverses |
|---|---|---|
| Varna | groom rank ≥ bride rank | which role may lose the point |
| Tara | from/to counting direction | which star anchors the count; single- vs bi-directional |
| Gana | groom-row / bride-column 3×3 | matrix must be transposed |

## 6. High-risk mappings

See `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` §"High-risk table index". In brief: Vashya
table form + gradations; Tara directional counting; Yoni friendly/unfriendly gradations; Graha Maitri
Naisargika-only; Gana Deva×Rakshasa; Bhakoot dosha + cancellation; Nadi classification + same-rashi/
same-lord exceptions; directional bride/groom ordering; regional North/South differences.

## 7. Every source conflict

1. **Vashya** — 12×12 canonical rashi-pair table vs 5×5 group reduction; off-diagonal gradations. `PENDING`.
2. **Yoni** — friendly(3) vs unfriendly(1) off-diagonal cells. `PENDING`.
3. **Gana** — Deva×Rakshasa: MC = 0 vs Raman = 1 (both orders). `PENDING`.
4. **Bhakoot parihara (friendly lords)** — numeric cancellation vs interpretive relief only. `PENDING`.

## 8. Every excluded rule

- **Vashya 12×12 canonical table** — not transcribed (`BLOCKED_DOMAIN_SOURCE`).
- **Yoni friendly(3)/unfriendly(1) gradations** — placeholder `2`, not executable (`BLOCKED`).
- **`parihara.nadi_relief_lords_friends`** — weak source support (`BLOCKED`), disabled.
- **All pariharas** — `enabled: false` by default.
- **Mangal / Manglik dosha** — excluded from the 36-point sum (DEC-019); separate flag only.
- **South-Indian Dashakoota variants** — out of scope (OQ-1).

## 9. Every parihara (all disabled)

See `docs/DILCHAT_PARIHARA_PRECEDENCE_AND_STACKING.md` and
`rules/ashtakoota_muhurta_chintamani_raman_v1/parihara.json`. Ordered deterministic model, no weighted
accumulation. Rules: `nadi_cancel_same_rashi_diff_nakshatra` (p10, cancel),
`nadi_cancel_same_nakshatra_diff_pada` (p11, cancel), `nadi_relief_lords_friends` (p30, relief,
BLOCKED), `bhakoot_cancel_same_rashi_lord` (p10, cancel),
`bhakoot_relief_lords_friends` (p20, SOURCE_CONFLICT), `mangal_dosha_separate_flag` (p99, separate flag).

## 10. Sample manual calculations

Reference: `rules/fixtures/guna_manual_cases.json` (all `DRAFT_MANUAL_VALIDATION_CASE`, values
"manual (unverified)"). Cases include: full-friendly (36), low-score (~1.5), each koota independently
non-maximal (8 cases), direction reversal (Gana 6 vs 5), Bhakoot dosha, Bhakoot cancellation, Nadi
dosha, Nadi exception, Yoni mortal-enemy, mixed Graha Maitri, source-conflict (Gana 0 vs 1), and
regional-rule exclusion. **The reviewer must recompute each independently against the frozen source.**

## 11. Proposed golden Guna cases

Once editions are frozen and conflicts resolved, promote a subset of the manual cases to **golden
fixtures** (locked expected scores). Proposed golden set: `GUNA-FULL-FRIENDLY`,
`GUNA-YONI-MORTAL-ENEMY`, `GUNA-BHAKOOT-DOSHA`, `GUNA-NADI-DOSHA`, plus one directional case
(`GUNA-DIRECTION-REVERSAL-GANA`) and one resolved conflict case (`GUNA-SOURCE-CONFLICT-GANA`). None
may be promoted before sign-off.

## 12. Reviewer questions

1. Which edition/translation of Muhurta Chintamani (and Raman's *Muhurtha*) shall be frozen?
2. **OQ-2:** Confirm the seeker/partner → bride/groom mapping (affects Varna, Tara, Gana directionality).
3. **OQ-1:** North-Indian Ashtakoota only, or add a South-Indian Dashakoota variant?
4. Vashya: use the 12×12 rashi-pair canonical table or the 5×5 group reduction? Provide the graded cells.
5. Tara: single-direction (bride-star-only) or bidirectional-combine convention?
6. Yoni: provide the authoritative friendly(3)/unfriendly(1) values for all off-diagonal cells.
7. Graha Maitri: confirm Naisargika-only and the exact 6-band compound point values.
8. **Gana Deva×Rakshasa: 0 or 1?**
9. Bhakoot: uniform 0 for all three dosha types, or differentiated? Which cancellations are valid?
10. Bhakoot friendly-lords parihara: full numeric cancellation or interpretive relief only?
11. Nadi: confirm the nakshatra→nadi classification and which same-rashi/same-lord/pada exceptions apply.
12. Confirm Mangal dosha stays entirely outside the 36-point sum.

## 13. Approval checklist

- [ ] Editions selected and frozen (all four sources).
- [ ] OQ-1 (tradition scope) confirmed.
- [ ] OQ-2 (bride/groom mapping) confirmed.
- [ ] All eight koota tables verified against the frozen source (chapter/verse/page recorded).
- [ ] Every `SOURCE_CONFLICT` resolved with a cited decision.
- [ ] Every `BLOCKED_DOMAIN_SOURCE` cell transcribed and cited.
- [ ] Parihara set decided (which enabled, precedence confirmed).
- [ ] DEC-021 (Nadi constitutional-only) wording confirmed.
- [ ] DEC-019 (Mangal outside the sum) confirmed.
- [ ] Golden Guna cases recomputed and locked.

## 14. Sign-off template (to be completed by the reviewer)

```
Reviewer name:            ____________________________
Qualifications:           ____________________________
Editions reviewed:        ____________________________
Kootas approved:          ____________________________
Exceptions/pariharas approved: ______________________
Unresolved items:         ____________________________
Limitations/caveats:      ____________________________
Date:                     ____________________________
Signature:                ____________________________
```

**No reviewer approval is recorded. This package is `DOMAIN_REVIEW_PENDING`.**
