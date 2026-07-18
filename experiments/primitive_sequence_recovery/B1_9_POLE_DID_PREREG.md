# B1.9 — Pole Diff-in-Diff Probe — PREREGISTRATION

**Status:** preregistration + implemented, mock-tested driver. **No real generation. No judging. No
`GENUTILITY_*` terminal label.** Real run is **gated on operator sign-off of the referent classification.**

**Readiness label: `B1_9_POLE_DID_DRIVER_READY_MOCK_TESTED`.**

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** No ontology, no Sanskrit privilege, no semantic-truth claim.

---

## 0. Purpose

Test whether the **binding/liberating pole resolution** carries *varṇa-specific* meaning — controlling for the
trivial confound that pole-polarized words (surrender, dread) have a plain word-meaning ↔ pole-valence
congruence. A bare correct-vs-flipped test cannot separate the two; a **diff-in-diff** can.

## 1. Design — 4 arms (pole is manipulated; a distant word W′ is the valence control)

For each target `W` (with its context):

| arm | facets | 
|---|---|
| **`OWN_CORRECT_POLE`** | `W`'s own varṇas at `W`'s referent-correct pole |
| **`OWN_FLIPPED_POLE`** | `W`'s own varṇas at the OPPOSITE pole |
| **`CONTROL_CORRECT_POLE`** | a distant word `W′`'s varṇas at `W`'s correct pole |
| **`CONTROL_FLIPPED_POLE`** | `W′`'s varṇas at the OPPOSITE pole |

All four are readings **of `W`** (same target, same context, same plane); only the facet source (own/`W′`) and the
pole (correct/flipped) vary. `W′` is a **frozen seeded derangement** (no fixed point), selected with **no
reference to any output/score**.

## 1b. Rendering rule (CORRECTED) + contrastive audit

The first (permissive) run of this same experiment was **inconclusive**: it rendered facets as "a lens" and the
model frequently used the *flipped* pole **contrastively** (e.g. *"equanimity is a shield against grasping
desire"*), so correct-vs-flipped did not cleanly vary pole correctness (see `B1_9_POLE_DID_RESULTS.md`;
flipped-arm contrastive rate 60–67% vs correct 46–58%; 10/11 own-flipped wins were contrastive). This is the
**same** `B1.9_pole_did` experiment (same items, varṇas, poles, `W′`, arms, DiD) with **only the rendering
instruction corrected** — not a new representation.

**Corrected render instruction (all four arms, identical):**
> *"Render each facet as the word's **direct inner meaning** in this context. Do not frame any facet as the
> word's obstacle, opposite, contrast, antidote, what it resists, what it overcomes, what it is free from, or
> what it protects against."*

**Contrastive-marker audit (diagnostic only):** every output is scanned for contrastive markers (`against`,
`overcomes`, `resists`, `shield against`, `free from`, `freedom from`, `rather than`, `instead of`, `antidote`,
`opposite`, `release from`, `letting go of`, …) and per-arm rates are reported in the run manifest. **No output is
dropped and no score is penalized** on this basis (no post-hoc dropping unless a future prereg specifies it); the
audit only confirms the corrected prompt reduced contrastive framing vs the permissive run.

## 2. Primary statistic

`DiD = (OWN_CORRECT_POLE − OWN_FLIPPED_POLE) − (CONTROL_CORRECT_POLE − CONTROL_FLIPPED_POLE)`, paired by item
(penalty-adjusted composite; `specificity_to_target` as a secondary). Report all four arm means, both component
diffs, and the DiD with bootstrap CI + sign test.

## 3. Interpretation (fixed in advance)

- **`OWN_CORRECT` beats `OWN_FLIPPED` but the CONTROL shows the same margin** → generic pole-valence congruence
  (word meaning ↔ pole valence), **not** varṇa-specific signal. `DiD ≈ 0`.
- **Only an EXCESS own-mapping margin (`DiD > 0`, robust)** supports **pole-specific varṇa resolution** — and even
  then it is **low-level only**: no ontology, no semantic truth, no Sanskrit privilege, no `GENUTILITY_*`.
- **`DiD ≈ 0` (null) is informative** — the pole resolution adds nothing beyond generic valence.
- **`DiD < 0`** would anti-support the mapping.
- **If the contrastive audit shows framing is still high under the corrected prompt** (the instruction failed),
  the run is again **inconclusive**, not a clean null — report and do not over-read.
- No terminal verdict under any outcome.

## 4. Item set (24; balanced 12 liberating / 12 binding; no ambiguous items)

Frozen in `frozen/b1_9_pole_did_items.json`. Liberating (subjective release/realization): surrender, release,
forgiveness, awakening, acceptance, clarity, insight, letting-go, peace, compassion, equanimity, liberation.
Binding (physical/objectified + subjective contraction): anchor, cage, chain, wall, lock, weight, terror,
craving, dread, resentment, obsession, panic. Correct pole set by the **referent-ontology rule**
(physical/objectified/contraction → binding; subjective release/realization/transformation → liberating; valence
**not** used). **Anti-circularity:** the classification must be operator-approved
(`classification_approved: true`) **before** any generation; the gate refuses otherwise.

## 5. Varṇa derivation — CANONICAL, consonant-only

Sequences derived by **`stage_a_prime_coverage.normalize(word, "A_PRIME_EN")` + the frozen
`b1_6_phoneme_to_varna_bridge_manifest.json` mapping** — the exact path that produced the B1.6/B1.8/B1.9 targets
(**verified to reproduce all 12 existing sequences**; `varna_lens` does **not** and is not used). No dedup
(repeats kept). Both the decomposer and bridge are pinned as freeze-gate hash inputs.

### 5b. Vowel-omission limitation (recorded)

- The current frozen Symbol-U tables are **consonant-only**; every varṇa key is a consonant.
- Vowels are marked **`VOWEL_NO_PROFILE`** and **dropped** (and `f/z/zh` → `UNSUPPORTED_NO_VARNA`).
- This **may underrepresent Sanskrit varṇa theory**, in which vowels/svara may be central (mātṛkā/bīja).
- **Adding vowels would require** a new sourced/researcher-authored vowel table, a new representation version, a
  new bridge, new hashes, and a **separate prereg** — it is **not** retrofitted here. No vowel meanings invented.
- For this probe, consonant-only is accepted deliberately (it isolates the consonant contribution and removes the
  vowel-processing aspect); the omission is a stated limitation, not a validated choice.

## 6. Models, blinding, judging

Generators Mistral-7B-Instruct-v0.3 (M1) + Qwen2.5-7B-Instruct (M2); judges Llama-3.1-8B, Meta-Llama-3-8B,
Gemma-2-9b (disjoint families). **Expected: 24 × 4 × 2 = 192 outputs; × 3 = 576 ratings.** Judges see only
`{item_id, target_text, neutral_context, blinded_output_id, generation_text, output_format}` — never the arm,
pole, `W′`, or generator. Blinding reuses the shared whole-word leak matcher; content words not filtered (all four
arms draw from the same table → no differential attrition). Judging + aggregation reuse the B1.6-v2 panel and
`judge_b1_6_pilot_outputs.aggregate` unchanged; the DiD is computed from the unblinded per-(item,arm) composites.

## 7. Guardrails

No real generation/judging in this commit. No `run_out/` committed. No `GENUTILITY_*`, ontology, semantic-truth,
or Sanskrit-privilege claim. No v3 / vowel representation. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure, not
validated meaning.

---

## Final report

- **Files:** `B1_9_POLE_DID_PREREG.md`, `run_b1_9_pole_did.py`, `test_run_b1_9_pole_did.py`,
  `build_b1_9_pole_did_scaffold.py`, `frozen/b1_9_pole_did_items.json` (DRAFT — needs sign-off),
  `frozen/b1_9_pole_did_scaffold.json`, `B1_9_POLE_DID_RUNPOD_COMMANDS.md`.
- **Readiness:** `B1_9_POLE_DID_DRIVER_READY_MOCK_TESTED`.
- **Primary statistic:** `DiD = (OWN_CORRECT − OWN_FLIPPED) − (CONTROL_CORRECT − CONTROL_FLIPPED)`.
- **Expected outputs / ratings:** 192 / 576.
- **Varṇa source:** canonical Stage A′ + bridge (reproduces the 12); consonant-only (vowels dropped — §5b).
- **Real run gated on `classification_approved: true`** (currently false — DRAFT).
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.9 pole diff-in-diff preregistered and driver mock-tested. Canonical consonant-only varṇas; vowel omission
recorded as a limitation; referent classification requires operator sign-off before any run. No generation. No
judging. No GENUTILITY terminal label. No B1.10. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
