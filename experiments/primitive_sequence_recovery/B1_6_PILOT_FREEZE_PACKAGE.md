# B1.6 — Pilot Freeze Package (Actual-Source Scaffold Instantiation Attempt)

**Status:** Freeze-package audit (docs + manifest only). Attempts to instantiate the Symbol-U scaffold for a
B1.6 pilot **using the actual project varṇa/Kosha/KCPR/CSR-STL sources**. **Outcome: BLOCKED — the scaffold
cannot be honestly instantiated from frozen sources without inventing mappings and resolving acronym ambiguity.**
**No generation run. No judging. No evidence freeze. No generated outputs. No scaffold values fabricated.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`** (with two concurrent blockers —
`B1_6_PILOT_BLOCKED_CSR_STL_RULEBOOK_AMBIGUOUS` and `B1_6_PILOT_BLOCKED_KCPR_KOSHA_RULEBOOK_AMBIGUOUS`).

Subordinate to: `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` (`c1f5028`),
`B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` (`17a5ea0`),
`B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` (`1244335`).
Manifest: `frozen/b1_6_pilot_freeze_manifest.json`.

---

## 1. Purpose

Take the abstract B1.6 pilot plan and try to make it **concrete** by filling the scaffold placeholders
(`{TARGET_TEXT}`, `{VARNA_SEQUENCE}`, `{VARNA_PROFILE_TABLE}`, `{CSR_STL_FRAME}`, plus `{KCPR_CONTEXT_FRAME}`)
from the **real** project sources — not toy values. This document reports what the actual sources are, whether
they can populate the scaffold, and, where they cannot, **stops with a blocker rather than inventing content.**
It runs no generation, judges nothing, and declares no evidence freeze.

## 2. Relationship to prior B1.6 docs

Subordinate to the prereg (claim/labels), the prompts/rubric spec (frozen templates), and the pilot
target/scaffold freeze plan (freeze procedure). Where anything here could appear to differ, **the prereg governs
first**. This document adds no new arms and no new terminal labels; it only reports a source audit and a
readiness label from the plan's pre-defined blocked-label set.

## 3. Authoritative scaffold sources — search results

Searched the repo for varṇa / Kosha / KCPR / CSR-STL lexicons, polarity/profile tables, rulebooks, and rendering
rules. **Found** (the real, versioned project varṇa sources):

| Role | Path | sha256 (16) | frozen | key space |
|---|---|---|---|---|
| Varṇa polarity/profile table | `track_g_varna_polarity_table.json` | `5f78224c06850788` | no (versioned) | 34 Sanskrit consonant varṇas |
| Varṇa four-sphere lexicon | `track_e_varna_sphere_lexicon.json` | `cf5f8a33d472cae7` | no (versioned) | 34 Sanskrit consonant varṇas |
| Polarity axes definition | `track_g_polarity_axes.json` | `37631d84eb50a611` | no (versioned) | 10 signed axes |
| Varṇa→atom assignment | `frozen/assignment.json` | `b7218e911c625f26` | yes | 34 Sanskrit consonant varṇas |
| Vṛtti gloss reference (frozen) | `frozen/realization_en_gloss.json` | `8883bcbf61e910d2` | yes | 34 varṇas → glosses |
| Decomposer named by pilot plan | `stage_a_prime_coverage.py` | `217c9ec98fc876bc` | yes | 39 bare phoneme keys |

**KCPR expansion:** searched exhaustively — the acronym `KCPR` is *used* throughout
`VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` and elsewhere but is **never expanded** anywhere in the repo.
**Reported result: `KCPR_EXPANSION_NOT_FOUND`.** (No inference of the expansion is made, per the task's explicit
instruction.)

## 4. Chosen authoritative source set

No silent merging. For the varṇa profile the **single** chosen source is
`track_g_varna_polarity_table.json` (per-varṇa signed contributions on 10 polarity axes), with
`track_e_varna_sphere_lexicon.json` as the four-sphere companion and `frozen/realization_en_gloss.json` as the
frozen gloss basis they were authored from. These are the sources **previously used in Symbol-U experiments**
(Tracks E/G), versioned in git. **No newly-invented table is introduced.**

**But every one of these sources self-declares as an *unvalidated candidate representation*:**
`authoring_status = researcher_authored_candidate_representation`, `validation_status = unvalidated`,
`source_supplies_polarity = false`, `evidence_status = not_ontological_evidence`, `degrees_of_freedom =
high_degrees_of_freedom`, and `not_for = [ontological claims, Sanskrit privilege, Track B unblocking,
validation]`. For B1.6's *generative-utility* claim that is **acceptable** (B1.6 tests whether a scaffold is
*useful*, not whether it is *true*) — but it forecloses any validity/ontology reading, exactly as the prereg
requires.

An authoritative varṇa source therefore **exists** → this is **not**
`B1_6_PILOT_BLOCKED_NO_AUTHORITATIVE_VARNA_KOSHA_KCPR_SOURCE`. The blockers are downstream (§6–§8).

## 5. Source audit (leakage)

- Both varṇa tables carry **semantic/gloss text** per varṇa (vṛtti glosses like "hope / forward-grasping
  desire"; four-sphere root names such as *moha/bhaya/kāma/tṛṣṇā/lobha*). Both files set high `leak_risk` and
  state these strings **must never be sent to a scorer/judge**. Any scaffold use would pass **only the numeric
  axis contributions**, never the gloss text — and B1.6's blind packaging already scrubs system/register
  giveaways.
- `frozen/realization_en_gloss.json` is a dictionary-like gloss source → **excluded from any judge-facing text**.
- **No dictionary/meaning leakage may enter the Symbol-U arm's *output***; the scaffold is numeric-profile only.

## 6. BLOCKER 1 — target decomposition cannot be joined to the varṇa profile table

**The decisive, mechanical finding.** The varṇa profile/polarity/sphere tables are keyed on **34 Sanskrit
consonant varṇas** (`ka, kha, ga, … ksha`; **no vowels**). The decomposer named by the pilot plan
(`stage_a_prime_coverage.py`, Stage A′) emits a **39-key bare-phoneme inventory** (`a, aa, ax, b, ch, d, … zh`).

```
overlap(Stage A′ phoneme keys, varṇa-table keys) = 0
vowels present in varṇa-table                    = 0
frozen phoneme→varṇa bridge                       = none
```

There is **no frozen mapping** from a target's decomposed phoneme sequence to the varṇa profile rows. Building
`{VARNA_PROFILE_TABLE}` for any target would require **inventing** a phoneme→varṇa bridge (e.g. `k`→`ka`,
`sh`→`sha`) — lossy, ambiguous, and with **no varṇa entry at all for vowels** — which the pilot plan and this
task **explicitly forbid** ("do not invent new varṇa meanings"; "no newly invented mappings"; "do not patch
missing mappings after seeing targets"). The same gap holds for the **original** Stage A 14-grapheme chart
(also bare graphemes, no `ka/kha` keys). It holds **regardless of track** (A_PRIME_EN or A_PRIME_SA both emit
the bare-phoneme inventory, not varṇa keys) — so even an all-Sanskrit stratum would not bridge under the named
toolchain.

Therefore `{VARNA_SEQUENCE}` could be produced (Stage A′ runs), but `{VARNA_PROFILE_TABLE}` — the substantive
content of the scaffold — **cannot** be instantiated from frozen sources. **→ `B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`.**

## 7. BLOCKER 2 — CSR/STL frame is ambiguous

`{CSR_STL_FRAME}` cannot be frozen from the sources. Searching the repo, **CSR** resolves to *multiple
conflicting* expansions — "Context × Semantic × Resonance", "Coherent Semantic Resonance", "Consonant-Syllable
Resonance", "Constraint-Structure-Resonance", "Phonemic Mental Resonance", "contextual semantic resonance" — and
**STL** to "Signal → Transformation → Laya", "Symbolic Reasoning (10D)", "Symbolic Transfer Learning". **No
single authoritative definition** is anchored in the frozen `primitive_sequence_recovery` varṇa sources, and
those sources contain **no CSR/STL fields**. Deriving a frozen CSR/STL frame would require a **choice the frozen
sources do not make** → this would be inventing content. **→ `B1_6_PILOT_BLOCKED_CSR_STL_RULEBOOK_AMBIGUOUS`**
(concurrent).

## 8. BLOCKER 3 — KCPR/Kosha context is ambiguous / unsourced

`{KCPR_CONTEXT_FRAME}` cannot be instantiated per target. `KCPR` is **never expanded** in the repo
(`KCPR_EXPANSION_NOT_FOUND`). The KCPR rules memo defines KCPR only as a **decoder-side pole-selection rule**
whose **kosha condition is *experimentally assigned* and frozen before generation — not read from a lexicon**.
There is **no frozen kosha→varṇa lexicon** and **no per-target kosha-assignment source**. Selecting a kosha per
pilot item, or a polarity pole per axis, would be an **invented** assignment. **→
`B1_6_PILOT_BLOCKED_KCPR_KOSHA_RULEBOOK_AMBIGUOUS`** (concurrent).

*(If a future run **assigned** a fixed kosha condition experimentally — per the KCPR rules — and used it
identically across all arms, this blocker could be lifted for that run; it is not resolvable from existing
frozen data alone, so it blocks now.)*

## 9. Pilot target set

**Not frozen.** A frozen 20–30-item pilot target set is *not* produced here, because the scaffold that the
targets must feed **cannot be instantiated** (§6–§8). Freezing targets now would be premature and could invite a
post-hoc scaffold patch to "fit" them — which is forbidden. The `TOY_ONLY` illustrative target table in
`B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` §6 remains the only target material, and remains `TOY_ONLY`
(not frozen, not scored, not evidence). **No target set is frozen by this document.**

## 10. Target decomposition

`{VARNA_SEQUENCE}` and normalized `{TARGET_TEXT}` **could** be produced for a target via Stage A′ (100% coverage
on the repo pools; no silent fallback; unsupported segments reported). But because the sequence cannot be joined
to the profile table (§6), decomposition is **not carried out for a frozen set here** — it would be a dead-end
half-scaffold. No decompositions are hand-patched. **→ blocked at `B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`.**

## 11. Symbol-U scaffold instantiation

**Not performed.** `{VARNA_PROFILE_TABLE}`, `{CSR_STL_FRAME}`, and `{KCPR_CONTEXT_FRAME}` **cannot** be populated
from frozen sources (§6–§8). **No scaffold values were fabricated**; the file
`frozen/b1_6_pilot_targets_scaffolds.json` was **deliberately not created**, because it could only be filled by
inventing the very mappings the task forbids.

## 12. KCPR/Kosha context handling

See §8. `KCPR_EXPANSION_NOT_FOUND`. KCPR is a decoder-side pole-selection rule with an **experimentally-assigned,
pre-frozen kosha condition**, applied mechanically and identically within a paired comparison; **pole choice must
never be inferred from the target's meaning after seeing the item**. No frozen kosha→varṇa lexicon exists, so no
`{KCPR_CONTEXT_FRAME}` is instantiated. **→ `B1_6_PILOT_BLOCKED_KCPR_KOSHA_RULEBOOK_AMBIGUOUS`.**

## 13. CSR/STL handling

See §7. No single explicit CSR/STL definition governs the `primitive_sequence_recovery` varṇa sources; the varṇa
tables carry no CSR/STL fields. Only the **10 polarity axes** (`track_g_polarity_axes.json`) are explicitly and
consistently defined — but those are the *polarity* axes, not a CSR/STL frame, and by themselves are
interpretive-only, never a scoring signal for B1.6. Because a frozen CSR/STL frame cannot be derived without an
un-sourced choice, this is recorded as **`B1_6_PILOT_BLOCKED_CSR_STL_RULEBOOK_AMBIGUOUS`**.

## 14. Randomized Symbol-U control

**Not frozen.** A deterministic randomized control (fixed seed; shuffled/relabelled varṇa profiles; matched
length/format; no reveal to generator or judge) is well-specified in the plan, **but it is a permutation of the
real profile scaffold** — which does not exist for these targets (§6). With nothing to shuffle, no randomized
control is generated or frozen here. **No randomization manifest/hash is produced.** *(Downstream of the primary
blocker; would otherwise be `B1_6_PILOT_BLOCKED_RANDOMIZED_CONTROL_UNFROZEN`.)*

## 15. Baseline parity manifest

Parity requirements are unchanged and remain enforceable once a scaffold exists: all arms receive the **same
target text, same neutral context, same output format, same later model settings, same length budget, and no arm
labels in final output** (prompt spec §5, §18). No arm is run here.

## 16. Freeze manifest

`frozen/b1_6_pilot_freeze_manifest.json` records: the prior B1.6 doc hashes; the candidate scaffold source paths
+ full sha256 + frozen/versioned status + what each contains + leakage notes; the decomposition-join audit
(overlap 0); the CSR/STL audit (conflicting expansions); the KCPR/Kosha audit (`KCPR_EXPANSION_NOT_FOUND`, no
kosha lexicon); `scaffold_values_instantiated=false`; `randomized_control_frozen=false`;
`evidence_freeze_declared=false`; and the readiness label. It is an **audit record, not a freeze** —
`status = AUDIT_ONLY_NOT_A_FREEZE`. It contains **no generated text, no fabricated scaffold, no raw gloss dumps**
(only the already-in-repo source hashes and counts).

## 17. Readiness label

**`B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`** — the target decomposition cannot be joined to the frozen varṇa
profile table (zero key overlap; vowels absent; no frozen bridge; bridging would require forbidden invented
mappings), so `{VARNA_PROFILE_TABLE}` cannot be instantiated. **Concurrent blockers:**
`B1_6_PILOT_BLOCKED_CSR_STL_RULEBOOK_AMBIGUOUS` (§7, §13) and
`B1_6_PILOT_BLOCKED_KCPR_KOSHA_RULEBOOK_AMBIGUOUS` (§8, §12) — each independently prevents readiness. Not
`..._NO_AUTHORITATIVE_VARNA_KOSHA_KCPR_SOURCE` (a source exists, §4). Not `..._READY`. Not `..._INVALID_LEAKAGE`
(no leakage occurred — nothing was generated or packaged).

**What would unblock a pilot** (each a separate, pre-registered, blind, frozen step — none done here): (a) a
frozen, blind-authored **phoneme→varṇa bridge** (or a varṇa-native segmenter that emits `ka/kha` keys **and** a
vowel treatment), so `{VARNA_PROFILE_TABLE}` can be built without invention; (b) a **single frozen CSR/STL
definition** anchored in the sources, or dropping the CSR/STL axis and declaring the scaffold uses the 10
polarity axes only; (c) an **experimentally-assigned, pre-frozen kosha condition** applied identically across
arms per the KCPR rules, with `KCPR` explicitly expanded — or dropping the KCPR frame from the pilot scaffold.

## 18. Leakage and overclaim guard

- **No generated text created.** **No judge exposure.** **No semantic-truth claim.** **No `ONTOLOGICAL_SIGNAL`.**
  **No Sanskrit privilege.** **No target-specific varṇa editing.** **No post-hoc target replacement after
  freeze** (nothing was frozen). **No invented varṇa mappings.** Gloss/root strings kept out of any
  judge-facing surface (none exists yet).

## 19. Validation checklist

- [x] **Docs/manifest only** — one Markdown audit + one JSON manifest; no code.
- [x] **No generation** — none.
- [x] **No evidence freeze** — `evidence_freeze_declared=false`; manifest is `AUDIT_ONLY_NOT_A_FREEZE`.
- [x] **Source hashes recorded** — full sha256 in the manifest and §3 table.
- [x] **Scaffold placeholders populated OR blocker emitted** — **blocker emitted**
  (`B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION` + two concurrent); no placeholder fabricated.
- [x] **KCPR explicitly searched** — yes; **`KCPR_EXPANSION_NOT_FOUND`** reported (no inference).
- [x] **KCPR expansion reported if found** — not found; reported as such.
- [x] **CSR/STL explicitly searched** — yes; conflicting expansions recorded → ambiguous.
- [x] **Randomized control frozen OR blocker emitted** — not frozen (downstream of the primary blocker);
  recorded.
- [x] **Prior artifacts untouched** — B1.6 prereg/prompt-spec/pilot-plan, B1.4b′ artifacts, Stage A, Stage A′,
  scorer, B1.3, B1.4a, B1.4b, and lexicons all unmodified (only new files added).

## 20. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning claim. No claim that sound objectively encodes meaning. No rescue of B1.4b′. No
reuse-as-positive of any prior null. No invented varṇa meanings; no post-hoc mapping patch. Original B1.4b
remains blocked. Track B remains blocked. **Structure, not validated meaning.**

---

## Final report

- **Files created:** `experiments/primitive_sequence_recovery/B1_6_PILOT_FREEZE_PACKAGE.md`;
  `experiments/primitive_sequence_recovery/frozen/b1_6_pilot_freeze_manifest.json`.
  **Deliberately NOT created:** `frozen/b1_6_pilot_targets_scaffolds.json` (could only be filled by inventing
  forbidden mappings).
- **Commit hash:** (recorded on commit below).
- **Selected varṇa/Kosha/KCPR/CSR-STL/rulebook source paths:** `track_g_varna_polarity_table.json`
  (varṇa polarity/profile), `track_e_varna_sphere_lexicon.json` (four-sphere), `track_g_polarity_axes.json`
  (10 axes), `frozen/assignment.json` (varṇa→atom), `frozen/realization_en_gloss.json` (vṛtti glosses),
  governed by `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` and `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`; decomposer
  `stage_a_prime_coverage.py`. **No Kosha lexicon and no CSR/STL rulebook found.**
- **KCPR expansion:** **`KCPR_EXPANSION_NOT_FOUND`** (acronym used, never expanded in-repo; no inference made).
- **Readiness label:** **`B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`** (concurrent:
  `B1_6_PILOT_BLOCKED_CSR_STL_RULEBOOK_AMBIGUOUS`, `B1_6_PILOT_BLOCKED_KCPR_KOSHA_RULEBOOK_AMBIGUOUS`).
- **Were actual scaffold values instantiated?** **No** — `{VARNA_PROFILE_TABLE}`, `{CSR_STL_FRAME}`,
  `{KCPR_CONTEXT_FRAME}` cannot be built from frozen sources without inventing mappings; none fabricated.
- **Were randomized Symbol-U controls frozen?** **No** — nothing to permute without the real profile scaffold.
- **No generation run was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is not a semantic-decoding or ontology claim** — it is a source-audit for a *generative-utility-of-a-
  scaffold* pilot, which is blocked pending an honestly-frozen phoneme→varṇa bridge and disambiguated CSR/STL and
  KCPR/Kosha frames.

> B1.6 pilot freeze package drafted using actual project varṇa/Kosha/KCPR/CSR-STL sources where available. No
> generation run. No evidence freeze. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B
> remains blocked. Structure, not validated meaning.
