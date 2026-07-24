# Read-Only Component Adapters (Phase 9)

*`governed_inference_pilot/adapters/`. Each adapter imports its component **read-only**, exposes a
stable pilot contract (`AdapterResult`), preserves the component's original output (`source_repr`),
maps to the canonical schema (`transformed_repr`), emits semantic-loss warnings, exposes component
version, records a deterministic latency-unit cost, records exceptions, and **fails closed** on unknown
critical states. Adapters do not duplicate component logic.*

## Adapters and the real logic they invoke

| Adapter | Frozen call | Genuine? |
|---|---|---|
| `execution_gate.py` | `ExecutionGate().evaluate(Candidate, Request, now)` | yes — constructs fully-signalled candidates and calls the real gate |
| `model_policy.py` | constrained quality-floor objective (argmin cost s.t. quality ≥ q_min) | objective shape from the reconciliation study; abstains below floor |
| `claim_integrity.py` | `claim_integrity.claims.decompose` | yes |
| `claim_integrity.py` (scope) | `scope_integrity.variants.variant_h_integrated` | yes — the frozen gated extension |
| `evidence_assurance.py` | `evidence_assurance.adapter.to_delivery(AssuranceResult, risk)` | yes — the frozen EA→delivery contract |
| `assertion_gate.py` | `assertion_gate_robustness.gate.govern(SignalBundle, claim_strength)` | yes |
| `action_gate.py` | conservative authority/reversibility/risk mapping (shadow) | shadow adapter |

Six of the seven stages call the **actual frozen decision code**; ModelPolicy uses the reconciliation
study's constrained-objective *shape* over the registry (not a re-implementation of internal routing),
and ActionGate is an explicitly-labelled conservative shadow mapping (no standalone frozen ActionGate
decision function with a compatible signature was available; the adapter is documented as shadow, not
presented as the frozen component).

## Adapter guarantees (enforced in code)

- **Original output preserved:** every `AdapterResult` carries `source_repr` (the component's own
  output) and `transformed_repr` (the canonical mapping). The semantic-loss check runs between them.
- **Fail closed:** the `safe()` wrapper turns any component exception into an `INDETERMINATE` result
  with `GIP.STAGE_EXCEPTION` — a component fault is never a silent success. An unknown evidence state or
  missing field yields `INDETERMINATE` + a reason code, never `ALLOW`.
- **Versions exposed:** each result carries the component version (`exec_gate_v1`, `ea_evidence_v1`,
  `assertion_gate_v1`, `ci_claim_v1`, …) for the audit trace and replay version-comparison modes.
- **Deterministic cost:** latency is a fixed unit count per stage (Phase 20), not wall-clock, so traces
  reproduce.
- **No logic duplication:** adapters translate inputs/outputs only; the decision is the component's.

## Verified behavior

- ExecutionGate → ELIGIBLE (fully-signalled) / INELIGIBLE (failed critical signal).
- ModelPolicy → selected / abstain (no model meets the quality floor).
- ClaimIntegrity → VALID / INDETERMINATE; ScopeIntegrity → resolved / INDETERMINATE_SCOPE.
- EvidenceAssurance → ALLOW / QUALIFY / REJECT / ESCALATE / INDETERMINATE via the frozen mapping.
- AssertionGate → ALLOW / QUALIFY / REJECT / ESCALATE (real `govern`).
- ActionGate → PERMIT / CONSTRAIN / BLOCK / ESCALATE / INDETERMINATE / NO_ACTION.
