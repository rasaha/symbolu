# Contract-Mapping Matrix — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§6, §18).
> Verified against live code at commit `3ec11e4e`. Machine-readable form: `contract_mapping.json`.

Every Code Governance design concept is mapped onto an existing repository type **before** any new
contract is proposed. New-type classes: `PRODUCT_INTERNAL`, `PRODUCT_PUBLIC`, `PROVIDER_SPECIFIC`,
`CAPABILITY_NEUTRAL`, `UNNECESSARY`.

| Design concept | Existing type / API | Owning capability | Gap | Required action | New-type class |
|---|---|---|---|---|---|
| GitHub PR reference | — | GitHub Evidence Connector (product) | no PR type | product record → `evidence_refs` | PRODUCT_INTERNAL |
| Evidence bundle | `ValidationEvidenceBundle` (design) · `EvidencePacket` (TAP E5) | Evidence Connector + TAP | no durable store | product-side store; emit immutable refs | PRODUCT_INTERNAL |
| Claim manifest | none (nearest `EvidencePacket`; `ValidationRecord` E6 docs-only) | TAP / product | no `ClaimManifest` contract | product schema first | PRODUCT_PUBLIC |
| TAP request | `AssertionGovernanceRequest` (`contracts/assertion.py:26`) | governance-contracts | none | REUSE | — |
| TAP result | `AssertionGovernanceResult` (`:41`) | governance-contracts | none | REUSE | — |
| Recommendation | `RecommendationRecord` (DA) · `AdjudicationRecommendation` (design) | Decision Authority / Adjudication | adjudication = MVP2 | REUSE (DA); adjudicator = PRODUCT_PUBLIC | PRODUCT_PUBLIC |
| **DecisionRecord** | `DecisionRecord` (`decisions/decision.py:25`) | Decision Authority | none — **no `MergeDecisionRecord`** | REUSE | — |
| **ContextEnvelopeRecord** | `ContextEnvelopeRecord` cer.v1 (`actions/cer.py:62`) | Decision Authority | no typed field for exact SHA **values** | REUSE; values via `ActionRequest.requested_parameters` + product envelope | — |
| Prepared merge action | `ActionGovernanceRequest` + `ActionRequest` | Workflow Service → ActionGate | none | REUSE; product builds request | — |
| ActionGovernanceRequest | `ActionGovernanceRequest` (`contracts/action.py:29`) | governance-contracts | none | REUSE | — |
| ActionGovernanceResult | `ActionGovernanceResult` (`:47`) | governance-contracts | none — **no `ExactChangeAuthorization` emitted** | REUSE | — |
| Exact-change product envelope | compose CER + `ActionGovernanceRequest` + `ActionGovernanceResult` + fingerprint + expiry | Workflow Service (product) | product composition only | PRODUCT_INTERNAL envelope | PRODUCT_INTERNAL |
| ACP clearance | `OperationalClearanceRecord` (conceptual) · `ClearanceVerdict` (console) · `ActionDecision` (robotics) | ACP | no GitHub domain; no durable ref; shadow-only | ADAPTER + NEW_CAPABILITY (durable clearance ref) | PROVIDER_SPECIFIC |
| Execution dispatch | `ExecutionDispatchRequest` (+ DA `ExecutionIntent`) | GitHub Execution Provider (new) | provider missing | PROVIDER_SPECIFIC impl over REUSE contract | PROVIDER_SPECIFIC |
| Execution observation | `ExecutionObservation` (+ DA `ExecutionRecord`) | Execution provider / DA | none in contract | REUSE contract | — |
| Merge result | `ExecutionRecord` | DA execution | digest is product data | REUSE; digest in `observed_parameters`/`evidence_refs` | PRODUCT_INTERNAL (payload) |
| Reconciliation record | `ReconciliationResult` (`execution/reconciliation.py:23`) | DA execution | none | REUSE | — |
| Workflow state | none (DecisionCase state machine is DA-internal) | Workflow Service (product) | no durable workflow engine | PRODUCT_INTERNAL state machine + persistence | PRODUCT_INTERNAL |
| Audit reconstruction view | `AuditEvent` + StoryGraph `durable_audit` (partial) | product over durable backend | no unified kernel chain | PRODUCT_INTERNAL view; PLANNED dependency | PRODUCT_INTERNAL |
| Policy reference | `VersionedRef` (`decisions/subject.py:30`) | Decision Authority / product | none (free ref) | REUSE | — |
| Override | `OverrideRecord` + `override_record_id` | Decision Authority | none | REUSE | — |
| Supersession | `supersedes_*_id` + `EffectiveStatus`/`CaseStatus.SUPERSEDED` | Decision Authority | no auto patch-hash invalidation | REUSE; product triggers supersession | PRODUCT_INTERNAL (trigger) |
| Merge-group identity | none | product (Exact Merge Identity) | GitHub-specific | PRODUCT_INTERNAL tuple (`merge_identity_schema.json`) | PRODUCT_INTERNAL |

## Headline results

- **No frozen neutral contract needs to change for MVP.** Every merge-governance concept maps
  onto existing `DecisionRecord` / CER / `ActionGovernance*` / `Execution*` types plus
  product-owned envelopes.
- **No duplicate `MergeDecisionRecord`** (design §4.3 confirmed): `DecisionRecord` already carries
  `recommendation_refs`, `assessment_refs`, `policy_refs`, `reason_codes`, `override_record_id`,
  `supersedes_decision_id`.
- **`ExactChangeAuthorization` is a product envelope**, not a new ActionGate contract
  (design §4.4 confirmed): `ActionGovernanceResult` emits no such object.
- The genuinely-new artifacts are all **PRODUCT_INTERNAL** or **PROVIDER_SPECIFIC** (Workflow
  state, merge identity tuple, exact-change envelope, GitHub connector/execution provider). The
  only candidate `CAPABILITY_NEUTRAL`/`PRODUCT_PUBLIC` item is a **claim manifest schema**, and
  even that starts product-side.
