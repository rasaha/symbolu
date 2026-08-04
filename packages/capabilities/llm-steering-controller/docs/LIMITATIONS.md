# Limitations

The controller recommends model/provider routing. It does **not** execute model requests, load provider
credentials, perform retries or fallbacks, or replace the Agent Runtime. It contains no Hybrid LLM model
internals.

## What this package establishes

- The canonical LLM routing/steering implementation is identified and packaged (single source).
- Routing recommendations are **deterministic** under fixed inputs and policy.
- **Hard constraints are enforced before scoring**; no soft score restores a disqualified candidate.
- Recommendation **evidence is reproducible** (fingerprints + full rejection/score records).
- The package performs **no provider execution** and **imports without side effects**.

## What this package explicitly does NOT establish

- **No** best model-selection quality.
- **No** production routing performance.
- **No** cost savings, latency reduction, or reliability improvement.
- **No** provider availability guarantees.
- **No** safe autonomous fallback (fallback is a recommendation only).
- **No** customer validation, production readiness, or production certification.
- **No** AGI or Hybrid-LLM superiority claim.

## Evidence tier

All scores are **estimated from declared / configured metadata**, not measured production values. Quality,
reliability, availability, cost, and latency priors are configured inputs; the package makes no empirical
performance claim. Simulation is over `FAKE_LOCAL_FIXTURE` inputs and validates deterministic *policy*
behavior only — never real routing outcomes.

## Scope boundaries

- The registry holds metadata only; live catalog refresh is out of scope (belongs outside the advisory
  core).
- Confidence is a dispersion diagnostic, not a correctness probability.
- The controller does not choose *whether* to call a model, only *which* it would recommend if a
  governed runtime decides to proceed.
