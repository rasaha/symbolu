# SYMBOL_U_IMPLEMENTABLE_ARCHITECTURE_V1

> **Goal:** design (not build) the *smallest* system that could test whether the theory has
> useful **computational consequences** — reframed from "read meaning" (which failed in
> O1.5) to "**produce order-structure that beats bag / random / relabel offline.**"
> **Design-only.** Stage A is not to be implemented until explicitly authorized. Companion:
> `SYMBOL_U_THEORY_V1_FREEZE.md`.

## 1. Inputs

- text → unit (varṇa/phoneme) **sequence** (via existing decomposition);
- *optional* semantic anchor (a target vector — **validation only**, never an input to the
  reading);
- *optional* modality tags (future multi-view; v1 = single modality).

## 2. Latent state representation

- **Per-unit operator** `M_σ ∈ ℝ^{d×d}`, small `d` (e.g. 4–8). Initial entries from existing
  varṇa features — **flagged provisional / to-be-estimated**, never treated as ground truth.
- **Reading state** `s ∈ ℝ^d`.
- **CSR / contextual resonance:** a **placeholder slot, set to identity (off)** in v1. Not
  built.
- **Confidence / uncertainty:** a stability scalar (e.g. concentration of `s`, or variance
  under small input perturbation). Placeholder.

## 3. Composition engine (compare → select)

| option | role |
|---|---|
| additive (bag) | **mandatory baseline** |
| finite-state update `s_i=f(s_{i-1},σ_i)` | general (not v1) |
| **matrix / operator product** `s = M_{σₙ}…M_{σ₁}s₀` | **v1 choice** — order-sensitive, identifiable (Hankel/Fliess), computable emergence |
| CSR-enriched | **deferred** |

**Selected v1:** the **linear operator product**, run **alongside the additive bag** as the
control. Nothing more.

## 4. Outputs

- **semantic reading:** final state `s` + linear readouts — emitted as *structure*,
  **labeled "not validated as meaning."**
- **resonance profile:** placeholder (off).
- **uncertainty / confidence:** the stability scalar.
- **explanation trace:** intermediate states `s₀…sₙ` + operators applied — **reported in
  gauge-invariants only** (raw entries are gauge-dependent and not meaningful).
- **policy object:** **deferred** (not v1).

## 5. Evaluation hooks (offline, no LLM)

- **Primary (structural — the v1 focus):** order-sensitivity (permutation changes the
  reading); factorization (order-effect pattern decomposes into `k ≪ n` factors;
  disjoint-factor pairs commute); baseline comparison (operator product vs bag vs sentiment
  lexicon vs length); random / relabel controls.
- **Secondary (meaning — reported but NOT gating, since it needs human data):** paraphrase
  stability; minimal-pair sensitivity; human interpretability of the trace.

**The v1 pass criterion is structural** (beat bag + random + relabel on
order/factorization), **not** meaning.

## 6. LLM integration — deferred

**No LLM in v1.** LLM / policy use is admitted only *after* the reading passes the offline
structural gates **and** human order-effect data validates it. (The LLM layer was shown to
add confounds and to let a near-constant signal masquerade; the reading must earn its way
first.)

## 7. Risk controls (the lessons, as guardrails)

- **No argmax collapse** — keep full operators/distributions.
- **No bag-only aggregation** except as the explicit baseline.
- **No policy translation before reading validation.**
- **No hidden fallbacks** — surface every failure / warning.
- **No unsupported Sanskrit privilege** — varṇa is one chart; test comparatively vs
  IPA / random.
- **Every added layer must improve a measurable signal** vs the simpler version, or it is
  removed.
- **Gauge discipline** — report only gauge-invariants as meaningful.
- **Provisional operators** are labeled provisional (not yet estimated from data).
- **Output is structure, not validated meaning,** until human data says otherwise.

## 8. Minimal build plan (staged)

- **Stage A — offline reading engine:** operator-product + bag baseline + the evaluation
  hooks. Cheap, deterministic, no API.
- **Stage B — structural validation:** test order-sensitivity + factorization; must beat
  bag / random / relabel. *(Replaces O1.5's meaning test with a structural one, since
  meaning needs human data.)*
- **Stage C — baseline & inventory comparison:** vs bag / sentiment / length / random;
  varṇa vs IPA vs data-derived partition, on structural metrics.
- **Stage D — gated:** cross-modal and/or LLM/policy **only after** A–C pass **and** human
  order-effect data exists.

---

## Stop/Go (conservative)

**Design-only is complete with this document.** Stage A may be **designed** but **not
implemented until explicitly authorized.** When authorized, build Stage A *only* as a
minimal structural testbed (operator product vs bag, structural metrics), kept cheap, with
a pre-registered structural gate; treat its output as **structure, never validated
meaning.** Do not proceed past Stage A (no C/D, no LLM, no policy, no cross-modal build)
until **(a)** Stage A clears its structural gate **and (b)** human single-modality
order-effect data exists. **The binding constraint is data, not code:** the decisive test
of the theory — does the order-structure carry *meaning*, and is it *cross-modal* —
requires human order-effect measurements that **no engine can produce**. If forced to
choose one next investment, it is the **human order-effect study, not engine elaboration.**
