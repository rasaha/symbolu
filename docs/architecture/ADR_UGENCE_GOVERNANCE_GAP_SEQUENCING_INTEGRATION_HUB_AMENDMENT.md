# Amendment — the wave 3 "enterprise integration hub" row, closed and decomposed

**Status:** ratified 2026-09-05 by the repository owner. Amends the disposition of
one row in `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (`:59`).
Documentation only: it creates no package, adapter, credential, network call or
implementation, and amends no package ADR, port, test or manifest.

## The two rulings

**IH-1 — `INTEGRATION_HUB_FOLDED_TO_EXISTING_SEAMS`.** No integration-hub package
or ADR is created. The missing Kubernetes `ScalingBackend` is an **execution-target
adapter** owned by `cloud-scaling-operations` and sequenced through the
cloud-scaling ladder.

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
| `FakeScalingBackend` | **Execution-target adapter, fake only** `[V]` | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/executors.py:50` |
| `ScalingBackend` Protocol | The **seam** an execution-target adapter implements `[V]` | ibid. `:39` |
| *(nothing)* | **Runtime connector** `[G]` | — |

Repo-wide there are exactly two backend classes, the Protocol and the fake `[V]`.
In `packages/`, `kubernetes` appears almost only inside the **21** boundary tests
that forbid importing it `[V]`
(`grep -rl -i kubernetes --include=test_import_boundary.py --include=test_boundaries.py packages/`).

## 3 — Outstanding v1 gaps, counted separately

Roadmap §4 puts three things in v1 (`:98`, `:100`). They are **two distinct gaps**,
not one, and closing either does not close the other:

| Gap | v1 requirement | Status |
|---|---|---|
| **Gap A — runtime connectors** | "Two runtime connectors" (`:98`) | **Zero exist** `[G]`. IH-2 rules that neither shipped connector counts. |
| **Gap B — execution-target adapter** | "One governed execution-target connector (Kubernetes)" (`:100`) | **None exists** `[G]`; only the Protocol and a fake. |

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

Per IH-1, Gap B leaves wave 3 and joins the cloud-scaling ladder alongside 5C, 5D
and 5X. It is **gated by two decisions already ratified there**, and neither is
reopened here:

1. **The credential decision (5X).** "A grant is a handle, not execution"
   (`cloud-scaling-credential-broker/README.md:7-8`). An adapter consumes a grant;
   it never brokers or holds one.
2. **The LIVE-execution decision (5D).** `LIVE` survives only under a fully proven
   posture — production Risk Authority application, production-mode execution
   ledger, production-authoritative grant store and broker, a non-reference grant
   handle, readiness required — and **any absence resolves `LIVE` to `dry_run`**
   (`cloud-scaling-bounded-execution/README.md:39-51`).

**`[R]` One posture question this raises rather than answers.** That same LIVE
table currently lists the injected backend as *"built by the deployment from the
grant handle **outside this repository**"* `[V]`
(`cloud-scaling-bounded-execution/README.md:47`). Sequencing a Kubernetes backend
*into* the ladder moves it inside. Whether that is intended — a shipped adapter
rather than a deployment-supplied one — is a ladder decision for its own scoping
record, and this amendment does not presume it.

## What this creates

Nothing. No package, no adapter, no credential, no network call, no implementation,
and no change to any package ADR, port, test or manifest. Closing the row **removes
nothing and unblocks nothing**: the Kubernetes backend remains unwritten and the two
runtime connectors remain unbuilt. What changes is only where each is sequenced and
what each is called.

Wave 3 is complete: G4's contracts, the incident-response package, and the
control-plane root, all merged.
