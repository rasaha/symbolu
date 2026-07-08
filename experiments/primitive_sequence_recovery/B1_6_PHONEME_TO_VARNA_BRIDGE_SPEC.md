# B1.6 — Phoneme→Varṇa Bridge Specification

**Status:** Bridge specification (docs + manifest only). Defines a **frozen, target-independent** lookup from the
Stage A′ decomposer's single-phoneme keys to the existing Sanskrit consonant-varṇa profile keys, so B1.6
`{VARNA_PROFILE_TABLE}` can be populated later **without inventing target-specific mappings**. **No code, no
generation run, no target-scaffold instantiation, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Bridge mode: `CONSONANT_ONLY_BRIDGE`. Readiness label: `B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY`.**

Subordinate to: `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` (`c1f5028`),
`B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` (`17a5ea0`),
`B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` (`1244335`),
`B1_6_PILOT_FREEZE_PACKAGE.md` (`b252454`).
Manifest: `frozen/b1_6_phoneme_to_varna_bridge_manifest.json`.

---

## 1. Purpose

Define a **mechanical, frozen lookup bridge** from the frozen decomposer's phoneme keys (Stage A′,
`stage_a_prime_coverage.py`) to the existing varṇa profile keys (`track_g_varna_polarity_table.json`,
`track_e_varna_sphere_lexicon.json`), so that B1.6 scaffold instantiation (`{VARNA_SEQUENCE}` →
`{VARNA_PROFILE_TABLE}`) can proceed later **without ad-hoc invention**. The bridge is authored **before** any
B1.6 target freeze, is **target-independent**, and changes no prior artifact, no evidence, and no code.

## 2. Relationship to the prior B1.6 blocker

`B1_6_PILOT_FREEZE_PACKAGE.md` (`b252454`) and `frozen/b1_6_pilot_freeze_manifest.json` recorded the honest
blocker **`B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`**: the varṇa profile tables are keyed on 34 Sanskrit
consonant varṇas (`ka, kha, …`) while the decomposer emits 39 bare-phoneme keys (`a, b, ch, …`), with
**overlap = 0** and **no vowels** in the tables. Without a pre-frozen bridge, `{VARNA_PROFILE_TABLE}` could not
be built for any target except by inventing a phoneme→varṇa map — which is forbidden. This document supplies
exactly that pre-frozen bridge, built from the actual key spellings, so the join is mechanical rather than
invented.

## 3. What this bridge CAN do

It can define a **mechanical lookup** — phoneme key → varṇa profile key — used **only** to assemble the
generative-utility scaffold's `{VARNA_PROFILE_TABLE}`. It is a data-plumbing convenience for scaffold
construction: it lets each decomposed consonant phoneme fetch its row from the existing (unvalidated, candidate)
varṇa profile tables.

## 4. What this bridge CANNOT do

It cannot prove: **semantic truth**; **ontology**; **Sanskrit privilege**; that **phonemes objectively encode
meaning**; that **B1.4b′ was wrong** (it stands); `ONTOLOGICAL_SIGNAL`; or `L1_L2_L3_ATTRIBUTE_SIGNAL`. It is a
lookup convention over **self-declared unvalidated candidate** tables; even a downstream B1.6 utility win would
be **scaffold usefulness on a task**, never validated meaning. The bridge also **loses information** (§7–§8), so
it cannot even be read as a faithful phonological representation — only as a frozen, auditable scaffold input.

## 5. Authoritative source audit (from `b252454`, re-verified)

| Role | Path | sha256 (16) | frozen |
|---|---|---|---|
| Varṇa polarity/profile table | `track_g_varna_polarity_table.json` | `5f78224c06850788` | no (versioned) |
| Varṇa four-sphere lexicon | `track_e_varna_sphere_lexicon.json` | `cf5f8a33d472cae7` | no (versioned) |
| Polarity axes | `track_g_polarity_axes.json` | `37631d84eb50a611` | no (versioned) |
| Varṇa→atom assignment | `frozen/assignment.json` | `b7218e911c625f26` | yes |
| Vṛtti gloss reference | `frozen/realization_en_gloss.json` | `8883bcbf61e910d2` | yes |
| Governing rules | `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` | — | — |
| Governing rulebook | `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` | — | — |
| Decomposer | `stage_a_prime_coverage.py` | `217c9ec98fc876bc` | yes |

Also recorded (unchanged from the freeze-package audit): **`KCPR_EXPANSION_NOT_FOUND`** (acronym never expanded
in-repo); **no Kosha lexicon found**; **CSR/STL rulebook ambiguous** (multiple conflicting expansions, no frozen
frame). This bridge resolves **only** the decomposition→profile join; §7's CSR/STL and KCPR blockers remain and
are **out of scope** here.

## 6. Bridge design choice

Three options were evaluated:

- **A. `CONSONANT_ONLY_BRIDGE`** — map consonant phoneme keys to the existing consonant varṇa profile keys;
  retain vowels in the sequence but exclude them from profile lookup (they have no entry). Uses **only existing
  tables**; invents nothing. **Safest.**
- **B. `BLOCK_UNTIL_VOWEL_PROFILES_EXIST`** — run no B1.6 pilot until an authoritative vowel-profile source is
  added. Correct but unnecessarily halts a consonant-scaffold pilot that the prereg permits.
- **C. `ADD_VOWEL_PROFILES`** — allowed **only if** an already-existing, frozen, authoritative vowel-profile
  source is found. **Search result:** none. The consonant tables have **zero** vowel keys, and
  `H2_EXPERIMENTAL_VOWEL_POSITIONAL_POLARITY_MEMO.md` provides only an **experimental, single positional binding
  pole** for a word-initial vowel (explicitly "NOT SEMANTIC EVIDENCE") — **not** a full varṇa profile of the
  consonant-table schema. Option C is therefore **disallowed** (no authoritative vowel source; adding one would
  be invention).

**Recommendation: Option A, `CONSONANT_ONLY_BRIDGE`**, with vowels marked `VOWEL_NO_PROFILE` (§9).

## 7. Consonant mapping table (frozen; existing table keys only)

Applied to **single-phoneme keys after Stage A′ decomposition** (the bridge does **not** modify the decomposer).
`mapping_table_sha256 = 1415350d3fabe6ffb433edf4fe82e56f8a5af8b3ee2eed4905e9de0c1b1332b3`.

| phoneme | → varṇa | notes / justification |
|---|---|---|
| `k` | `ka` | velar stop |
| `g` | `ga` | velar stop |
| `t` | `ta` | **dental** (retroflex is `tr`) |
| `d` | `da` | **dental** (retroflex is `dr`) |
| `tr` | `tta` | retroflex ṭ (decomposer's `tr` = "retroflex ṭ/ḍ") |
| `dr` | `dda` | retroflex ḍ |
| `p` | `pa` | labial stop |
| `b` | `ba` | labial stop |
| `m` | `ma` | labial nasal |
| `n` | `na` | dental nasal |
| `nr` | `nna` | retroflex ṇ |
| `ng` | `nga` | velar ṅ |
| `ny` | `nya` | palatal ñ |
| `ch` | `ca` | **base palatal affricate** — decomposer maps IAST `c`→`ch` and splits `chh`→`ch,h`, so `ch` is the *unaspirated* base → `ca`, **not** `cha` (§8 collapse) |
| `jh` | `ja` | **base voiced palatal affricate** — decomposer maps `j`→`jh` and `jh`→`jh`, so `jh` is the base → `ja`, **not** `jha` (§8 collapse) |
| `th` | `tha` | dental aspirate (decomposer keeps `th` as a single phoneme → reachable) |
| `dh` | `dha` | dental aspirate voiced (single phoneme → reachable) |
| `s` | `sa` | dental sibilant |
| `sh` | `sha` | palatal ś (decomposer maps `ś`→`sh`) |
| `shr` | `ssa` | retroflex ṣ (decomposer maps `ṣ`→`shr`) — **distinct** from `sh` |
| `h` | `ha` | glottal |
| `r` | `ra` | liquid |
| `l` | `la` | liquid |
| `y` | `ya` | glide |
| `v` | `va` | labial semivowel |
| `w` | `va` | **recorded collapse** — `va` is the classical labial semivowel; English `v`/`w` distinction is lost (§8) |

**The table respects the actual key spellings.** It uses `ca` (not `cha`) and `ja` (not `jha`) because the
decomposer's `ch`/`jh` phonemes are the *unaspirated bases*; it keeps `s`/`sh`/`shr` → `sa`/`sha`/`ssa`
distinct; it keeps dental/retroflex `t,d,n` vs `tr,dr,nr` distinct. **Ambiguous contrasts the decomposer does
not carry are not silently collapsed into a new key — they are recorded as losses (§8).**

**Coverage:** **25 of 34** varṇa profile keys are reachable. **9 are unreachable:** `kha, gha, cha, jha, ttha,
ddha, pha, bha, ksha` — all **aspirated** stops/affricates (plus the conjunct `ksha`). Because the decomposer
splits most aspirates into base + `h` (`kh`→`[k,h]`, `gh`→`[g,h]`, `ph`→`[p,h]`/`[f]`, `bh`→`[b,h]`, retroflex
`ṭh/ḍh`→`[tr/dr,h]`) or collapses affricate aspiration, **aspiration cannot be recovered from the phoneme
stream**, so aspirated varṇa keys cannot be selected. This is a **documented structural limitation of the
scaffold input**, not a defect this spec may "fix" by invention.

## 8. Ambiguity policy

- **Dental vs retroflex `t`/`d`** — **preserved**: `t`→`ta`, `d`→`da` (dental); `tr`→`tta`, `dr`→`dda`
  (retroflex). No collapse.
- **Palatal `c`/`ch` (aspiration)** — **collapsed with record**: `ch`→`ca`; `cha` is unreachable. Aspiration
  loss recorded.
- **`ś`/`ṣ`/`s`** — **preserved**: `s`→`sa`, `sh`→`sha`, `shr`→`ssa`. No collapse.
- **English `f`, `z`, `w`, `th`, `dh`** — `th`→`tha`, `dh`→`dha` (dental aspirates, reachable); `w`→`va`
  (recorded v/w collapse); **`f`, `z`** have **no Sanskrit varṇa** → **`UNSUPPORTED_NO_VARNA`** (also `zh`).
- **Clusters** — the decomposer already tokenizes to single phonemes (e.g. `x`→`[k,s]`, `qu`→`[k,w]`); each
  resulting single phoneme is looked up independently. The conjunct `ksha` key is therefore **never** produced
  (unreachable).
- **Aspirates** — velar/labial/palatal/retroflex aspirates are unreachable (aspiration split/collapsed); only
  dental `th`/`dh` reach `tha`/`dha`. Recorded.
- **Nasal distinctions** — **preserved**: `na`/`nna`/`nga`/`nya`.
- **Unsupported phonemes** — retained in the sequence, marked `UNSUPPORTED_NO_VARNA`, **excluded** from the
  profile table, and **reported visibly** (§10). Never silently dropped or coerced to a "nearest" key.

**Policy in one line:** map only single phonemes that resolve to exactly **one existing** varṇa key; record
every collapse; mark everything else `VOWEL_NO_PROFILE` (§9) or `UNSUPPORTED_NO_VARNA` (§10). **No conservative
default is used where it would fabricate a distinction.**

## 9. Vowel policy (first-run)

- Vowels (`a, aa, ax, e, i, ii, o, u, uu`) **and vocalic `rv`** are **retained in `{VARNA_SEQUENCE}`**.
- Each is **marked `VOWEL_NO_PROFILE`**.
- Vowels are **excluded from `{VARNA_PROFILE_TABLE}`** (the consonant-only tables have no vowel rows).
- The assembled scaffold **explicitly states** that vowel profiles are unavailable in the current table.
- **No vowel meanings are invented.** (Option C remains disallowed until an authoritative frozen vowel-profile
  source exists.)

## 10. Unsupported-segment policy

- Unsupported segments (`f, z, zh`, or any future unmatched phoneme) are **recorded** with the tag
  `UNSUPPORTED_NO_VARNA`, kept in the sequence, and **excluded** from the profile lookup — **visibly**, never
  silently.
- A target **may remain eligible** with some unsupported segments, **provided** its unsupported rate is within
  the pilot cap.
- **Pre-declared cap for pilot eligibility:** a target is eligible only if **≥ 60%** of its consonant phonemes
  map to varṇa keys (equivalently, **> 40% unsupported consonants → ineligible**). *(This is a frozen eligibility
  threshold, not a per-target tuning knob; it is declared here, before any target set, and applies uniformly.)*
- Targets exceeding the cap must be **replaced before freeze using the pre-declared selection rules** in
  `B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` §5 — **not** by editing the bridge to accommodate them.

## 11. English vs Sanskrit handling

- **Same bridge** for both tracks — both A_PRIME_EN and A_PRIME_SA decompose to the shared 39-phoneme inventory,
  and the bridge operates on that inventory.
- **Sanskrit transliteration (A_PRIME_SA) may preserve more distinctions** (retroflex/palatal/sibilant via
  diacritics) that **English (A_PRIME_EN) collapses** (e.g. English `t` is always dental `ta`; English has no
  way to reach retroflex `tta` without IAST input). **Neither track recovers aspiration** for velar/labial/
  palatal stops.
- **No language-specific override rule is added here.** Any future language-specific rule **must be frozen
  before target selection** and recorded in the manifest; introducing one after seeing targets is forbidden
  (§12).

## 12. No-target-tuning rule

The bridge (mapping, vowel policy, unsupported policy, eligibility cap) is **frozen before** the final B1.6
target freeze and **must not be changed after** seeing any target's decomposition, scaffold, generated output,
or judge score. Its hash (`mapping_table_sha256` in the manifest) pins it. Any change constitutes a new,
separately-justified bridge version — never a silent patch.

## 13. Bridge manifest

`frozen/b1_6_phoneme_to_varna_bridge_manifest.json` records: the selected **bridge mode**
(`CONSONANT_ONLY_BRIDGE`); the **source hashes** (decomposer + varṇa tables + gloss/assignment); the **mapping
table** and its `mapping_table_sha256`; the **vowel policy**, **unsupported policy**, and **ambiguity/collapse**
records; the **coverage audit** (25 reachable / 9 unreachable varṇa keys); and the **readiness label**. It is a
**spec manifest, not a freeze** (`status = SPEC_MANIFEST_NOT_A_FREEZE`); it declares no evidence freeze and
instantiates no target scaffold.

## 14. Readiness label

**`B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY`.** A safe, target-independent consonant mapping exists using only
existing varṇa keys (§7); the vowel policy is explicit and invents nothing (§9); the unsupported policy is
explicit and visible (§10); ambiguities are recorded as collapses, not silently merged (§8). Not
`..._BLOCKED_NO_SAFE_MAPPING` (25 keys map safely). Not `..._BLOCKED_VOWEL_POLICY` (vowels handled by explicit
exclusion, not invention). Not `..._BLOCKED_AMBIGUOUS_KEYS` (ambiguity handled by recorded collapse/unsupported).
Not `..._INVALID_LEAKAGE` (no generation, no judge exposure; gloss strings kept out of scope).

*(Ready is scoped narrowly to the decomposition→profile join. The B1.6 pilot as a whole remains blocked on the
still-open CSR/STL and KCPR/Kosha items, §5, and on the downstream steps in §15.)*

## 15. Downstream effect

Even with this bridge `..._READY`, a B1.6 pilot still requires, each as a separate gated step (none done here):

1. **final pilot target freeze** (20–30 items, stratified);
2. **scaffold instantiation** (`{VARNA_SEQUENCE}` → `{VARNA_PROFILE_TABLE}` via this bridge);
3. **`{CSR_STL_FRAME}` disambiguation or drop**, and **`{KCPR_CONTEXT_FRAME}` resolution or drop** (still
   `CSR_STL_RULEBOOK_AMBIGUOUS`, `KCPR_EXPANSION_NOT_FOUND`, no kosha lexicon);
4. **randomized Symbol-U control freeze** (deterministic seed);
5. **operator evidence-freeze declaration**;
6. **generation run**;
7. **blind judging**.

The bridge removes **one** of the three freeze-package blockers (`TARGET_DECOMPOSITION`); the other two remain.

## 16. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning claim. No claim that sound objectively encodes meaning. No rescue of B1.4b′. **B1.4b′ remains
`NULL_RETURN_BOTTOM`.** No invented varṇa meanings; no target tuning. Original B1.4b remains blocked. Track B
remains blocked. **Structure, not validated meaning.**

## 17. Validation checklist

- [x] **Docs/manifest only** — one Markdown spec + one JSON manifest; **no code**.
- [x] **No code implementation** — the bridge is a data table, not an executable.
- [x] **No generation** — none.
- [x] **No evidence freeze** — `SPEC_MANIFEST_NOT_A_FREEZE`; `evidence_freeze_declared=false`.
- [x] **No prior artifacts modified** — Stage A, Stage A′, scorer, B1.3, B1.4a, B1.4b, B1.4b′, lexicons, and
  prior B1.6 docs all unmodified (only new files added).
- [x] **No target-specific tuning** — bridge is target-independent, frozen before target selection.
- [x] **No invented varṇa meanings** — only existing table keys used; unreachable/unsupported recorded, not
  fabricated.
- [x] **Vowel policy explicit** — `VOWEL_NO_PROFILE` (§9).
- [x] **Unsupported policy explicit** — `UNSUPPORTED_NO_VARNA` + eligibility cap (§10).

---

## Final report

- **Files created:** `experiments/primitive_sequence_recovery/B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md`;
  `experiments/primitive_sequence_recovery/frozen/b1_6_phoneme_to_varna_bridge_manifest.json`.
- **Commit hash:** (recorded on commit below).
- **Selected bridge mode:** **`CONSONANT_ONLY_BRIDGE`** (Option A). Option C (`ADD_VOWEL_PROFILES`) disallowed —
  no authoritative frozen vowel-profile source exists.
- **Readiness label:** **`B1_6_PHONEME_VARNA_BRIDGE_SPEC_READY`** (scoped to the decomposition→profile join;
  CSR/STL and KCPR/Kosha remain open).
- **Mapping table proposed/frozen?** Proposed and hash-pinned (`mapping_table_sha256 = 1415350d3fabe6ff…`);
  26 phoneme keys → 25 distinct varṇa keys; **9 aspirated/conjunct varṇa keys unreachable** (aspiration is not
  carried by the phoneme stream) — recorded, not fabricated. It is frozen **as a spec** (not an evidence
  freeze).
- **Vowel treatment explicit?** **Yes** — `VOWEL_NO_PROFILE`: retained in sequence, excluded from profile, no
  vowel meanings invented.
- **Unsupported-segment policy explicit?** **Yes** — `UNSUPPORTED_NO_VARNA` for `f, z, zh`, visibly recorded,
  with a pre-declared ≥60% consonant-coverage eligibility cap.
- **No generation run was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is not a semantic-decoding or ontology claim** — it is a frozen data-plumbing bridge over
  self-declared unvalidated candidate tables, for *generative-utility scaffold construction* only.

> B1.6 phoneme→varṇa bridge spec drafted docs-only. No generation run. No evidence freeze. B1.4b′ remains
> NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.
