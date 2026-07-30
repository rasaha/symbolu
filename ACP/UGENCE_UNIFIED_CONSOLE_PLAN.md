# Ugence AI Control Plane — Unified Console Plan

*Consolidating the nine Specialized-AI-Systems and AI-Control-Plane modules
(excluding the two AI-Infrastructure modules, KVPro and the Cloud Scaling
Controller) behind one governance surface, driven from a unified web console.*

Status of this document: **living plan.** Phase 0 and a Phase-1 vertical slice
are **built and merged** on `claude/unified-web-interface-en7t8w`
(`ugence_console_api/` + `apps/console/`). The remaining phases are specified but
not yet built. The exact request/response contracts for the Phase-1 endpoints are
in the companion spec `ACP/PHASE1_GOVERNED_LOOP_DTO_CONTRACT.md`.

---

## 1. What we are building & why it is the right gap

A **unified web console + a dedicated backend service** over the nine Layer-1/
Layer-2 modules. This is not net-new product surface — `UGENCE_PRODUCTIZATION_
ROADMAP.md` lists it as integration gap **#4 ("Unified control surface")** and
**#5 ("Standard external APIs & canonical contracts")**. The console *is* the
"connective tissue that makes the modules one operable product."

Design decisions (fixed):

- **Separate frontend app** — `apps/console/`, decoupled from the Symbol-U
  research/marketing UI in `frontend/`.
- **New dedicated backend service** — `ugence_console_api/`, separate from the
  Symbol-U research `symbolu.service.api_server`.
- **Excludes KVPro and the Cloud Scaling Controller** by design — infrastructure
  never governs.

## 2. Two facts that shape everything

1. **The modules are in-process libraries, not services.** Only the Agent Runtime
   ships real HTTP today (`agentic/agentic_framework/governance_api.py`). The four
   Layer-2 governance packages (`actiongate_provider`, `tap_provider`,
   `governance_providers`, `decision_governance`) are clean **frozen-API** contract
   libraries whose `Remote*` clients only *simulate* transport. The console backend
   is therefore the first real HTTP surface for them — exactly the roadmap's
   "canonical contract layer" work.
2. **Two maturity tiers among the nine.** Layer-2 governance modules are
   `evaluate()/authorize()` libraries with typed requests/verdicts — cheap and
   high-value to expose. Layer-1 systems (Hybrid LLM, Steering Controller,
   Autonomous Runtime) are research/experiment packages with no clean callable
   service and, for Hybrid LLM, GPU/model-weight cost. **v1 treats Layer-1 as
   read-only substrate/status panels, not live interactive endpoints.**

## 3. Console information architecture

Navigation follows the framing in `UGENCE_AI_CONTROL_PLANE_FIRST_LOOK.md`: the
**six customer-facing capabilities**, the **Propose → Verify → Authorize →
Execute → Record** lifecycle, and a global **Shadow / Recommendation /
Enforcement** mode. The nine modules map onto the six capabilities:

| # | Console capability | Modules behind it | Primary code entry point |
|---|---|---|---|
| 1 | **Agent Gateway** (what enters) | Context Minimization | `actiongate_context_ablation/compressor.py::structural_compress()` |
| 2 | **Truth & Evidence** (is a claim supported) | Truth Assurance Platform *(emerging)* | `tap_provider/provider.py::TAPProvider.evaluate(AssertionGovernanceRequest)` |
| 3 | **Policy & Decision Authority** | Model Selection & Governed Inference + Decision Governance | `execution_gate/gate.py::ExecutionGate.evaluate()`; `execution_gate/policy.py::ModelPolicy.select()`; `decision_governance.api.services` |
| 4 | **Action Control** (may THIS action run + safe now) | ActionGate + Autonomous Control Plane | `governance_providers/adapters/action_to_control_plane.py::authorize(action_request, cer)`; ACP `authorization.py::ReferenceControlAuthorizer.authorize()` |
| 5 | **Governed Runtime** | Agent Runtime + Autonomous Runtime *(+ Hybrid LLM, Steering Controller as substrate)* | `agentic_framework/agent.py::AgenticLLMWrapper.run_with_trace()`; existing `governance_api.py` |
| 6 | **Audit & Reconstruction** | Cross-cutting | `decision_governance.api.audit`, keyed by **CER `cer_id` / `correlation_id`** |

**The join key is the CER.** The console threads one `correlation_id` /
`cer_id` across capabilities 2 → 3 → 4 → 6 — what makes it auditable end-to-end.

## 4. Backend service design (`ugence_console_api/`)

- Separate `create_app()` FastAPI factory + own process; adds the CORS middleware
  the research server lacks.
- **Layered like the modules:** thin routers → a `capabilities/` adapter layer
  that imports **only the frozen `*.api.*` surfaces** (staying inside the
  versioning guarantees in `platform/PLATFORM_FREEZE_V1.json`; anything else is a
  MAJOR-class break) → the module libraries in-process.
- **Canonical DTOs** (Pydantic) per capability, mapping 1:1 to module types. These
  are the stable public contract (see the companion spec).
- **Deployment modes as a first-class field:** every module call is
  evaluation-only, so **Shadow is native** (evaluate + record, change nothing);
  **Recommendation** surfaces findings/escalations; **Enforcement** acts on the
  verdict. Per-control configurable.
- **Fail-safe adapters:** a module that cannot import degrades to "unavailable"
  and is reported as such, never crashing the service.

### Endpoint set

```
GET  /health                            service + per-module availability
GET  /v1/modules                        the nine modules + maturity + wiring
GET  /v1/scenarios                      sample K8s shadow workflows
POST /v1/gateway/minimize               Context Minimization
POST /v1/assertions/evaluate            Truth Assurance Platform
POST /v1/actions/authorize              ActionGate (CER-bound)
POST /v1/actions/clear                  Autonomous Control Plane (operational safety)
POST /v1/governed-loop/shadow           full governed loop over a supplied request
POST /v1/governed-loop/scenario/{id}    full governed loop over a sample scenario
GET  /v1/audit                          list recorded correlation ids
GET  /v1/audit/{correlation_id}         reconstruct the decision chain
```

## 5. Frontend console (`apps/console/`)

- Vite + React 18 + TypeScript + Tailwind + Zustand + lucide-react (mirrors
  `frontend/`), decoupled from the research UI.
- **Views:** Governed Loop (live shadow trace per stage), Modules registry
  (maturity + wiring + availability), Audit reconstruction. A global
  Shadow/Recommendation/Enforcement switch is the next addition.
- **Honesty by design:** each module carries a maturity badge straight from the
  platform evidence discipline — TAP labelled *emerging*, Layer-1 labelled
  *research/substrate*.

## 6. The governed loop (the product)

```
Gateway   -> Context Minimization      what may enter
Verify    -> Truth Assurance Platform  is the assertion supported
Authorize -> ActionGate                may THIS exact action execute (CER-bound)
Clear     -> Autonomous Control Plane  is it operationally safe right now
Record    -> Audit                     reconstructable decision chain
```

Deployment mode governs consequence, not evaluation. In **shadow** the loop
evaluates and records but changes nothing; `would_execute` still reports what
enforcement would have done. **Gates are non-compensatory:** a clean
authorization cannot buy back an operational HOLD or an unsupported assertion.

## 7. Phasing

| Phase | Deliverable | Status |
|---|---|---|
| **0** | Backend scaffold: `create_app()`, DTOs, `/health`, `/v1/modules` | **Built** |
| **1** | Governed-loop core: Context Minimization + TAP + ActionGate + operational clearance + audit reconstruction, threaded by CER; one end-to-end shadow workflow on the Kubernetes wedge (3 scenarios) + tests; console with Governed-Loop / Modules / Audit views | **Built** |
| **2** | Policy & Decision Authority in the loop: Model Selection (`ExecutionGate.evaluate` + `ModelPolicy.select`) and the Decision Governance kernel case decision | Planned |
| **3** | Governed Runtime: proxy the Agent Runtime `governance_api`; Autonomous Runtime / Hybrid LLM / Steering as read-only panels | Planned |
| **4** | Cross-cutting: Shadow/Recommendation/Enforcement toggle, findings/review queue, durable tamper-evident audit (roadmap gap #3) | Planned |

## 8. Primary workflow — the wedge

The prototype anchors on the platform's primary commercial wedge (First Look §3;
Roadmap §4): an enterprise **Kubernetes / infrastructure agent** proposing a
high-consequence write, run through the governed loop in **shadow**. Three
scenarios exercise the non-compensatory gates:

- **Clean rollout restart** → ADMITTED · SUPPORTED · AUTHORIZED · CLEAR → *would ALLOW*.
- **Delete during change-freeze** → AUTHORIZED but **HOLD** → *would BLOCK*
  (authorized ≠ safe now).
- **Scale-up on an unsupported claim** → TAP **INDETERMINATE** → *would BLOCK*
  (caught before reliance).

## 9. Risks / decisions

- **Frozen APIs:** consume `actiongate_provider.api`, `tap_provider.api`,
  `governance_providers.api`, `decision_governance.api` only — never internal
  modules — or trip the MAJOR change class.
- **Layer-1 is not a live service in v1** (no clean callable, GPU cost). Live
  Hybrid-LLM inference in the console is a separate, heavier workstream.
- **Persistence:** the in-memory audit store demonstrates the loop but is roadmap
  gap #3 (durable, tamper-evident) before any pilot.
- **Physical vs digital ACP:** the robotics `autonomous_control_plane` clears
  robot actions against world state; the console ships its **digital sibling** —
  the same discipline applied to enterprise infrastructure signals — as the
  platform doc frames the two runtimes ("same discipline, two worlds").
- **Two apps, two backends** now run: the research server (`:8000`) and the
  console API (`:8090`). Deploy as separate processes.

## 10. Run

```bash
# backend
pip install -e . 'fastapi[standard]' uvicorn pydantic
python -m ugence_console_api            # :8090

# console
cd apps/console && npm install && npm run dev   # :3100, proxies /api -> :8090

# tests
python -m pytest ugence_console_api/tests/ -q
```
