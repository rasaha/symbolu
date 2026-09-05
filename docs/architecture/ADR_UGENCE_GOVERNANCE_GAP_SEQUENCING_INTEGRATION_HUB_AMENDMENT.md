# Amendment — the wave 3 "enterprise integration hub" row, closed and decomposed

**Status:** ratified 2026-09-05 by the repository owner. Amends the disposition of
one row in `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (`:59`).
Documentation only: it creates no package, adapter, credential, network call or
implementation, and amends no package ADR, port, test or manifest.

## CORRECTION — 2026-09-05

**This record originally claimed, as `[V]`, that no Kubernetes execution-target
adapter existed. That claim was false and is corrected below.** It is not erased:
the error and its cause are recorded because a ratification record whose
corrections are invisible is worth less than one that shows them.

`KubernetesScalingExecutor` already ships, is exported from the curated public API,
and is tested by Ugence. The original claim rested on a single naming-pattern
search — `grep "class .*ScalingBackend"` — and this class is named `…Executor`, so
the search could not have found it. **An absence established by one naming pattern
is not an absence.**

What changed as a result: §2's inventory now lists the shipped adapter; **Gap B is
removed** — it was never a gap; and the narrower gap the ladder record had stated
accurately all along takes its place. Only **Gap A** remains outstanding in this
record. Ratified in `ADR_UGENCE_RUNTIME_CONNECTOR_AND_KUBERNETES_BACKEND_AMENDMENT.md`
(rulings RC-1 and KBE-1, PR #1624).

## The two rulings

**IH-1 — `INTEGRATION_HUB_FOLDED_TO_EXISTING_SEAMS`.** No integration-hub package
or ADR is created. The ~~missing~~ Kubernetes `ScalingBackend` is an
**execution-target adapter** owned by `cloud-scaling-operations` and sequenced
through the cloud-scaling ladder.

> **Annotation, 2026-09-05.** The ruling is preserved as ratified, including the
> word "missing", because a ruling is not rewritten after the fact. But that word
> rested on a premise this record supplied and got wrong: the adapter was **not**
> missing — `KubernetesScalingExecutor` already shipped, and the CORRECTION note
> above explains how the error was made. **IH-1's disposition is unaffected**:
> ownership by `cloud-scaling-operations` and sequencing through the ladder are
> exactly right, and are what the ruling turns on. What is missing is narrower —
> the deployment-side factory (§3) — and KBE-1 places that outside the repository.

**IH-2 — `SIGNAL_AND_WEBHOOK_DO_NOT_COUNT_AS_RUNTIME_CONNECTORS`.** The Prometheus
client is a **signal/evidence-source connector**; the GitHub webhook receiver is
**source-system ingress**. Neither bridges an agent runtime to Ugence's canonical
execution and lifecycle contracts, so **neither satisfies** roadmap §4's
requirement for two runtime connectors.

IH-2 settles a question this record previously left open, and settles it against
the reading that would have counted v1's runtime-connector line as already met. It
is not met.

## 1 — Definitions

Roadmap §3 names "runtime adapters + execution-target adapters" in one line
(`UGENCE_PRODUCTIZATION_ROADMAP.md:87`) and defines neither `[G]`. These four terms
are defined here so the inventory below can be checked rather than argued.

| Term | Definition | Direction | Test that distinguishes it |
|---|---|---|---|
| **Runtime connector** | Bridges an **agent runtime** to Ugence's canonical **execution and lifecycle contracts**, so that a runtime's consequential transitions are governed by, and recorded against, those contracts. | Bidirectional: proposal out, decision back | Does a runtime's *own* execution path traverse it? |
| **Signal / evidence-source connector** | Ingests observations that may *trigger* reassessment or supply evidence. It carries no authority and no execution. | Inbound | Could it be removed and leave execution still governed? If yes, it is a signal connector. |
| **Source-system ingress connector** | Accepts events from an external system of record and normalizes them into neutral records. | Inbound | Does it originate outside and terminate in a record, never a decision? |
| **Execution-target adapter** | Turns an already-authorized, already-reserved, already-credentialed action into one bounded change against a real infrastructure target. | Outbound, terminal | Is it the last thing before the world changes? |

The load-bearing distinction is **not** inbound versus outbound. It is whether the
thing sits on a runtime's execution path. A signal connector may be busy and
important and still be removable without ungoverning anything.

## 2 — The existing inventory, classified

| What ships | Class under §1 | Evidence |
|---|---|---|
| Prometheus HTTP poller (`/api/v1/query`) | **Signal / evidence-source** `[V]` | `packages/capabilities/cloud-scaling-controller/src/ugence_cloud_scaling_controller/signals/prometheus.py:1-8` |
| GitHub webhook verifier + normalizer | **Source-system ingress** `[V]` — and payload-driven: no outbound call exists in it | `products/code-governance/src/ugence_code_governance/github/` (`__init__.py:1-6`, `webhook.py`, `normalizer.py`) |
| `KubernetesScalingExecutor` | **Execution-target adapter — shipped and tested** `[V]`. Implements `ScalingBackend` against an injected `AppsV1Api`-like client; exported from the curated API; the real SDK is an optional extra, touched only if no client is injected and a live one is explicitly requested; loads no credential at import and refuses without a client | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/k8s_executor.py:1-8`, `:28-47`; `__init__.py:45`, `:82`; `pyproject.toml:42-44`; tested in `tests/packaging/test_packaging.py`, `tests/execution/test_execution.py`, `tests/execution/test_guard_coverage.py` |
| `FakeScalingBackend` | Deterministic fake driving SIMULATION and tests `[V]` | `.../executors.py:50` |
| `ScalingBackend` Protocol | The **seam** an execution-target adapter implements `[V]` | ibid. `:39` |
| *(nothing)* | **Runtime connector** `[G]` | — |

~~Repo-wide there are exactly two backend classes, the Protocol and the fake.~~
**Corrected 2026-09-05:** there are three — the Protocol, the fake, and
`KubernetesScalingExecutor`. In `packages/`, `kubernetes` appears almost only inside the **21** boundary tests
that forbid importing it `[V]`
(`grep -rl -i kubernetes --include=test_import_boundary.py --include=test_boundaries.py packages/`).

## 3 — Outstanding v1 gaps, counted separately

Roadmap §4 puts three things in v1 (`:98`, `:100`). **One product gap remains in
this record, not two** — the second was an error, corrected 2026-09-05:

| Gap | v1 requirement | Status |
|---|---|---|
| **Gap A — runtime connectors** | "Two runtime connectors" (`:98`) | **Zero exist** `[G]`. IH-2 rules that neither shipped connector counts. **The one outstanding product gap in this record.** |
| ~~Gap B — execution-target adapter~~ | "One governed execution-target connector (Kubernetes)" (`:100`) | **Withdrawn.** The adapter ships and is tested — see §2. This was never a gap. |

**What is genuinely absent, and it is narrower** `[G]`: **no deployment-side
production factory constructs the adapter from a Credential Broker grant handle.**
The ladder record stated this accurately all along — *"no production backend
factory from a grant handle exists in this repository"*
(`ADR_CLOUD_SCALING_PHASE5D_BOUNDED_EXECUTION_SCOPING.md:61-64`) — and it is a
narrower thing than the missing adapter this record wrongly asserted.

**KBE-1 places that construction outside the repository.** Ugence owns and tests
the adapter code; deployment code builds it from a broker-resolved handle and an
environment-specific client, outside this repository. The adapter stores no
credential, and LIVE remains gated: absent authority, credentials or configuration
resolves to refusal or dry-run. See
`ADR_UGENCE_RUNTIME_CONNECTOR_AND_KUBERNETES_BACKEND_AMENDMENT.md` (PR #1624).

Deferred and **not** gaps: additional systems-of-record connectors (ATS, HRIS,
claims, finance) and multi-cloud targets beyond Kubernetes (`:95`, `:98`).

## 4 — Candidate seams for the two runtime connectors

Named as **seams a runtime connector would land on**, not as products to connect.
No product is selected here and none should be inferred.

| Candidate seam | Why it is a candidate | Where |
|---|---|---|
| Agent Runtime's **governance boundary** | The runtime already "constructs an immutable proposal and asks an external, neutral governance boundary whether that exact proposal may proceed — and it obeys the answer", failing closed when unconfigured `[V]` | `packages/runtime/agent-runtime/README.md:40-45` |
| `agent-runtime-governance`'s **projection** | Already the fourth hook "a deployment actually uses", projecting a `GovernedExecutionDecision` onto the runtime's `GovernanceEvaluation` — the *governance* half of the bridge exists `[V]` | `packages/integration/agent-runtime-governance/README.md:1-12` |
| **Execution-reservation ports** | `ClearanceReceiptRepository`, `ExecutionReservationPort`, `PriorConsumptionSource`, and Decision Authority `ExecutionRepository` conformance — the canonical execution contracts a connector must record against `[V]` | `packages/integration/execution-reservation/README.md` (port table) |
| **RA-6 reassessment signal** | The lifecycle side: the neutral, authority-free payload an observer may emit `[V]` | `packages/risk_authority/src/risk_authority/domain/authority_signal.py` |
| **Control-plane root audit ledger** | Where a connector's records acquire an `AuditReference` `[V]` | `packages/integration/control-plane-root/` |

**`[I]` The governance half of a runtime connector already exists and the execution
half does not.** `agent-runtime-governance` bridges a runtime to a *decision*;
nothing bridges one to the *execution and lifecycle* contracts. That asymmetry is
the most likely shape of Gap A, and is offered as an observation for whoever scopes
it — not as a scoping decision.

## 5 — Kubernetes `ScalingBackend`: sequencing moved to the ladder

**Corrected 2026-09-05.** This section originally sequenced "Gap B" into the ladder
as work to be done. The adapter already ships (§2), so what moves to the ladder is
the **remaining factory gap**, not the adapter. IH-1's disposition is unchanged —
the Kubernetes execution-target adapter is owned by `cloud-scaling-operations` and
sequenced by the ladder alongside 5C, 5D and 5X, and never by wave 3. It is **gated by two decisions already ratified there**, and neither is
reopened here:

1. **The credential decision (5X).** "A grant is a handle, not execution"
   (`cloud-scaling-credential-broker/README.md:7-8`). An adapter consumes a grant;
   it never brokers or holds one.
2. **The LIVE-execution decision (5D).** `LIVE` survives only under a fully proven
   posture — production Risk Authority application, production-mode execution
   ledger, production-authoritative grant store and broker, a non-reference grant
   handle, readiness required — and **any absence resolves `LIVE` to `dry_run`**
   (`cloud-scaling-bounded-execution/README.md:39-51`).

**~~`[R]` One posture question this raises rather than answers.~~ Withdrawn
2026-09-05 — the question rested on the same error.** I read the LIVE table's
*"built by the deployment from the grant handle **outside this repository**"*
(`cloud-scaling-bounded-execution/README.md:47`) as contradicting a shipped
adapter, and concluded that sequencing one into the ladder would move it inside.
It would not: that clause governs **construction, not authorship**. The class ships
inside and is tested by Ugence; the client and the handle resolution stay outside.
KBE-1 ratifies exactly that split, so there was never a tension to resolve.

## What this creates

Nothing. No package, no adapter, no credential, no network call, no implementation,
and no change to any package ADR, port, test or manifest. Closing the row **removes
nothing and unblocks nothing**: the two runtime connectors remain unbuilt, and the
deployment-side factory remains absent by ruling rather than by omission. What
changes is only where each is sequenced and what each is called.

*(Corrected 2026-09-05: this paragraph previously said "the Kubernetes backend
remains unwritten". It was written; see the CORRECTION note above.)*

Wave 3 is complete: G4's contracts, the incident-response package, and the
control-plane root, all merged.
