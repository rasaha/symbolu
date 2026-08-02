# Code Governance Record Model (MVP 1A)

> Machine-readable form: `docs/record_inventory.json`. All product records are
> immutable frozen dataclasses, tenant-bound, and (where identity matters)
> content-addressed via domain-separated SHA-256.

## Product-owned records

| Record | Module | Binds | Fingerprint / digest |
|---|---|---|---|
| `GovernedChangeIdentity` | `models.change_identity` | tenant, repo owner/name, PR number, base/head ref+SHA, target branch, merge method, installation/org, event source, delivery id, captured_at | `fingerprint` over **governed fields only** (delivery id + capture time excluded → idempotent) |
| `EvidenceRecord` | `evidence.records` | tenant, repo, PR, base/head SHA, evidence_type, source id/kind, validator id+version, trust level, captured_at, valid_until, content_digest, provenance, normalized payload / ref | content-addressed `evidence_id`; `content_digest` over payload |
| `ValidatorIdentity` | `claims.manifest` | validator id, version, trust level | `fingerprint` |
| `EvidenceReference` | `claims.manifest` | evidence id, content digest, head SHA, validator id+version | `fingerprint` |
| `ClaimEntry` | `claims.manifest` | claim id/type, required-by-policy, status, tenant, repo, base/head, validator id+version+trust, policy_ref, evidence refs, valid_until | `fingerprint` (evidence-ref order-insensitive) |
| `ClaimManifest` | `claims.manifest` | manifest id, tenant, repo, PR, base/head, risk tier, policy_ref, captured_at, change fingerprint, entries | **order-independent** `fingerprint` |
| `GovernanceRecommendation` | `governance.recommendation` | tenant, repo, PR, change fp, manifest fp, disposition, rationale, policy_ref, created_at | `fingerprint`; `is_binding = False` (never a `DecisionRecord`) |
| `PreparedMergeAction` | `governance.prepared_action` | tenant, repo, PR, base/head, merge method, target branch, change fp, decision id, cer id + content hash, policy refs, expiry, expected tree | content-derived `fingerprint` (excludes minted ids) |
| `TapAssertionResult` | `governance.tap_adapter` | claim id/type, coverage, evidence_coverage, covered refs, unsupported elements, trace id, request+result fingerprints | from TAP |
| `ShadowActionEvaluation` | `governance.actiongate_adapter` | mode=SHADOW_ONLY, prepared-action fp, request/result fp, outcome, reason codes, obligations, constraints, expiry, policy refs | from ActionGate |
| `WorkflowRevision` | `workflow.records` | workflow id, revision id, tenant, repo, PR, change fp, base/head, state, mode, timestamps, all references | lineage: one PR → many head/base revisions |
| `GovernanceChainRecord` | `reconstruction.records` | all links (see chain doc) + `ACTION_CLEARANCE_NOT_EVALUATED` + `EXECUTION_DISABLED` | `fingerprint` |

## Reused upstream records (verbatim, via public API)

| Record | Package | Note |
|---|---|---|
| `DecisionRecord` | `ugence_decision_authority` | **no** `MergeDecisionRecord` / `CodeGovernanceDecisionRecord` created |
| `ContextEnvelopeRecord` | `ugence_decision_authority` | canonical `schema_version = "cer.v1"`; **no** `cer.v2` |
| `AssertionGovernanceRequest` / `AssertionGovernanceResult` | `ugence_governance_contracts` | TAP request/result |
| `ActionGovernanceRequest` / `ActionGovernanceResult` | `ugence_governance_contracts` | ActionGate request/result; exact SHA values ride in `requested_parameters` |

## Exact-artifact value placement (no CER schema change)

Per the readiness audit's Decision & CER mapping:

- exact SHA / merge-method **values** → `ActionRequest.requested_parameters` and
  neutral `ActionGovernanceRequest.requested_parameters` + the product
  `PreparedMergeAction` envelope;
- **names** of permitted parameters + required controls → CER
  `permitted_parameters` / `prohibited_parameters` / `required_controls`;
- decision / tenant / policy / expiry / content hash → CER typed fields.

Exact SHA values are **never** misrepresented as CER parameter-name fields.

## Persistence (evidence-store classification)

In-memory tenant-isolated immutable reference stores. This is **not** the
production durable store; no production database is introduced (see
`CODE_GOVERNANCE_SHADOW_LIMITATIONS.md`). Existing durable stores were classified:

| Store | Classification | Rationale |
|---|---|---|
| StoryGraph `DurableAuditLog` | REFERENCE_ONLY | reference-grade hash-chained SQLite; productionization is a later phase |
| `agentic/ledger` `GovernanceAuditStore` | REFERENCE_ONLY | reference-grade; not adopted in 1A |
| Decision Authority in-memory repos | REUSE_AS_IS (for DA records) | product wires the DA in-memory reference repos for `DecisionRecord`/CER |
| a new production database | NOT_SUITABLE (this phase) | premature commitment; explicitly deferred |
