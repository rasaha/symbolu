# Sanskrit-First Restructure — Repository Audit & Staged Hardening Plan (docs-only)

**Docs-only.** No code, no run, no mapping/table/context/judge change, no new experiment number. This document
(1) audits what the repository actually contains for a native-Sanskrit varṇa mechanism, and (2) lays out a
two-stage plan: **Stage 1 = harden the mechanism on native Sanskrit words only; Stage 2 = English → phonetic →
fixed Sanskrit-varṇa transcription → the frozen Stage-1 mechanism.** English experimentation is stopped as the
active line. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no
ontology / semantic-truth / Sanskrit-privilege / generation-utility / individual-varṇa claim. **B1.4b′ remains
`NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**

---

## PART A — Repository audit (what exists today)

Sources audited: `frozen/varna_polarity_table_v3.json` (active table), `varna_bridge_active.py` /
`varna_bridge_thfix.py` (decomposition), `build_b1_10_control_ext.py` (`VARNA_PLAIN` rendering), the Track-G
artifacts (`track_g_*`, the closest existing native-Sanskrit work), and the run01 / G0 results.

### A.1 Varṇa inventory actually used
- **34 entries, ALL consonants:** `ba bha ca cha da dda ddha dha ga gha ha ja jha ka kha kṣa la ma na ṅa nna
  nya pa pha ra sa sha ṣa ta tha ṭa ṭha va ya`.
- **No vowels. No anusvāra (ṃ). No visarga (ḥ).** Sanskrit varṇa theory assigns acoustic roots to the vowels
  (a ā i ī u ū ṛ ṝ ḷ e ai o au) and to aṃ/aḥ; **none are present.** This is a foundational gap.
- **Aspiration present-but-excluded:** the ~10 aspirates (kha gha cha jha ṭha ḍha tha dha pha bha) exist as
  table rows but are **not produced** by the active mapping — `n_practically_reachable = 19`, 6
  bridge-reachable-not-practical, 9 unreachable; "aspiration EXCLUDED" in the active bridge.

### A.2 Binding / liberating assignment per varṇa
- **Backbone:** the b1_2 Sarkar-attributed lexicon + a few operator primary-text corrections (ha, pa). The
  table's own methodology says: *"a SEEDED framework … NOT a finished re-derivation."*
- **Asymmetry (critical):** `classical_side_attested` = **binding 27, liberating_oriented 5, dual 1, neutral
  1** — i.e. most varṇas are attested only on the **binding (kleśa)** side. The table's own caveat: *"The
  LIBERATING pole is author counter-rewritten for most varṇas — not attested."* Mechanically, **28 of 34
  liberating poles are AUTHORED, not sourced.**
- **Primary-text scope:** `NAME_PLUS_DEFINITION` 17, `NAME_ONLY` 3, **None 14** — 14 varṇas have no
  primary-text scope recorded at all.
- **Flagged problems (the table's own `important_caveats`):**
  - **`ha`'s binding/liberating split is researcher-authored, "motivated partly by making 'happy' cohere"** —
    an explicit back-fit-to-a-target-word risk the authors say MUST be frozen + pre-registered.
  - **`pa`'s operator reading partially INVERTS the source-attested pole** (ghṛṇā).
  - **`ṭha` (ṭṭha): classical night/moon reading vs lexicon "Repentance" is UNRESOLVED.**

### A.3 Treatment of vowels / aspiration / conjuncts / anusvāra / visarga / sandhi / position
| feature | current treatment |
|---|---|
| vowels | **dropped** (not in table, not produced) |
| aspiration | **excluded** (aspirates collapse to unaspirated) |
| conjuncts | **partial** — retroflex `tr/dr → ṭa/ḍa`; `kṣa` present as a row; general conjunct logic absent |
| anusvāra (ṃ) | **absent** |
| visarga (ḥ) | **absent** |
| sandhi | **none** |
| position / order | **none** — sequence is de-duplicated to a **set** |

### A.4 Word → interpretation rule
The active rule is: word → phonemes → **consonant varṇas, de-duplicated to a set** → the word's "packet" =
the **union of each varṇa's binding facet clauses (and, separately, liberating clauses)**. It is an **unordered
bag-of-varṇas**: no ordering, no positional weighting, no compositional/sequential operation, no vowels. (Seen
directly: `pride → {pa,ra,da}`; packet = the three varṇas' facet clauses.)

### A.5 Rule provenance register (sourced / inferred / provisional / contradictory / missing)
- **Sourced (attested):** ~27 **binding** poles (Sarkar lexicon) + operator primary-text for ha, pa.
- **Inferred / authored:** **28/34 liberating poles**; `ha`'s split (authored, target-word-motivated).
- **Provisional:** the **14** varṇas with no primary-text scope; the **~9–10 aspirates** (reference-only,
  never produced); the whole liberating axis.
- **Contradictory:** **pa** (operator reading inverts source pole); **ṭha** (night/moon vs "Repentance"
  unresolved).
- **Missing entirely:** **all vowels, anusvāra, visarga, sandhi, positional/sequence rules, aspiration
  handling, and any native Sanskrit akṣara decomposition** (see A.6).

### A.6 Decomposition mechanism
- `word_to_varnas` runs an **English grapheme-to-phoneme** stage then a phoneme→varṇa bridge. It is
  **consonant-only** and **vowel-dropping**, and (for English) demonstrably **orthographic**, not phonetic:
  silent letters produce varṇas (`doubt/debt → da·ba·ta` from a silent b; `write → va·ra·ta` from a silent w;
  `knee → ka·na` from a silent k). **There is no native Sanskrit akṣara reader** — feeding IAST words routes
  them through the English g2p (`krodha → ka·ra·da·ha`, vowels dropped, `dh→d`).
- **Consequence for a "native Sanskrit" claim:** the repository cannot presently decompose a Sanskrit word in
  its native varṇa form. A Sanskrit word IS a varṇa sequence by definition (read off its akṣaras) — but the
  current pipeline neither reads akṣaras nor keeps vowels/aspiration/order.

### A.7 Existing Sanskrit-oriented infrastructure — Track G
Track G is the closest existing native-Sanskrit work: a small **Sanskrit surface-word list**
(`track_g_smoke_words.jsonl`: happy→**sukha** `sa·kha`, peace→**śānti** `sha·na·ta`, courage→**bala** `ba·la`,
…), a **candidate-gloss discrimination design** with target / opposite-pole / hard-negative / **Barnum**
controls (`track_g_smoke_candidates.jsonl`), and a smoke run (`TRACK_G_SMOKE_RESULT.md`). Status:
`draft_researcher_frozen_unverified`, **consonant-only** decomposition (same vowel/aspiration gap). It is the
natural seed for Stage 1, but inherits A.1–A.6's limitations.

**Audit bottom line.** The "Sanskrit mechanism" today is: a consonant-only, vowel-less, aspiration-less,
order-less bag-of-varṇas, with **attested binding poles but authored liberating poles**, three flagged
contradictions/back-fits (ha, pa, ṭha), and **no native akṣara decomposition**. It is explicitly a *seeded
framework*, not a finished mechanism. This is not yet in a state to be frozen or fairly tested.

---

## PART B — STAGE 1: native-Sanskrit mechanism hardening (no English)

**Goal:** turn the seeded framework into a *frozen, sourced, internally consistent* native-Sanskrit mechanism,
tested only on native Sanskrit words. The seven clarifications the restructure requires:

**B.1 Exact varṇa inventory.** Decide and freeze the inventory the mechanism operates on. Either (a) **extend
the table to the full akṣara set** — add the vowels (a ā i ī u ū ṛ ṝ ḷ e ai o au), anusvāra, visarga — with
their Sarkar-attested acoustic roots; or (b) **explicitly scope Stage 1 to consonants only**, with a written
rationale and a standing note that vowel-bearing meaning is out of scope. Silent choice (current state) is not
acceptable: the gap must be a *declared* decision.

**B.2 Binding & liberating per varṇa — separate attested from authored.** Freeze **only the attested backbone**
(the ~27 sourced binding poles) as the mechanism's committed content. Mark every **authored liberating pole**
and every no-primary-text varṇa as **PROVISIONAL** and quarantined from any "meaning" claim until sourced or
formally pre-registered as authored. **Resolve or quarantine the contradictions**: `pa` (source-inverting),
`ṭha` (unresolved), and especially **`ha`** (authored to make an English target cohere — must be re-derived
from source or dropped, never used while target-motivated).

**B.3 Positional / phonological treatment — pre-register each.** For **vowels, aspiration, conjuncts,
anusvāra, visarga, sandhi, and positional effects**, write an explicit include/defer decision with its source:
does the mechanism read them, and if so how do they contribute? (e.g. is an aspirated stop a distinct varṇa
with its own root, or a modifier? does anusvāra carry a nasal root? does word-position weight a varṇa?) Each
answer must cite Sarkar / primary text or be marked authored-provisional.

**B.4 Word-level composition rule.** Decide and freeze how a varṇa **sequence** yields a word interpretation.
The current unordered set-union ("bag of varṇas") discards order, repetition, position, and vowels. Pre-register
whether Stage 1 keeps bag-of-varṇas (and owns that limitation) or adopts an **ordered / positional /
first-varṇa-weighted / compositional** rule — with the rule stated *before* any word is scored.

**B.5 Living provenance register.** Maintain a machine-checkable register classifying **every** rule and pole
as `SOURCED | INFERRED | PROVISIONAL | CONTRADICTORY | MISSING` (seed it from A.5). Freezing is gated on this
register having **no CONTRADICTORY entries in the committed backbone** and every committed pole `SOURCED`.

**B.6 Development examples & evaluation (native Sanskrit only).** Select native Sanskrit words **whose varṇa
meaning is itself attested in the source** (e.g. Sarkar's own illustrations: `krodha`/`karkaśatā` for da,
`lajjā` for ḍa, `vitarka` for ṭa, `jāḍya`/`nidrā` for ta, `āśā` for ka). Evaluate with a **discrimination
design** (reuse the Track-G scaffold): a word's varṇa-derived reading vs an opposite-pole gloss vs hard
negatives vs a **Barnum** (generically-true) control; **blind** non-Claude judges; the varṇa→word direction
authored **before** the candidate glosses; own-vs-other and vs-control margins pre-registered. Crucially, avoid
the run01 trap: contexts/glosses must not simply restate the varṇa definition (which would tautologically win).

**B.7 Freeze criteria for the native mechanism.** Stage 1 may be frozen only when: (i) the committed inventory
is declared (B.1); (ii) every committed pole is `SOURCED` and every contradiction is resolved or quarantined
(B.2, B.5); (iii) the phonological/positional treatment is pre-registered (B.3–B.4); and (iv) a **pre-registered
discrimination test on native Sanskrit words shows the mechanism's readings beat the opposite-pole, hard-
negative, AND Barnum controls, robustly across judges and words.** Absent (iv), the mechanism is documented as
*not validated* and English transfer does not begin.

**Stage-1 rule:** **no English words.** Do not transcribe, test, or tune on English at this stage.

---

## PART C — STAGE 2: English → Sanskrit-varṇa transcription (cross-language transfer)

Begins **only after Stage 1 is frozen (B.7).** The pipeline is fixed as:

```
English word → English PRONUNCIATION (IPA, not spelling) → phonetic representation
            → FIXED Sanskrit-varṇa transcription (pre-registered rules) → frozen Stage-1 mechanism
```

- **No spelling-derived varṇas.** Silent letters must not contribute (the current pipeline's silent-b in
  `doubt`, silent-w in `write`, etc. are prohibited) **unless** a *separately stated orthographic hypothesis*
  is explicitly being tested and labelled as such.
- **Pre-register and freeze the transcription rules — before any Stage-2 test — for:** English **vowels &
  diphthongs**; **alveolar vs dental vs retroflex** stops (the `da`/`ḍa`, `ta`/`ṭa` choice that flips
  peevishness↔shyness / staticity↔vitarka — decided on phonetic principle, **not** by which meaning "fits");
  **fricatives & affricates**; **consonant clusters**; **aspiration**; **rhotic** sounds; **phonemes with no
  exact Sanskrit equivalent** (define the nearest-varṇa policy or a drop policy); and **dialect / pronunciation
  variants** (pick one reference accent + lexicon, frozen). Each rule fixed on phonetic grounds, frozen before
  outcomes are seen.
- Stage 2 is **cross-language transfer**, evaluated against the frozen Stage-1 mechanism — never a place to
  re-tune the mechanism.

---

## PART D — Reclassification of prior English work (do not mis-read the negatives)

- **run01 (English control-extension, negative).** Ran on the **English, orthographic, consonant-only,
  vowel-less** decomposition — i.e. a Stage-2-type substrate **built before Stage 1 was hardened and on a
  flawed (spelling-based) transcription** (silent-b in doubt, /ʃ/→ta and /s/→ka in patience, /dʒ/→ga in
  courage). Its negative **bounds that English-spelling implementation**; it is **NOT** evidence against the
  native-Sanskrit hypothesis, which has not yet been developed or tested. Retained as record.
- **Gate G0 (English word-specificity, not testable).** Showed the current 11-varṇa prose-render cannot yield
  six mutually-distinctive English packets — again a limitation of the English-substrate rendering, not a
  verdict on native Sanskrit.
- **Do not interpret English failures as evidence against the native hypothesis until Stage 1 is complete.**
  All standing guardrails persist unchanged (B1.4b′ `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B
  blocked).

---

## PART E — Immediate next actions (smallest rigorous Stage-1 start; each separately approved)

1. **Provenance register (B.5)** — build the machine-readable `SOURCED/INFERRED/PROVISIONAL/CONTRADICTORY/
   MISSING` register from the v3 table (docs/data only; no table change).
2. **Inventory decision (B.1)** — a docs-only decision memo: extend to vowels/anusvāra/visarga (with sources)
   vs consonant-only Stage 1 (with rationale).
3. **Contradiction resolution (B.2)** — re-derive or quarantine `ha`, `pa`, `ṭha` from primary text; freeze
   only sourced poles.
4. **Composition-rule pre-registration (B.4)** — bag-of-varṇas vs ordered/positional, decided before scoring.
5. **Native-Sanskrit dev set + discrimination prereg (B.6)** — seed from Track G + Sarkar's own varṇa
   illustrations; blind non-Claude judges; Barnum + hard-negative controls.
Only after 1–5 and a passing B.7 test does Stage 2 (Part C) begin.

## Guardrails
Docs-only audit + plan. No code, no run, no mapping/table/context/judge change, no new experiment number.
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no ontology /
semantic-truth / Sanskrit-privilege / generation-utility / individual-varṇa claim. **B1.4b′ remains
`NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**
