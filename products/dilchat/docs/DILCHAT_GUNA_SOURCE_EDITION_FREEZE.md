# DilChat Guna Milan — Source Edition Freeze

**Status: `PENDING_ACQUISITION` — editions are now IDENTIFIED (real ISBNs / catalogue IDs), but NO
edition is frozen. NO source has been acquired, opened, paginated, or verified in this environment.**

This document summarizes the bibliographic edition-freeze record for the DilChat v1 Ashtakoota
(Guna Milan) rule pack `ashtakoota_muhurta_chintamani_raman_v1`. It is derived from
`rules/sources/GUNA_SOURCE_MANIFEST.json` (`guna_source_manifest_v2`), and the full acquisition
narrative is in `docs/DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md`.

> **Honesty statement.** Nothing below is approved. Specific candidate editions have now been
> **identified** from catalogue metadata (publisher / translator / ISBN / archive identifier), but no
> page number, verse number, printing, or edition identity has been **confirmed** — no copy was
> acquired or opened here (Internet Archive content endpoints returned HTTP 403 through the environment
> proxy). Every source is `PENDING_ACQUISITION` with `edition_identification: EDITION_IDENTIFIED_NOT_
> ACQUIRED`; every rule that cites a source is `PENDING_DOMAIN_REVIEW`, `BLOCKED_DOMAIN_SOURCE`, or
> `SOURCE_CONFLICT`. Internet consensus is **not** accepted as textual authority.

---

## 1. Frozen-status legend

| Status | Meaning |
|---|---|
| `FROZEN_PRIMARY` | Normative classical edition physically acquired, verified, and locked. **Not reached.** |
| `FROZEN_ENGINEERING` | Engineering-interpretation edition acquired and locked. **Not reached.** |
| `FROZEN_CROSS_REFERENCE` | Cross-reference edition acquired and locked. **Not reached.** |
| `PENDING_ACQUISITION` | Source named; not yet acquired or verified. **Current overall state of all sources.** |
| `PENDING_DOMAIN_REVIEW` | Awaiting qualified Jyotisha + Sanskrit reviewer sign-off. |
| `REJECTED_SOURCE` | Considered and rejected as authority. |

### Edition-identification legend (distinct from freeze status)

| Value | Meaning |
|---|---|
| `EDITION_IDENTIFIED_NOT_ACQUIRED` | A specific, real, citable edition has been identified from catalogue metadata, but no copy has been acquired and no page opened or verified here. **Current state of all four sources.** |
| `ACQUIRED_PENDING_VERIFICATION` | A copy is legally in hand, but pagination / identity / usability is not yet reviewer-confirmed. **Not reached.** |
| `FROZEN_ANY` | Edition known, pages accessible, pagination stable, identity unambiguous, immutable checksum/permalink recorded, text usable for adjudication, reviewer confirmed. **Not reached.** |

**Overall status: `PENDING_ACQUISITION`.** Identifying an edition is **not** acquiring or freezing it.

---

## 2. Intended source hierarchy

The pack declares a strict authority order. Where the normative and engineering sources are known
to differ, the difference is recorded as `SOURCE_CONFLICT` and **both** candidate values are kept —
it is never silently resolved.

| Rank | Source ID | Role | Canonical title | Author / translator | Freeze status |
|---|---|---|---|---|---|
| 1 | `MC-NORMATIVE` | Normative classical authority | *Muhurta Chintamani*, Melapaka Prakarana | Rama Daivajna | `PENDING_ACQUISITION` |
| 2 | `RAMAN-ENGINEERING` | Engineering interpretation | *Muhurtha (Electional Astrology)*, Marriage Adaptability | B. V. Raman | `PENDING_ACQUISITION` |
| 3 | `BPHS-XREF` | Foundational cross-reference (Naisargika friendship only) | *Brihat Parashara Hora Shastra* | attr. Parashara (tr. R. Santhanam) | `PENDING_ACQUISITION` |
| 4 | `KALAPRAKASIKA-XREF` | Supplementary cross-check (only where exact page/verse exists) | *Kalaprakasika* | tr. N. P. Subramania Iyer | `PENDING_ACQUISITION` |

### Identified candidate editions (real metadata — not yet acquired)

Each row is `edition_identification: EDITION_IDENTIFIED_NOT_ACQUIRED`. See the acquisition report for
sourcing, catalogue URLs, and copyright posture.

| Source ID | Candidate edition | Publisher / year | ISBN / identifier |
|---|---|---|---|
| `MC-NORMATIVE` (English bridge) | tr. Girish Chand Sharma (Sanskrit + English, commentary) | Sagar Publications, 1996 | ISBN **PENDING**; Open Library `OL63483W` |
| `MC-NORMATIVE` (Sanskrit reference) | w/ Pt. Kapileshwar Shastri (Sanskrit) | Haridas Sanskrit Series #185, Chowkhamba; year **PENDING** | archive item `muhurt-chintamani-...-185-haridas-sanskrit-series` (content 403, not opened) |
| `RAMAN-ENGINEERING` (primary) | B. V. Raman, *Muhurtha (Electional Astrology)* | UBSPD, 1993 (cited 13th ed./reprint) | ISBN-13 978-8185674681 / ISBN-10 818567468X |
| `RAMAN-ENGINEERING` (alternate) | B. V. Raman, MLBD reprint | Motilal Banarsidass; year **PENDING** | ISBN 9789359662923 (also 9789359661070) |
| `BPHS-XREF` | tr. R. Santhanam, 2-vol set (Naisargika friendship only) | Ranjan Publications, 1984 | ISBN-13 978-8188230600 / ISBN-10 818823060X |
| `KALAPRAKASIKA-XREF` | tr. N. P. Subramania Iyer (reprint of 1917 ed.) | Gyan Publishing House / Asian Educational Services; year **PENDING** | ISBN 9788121236591 (pb) / 9788121236607 (hb) |

**Note on Raman printings:** table pagination differs between the UBSPD and MLBD printings; exactly
**one** printing must be pinned before any page citation is recorded.

Beyond the identified edition and ISBN/identifier above, the freeze-critical fields
(`edition_number`/printing confirmation, `page_range`, `verse_range`, `chapter`, `acquisition_date`,
`file_checksum`) remain **PENDING / `null`**. They stay unfilled until a copy is acquired, opened,
reviewer-verified, and frozen.

---

## 3. Committed-evidence policy (no copyrighted scans)

Per `GUNA_SOURCE_MANIFEST.json`:

- **Allowed in the repository:** bibliographic metadata, page/verse *references*, brief
  copyright-compliant quotations added at review time, reviewer notes, file hashes, and acquisition
  records.
- **Prohibited in the repository:** full scans or OCR of copyrighted works (*Muhurtha* by Raman and
  most translation editions of BPHS / Kalaprakasika are in copyright). No book text or scan is
  committed with this pack.
- **Rejected as authority:** blogs, mobile apps, AI summaries, anonymous websites, and uncorrected
  OCR. These may never be cited as rule authority.

---

## 4. What "freeze" will require

A source moves from `PENDING_ACQUISITION` to a `FROZEN_*` status only when **all** of the following
are recorded in `GUNA_SOURCE_MANIFEST.json`. Step 1 is now **partially** advanced (candidate editions
and ISBNs identified); the printing pin and everything from step 2 onward remain **PENDING**.

1. Exact edition selected (publisher, year, edition number/printing, ISBN/identifier) — candidates
   identified; final printing pin **PENDING**.
2. Physical (or authorized-digital) copy acquired; `acquisition_date` set.
3. `file_checksum` recorded for any privately-held (non-committed) scan used at review time.
4. Relevant `chapter` / `verse_range` / `page_range` filled for every rule that cites it.
5. Qualified Jyotisha + Sanskrit reviewer sign-off recorded (see the Domain Review Package).

Until then the pack is `draft: true`, `executable: false`, `authority_gate: "BLOCKED"`.

---

## 5. Related artifacts

- `rules/sources/GUNA_SOURCE_MANIFEST.json` — the machine-readable edition-freeze record (`v2`).
- `docs/DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md` — full acquisition narrative, environment
  limitation, and the human acquire-and-freeze checklist.
- `docs/DILCHAT_GUNA_V1_TRADITION_SCOPE.md` — precisely what DilChat v1 claims to implement.
- `rules/ashtakoota_muhurta_chintamani_raman_v1/source_traceability.json` — per-rule source mapping.
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — human-readable rule → source matrix.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md` — reviewer package and sign-off template.

---

## Update — Source-material gate: `SOURCE_MATERIAL_REQUIRED`

No source has moved toward `FROZEN`. In this environment no source pages are
lawfully available (bibliographic metadata only; Internet Archive content
403-blocked; no purchase/library/archive/user-provided pages), so rule adjudication
is not performed. A new status `ACQUIRED_PENDING_TEXT_VERIFICATION` is added to the
manifest for the point at which a lawful copy is in hand (provenance recorded via
`scripts/source_intake.py`) but the text is not yet reviewer-verified — this is
**still not frozen**. All four sources remain `EDITION_IDENTIFIED_NOT_ACQUIRED`;
overall status stays `PENDING_ACQUISITION`. See
`DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md` for the acquisition checklist.
