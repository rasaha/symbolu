# ADR — Cloud Scaling: Canonical Capacity Intelligence (Phase 1)

**Status:** **ACCEPTED.**
**Date:** 2026-08-11
**Package:** `packages/capabilities/cloud-scaling-controller` (`ugence-cloud-scaling-controller`), v0.1.1 → **v0.2.0**.
**Scope:** Additive observation / normalization-projection / recommendation-evidence
layer built *around* the existing Cloud Scaling Controller. The controller's advisory
authority, provider neutrality, and five-signal decision algorithm are unchanged.

---

## Context

The Cloud Scaling Controller is a deterministic, provider-neutral, **advisory-only**
recommendation engine. Its stable input contract, `ScalingObservation`, carries five
normalized decision signals (`cpu`, `memory`, `latency_p99`, `error_rate`, `queue_depth`)
plus `deploy_active`, `recent_pod_restarts`, `current_replicas`, `phase`, `correlation_id`
and `timestamp`. Its output, `ScalingRecommendation`, is advisory (`advisory_only=True`,
`actuation_performed=False`) with a `determinism` disclosure block.

We want later capacity intelligence (forecasting, topology, economics) and later
governance (the shipped Risk Authority RA-1→RA-8 lifecycle) to consume a **trustworthy,
provider-neutral representation of the operational world** with explicit provenance,
units, normalization, projection, scope, and immutable recommendation evidence — *without*
changing the existing controller's authority or its tested decision behavior, and without
confusing observed information with decision authority.

The naive path — feed a richer metric set straight into the controller — would silently
change the tested five-signal decision model, entangle provider semantics with the
decision kernel, and invite feature creep. We reject it.

## Decision

Introduce a new, additive, pure-stdlib subpackage
`ugence_cloud_scaling_controller.canonical` implementing the Phase-1 flow:

```text
Provider / Monitoring Source
        ↓
CanonicalCapacityState          (rich, immutable, versioned, provider-neutral)
        ↓
Normalization / Projection      (explicit, deterministic, policy-driven)
        ↓
existing ScalingObservation
        ↓
existing CloudScalingController (UNCHANGED decision kernel)
        ↓
ScalingRecommendation  +  CapacityDecisionEvidence  (immutable, sha256 content-identity)
```

The canonical state is deliberately richer than the decision model (workload,
performance, infrastructure, capacity, reliability, deployment, economics, topology,
forecast — all optional). An explicit `project_to_scaling_observation` maps **only** the
controller's established inputs and reports everything else as *ignored context*. The
controller then runs unmodified. `CapacityDecisionEvidence` records, distinctly:

```text
observed  !=  normalized  !=  decision-used  !=  recommendation
```

Evidence is built only through a controlled service path (`recommend_with_evidence`),
binding it to the *real* projection and *real* controller output so it cannot be forged by
a caller-supplied recommendation. Its `sha256:` digest is a **content identity** for later
authority binding — not a signature, verdict, or authorization.

### Why the canonical state does NOT directly expand the controller algorithm

1. **Preservation of tested behavior.** The controller's decision fields are frozen by a
   behavior-baseline parity suite. Routing new signals into the kernel would break that
   contract; projecting into the *existing* five signals preserves it exactly.
2. **Provider neutrality.** Provider semantics terminate at observation/normalization.
   Provider labels live only in provenance; the projection has no `provider == "..."`
   branch. The decision kernel stays provider-neutral.
3. **Prevention of feature creep.** Presence of a field in `CanonicalCapacityState`
   (GPU utilization, economics, forecast, topology) does **not** make it decision-driving.
   Ignored fields are reported as ignored, never as causal evidence.
4. **Room for richer reasoning later.** Forecast/topology/economics intelligence can be
   layered above the canonical state in future phases without touching the controller.
5. **Separation of observed vs decision-used information.** The projection's
   used/ignored/missing accounting makes the boundary auditable.
6. **Honest causal evidence.** Evidence never implies ignored data drove the decision;
   it records exactly which signals reached the controller.
7. **Stable evidence for later authority binding.** A deterministic, documented digest
   over decision-relevant fields gives a future integration package a stable identity to
   reference.
8. **No reverse dependency on RA-1→RA-8.** The controller stays a numpy-only leaf; it
   does not import any authority/orchestration package. Canonicalization/digest
   conventions are *mirrored by pattern*, not imported.

### Key sub-decisions

- **`current_replicas` ← `capacity.running_replicas`.** The controller documents
  `current_replicas` as the *current running replica count*, so the projection reads
  `running_replicas` and never silently substitutes `ready`/`healthy`/`desired` (distinct,
  and material for later execution/effect verification). Missing `running_replicas` fails
  closed.
- **`latency_p99 != latency_p95`.** p95 stands in for a missing p99 only under an
  explicitly named policy opt-in (`allow_latency_p95_substitution`), and the substitution
  is disclosed in the projection warnings and evidence.
- **Time phase is separate from deployment rollout phase.** The controller's `phase` is an
  operational *time context* (`peak`/`normal`/`off_peak`/`maintenance`), modeled as the
  canonical `time_phase`. `deployment.rollout_phase` is a distinct lifecycle field and is
  treated as ignored context (only `deployment.deploy_active` maps to the controller).
- **Independent schema versions.** `capacity-state-1`, `capacity-evidence-1`,
  `capacity-normalization-policy-1`, `capacity-projection-1`. The existing
  `ScalingObservation`/`ScalingRecommendation` schemas are **not** bumped.
- **Digest determinism.** The evidence digest excludes `evidence_produced_at` (production
  time, isolated from the decision path) and `controller_explanation` (embeds the disclosed
  nondeterministic `identity_deviation` diagnostic); it is reproducible for identical
  `(state, policy, config, controller history)`.

## Boundary: what Phase 1 does NOT own

Phase 1 owns **OBSERVATION + NORMALIZATION/PROJECTION + RECOMMENDATION EVIDENCE**. It does
not own — and this layer never performs — RISK EVALUATION, AUTHORITY, AUTHORIZATION,
action-gate ENFORCEMENT, ACTUATION, or EFFECT VERIFICATION. No AWS/Azure/GCP or Kubernetes
actuation, predictive forecasting, dependency optimization, cost optimization, cross-cloud
placement, Risk Authority integration, or LLM is added. `CapacityDecisionEvidence` is
upstream recommendation evidence only.

## Future architecture (documented, NOT implemented here)

The exact authority lifecycle and package ordering are defined by the shipped RA-1→RA-8
contracts and their ADRs (`ADR_RISK_AUTHORITY_RA45…RA8…`, `RISK_AUTHORITY_RA*_SPEC.md`);
this ADR does not restate or simplify them in code. Downstream stages below Phase 1 are
**not implemented** in this phase:

```text
Observability
      ↓
Canonical Capacity State                         [IMPLEMENTED — Phase 1]
      ↓
Forecast / Topology / Economics Intelligence     [NOT IMPLEMENTED]
      ↓
Capacity Intelligence                            [NOT IMPLEMENTED]
      ↓
ScalingRecommendation + CapacityDecisionEvidence [IMPLEMENTED — Phase 1 ends here]
      ↓
Separate Cloud-Governance Integration Package    [NOT IMPLEMENTED]
      ↓
Canonical RA-1→RA-8 Authority Lifecycle          [IMPLEMENTED ELSEWHERE — not integrated here]
      ↓
Downstream Decision / Exact-Action Enforcement   [IMPLEMENTED ELSEWHERE — not integrated here]
      ↓
Provider Executor                                [NOT IMPLEMENTED]
      ↓
Execution Receipt                                [NOT IMPLEMENTED]
      ↓
Runtime Assurance                                [IMPLEMENTED ELSEWHERE — not integrated here]
      ↓
Observed Effect                                  [NOT IMPLEMENTED]
```

The dependency direction is one-way and must stay so: the Cloud Scaling Controller
*produces* `CapacityDecisionEvidence`; a **separate, future** cloud-governance integration
package would *reference/translate* that evidence into the canonical RA-1→RA-8 lifecycle.
Neither leaf package depends directly on the other.

## Consequences

- **Positive:** the controller's tested behavior, advisory authority, provider neutrality,
  and numpy-only footprint are preserved; observation richness and honest evidence are
  gained; a stable evidence identity is available for later governance without any reverse
  dependency.
- **Cost:** a new subpackage and a minor distribution bump (0.2.0); the canonical layer is
  additive surface area to maintain.
- **Explicitly deferred:** native cloud collectors, forecasting, dependency/economic
  reasoning, the CapacityDecisionEvidence→RA integration adapter, provider execution, and
  effect verification.

## Verification

Package suite + canonical suite green (`pytest tests/`), behavior-baseline parity
unchanged, advisory distribution verifier green (wheel content scans, isolated install),
RA/authority dependency-boundary tests green. See the PR body and
`docs/EVIDENCE_AND_LIMITATIONS.md`.
