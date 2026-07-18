# Clarity Memo — Layer 1 / Layer 2 / Layer 3 Mechanism

**Docs only — no code, no implementation, no model, no experiment, no scoring, no result.** Prior PSE negatives remain valid; Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B **BLOCKED**; no ontology, no Sanskrit privilege, no semantic-truth claim, no Track G rescue.

## Corrected conceptual model
- **Layer 1** — phoneme/G2P → varṇa → **frozen pole/process emission** (opaque glosses per unit; onset=binding, vowel=field, final=liberating transformer). *Built (`sample_text_rule_harness.py`).*
- **Layer 2** — frozen pole/process emission → **controlled latent-process synthesis** (fixed templates + frozen bridge vocabulary; a paraphrase of the poles, adding nothing). **Layer 2 is NOT a dictionary-meaning renderer.** *Built (optional `--synthesize`, off by default).*
- **Layer 3** — **Synonym-Attribute Attribution Check** — does the Layer 2 process **support** the word's synonym-derived attributes, traceably, and better than controls? **Not semantic proof; never "therefore the word means X."** *Not built; DOCS_ONLY (see `H2_LAYER3_ATTRIBUTION_CHECK.md`).*

Layer 2's job is to emit a *process*, not a *label*. Whether that process aligns with a word's attribute cluster is a **separate Layer 3 question**, meaningful only under controls.

## 1. Direct semantic recovery — rejected / not claimed
No layer claims "varṇa sequence → the word's dictionary meaning." That claim is falsified (Tracks C–G; PSE lexical `NO_SIGNAL`). Layer 2 outputting the input word's dictionary label is **not required and not expected**, and its absence is **not** evidence against Layer 3.

## 2. Layer 2 latent-process rendering — what the harness does
Given Layer 1 poles, Layer 2 substitutes each emitted gloss through a **frozen bridge phrase** via **fixed templates**, yielding e.g. for *love*: "separative harshness moves toward compassion/gentleness, and order/dharmic relation is the resolving principle." It is a **deterministic paraphrase** — identical for any word with the same poles, adds no content, never looks up the input word's meaning.

## 3. Layer 3 synonym-attribute attribution — the future proposed check
- **Input:** Layer 1 emitted glosses + Layer 2 synthesis + a **frozen synonym/attribute inventory** (independent thesaurus, blind to varṇa glosses) + a **frozen attribute→gloss bridge table** (blind to target words).
- **Output:** per attribute — `SUPPORTED` / `UNSUPPORTED` / `UNRESOLVED`, each `SUPPORTED` with an evidence path `attribute ← bridge_rule[gloss] ← varṇa.role`.
- **It is an attribution check, not a meaning assertion.**

## 4. Why Layer 2 sample outputs should not be judged as dictionary meanings
- *compassion* → Layer 2 "hope moves toward detachment/letting-go, and [unresolved] …" is **not a failure** — Layer 2 is not asked to say "compassion."
- The proper question is Layer 3: does that process support compassion-cluster attributes (care, tenderness, mercy, empathy, non-harm, concern-for-suffering) better than controls?
- So the earlier "compassion ≠ compassion" observation is **re-scoped**: it correctly shows **Layer 2 is not a direct dictionary renderer** (expected), and is **not** a verdict on the Layer 3 hypothesis.

## 5. What the current sample outputs do and do not show
- **Do show:** Layer 1/Layer 2 run deterministically, stay within frozen terms, mark `[unresolved]` / `INTERNAL_UNRESOLVED`, produce a latent process — discipline guards working.
- **Do NOT show:** any evidence for or against the Layer 3 hypothesis; any dictionary-meaning recovery; anything scored. `compassion` → non-"compassion" only confirms Layer 2 is not direct dictionary recovery.

## 6. Is Layer 3 still logically meaningful?
**Yes — logically coherent, with a null prior**, subject to two structural cautions (not a rescue of anything):
1. The correct attribute set is **derived from dictionary/thesaurus data**, so **D (dictionary-only) is structurally close to the answer key** — "A must beat D" is near-unbeatable. Layer 3's positive path is *harder* than prior tracks, not easier.
2. "Support" is set-membership over a **frozen, high-DOF, researcher-authored** attribute→gloss table, so a **scrambled** lexicon supports a different attribute set equally → `A ≈ S` is the expected outcome (the committed NO_SIGNAL pattern).

## 7. What must be frozen before any Layer 3 implementation
Synonym clusters + attribute inventories (independent thesaurus, blind); attribute→gloss bridge rules (blind to target words); Layer 2 fixed templates; the evidence-path validator (rejects any attribute not traceable to an emitted gloss; preserves `[unresolved]`); co-primary comparisons, target sets, seeds, decision rule. Post-hoc edits → `INVALID_POSTHOC`.

## Recommendation
**DOCS_ONLY first — no Layer 3 implementation yet.** If built at all, build Layer 3 initially as an **inspection-only attribution display** (`LAYER3_ATTRIBUTION_CHECK — not scored, not evidence`), never scored. Scoring stays a separate, explicitly-approved, pre-registered step with a **null prior**, framed as a rigor check — never a rescue. Honest expectation for a scored Layer 3: **NO_SIGNAL / NO_INCREMENTAL_UTILITY** (D-dominance + scramble-equivalence). The reframe fixed the *conceptual model*; it did not change the evidential prior.

---

Guardrails: prior PSE negatives remain valid; no ontology, no Sanskrit privilege, no semantic-truth claim, no Track B unblock, no rescue of Track G; Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`).

Structure, not validated meaning.
