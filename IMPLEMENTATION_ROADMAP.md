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

### Milestone A′ — Existing-Data Upper Bound (desk study, cheapest falsifier)
**Runs before any harness is built.** This is the cheapest decisive test in the program and is
sequenced ahead of Milestone B.
**Goal:** estimate, from **existing public datasets only**, whether externally-measured
sound-symbolism norms carry **any conditional mutual information with semantic observables
beyond phonology** — i.e. an upper bound on `I(Y; E | phonology)` achievable in principle.
**Do:** desk computation on already-published norm sets and semantic/`Y` resources; **no new
data collection, no harness, no sourced `E` required.** Pre-register the `⊥` threshold before
looking at the data.
**Why first:** it is cheaper than Milestone B (no harness module, no `Y` collection, no
power-calibrated probe), and it doubles as the Milestone A path-(3) source search. It can end
the program before any implementation.

**Gate (TERMINAL):** if the estimated conditional MI is **approximately zero** (within the
pre-registered band) → the program may **terminate before implementation**. A non-zero upper
bound does **not** validate anything; it only licenses proceeding to a built test.

### Milestone B — Atomic and Order Validation
**Goal:** build the **Validation Layer only** and run the cheapest *built* kill test, split into
its two logically distinct components.
**Implement:** probe `P`; baseline suite `B`; failure state `⊥`; the evaluation harness.
**Do NOT implement `F`.**

**B.0 — Synthetic harness calibration (prerequisite, before any real run).** Before the harness
is pointed at real data it must be validated on synthetic data with known ground truth:
- **planted-signal** synthetic data **must be detected** (adequate power);
- **null** synthetic data **must return `⊥`** (no false reading);
- the **false-positive rate must be estimated**;
- the **minimum detectable effect must be recorded**.
Without B.0, a real-world `⊥` is **uninterpretable** (it cannot be distinguished from a probe
too weak or an `N` too small) and a real-world positive is **unverified** (false-positive rate
unknown). B.0 gates every subsequent real-data interpretation.

**B.1 — Atomic / additive test.** Does `E`, under the pre-registered additive aggregation,
predict `Y` at the *unit* level beyond phonology, chance, and **all** baselines?

**B.2 — Order-dependent interaction test.** A **minimal order-effect existence test** (pulled
forward from the structural branch): is there any **order-dependent / non-additive** signal —
i.e. does varṇa order change the predicted observable beyond the additive aggregate? This is
the cheap existence check, not the full operator estimation (that remains Milestone D).

**Gate (NOT a logical falsification of L2 — read carefully).** L2's distinctive claim is
**non-additivity**; therefore an **atomic (B.1) null does not logically falsify L2.** It
falsifies only the **additive / atomic-substrate branch** (the S1/S2/Level-B claim). A
pure-emergence theory predicts exactly an atomic null with surviving order signal. The four
pre-registered outcomes:

| B.1 atomic | B.2 order | Decision |
|---|---|---|
| null | null | **Terminate.** No signal anywhere beyond phonology/baselines. |
| null | positive | **Do not terminate.** Continue to the operator/order branch (Milestone D). The additive branch is dead; the emergent branch is live. |
| positive | null | Proceed with the **additive/essence branch only**; do **not** pursue the operator-interaction branch on this evidence. |
| positive | positive | **Strongest continuation.** |

**On terminating after an atomic-only null (B.1 null, B.2 also null is the terminate case above;
B.1 null with B.2 positive is *not*).** If a program chooses to stop after an atomic failure
*without* running or while ignoring B.2, that is a **resource decision** — an allocation choice
given negative priors — **not a logical proof that L2 is false.** The roadmap must not describe
an atomic null as full L2 falsification. (Prior evidence at the atomic level is negative; a
resource-driven early stop there remains economically defensible, but it is labelled as such.)

### Milestone C — Replication
**Goal:** repeat Milestone B on an **independent dataset**.
**Reason:** avoid building an architecture on a statistical accident; a single dataset's signal
is not yet a finding.

**Gate (TERMINAL):** whichever signal survived Milestone B (atomic and/or order) must
**replicate** on independent data. Otherwise **terminate.**

### Milestone D₀ — Gauge / Identifiability Analysis (specification, before any operator estimation)
**Must be written and frozen before Milestone D estimates anything.** "Validate the operators"
is **ill-posed** until this exists: the operators `{Mσ}` (with `s₀`, `{uᵢ}`) are defined only up
to a **gauge** (a similarity transform `Mσ ↦ P Mσ P⁻¹`, `s₀ ↦ P s₀`, `uᵢ ↦ P⁻ᵀ uᵢ`) that leaves
every observable invariant. Deliverables (design only, no code):
- **define the gauge equivalence** class of `(d, s₀, {Mσ}, {uᵢ})`;
- **define the gauge-invariant quantities** that a validation may legitimately test (only these
  are meaningful — anything gauge-dependent is an artifact of coordinates);
- **specify identifiability conditions** (e.g. Hankel-rank / Fliess–Schützenberger conditions;
  how many distinct sequences are needed to identify `n·d²` parameters at the committed `d`);
- **reconcile the two routes to the operators** — the `E`-derived operators (from the essence
  table) versus the behavior-estimated operators (Milestone D) — stating whether they are
  required to match, and how the comparison is made, so Milestone D tests *Symbol-U's* operators
  rather than generic linguistic order effects.

**Gate (TERMINAL):** if no gauge-invariant, identifiable quantity can be defined, operator
validation has no well-posed target — **terminate** (the structural claim is untestable as
specified).

### Milestone D — Structural Validation
**Only after B, C, and D₀ survive.**
**Goal:** validate the L1 operators non-circularly, **against the gauge-invariant, identifiable
quantities fixed in D₀** and against a **generic-composition baseline** (so a pass reflects
Symbol-U's specific assignment, not the trivial fact that language has order effects).
**Do:** human order-effect study; estimate operators from behavior; run the frozen Stage A
**G1–G4** gate on the *data-estimated* operators, applying the phonology baseline to behavioral
effects too. **No semantic decoder work.** (Note: G4/factorization is already **NOT VALIDATED**
on the cleaner Stage A operators; treat a G4 pass on noisier behavior-estimated operators as
unlikely and do not assume it.)

**Gate (TERMINAL):** operators must validate **structurally on the D₀ quantities, beyond the
generic-composition baseline**. If data-estimated operators show no such structure,
`z = F(operators)` has no substrate — **terminate.**

### Milestone E — Latent Representation
**Pre-register a finite `F`-ladder before implementing anything.** To keep L2 falsifiable, the
admissible `F` family must be enumerated **in advance** as a **finite, pre-registered ladder**
of candidate functionals (e.g. ordered by complexity), with a **stopping rule** fixed before
data:
- list the **finite set** of admissible `F` candidates to be tried (and in what order);
- fix **how many candidate failures terminate the `F`-family** (a counter `K_F`), so that
  "try another `F`" cannot drift indefinitely;
- declare that exhausting the pre-registered ladder against the gate **rejects the L2
  hypothesis** — not merely "the family was not big enough".

**Requirements on each `F`:** gloss-independent, operator-derived, non-additive.
**Measure (with probe `P` against `B`):** `I(z;E)` and `I(z;meaning|phonology)`; must beat
**every** baseline, especially phonological similarity.

**Gate:** if a candidate `z` does not beat the baselines → **return `⊥`** and **reject that
`F`**, advancing the ladder counter. When the pre-registered ladder is exhausted (counter
reaches `K_F`) → **the L2 hypothesis fails** and the semantic program terminates. No `F` outside
the pre-registered ladder is admitted without a logged amendment made *before* its result is
seen.

### Milestone F — Semantic Decoders
**Only after `z` demonstrates recoverable information.**
**Pre-register a decoder stopping rule before implementing anything.**
**Implement:** DBP, transformation, polarity, and future decoders as `y = D(z)`.
**Emphasis — Probe ≠ Decoder:** a **probe success does not validate a production decoder**
(probes can extract information a decoder does not use); a decoder failure does not by itself
prove `I(z;·)=0`.
**Do:** nested comparisons `position ⊂ trajectory ⊂ diffusion ⊂ transformation`; each level
admitted only if it beats the simpler one and the baselines.

**Stopping rule (so probe≠decoder does not become an unfalsifiability shield):**
- a **single** decoder failing terminates **only that decoder branch** — L2 may still stand,
  because decoders are replaceable and a probe already evidenced recoverable information;
- but **repeated** decoder failures are bounded: pre-register a finite decoder set and a
  counter `K_D`; if **every** pre-registered decoder fails to beat baselines non-circularly
  **while the probe `P` continues to show `I(z;·)>0`**, that divergence is itself reported as an
  anomaly, and exhausting `K_D` **downgrades the practical status of L2** (recoverable in
  principle, not decodable in practice) rather than being absorbed silently;
- the asymmetry "decoder failure ≠ `I(z;·)=0`" may be invoked **at most `K_D` times**; it is a
  bounded allowance, **not** an open-ended escape from negative results.

**Gate:** a decoder must produce `y` beating baselines without circularity; otherwise that
decoder is rejected. Exhaustion of the pre-registered decoder set (`K_D`) ends the decoder
program even though the L2 representation result stands on the probe evidence.

### Milestone G — Comparative Research
**Only if everything else survives. Explicitly the most expensive and least urgent milestone.**
**Examples:** Sanskrit vs IPA vs random partitions; cross-language; cross-modal; ontological
comparisons. Each requires its own additional data and pre-registration. None is attempted
before A–F clear their gates.

---

## Critical Path

```
Milestone A  — Foundations
        ↓        (TERMINAL gate: E must be gloss-independent)
Milestone A′ — Existing-Data Upper Bound (desk; no harness)
        ↓        (TERMINAL gate: if conditional MI ≈ 0 → terminate before implementation)
Milestone B  — Atomic and Order Validation
        │  B.0 calibrate harness (planted→detect, null→⊥, FPR, min detectable effect)
        │  B.1 atomic/additive test     B.2 order-dependent test
        ↓        (atomic null is NOT logical L2 falsification — see 4-outcome table;
                  terminate only if BOTH null, else branch accordingly)
Milestone C  — Replication
        ↓        (TERMINAL gate: surviving signal must replicate)
Milestone D₀ — Gauge / Identifiability (specification only)
        ↓        (TERMINAL gate: a gauge-invariant identifiable target must exist)
Milestone D  — Structural Validation
        ↓        (TERMINAL gate: operators validate beyond generic-composition baseline)
Milestone E  — Latent Representation (pre-registered finite F-ladder + K_F)
        ↓        (gate: z beats baselines; ladder exhausted → L2 fails)
Milestone F  — Semantic Decoders (pre-registered decoder set + K_D)
        ↓        (gate: a decoder beats baselines non-circularly; K_D bounds the shield)
Milestone G  — Comparative Research
```

**Project-terminating milestones:** **A, A′, C, D₀, D** can each end the entire program. **B**
can terminate **only when both the atomic (B.1) and order (B.2) tests are null**; an atomic-only
null is **not** a logical L2 falsification (it kills the additive branch and may be a
resource-driven stop, explicitly labelled as such). **E** can end the L2 hypothesis when the
**pre-registered finite `F`-ladder is exhausted** (`K_F`). **F** rejects individual decoders and,
on exhausting the pre-registered set (`K_D`), ends the decoder program without necessarily ending
L2. **G** never gates the core program. The termination mass is deliberately concentrated **early
and cheap** — and the single cheapest terminal test is now **A′**, a desk study requiring no
harness.

---

## Cost vs Information table (qualitative)

| Milestone | Cost | Information Gain | Kill Probability |
|---|---|---|---|
| A — Foundations | Low | Medium (defines a fair test) | Low–Medium |
| A′ — Existing-Data Upper Bound | **Very Low** (desk only) | **High** (cheapest decisive test) | **High** |
| B — Atomic and Order Validation | Low | **High** | **High** (both-null branch) |
| C — Replication | Low–Medium | High (rules out accident) | Medium |
| D₀ — Gauge / Identifiability | Low (specification) | Medium (makes D well-posed) | Low–Medium |
| D — Structural Validation | **High** (human data) | High | Medium |
| E — Latent Representation | Medium | High | Medium–High |
| F — Semantic Decoders | Medium | Medium | Medium |
| G — Comparative Research | **High** | Low–Medium (refinement) | Low |

**Why early validation is economically optimal.** The highest kill probability sits at the
**lowest-cost** milestones (A′–C). The cheapest decisive test is now the **desk-level upper
bound (A′)**, which requires no harness, no `Y` collection, and no sourced `E`, and can end the
program before implementation. Spending the cheap budget first means the expensive, data-bound
work (D) and all representation building (E–F) are only ever funded *after* the near-free tests
have failed to kill the idea. Most of the program's risk is retired before most of its cost is
incurred.

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
