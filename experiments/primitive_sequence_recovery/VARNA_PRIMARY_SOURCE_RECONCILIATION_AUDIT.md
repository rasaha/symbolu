# Primary-Source Reconciliation Audit — "The Acoustic Roots of the Indo-Aryan Alphabet"

**Read-only. No frozen mapping, preregistration, feature-lift dataset, or prior result modified.** Reconciles the
**actual primary source** — P.R. Sarkar, *"The Acoustic Roots of the Indo-Aryan Alphabet,"* in *Ánanda Márga
Philosophy in a Nutshell* Part 8 (1984–85, Calcutta) — against our frozen mappings. `EXPLORATORY /
DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## ⚠️ Headline: two findings, one of them a confirmed data error

1. **`ś` / `ṣ` are SWAPPED in the frozen lexicon relative to the primary source.** This is a genuine data error,
   and it **reverses** the earlier `VARNA_SHA_SWAP_PROVENANCE_AUDIT.md` verdict
   (`SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR`). That verdict was **wrong** — I trusted the intermediate `b1_2`
   ledger as the primary-text authority; the real primary text shows the opposite.
2. **Vowels are a two-layer case — not "entirely intuition" (correcting an earlier overstatement).** Sarkar gives
   each vowel a **musical-note** root *and*, for several, a distinct **semantic import**. The operator's vowel
   glosses are **grounded in Sarkar's semantic import** for **a=creation, e=vauṣaṭ (knowledge), ai=vaṣaṭ
   (welfare), o=svāhā (completion), au=namaḥ (surrender)** — near-verbatim — and are the operator's **own authored**
   reasoning only where Sarkar gives *just* a note (ā, i, ī, u, ū). The **musical-note** layer is separately set
   aside as out-of-domain.

## 1. The ś/ṣ swap — what the primary source actually says

The source is unambiguous and states the sibilants **three times**, including a single summarizing passage under
**SA**:

> "va is the acoustic root of dharma …; **sha is the acoustic root of artha** …; and **s'a is the acoustic root
> of kāma** … Each of the letters is the acoustic root of one of the four vargas. Va is additionally the acoustic
> root of the liquid factor; **sha is the acoustic root of rajoguṇa**; **s'a is the acoustic root of tamoguṇa**;
> and sa is [the acoustic root of sattvaguṇa]."

**Romanization is decisive and internally consistent:** throughout the document the apostrophe marks the
**retroflex/cerebral** series — `ṭ`=t', `ḍ`=d', `ṇ`=n' (Varuṇa = "Varun'a"), `ṣ`=s' (kṣa = "Ks'a", ṛṣabha =
"rs'abha", ṣaḍja = "s'ad'aja"). Therefore:

| Source token | IAST atomic | Guṇa | Puruṣārtha |
|---|---|---|---|
| **"Sha"** | **ś** (palatal, U+015B) | **rajoguṇa** (mutative) | **artha** |
| **"S'a"** | **ṣ** (retroflex, U+1E63) | **tamoguṇa** (static) | **kāma** |
| "Sa" | s (dental) | sattvaguṇa (sentient) | mokṣa |

**Our frozen merged lexicon (`af4c1f54…`) has the opposite:**

| Unit | Frozen merged binding | Primary source | Verdict |
|---|---|---|---|
| `ś` | "kāma … the **tamasic** pull" | should be **artha / rajoguṇa** | **SWAP_ERROR** |
| `ṣ` | "artha … **rajasic** grasping" | should be **kāma / tamoguṇa** | **SWAP_ERROR** |
| `s` | sattvic / mokṣa | sattvaguṇa / mokṣa | MATCH |

### How the error entered (corrected history)

- **b1_1 draft & `b1_2_varna_source_lexicon.json`** had `sha(ś)=rajoguṇa+artha`, `ssa(ṣ)=Kāma/Tamoguṇa` —
  **CORRECT** per the primary source.
- **`b1_2_varna_classical_verifications.json`** (which I earlier treated as the primary-text authority)
  **mis-decoded the romanization** — it read Sarkar's "sha" (palatal ś) as if it were IAST retroflex `ṣ`, wrote
  "ṣa ('sha') = artha + rajoguṇa" and "śa = kāma + tamoguṇa," and **wrongly declared the correct source-lexicon
  "swapped."**
- **v3.1** then "corrected" the originally-correct table to match that mis-decoded ledger, propagating the
  inversion into the frozen merged lexicon and the feature-lift dataset.
- My **prior audit** trusted the ledger over the source and certified "no data error." The actual primary source
  now falsifies that. I'm flagging my own mistake explicitly.

**Impact.** The feature-lift 88-word dataset uses the swapped ś/ṣ binding glosses: words containing `ś` received
the kāma/tamasic gloss (should be artha/rajasic) and words with `ṣ` the reverse. Because it is exactly two
consonants transposed, it is a contained but real error — it should be fixed before the lift run, not after.

## 2. The vowel layer — two layers, and the operator's glosses are partly Sarkar-grounded

**Correction to an earlier overstatement.** I first called the vowel glosses "entirely intuition." That is wrong.
Sarkar gives each vowel **two** things: (a) a **musical-note** root (the surasaptaka — a=ṣaḍja … ṛ=niṣāda), which
*is* a different domain and is set aside; and (b) for several vowels, a distinct **semantic/cosmological import**.
The operator's vowel glosses are **grounded in that semantic layer** where it exists:

| Vowel | Sarkar semantic import | Operator liberating gloss | Grounding |
|---|---|---|---|
| **a** | **creation** | "Birth of cognition / raw potential" | **Sarkar-grounded** |
| **e** | vauṣaṭ — mundane knowledge / welfare | "Practical thought, benefit" | **Sarkar-grounded** |
| **ai** | vaṣaṭ — welfare (subtler sphere) | "Welfare, materialization" | **Sarkar-grounded** |
| **o** | svāhā — completion of an action | "Completion, closure" | **Sarkar-grounded** |
| **au** | namaḥ — surrender | "Surrender, Letting-go" | **Sarkar-grounded** |
| ā, i, ī, u, ū | (Sarkar gives only a musical note) | expansion / I-ness / specialization / zoom / holding | operator-authored |
| **ṝ, ḷ, ḹ** | oṃ · hummm · phaṭ | (no operator gloss) | **Sarkar semantic available, not yet mapped** |
| ṛ | (only musical note niṣāda) | (no gloss) | operator-absent |

So five vowels (**a, e, ai, o, au**) are near-verbatim Sarkar semantics, not invention; five (ā, i, ī, u, ū) are
the operator's own reasoning where Sarkar gives only a note; and three (**ṝ=oṃ, ḷ=hummm, ḹ=phaṭ**) carry
Sarkar-backed semantics the mapping doesn't yet include (optional to add — rare vocalic sounds). The **musical
notes** themselves remain out-of-domain for the affliction mappings.

| Vowel | Primary-source acoustic root |
|---|---|
| a | creation; controller of the seven notes; 1st note ṣaḍja |
| ā | ṛṣabha (2nd note) · i → gāndhāra (3rd) · ī → madhyama (4th) · u → pañcama (5th) · ū → dhaivata (6th) · ṛ → niṣāda (7th) |
| ṝ | **oṃ** (creation/preservation/destruction; Saguṇa & Nirguṇa) |
| ḷ | **hummm** — struggle, sādhanā, kuṇḍalinī (the "battle cry") |
| ḹ | **phaṭ** — putting theory into practice (atibīja) |
| e | **vauṣaṭ** — mundane knowledge/welfare |
| ai | **vaṣaṭ** — subtler welfare; six stages of vocalization |
| o | **svāhā** — completion of an action · au → **namaḥ** (surrender) |
| aṃ | an idea · aḥ → positive/negative by utterance |

Note `ṛ, ṝ, ḷ, ḹ` are **entirely missing** from the merged lexicon (source `None`); the others exist there only as
authored binding glosses with none of this acoustic-root content.

## 3. Consonant vṛttis — otherwise consistent

All **31** other consonant vṛtti assignments agree with the merged lexicon (ka=āśā, kha=cintā, … ha=parā-vidyā,
kṣa=aparā-vidyā). Several extra associations the primary text carries (ra=RAM bīja, ha/ṭha loka/kośa cluster,
ka=Kārya Brahma/Nārāyaṇa, va=Varuṇa) match what `VARNA_CLASSICAL_SOURCE_COMPLETENESS_AUDIT.md` already flagged as
"left on the table." (Note: `la=kṣititattva` is **not** in this particular text — it comes from a different Sarkar
passage — so it is neither confirmed nor contradicted here.)

## Reconciliation summary

| Status | Count | Units |
|---|---|---|
| **SWAP_ERROR** (must fix) | 2 | ś, ṣ |
| vowels — Sarkar-semantic-grounded operator gloss | 5 | a e ai o au |
| vowels — operator-authored (Sarkar gives only a note) | 7 | ā i ī u ū aṃ aḥ |
| vowels — Sarkar semantics available, not yet mapped | 3 | ṝ (oṃ) ḷ (hummm) ḹ (phaṭ) |
| vowels — operator-absent (only a note) | 1 | ṛ |
| MATCH (consonant vṛtti) | 31 | all other consonants |
| out of atomic scope | 1 | kṣ (conjunct) |

Machine-readable: `varna_acoustic_roots_primary_source.json` (sha256 `553fc3ee…`), built by
`build_primary_source_reconciliation.py`.

## Recommendation (nothing changed here — needs your decision)

1. **Correct the ś/ṣ swap** in a **new versioned refreeze** of the polarity table + merged lexicon (swap the
   binding/liberating glosses, guṇa, and puruṣārtha between the `sha`(ś) and `ssa`(ṣ) rows), and **retract** the
   `SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR` verdict. Because this touches a **frozen** artifact and the
   **feature-lift dataset**, I have not done it — it needs your go-ahead.
2. **Rebuild the feature-lift prerun** after the correction (only words containing ś or ṣ change; a targeted
   rebuild suffices), or explicitly accept the swap and document it — but the honest path is to fix it.
3. **Vowels: mostly settled.** The musical-note layer stays out of scope; the operator's glosses for a/e/ai/o/au
   are Sarkar-grounded and correct to keep. The only optional addition is the three unmapped Sarkar semantics
   (ṝ=oṃ, ḷ=hummm, ḹ=phaṭ) — rare vocalic sounds; add only if the vowel layer is developed further.

## Guardrails
Read-only reconciliation; no frozen mapping, preregistration, feature-lift dataset, or prior result modified. The
ś/ṣ swap is reported as a confirmed error to be fixed by a future versioned refreeze, pending your decision.
Structure, not validated meaning.
