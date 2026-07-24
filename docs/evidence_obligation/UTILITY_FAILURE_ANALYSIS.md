# Utility-Failure Analysis (Phase 1)

*Where the natural-artifact utility failure comes from, established from the frozen bounded_shadow_pilot
evidence, so the calibration target is precise.*

## The failure, located

The prior pilot's full-stack governed runtime, on 857 natural artifacts:

- delivered **0% clean allow**,
- **over-qualified 85.5%** of benign documentation,
- withheld or escalated the rest,
- with **0 unsafe permits** and every safety property intact.

The failure is therefore **not a safety failure and not a gate defect** — it is a **utility/calibration**
failure, and it is located **upstream of the gates**.

## The causal chain

```
natural text
   -> derivation assigns a UNIFORM evidence obligation / evidence state
      (typically VERIFIED_WITH_LIMITATIONS, because natural text carries no gold evidence bundle)
         -> EvidenceAssurance correctly judges that state as limited
            -> AssertionGate correctly qualifies
               -> final disposition = WOULD_QUALIFY (85.5%)
```

Every stage after the derivation behaves **correctly relative to its input**. The defect is the
**uniform evidence burden** applied at the top: a plain descriptive docstring, a policy statement, a
code-behavior claim, and a medical claim are all handed the same blunt obligation, so the runtime treats
an inspectable implementation detail with the same suspicion as an unverified external factual claim.

## The evidence-sensitivity proof

The bounded_shadow_pilot derivation-sensitivity probe is the key diagnostic:

| Derived evidence base | Clean-allow rate |
|---|---|
| `VERIFIED_WITH_LIMITATIONS` (uniform, blunt) | 0.0% |
| `VERIFIED` (optimistic, uniform) | 83.3% |

Both bases are **uniform**. Flipping the uniform base moves the clean-allow rate from 0% to 83%,
demonstrating (a) the runtime is not broken, and (b) the outcome is dominated by a single uniform knob.
Neither uniform setting is correct: `VERIFIED_WITH_LIMITATIONS` under-credits inspectable/authoritative
claims; blanket `VERIFIED` would over-credit unverified external factual claims and **create unsafe
allows**. The honest fix is **heterogeneous**: assign each claim the obligation its type/risk/source
actually warrants.

## The calibration target (what this track must move)

| Metric | Prior | Target direction |
|---|---|---|
| Clean allow | 0.0% | **materially higher** — only where the lower obligation is justified |
| Over-qualification | 85.5% | **materially lower** |
| Unsafe assertion allow | 0 | **stay 0** |
| Unsafe action allow | 0 | **stay 0** |
| High-risk unsafe allow | 0 | **stay 0** |
| False withholding | (bounded) | bounded |
| Review burden | 11.6% | bounded |

## The mechanism to test

A distinct **EvidenceObligation** stage, upstream of Evidence binding, that classifies each claim's
type, source role, artifact authority, risk, and use, and assigns one of a rich set of obligation types
(external-authoritative, independent-corroboration, internal-authoritative-sufficient,
implementation-sufficient, telemetry-required, attribution-verification, policy/authority,
logical/mathematical, temporal, contextual-sufficient, no-factual-gate, qualify-by-default,
human-review, indeterminate). It specifies the **required** evidence standard; EvidenceAssurance still
decides whether available evidence **meets** it. Crucially, "no external evidence required" must be
represented as *obligation satisfied by context*, **never** as *claim is verified*.

## The falsification obligation

The hypothesis — that a uniform evidence burden is the primary cause and that a contextual policy fixes
it without weakening safety — is only credible if it survives: simple-comparator challenges (risk-only,
claim-type-only), safety subgroup analysis, adversarial obligation cases, source-role reliability,
implementation self-verification risk, and the "EvidenceAssurance already captures this implicitly"
null. Those are preregistered in `FALSIFICATION_PLAN.md` (Phase 5) and frozen before final evaluation.
