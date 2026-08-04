# DilChat — Guna Milan Rule-Pack Traceability Audit

**Rule pack audited:** `products/dilchat/rules/ashtakoota_lahiri_classical_v1/`
(`version: 1.0.0-draft`, `draft: true`, `review_required: true`, `tradition: north_indian_ashtakoota` (assumed)).
**Audit stance:** The draft rule pack is treated as **astrologically unverified** until each element is
traced to a **named, authoritative** textual source. Anonymous blogs and unsourced secondary
websites are explicitly **not** accepted as authority.

## Legend

- **STRUCTURE** — Is the table/rule mechanically complete and internally consistent? (verified by
  this audit; see `DILCHAT_ARTIFACT_VALIDATION_REPORT.md §4`.)
- **SOURCE** — Is the *content* traced to a named authority with `verified: true`?
- **`BLOCKED_DOMAIN_SOURCE`** — element cannot be certified for user-facing use until a domain
  expert confirms it against a cited authority. It is **not** silently filled.

## Global finding

`sources.json` contains **9/9 citations with `verified: false`** and `intended_primary_authority.confirmed: false`
(candidate: *B. V. Raman — Muhurta / Hindu Predictive Astrology*). Therefore **every koota's SOURCE
status is `BLOCKED_DOMAIN_SOURCE`**, regardless of structural completeness. This is the correct,
honest state for a draft pack per DEC-009; it is the single dominant blocker for user-facing reports.

`manifest.role_mapping.confirmed: false` and directional-orientation notes (Gana, Tara) mean the
**directionality** of three kootas is also unconfirmed (OQ-2).

---

## Per-Koota traceability matrix

### Varna (max 1) — `varna.json`
| Field | Value |
|-------|-------|
| Inputs | Moon **rashi** of each partner |
| Directionality | **Directional** (`groom varna_rank ≥ bride varna_rank → 1 else 0`) |
| Lookup tables | `rashi_to_varna` (12/12, element-based: water=Brahmin, fire=Kshatriya, earth=Vaishya, air=Shudra); `varna_ranks` |
| Max | 1 ✅ |
| STRUCTURE | **Complete** — covers 0..11; 3/3/3/3 distribution; ranks valid |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` (citation `verified:false`) |
| Exceptions | none |
| Safe to implement? | **Engine yes; user-facing no** until source + role_mapping confirmed |

### Vashya (max 2) — `vashya.json`
| Field | Value |
|-------|-------|
| Inputs | Moon **rashi** of each partner → vashya group |
| Directionality | Symmetric (`directional:false`) |
| Lookup tables | `rashi_to_vashya` (12/12: Chatushpada/Manava/Jalachara/Vanachara/Keeta); 5×5 `group_score_matrix` (diagonal 2, symmetric) |
| Max | 2 ✅ |
| STRUCTURE | **Complete but reduced** — the file itself flags that the *canonical* form is a 12×12 rashi-pair table; a 5×5 group reduction is used as a stand-in. Off-diagonal values are the **most source-variable** cells in the pack. |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — **highest-risk table**; half-sign assignments (Sagittarius, Capricorn) and off-diagonal scores must be transcribed from the authority (prefer the 12×12 form). |
| Exceptions | none |
| Safe to implement? | **No** for user-facing; the 5×5 reduction should be replaced by the sourced 12×12 table before freeze. |

### Tara (max 3) — `tara.json`
| Field | Value |
|-------|-------|
| Inputs | Janma **nakshatra** of each partner |
| Directionality | **Directional / bidirectional** — count both ways, combine (both auspicious 3 / one 1.5 / none 0) |
| Lookup tables | 9-tara sequence with auspicious flags (auspicious {2,4,6,8,9}); inclusive counting rule mod 9 (remainder 0→9) |
| Max | 3 ✅ |
| STRUCTURE | **Complete** — counting formula explicit; auspicious set matches classical |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — **convention ambiguity:** single-direction (from bride's star, score/3) vs the bidirectional-combine convention used here differ by school (OQ-2). |
| Exceptions | none |
| Safe to implement? | **No** for user-facing until the counting convention is confirmed. |

### Yoni (max 4) — `yoni_matrix.json`
| Field | Value |
|-------|-------|
| Inputs | Janma **nakshatra** → yoni animal (14 yonis) |
| Directionality | Symmetric |
| Lookup tables | `nakshatra_to_yoni` (27/27); 14×14 `yoni_score_matrix` (diagonal 4, symmetric); 7 `mortal_enemy_pairs` → 0 |
| Max | 4 ✅ |
| STRUCTURE | **Partially complete** — diagonal (4) and mortal-enemy (0) are load-bearing and present; but **only values {0,2,4} are populated**: the friendly(3) and unfriendly(1) gradations are defaulted to neutral(2). |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — the intermediate gradations are un-sourced placeholders. |
| Exceptions | none |
| Safety | DEC-021: bounded to consensual adult romantic context; enforced in interpretation/AI layers. |
| Safe to implement? | **No** for scoring accuracy — a couple whose true relation is friendly(3)/unfriendly(1) would be mis-scored as 2. Must complete the matrix from source. |

### Graha Maitri (max 5) — `graha_maitri_matrix.json`
| Field | Value |
|-------|-------|
| Inputs | Moon **rashi** → rashi lord → planetary friendship |
| Directionality | Symmetric via compound of both directions |
| Lookup tables | `rashi_to_lord` (12/12, all within 7 classical planets); 7×7 `planet_relationships` (Naisargika, each planet vs other 6 complete); `compound_table` (friend+friend 5 … enemy+enemy 0, incl. neutral+neutral 3) |
| Max | 5 ✅ |
| STRUCTURE | **Complete** — relationship graph complete; compound endpoints correct |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — two open points: (a) the design added `neutral+neutral = 3`, a band the original task enumeration omitted — must confirm the authority uses it; (b) natural (Naisargika) vs compound (Panchadha) friendship choice must be confirmed. |
| Exceptions | none |
| Safe to implement? | **Engine yes; user-facing no** until the compound-band values are confirmed. |

### Gana (max 6) — `gana_matrix.json`
| Field | Value |
|-------|-------|
| Inputs | Janma **nakshatra** → gana (Deva/Manushya/Rakshasa) |
| Directionality | **Directional** (`rows = groom, cols = bride`; asymmetric off-diagonals) |
| Lookup tables | `nakshatra_to_gana` (27/27, 9/9/9); 3×3 `gana_score_matrix` (diagonal 6) |
| Max | 6 ✅ |
| STRUCTURE | **Complete** — distribution 9/9/9; diagonal 6 |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — **two unconfirmed decisions:** (a) Deva×Rakshasa = 1 here (some tables use 0); (b) matrix orientation (groom-row/bride-column) depends on the unconfirmed `role_mapping` — if roles map the other way the matrix must be transposed (OQ-2). |
| Exceptions | `gana_cancel_rashi_lords_friends` (disabled) |
| Safe to implement? | **No** for user-facing until orientation + Deva×Rakshasa value confirmed. |

### Bhakoot (max 7) — `bhakoot.json`
| Field | Value |
|-------|-------|
| Inputs | Moon **rashi** of each partner (mutual count) |
| Directionality | Symmetric |
| Lookup tables | penalized count-pairs {2/12, 5/9, 6/8} → 0; else 7 |
| Max | 7 ✅ |
| STRUCTURE | **Complete** — the three dosha pairs are exactly the classical set |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — uniform 0 for all three vs school-specific weighting must be confirmed. |
| Exceptions | `bhakoot_cancel_same_rashi_lord`, `bhakoot_cancel_lords_friends` (both disabled) |
| Safe to implement? | **Engine yes; user-facing no** until weighting confirmed. This is the closest-to-ready table. |

### Nadi (max 8) — `nadi.json`
| Field | Value |
|-------|-------|
| Inputs | Janma **nakshatra** → nadi (Aadi/Madhya/Antya) |
| Directionality | Symmetric |
| Lookup tables | `nakshatra_to_nadi` (27/27, 9/9/9); same nadi → 0 (dosha), different → 8 |
| Max | 8 ✅ |
| STRUCTURE | **Complete** — distribution 9/9/9; scoring 0/8 correct |
| SOURCE | `BLOCKED_DOMAIN_SOURCE` — the nakshatra→nadi assignment must match the chosen authority (some traditions permute the pattern). |
| Safety | **DEC-021 constraint embedded in the file** (`safety_constraint.hard:true`): constitutional-only; never medical/genetic/fertility/health. ✅ verified present. |
| Exceptions | 3 Nadi-cancellation rules (all disabled) |
| Safe to implement? | **Engine yes; user-facing no** — and Nadi carries the highest weight (8), so a wrong assignment has the largest score impact. |

---

## Exceptions (`exceptions.json`)

| Property | Finding |
|----------|---------|
| Default state | **All 7 rules `enabled:false`** ✅ (verified) |
| Silent cancellation | `policy.no_silent_cancellation: true`; trace-on-apply required ✅ |
| Mangal dosha | Present as a **disabled placeholder**, explicitly kept **out** of the 36-point sum (DEC-019) ✅ |
| Citations | All exception `citation.verified:false` → any enabling is `BLOCKED_DOMAIN_SOURCE` |

**No dosha cancellation can fire in the current pack.** This is correct and safe: the base pack
yields the raw classical 36-point score with full trace.

---

## Directionality summary (manifest) — requires OQ-2 confirmation

| Koota | `directional` flag | Confirmed? |
|-------|--------------------|-----------|
| Varna | true | ❌ role_mapping unconfirmed |
| Tara | true | ❌ convention + roles unconfirmed |
| Gana | true | ❌ orientation unconfirmed |
| Vashya, Yoni, Graha Maitri, Bhakoot, Nadi | false | n/a (symmetric) |

---

## Conclusion

| Dimension | Status |
|-----------|--------|
| Mechanical structure / maxima / indices | **Complete & consistent** (43/43 checks; Σ = 36) |
| No silent cancellation | **Guaranteed** (all exceptions disabled) |
| Nadi medical-safety (DEC-021) | **Present & hard** |
| Authoritative SOURCE for every koota | **`BLOCKED_DOMAIN_SOURCE` (9/9 unverified)** |
| Directionality (Varna, Tara, Gana) | **Unconfirmed (OQ-2)** |
| Highest-risk content tables | Vashya (5×5 reduction), Yoni (missing 3/1 gradations) |

### Verdict: **RULE_PACK_BLOCKED**

The pack is **structurally implementation-ready** (the engine can be built and unit-tested against
it today), but it is **NOT astrologically certified** and **must not back any user-facing report**.
Every koota is `BLOCKED_DOMAIN_SOURCE`. To reach `RULE_PACK_READY`:

1. Confirm the named authority (OQ-1) and set `intended_primary_authority.confirmed: true`.
2. Transcribe/verify each koota table against that authority; set each `sources.json` citation
   `verified: true`. **Replace the Vashya 5×5 reduction with the sourced 12×12 rashi-pair table**
   and **complete the Yoni matrix's friendly(3)/unfriendly(1) cells**.
3. Confirm directionality and `role_mapping` (OQ-2); transpose the Gana matrix if roles invert.
4. Domain-expert sign-off; then **freeze as a new immutable version** (do not edit the draft in
   place — mint `…_v1` frozen or `…_v2`), and flip `manifest.draft:false`.

Until step 4, `guna_report` generation must remain gated to non-user-facing test/QA contexts.
