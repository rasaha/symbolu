# Amendment — runtime-connector sequencing (RC-1) and the Kubernetes backend posture (KBE-1)

**Status:** ratified 2026-09-05 by the repository owner. Amends two scoping
records: `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_INTEGRATION_HUB_AMENDMENT.md`
(the roadmap-facing connector record) and
`ADR_CLOUD_SCALING_PHASE5D_BOUNDED_EXECUTION_SCOPING.md` (the ladder record).
Documentation only: no connector, no Kubernetes call, no credential, no LIVE
execution, no package, and no change to any port, test or manifest.

## Correction first — the record this amends contained a false claim

`ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_INTEGRATION_HUB_AMENDMENT.md` stated, as
`[V]`, that repo-wide there were "exactly two backend classes, the `ScalingBackend`
Protocol and `FakeScalingBackend`", and recorded a **Gap B** that "none exists".

**That is false, and Gap B does not exist.** A Kubernetes execution-target adapter
already ships:

| Fact | Where |
|---|---|
| `KubernetesScalingExecutor` implements the `ScalingBackend` interface against an injected `AppsV1Api`-like client `[V]` | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/k8s_executor.py:1-8`, `:28-47` |
| It is part of the curated public API `[V]` | `.../ugence_cloud_scaling_operations/__init__.py:45`, `:82` |
| It is tested by Ugence, in three suites `[V]` | `tests/packaging/test_packaging.py`, `tests/execution/test_execution.py`, `tests/execution/test_guard_coverage.py` |
| The real SDK is an **optional extra**, touched only if no client is injected and a live client is explicitly requested `[V]` | `pyproject.toml:42-44`; `k8s_executor.py:1-8` |
| It loads no credential at import and refuses without an injected client `[V]` | `k8s_executor.py:41-47`; the 5D record already stated this at `:32` |

The error's cause is worth naming, because it is the same one four earlier reviews
caught: the claim rested on `grep "class .*ScalingBackend"`, and this class is named
`…Executor`. **An absence established by one naming pattern is not an absence.**

The 5D record's own gap statement was accurate all along and is narrower than what
I wrote: *"no production backend **factory from a grant handle** exists in this
repository"* (`:61-64`, the claim at `:64`). The adapter exists; the factory does not.

## RC-1 — `CONTRACT_FIRST_NATIVE_THEN_EXTERNAL`

**Ruling.** Define one neutral **runtime-connector contract** and a **conformance
matrix** before any connector is built. Sequence the **native Agent Runtime
execution/lifecycle bridge first**, and **one external-runtime adapter second**.
The external product is selected only after a separate evidence-based audit or a
demonstrated design-partner need. **DBOS is durability and does not count as a
runtime connector. No connector may mint authority.**

**Why DBOS does not count** `[V]`. The durable-execution package already states the
boundary this ruling relies on: *"The engine owns scheduling and recovery. It owns
nothing else… The engine never decides whether a step may run"*
(`packages/integration/durable-execution/README.md:1-8`). An engine that drives
transitions without holding governance state is durability, not a bridge to the
execution and lifecycle contracts. The DBOS adapter in
`governed-review-service` (`README.md:24-25`) is the same shape.

**What is unchanged.** Gap A stands: **zero runtime connectors exist**, and IH-2's
ruling that the Prometheus signal connector and the GitHub ingress connector do not
count is untouched.

## KBE-1 — `SHIP_ADAPTER_CONSTRUCT_OUTSIDE`

**Ruling.** The Kubernetes `ScalingBackend` implementation **ships inside
`cloud-scaling-operations` and is tested by Ugence**. Deployment code constructs it
from a Credential Broker-resolved handle and an environment-specific client
**outside the repository**. The adapter **stores no credential**, and **LIVE remains
gated**: absent authority, credentials or configuration resolves to refusal or
dry-run.

**KBE-1 ratifies the posture that already exists rather than directing new work**
`[V]` — see the correction above. It also **closes an `[R]` I raised in error**: I
read 5D's *"an injected backend built by the deployment from the grant handle
outside this repository"* (`:57`, D-3) as contradicting a shipped adapter. It does
not. That clause governs **construction**, not authorship: the class ships inside,
the client and handle resolution stay outside. There was never a tension.

**What remains genuinely absent** `[G]`: the production backend **factory** from a
grant handle, which 5D already names as a surviving gap (`:61-64`) and which KBE-1
places **outside** this repository by ruling.

## Owner decisions required before implementation

Neither ruling authorizes code. These are the decisions that must be settled first,
and none is settled here.

### For RC-1 (the runtime-connector contract)

| # | Decision |
|---|---|
| RC-D1 | **What the contract carries.** Which canonical execution and lifecycle contracts a connector must bind to — the execution-reservation ports, Decision Authority `ExecutionRepository` conformance, RA-6's reassessment signal, the control-plane root's `AuditReference` — and which are mandatory versus optional. |
| RC-D2 | **Where the contract lives.** A new leaf in `governance-contracts`, or a package of its own. The prohibition on taking a reserved noun applies either way. |
| RC-D3 | **What "no connector may mint authority" forbids structurally**, not merely by convention — which types a connector may not construct, and which it may only receive. |
| RC-D4 | **What the native bridge's first slice is**, given that `agent-runtime-governance` already bridges a runtime to a *decision* and nothing bridges one to *execution and lifecycle*. |
| RC-D5 | **What evidence the external-product audit must produce** before any product is named. Naming one earlier is the failure this ruling exists to prevent. |

### For KBE-1 (the factory boundary)

| # | Decision |
|---|---|
| KBE-D1 | **What the deployment-side factory contract is** — the shape Ugence documents but does not ship, so a deployment can build a client from a broker-resolved handle without guessing. |
| KBE-D2 | **Whether "stores no credential" is asserted structurally**, as the sibling packages assert their prohibitions over the AST, or left to review. |
| KBE-D3 | **Whether 5D's LIVE precondition table is restated** now that the adapter's authorship is settled, since its current wording invited the misreading corrected above. |

## Failure matrices required before implementation

Each ruling turns on refusals, so each needs its failure behaviour enumerated and
tested before code lands. These are the matrices, not their contents.

**RC-1 — runtime-connector conformance matrix.** For each row, the required
outcome: connector present but unconfigured; governance boundary unreachable;
decision returned for a *different* proposal than the one submitted; execution
contract unavailable; lifecycle signal undeliverable; connector asked to act
without a decision; connector offered an authority-bearing value it must refuse.
The default for every unresolved row is **fail closed**, matching Agent Runtime's
existing posture that consequential transitions fail closed with no governance
adapter configured (`packages/runtime/agent-runtime/README.md:40-45`).

**KBE-1 — LIVE and credential failure matrix.** For each row, the required
resolution: no injected client; client injected but no grant; grant present but
reference-prefixed; grant expired mid-execution; cluster, namespace or resource
outside the authorization's allowlist; observed pre-state differing from the
expected pre-state; optimistic-concurrency conflict; audit sink unavailable;
readiness not required but absent. Every unresolved row resolves to **refusal or
dry-run, never `SIMULATION`**, per 5D D-3.

## What this creates

Nothing. No connector, no Kubernetes call, no credential, no LIVE execution, no
package, and no change to any port, test or manifest. RC-1 sequences work that does
not exist; KBE-1 ratifies a posture that already does, and corrects a record that
said otherwise.
