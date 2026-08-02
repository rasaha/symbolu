# Model Selection — Contract Ownership Matrix

Section 15. For every public model/enum, where does it belong? **Governance Contracts is NOT modified in
this phase.** A record belongs in Governance Contracts **only** when it is capability-neutral,
authority-neutral, stable, and truly shared at a lower dependency layer — merely being used by two
modules is not sufficient.

## 1. Model Selection-owned records (would live in the capability, not Governance Contracts)

| Record / enum | Defined at | Owner | Rationale |
|---|---|---|---|
| `Request` (execution requirements) | `execution_gate/model.py` | Model Selection | request-shaped input to selection; capability-specific |
| `Candidate` (provider/model + declared caps + signals) | `execution_gate/model.py` | Model Selection | candidate metadata; capability-specific |
| `Signal` (observed fact + evidence) | `execution_gate/model.py` | Model Selection | eligibility evidence unit |
| `GateConfig` | `execution_gate/model.py` | Model Selection | eligibility configuration |
| `Evidence`, `EvidenceSource`, `ConditionResult` | `execution_gate/states.py` | Model Selection | eligibility evidence/condition types |
| `EligibilityState` (ELIGIBLE/INELIGIBLE/CONDITIONALLY_ELIGIBLE/INDETERMINATE) | `execution_gate/states.py` | Model Selection | eligibility outcome enum |
| `Verdict`, `Criticality` | `execution_gate/states.py` | Model Selection | per-condition verdict + criticality class |
| `EligibilityDecision` (+`to_dict`) | `execution_gate/states.py` | Model Selection | the eligibility contract; serialization-sensitive |
| `ReasonCode` (append-only) + `normalize_raw` | `execution_gate/reason_codes.py` | Model Selection | selection/eligibility reason taxonomy; **append-only invariant** |
| `ModelRecord`, `ExecStatus`, `ExecutableRegistry` | `execution_gate/registry.py` | Model Selection | registry port + record |
| `PolicyWeights`, `Selection` | `execution_gate/policy.py` | Model Selection | selection weights + output record |
| `ConstraintSet` (resolved hard constraints) | `model_selection_experiment/policy.py` (dict), `MODEL_SELECTION_POLICY_ENGINE_SPEC.md` | Model Selection | resolved-constraint contract |
| Decision record (`eligible`/`eliminated`/`scored`/`fallback_chain`/`selected`/`abstained`/…) | experiment & pilot `route` (dict) | Model Selection | selection-record contract (audit-friendly) |
| Score breakdown / evidence list (`predicted_quality`,`components`,`evidence`) | experiment `score`/`fuse_quality` | Model Selection | scoring explanation contract |
| `NO_ELIGIBLE_MODEL` / abstain result | experiment/pilot `route`, `variants.py` | Model Selection | escalation contract |
| `SelfAssessmentViolation` | experiment/pilot | Model Selection | advisory-boundary error |

## 2. Records owned elsewhere (Model Selection consumes, does not own)

| Record / concern | Owner | Note |
|---|---|---|
| Assertion validity / evidence admissibility | **TAP** | downstream of a chosen model's output |
| Exact-action authorization (CER-hashed) | **ActionGate** | downstream |
| Commit-time operational clearance | **ACP** | downstream |
| Binding business-decision authority | **Decision Authority** | not a selection concern |
| Advisory sequence-risk evidence | **StoryGraph** | not a selection concern |
| Provider *implementation* registration/lifecycle | **Governance Provider Framework** | governs provider adapters, a different object than model candidates |
| Request normalization / task classification / risk profiling envelope | **control-plane research** (`control_plane/contracts.py`, `policy_context.py`) | upstream of MSP; feeds it |
| Provider execution / retry / spend accounting | provider-execution layer | downstream |

## 3. Should any of these move into Governance Contracts?

**No — not in this phase, and probably not most of them.** Test against the four criteria:

| Candidate | Capability-neutral? | Authority-neutral? | Stable? | Truly shared lower-layer? | Verdict |
|---|---|---|---|---|---|
| `ReasonCode` | partly (reason taxonomy) | yes | append-only (stable) | only Model Selection + its consumers use it | **Keep in Model Selection.** Shared by consumers, but consumers depend *on* Model Selection — that is normal capability→consumer flow, not a lower-layer shared contract. |
| `EligibilityState` / `EligibilityDecision` | no (eligibility-specific) | yes | stable | no | **Keep in Model Selection** |
| `Evidence`/`EvidenceSource` | *looks* generic | yes | stable | possibly (TAP/StoryGraph also model evidence) | **Do NOT move now.** Superficial name overlap; MSP's `Evidence` is operational-signal evidence with TTL/source-precedence, semantically distinct from TAP admissibility evidence. Moving it would over-generalize. Revisit only if a real cross-capability need is proven. |
| Decision-record schema | no | yes | not yet stable (dict, three variants) | no | **Keep in Model Selection**; stabilize during migration |

**Conclusion:** every Model Selection contract belongs in the Model Selection capability. None meets the
bar for Governance Contracts today (they are capability-specific and flow *downward to consumers*, not
*shared at a lower layer*). Governance Contracts must not be modified in this phase, and this audit finds
no record that should move there.
