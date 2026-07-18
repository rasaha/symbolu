# Design Memo — Revised Layer Architecture (5 Layers)

**Proposal only. Docs — no code, no implementation, no model, no generation, no experiment, no scoring, no result.** Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); prior PSE negatives valid; Track B **BLOCKED**; no ontology, no Sanskrit privilege, no semantic-truth claim; no model call.

This revision splits the old Layer 3 into a **dictionary-meaning bridge (L3)** and a **synonym-attribute check (L4)**, with generation conditioning as **L5**.

## Roles of the three information sets (fixed vocabulary)
- **Anchor** = the word's **core dictionary meaning** (L3's reference point).
- **Expansion set** = **synonyms / near-synonyms → attribute inventory** (L4's checklist).
- **Evidence set** = the **Layer 1/2 emitted glosses** (what the resonance actually produced).

No layer ever says "therefore the word means X." L3/L4 outputs **may guide generation** but do **not** validate meaning.

## 1. Why the split is cleaner than the old Layer 3
The old Layer 3 fused two different operations — "relate the process to the dictionary" **and** "check synonym attributes." Splitting them:
- makes the **anchor vs expansion** distinction explicit (§5), so neither is silently used as the other;
- quarantines the **dictionary-only baseline (D)** in L3, where its answer-key / dominance problem belongs;
- lets L4 be a **pure attribution check** over the evidence set without the anchor leaking in;
- keeps each layer's **allowed/forbidden** rules local and auditable.

## 2–3. Definitions + input/output
| Layer | Definition | Input | Output |
|---|---|---|---|
| **L1 — resonance extraction** | word → G2P/varṇa → **frozen pole/process emission** | word (true G2P) | ordered varṇa units + roles (onset-seed / field / transformer / internal-unresolved) + frozen glosses; `MISSING` / `~approx` marks |
| **L2 — latent-process synthesis** | frozen poles → **controlled process sentence** (fixed templates + frozen bridge vocab) | L1 glosses | one deterministic process paraphrase; `[unresolved]` where unbridged |
| **L3 — dictionary-meaning bridge** | *interpretively* relate L2 to the word's **core dictionary meaning (anchor)** | L2 synthesis + frozen dictionary anchor | a cautious relation note: `aligns / partially-aligns / diverges / unresolved` — **interpretive, not scored** |
| **L4 — synonym-attribute check** | synonyms → attribute inventory; check each attribute against the **evidence set** | L1/L2 glosses + frozen synonym-attribute inventory + frozen attribute→gloss bridge | per attribute: `SUPPORTED / UNSUPPORTED / UNRESOLVED` + evidence path |
| **L5 — generation conditioning** | use L2–L4 as a **soft conditioning field** for generation | L2 (+optionally L3/L4) + user task | a **conditioning prompt** (arms A/R/S/C/X/D), format-matched — **prompt construction only unless separately evaluated** |

## 4. Example — `mercy` (from the committed harness; g2p ok)
**L1 (evidence set):** seed `ma`=*Praśraya/Praṇāśa (indulgence/annihilating collapse)*; fields `a`=*Birth of cognition*, `ii`=*Specialization of self*; transformer `sa`=*Mokṣa/Sattvaguṇa (liberation/clarity)* (all ~approx).
**L2:** `[unresolved] moves toward [unresolved], and [unresolved] is the resolving principle` (ma/sa poles not in the frozen bridge table — harness did not invent).
**L3 — `LAYER3_DICTIONARY_BRIDGE — interpretive only, not scored, not evidence`:** anchor = "compassion or forbearance shown toward another." Relation: **unresolved/diverges** — L2 is `[unresolved]`, so it neither aligns nor conflicts with the anchor. Cautious language only; no "therefore mercy means…".
**L4 — `LAYER4_SYNONYM_ATTRIBUTE_CHECK — not scored, not evidence`:** inventory (illustrative) = {compassion, kindness, forgiveness, relief/release, clemency, leniency}.
- `relief/release` → **SUPPORTED** — path `relief ← bridge[Mokṣa/Sattvaguṇa] ← sa.transformer` (**but** a final-/s/ Barnum artifact — every /s/-final word supports it).
- `compassion`, `kindness` → **UNSUPPORTED** (bridge[Karuṇā/Sneha] exists; not emitted by mercy).
- `forgiveness`, `clemency`, `leniency` → **UNRESOLVED** (no frozen bridge rule).
**L5 — `LAYER5_GENERATION_CONDITIONING — prompt construction only unless separately evaluated`:** arm A conditioning would read "…can be read as: `[unresolved] moves toward [unresolved]…`; use as a soft guide" — i.e., **empty for mercy**, while R (random) reads fluently and D (dictionary anchor) is the strongest baseline. Prompt only; no generation.

## 5. Dictionary meaning vs synonym attributes
- **Dictionary meaning (anchor, L3):** a *single, authoritative* core sense. It is the **reference the process is compared against** — and, as a conditioning arm (D), the **answer key / strongest baseline**, so it must be quarantined, never used as evidence *for* the resonance.
- **Synonym attributes (expansion, L4):** a *set of derived properties* from near-synonyms. They form a **checklist** the evidence set is tested against — broader, noisier, and still **dictionary-derived**, so L4's "correct" set is an answer key in disguise (see §9).

## 6. Layer 3 — allowed / forbidden
**Allowed:** cautiously *relate* L2 to the anchor with `aligns / partially-aligns / diverges / unresolved`; use "can be read as", "may relate to", "does not obviously relate to". Anchor is a **frozen** dictionary sense, committed first.
**Forbidden:** "therefore the word means X"; using L3 as **evidence**; runtime dictionary lookup (anchor pre-frozen); editing the anchor after seeing L2; **scoring L3** (interpretive only); asserting ontology / Sanskrit privilege / semantic truth.

## 7. Layer 4 — allowed / forbidden
**Allowed:** mark each attribute `SUPPORTED` (bridge rule exists **and** required gloss in the evidence set, with an evidence path), `UNSUPPORTED` (rule exists, gloss not emitted), `UNRESOLVED` (no rule, or varṇa `[unresolved]`); preserve `[unresolved]`.
**Forbidden:** adding attributes **not traceable** to an emitted gloss; **target-fitting** the attribute→gloss bridge after seeing outputs; using synonym meaning to **modify L2**; runtime dictionary lookup (inventory + bridge pre-frozen, authored blind); "therefore means X"; treating `SUPPORTED` as evidence (set-membership over a high-DOF frozen table — a scrambled lexicon supports a different set equally).

## 8. How Layer 5 uses the outputs for generation conditioning
L5 injects L2 (and optionally L4's supported-attribute set / L3's relation note) into a **format-matched conditioning slot** (the committed `generation_conditioning_prompt_demo.py` wrapper), producing arms **A** (real resonance) · **R** random · **S** scrambled · **C** surface-only · **X** neutral · **D** dictionary-anchor. Only the slot content differs; no arm claims the resonance is true; the output is a **prompt**, never generated text, **unless a separate evaluation is approved**. L3/L4 are optional conditioning enrichers, not truth claims.

## 9. What is needed before any scoring or model evaluation
- **Freeze first, blind:** dictionary anchors (L3), synonym-attribute inventories (L4, independent thesaurus), attribute→gloss bridge (L4, authored from gloss meanings — **not** from which words emit which glosses), L2 templates, seeds, decision rule. Post-hoc edits → `INVALID_POSTHOC`.
- **Coverage first (docs-only, blind):** the current L2 bridge table resolves A for only ~1 of 4 sample words; a fair eval needs a **coverage-complete, blind-authored** bridge — **no bridge/inventory tuning on observed outputs**.
- **Full control stack + blinding:** all arms **A/R/S/C/X/D** through equivalent L1→L5 paths; scorer blinded to word / arm / meaning / answer-key; co-primary comparisons predeclared; null + surface-parity + relabeling-invariance checks; human-review subset.
- **Future model evaluation requires separate explicit approval and full controls A/R/S/C/X/D.**

## Required caveats (carried forward)
- **D / dictionary anchor is close to the answer key** → `A_vs_D` is near-unbeatable.
- **R / random can be fluent and evocative** (any-injection confound).
- **S / scrambled may match A** (and both collapse to `[unresolved]` together when unbridged).
- **A is currently often unresolved** because bridge coverage is incomplete (A resolves for ~1 of 4 sample words).
- **Track F prior remains `CORRECTNESS_DEGRADED`.** Prior PSE negatives remain valid. Track G negative remains valid. **Track B remains BLOCKED.**
- Null prior throughout. The split improves **clarity and auditability**; it does **not** change the evidential prior, which remains negative/inconclusive.

## 10. Recommendation
**DOCS_ONLY first.** Adopt the 5-layer split as **documentation/architecture** with the three required labels. Keep L3 and L4 as **interpretive/inspection layers only** (never scored), and L5 as **prompt construction only**. Do **not** implement scoring, do **not** run a model, and do **not** tune the bridge/inventory tables on observed outputs. If the line proceeds, the next step is a **docs-only, blind-authored coverage + freeze plan** (not an eval); only after that a separate, explicitly-approved `FUTURE_EVAL_PREREG_ONLY` with a null prior.

---

Guardrails: no ontology, no Sanskrit privilege, no semantic-truth claim, no Track B unblock, no rescue of Track G; prior PSE negatives valid; Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`).

Structure, not validated meaning.
