# CER V0.3 — Publication-Readiness Checklist (Deliverable 18)

The frozen public-repository criteria (preregistration §13), each with its evidence and
status. **Public-repository readiness ≠ standards-body acceptance or industry adoption** —
no such claim is made.

Labels: `FACT`.

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | Two independent conformant implementations | reference + clean-room; AST boundary test; differential 73/73 payload+bytes+digest | ✅ |
| 2 | No identity-affecting ambiguity | differential identity-affecting differences = 0; errata audit (15 classes) = 0 | ✅ |
| 3 | Two materially different domains | Kubernetes {scale, rollout} + database {mutation} | ✅ |
| 4 | No cross-profile / cross-domain collision | `cross_profile_collisions = 0`; DB digest ≠ K8s digests | ✅ |
| 5 | Complete versioned conformance vectors | V0.1 `3ec7f36d`, V0.2 `3dc9f372` (unchanged), DB `06696792`; differential (77) + cross-domain (29) records | ✅ |
| 6 | No runtime-specific Control Plane branch | `ownership_no_runtime_switch = true`; 0 runtime tokens in frozen AG/ACP | ✅ |
| 7 | No unresolved high-severity security issue | all 15 §11 invariants hold; secrets never enter identity | ✅ |
| 8 | Backward compatibility with V0.1/V0.2 | frozen fingerprints unchanged; V0.2 base digests preserved; 284 regression tests pass | ✅ |

## Frozen-core impact
`FACT`. ActionGate **0 lines**, ACP core **0 lines**, CER V0.1/V0.2 **0 lines**, Context
Minimization **0 lines**. New code is additive (`cer_v0_3/`, 3,068 py LOC).

## Verdict
`FACT`. **`CER_V0_3_READY_FOR_PUBLIC_REPOSITORY`** — all eight criteria met. The CER
specification, JSON Schemas, conformance vectors, differential runner, and two reference
implementations are internally ready to be published as a public repository draft for
external review.

## Explicit non-claims
`FACT`. This milestone does **not** claim: standards-body acceptance; industry adoption;
production-grade signing custody; live-cluster or live-database operation; coverage of
domains beyond Kubernetes + database; or that ActionGate/ACP are authoritative in production.
Publication here means "ready to open for external review", not "adopted".

## Pre-publication residual actions (out of this milestone's scope)
`INTERPRETATION`. Before an actual public push: a third independent implementation (different
language); a third actuation domain; a live-cluster/live-DB ACP path; production asymmetric
signing; and a licensing/governance file. None is required for the V0.3 internal verdict; all
are recommended before external release.
