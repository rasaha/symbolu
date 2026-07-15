# Varṇa Symbolic Resonance — B1.12 Instrument Refinement · PREREGISTRATION **V2**

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Design chosen: (A) Reliability fix only — single tightened Direct Bare-Word Resonance (DBR) axis.**
**Status: READY_TO_FREEZE — pending (i) confirmation of the §1.4 opposition convention, then a content-hash
freeze; NO words selected; NOTHING run.**

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
**DBR question, per occurrence:** *Is the mapping inherent in, characteristic of, or strongly implied by the
ordinary, unqualified dictionary meaning of the bare word itself — without inventing a story?*

Scale (integers only), each anchored with ≥1 worked exemplar in the frozen prompt:
- **100** — the mapping is inherent in / directly characteristic of the ordinary meaning.
- **75** — strongly implied by the ordinary meaning; little interpretive work.
- **50** — a natural but nonessential association most evaluators would recognize **without constructing a story**.
- **25** — reachable **only** through metaphor, an external actor, contextual supplementation, or a special
  scenario. **Hard rule: if the adjudication says the link "requires interpretation / external context /
  inversion / a special case," the score is 25, not 50.**
- **0** — no defensible relationship without importing outside meaning.

### 1.3 No-supplementation firewall enforced *at scoring* (fixes Cause 3)
Explicit scorer instruction, frozen verbatim in the prompt:
> "If accounting for the mapping required inventing a causal or narrative chain that is not part of the bare word's
> ordinary meaning, score 0 — no matter how plausible the chain is. If your own opposing evidence names an invented
> bridge, the score may not exceed 25."

### 1.4 Opposition / resolution convention — **RESOLVED** (fixes Cause 2)
On a *direct bare-word resonance* axis, an `opposition` relationship means the bare word is the **antonym/negation**
of the mapping — i.e. the mapping is **not** inherent in the word's ordinary meaning; the word means the opposite.
A `resolution` relationship means the word is the *resolved/ceased* state of the mapping, likewise not the mapping
itself. Therefore, on DBR:

- **`opposition` and `resolution` components are scored ≤ 25** (the mapping is definitionally not inherent in the
  ordinary meaning), and are **tagged `oppositional_structural`**.
- They are **included** in the DBR mean (so an all-oppositional word correctly reads as low *direct* resonance) but
  are **reported in a separate table** so a reader sees the word relates by negation, not by direct resonance.
  Oppositional components are **never** presented as resonance "successes."

Rationale and honest consequence: this *lowers* opposition-heavy words (e.g. love↔hatred), which is the correct DBR
reading — love does not *contain* hatred, it opposes it. Capturing oppositional/structural resonance as a positive
phenomenon would require a separate axis (the EPR axis explicitly deferred, §2). Both models receive the identical
rule, which removes the v1 opposition gap at the definition level.

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
- **DBR word mean** = mean of per-occurrence `dbr_score` (oppositional_structural components included but capped per
  §1.4). **min** = min across occurrences.
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
- Do **not** present oppositional_structural components as resonance successes.
- Do **not** modify the frozen mappings, parser, v1 prereg, or the v1 verdict/role freeze.

## 6. Readiness / gate sequence
`READY_TO_FREEZE`. In order: **(1)** confirm the §1.4 opposition convention (recommended as written); **(2)** freeze
this file (record its SHA-256 in a freeze note); **(3)** precommit a new fresh word list under it; **(4)** only then
build/execute the V2 runner. No word has been selected and no model has been called for V2.

## 7. Provenance
Motivated by `results/b1_12_symbolic_resonance_multillm_v1/` (v1 run) and `B1_12_BSR_DISAGREEMENT_AUDIT.md`.
Design (A) selected by the maintainer. No frozen input, controlling preregistration, freeze, or prior artifact was
modified by writing this file.
