# Varṇa Symbolic Resonance — B1.12 Instrument Refinement · PREREGISTRATION **V2**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Design chosen: (A) Reliability fix only — one tightened Bare-Word Symbolic Resonance axis (labelled DBR, "Direct
Bare-Word Resonance"; "direct" = available from the bare word without supplementation, clarified in §1.4 — NOT
semantic containment).**
**Status: FROZEN (SHA-256 recorded in `B1_12_V2_PREREG_FREEZE.md`). NO words selected; NOTHING run; ready for a
fresh word-list precommitment.**

Supersedes the working draft `VARNA_SYMBOLIC_RESONANCE_PREREG_V2_DRAFT.md`. Does **not** modify anything frozen:
the v1 controlling prereg (`VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`), the v1 verdict/role freeze
(`B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md`), the frozen mappings (`frozen/varna_native_stage1_merged_v3.json`),
and the recorded v1 result (`SIGNIFICANT_ROLE_DEPENDENCE`) all stand. V2 is a **separate instrument** on a **new
fresh word set**; the v1 20-word run is retained as the V1 instrument result and comparison baseline.

---

## 0. Motivation (from the v1 disagreement audit)

`B1_12_BSR_DISAGREEMENT_AUDIT.md` traced v1's `SIGNIFICANT_ROLE_DEPENDENCE` to three structured, correctable
causes, plus a design flaw:

- **Cause 1** — a global scorer-strictness offset (~+10 pts Qwen over Mistral) that persists even when both models
  choose the identical relationship (a calibration difference).
- **Cause 2** — an unspecified score-scale convention for `opposition`/`resolution` (opposition: Mistral 40.9 vs
  Qwen 66.7 — a 25.8-pt gap).
- **Cause 3** — under-enforced no-supplementation control at scoring (invented bridges scored 50).
- **Design flaw** — the author→scorer crossover let the scorer react to a narrative the *other* model assembled,
  rather than judging the raw word + mapping independently (anchoring).

V2 targets each directly. **Its purpose is evaluator reliability; no threshold is loosened to make words "succeed."**

---

## 1. Design — single tightened DBR axis, fully independent judgments

### 1.1 Fully independent judgments (fixes the design flaw)
- Both models receive the **same** frozen bare-word definition, the **same** exact frozen mapping(s), and the
  **same** rubric.
- Each model **independently** produces, per occurrence: `supporting_evidence`, `opposing_evidence`,
  `relationship_type`, and `dbr_score` — **blind to the other model's output**. No model scores another model's
  narrative.
- Agreement is computed post hoc between two complete, independent judgments. (Determinism, seed, and the "no
  model-family substitution" gate are unchanged from v1.)

### 1.2 The DBR axis and its tightened scale (fixes Causes 1 & 3)
**DBR question, per occurrence:** *Does the stable, ordinary, unqualified bare word **directly and naturally
account for** the exact frozen mapping — through **any** preregistered relationship (embodiment, constitutive
property, characteristic expression, implication, natural consequence, generation, opposition, resolution,
regulation, or containment) — **without semantic supplementation** (no added actors, scenarios, metaphors,
exceptional subtypes, or narrative chains)?* This is the v1 Bare-Word Symbolic Resonance objective; it is **not** a
test of semantic containment, inclusion, or positive instantiation, and it does **not** privilege embodying
relationships over polarity-reversing ones.

Scale (integers only), each anchored with ≥1 worked exemplar in the frozen prompt. The anchors describe *how
strongly and directly the bare word accounts for the mapping*, independent of whether the accounting is by
embodiment, implication, opposition, resolution, regulation, or containment:
- **100** — directly and characteristically accounted for by the ordinary meaning.
- **75** — strongly and conventionally accounted for by the ordinary meaning; little interpretive work.
- **50** — a natural, broadly recognizable association that requires no constructed scenario.
- **25** — reachable **only** through metaphor, an external actor, contextual supplementation, an exceptional
  subtype, or a special scenario. **Hard rule: if the adjudication says the link "requires interpretation /
  external context / a special case / an invented bridge," the score is 25, not 50** — this rule keys on
  *supplementation*, never on polarity.
- **0** — no defensible relationship without importing outside meaning.

### 1.3 No-supplementation firewall enforced *at scoring* (fixes Cause 3)
Explicit scorer instruction, frozen verbatim in the prompt:
> "If accounting for the mapping required inventing a causal or narrative chain that is not part of the bare word's
> ordinary meaning, score 0 — no matter how plausible the chain is. If your own opposing evidence names an invented
> bridge, the score may not exceed 25."

### 1.4 Opposition / resolution convention — **RESOLVED** (fixes Cause 2)
Opposition and resolution are **legitimate** Bare-Word Symbolic Resonance relationships, on equal footing with
embodiment, constitutive property, characteristic expression, implication, natural consequence, generation,
regulation, and containment. A bare word can **directly and naturally account for** a mapping by opposing,
removing, resolving, regulating, neutralizing, or standing in a defining polarity to it, just as much as by
embodying or implying it. They are **not** capped, discounted, or treated as failures merely because they reverse
polarity.

**Convention (frozen):**
> Opposition and resolution may receive the full score range (0–100) when the ordinary bare word directly,
> conventionally, and story-free opposes, removes, resolves, regulates, neutralizes, or stands in a defining
> polarity to the exact frozen mapping.

The score depends **only** on:
- **directness** — the relationship is available from the ordinary bare word itself;
- **conventionality** — it is a broadly recognized, standard relationship, not idiosyncratic;
- **strength** of the relationship to the *exact* frozen mapping;
- **sufficiency** — whether the bare word alone is enough;
- **absence** of added actors, scenarios, metaphors, exceptional subtypes, or narrative chains.

The score does **not** depend on whether the relationship is positive, negative, embodying, or oppositional.

**"Direct" clarified.** "Direct" means the relationship is available from the ordinary bare word itself without
semantic supplementation. It does **not** mean the mapped state must be positively contained as a dictionary
feature. Antonymy is **not** evidence against resonance.

**Full-range opposition/resolution examples** (no external actor or invented scenario needed):
- `prema` / love ↔ hatred or revulsion — direct conventional opposition; **potentially 75–100** if the exact gloss
  is adequately covered by the ordinary bare word.
- `śānti` / peace ↔ agitation or unrest — direct opposition/resolution; **potentially 75–100**.
- `jñāna` / knowledge ↔ delusion or ignorance — direct opposition/resolution; **potentially 75–100**.

**Capped (≤ 25) opposition/resolution examples** — capped because they require semantic supplementation, exactly as
for any other relationship type, **not** because of polarity:
- boat ↔ despair only because a traveler *uses* a boat to escape despair (external actor + scenario);
- nose ↔ attachment only because scent *reminds* a person of the past (invented sensory-memory chain);
- lamp ↔ ignorance only through an added metaphorical story not inherent in the controlling ordinary meaning.

The ≤ 25 cap therefore attaches to **semantic supplementation**, never to polarity. Both models receive this
identical, polarity-neutral convention, which removes the v1 opposition ambiguity (Cause 2) by giving one explicit
shared scoring standard — without discounting a legitimate relationship type. The final relationship type is
recorded descriptively in the output (see §4); it is a label, not a score cap.

### 1.5 Keep everything that worked (unchanged from v1)
Frozen mappings; pronunciation-derived native Stage-1 decomposition; occurrence-level scoring; bidirectional
(supporting + opposing) evidence; the 10-type relationship taxonomy (with the relationship-token canonicalizer for
orthographic typos, logged); component-level anti-rescue (no holistic score may repair weak components); separate
reporting of weak components; deterministic decoding; the two hard gates (input-hash match; no model-family
substitution); glosses read **only** at scoring time, never during word selection.

### 1.6 New fresh word set (separate gate, not done here)
A **new** precommitted, attested-Sanskrit, category-balanced word list (FRESH_UNINSPECTED). The v1 20 words are
**not** reused (now inspected). Selection is a separate gate performed before any scoring, with glosses hidden
during selection.

---

## 2. Rejected for V2 — two-axis DBR/EPR scoring
The Experiential-Process (EPR) axis is **not** part of V2 (single-axis chosen). As documented in the draft, an
unbounded EPR axis re-admits the invented bridges v1 correctly penalized (nose→attachment, boat→destination) and
inflates resonance, since nearly every noun participates in *some* process. If revisited later it must carry the
"intrinsic and necessary process only" guard. Not in scope here.

## 3. Separate future study — hypothesis discrimination (out of scope for V2)
V2 does **not** attempt to separate *"varṇas encode transformations"* (H-transform) from the simpler *"abstract
words have richer semantic neighborhoods, so LLMs fit anything to them"* (H-neighborhood). Both predict
abstract > concrete; a single tightened DBR axis cannot distinguish them. That requires a discriminating control —
a shuffled/alternate-mapping baseline (does a word score high on the *wrong* mapping?) and/or matched
concrete-process vs concrete-static words — and is a separate, larger preregistration. Noted so it is not confused
with the reliability fix.

---

## 4. Aggregation & verdicts (reused from the v1 freeze for comparability)
- **DBR word mean** = mean of per-occurrence `dbr_score` across **all** mapped occurrences, regardless of
  relationship type — opposition and resolution are scored on the same full-range criteria as every other
  relationship (§1.4); no relationship type is capped by polarity. **min** = min across occurrences.
- **Relationship type is preserved descriptively** in every component's output (embodiment / constitutive_property /
  characteristic_expression / implication / natural_consequence / generation / opposition / resolution / regulation
  / containment) so the report can describe *how* each word accounts for its mapping. The tag is descriptive only
  and imposes no score cap.
- **Verdict bands (unchanged from `B1_12_BSR_VERDICT_AND_ROLE_STABILITY_FREEZE.md`):** STRONG (mean ≥ 75 & min ≥ 50),
  MODERATE (≥ 50), WEAK (≥ 30), MINIMAL (≥ 15), NO_RESONANCE (< 15).
- **Role/evaluator agreement** between the two independent judgments uses the same component/relationship/verdict
  agreement and the same role-dependence bands (ROLE_STABLE / MINOR / SIGNIFICANT / RUN_INVALID) as v1. Because V2
  is non-crossover, "role dependence" becomes **model-identity dependence** (Qwen vs Mistral as independent judge),
  a cleaner measure than v1's author/scorer-confounded version.
- **No forced consensus.** Both models' complete judgments are retained and reported.

## 5. What must NOT change / must NOT be done
- Do **not** rescore the v1 20 words or replace the v1 report; do **not** reuse the v1 word set.
- Do **not** lower any threshold to make more words pass.
- Do **not** admit mythological/etymological/cultural narrative into the ordinary-meaning constraint.
- Do **not** apply any polarity-based score cap. Opposition and resolution use the full 0–100 range; the ≤ 25 cap
  attaches **only** to semantic supplementation (added actors, scenarios, metaphors, exceptional subtypes, narrative
  chains), never to whether a relationship is positive or oppositional.
- Do **not** redefine the study as semantic containment, semantic inclusion, or positive instantiation, and do
  **not** treat antonymy as evidence against resonance.
- Do **not** let combined reconciliation repair a weak component (component-level anti-rescue stands).
- Do **not** modify the frozen mappings, parser, v1 prereg, or the v1 verdict/role freeze.

## 6. Readiness / gate sequence
`FROZEN`. Consistency checks passed (§1.4 corrected: opposition and resolution use the full 0–100 range; the ≤ 25
cap attaches only to semantic supplementation, never to polarity; no wording treats antonymy or polarity-reversal as
inherently weak). SHA-256 recorded in `B1_12_V2_PREREG_FREEZE.md`. **Next gate: precommit a new fresh word list**
under this frozen spec (a separate task; attested Sanskrit, category-balanced, FRESH_UNINSPECTED, glosses hidden
during selection), then build/execute the V2 runner. No word has been selected and no model has been called for V2.

## 7. Provenance
Motivated by `results/b1_12_symbolic_resonance_multillm_v1/` (v1 run) and `B1_12_BSR_DISAGREEMENT_AUDIT.md`.
Design (A) selected by the maintainer. No frozen input, controlling preregistration, freeze, or prior artifact was
modified by writing this file.
