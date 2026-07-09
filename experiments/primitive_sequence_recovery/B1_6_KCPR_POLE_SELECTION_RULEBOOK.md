# B1.6 — KCPR Pole-Selection Rulebook

**Status:** Pole-selection rulebook (docs + manifest only). Defines how KCPR renders the existing varṇa polarity
table into poles for the B1.6 Symbol-U generative scaffold — **without any per-target pole selection**. **No
code, no generation run, no final target-scaffold instantiation, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Selected policy: `DUAL_POLE_RENDERING`. Kosha: DEFERRED. CSR/STL: DEFERRED. Readiness:
`B1_6_KCPR_POLE_RULEBOOK_READY`.**

Subordinate to: `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` (`c1f5028`),
`B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` (`17a5ea0`),
`B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` (`1244335`).
Builds on: `B1_6_PILOT_FREEZE_PACKAGE.md` (`b252454`), `B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md` (`b680063`),
`B1_6_PHONEME_TO_VARNA_BRIDGE_ENGLISH_ASPIRATE_AMENDMENT.md` (`a629329`).
Manifest: `frozen/b1_6_kcpr_pole_selection_manifest.json`.

---

## 1. KCPR source search (re-run)

Searched the repo for `KCPR`, `Kosha`, `pole`, `polarity`, `worldly`, `liberating`, `counter`, `binding`, and
the named governing files. Relevant sources found (hashes = full sha256):

| Role | Path | sha256 (16) |
|---|---|---|
| Varṇa polarity/profile table (signed contributions) | `track_g_varna_polarity_table.json` | `5f78224c06850788` |
| **Polarity axes — named pole pairs (dual-pole source)** | `track_g_polarity_axes.json` | `37631d84eb50a611` |
| Varṇa four-sphere lexicon (companion) | `track_e_varna_sphere_lexicon.json` | `cf5f8a33d472cae7` |
| KCPR experiment rules (governing) | `VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md` | `acfff4043db5b2f1` |
| L2 validation rulebook (governing) | `SYMBOL_U_L2_VALIDATION_RULEBOOK.md` | `b0bcce75039b30ca` |
| Phoneme→varṇa bridge (reachable keys) | `frozen/b1_6_phoneme_to_varna_bridge_manifest.json` | (this session) |

**Kosha:** no frozen Kosha lexicon or Kosha→varṇa assignment rulebook exists (the only `kosha` matches are this
session's B1.6 manifests and an unrelated `b1_3` orthographic-ablation prereg). **No per-target KCPR
pole-selection rulebook exists.**

**Pole data actually available:** `track_g_polarity_axes.json` defines, for each of 10 axes, a named
`positive_pole` and `negative_pole` (all `leak_risk = low`) — a genuine **dual-pole** source.
`track_g_varna_polarity_table.json` gives each varṇa a **signed contribution** (`+1`/`-1`) on a subset of axes,
authored from the frozen `realization_en_gloss` **vṛtti binding-sense** glosses (self-declared **unvalidated
candidate representation, high-DOF, not ontological evidence**).

## 2. KCPR expansion

**No explicit KCPR expansion exists anywhere in the repo → `KCPR_EXPANSION_NOT_FOUND`** (confirmed again). For
**this B1.6 rulebook only**, define the operational expansion:

> **KCPR = Kosha-Context Pole Resolution** — *a B1.6 operational expansion, not a historical repo expansion.*

This label is used only to name the mechanism in B1.6 documents; it makes **no** historical or ontological
claim, and the "Kosha" in the name is **not** activated in the pilot (§6).

## 3. Purpose of KCPR

KCPR is the rule that decides **how a varṇa's profile is rendered into poles** for generative interpretation. It
answers:

- **When to use the binding/worldly pole vs the liberating/counter pole:** in B1.6, **neither is chosen** —
  **both** are always shown (§4). The candidate table's signed lean is displayed only as a *lean*, not a
  selection.
- **Whether both poles are shown:** **yes** — always, per axis.
- **How target context affects pole selection:** it **does not** — no per-target pole choice is made (§8).
- **How ambiguity is handled:** show both poles; record any one-sided availability as an explicit asymmetry;
  never fabricate a pole to balance (§4, §8).

## 4. Preferred safe policy — `DUAL_POLE_RENDERING`

Since no frozen rulebook selects a single pole, B1.6 adopts the conservative policy:

**`DUAL_POLE_RENDERING`** —
- each **supported consonant-varṇa** shows **both poles** of every axis it contributes to;
- the generator is **not told which pole is "correct"**;
- the generator must use the pole **pair as a tension-field**, not a truth claim;
- **no item-specific pole choice** is made before (or after) generation;
- this **avoids cherry-picking** the pole that "sounds best" for a target.

**Mechanical rule (frozen; `policy_sha256 = e74068f0ff141e7e…`):** for a varṇa contributing sign `s` on axis
`X` (with `X.positive_pole`, `X.negative_pole` from `track_g_polarity_axes.json`):
- render **both** `X.positive_pole` and `X.negative_pole`;
- mark the **table lean**: `s = +1` → worldly/binding pole = `positive_pole`; `s = −1` → worldly/binding pole =
  `negative_pole`; the **counter/liberating** pole is the opposite.

*(Honesty note: the axes are **not** uniformly "positive = binding" — e.g. `fear_courage` has `+=courage`,
`attachment_freedom` has `+=freedom`. So the worldly/counter labeling follows **only** the candidate table's
own `vṛtti binding-sense` sign, applied uniformly and mechanically. It asserts no per-axis metaphysics; both
poles are shown regardless, so a wrong lean cannot bias the generator toward a single "answer".)*

## 5. Alternative policies (evaluated)

- **`TARGET_SPECIFIC_POLE_SELECTION`** — **rejected.** There is no frozen, pre-output rule for choosing a pole
  per target; choosing one after seeing the target/output would be cherry-picking.
- **`KOSHA_LAYER_POLE_SELECTION`** — **blocked/deferred.** Requires a Kosha assignment rulebook; none exists
  (§6). Not used in the pilot.
- **`SINGLE_POLE_BY_DEFAULT`** — **rejected.** No source rule justifies collapsing to one pole; it would import
  an unvalidated pole choice as if it were correct.
- **`DUAL_POLE_RENDERING`** — **preferred/selected** (§4).

## 6. Kosha handling

No Kosha lexicon or Kosha→varṇa assignment rulebook is found. Therefore:

- **Do not invent Kosha layers.**
- **B1.6 will not use Kosha assignment in the pilot.**
- **KCPR is limited to pole *rendering* from the existing varṇa polarity tables** (the "Kosha-Context" in the
  operational name is **dormant** in the pilot).

*(If a frozen Kosha rulebook is added later, a separate amendment would define exactly how it is applied, freeze
the layer-assignment rule, and record source hashes — none of that happens here.)*

## 7. Pole rendering template

For each **supported consonant-varṇa**, aggregate its contributing axes. Exact scaffold format (per axis line):

```
{varna}: axis = {axis_id}; worldly/binding pole = {lean_pole}; liberating/counter pole = {counter_pole}; table_lean = {+1|-1}; source = track_g_varna_polarity_table.json + track_g_polarity_axes.json
```

- **Vowels:** `{vowel}: VOWEL_NO_PROFILE`
- **Unsupported segments:** `{seg}: UNSUPPORTED_NO_VARNA`

**Worked example (real data, `ka`):**

```
ka: axis = desire_contentment;   worldly/binding = desire;     liberating/counter = contentment;  table_lean = +1
ka: axis = expansion_contraction; worldly/binding = expansion; liberating/counter = contraction;  table_lean = +1
ka: axis = activity_inertia;      worldly/binding = activity;  liberating/counter = inertia;       table_lean = +1
ka: axis = ascent_descent;        worldly/binding = ascent;    liberating/counter = descent;       table_lean = +1
```

**Only low-leak axis pole *names* are rendered.** The per-varṇa vṛtti gloss `notes` (e.g. "hope / forward-
grasping desire"; `leak_risk = high`) are **never** sent to the generator or judge. Everything rendered is a
**candidate, unvalidated** representation — shown as a tension-field, never as truth.

## 8. No target tuning

KCPR **cannot** select poles based on what makes a target interpretation sound impressive. **If both poles are
available, both must be shown.** **If only one pole is available, the asymmetry is recorded** (never balanced by
a fabricated pole). The pole rendering for a varṇa is **identical regardless of the target** — it is a function
of the varṇa's frozen row, not of the word being interpreted. The rendering rule is hash-pinned
(`policy_sha256`) and frozen before any target selection; it must not change after any output or score is seen.

## 9. B1.6 scaffold impact

The intended Symbol-U scaffold frames become:

```
{VARNA_SEQUENCE}         — from Stage A′ + the frozen phoneme→varṇa bridge (b680063, a629329)
{VARNA_PROFILE_TABLE}    — per-varṇa signed axis contributions (track_g)
{KCPR_DUAL_POLE_FRAME}   — §7 dual-pole rendering (both poles per contributing axis)
```

**`{CSR_STL_FRAME}` is removed/deferred** from the B1.6 scaffold until a **frozen CSR/STL rulebook** is
separately created (CSR/STL remain ambiguous per `b252454`). The pilot scaffold is therefore a **KCPR dual-pole
varṇa scaffold**, CSR/STL-free.

## 10. Randomized-control compatibility

The `RANDOMIZED_SYMBOLU_CONTROL` must **randomize the varṇa→profile association** (under the frozen
randomization seed) **but preserve the identical KCPR dual-pole rendering *format*** — same template, same number
of axis lines where possible, same "both poles shown" structure — so the **format is not a giveaway** and the
judge stays blind to which arm is real vs randomized.

## 11. Readiness label

**`B1_6_KCPR_POLE_RULEBOOK_READY`.** A polarity source exists (`track_g` table + axes), so **not**
`B1_6_KCPR_BLOCKED_NO_POLARITY_SOURCE`. Dual-pole rendering needs **no** Kosha assignment, so the missing Kosha
rulebook does not block it → **not** `B1_6_KCPR_BLOCKED_KOSHA_REQUIRED_BUT_MISSING`. No target-specific selection
is used → **not** `B1_6_KCPR_BLOCKED_TARGET_SPECIFIC_SELECTION_UNFROZEN`. No generation/judge exposure and only
low-leak pole names are rendered → **not** `B1_6_KCPR_INVALID_LEAKAGE`.

## 12. Downstream readiness

With this rulebook `READY`, the remaining B1.6 scaffold can proceed as a **KCPR dual-pole varṇa scaffold**
(`{VARNA_SEQUENCE}` + `{VARNA_PROFILE_TABLE}` + `{KCPR_DUAL_POLE_FRAME}`), with **CSR/STL deferred**. Still
required before any pilot (each a separate gated step, none done here): final pilot **target freeze**; **scaffold
instantiation**; **randomized-control freeze**; **operator evidence-freeze declaration**; **generation run**;
**blind judging**. This rulebook removes the KCPR/Kosha blocker from the freeze package; **CSR/STL remains the
one deferred item** (satisfiable by dropping it, as done here, or by a future frozen CSR/STL rulebook).

## 13. Guardrails

No `ONTOLOGICAL_SIGNAL`. No `L1_L2_L3_ATTRIBUTE_SIGNAL`. No Sanskrit privilege. No semantic-truth /
validated-meaning claim. No claim that sound objectively encodes meaning. No rescue of B1.4b′. **B1.4b′ remains
`NULL_RETURN_BOTTOM`.** No invented varṇa meanings; no invented Kosha layers; no target-specific pole selection.
Original B1.4b remains blocked. Track B remains blocked. **Structure, not validated meaning.**

## 14. Validation checklist

- [x] **Docs/manifest only** — one Markdown rulebook + one JSON manifest; **no code**.
- [x] **No generation** — none.
- [x] **No evidence freeze** — `SPEC_MANIFEST_NOT_A_FREEZE`; `evidence_freeze_declared=false`.
- [x] **No target-specific pole selection** — `DUAL_POLE_RENDERING`; both poles always shown; target-independent.
- [x] **No invented varṇa meanings** — only existing table signs + existing axis pole names rendered.
- [x] **No invented Kosha layers** — Kosha deferred; not used in the pilot.
- [x] **Source hashes recorded** — full sha256 in §1 and the manifest.
- [x] **KCPR policy frozen** — `policy_sha256 = e74068f0ff141e7e…`; frozen before target selection.

---

## Final report

- **Files created:** `experiments/primitive_sequence_recovery/B1_6_KCPR_POLE_SELECTION_RULEBOOK.md`;
  `experiments/primitive_sequence_recovery/frozen/b1_6_kcpr_pole_selection_manifest.json`. No prior artifact
  modified.
- **Commit hash:** (recorded on commit below).
- **KCPR expansion:** **`KCPR_EXPANSION_NOT_FOUND`** in-repo → **B1.6 operational expansion = "Kosha-Context Pole
  Resolution"** (operational only, not historical).
- **Selected KCPR policy:** **`DUAL_POLE_RENDERING`** — both poles shown per contributing axis; no per-target
  selection; hash-pinned.
- **Kosha used or deferred?** **Deferred** — no Kosha lexicon exists; KCPR limited to pole rendering; no Kosha
  layers invented.
- **Readiness label:** **`B1_6_KCPR_POLE_RULEBOOK_READY`**.
- **CSR/STL:** **remains deferred** — removed from the B1.6 scaffold until a separate frozen CSR/STL rulebook is
  created.
- **No generation run was performed.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

> B1.6 KCPR pole-selection rulebook drafted docs-only. KCPR retained as the pole-rendering mechanism. No
> generation run. No evidence freeze. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B
> remains blocked. Structure, not validated meaning.
