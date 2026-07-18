# B1.9 — Pole-Sensitivity Probe (Q2) — PREREGISTRATION

**Status:** preregistration + implemented, mock-tested driver. **No real generation. No judging. No
`GENUTILITY_*` terminal label.** Real run is **gated on operator sign-off of the referent classification.**

**Readiness label: `B1_9_POLE_SENSITIVITY_DRIVER_READY_MOCK_TESTED`.**

**B1.4b′ remains `NULL_RETURN_BOTTOM`.** No ontology, no Sanskrit privilege, no semantic-truth claim.

---

## 0. What this tests and why it's different

Prior B1.9 arms tested varṇa **content** (does a word's own varṇas beat another's?) — null. Those tests could not
speak to the operator's actual hypothesis, because:

- the **resolver-free** representation (`named_attribute`) is a **both-poles superposition** (e.g. `va` = "holding"
  *and* "dharma / sustaining flow") — a generic "order" with no determinate sense, so it cannot carry a
  word-specific meaning and its null is **predicted, not diagnostic**;
- the **resolved** arm used B1.8's **keyword-valence** resolver, which the operator rejects as wrong and which is
  internally inconsistent (it assigned bridge the *liberating* pole while assigning it the *physical/gross* plane).

**Q2 isolates the pole resolution itself.** The determinate meaning exists only *after* a pole is chosen. This
probe asks: **does choosing the pole by the referent-ontology rule produce a more target-appropriate reading than
the flipped pole — holding the word, varṇas, context and plane constant?** Pole is the ONLY variable. There is
**zero content confound** (identical varṇas on both sides).

## 1. The frozen pole rule (anti-circularity)

The **correct** pole per word is fixed by `frozen/b1_9_pole_referent_classification.json`, authored from the
**referent's ontology only** (NOT context valence):

- referent **physical / objectified** → **binding** pole (`worldly_binding_distortion`);
- referent **mental & objectified** → **binding**;
- referent **mental & subjectified** (lived first-person experience) → **liberating** (`spiritual_liberating_reading`).

Valence is deliberately **not** used: a negatively-valenced but subjectively-lived emotion (e.g. dread) maps to
the *liberating* pole under this rule. This is what distinguishes it from B1.8's keyword resolver.

**Mandatory pre-commitment:** the classification must be **operator-approved (`classification_approved: true`)
BEFORE any generation output is produced or seen.** No row may be revised after seeing any reading. The runner's
gate refuses the real run unless the flag is true. This prevents "pick the pole to fit, then confirm it fits."

## 2. Arms (4)

| arm | facets | role |
|---|---|---|
| **`POLE_CORRECT`** | W's varṇas at the frozen correct pole | authentic resolution |
| **`POLE_FLIPPED`** | W's varṇas at the OPPOSITE pole | the only contrast that matters |
| `PLAIN_PROMPT_BASELINE` | none | floor / coherence anchor |
| `SEMANTIC_LLM_BASELINE` | none | content ceiling |

`POLE_CORRECT` and `POLE_FLIPPED` share **everything** except the pole (same word, varṇas, context, plane).

## 3. Primary contrast

**`POLE_CORRECT` vs `POLE_FLIPPED`**, paired by item, blind-judged. Endpoints: penalty-adjusted composite
(primary) and `specificity_to_target` (secondary). The baselines are context only — a coherent reading beating an
incoherent one is *not* the claim; the claim is **correct pole > flipped pole** on target-aptness.

## 4. Interpretation rules (fixed in advance)

- **Null** (`POLE_CORRECT ≈ POLE_FLIPPED`, win-rate ≈ 0.5): the binding/liberating resolution carries **no**
  recoverable meaning — the first result that genuinely bears on the operator's hypothesis, and it would be a
  negative for it.
- **`POLE_CORRECT` > `POLE_FLIPPED`, robust:** a **candidate** signal that the pole resolution matters. Then, and
  only then, a **second-step confound check** is required before any claim: rule out that the correct pole simply
  produced a *more coherent* reading (compare both poles' coherence vs the flipped, and re-judge on aptness given
  equal coherence), and replicate with an independent referent-classifier. Still **no** ontology / truth claim.
- **`POLE_CORRECT` < `POLE_FLIPPED`:** the rule anti-predicts — a strong negative.
- **Under no outcome** emit `ONTOLOGICAL_SIGNAL` or `GENUTILITY_*`.

## 5. Models, blinding, judging

Generators Mistral-7B-Instruct-v0.3 (M1) + Qwen2.5-7B-Instruct (M2); judges Llama-3.1-8B, Meta-Llama-3-8B,
Gemma-2-9b (disjoint families). **Expected: 12 × 4 × 2 = 96 outputs; × 3 = 288 ratings.** Judges see only
`{item_id, target_text, neutral_context, blinded_output_id, generation_text, output_format}` — never the arm,
pole, generator, or classification. Blinding reuses the shared whole-word leak matcher; content words are not
filtered (both poles use the same varṇas → no differential attrition possible). Judging + aggregation reuse the
B1.6-v2 panel and `judge_b1_6_pilot_outputs.aggregate` unchanged.

## 6. Honest prior & scope

Prior remains **low** given B1.4b′ and the embedding/content nulls — but those did **not** test pole resolution,
so this is the first probe that can. A null here would be the cleanest negative yet for the pole-resolution
hypothesis; a positive would need the §4 confound checks before meaning anything. Exploratory, N=12; no terminal
verdict.

## 7. Guardrails

No real generation/judging in this commit. No `run_out/` committed. No `GENUTILITY_*`, ontology, or
semantic-truth claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`.** Structure, not validated meaning.

---

## Final report

- **Files:** `B1_9_POLE_SENSITIVITY_PREREG.md`, `run_b1_9_pole_sensitivity.py`,
  `test_run_b1_9_pole_sensitivity.py`, `build_b1_9_pole_scaffold.py`,
  `frozen/b1_9_pole_referent_classification.json` (DRAFT — needs sign-off), `frozen/b1_9_pole_scaffold.json`,
  `B1_9_POLE_SENSITIVITY_RUNPOD_COMMANDS.md`.
- **Readiness:** `B1_9_POLE_SENSITIVITY_DRIVER_READY_MOCK_TESTED`.
- **Primary contrast:** `POLE_CORRECT` vs `POLE_FLIPPED` (pole is the only variable).
- **Expected outputs / ratings:** 96 / 288.
- **Real run gated on `classification_approved: true`** (currently false — DRAFT).
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

B1.9 pole-sensitivity probe preregistered and driver mock-tested. Correct pole from a frozen referent-ontology
classification, operator sign-off required before any run. No generation. No judging. No GENUTILITY terminal
label. B1.4b′ remains NULL_RETURN_BOTTOM. Structure, not validated meaning.
