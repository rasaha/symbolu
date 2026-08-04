# DilChat Guna Milan — v1 Tradition Scope

**Pack:** `ashtakoota_muhurta_chintamani_raman_v1` · **Draft:** yes · **Executable:** no ·
**Authority gate:** `BLOCKED (pending edition freeze + domain review)`.

This document states **precisely what DilChat v1 claims to implement** — the one tradition it selects,
the conventions it fixes, and the boundaries it will not cross. It exists so the product never
overclaims. Where a choice is a founder or domain-reviewer decision, it is flagged **PENDING** and is
**not** decided here.

> **Scope honesty.** DilChat v1 is **not** universal, pan-Indian, or tradition-neutral. It implements
> **one explicitly selected North-Indian Ashtakoota tradition**, derived from the (not-yet-frozen)
> *Muhurta Chintamani* normative text and B. V. Raman's engineering interpretation. Other regional
> traditions and other classical authorities can and do produce **different** results. No claim below
> is executable until the source editions are FROZEN and a qualified Jyotisha + Sanskrit reviewer has
> signed off.

---

## 1. Recommended product wording

Use this wording (or a legal/founder-approved variant) wherever the compatibility method is described
to users:

> **"DilChat Classical Ashtakoota v1 implements one explicitly selected textual tradition derived from
> the frozen Muhurta Chintamani edition and its approved engineering interpretation. Other regional
> traditions may produce different results."**

This wording presumes a **frozen** edition; until freeze it must not be shown as a live product claim.

---

## 2. What v1 claims to implement (item by item)

| # | Dimension | v1 claim | Decision status |
|---|---|---|---|
| 1 | Matching family | **Ashtakoota** (8 kootas, 36-point) — **not** a blended Dasakoota/Dashakoota system | Fixed by pack; founder-confirmation **PENDING** (OQ-1) |
| 2 | Regional tradition | **North-Indian**, per the MC normative text | Founder-confirmation **PENDING** (OQ-1) |
| 3 | Directional orientation | Default seeker→bride, partner→groom | **PENDING** (OQ-2, DEC-009a) |
| 4 | Zodiac | **Sidereal** | Accepted (DEC-008) |
| 5 | Ayanamsa | **Lahiri** | Accepted (DEC-008) |
| 6 | Nakshatra scheme | **27-fold**; **Abhijit excluded** | Founder/domain-confirmation **PENDING** |
| 7 | Planetary friendship | **Naisargika (natural) ONLY**; Tatkalika (temporary) excluded | **PENDING_DOMAIN_REVIEW** |
| 8 | Regional exceptions | North-Indian only; South-Indian Dashakoota variants **excluded** | **PENDING** (OQ-1) |
| 9 | Parihara (dosha cancellation) | Defined but **all disabled** in v1 | **PENDING** (see §9) |
| 10 | Same-sex / role-neutral | **Unsupported / separately-defined**; deferred to founder | **PENDING** (see §10) |
| 11 | Unknown/approximate birth time | Eligibility **gated** by nakshatra determinacy | **PENDING** confirmation (see §11) |
| 12 | Boundary-uncertain natal | Excluded from a definite score when the interval crosses a nakshatra/pada boundary | **PENDING** confirmation (see §12) |

Each item is expanded below.

### 2.1 Ashtakoota, not a blended Dasakoota system

v1 implements the **eight-koota, 36-point** Ashtakoota family (Varna 1, Vashya 2, Tara 3, Yoni 4,
Graha Maitri 5, Gana 6, Bhakoot 7, Nadi 8). It does **not** implement the South-Indian **Dashakoota**
(ten-koota) system, and it does **not** blend the two. Mixing koota sets across traditions is
explicitly out of scope. The Ashtakoota 36-point family is also kept **entirely separate** from Mangal
/ Kuja dosha and every other score family — never folded together (**DEC-019**; Mangal is a separate
flag only, outside the 36-point sum).

### 2.2 Selected tradition: North-Indian (per MC normative)

The selected tradition is **North-Indian Ashtakoota**, taking the *Muhurta Chintamani* Melapaka
Prakarana as normative and B. V. Raman's *Muhurtha* as the engineering interpretation. **Founder
confirmation of this selection is PENDING (OQ-1).** The pack must not be described as representing
"Vedic astrology" generally, or all of India; it is one regional reading among several.

### 2.3 Bride/groom directional orientation (OQ-2 — PENDING)

Three kootas are directional: **Varna** (groom rank ≥ bride rank), **Tara** (from/to counting
anchor), and **Gana** (groom-row / bride-column 3×3). v1 stores partner **roles neutrally**
(`role: "seeker" | "partner"`) and maps them to the classical bride/groom ordering per the pack
(**DEC-009a**). The **default** mapping is seeker→bride, partner→groom, but this mapping is
**UNCONFIRMED (OQ-2)**; reversing it transposes the Gana matrix, flips which role may lose the Varna
point, and changes the Tara counting anchor. **This is a founder + domain decision and is not made
here.**

### 2.4 Sidereal zodiac + Lahiri ayanamsa (DEC-008)

All positions are computed in the **sidereal** zodiac using the **Lahiri** ayanamsa. This is accepted
(DEC-008) and is consistent across the astronomy engine and the rule pack. (Swiss Ephemeris production
licensing is a **separate open external gate — OQ-10 / DEC-007** — and does not change the ayanamsa
policy.)

### 2.5 Nakshatra scheme: 27-fold, Abhijit excluded

v1 uses the **27-nakshatra** scheme. The 28th nakshatra **Abhijit is excluded** from koota
classification (Yoni, Tara, Gana, Nadi all key off the 27-fold scheme). Founder/domain confirmation of
this convention is **PENDING**.

### 2.6 Natural vs temporary planetary friendship: Naisargika ONLY

Graha Maitri uses **Naisargika (natural) friendship ONLY**, cross-referenced from BPHS. **Tatkalika
(temporary)** and **Panchadha (compound five-fold)** friendship are **excluded** — they must not be
folded into the Graha Maitri score. Confirmation of Naisargika-only and the exact 6-band compound point
values is **PENDING_DOMAIN_REVIEW**.

### 2.7 Regional exceptions: North-Indian included, South-Indian excluded

Only North-Indian Ashtakoota rules are in scope. **South-Indian Dashakoota variants and additional
regional kootas are excluded (OQ-1).** The *Kalaprakasika* cross-reference (a South-Indian electional
system) is **supplementary only** and must never be silently blended into the North-Indian tradition.
Regional North/South differences are recorded per rule; their resolution is **PENDING**.

### 2.8 Parihara (dosha cancellation): included in the model, all currently disabled

The parihara (dosha-cancellation / relief) model is defined with a deterministic ordered precedence
(no weighted accumulation), but **every parihara rule is `enabled: false` in v1**. See §9 and
`docs/DILCHAT_PARIHARA_PRECEDENCE_AND_STACKING.md`.

### 2.9 Same-sex / role-neutral / non-traditional-bride-groom relationships

The classical Ashtakoota model is defined over a **traditional bride/groom** pairing with directional
asymmetries (Varna, Tara, Gana). For **same-sex or otherwise role-neutral** relationships DilChat v1
makes **no** classical claim:

- It does **not** invent a symmetric classical result (e.g. averaging or symmetrizing the directional
  kootas) and present it as traditional.
- It does **not** claim the traditional model is preserved unchanged when the bride/groom roles do not
  map to the partners.
- The methodology for such relationships is marked **unsupported / separately-defined**, and the
  decision on whether and how to offer it is **deferred to the founder** (and, for any classical
  framing, to domain review). No such method is enabled in v1.

### 2.10 Unknown / approximate birth-time eligibility

A Guna score is offered only when the inputs determine each partner's Moon **nakshatra (and pada where
a rule needs it)** unambiguously. When birth time is unknown or approximate such that the natal-Moon
nakshatra cannot be pinned, v1 does **not** guess a nakshatra to force a score; eligibility is gated on
determinacy. The exact eligibility thresholds are **PENDING** confirmation and interact with the
birth-time uncertainty interval model (see the astronomy engine spec and interval-completeness proof).

### 2.11 Boundary-uncertain natal handling

When the birth-time uncertainty interval spans a **nakshatra or pada boundary** (so more than one
classification is possible), v1 must **not** collapse to one side silently. The pair is treated as
boundary-uncertain and is **not** given a single definite Guna score for the affected koota(s); the
uncertainty is surfaced rather than hidden. Exact presentation is **PENDING** confirmation.

---

## 3. Explicit non-claims

DilChat v1 does **NOT** claim to:

- be universal, pan-Indian, or tradition-neutral;
- implement or blend the South-Indian Dashakoota (ten-koota) system;
- produce a medically, genetically, fertility-, pregnancy-, progeny-, or health-relevant reading from
  **Nadi** — Nadi is **constitutional-temperament framing ONLY (DEC-021)**, never medical;
- fold Mangal / Kuja dosha (or any other score family) into the 36-point Ashtakoota sum (**DEC-019**);
- resolve the four open source conflicts (Vashya table form; Yoni friendly/unfriendly gradations; Gana
  Deva×Rakshasa 0-vs-1; Bhakoot friendly-lords cancel-vs-relief) — all remain `resolution: PENDING`;
- offer a validated symmetric or role-neutral classical result;
- be executable before source editions are FROZEN and domain-reviewed.

---

## 4. Founder / domain decisions still PENDING (not decided here)

- **OQ-1** — Confirm North-Indian Ashtakoota only vs adding a South-Indian Dashakoota variant.
- **OQ-2 / DEC-009a** — Confirm the seeker/partner → bride/groom directional mapping.
- **MC + Raman edition selection** — Confirm and freeze the exact editions/printings (see the
  acquisition report and edition-freeze doc).
- **Nakshatra convention** — Confirm 27-fold with Abhijit excluded.
- **Graha Maitri** — Confirm Naisargika-only and the 6-band compound point values.
- **Four source conflicts** — Resolve each with a cited decision.
- **Parihara set** — Decide which (if any) pariharas are enabled and confirm precedence.
- **Nadi wording (DEC-021)** — Confirm constitutional-only framing and disclaimer wording (legal
  review).
- **Role-neutral / same-sex methodology** — Decide whether to offer it and, if so, how it is defined
  and labelled.
- **Birth-time eligibility + boundary handling** — Confirm determinacy thresholds and presentation.

**Every item above is PENDING. None is decided in this document.**

---

## 5. Related artifacts

- `rules/sources/GUNA_SOURCE_MANIFEST.json` — machine-readable edition record (`v2`).
- `docs/DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md` — acquisition narrative + checklist.
- `docs/DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md` — freeze-status summary.
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — per-rule → source mapping and every conflict.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md` — reviewer package and sign-off template.
- `docs/DILCHAT_PARIHARA_PRECEDENCE_AND_STACKING.md` — parihara ordered-precedence model.
- `docs/DILCHAT_DECISION_LOG.md` — DEC-008, DEC-009/009a, DEC-019, DEC-021; OQ-1, OQ-2, OQ-10.
