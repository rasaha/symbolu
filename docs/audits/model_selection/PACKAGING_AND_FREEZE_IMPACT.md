# Model Selection — Packaging & Freeze/API Impact

Section 16–17. Could a future canonical package exist, and what is the freeze/API blast radius?

## 1. Proposed (future) canonical shape — DO NOT CREATE NOW

| Item | Proposed value |
|---|---|
| Package path | `packages/capabilities/model-selection/` |
| Canonical namespace | `ugence_model_selection` |
| Distribution | `ugence-model-selection` |

These are recorded as targets only; **no package, namespace, or distribution is created in this phase.**

## 2. Dependency fitness for an independent package

The capability should depend only on: Python stdlib, approved third-party libs, Governance Contracts
(where justified), provider-metadata interfaces (where justified).

| Requirement | Current reality | Fit |
|---|---|---|
| Depends only on stdlib / approved libs | `execution_gate` and `model_selection_experiment` import **nothing** external; `reconciliation` imports only `experiment`; `pilot` uses stdlib `urllib` + lazy `boto3` | ✅ excellent (core is dependency-free) |
| Must NOT require AI Control Plane / Orchestrator | it does not; the control plane imports *it* | ✅ |
| Must NOT require applications / domains | it does not | ✅ |
| Must NOT require Hybrid LLM / LLM Steering | it does not | ✅ |
| Must NOT require concrete providers | core does not; only the pilot's `provider.py` does (execution, to be left behind) | ✅ (with pilot execution excluded) |
| Must NOT require console / research harnesses | core does not; research harnesses are separable | ✅ (with research excluded) |
| Provider adapters / routers depend on MSP, not the reverse | consumers (`control_plane`, shadows, `governed_inference_pilot`) depend on `execution_gate`; correct direction | ✅ no dependency inversion to unwind |

**Dependency inversions found:** none. `execution_gate` is already a dependency-free leaf, and
`ExecutableRegistry`/`ModelRecord` already act as the provider-metadata port. A migration needs no new
port abstraction on dependency grounds.

## 3. What blocks "package it independently *now*"

Not dependencies — **fragmentation and duplication**:

1. The capability is spread across **4 directories + a 5th re-host** (`governed_inference_pilot/adapters`).
2. The two-stage core is **duplicated 4–5×** with divergent I/O shapes (dataclass vs dict) and cost/latency
   numerics (see `DUPLICATION_MATRIX.md`).
3. Product logic is **interleaved with research evaluation** in every directory (simulator, baselines,
   metrics, harness) and with **provider execution** in the pilot (see `ARTIFACT_CLASSIFICATION.md`).

A canonical package therefore requires a *consolidation + product/research separation* step first; it is
not a lift-and-shift of a single existing directory.

## 4. Freeze / API-snapshot impact

| Question | Answer |
|---|---|
| Is Model Selection a platform-frozen core tree? | **No.** `platform_freeze/version.py` `CORE_TREES = (decision_governance, governance_providers, actiongate_provider, tap_provider)` |
| Does it have a platform public-API snapshot? | **No.** `PUBLIC_API_MODULES` lists only the four `*.api` surfaces above |
| Component version entry? | **No.** `COMPONENT_VERSIONS` covers only decision-governance + the three provider dists |
| Behaviour-tree freeze entry? | **No.** `BEHAVIOUR_TREES` = enterprise_validation_pilot, comparative_governance_benchmark, provider_heterogeneity_validation |
| Would a future migration re-baseline the platform freeze? | **No platform freeze change is required** to move Model Selection; the platform-freeze verifier is invariant to it |
| Local freeze to preserve | `execution_gate/frozen/replay_v1` — a **self-contained** replay determinism guard (13 artifacts, aggregate `8b05b2da798a6222`, verifier PASS). It would move **with** the code and must keep verifying byte-identically |

**Conclusion:** Model Selection sits **entirely outside** the platform freeze and public-API snapshot
surface. A future canonical migration has **zero platform-freeze / API-snapshot impact** — the only
freeze obligation is to carry `execution_gate`'s own replay freeze along and keep it green. This is a
materially *lower*-risk migration than the earlier governance migrations, which each touched frozen core
trees and public-API snapshots.

## 5. Product & commercial boundary (Section 17)

Customer-facing problem solved (per `MODEL_SELECTION_POLICY_VC_BRIEF.md`, constrained to repo evidence):

> Ensure an enterprise AI request is assigned only to an **approved** model/provider that satisfies
> declared cost, quality, latency, privacy, jurisdiction, and risk constraints — with a deterministic,
> replayable selection record.

Distinct from: generic LLM gateways, cheapest-model routing, load balancing, provider failover, prompt
routing, multi-agent orchestration, model benchmarking, model training, AI-coding adjudication.

Legitimate customer-facing outputs (all present in code): selection record, policy/disqualification
explanation (`eliminated` with reason+constraint+provenance), cost/quality/latency trade-off
(`components`), `NO_ELIGIBLE_MODEL` escalation, model/provider audit trail (deterministic + version
stamped).

**Wording discipline (from the reconciliation doc):** use *"selects an eligible model using calibrated
quality, cost, latency, and policy evidence"* with an *optional* sufficiency-constrained mode described
as **predicted**, never **guaranteed**. Do not claim "always the cheapest sufficient model," real-provider
validation, or calibrated production routing — none is supported (evidence is synthetic; pilot is
credential-blocked). No marketing claim in these deliverables exceeds repository evidence.
