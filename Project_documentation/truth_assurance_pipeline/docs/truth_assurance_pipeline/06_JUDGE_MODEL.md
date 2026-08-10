# TAP — Judge Model v0.1

Defines judge **roles**, not implementations. Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Roles

| Role | Responsibility |
|---|---|
| **Evidence Advocate** | find evidence that *supports* the assertion. |
| **Evidence Challenger** | independently try to *falsify* the assertion. |
| **Deterministic Validator** | settle anything a rule/schema/computation can settle (`07_…`). |
| **Adjudicator** | resolve genuine advocate/challenger disagreements, predicate by predicate. |

## 2. Hard rules

1. **Judges never replace deterministic evidence.** If a deterministic validator can
   decide a point (schema, id, date, citation, math, code, DB lookup), its result is
   authoritative and judges do not overturn it.
2. **No majority voting as the primary mechanism.** Disagreements are resolved by the
   Adjudicator on evidence, not by counting votes. (Voting may appear only as a
   secondary, logged signal, never as the deciding rule.)
3. **Challenger independence.** The Challenger must not receive the Advocate's
   conclusion; it forms its own view from the evidence.
4. **Adjudicator resolves predicates, not preferences.** It decides each disputed
   predicate from the evidence and explicitness, not by picking a favored side.
5. **Adjudicator runs only on genuine disagreement**, keeping cost proportional to
   difficulty.

## 3. Where judges live

Judges are a *mechanism* usable inside any truth layer (1, 2, 4, 5). The
Deterministic Validator is a cross-cutting authority (`07_…`). A layer may be
implemented as deterministic-only (no judges) or deterministic + judges; either
conforms, because the interface (`03_…`) is the contract, not the mechanism.

## 4. Reference instantiation (existing, synthetic, Layer 4)

The `relationship_claim_validation/` v0.1 prototype instantiates all four roles
**deterministically** (advocate, challenger, deterministic pre-checks, adjudicator)
for the Claim Validation Layer. Its measured ablation shows each role removes a **distinct
failure class** (challenger → contradictions; adjudicator → equally-explicit
conflicts). That is a **synthetic, construction-validated** demonstration of the role
decomposition — not evidence that any LLM-judge instantiation works. See its
`docs/relationship_claim_validation/JUDGE_PROTOCOL.md` and `FINAL_VERDICT.md`.

## 5. LLM vs deterministic judges

The role model is agnostic to whether a judge is an LLM or a rule engine. TAP
requires only that: deterministic evidence is never overridden; the challenger is
independent; and adjudication is evidence-based, not vote-based. Determinism vs
LLM is an *implementation* choice measured per experiment (`10_…`, `11_…`).
