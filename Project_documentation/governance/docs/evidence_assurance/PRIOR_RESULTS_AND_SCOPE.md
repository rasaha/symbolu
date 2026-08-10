# Prior Results and Scope

*Phase 1. Records what the AGE and AssertionGate-robustness studies established, and why this track
is **upstream** (evidence verification) rather than another downstream AssertionGate revision. Prior
outcome-bearing artifacts are hashed and guarded by `evidence_assurance/verify_prior_artifacts.py`
(fails on drift).*

## What the AGE experiment established

- Assertion governance is a legitimate delivery-boundary function; single existing signals
  (confidence, grounding, entailment, authority) are each insufficient.
- On oracle-clean signals, a thin composition **grounding + entailment + risk (`G_risk`)** matched a
  synthetic rubric **perfectly (1.00 agreement, 0.00 unsupported-escape)** — a dedicated engine was
  not justified.

## What the AssertionGate robustness study established

1. Simple grounding + entailment + risk remained **useful under ordinary noise** (`G_risk` did not
   collapse; escape-AUC ≈ 0.024, never > 0.10).
2. A **thin calibrated rule outperformed a more elaborate AssertionGate** on escape.
3. **Conflict and freshness checks were load-bearing**; the aggregate uncertainty scalar was not.
4. **No tested composition remained safe under correlated failure** — escape 0.09–0.45 when grounding
   and entailment failed together with high confidence.
5. Grounding and entailment can **fail together when both rely on the same incorrect evidence**.
6. Adding more **downstream** decision logic cannot reliably repair **upstream** evidence failure.

## The clean `G_risk` result and the noisy findings (frozen)

- Clean (oracle): `G_risk` = 1.00 agreement / 0.00 escape.
- Noisy: `G_risk` degrades gracefully on ordinary noise; the thin gate halves escape vs `G_risk` at
  modest false-blocking cost, but a 2-parameter calibrated rule is safer still.
- Correlated: **every** method fails (escape 0.09–0.45). This is the unsolved boundary.

## Why downstream combination failed

The prior studies operated **after** evidence was produced: they consumed a grounding score, an
entailment label, and meta-signals (confidence/conflict/freshness), then combined them. When the
**upstream evidence itself is wrong and both grounding and entailment are computed against that same
wrong evidence**, they fail *together* and *confidently* — so no downstream combination of their
outputs has an independent signal to detect the failure. The confidence a downstream gate would
propagate is itself derived from the corrupted evidence.

## Why this track is upstream, not another AssertionGate revision

The failure boundary is **the evidence**, not the decision logic over it. This track therefore moves
**upstream of AssertionGate** to verify the *evidence state* directly — provenance, source
independence, claim-to-source alignment, authority, freshness, and counterevidence — before any
grounding/entailment score is trusted. The question is whether verifying these evidence properties
can detect correlated failure that downstream signal-combination structurally cannot. This is a
genuinely different lever, tested here without assuming it works.

## Prior artifacts (frozen; verified by `verify_prior_artifacts.py`)

| Artifact | SHA-256 (prefix) |
|---|---|
| `assertion_governance/data/corpus_v1.json` | `f16ed388…` |
| `assertion_governance/eval_results/evaluation_v1.json` | `90dc6b3a…` |
| `assertion_gate_robustness/data/v1/corpus.json` | `b86c24be…` |
| `assertion_gate_robustness/eval_results/robustness_v1.json` | `d2d5d0f8…` |

## Scope discipline

- **Prior final-evaluation data is NOT reused as this study's primary evaluation set.** This track
  builds a **new** provenance/evidence corpus (`evidence_assurance/data/v1/`).
- No prior AGE / AssertionGate / ExecutionGate / ModelPolicy / ActionGate / TAP / control-plane /
  frozen artifact is modified.
- No live provider calls, no unrestricted web retrieval, no real actions, no control-plane
  integration, no enforcement. Counterevidence search operates on the frozen corpus + local fixtures
  only.
