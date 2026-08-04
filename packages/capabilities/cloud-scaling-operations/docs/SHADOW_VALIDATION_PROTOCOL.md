# Read-Only Shadow Validation Protocol

This protocol governs a bounded, read-only shadow validation of the Cloud Scaling
Operations package against a **genuine non-production** Kubernetes environment. This
repository currently ships only the **environment-independent harness** that implements
the protocol; the real-environment run is a separate, resource-gated task.

## Phases

1. **Repository state gate** — confirm the packaging baseline (PR #1333 merge
   `9d8cc0e5…`) is an ancestor of the default tip; advisory stays advisory-only;
   operations stays controlled-execution capable and dry-run-by-default.
2. **External environment resource gate** — a real, explicitly-configured,
   non-production cluster with read-only credentials must be supplied. If none is
   available the run stops with `CLOUD_SCALING_OPERATIONS_READ_ONLY_SHADOW_RESOURCE_BLOCKED`
   and is **never** substituted with mocks.
3. **Explicit config + injected client** — no auto-discovery of kubeconfig/context/creds.
4. **Read-only observation** — allowlisted targets only, through the transport barrier.
5. **Advisory recommendation → policy/safety → local shadow authorization → proposed
   decision → audit** — every decision is proposed-only and never executed.
6. **Stale-state, HPA-interaction, authorization, network-failure** evaluation.
7. **Sanitized evidence** + integrity verification.

## Authority boundary (non-negotiable)

Allowed: real reads (`GET/LIST/WATCH`), read-only metrics, shadow recommendations,
local authorization validation, proposed plans/receipts, audit generation.

Prohibited: any `POST/PUT/PATCH/DELETE/DELETECOLLECTION`, scale-subresource mutation,
HPA/Deployment/StatefulSet mutation, ArgoCD sync, admission-webhook or metrics-listener
deployment, live orchestrator/live execution mode, credential creation, publication.

No Kubernetes or ArgoCD write request may reach a remote endpoint. A client-side denial
is acceptable only when the request is blocked **before** transmission and recorded as a
local safety test.

## Verdicts

- `CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_VERIFIED` — harness implemented and verified
  (this phase). Never implies real validation.
- `CLOUD_SCALING_OPERATIONS_READ_ONLY_SHADOW_VALIDATED` — reserved for a genuine
  real-environment run; **not** usable in the harness-only phase.
- `..._RESOURCE_BLOCKED` — no genuine non-production cluster / read-only access available.
