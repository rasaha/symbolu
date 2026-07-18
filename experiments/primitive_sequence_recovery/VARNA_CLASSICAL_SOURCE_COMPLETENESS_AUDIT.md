# Classical-Association Source-Completeness Audit (read-only, exhaustive extraction)

**Read-only. No inference, no synthesis, no modification.** Exhaustively extracts every directly-attested varṇa
association from the primary-text ledger and asks: is the current normalized classical layer complete, or was
source-backed information left on the table? `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Verdict

> **The current classical layer is INCOMPLETE.** It normalized only **guṇa (3)**, **tattva (5)**, and **deity
> (1)**. The primary-text ledger attests **several further, explicitly source-backed association classes** that
> were left on the table — most substantively a **puruṣārtha (four-longing) layer**, a **bīja-mantra + yantra
> layer**, and a **loka / kośa / celestial layer**, plus **ka's Brahma/Nārāyaṇa cosmology** and **ra's
> prāṇaśakti**. None of this is inferred; each is a verbatim token in the ledger.

## Sources searched (what actually contributes to the ledger)

The ledger `b1_2_varna_classical_verifications.json` (sha256 `a1ad271f…`) is the primary-text authority; its own
`purpose` states it records "the cosmological/etymological ASSOCIATIONS (kept SEPARATE from the poles)." It
contains **34 entries: 33 atomic consonants + the kṣa conjunct. No vowels.** Every quote is from a **single
source tradition** (Sarkar's varṇa / bīja-mantra exposition).

- **Independent-text variants:** **none.** No second, independent classical text is cited, so there are **no
  cross-text variant conflicts** to report. The only internal conflict ever present was the **ś/ṣ swap**, which is
  already **RESOLVED** (see `VARNA_SHA_SWAP_PROVENANCE_AUDIT.md`). This single-source dependence is itself a
  completeness *limitation* worth stating: coverage reflects one author's system, not a cross-tradition consensus.
- **Vowels:** **ABSENT** from all primary-text sources. The only vowel data in-repo
  (`varna_lens/lexicon_authoritative_varna.json`, from `Sanskrit_letters_full.docx`) carries **only authored
  binding/liberating states** — **no tattva, guṇa, bīja, deity, or loka** for any vowel. So there is **no
  source-backed vowel classical layer to extract**; report as absent, not missing-and-recoverable.

## What the normalized layer captured (complete for its scope)

`varna_classical_associations_33.json`: guṇa = {ś→tamas, ṣ→rajas, s→sattva}; tattva = {y→air, r→fire, l→earth,
v→water, h→ether}; deity = {v→Varuṇa}. These are correct and complete **for those three classes**.

## Attested associations left on the table (verbatim, not inferred)

| Association class | Varṇas (ledger keys) | Example verbatim token | In normalized layer? |
|---|---|---|---|
| **puruṣārtha** (four longings) | va, ṣa (ssa), ś (sha), s (sa) | va=dharma · ṣa=artha · śa=kāma · sa=mokṣa (four-varga scheme) | **No** |
| **bīja-mantra + yantra** | ra, la | ra=RAM (triangular, red) · la=LAM (square, deep-yellow) | **No** |
| **loka** | ha, ṭha (ttha) | ha=svarloka · ṭha=bhúvarloka | **No** |
| **kośa** | ṭha (ttha) | ṭha=kāmamaya kośa | **No** |
| **celestial / temporal** | ha, ṭha | ha=daytime+sun · ṭha=nighttime+moon | **No** |
| **brahma / cosmological** | ka | Kārya Brahma (Saguṇarasātmaka Brahma; controller of the living world) | **No** |
| **buddhist** | ka | Saṃvṛtti Bodhicitta = the created world | **No** |
| **deity (further)** | ka, ha | ka→Nārāyaṇa (kesha) · ha→Shiva (via hao compound) | **No** (only Varuṇa was captured) |
| **prāṇaśakti (vitality)** | ra | ra = agnitattva **and** prāṇaśakti | **No** |
| **vidyā** | ha, kṣa | ha=parā-vidyā · kṣa=aparā-vidyā | Partial (in glosses only) |
| **opposite-varṇa structure** | ha↔ṭha, ka/kṣa, kha/kṣa | "Opposite to ha is ṭha" | **No** |
| **etymology / cross-reference / scope** | many (pa, ka, ta, na, ba, …) | pāśa/ripu memberships, Tantra etymology, brahmavihāra | **No** (verbatim only) |

**Absent (correctly, no association attested):** `ca, cha, ja, ṇa (nna), tha, da` — the ledger attests **only the
vṛtti name** for these; report as genuinely absent, not omitted.

### The three high-value omissions

1. **Puruṣārtha layer (4 varṇas).** The four-varga scheme assigns **va=dharma, ṣa=artha, śa=kāma, sa=mokṣa**.
   The normalized layer captured the guṇa half of the sibilant triad but **not** the puruṣārtha half, and **not**
   `va=dharma` at all. This is the single cleanest, most systematic omission — a complete, closed 4-element
   attested set.
2. **Bīja-mantra + yantra layer (ra, la).** `ra`=RAM (triangular, red-glowing) and `la`=LAM (square,
   deep-yellow) are attested with geometry and color. The tattva was captured; the bīja/yantra was dropped.
3. **Loka / kośa / celestial cluster (ha, ṭha).** `ha` and its explicit opposite `ṭha` carry a full attested
   celestial/loka/kośa structure (day↔night, sun↔moon, svarloka↔bhúvarloka, parā-vidyā↔kāmamaya kośa). Only ha's
   ether-tattva was captured.

## Coverage counts (primary-text ledger, 34 entries)

- guṇa: **3** (ś, ṣ, s) · tattva: **5** (y, r, l, v, h) · deity(normalized): **1** (v)
- puruṣārtha: **4** (va, ṣa, ś, s) · bīja-mantra: **2** (ra, la) · loka: **2** (ha, ṭha) · kośa: **1** (ṭha)
- celestial/temporal: **2** (ha, ṭha) · brahma/cosmological: **1** (ka) · buddhist: **1** (ka)
- further deity: **2** (ka→Nārāyaṇa, ha→Shiva-compound) · prāṇaśakti: **1** (ra) · vidyā: **2** (ha, kṣa)
- entries with **no** association attested: **6** (ca, cha, ja, ṇa, tha, da)
- **vowels with any source-backed classical association: 0**

## Machine-readable output

`varna_classical_associations_exhaustive.json` (sha256 `9ea52cdf…`) — per-varṇa full `source_quote_verbatim`,
`classical_associations_verbatim`, and a tagged `attested_associations` list with a
`captured_in_normalized_layer` flag per item, plus an `omitted_but_attested_classes` roll-up. Built by
`build_varna_classical_exhaustive.py`.

## Recommendation (no change made here)

If the classical layer is to be used for feature work, the **puruṣārtha** set (closed, 4 varṇas) and the
**bīja-mantra/yantra** set are the most systematic, cleanly-attested additions; the **loka/kośa/celestial**
cluster is attested but sparse (2 varṇas). Any expansion must be a **new, separately-versioned extraction
artifact** — the frozen merged lexicon, preregistrations, and the feature-lift dataset are **not** modified, and
these associations must **not** be back-filled into V1. Single-source dependence (Sarkar) should be disclosed in
any downstream use.

## Guardrails
Read-only exhaustive extraction; no inference; no frozen mapping, preregistration, feature-lift dataset, or prior
result modified. Absences reported as absent. Single source tradition; no cross-text variants. Structure, not
validated meaning.
