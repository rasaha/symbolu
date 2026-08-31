# ACP Terminology & Scope (Disambiguation)

## Headline finding

**"Action Clearance Protocol" does not appear anywhere in the repository or its git history.** A
case-insensitive search across `*.md/*.py/*.txt/*.json` and `git log --all -S` returns nothing. The term is
a coinage of the audit request. In the actual codebase, **"ACP" expands to "Autonomous Control Plane"**
consistently (e.g. `symbolu_robotics/autonomous_control_plane/__init__.py`, `Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md:1`,
`Project_documentation/control_plane/acp/ACP_EXECUTIVE_SUMMARY.md:58,64`). "Clearance" is a separate vocabulary word — the CLEAR/HOLD verdict of
the operational-safety component — not an expansion of the acronym.

Consequently, wherever this audit says "ACP" it means the *discipline* the request describes
(*"is the already-authorized action clear to execute now?"*), and it maps that discipline onto the physical
code that implements it under other names.

## Terminology inventory

| Term | Meaning | Location(s) | Current owner | Status |
|---|---|---|---|---|
| **ACP** / Autonomous Control Plane (robotics) | Deterministic decision-and-authorization runtime for robot actions; frozen stdlib-only core | `symbolu_robotics/autonomous_control_plane/`; docs `acp/` (60 files) | Robotics | Live code, Phase 0–3, `0.1.0-phase0`; **shadow-only, disabled-by-default** |
| **ACP** / AI Control Plane (product umbrella) | The 3-layer enterprise stack (Context Minimization + ActionGate + ACP); unified console plan | `Project_documentation/control_plane/ACP/UGENCE_UNIFIED_CONSOLE_PLAN.md`, `ai_control_plane_v3/`, `AI_CONTROL_PLANE_VC_BRIEF.md` | Ugence platform | **Documentation only** |
| **Autonomous Control Plane** (console digital sibling) | Deterministic CLEAR/HOLD gate over live infra signals (freeze / cluster health / error budget) | `ugence_console_api/capabilities/operational_safety.py`, `ugence_console_api/models.py:116` | `ugence_console_api` | Live product code; **does NOT import the robotics core** (name collision by design) |
| **ACP DB** (`acp_db`) | DB-domain operational-safety adapter reusing the frozen robotics `cloud.compose()` | `cer_v0_3/acp_db/{adapter,safety,envelopes}.py` | CER v0.3 | Live, **shadow-only** |
| **clearance** / CLEAR–HOLD | Shared vocabulary for the operational-safety verdict ("safe right now?") | `models.py:7`, `operational_safety.py`, `Project_documentation/control_plane/ACP/PHASE1_GOVERNED_LOOP_DTO_CONTRACT.md:208` | shared | vocabulary, not a module |
| **ActionGate** | Authorization engine ("may this be done?"); mints the token | `actiongate_provider/`, `cyber_security/action_gate_reference/` | ActionGate | Live; first Action-Governance provider |
| **`ActionGovernanceOutcome.EXPIRED`** etc. | Neutral governance seam carrying clearance vocabulary | `packages/governance-contracts/…/contracts/action.py` | Governance Contracts | Frozen (contract 1.0.0) |
| **ExecutionGate** | *Model/provider eligibility* (Model Selection) — NOT action clearance | `execution_gate/`, `ugence_model_selection` | Model Selection | Live; **UNRELATED** to ACP |
| **`control_plane/` / `control_plane_shadow/`** | AI-governance pipeline eval (model selection) — NOT robotics clearance | `control_plane/`, `control_plane_shadow/` | Model-Selection/governance eval | Live; **UNRELATED** to ACP |

**Distinct concepts denoted by "ACP": four** (robotics Autonomous Control Plane; AI Control Plane umbrella;
console digital clearance; ACP DB adapter), plus one shared vocabulary word.

### Collision hazards (do not merge)

- The sibling directories **`ACP/`** (AI Control Plane, docs) and **`acp/`** (Autonomous Control Plane,
  robotics docs) differ **only by case**.
- Concept #1 (robotics Autonomous Control Plane) and concept #3 (console digital "Autonomous Control Plane")
  share the exact display name and the CLEAR/HOLD vocabulary but are **wholly separate code with no shared
  import**.
- `execution_gate` / `control_plane*` use "gate" and "control plane" for the **Model Selection** product,
  which is a different capability entirely.

## Authoritative meaning vs live code

The Ugence governance architecture's intended meaning is:

> **ACP evaluates whether an already-authorized action remains valid and operationally permissible
> immediately before execution.** It never re-decides, never authorizes, never executes.

Live-code agreement:

- **Agrees:** the **cloud/console** framing — `ugence_console_api/…/operational_safety.py:11-12` (*"It never
  authorizes — ActionGate already decided whether the action may run; ACP decides whether now"*);
  `Project_documentation/control_plane/acp/RESPONSIBILITY_MATRIX.md:12-13`; `symbolu_robotics/autonomous_control_plane/cloud/composition.py`.
- **Contradicts:** the **robotics V1** framing — `Project_documentation/control_plane/acp/ACP_ARCHITECTURE.md:20` (*"deterministic
  **decision-and-authorization** runtime"*) and stage 9 which *"mints a one-shot execution grant"*
  (`:110`); the code mints a `ControlAuthorization` (`authorization.py:34`).

The definition is therefore **not uniformly true of the live code**; this is the central architectural
ambiguity behind the NOT-READY verdict (see `AUTHORITY_BOUNDARY.md`).

## Scope of this audit

In-scope as "the ACP discipline": the robotics Autonomous Control Plane core and its cloud/safety adapters;
the console digital clearance; the `acp_db` reuse; the reliability benches; and the neutral seam. Out of
scope / UNRELATED_ACP: `execution_gate*` and `control_plane*` (Model Selection), `bounded_shadow_pilot`
(cyber ActionGate pilot), and the AI-Control-Plane umbrella docs (concept #2, documentation only).
