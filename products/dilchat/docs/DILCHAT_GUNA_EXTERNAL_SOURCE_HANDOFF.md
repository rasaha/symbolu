# DilChat Guna — External Source Acquisition Handoff

**Status: `SOURCE_MATERIAL_REQUIRED`.** This document is the acquisition brief a
human (founder / researcher / librarian) must fulfil **outside this environment**
before any Guna rule can be adjudicated. Nothing here is adjudicated, frozen, or
approved. Until the minimum package below is supplied, the Guna authority and
rule-pack verdicts remain **BLOCKED** and no Guna engine may be built.

> **Copyright & repository boundary.** Do **not** commit whole books, full scans,
> or substantial extracts. Retain acquired copies **outside Git**. Only sanitized
> provenance (SHA-256 + edition identity via `scripts/source_intake.py`),
> bibliographic metadata, page/verse references, brief legally-appropriate
> quotations, and reviewer notes may enter the repository. Local file paths must
> never appear in committed files.

## How acquired material is recorded (lawful intake)

For every acquired copy, run the approved intake utility (it does **not** copy the
file into the repo and never records the local path):

```bash
python scripts/source_intake.py \
  --file /path/to/lawful/copy.pdf \
  --source-id MC-NORMATIVE \
  --edition "<exact edition identity>" \
  --acquisition-method purchased_ebook \   # or purchased_physical | library_access |
                                           # lawful_archive_access | user_provided_excerpt |
                                           # professional_transcription
  --access-date YYYY-MM-DD
```

The utility emits `freeze_status: ACQUIRED_PENDING_TEXT_VERIFICATION` — **never**
`FROZEN_*`. A source becomes `FROZEN_PRIMARY` / `FROZEN_ENGINEERING` /
`FROZEN_CROSS_REFERENCE` only after a qualified reviewer verifies the actual text
and pagination.

---

## Minimum required acquisition package

For **each required book**, supply the following (as images/excerpts for private
analysis, or exact references — not the whole book):

1. Front cover.
2. Title page.
3. Author / editor / commentator / translator page.
4. Publisher and copyright page.
5. Edition and printing details.
6. ISBN or catalogue/library identifier.
7. Table of contents.
8. Relevant chapter opening.
9. **All** pages containing the applicable Koota rules.
10. **All** matrices and tables used by the rule pack.
11. **All** Parihara / exception passages.
12. Page numbers for every cited item.
13. Verse numbers where present.
14. Appendix identifiers where applicable.
15. Confirmation of lawful possession or library access.

### PRIMARY required source (normative) — `MC-NORMATIVE`

- **Title:** *Muhurta Chintamani* — **Author:** Rama Daivajna
- **Required section:** **Melapaka Prakarana** (marriage-matching chapter).
- **Exact selected edition:** to be pinned on acquisition. Candidate:
  Girish Chand Sharma tr. (Sanskrit + English), Sagar Publications, 1996; and/or a
  Sanskrit normative reference (e.g. Haridas Sanskrit Series #185, Kapileshwar
  Shastri). Pin **one** printing for all page citations.
- **Needed for:** the normative verse/page evidence for every Koota, matrix, and
  Parihara passage in the Melapaka Prakarana. The Sanskrit text governs on conflict.

### PRIMARY engineering source — `RAMAN-ENGINEERING`

- **Author:** B. V. Raman — **Title:** *Muhurtha (Electional Astrology)*
- **Required section:** **Marriage Adaptability** chapter **and** every Ashtakoota /
  Kuta appendix and score **table** used by the implementation.
- **Exact selected edition:** to be pinned. Candidate: UBSPD, 1993 (ISBN
  978-8185674681) or the Motilal Banarsidass reprint. Pagination varies across
  printings — **pin one printing** and cite its page/table numbers.
- **Needed for:** the deterministic table gradations and directional ordering
  (engineering interpretation). Raman must **not** silently override a clearly
  adjudicated MC normative verse.

### SUPPORTING sources (optional — only when a specific unresolved rule genuinely requires them)

- **`BPHS-XREF`** — *Brihat Parashara Hora Shastra* (e.g. R. Santhanam tr., Ranjan
  Publications, 1984, ISBN 978-8188230600): **only** the Naisargika (natural)
  planetary-friendship chapter, for Graha Maitri. Do **not** combine natural +
  temporary + compound friendship unless the selected matching source requires it.
- **`KALAPRAKASIKA-XREF`** — Kalaprakasika (N. P. Subramania Iyer tr.): **only**
  where a precise cited rule is genuinely needed and consistent with the selected
  v1 tradition. Do **not** blend regional systems silently, and do **not** use it to
  fill a missing cell.

Supporting sources stay **optional** until a named unresolved rule cannot be
adjudicated from MC + Raman alone.

---

## Not acceptable as authority (rejected)

The following are **not** acceptable rule authority and must never be recorded as a
source or used to adjudicate a rule:

- search-result snippets;
- astrology websites;
- mobile-app results;
- anonymous matrices / tables;
- AI summaries or AI-generated Sanskrit/translations;
- unverified OCR;
- pages **without** edition-identifying material (cover / title / copyright / ISBN).

---

## What each Koota / conflict needs from the acquired pages

To lift the gate, the acquired pages must let a qualified reviewer resolve:

- **Varna** (max 1): rashi→varna classification, directionality (role ordering), score.
- **Vashya** (max 2): rashi→category mapping, category count, multi-classification
  signs, full score matrix, directional/symmetric — **Conflict A** (12×12 vs 5×5).
- **Tara/Dina** (max 3): counting origin/convention, auspicious/inauspicious groups,
  directional from/to, gradations.
- **Yoni** (max 4): nakshatra→animal, complete 14×14 matrix with exact 0–4 values —
  **Conflict B** (friendly-3 / unfriendly-1 gradations). **Do not interpolate cells.**
- **Graha Maitri** (max 5): rashi lords, Naisargika friendship matrix, compound bands.
- **Gana** (max 6): nakshatra→gana, full matrix, Deva×Rakshasa and Rakshasa×Deva —
  **Conflict C** (0 vs 1), directionality.
- **Bhakoot/Rasi** (max 7): 2/12, 5/9, 6/8, same-sign, same-lord / friendly-lord
  relief — **Conflict D** (does relief restore points or only soften severity?).
- **Nadi** (max 8): nakshatra→nadi, same-nadi rule, exceptions. **Never** a medical,
  fertility, genetic, pregnancy, or health claim (DEC-021).
- **Parihara**: exact source, conditions, priority, numeric-vs-interpretive effect,
  stacking, mutual exclusions — all six rules stay `enabled:false` until approved.

---

## Acceptance criteria (when the gate lifts)

1. MC + Raman selected editions acquired lawfully and **pinned** (one printing each).
2. Provenance recorded via `scripts/source_intake.py` (sanitized SHA-256 records).
3. Edition-identifying pages present (cover/title/copyright/ISBN) for each source.
4. All relevant Koota-rule, matrix, and Parihara pages available with stable page/
   verse references.
5. A **qualified Jyotisha/Sanskrit reviewer** (see the domain-review package)
   verifies the text/pagination, adjudicates the four conflicts, and signs off.
6. Only then do sources move to `FROZEN_*`, rules to `DOMAIN_APPROVED`, and the
   authority package toward `RULE_PACK_READY` / `..._WITH_EXPLICIT_EXCLUSIONS`.

Until all six are satisfied, verdicts remain **`SOURCE_MATERIAL_REQUIRED` /
`GUNA_AUTHORITY_VALIDATION_BLOCKED` / `RULE_PACK_BLOCKED` / `executable:false`**.

See also: `DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md`,
`DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md`,
`DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md`,
`DILCHAT_GUNA_DOMAIN_REVIEW_RECORD.md`.
