# SYMBOL_U_UNBLOCKED_RESEARCH_PLAN

> **STATUS — Research-planning document. Adopts a data-independent track.** Documentation only.
> No implementation, no data, no analysis run, no Stage A / structural_v1 modification, no
> semantic claim, no L2/`F`/decoder work, ⊥ preserved. Does **not** reopen A′ and does **not**
> start Milestones B–G. Date: 2026-06-29. **structure, not validated meaning.**

## 0. Standing state (established; not revisited here)
- **A′ = NOT EXECUTED — canonically halted due to data availability.** No admissible,
  construct-aligned, mutually-available `E×Y` pairing exists (see
  `MILESTONE_A_PRIME_EXECUTION_STATUS.md`). **A′ is not reopened by this plan.**
- No PASS / FAIL / ⊥ / INCONCLUSIVE has been emitted for A′ (no run occurred).
- Stage A (`symbolu_neural/structural_v1/`) remains **frozen**.
- The A1.4 projection pipeline is validated as **engineering only** (`experiments/a_prime/`).
- The identifiability observation `rank(X)=21 < 23` on the frozen-operator-adjacent projection
  remains recorded.
- No downstream semantic conclusions may be drawn.

## 1. Why a data-independent track
Milestones A′, B, C, D, E, F, G and the CSR/STL line are all **externally blocked** (licensed
construct-aligned `E×Y`, independent replication data, human order-effect data, or neural/LLM
infra). Holding the entire program on A′ — which is *canonically halted for lack of data* —
would freeze all progress on a test that cannot run. This plan therefore opens a **parallel,
self-contained track** of work that requires **no external dataset** and makes **no semantic
claim**, while leaving the data-blocked semantic track exactly where it is.

## 2. Six binding statements (scope guards for this track)
1. **A′ remains canonically halted** due to data availability; nothing here changes or bypasses
   that.
2. **D₀′ does NOT bypass A′ for semantic validation.** It answers a *structural* question and
   provides no evidence about meaning, dictionary prediction, or Sanskrit privilege.
3. **D₀′ is a structural / gauge / operator-algebra falsifier ONLY** — non-commutativity,
   joint-diagonalizability, Hankel-rank/class-irreducibility, gauge invariants. No `Y`, no `F`,
   no decoder, no probe-on-meaning.
4. **A positive D₀′ result means only "nontrivial frozen operator algebra"** (the
   feature-derived Stage A operator instance is non-abelian / not a bag). It is **not** semantic
   validity, **not** validation of Symbol-U's "true" operators, and **not** an A′ result.
5. **A negative D₀′ result may structurally falsify the current frozen Stage A operator
   instance** (effectively abelian / jointly diagonalizable / no Hankel-rank gap ⇒ the
   distinctive non-commutativity claim fails on the only operator instance we have). This is a
   structural falsification of that instance, not of any semantic claim.
6. **B.0, if later decoupled, is harness calibration ONLY** — probe/baseline/⊥ power, false-
   positive rate, minimum detectable effect on synthetic data. It is **instrument readiness, not
   semantic progress**, and emits no A′/B decision.

## 3. Per-thread analysis (blocked vs unblocked)

| Thread | Blocked? | Blocking dependency | Answerable now? | Cheapest falsifier | De-risk |
|---|---|---|---|---|---|
| **D₀′ gauge/identifiability + operator algebra** | **No** | none (frozen ops reproducible read-only) | Are the operators non-abelian / class-irreducible, or effectively a bag? | commute / jointly-diagonalizable / Hankel-rank ≤ abelian ⇒ bag | **Highest** — grounds or kills the operator substrate; pre-empts D |
| B.0 synthetic harness calibration | Self-imposed gate only | A′-PASS gate (§12) — now permanently unmet | probe power / FPR / min-detectable-effect | planted signal undetected, or null not → ⊥ | Medium — makes future A′/B interpretable |
| L2 `F`-family theory | No | none | which functionals are admissible/non-additive | a member reduces to the bag | Low — *representation before evidence* (anti-pattern) |
| A′ / B / C / D / E / F / G | **Yes** | licensed `E×Y` / replication / human data / prior gates | — | — | — |
| CSR / STL | **Yes** | neural/LLM infra (no API) | — | — | — |
| Phase-Quad operator theory | Tangential | entangled with the LLM-training line; off the Symbol-U falsification path | — | — | Low |

## 4. Dependency graph

```
                    ┌───────────────────── EXTERNAL-DATA / INFRA BLOCKED ─────────────────────┐
  A′ (E×Y) ─────────► B(atomic+order) ─► C(replication) ─► D(human order-effect) ─► E ─► F ─► G
        (CANONICALLY HALTED — not reopened)                                                    
  CSR/STL ── needs neural/LLM infra (no API)                                                   
  └──────────────────────────────────────────────────────────────────────────────────────────┘

  ┌────────────────────────── SELF-CONTAINED DATA-INDEPENDENT TRACK ──────────────────────────┐
  │  D₀′ Gauge-invariant operator-algebra analysis  ◄── frozen Stage A operators (read-only)    │  ◄── NEXT
  │        │   defines the gauge-invariant observables any future operator validation (D) needs │
  │        └──► B.0 synthetic harness calibration (decoupled from §12 A′ gate; power/FPR/MDE)    │
  │  L2 F-theory — deferred (gate behind evidence)                                              │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
        A1.4 projection pipeline ✓ (already validated — engineering only)
```

## 5. Revised critical path (data-independent first)

```
D₀′  Gauge-invariant operator-algebra analysis (frozen ops, read-only)
       │   TERMINAL (structural only): effectively abelian / jointly diagonalizable /
       │   Hankel-rank ≤ abelian  ⇒  non-commutativity claim fails on this operator instance
       ▼
B.0  Synthetic validation-harness calibration (decoupled from the A′ §12 gate)
       │   instrument readiness only — power / FPR / minimum detectable effect
       ▼
[DATA-BLOCKED TRACK UNCHANGED]  A′ (halted) → B → C → D (reuse D₀′ invariants) → E → F → G
```

The A′ §12 hard gate is **narrowed**, not removed: it still blocks all **representational and
semantic** work (`F`, decoders, comparative, and any real-data A′/B run). It no longer blocks
**self-contained, non-semantic methodology** (D₀′, B.0), because that work needs no data, builds
no representation, and emits no semantic decision — so none of the gate's protective intents
apply to it.

## 6. Next single milestone (max information / effort): D₀′

**D₀′ — Gauge-Invariant Operator-Algebra Analysis** (design + **read-only** computation on the
frozen, feature-derived Stage A operators; new code in `experiments/`, never touching
`structural_v1/`).

**Justification.**
- **Mathematics.** Symbol-U's distinctive content is non-commutativity (`M_a M_b ≠ M_b M_a`); if
  the `{M_σ}` commute, the theory collapses to the bag (VSO falsifiers #2/#3). Compute, in a
  **gauge-invariant** (similarity-invariant) way: (i) pairwise commutator norms; (ii) joint-
  diagonalizability defect; (iii) Hankel-rank separation of `w ↦ u^⊤ M_{σ_n}…M_{σ_1} s₀` vs the
  best abelian model (Fliess–Schützenberger); (iv) the gauge-orbit dimension and the identified
  invariants — which *is* the D₀ deliverable that makes "validate operators" well-posed.
- **Information theory.** A Hankel-rank gap is the precise falsifiable statement that the
  sequence→observable map carries information no additive/commutative model can represent — all
  without any semantic `Y`.
- **Software architecture.** Read-only import of the frozen feature→operator construction; new
  analysis code in `experiments/`; numpy-only; minutes to run; fully reproducible.
- **Experimental design.** Terminal-capable and near-free; pre-empts the most expensive
  milestone (D, human data) and supplies the gauge-invariant methodology D will reuse for any
  future *data-estimated* operators.
- **Honest scope (per §2).** These are the *feature-derived* Stage A operators — a benchmark
  proxy. A positive result is "nontrivial operator algebra," not semantic validity and not
  validation of the "true" operators; a negative result structurally falsifies *this* operator
  instance. Purely structural; no meaning claim; ⊥ preserved.

## 7. Out of scope for this track (explicit)
No reopening of A′; no Milestone B–G representational/semantic work; no `F`, decoder, or probe-
on-meaning; no external data; no Stage A modification; no semantic, dictionary-prediction, or
Sanskrit-privilege claim. D₀′ and B.0 produce **structural / methodological** artifacts only.

---

## Standing constraints (do not weaken)
A′ canonically halted · structural-only track · no semantic claims · no `F`/decoder · Stage A
frozen · gloss-independent inputs · ⊥ preserved · structure, not validated meaning.

> **structure, not validated meaning.**
