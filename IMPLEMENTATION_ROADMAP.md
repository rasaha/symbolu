# IMPLEMENTATION_ROADMAP

> **STATUS — canonical research execution plan.** This document describes **how research
> should proceed**, not what the theory is. It is **documentation only**. It does not modify
> Stage A, introduces no code, and weakens no scientific caveat.
> **Candidate hypothesis · Not validated · Stage A untouched · No Sanskrit privilege ·
> No semantic claims · Glossary-independent inputs required · Preserve ⊥.**

Architecture under execution (defined elsewhere, unchanged here):
- **L1 — Structural Operator Layer** (frozen): `t_i = M_{σ_i} t_{i−1}`.
- **L2 — Latent Semantic Formation** (candidate): `z = F(M_{σ_1},…,M_{σ_n}, s₀) ∈ S`.
- **L3 — Semantic Decoders** (DBP, transformation, polarity, …): `y = D(z) ∈ Y`.
- **Validation Layer**: probe `P`, baseline set `B`, failure state `⊥`.

The single question this roadmap answers:

> **In what order should hypotheses be tested so the project can fail as early and as cheaply
> as possible?**

---

## Research Principles

These are governance rules, not engineering tasks.

- **Data is the binding constraint, not code.** The critical path is set by data we do not yet
  have (a gloss-independent essence table; human order-effect measurements), not by software.
- **Cheapest falsifier first.** Sequence work so the least expensive decisive test runs first.
- **Validation precedes representation.** Build the probe/baseline/⊥ instruments *before* any
  representation model `F`.
- **Representation follows evidence, not intuition.** No representational layer
  (`F`, DBP, transformation fields, polarity, …) is implemented until the previous gate shows
  **measurable information gain**.
- **Every layer must beat the complete baseline suite** — bag-of-varṇas, relabel/random,
  phonological similarity, length/frequency, sentiment/lexicon — *especially phonological
  similarity*.
- **Preserve the failure state `⊥`.** When nothing beats the baselines, or the state is
  unstable/undefined, the system returns `⊥`; it never forces a reading.
- **Stage A remains frozen.** All new work lives outside `symbolu_neural/structural_v1/` and
  changes no gate, threshold, operator, or test.
- **Every hypothesis is replaceable except validated measurements.** `F`, decoders, and fields
  are disposable; a recorded measurement against frozen baselines is the durable asset.
- **Complexity must be earned by predictive gain.** A new layer is admitted only if it beats
  the simpler version on the metric, not because it is elegant or intuitive.

> **Every new representational layer must demonstrate measurable information gain before
> additional theoretical complexity is introduced.**

> **A negative result is a successful scientific outcome.** Terminating early on a clean null
> is the roadmap working as designed, not a failure of it.

---

## Milestones

Research milestones, not software phases. Each lists its goal, what is (and is not) built, and
its **gate** — including whether the gate can **terminate the entire project**.

### Milestone A — Foundations
**Goal:** freeze everything that defines a *fair* experiment. **No implementation.**
Deliverables (all frozen, pre-registered, gloss-independent):
- glossary of terms;
- codomain `Y` (what "meaning" is: semantic-field categories / VAD norms / embeddings),
  externally sourced;
- **gloss-independent essence table `E`** with a provenance specification;
- anti-circularity rules (no input derived from the glosses it will predict);
- probe protocol (the probe class `P`);
- baseline definitions (the full suite `B`);
- preregistration (hypotheses, metrics, thresholds fixed before data);
- evaluation metrics (`I(z;E)`, `I(z;meaning|phonology)`, baseline-exceedance rule).

**Gate (TERMINAL):** if `E` cannot be defined **independently of dictionary meaning**, the
program cannot be tested non-circularly — **terminate.**

### Milestone B — Atomic Validation
**Goal:** build the **Validation Layer only** and run the cheapest kill test.
**Implement:** probe `P`; baseline suite `B`; failure state `⊥`; the evaluation harness.
**Do NOT implement `F`.** Run only **atomic** tests (does `E` predict `Y` at the *unit* level?).

**Gate (TERMINAL):** if atomic semantic signal does **not** beat phonology, chance, and **all**
baselines → **return `⊥`** and **terminate research.** This is **intentionally the cheapest
kill test**: it can end the program for the price of one harness module, before any
representation is built. (Prior evidence at this level is negative; an early stop here is the
expected and economically optimal outcome.)

### Milestone C — Replication
**Goal:** repeat Milestone B on an **independent dataset**.
**Reason:** avoid building an architecture on a statistical accident; a single dataset's signal
is not yet a finding.

**Gate (TERMINAL):** the atomic signal must **replicate** on independent data. Otherwise
**terminate.**

### Milestone D — Structural Validation
**Only after B and C survive.**
**Goal:** validate the L1 operators non-circularly.
**Do:** human order-effect study; estimate operators from behavior; run the frozen Stage A
**G1–G4** gate on the *data-estimated* operators. **No semantic decoder work.**

**Gate (TERMINAL):** operators must validate **structurally**. If data-estimated operators show
no structure, `z = F(operators)` has no substrate — **terminate.**

### Milestone E — Latent Representation
**Only now define one admissible `F`.**
**Requirements on `F`:** gloss-independent, operator-derived, non-additive.
**Measure (with probe `P` against `B`):** `I(z;E)` and `I(z;meaning|phonology)`; must beat
**every** baseline, especially phonological similarity.

**Gate:** if `z` does not beat the baselines → **return `⊥`** and **reject `F`** (try another
admissible member, or, if the family is exhausted against the gate, the L2 hypothesis fails).

### Milestone F — Semantic Decoders
**Only after `z` demonstrates recoverable information.**
**Implement:** DBP, transformation, polarity, and future decoders as `y = D(z)`.
**Emphasis — Probe ≠ Decoder:** a **probe success does not validate a production decoder**
(probes can extract information a decoder does not use); a decoder failure does not by itself
prove `I(z;·)=0`.
**Do:** nested comparisons `position ⊂ trajectory ⊂ diffusion ⊂ transformation`; each level
admitted only if it beats the simpler one and the baselines.

**Gate:** a decoder must produce `y` beating baselines without circularity; otherwise that
decoder is rejected (L2 may still stand — decoders are replaceable).

### Milestone G — Comparative Research
**Only if everything else survives. Explicitly the most expensive and least urgent milestone.**
**Examples:** Sanskrit vs IPA vs random partitions; cross-language; cross-modal; ontological
comparisons. Each requires its own additional data and pre-registration. None is attempted
before A–F clear their gates.

---

## Critical Path

```
Milestone A — Foundations
        ↓        (TERMINAL gate: E must be gloss-independent)
Milestone B — Atomic Validation
        ↓        (TERMINAL gate: beat phonology/chance/baselines, else ⊥)
Milestone C — Replication
        ↓        (TERMINAL gate: signal must replicate)
Milestone D — Structural Validation
        ↓        (TERMINAL gate: operators validate G1–G4)
Milestone E — Latent Representation
        ↓        (gate: z beats baselines, else reject F / ⊥)
Milestone F — Semantic Decoders
        ↓        (gate: a decoder beats baselines non-circularly)
Milestone G — Comparative Research
```

**Project-terminating milestones:** **A, B, C, D** can each end the entire program. **E** can
end the L2 hypothesis (and, if the admissible family is exhausted, the semantic program). **F**
rejects individual decoders without necessarily ending L2. **G** never gates the core program.
The termination mass is deliberately concentrated **early and cheap**.

---

## Cost vs Information table (qualitative)

| Milestone | Cost | Information Gain | Kill Probability |
|---|---|---|---|
| A — Foundations | Low | Medium (defines a fair test) | Low–Medium |
| B — Atomic Validation | Low | **High** (cheapest decisive test) | **High** |
| C — Replication | Low–Medium | High (rules out accident) | Medium |
| D — Structural Validation | **High** (human data) | High | Medium |
| E — Latent Representation | Medium | High | Medium–High |
| F — Semantic Decoders | Medium | Medium | Medium |
| G — Comparative Research | **High** | Low–Medium (refinement) | Low |

**Why early validation is economically optimal.** The highest kill probability sits at the
**lowest-cost** milestones (A–C). Spending the cheap budget first means the expensive,
data-bound work (D) and all representation building (E–F) are only ever funded *after* the
near-free tests have failed to kill the idea. Most of the program's risk is retired before most
of its cost is incurred.

---

## Relationship to existing documents

This roadmap **does not replace**:
- `SYMBOL_U_THEORY_V1_FREEZE.md`
- `SYMBOL_U_IMPLEMENTABLE_ARCHITECTURE_V1.md`
- `LATENT_SEMANTIC_FORMATION_HYPOTHESIS.md`

Instead it specifies **how research proceeds through them**: the theory freeze and architecture
define *what* is claimed and *how it is structured*; this document defines *in what order, and
under what gates,* those claims are tested.

---

## Standing constraints (do not weaken)

Candidate hypothesis · Not validated · Not implemented beyond the validation harness when
authorized · Stage A untouched · No Sanskrit/varṇa privilege · No semantic claims · No
implementation assumptions · Inputs glossary-independent · `⊥` preserved · Structure frozen,
semantics hypothetical.

> **structure, not validated meaning.**
