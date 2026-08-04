# DilChat Guna Milan — Rule Adjudication Ledger

Per-rule adjudication ledger for the Ashtakoota (Guna Milan) rule pack
`ashtakoota_muhurta_chintamani_raman_v1`, covering all eight kootas plus the
dosha-parihara model. Derived from and consistent with
`rules/ashtakoota_muhurta_chintamani_raman_v1/source_traceability.json`,
`manifest.json`, `parihara.json`, `pack_control.json`, and the eight per-koota
JSON files.

**Pack:** `ashtakoota_muhurta_chintamani_raman_v1` · **Tradition:** north_indian_ashtakoota
(ASSUMED per DEC-009; not founder-confirmed) · **Draft:** yes · **Executable:** no ·
**Authority gate:** `BLOCKED (pending edition freeze + domain review)`

> **Honesty statement.** This is a *Guna Source Acquisition, Rule Adjudication, and Domain
> Sign-off Preparation* working document. **Nothing here is approved.** No rule is
> `DOMAIN_APPROVED` and no rule is executable. No source edition is `FROZEN`. Every
> `chapter` / `verse` / `page` reference is `null` and `PENDING (not acquired / not verified)`.
> None of the four source conflicts is resolved — both competing candidates are recorded and the
> resolution is `PENDING`. Resolution requires a frozen edition **and** a qualified
> Jyotisha + Sanskrit reviewer, neither of which exists yet. Internet consensus is **not**
> accepted as textual authority.

---

## 0. Governing invariant

> **No rule may become executable while its status is `PENDING_DOMAIN_REVIEW`,
> `BLOCKED_DOMAIN_SOURCE`, or `SOURCE_CONFLICT`.**

Corollaries, all currently binding on every rule in the pack:

- `manifest.executable` is `false` and `pack_control.derived_executable` is `false`; the
  executable flag may become `true` only when the blocker list in `pack_control.json` is empty.
- No source-conflict topic is resolved by an engineering default. Both candidate values are
  retained until a frozen edition + qualified reviewer adjudicate.
- `RAMAN-ENGINEERING` must **not** silently override a clearly adjudicated `MC-NORMATIVE` verse.
- Mangal / Kuja (Manglik) dosha stays **outside** the 36-point sum (DEC-019).
- Nadi is **constitutional-temperament framing only** — never medical / genetic / fertility /
  pregnancy / progeny / health (DEC-021).

## 0.1 Status vocabulary

| Adjudication status | Meaning | Present in this pack? |
|---|---|---|
| `DOMAIN_APPROVED` | Frozen source + reviewer sign-off; executable-eligible. | **No rule** |
| `DOMAIN_APPROVED_WITH_LIMITATION` | Approved but with a recorded scope caveat. | **No rule** |
| `PENDING_DOMAIN_REVIEW` | Structure documented; awaiting frozen source + reviewer. | Yes |
| `BLOCKED_DOMAIN_SOURCE` | A load-bearing value is not transcribable from any acquired source. | Yes |
| `SOURCE_CONFLICT` | Normative vs engineering candidates differ; not resolved. | Yes |
| `EXCLUDED_FROM_V1` | Deliberately out of v1 scope. | **No rule** |

## 0.2 Source hierarchy (authority order)

1. `MC-NORMATIVE` — *Muhurta Chintamani*, Melapaka Prakarana (normative classical authority).
2. `RAMAN-ENGINEERING` — B. V. Raman, *Muhurtha (Electional Astrology)* (engineering interpretation;
   must not silently override a clearly adjudicated MC verse).
3. `BPHS-XREF` — *Brihat Parashara Hora Shastra* (Naisargika natural friendship **only**).
4. `KALAPRAKASIKA-XREF` — *Kalaprakasika* (supplementary; only where exact page/verse evidence exists).

Editions are now **IDENTIFIED** (real, externally-verifiable candidate editions with ISBNs /
catalogue identifiers recorded in `rules/sources/GUNA_SOURCE_MANIFEST.json`), but **not frozen**:
`edition_identification = EDITION_IDENTIFIED_NOT_ACQUIRED`, `overall_status = PENDING_ACQUISITION`.
No copy has been acquired, opened, paginated, or reviewer-confirmed here, so every page/verse field
remains `null` / `PENDING`.

## 0.3 Pack-level counts (from `pack_control.json`)

| Count | Value |
|---|---|
| Traceability rules | 23 |
| Approved rules | 0 |
| Excluded rules | 0 |
| `BLOCKED_DOMAIN_SOURCE` rules | 3 |
| `PENDING_DOMAIN_REVIEW` rules | 16 |
| Source-conflict **rule-entries** | 6 |
| Source-conflict **topics** | 4 |
| Parihara rules | 6 (all `enabled: false`) |
| Manual cases / verified | 24 / 0 |

The 6 conflict rule-entries are: `vashya.rashi_to_group`, `vashya.group_score_matrix_5x5`,
`vashya.rashi_pair_12x12_canonical` (topic 1 — Vashya), `yoni.score_matrix_14x14` (topic 2 — Yoni),
`gana.score_matrix_3x3` (topic 3 — Gana), and `parihara.bhakoot_relief_lords_friends` (topic 4 —
Bhakoot friendly-lords relief).

---

## 1. Per-koota adjudication

Directional role ordering (which of bride / groom must hold the higher rank, or is the `from`/`to`
of a count) is bound to the neutral-role mapping `seeker → bride`, `partner → groom`, which is
**`confirmed: false` (OQ-2)**. Wherever a rule is directional, the role ordering is `PENDING (OQ-2)`.

### 1.1 Varna (max 1) — directional

**Sanskrit term:** Varna / Varan. **Literal meaning:** "class / caste-order" — here a temperament
grade (Brahmin > Kshatriya > Vaishya > Shudra as a scoring order only, not a social value judgement).
**Implementation interpretation:** Moon rashi → element → varna (water = Brahmin, fire = Kshatriya,
earth = Vaishya, air = Shudra); score 1 if the groom's varna rank ≥ the bride's, else 0.
**Regional applicability:** north_indian. **Exception / parihara dependencies:** none.

| Field | `varna.rashi_to_varna` | `varna.directional_scoring` |
|---|---|---|
| Rule type | classification_table | scoring_rule |
| Input → output | `moon_rashi` → varna class | `groom_varna_rank`, `bride_varna_rank` → {1, 0} |
| Maximum score | 1 | 1 |
| Directionality | directional (groom rank ≥ bride rank) | directional |
| Traditional role ordering | `PENDING (OQ-2)` | `PENDING (OQ-2)` — which role holds the higher rank flips the asymmetry |
| Intended source | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | NONE | NONE |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` | `PENDING` |

### 1.2 Vashya (max 2) — symmetric · **SOURCE_CONFLICT / BLOCKED** · see Dossier A

**Sanskrit term:** Vashya / Vasya. **Literal meaning:** "one who is controlled / brought under
sway" — mutual magnetic attraction / control between the two Moon rashis. **Implementation
interpretation:** rashi → one of five vashya groups (Chatushpada / Manava / Jalachara / Vanachara /
Keeta), scored 2 / 1 / 0.5 / 0. **Regional applicability:** north_indian. **Exception / parihara
dependencies:** none.

| Field | `vashya.rashi_to_group` | `vashya.group_score_matrix_5x5` | `vashya.rashi_pair_12x12_canonical` |
|---|---|---|---|
| Rule type | classification_table | score_matrix (reduction) | score_matrix (canonical) |
| Input → output | `moon_rashi` → group | `group_A`, `group_B` → {2,1,0.5,0} | `rashi_A`, `rashi_B` → {2,1,0.5,0} |
| Maximum score | 2 | 2 | 2 |
| Directionality | symmetric | symmetric | symmetric |
| Intended source | MC-NORMATIVE | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | SOURCE_CONFLICT | SOURCE_CONFLICT | SOURCE_CONFLICT |
| Adjudication status | `SOURCE_CONFLICT` | `SOURCE_CONFLICT` | `BLOCKED_DOMAIN_SOURCE` |
| v1 inclusion | `BLOCKED_DOMAIN_SOURCE` | `BLOCKED_DOMAIN_SOURCE` | `BLOCKED_DOMAIN_SOURCE` |
| Reviewer | `PENDING` | `PENDING` | `PENDING` |

Same-group (diagonal) = 2 is certain. The off-diagonal 1 / 0.5 / 0 cells and the choice between the
canonical 12×12 rashi-pair table and the 5×5 group reduction are the conflict (**Dossier A**). Half-
sign assignments (Sagittarius = Manava, Capricorn = Jalachara, Cancer = Jalachara) are source-variable
and must be verified against the frozen edition.

### 1.3 Tara (max 3) — directional · see role-ordering note

**Sanskrit term:** Tara / Dina. **Literal meaning:** "star / day" — health, longevity and fortune
from the 9-fold count between the two janma nakshatras. **Implementation interpretation:** inclusive
count mod 9 → tara number; auspicious taras {2,4,6,8,9}. Both directions auspicious → 3, exactly one
→ 1.5, neither → 0. **Regional applicability:** north_indian. **Exception / parihara dependencies:**
none.

| Field | `tara.nakshatra_count_9fold` | `tara.direction_convention` |
|---|---|---|
| Rule type | counting_rule | scoring_rule |
| Input → output | `from_nakshatra`, `to_nakshatra` → tara number | `bride_to_groom_tara`, `groom_to_bride_tara` → {3, 1.5, 0} |
| Maximum score | 3 | 3 |
| Directionality | directional (bidirectional count + combine) | directional |
| Traditional role ordering | `PENDING (OQ-2)` — from/to ordering unconfirmed | `PENDING (OQ-2)` — single-direction (bride-star-only) vs bidirectional-combine is school-variable |
| Intended source | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | NONE | NONE |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` | `PENDING` |

The `directionality_conflict` recorded in `tara.json` (which partner is `from`/`to`, and single- vs
bidirectional evaluation) is a **PENDING domain-review question tied to OQ-2**, not a numbered
source-conflict topic.

### 1.4 Yoni (max 4) — symmetric · **BLOCKED** · see Dossier B

**Sanskrit term:** Yoni. **Literal meaning:** "womb / source / animal-kind" — instinctive/physical
temperament via the animal assigned to each janma nakshatra (interpretation bounded to consensual
adult romantic context only; never sexualized or medicalized). **Implementation interpretation:**
27 nakshatra → 14 animal yonis; scored 4 (same) down to 0 (mortal enemy). **Regional applicability:**
north_indian. **Exception / parihara dependencies:** none.

| Field | `yoni.nakshatra_to_yoni` | `yoni.score_matrix_14x14` |
|---|---|---|
| Rule type | classification_table | score_matrix |
| Input → output | `janma_nakshatra` → yoni | `yoni_A`, `yoni_B` → {4,3,2,1,0} |
| Maximum score | 4 | 4 |
| Directionality | symmetric | symmetric |
| Intended source | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | NONE | SOURCE_CONFLICT |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `BLOCKED_DOMAIN_SOURCE` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `BLOCKED_DOMAIN_SOURCE` |
| Reviewer | `PENDING` | `PENDING` |

Diagonal (same yoni) = 4 and the 7 mortal-enemy pairs = 0 **are reliable**. Every other cell in the
14×14 matrix is a placeholder neutral `2`; the friendly(3) / unfriendly(1) gradations are **BLOCKED**
until transcribed from a frozen edition (**Dossier B**).

### 1.5 Graha Maitri (max 5) — symmetric

**Sanskrit term:** Graha Maitri / Rasyadhipati. **Literal meaning:** "planetary friendship / lord of
the sign" — mental and psychological compatibility from the **natural** friendship between the lords
of the two Moon rashis. **Implementation interpretation:** rashi → classical 7-planet lord (nodes not
used); combine the two directional Naisargika relations via a 6-band compound table. **Regional
applicability:** north_indian (the Naisargika matrix itself is pan-tradition). **Exception / parihara
dependencies:** none. **Hard rule:** use Naisargika (natural, permanent) friendship **only** —
exclude Tatkalika (temporary) and the Panchadha (five-fold) compound.

| Field | `graha_maitri.rashi_to_lord` | `graha_maitri.naisargika_matrix` | `graha_maitri.compound_table_6band` |
|---|---|---|---|
| Rule type | classification_table | friendship_matrix | score_matrix |
| Input → output | `moon_rashi` → lord | `lord_A`, `lord_B` → relation | `relation_ab`, `relation_ba` → {5,4,3,1,0.5,0} |
| Maximum score | 5 | 5 | 5 |
| Directionality | symmetric | symmetric (combines both directional relations) | symmetric |
| Intended source | MC-NORMATIVE | **BPHS-XREF** (Naisargika data only) | RAMAN-ENGINEERING |
| Source conflict | NONE | NONE | NONE |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` | `PENDING` | `PENDING` |

The 6-band compound point values (esp. `neutral+neutral = 3`) are a `RAMAN-ENGINEERING`
interpretation; some schools collapse the middle bands. This is `PENDING_DOMAIN_REVIEW`, not a
numbered source-conflict topic — but reviewer confirmation is required, and Raman must not override a
clearly adjudicated MC verse if one exists.

### 1.6 Gana (max 6) — directional · **SOURCE_CONFLICT** · see Dossier C

**Sanskrit term:** Gana. **Literal meaning:** "class / troop / host of beings" — temperament class
(Deva / Manushya / Rakshasa) from each partner's janma nakshatra, via a directional 3×3 matrix.
**Implementation interpretation:** 27 nakshatra → gana; look up (groom-row, bride-column).
**Regional applicability:** north_indian. **Exception / parihara dependencies:** none.

| Field | `gana.nakshatra_to_gana` | `gana.score_matrix_3x3` |
|---|---|---|
| Rule type | classification_table | score_matrix |
| Input → output | `janma_nakshatra` → gana | `groom_gana`, `bride_gana` → {6,5,3,1,0} + CONFLICT cell |
| Maximum score | 6 | 6 |
| Directionality | directional | directional (groom-row / bride-column) |
| Traditional role ordering | `PENDING (OQ-2)` | `PENDING (OQ-2)` — transpose if mapping reversed |
| Intended source | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | NONE | SOURCE_CONFLICT |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `SOURCE_CONFLICT` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` | `PENDING` |

Same gana on both sides = full 6. The directional asymmetry is real (e.g. Manushya-groom × Rakshasa-
bride = 0 but Rakshasa-groom × Manushya-bride = 3). Both Deva × Rakshasa cells (either role order)
are marked `CONFLICT`: MC candidate 0 vs Raman candidate 1 — **not chosen** (**Dossier C**).

### 1.7 Bhakoot (max 7) — symmetric · see Dossier D (relief) and §2 (cancellation)

**Sanskrit term:** Bhakoot / Bhakut / Rashi koota. **Literal meaning:** "sign-cluster / rashi
position" — emotional bonding, family welfare and prosperity from the mutual rashi-to-rashi position.
**Implementation interpretation:** penalized mutual count-pairs {2,12}, {5,9}, {6,8} → 0 (Bhakoot
dosha); all other positions → 7. **Regional applicability:** north_indian. **Exception / parihara
dependencies:** `bhakoot_cancel_same_rashi_lord`, `bhakoot_relief_lords_friends` (both in
`parihara.json`, disabled).

| Field | `bhakoot.count_pairs` |
|---|---|
| Rule type | counting_rule |
| Input → output | `rashi_A`, `rashi_B` → {7, 0} |
| Maximum score | 7 |
| Directionality | symmetric |
| Intended source | MC-NORMATIVE |
| Source conflict | NONE |
| Adjudication status | `PENDING_DOMAIN_REVIEW` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` |

Whether the three dosha types are weighted equally (uniform 0) or differentiated (6/8 and 2/12
regarded as more serious than 5/9 in some schools) is `PENDING_DOMAIN_REVIEW`. The **friendly-lords
relief** effect is the conflict, and it lives on the parihara rule (**Dossier D**), not on this rule.

### 1.8 Nadi (max 8) — symmetric · **DEC-021** · see §2 (cancellation)

**Sanskrit term:** Nadi. **Literal meaning:** "channel / pulse / current" — traditional
**constitutional-temperament** compatibility from the nadi (Aadi / Madhya / Antya) of each janma
nakshatra. **Implementation interpretation:** same nadi on both sides → 0 (Nadi dosha); different
nadi → 8. **Regional applicability:** north_indian. **Exception / parihara dependencies:**
`nadi_cancel_same_rashi_diff_nakshatra`, `nadi_cancel_same_nakshatra_diff_pada`,
`nadi_relief_lords_friends` (all in `parihara.json`, disabled). **DEC-021 hard constraint:**
constitutional framing only — never medical / genetic / fertility / pregnancy / progeny / health; the
Vata/Pitta/Kapha glosses are traditional labels only, not Ayurvedic diagnosis.

| Field | `nadi.nakshatra_to_nadi` | `nadi.scoring_rule` |
|---|---|---|
| Rule type | classification_table | scoring_rule |
| Input → output | `janma_nakshatra` → nadi | `nadi_A`, `nadi_B` → {8, 0} |
| Maximum score | 8 | 8 |
| Directionality | symmetric | symmetric |
| Intended source | MC-NORMATIVE | MC-NORMATIVE |
| Source conflict | NONE | NONE |
| Adjudication status | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| v1 inclusion | `PENDING_DOMAIN_REVIEW` | `PENDING_DOMAIN_REVIEW` |
| Reviewer | `PENDING` | `PENDING` |

---

## 2. Parihara (dosha-cancellation) rules — all `enabled: false`

The parihara model is an **ordered deterministic** model (documented in full in
`DILCHAT_PARIHARA_ADJUDICATION_REPORT.md`). It is summarized here only for adjudication status; every
rule ships disabled and none is executable.

| `rule_id` | Koota | Source | Effect | Priority | Adjudication status | v1 | Reviewer |
|---|---|---|---|---|---|---|---|
| `parihara.nadi_cancel_same_rashi_diff_nakshatra` | nadi | MC | cancel_dosha (numeric) | 10 | `PENDING_DOMAIN_REVIEW` | PENDING | `PENDING` |
| `parihara.nadi_cancel_same_nakshatra_diff_pada` | nadi | MC | cancel_dosha (numeric) | 11 | `PENDING_DOMAIN_REVIEW` | PENDING | `PENDING` |
| `parihara.nadi_relief_lords_friends` | nadi | RAMAN | partial_relief_interpretive | 30 | `BLOCKED_DOMAIN_SOURCE` | PENDING | `PENDING` |
| `parihara.bhakoot_cancel_same_rashi_lord` | bhakoot | MC | cancel_dosha (numeric) | 10 | `PENDING_DOMAIN_REVIEW` | PENDING | `PENDING` |
| `parihara.bhakoot_relief_lords_friends` | bhakoot | RAMAN | cancel **vs** relief (conflict) | 20 | `SOURCE_CONFLICT` | PENDING | `PENDING` |
| `parihara.mangal_dosha_separate_flag` | external_mangal | RAMAN | no_numeric_change (separate flag) | 99 | `PENDING_DOMAIN_REVIEW` | PENDING | `PENDING` |

`parihara.bhakoot_relief_lords_friends` carries **Dossier D**. Mangal / Kuja dosha is a separate
report flag only and is **never** folded into or cancelled by the 36-point Guna score (DEC-019).

---

## 3. Four source-conflict dossiers

There are exactly **four conflict topics** carried across **six** traceability rule-entries. Each
dossier records both competing interpretations, the source hierarchy that will decide it, the
evidence required to resolve it, an **empty** reviewer-adjudication slot, the **not-yet-selected** v1
rule, rejected alternatives (**none yet** — nothing has been rejected because nothing has been
adjudicated), and the product implication. **No dossier is resolved.**

### Dossier A — Vashya table form and off-diagonal gradations

- **Rule-entries:** `vashya.rashi_to_group`, `vashya.group_score_matrix_5x5`,
  `vashya.rashi_pair_12x12_canonical`.
- **Competing interpretations:**
  - **A1 (canonical):** the classical form is a **12×12 rashi-pair Vashya table** — each rashi
    "controls"/attracts specific rashis with graded values. Not transcribed here.
  - **A2 (reduction):** a widely-circulated **5×5 vashya-group reduction** (Chatushpada / Manava /
    Jalachara / Vanachara / Keeta), whose off-diagonal 1 / 0.5 / 0 cells are source-variable across
    printings. Same-group (diagonal) = 2 is certain in both.
- **Source hierarchy to decide it:** `MC-NORMATIVE` governs the canonical form and any graded cell;
  `RAMAN-ENGINEERING` may supply the reduction only where it does not override a clearly adjudicated
  MC verse. Half-sign assignments (Sagittarius, Capricorn, Cancer) must be read from the frozen MC
  edition.
- **Evidence needed to resolve:** the Melapaka Prakarana Vashya passage / table from a frozen MC
  edition (verse + page), read by a Sanskrit-competent reviewer; confirmation of whether the tradition
  scores by rashi-pair or by group; and the exact off-diagonal gradation values.
- **Reviewer adjudication:** _(empty — PENDING)_ · reviewer = `PENDING` · date = `PENDING`.
- **Selected v1 rule:** _(none selected — PENDING)_.
- **Rejected alternatives:** _(none — nothing rejected yet)_.
- **Product implication:** Vashya (max 2) contributes nothing until resolved; both matrix rules are
  `BLOCKED_DOMAIN_SOURCE` for v1 inclusion. A wrong reduction would silently mis-score every couple
  whose rashis fall in differing groups.

### Dossier B — Yoni intermediate gradations (friendly-3 vs unfriendly-1)

- **Rule-entry:** `yoni.score_matrix_14x14`.
- **Competing interpretations:** which off-diagonal, non-mortal-enemy cells of the 14×14 matrix are
  **friendly (3)**, **neutral (2)**, or **unfriendly (1)**. The **diagonal (same yoni) = 4** and the
  **7 mortal-enemy pairs = 0** are reliable and are **not** in conflict; only the intermediate
  gradations are. All intermediate cells currently hold a placeholder neutral `2`.
- **Source hierarchy to decide it:** `MC-NORMATIVE` graded 14×14 Yoni table governs; engineering
  tabulations (`RAMAN-ENGINEERING`) vary in which pairs are friendly(3) vs unfriendly(1) and may be
  used only where they do not override MC.
- **Evidence needed to resolve:** the complete classical 14×14 Yoni compatibility table transcribed
  from a frozen edition (verse/page), with each intermediate cell's 3/2/1 value confirmed by a
  reviewer.
- **Reviewer adjudication:** _(empty — PENDING)_ · reviewer = `PENDING` · date = `PENDING`.
- **Selected v1 rule:** _(none selected — PENDING)_.
- **Rejected alternatives:** _(none — nothing rejected yet)_.
- **Product implication:** Yoni (max 4) is `BLOCKED_DOMAIN_SOURCE`. The reliable cells alone cannot
  produce a defensible 0–4 score, so Yoni cannot be executed until the gradations are transcribed.

### Dossier C — Gana Deva × Rakshasa cell (0 vs 1)

- **Rule-entry:** `gana.score_matrix_3x3`.
- **Competing interpretations:** the Deva × Rakshasa cell (in **both** role orders — Deva-groom ×
  Rakshasa-bride and Rakshasa-groom × Deva-bride) is either **0 (MC candidate)** or **1 (Raman
  candidate)**. All other cells of the directional 3×3 are agreed.
- **Source hierarchy to decide it:** `MC-NORMATIVE` (candidate 0) is normative; `RAMAN-ENGINEERING`
  (candidate 1) is an engineering table and must not silently override a clearly adjudicated MC verse.
  The directional orientation (groom-row / bride-column) is additionally bound to **OQ-2** — if the
  confirmed role mapping is reversed, the matrix transposes.
- **Evidence needed to resolve:** the Gana scoring passage from a frozen MC edition (verse + page)
  confirming the Deva × Rakshasa value, plus the corresponding Raman table page, adjudicated together;
  and OQ-2 role-mapping confirmation for the directional orientation.
- **Reviewer adjudication:** _(empty — PENDING)_ · reviewer = `PENDING` · date = `PENDING`.
- **Selected v1 rule:** _(none selected — PENDING; cell remains `CONFLICT`)_.
- **Rejected alternatives:** _(none — neither 0 nor 1 rejected yet)_.
- **Product implication:** Gana (max 6) is `SOURCE_CONFLICT`. Couples with one Deva and one Rakshasa
  nakshatra cannot be scored until the cell is adjudicated; a premature default of either value would
  mis-score exactly those couples.

### Dossier D — Bhakoot friendly-lords relief (full cancellation vs interpretive relief)

- **Rule-entry:** `parihara.bhakoot_relief_lords_friends` (priority 20, `NON_STACKING`, disabled).
- **Competing interpretations:** when Bhakoot dosha is present and the two rashi lords are mutual
  friends (and it is **not** the same-lord case), some schools treat this as a **full numeric
  cancellation** (restore 7); others as **interpretive relief only** (severity wording softened,
  numeric score unchanged at 0). This is a conflict over the **effect**, not over a table value.
- **Source hierarchy to decide it:** `MC-NORMATIVE` governs whether a numeric cancellation is
  classically warranted; `RAMAN-ENGINEERING` (the rule's stated source) may support relief only where
  it does not override MC. The same-lord cancellation `bhakoot_cancel_same_rashi_lord` (priority 10,
  numeric) is a listed mutual exclusion and pre-empts this rule when it fires.
- **Evidence needed to resolve:** the Bhakoot cancellation passage(s) from a frozen MC edition (and
  the Raman treatment), read by a reviewer, confirming whether friendly-lords yields numeric
  cancellation or interpretive relief.
- **Reviewer adjudication:** _(empty — PENDING)_ · reviewer = `PENDING` · date = `PENDING`.
- **Selected v1 rule:** _(none selected — PENDING; effect remains `SOURCE_CONFLICT`)_.
- **Rejected alternatives:** _(none — neither effect rejected yet)_.
- **Product implication:** whether a couple with Bhakoot dosha and friendly lords keeps a 0 or is
  restored to 7 depends entirely on this unresolved effect. The rule stays `enabled: false`; until
  resolved, Bhakoot dosha with friendly (non-same) lords resolves to `DOSHA_PRESENT` /
  `REQUIRES_DOMAIN_REVIEW`, never to a silent cancellation.

---

## 4. Reviewer sign-off ledger (all PENDING)

| Koota / model | Adjudication status | Reviewer | Sign-off date |
|---|---|---|---|
| Varna | `PENDING_DOMAIN_REVIEW` | `PENDING` | `PENDING` |
| Vashya | `SOURCE_CONFLICT` / `BLOCKED_DOMAIN_SOURCE` | `PENDING` | `PENDING` |
| Tara | `PENDING_DOMAIN_REVIEW` | `PENDING` | `PENDING` |
| Yoni | `BLOCKED_DOMAIN_SOURCE` | `PENDING` | `PENDING` |
| Graha Maitri | `PENDING_DOMAIN_REVIEW` | `PENDING` | `PENDING` |
| Gana | `SOURCE_CONFLICT` | `PENDING` | `PENDING` |
| Bhakoot | `PENDING_DOMAIN_REVIEW` | `PENDING` | `PENDING` |
| Nadi | `PENDING_DOMAIN_REVIEW` | `PENDING` | `PENDING` |
| Parihara (all rules) | `PENDING_DOMAIN_REVIEW` / `BLOCKED` / `SOURCE_CONFLICT` (disabled) | `PENDING` | `PENDING` |

**No koota is approved. No rule is executable. All four source conflicts remain unresolved. The whole
pack is blocked pending edition freeze + qualified domain review.**

## 5. Related artifacts

- `rules/ashtakoota_muhurta_chintamani_raman_v1/source_traceability.json` — machine-readable per-rule mapping (source of truth).
- `rules/ashtakoota_muhurta_chintamani_raman_v1/manifest.json`, `parihara.json`, `pack_control.json`, and the eight per-koota JSON files.
- `rules/sources/GUNA_SOURCE_MANIFEST.json` — identified candidate editions (ISBNs / catalogue IDs), not frozen.
- `docs/DILCHAT_PARIHARA_ADJUDICATION_REPORT.md` — the ordered deterministic parihara model.
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — human-readable rule → source matrix.
- `docs/DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md` and `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md`.
