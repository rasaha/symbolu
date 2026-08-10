# ACP V2.1 — Internal Summary (measured evidence vs vision)

Investor-safe. This separates **what we measured** from **what we believe** and
**what we have not shown**. Nothing here is a production or platform claim.

## The question we set out to answer

> Can the complete Ugence governance stack independently evaluate both
> *authorization* (ActionGate) and *operational safety* (ACP) for the same exact
> Kubernetes action, with clean ownership, deterministic composition, and zero
> impact on the authoritative runtime?

## What we measured (fact)

- We ran the **real** ActionGate authorization engine and the **real** ACP
  operational-safety adapter on the **same, cryptographically-bound** Kubernetes
  Deployment operation, across 18 scenarios, in shadow mode.
- The two layers composed into **8 well-defined outcome classes** with **0**
  contradictory-ownership errors and **0** duplicated constraints.
- **All 13 safety invariants held**, including the two that matter most
  commercially: an ActionGate **denial is never overridden**, and ACP **never
  grants authorization**. Execution is *hypothetically* eligible only when **both**
  layers pass.
- Both layers independently caught **post-approval tampering** (a changed replica
  state or a modified patch) at commit time.
- Everything was **deterministic** (identical reruns, identical authorization
  hashes) and had **zero** impact on any authoritative path — no cluster was
  touched, no execution token minted.
- The ACP decision core is the **frozen V1 core, unchanged** (hash-verified);
  ActionGate was **unmodified** — we only invoked it.

**Measured verdicts:** integrated composition `INTEGRATED_STACK_SUPPORTED`;
live-Kubernetes evidence `LIVE_K8S_SHADOW_LIMITED`; product evidence
`CONTROL_PLANE_STACK_PARTIALLY_VALIDATED`.

## What this demonstrates (supported interpretation)

The two-layer "authorized **and** operationally safe" governance model is
**architecturally real**, not a slide. Two independently-built engines — one for
*may I?*, one for *is it safe right now?* — evaluated the same action, kept clean
ownership boundaries, and composed deterministically. This is the core technical
premise of a governance control plane, shown working on real code.

## What we have NOT shown (honest gaps)

- **No live cluster.** The engines are real; the Kubernetes cluster state is
  reproduced from a real integration fixture with resourceVersion/availability/
  readiness **authored**, because a live/kind cluster was infeasible in this
  environment. This is decision-grade evidence, not a live-production demonstration.
- **One operation family, one Deployment.** Not a breadth claim.
- **Reference-grade crypto.** ActionGate signing is an HMAC stand-in, not
  production key custody.
- **No production enforcement** is recommended or implied. Both layers remain
  shadow-only; the current runtime is authoritative.

## The honest one-line takeaway

*The governance stack's central claim — two independent layers, clean ownership,
deterministic "both must pass" composition, zero runtime impact — is validated on
real engines for a real Kubernetes action. Turning that into a product claim
requires a live cluster, more operation surfaces, and production crypto; those are
the next steps, not done yet.*

## What would move each verdict up

| verdict | today | to advance |
|---|---|---|
| live Kubernetes | `LIMITED` | run the same harness on a real control-plane cluster (one bootstrap) |
| product evidence | `PARTIALLY_VALIDATED` | + a second operation surface, real `availableReplicas`, real crypto |
| integrated composition | `SUPPORTED` | already strong; hold it as surfaces are added |
