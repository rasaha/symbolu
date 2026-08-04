# DilChat Guna Milan — Source Acquisition Report

**Phase:** Guna Source Acquisition, Rule Adjudication, and Domain Sign-off Preparation.
**Pack:** `ashtakoota_muhurta_chintamani_raman_v1` (North-Indian Ashtakoota, 8 kootas, 36-point,
Lahiri ayanamsa, sidereal).
**Overall status: `PENDING_ACQUISITION`.** Editions are now **identified** (real publishers /
translators / ISBNs / catalogue identifiers), but **nothing has been acquired, opened, paginated, or
verified** in this environment. No source is `FROZEN`. No rule is `DOMAIN_APPROVED`.

This report is the human-readable companion to `rules/sources/GUNA_SOURCE_MANIFEST.json`
(`manifest_id: guna_source_manifest_v2`), which supersedes v1. v1 recorded the *intended* sources
with no edition identified; v2 records real, externally-citable **candidate** editions found by
bibliographic search. This is edition **identification**, not acquisition and not freeze.

> **Honesty statement.** Every page number, verse number, chapter number, printing confirmation,
> checksum, acquisition date, and reviewer approval in this workstream is **PENDING (not acquired /
> not verified in this environment)**. Where a value could not be verified here, it is left explicitly
> PENDING rather than guessed. Internet consensus is **not** accepted as textual authority.

---

## 1. Environment limitation (read this first)

This phase ran inside an isolated build environment behind a filtering proxy.

- **Reachable:** bibliographic search and catalogue *listing* pages — Open Library, AbeBooks / Amazon
  marketplace records, publisher product pages (Sagar, Motilal Banarsidass, Gyan Publishing House),
  and Internet Archive **item listing** pages. These returned verifiable catalogue metadata
  (publisher, translator, year, ISBN, archive item identifier).
- **Blocked:** Internet Archive **content** endpoints returned **HTTP 403** through the environment
  proxy. No scan page was opened, no viewer/reader stream loaded, and no OCR text was retrieved.
- **Consequence:** the Sanskrit **Melapaka Prakarana** (Muhurta Chintamani marriage-matching chapter)
  and Raman's **Marriage Adaptability** chapter were **not read here**. Pagination was not seen; verse
  identity was not confirmed; no cell of any koota table was verified against a primary page.
- **What this environment could NOT do, and therefore did not do:** acquire a physical or
  authorized-digital copy; open any page; record a real page/verse range; compute a file checksum of
  an acquired copy; obtain any reviewer sign-off. All of these remain human, out-of-environment steps.

Nothing in this environment was frozen, and nothing here should be read as a freeze.

---

## 2. Per-source acquisition record

Legend for `edition_identification` (from the manifest):

- **`EDITION_IDENTIFIED_NOT_ACQUIRED`** — a specific, real, citable edition is identified from
  catalogue metadata, but no copy has been acquired and no page has been opened or verified here.
  **This is the status of all four sources below.**
- `ACQUIRED_PENDING_VERIFICATION` — a copy legally in hand, pagination/identity not yet
  reviewer-confirmed. **Not reached.**
- `FROZEN_ANY` — edition known, pages accessible, pagination stable, identity unambiguous, immutable
  checksum/permalink recorded, text usable for adjudication, reviewer confirmed. **Not reached.**

### 2.1 `MC-NORMATIVE` — *Muhurta Chintamani* (normative classical authority)

- **Work:** *Muhurta Chintamani* (*Muhurtacintamani*), Rama Daivajna (Daivajna Acharya Shri Rama).
- **Relevant section:** **Melapaka Prakarana** (marriage-matching chapter).
- **Role in the pack:** normative classical authority — governs on conflict.
- **What was searched:** Open Library work record; Internet Archive for a Sanskrit critical edition
  with commentary; publisher catalogue for an English translation carrying the Melapaka Prakarana.
- **Candidate editions identified:**
  1. **English engineering bridge (primary bridge):** Girish Chand Sharma (translator/commentator),
     Sanskrit text + English translation with commentary and annotation, **Sagar Publications, New
     Delhi, 1996**. Catalogue: Open Library work `OL63483W`
     (`https://openlibrary.org/works/OL63483W/`). ISBN: **PENDING** (not confirmed here).
     Copyright: **in copyright** (Sagar Publications) → **no scans committed**. Acquisition method:
     purchase from a bookseller.
  2. **Sanskrit normative reference:** with **Pt. Kapileshwar Shastri** (Sanskrit commentary),
     **Haridas Sanskrit Series #185, Chowkhamba**. Archive item identifier:
     `muhurt-chintamani-of-shri-ram-daivajna-with-pt.-kapilessvar-shastri-185-haridas-sanskrit-series`
     (`https://archive.org/details/...`). Publication year / printing: **PENDING**. Copyright:
     verify per edition/date — older Sanskrit editions may be public domain, but **the content
     endpoint returned HTTP 403 and was not opened**.
- **Recommended acquisition posture:** acquire **both** a Sanskrit normative reference and an English
  bridge. On any conflict, the **Sanskrit normative text governs**; the English translation is an
  accessibility bridge only.
- **`edition_identification`: `EDITION_IDENTIFIED_NOT_ACQUIRED`.** Verse-level identity for the
  Melapaka Prakarana must be confirmed by a Sanskrit-competent reviewer against an acquired copy.
- Page range, verse range, printing confirmation, acquisition date, checksum: **PENDING**.

### 2.2 `RAMAN-ENGINEERING` — *Muhurtha (Electional Astrology)* (engineering interpretation authority)

- **Work:** *Muhurtha (Electional Astrology)*, B. V. Raman (Bangalore Venkata Raman).
- **Relevant section:** the **Marriage / Marriage Adaptability** chapter and the Ashtakoota / Kuta
  tables the pack relies on.
- **Role in the pack:** engineering interpretation authority for table gradations and directional
  ordering. Raman must **not** silently override a clearly adjudicated MC normative verse.
- **What was searched:** AbeBooks/marketplace by ISBN; the Motilal Banarsidass product catalogue.
- **Candidate editions identified:**
  1. **Primary engineering:** **UBS Publishers' Distributors (UBSPD), 1993**, commonly cited **13th
     edition / reprint**. **ISBN-13 978-8185674681 / ISBN-10 818567468X**. Catalogue:
     `https://www.abebooks.com/book-search/isbn/9788185674681/`. Copyright: **in copyright** → **no
     scans committed**.
  2. **Alternate engineering:** **Motilal Banarsidass** reprint. **ISBN 9789359662923** (also
     9789359661070). Catalogue:
     `https://www.mlbd.in/products/muhurtha-electional-astrology-by-b-v-raman-9789359662923-9359662925-9789359661070-9359661074`.
     Copyright: in copyright → no scans committed.
- **Critical acquisition note:** table pagination varies across reprints. **One printing must be
  pinned** for all page citations; the UBSPD and MLBD printings are not page-compatible.
- **`edition_identification`: `EDITION_IDENTIFIED_NOT_ACQUIRED`.**
- Pinned printing, page range, acquisition date, checksum: **PENDING**.

### 2.3 `BPHS-XREF` — *Brihat Parashara Hora Shastra* (foundational cross-reference, Naisargika only)

- **Work:** *Brihat Parashara Hora Shastra*, attributed to Maharshi Parashara.
- **Relevant section:** **Naisargika (natural) planetary-friendship data ONLY**, for the Graha Maitri
  cross-reference — where consistent with the selected matching tradition.
- **Candidate edition identified:** **R. Santhanam (translator)**, Sanskrit + English, **Ranjan
  Publications, New Delhi, 1984**, **2-volume set (reprinted)**. **ISBN-13 978-8188230600 / ISBN-10
  818823060X**. Catalogue:
  `https://www.abebooks.com/9788188230600/Brihat-Parasara-Hora-Sastra-Maharshi-818823060X/plp`.
  Copyright: translation **in copyright** (Ranjan Publications) → **no scans committed**.
- **Usage constraint:** use **only** the natural-friendship (Naisargika Maitri) chapter for the Graha
  Maitri matrix. Do **not** combine natural + temporary (Tatkalika) + compound friendship unless the
  selected Ashtakoota source explicitly requires it.
- **`edition_identification`: `EDITION_IDENTIFIED_NOT_ACQUIRED`.**
- Chapter/verse/page for the friendship matrix, acquisition date, checksum: **PENDING**.

### 2.4 `KALAPRAKASIKA-XREF` — *Kalaprakasika* (supplementary cross-check only)

- **Work:** *Kalaprakasika*, translated by N. P. Subramania Iyer (reprint of the 1917 edition).
- **Relevant section:** only where exact edition/chapter/page evidence is available **and** the rule is
  relevant to the selected v1 tradition.
- **Candidate edition identified:** N. P. Subramania Iyer (translator), Devanagari text + English,
  **Gyan Publishing House** (and an Asian Educational Services reprint of the 1917 edition). **ISBN
  9788121236591 (pb) / 9788121236607 (hb)**. Catalogue:
  `https://www.abebooks.com/9788121236591/Kalaprakasika-Standard-Book-Election-System-8121236592/plp`.
  Copyright: the 1917 text is old; **modern reprint typesetting may carry its own rights** — verify
  before retaining any scan.
- **Usage constraint:** **supplementary only.** It must **not** be used to fill a missing cell, and it
  is a South-Indian electional system — it must **not** be blended silently with the North-Indian MC
  tradition.
- **`edition_identification`: `EDITION_IDENTIFIED_NOT_ACQUIRED`.**
- Chapter/verse/page, printing confirmation, acquisition date, checksum: **PENDING**.

---

## 3. Copyright posture (no scans committed)

- **In copyright — no scans, no OCR committed to the repository:** the Sharma/Sagar *Muhurta
  Chintamani* English translation; Raman's *Muhurtha* (both UBSPD and MLBD printings); the Santhanam
  *BPHS* translation; and, pending verification, the modern *Kalaprakasika* reprint typesetting.
- **Possibly public domain (verify per edition/date):** the older Haridas Sanskrit Series *Muhurta
  Chintamani* Sanskrit text and the 1917 *Kalaprakasika* base text. **Even where the base text may be
  public domain, this environment did not open it** (Internet Archive content returned HTTP 403), so
  the public-domain status was not confirmed here.
- **Allowed in the repository:** bibliographic metadata, catalogue/archive identifiers, page/verse
  *references*, brief copyright-compliant quotations added at review time, reviewer notes, file
  hashes of privately-held copies, and acquisition records.
- **Rejected as authority (per manifest):** blogs, mobile apps, AI summaries, anonymous
  transcriptions, uncorrected OCR, and secondary websites without edition/page evidence. These may
  never be cited as rule authority.

---

## 4. Exactly what must happen next (human checklist to acquire + freeze)

Each source must pass **every** freeze criterion. None currently does.

**Freeze criteria (a source may be frozen only when ALL hold):** exact edition known; relevant
pages/verses accessible; pagination stable and citable; bibliographic identity unambiguous; immutable
identity (checksum or catalogue permalink) recorded; text usable by a qualified reviewer for rule
adjudication; the reviewer has confirmed usability.

### Per source

For **`MC-NORMATIVE`**:
- [ ] Purchase the Sharma / Sagar Publications English edition; record its actual ISBN (currently
      PENDING) and printing.
- [ ] Acquire the Haridas Sanskrit Series #185 Sanskrit reference (or another Sanskrit critical
      edition); confirm printing/year and copyright/public-domain status of that specific edition.
- [ ] Open the **Melapaka Prakarana**; record the real chapter, verse range, and page range.
- [ ] Have a **Sanskrit-competent** reviewer confirm verse identity and usability.
- [ ] Record acquisition date and (for any privately-held scan) a file checksum.

For **`RAMAN-ENGINEERING`**:
- [ ] Purchase **one** printing (UBSPD 978-8185674681 **or** the MLBD reprint) and **pin it** for all
      citations.
- [ ] Open the **Marriage Adaptability** chapter and the Ashtakoota/Kuta tables; record real page
      numbers for every table the pack cites.
- [ ] Confirm the printing/edition number actually held (the "13th edition/reprint" attribution is a
      common citation, not verified here).
- [ ] Record acquisition date and checksum.

For **`BPHS-XREF`**:
- [ ] Purchase the Santhanam / Ranjan 2-volume set (978-8188230600).
- [ ] Locate the **Naisargika (natural) friendship** chapter; record chapter/verse/page.
- [ ] Confirm it is used for natural friendship **only** (Tatkalika excluded).
- [ ] Record acquisition date and checksum.

For **`KALAPRAKASIKA-XREF`**:
- [ ] Only if a specific supplementary rule requires it: purchase the Subramania Iyer edition
      (9788121236591 / …607); verify reprint copyright.
- [ ] Record exact chapter/verse/page for any cell it supports; confirm it is not silently blended
      with the North-Indian MC tradition.
- [ ] Record acquisition date and checksum.

### After all four are acquired and reviewer-usable

- [ ] Update `GUNA_SOURCE_MANIFEST.json`: set each `edition_identification` to
      `ACQUIRED_PENDING_VERIFICATION`, then to `FROZEN_*` once the reviewer confirms usability; fill
      `acquisition_date`, `file_checksum`, and per-rule `chapter`/`verse_range`/`page_range`.
- [ ] Resolve the **four source conflicts** (Vashya table form; Yoni friendly/unfriendly gradations;
      Gana Deva×Rakshasa 0-vs-1; Bhakoot friendly-lords cancel-vs-relief) with cited decisions — all
      currently **`resolution: PENDING`**.
- [ ] Obtain qualified **Jyotisha + Sanskrit** reviewer sign-off (see
      `DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md`) and record it — never fabricated.
- [ ] Confirm the founder/domain open questions: **OQ-1** (North-Indian only vs add South-Indian
      Dashakoota), **OQ-2** (bride/groom directional mapping). See `DILCHAT_GUNA_V1_TRADITION_SCOPE.md`.

---

## 5. Bottom line

**No rule in `ashtakoota_muhurta_chintamani_raman_v1` can be executable until its sources are FROZEN
AND domain-reviewed.** Edition identification advances the record (real ISBNs and catalogue IDs are
now on file) but changes **nothing** about executability: the pack remains `draft: true`,
`executable: false`, `authority_gate: BLOCKED`, and the overall source status remains
**`PENDING_ACQUISITION`**.

## 6. Related artifacts

- `rules/sources/GUNA_SOURCE_MANIFEST.json` — machine-readable edition record (`guna_source_manifest_v2`).
- `docs/DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md` — freeze-status summary.
- `docs/DILCHAT_GUNA_V1_TRADITION_SCOPE.md` — what v1 claims to implement.
- `docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md` — per-rule → source mapping.
- `docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md` — reviewer package and sign-off template.
- `docs/DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md` — consolidated authority gate.

---

## Source-material availability gate (Guna Source Acquisition & Qualified Domain Adjudication phase)

**Verdict: `SOURCE_MATERIAL_REQUIRED`.**

This phase requires *actual source text*, not bibliographic metadata. In this
isolated build environment **no source pages are available in a legally usable
form**:

- catalogue/bibliographic search worked and identified real editions (recorded in
  `GUNA_SOURCE_MANIFEST.json`), but
- Internet Archive **content** endpoints are HTTP 403-blocked (only listing pages
  are reachable), and
- there is **no** purchased copy, library-access copy, lawful archive copy, or
  user-provided page image in this environment.

Search snippets, uncorrected OCR, second-hand summaries, unsourced internet tables,
AI-generated Sanskrit/translations, and different editions with uncertain pagination
are **not** acceptable authority. Therefore, per the phase rules, **no rule is
adjudicated** in this phase and every Koota / conflict / manual case remains at its
prior honest `PENDING_DOMAIN_REVIEW` / `BLOCKED_DOMAIN_SOURCE` / `SOURCE_CONFLICT`
status. Nothing is frozen; no reviewer is fabricated.

### Local-source intake process (available now)

`scripts/source_intake.py` records **sanitized provenance** for a lawful local copy
**without** copying it into the repository and **without** leaking its path:
computes SHA-256 + byte size, keeps only the file basename, rejects non-lawful
access methods, and emits `freeze_status: ACQUIRED_PENDING_TEXT_VERIFICATION`
(never `FROZEN`). Covered by `tests/unit/test_source_intake.py`.

```bash
python scripts/source_intake.py \
  --file /path/to/lawful/copy.pdf \
  --source-id MC-NORMATIVE \
  --edition "Muhurta Chintamani, Girish Chand Sharma tr., Sagar Publications, 1996" \
  --acquisition-method purchased_ebook \
  --access-date YYYY-MM-DD
```

### Exact acquisition checklist (to lift the gate)

1. **MC-NORMATIVE** — acquire a lawful copy of *Muhurta Chintamani* (Melapaka
   Prakarana). Recommended: Girish Chand Sharma tr. (Sagar, 1996, English + Sanskrit)
   **and** a Sanskrit normative reference (e.g. Haridas Sanskrit Series #185). Pin the
   printing; run `source_intake.py`; record chapter/verse/page for each Melapaka rule.
2. **RAMAN-ENGINEERING** — acquire *Muhurtha (Electional Astrology)*, B. V. Raman
   (UBSPD 1993, ISBN 978-8185674681, or the MLBD reprint). Pin the printing (pagination
   varies); capture the Marriage Adaptability chapter and every Ashtakoota/Kuta table.
3. **BPHS-XREF** — acquire R. Santhanam tr. (Ranjan Publications, 1984,
   ISBN 978-8188230600); use only the Naisargika (natural) friendship chapter.
4. **KALAPRAKASIKA-XREF** — acquire N. P. Subramania Iyer tr. (Gyan, ISBN
   9788121236591) only where a precise cited rule is needed; do not blend regionally.
5. For each acquired source, run `source_intake.py`, then a **qualified Jyotisha +
   Sanskrit reviewer** verifies the text/pagination before any source is set
   `FROZEN_*` and any rule is adjudicated.

Until steps 1–5 are complete, the Guna authority and rule-pack verdicts remain
**BLOCKED** and no Guna engine may be implemented.
