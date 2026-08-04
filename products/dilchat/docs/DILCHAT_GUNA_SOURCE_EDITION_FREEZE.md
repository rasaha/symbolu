# DilChat Guna Milan — Source Edition Freeze

**Status: `PENDING_ACQUISITION` — NO edition is frozen. NO source has been physically acquired or verified in this environment.**

This document summarizes the bibliographic edition-freeze record for the DilChat v1 Ashtakoota
(Guna Milan) rule pack `ashtakoota_muhurta_chintamani_raman_v1`. It is derived from
`rules/sources/GUNA_SOURCE_MANIFEST.json`.

> **Honesty statement.** Nothing below is approved. No page number, verse number, or edition
> identifier has been confirmed. Every source is `PENDING_ACQUISITION`; every rule that cites a
> source is `PENDING_DOMAIN_REVIEW`, `BLOCKED_DOMAIN_SOURCE`, or `SOURCE_CONFLICT`. Internet
> consensus is **not** accepted as textual authority.

---

## 1. Frozen-status legend

| Status | Meaning |
|---|---|
| `FROZEN_PRIMARY` | Normative classical edition physically acquired, verified, and locked. **Not reached.** |
| `FROZEN_ENGINEERING` | Engineering-interpretation edition acquired and locked. **Not reached.** |
| `FROZEN_CROSS_REFERENCE` | Cross-reference edition acquired and locked. **Not reached.** |
| `PENDING_ACQUISITION` | Intended source named; not yet acquired or verified. **Current state of all sources.** |
| `PENDING_DOMAIN_REVIEW` | Awaiting qualified Jyotisha + Sanskrit reviewer sign-off. |
| `REJECTED_SOURCE` | Considered and rejected as authority. |

**Overall status: `PENDING_ACQUISITION`.**

---

## 2. Intended source hierarchy

The pack declares a strict authority order. Where the normative and engineering sources are known
to differ, the difference is recorded as `SOURCE_CONFLICT` and **both** candidate values are kept —
it is never silently resolved.

| Rank | Source ID | Role | Canonical title | Author / translator | Status |
|---|---|---|---|---|---|
| 1 | `MC-NORMATIVE` | Normative classical authority | *Muhurta Chintamani*, Melapaka Prakarana | Rama Daivajna | `PENDING_ACQUISITION` |
| 2 | `RAMAN-ENGINEERING` | Engineering interpretation | *Muhurtha (Electional Astrology)*, Marriage Adaptability | B. V. Raman | `PENDING_ACQUISITION` |
| 3 | `BPHS-XREF` | Foundational cross-reference (Naisargika friendship only) | *Brihat Parashara Hora Shastra* | attr. Parashara (tr. e.g. R. Santhanam) | `PENDING_ACQUISITION` |
| 4 | `KALAPRAKASIKA-XREF` | Supplementary cross-check (only where exact page/verse exists) | *Kalaprakasika* | tr. N. P. Subramania Iyer | `PENDING_ACQUISITION` |

For each source, the edition-specific fields (`publisher`, `publication_year`, `edition_number`,
`isbn_or_identifier`, `page_range`, `verse_range`, `acquisition_date`, `file_checksum`) are **`null`**.
They remain `null` until a physical copy is acquired and frozen.

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
are recorded in `GUNA_SOURCE_MANIFEST.json`:

1. Exact edition selected (publisher, year, edition number, ISBN/identifier).
2. Physical copy acquired; `acquisition_date` set.
3. `file_checksum` recorded for any privately-held (non-committed) scan used at review time.
4. Relevant `chapter` / `verse_range` / `page_range` filled for every rule that cites it.
5. Qualified Jyotisha + Sanskrit reviewer sign-off recorded (see the Domain Review Package).

Until then the pack is `draft: true`, `executable: false`, `authority_gate: "BLOCKED"`.

---

## 5. Related artifacts

- `rules/sources/GUNA_SOURCE_MANIFEST.json` — the machine-readable edition-freeze record.
- `rules/ashtakoota_muhurta_chintamani_raman_v1/source_traceability.json` — per-rule source mapping.
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — human-readable rule → source matrix.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md` — reviewer package and sign-off template.
