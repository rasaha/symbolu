# Agent Runtime Migration — Target Architecture (Deliverable 3)

The design of the new, additive `agent_runtime_migration/` package. It is built to a **frozen
ownership boundary**: the runtime **proposes**; the AI Control Plane **governs**.

Labels: `FACT` (frozen design decision).

## 1. Single responsibility
> **Convert a goal and observations into a governed execution request (CER), submit it to the AI
> Control Plane, consume the execution result, and continue reasoning.**

The runtime never returns its own authoritative `ALLOW`/`DENY`. Authorization, operational safety,
execution eligibility, replay protection, exact-action binding, approvals, policy enforcement, and
commit-time validation belong exclusively to the AI Control Plane (`cer_v0_3.control_plane`,
ActionGate, ACP — **frozen, imported, never modified**).

## 2. The loop (not a one-way pipeline)
```
Goal
 → Plan (decompose)
 → Select next action
 → Build CER                      (proposal/cer_builder)
 → Submit to AI Control Plane     (control_plane/client → frozen run_control_plane)
 → Receive governance result      (ActionGate verdict · ACP recommendation · composed eligibility)
 → If eligible: governed executor runs the tool  (control_plane/governed_executor)
 → Receive execution observation  (observation/result_ingestion)
 → Update memory                  (memory + observation/memory_update)
 → Reflect                        (reasoning/reflection)
 → Continue / stop / replan / request human input
```

## 3. Module ownership map
| Package | Owns | Must NOT contain |
|---|---|---|
| `contracts/` | typed Goal, Plan, Action, Observation, Result, errors | any decision logic |
| `runtime/` | lifecycle, state, cancellation, retry, budget, the loop driver | authoritative allow/deny |
| `planning/` | planner, decomposition, planning policies | tool authorization |
| `reasoning/` | reasoner, reflection, **advisory** uncertainty | any gate that lowers scrutiny or authorizes |
| `memory/` | working + episodic memory, persistence interface | governance state |
| `tools/` | registry, selection, invocation, **trusted** risk class (`local_tool_policy`) | model self-classification of risk |
| `workflow/` | workflow, step, scheduler, checkpoint | execution-token minting |
| `proposal/` | **native CER** builder/adapter, proposal evidence, identity bridge | mutation of a CER after evaluation |
| `control_plane/` | narrow client, governed executor, decision adapter, receipt | reimplementation of ActionGate/ACP |
| `observation/` | result ingestion, memory update | re-deciding eligibility |
| `tracing/` | events, trace, sink | governance authority |
| `compatibility/` | legacy adapter, warnings | duplicate governance authority; silent legacy execution |

## 4. The governance boundary (narrow interface)
`control_plane/client.py` submits a CER and returns a **structured, separated** decision:
`actiongate_authorization`, `acp_operational_safety`, `composed_eligibility`, `required_next_step`,
`execution_reference` (only when eligible), and `reason/trace references`. It is a thin wrapper over
the frozen `cer_v0_3.control_plane.run_control_plane` — no policy, no re-decision.

`control_plane/governed_executor.py` is the **only** path that runs a governed consequential tool.
It executes iff the decision is `eligible` **and** carries a control-plane `execution_reference`; it
refuses otherwise. There is no direct tool call around it in governed mode.

The runtime **may** replan, request evidence, request human input, wait, stop, or reflect. It **may
not** override ActionGate/ACP, treat an ACP hold as authorization, treat an ActionGate allow as
operational safety, mint an execution token, or execute around the governed executor.

## 5. Risk-tiered execution paths
- **Governed consequential tools** (Kubernetes mutation, database mutation, financial/write/delete,
  privileged): **must** pass CER → AI Control Plane → governed executor. Supported profiles are the
  frozen CER profiles (`kubernetes.scale.v1`, `kubernetes.rollout.v1`, `database.mutation.v1`).
- **Low-risk local/read-only tools** (formatting, deterministic parsing, read-only retrieval where
  policy explicitly permits): may run on a **local fast path** with no CER. The **risk class comes
  from the trusted tool registry / policy profile — never from the model.** Every fast path is
  documented in `AGENT_RUNTIME_CONTROL_PLANE_BOUNDARY.md` with why it does not bypass enterprise
  governance (it performs no consequential actuation).

## 6. CER integration (native)
The runtime emits CER using the **frozen** `cer_v0_3` contract (envelope + identity + control
plane). It: emits CER before governed execution; keeps runtime provenance **outside** the CER action
identity (v2 profile excludes it); binds the CER to the exact tool/target/arguments/state/principal/
policy; rejects incomplete/invalid CERs before submission; never mutates a CER after evaluation; and
generates a new identity after any material change. Native production (no adapter translation step)
is the runtime's differentiator.

## 7. Research isolation
No CG / JEPA / vritti / sovereign / entropy **governance** module is imported by the production
runtime. Uncertainty may be attached as **advisory evidence** only — it may raise scrutiny, never
lower it or authorize. A forbidden-import test enforces this.

## 8. Rollback
The legacy `agentic/agentic_framework/` package is **untouched** and remains the rollback source. The
migration package is additive; nothing is deleted or moved.
