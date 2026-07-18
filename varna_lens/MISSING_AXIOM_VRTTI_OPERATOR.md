# Design Note — Missing Axiom for Vṛtti Operator Formalization

**Status:** Theory/architecture design only. No implementation, no code, no experiments, no Stage A modification, no pre-registration change. No semantic claim.

**Accepted assumptions:** (1) each varṇa has one fixed vṛtti; (2) a vṛtti is a propensity; (3) a vṛtti modifies/transforms a latent state; (4) word meaning = ordered composition of vṛttis; (5) not acoustic-iconic; (6) Stage A is a mathematical pattern only, not the table.

---

## 1. What axiom is missing?

Assumptions 1–6 fix the **shape** (a per-varṇa operator; ordered composition) but leave **L totally free** — nothing determines *which* operator a vṛtti is. The missing axiom is a **grounding / coordinatization axiom**:

> **(Grounding axiom, schematic)** There is a fixed rule assigning each vṛtti an operator/kernel from a **pre-specified, non-phonological property of the vṛtti**, the property specified **independently of the meanings to be predicted**, supplying **≥ 2 independent coordinates that engage non-commuting generators** (so composition is order-sensitive).

Two separable load-bearing clauses:
- **Non-circularity:** the operator must be fixed by a property specified *before and independently of* the prediction target. Otherwise "vṛtti → operator" = "fit the operator to the data" → unfalsifiable.
- **≥2 non-commuting coordinates:** one coordinate/generator gives commuting operators (`exp(cG)`) → order-blind → contradicts Assumption 4. Order-sensitivity requires ≥2 coordinates hitting non-commuting generators. (This is why Stage A's order gate passed: 4 coordinates, coupling generators.)

## 2. Which category is it?

Primarily **semantic coordinates** (vṛtti content → operator parameters), inseparable from **the state space** (coordinates must act on something) and a **polarity structure** on it (so binding/liberating has a referent). **Deterministic-vs-stochastic and readout are downstream, not the missing axiom.** Operator type and composition law are already constrained by Assumptions 3–4.

## 3–4. Candidate axiom sets

**Baseline Ø — Free operators.** No grounding. Only structural claims survive (order-sensitivity). Codomain: any operator monoid. Composition: product. Det/kernel: either. Stage-A-compatible: yes. **Rules out nothing → predicts nothing → unfalsifiable** (the "merely metaphorical" floor).

**Set 1 — Semantic-Coordinate Grounding (general).** `L(σ)=exp(Σ_j c_j(σ) G_j)`, `c` a fixed non-phonological map, `{G_j}` non-abelian. Consequence: L fixed by `c`; order-sensitive iff non-abelian. Codomain: a matrix Lie group. Composition: operator product. Deterministic (kernels if generators stochastic). **Stage-A-compatible: yes.** Rules out nothing algebraically; pushes blocker to "where does `c` come from?"; circular if `c` fitted/gloss-embedded.

**Set 2 — Polarity + Intensity (minimal, non-circular instance of Set 1).** `c(σ)=(polarity, intensity)` from the **frozen lexicon**, mapped to two **non-commuting** generators. Consequence: **non-circular by construction**. Codomain: 2-generator subgroup. Composition: product, non-commutative (required). Deterministic. **Stage-A-compatible: yes.** Rules out >2-dim semantics; rules itself out if the two generators commute. Risk: 2 coords coarse.

**Set 3 — Counter-Pole Involution (structural rider).** `L(σ†)=L(σ)^{-1}` for the lexicon counter_pole `†`. Consequence: **forces invertible operators (a group)**; counter-poles = inverses. Codomain: a group. Composition: group product. Deterministic. **Stage-A-compatible: yes** — if `c(σ†)=−c(σ)` then `exp(−ΣcG)=L(σ)^{-1}` (counter-pole = coordinate negation). Rules out dissipative/non-invertible vṛttis. Best as a rider on Set 1/2.

**Set 4 — Propensity-Kernel / Entropy-Polarity (stochastic).** `X` finite symbolic meaning-state; each vṛtti a Markov kernel `K_σ` with target `μ_σ`; **polarity = sign of entropy change** (binding contracts, liberating disperses). Consequence: propensity literal (distribution); polarity = entropy geometry. Codomain: Markov kernels on `X`. Composition: Chapman–Kolmogorov, non-commutative. **Kernels** (deterministic = point-mass limit). **Stage-A-compatible: NO** (SO(4) preserves entropy → cannot express binding-as-contraction). Rules out entropy-neutral realizations; forces non-invertibility/stochasticity. Highest faithfulness, highest cost.

**Set 5 — Finite-State Transition (discrete deterministic).** `X` finite; each vṛtti a function `t_σ:X→X`; polarity = contracts vs expands the reachable set. Consequence: point-mass limit of Set 4; fully discrete/interpretable. Codomain: transition monoid. Composition: function composition, non-commutative. Deterministic. **Stage-A-compatible: no** (different carrier). Rules out graded blending.

## 5. Ranking

| axiom set | minimality | faithful to "propensity" | implementability | elegance | falsifiability |
|---|---|---|---|---|---|
| Ø free | — | — | high | — | none (unfalsifiable) |
| 1 general coords | low | med | low | med | low–med (circular risk) |
| **2 polarity+intensity** | high | med | high | med-high | **high (pre-specified ⇒ non-circular)** |
| 3 counter-pole rider | high | n/a alone | high | high | high (adds a testable law) |
| 4 propensity-kernel | low | highest | med | high | med (target-dist circularity risk) |
| 5 finite-state | med-high | med | high | med | med |

Decisive column: **falsifiability**, which tracks **non-circularity** — grounding in frozen lexicon fields (polarity, counter_pole) is testable against the scramble null; fitted/embedded coordinates are not.

## 6. Recommendation

- **Primary: Set 2 + Set 3** — polarity+intensity coordinates with counter-pole = coordinate negation, as deterministic operators via the **Stage-A construction pattern with semantic (not phonological) coordinates**. Minimal axiom that (a) fixes L from **pre-registered** data (non-circular), (b) yields order-sensitivity (mandatory non-commuting-generator clause), (c) is **falsifiable against scramble**, (d) reuses existing machinery. Weakness: directional (not distributional) propensity; 2 coordinates may be coarse.
- **Fallback: Set 4** — propensity-kernel with entropy-polarity — if the directional reading is too coarse and genuine dispersion is needed. Most faithful to "propensity," higher cost, Stage-A-incompatible, requires care to keep target distributions non-circular.

## 7. Critical — unfalsifiable / metaphorical axioms

- **Ø (free operators):** unfalsifiable; surviving structural claims are true of all sequential language.
- **Set 1 with fitted or gloss-embedded coordinates:** circular — the single most important failure mode. The enterprise's falsifiability rests on coordinates being fixed *independently of the prediction target*.
- **Polarity-only (k=1):** commutative → order-blind → contradicts Assumption 4.
- **Any "operator defined to reproduce the observed meaning":** definitionally circular.

**Non-negotiable clause:** the grounding property must be **pre-specified and independent of the meanings to be predicted** (polarity and counter_pole qualify — frozen before any operator existed; embedded glosses and free parameters do not). Without it, no state space, operator family, or readout can rescue falsifiability.

> structure, not validated meaning.
