# Overlay Reduction Plan — P2.1

Grounded in the merged P3A ownership matrix and the compiler P2 field-resolution
trace. Machine form: `OVERLAY_REDUCTION_PLAN.json`.

## Classification of overlay fields

| Field | Classification | Reason |
|---|---|---|
| `role_name` | REMOVE_FROM_REQUIRED_OVERLAY | compiler emits `semantic_purpose` |
| `role_description` | REMOVE_FROM_REQUIRED_OVERLAY | compiler emits `semantic_description` |
| `human_review_requirement` | REMOVE_FROM_REQUIRED_OVERLAY | compiler classifies human review/authority |
| functional base capability (`evidence_extraction`) | REMOVE (adapter no longer injects) | compiler emits it via `NODE_KIND_MAPPING` |
| domain-specialist `required_capabilities` | RETAIN_AS_ENTERPRISE_POLICY | compiler does not know domain specialization |
| `required_evidence_classes`, `data_classification`, `required_permissions`, `required_security_classification`, provider/residency/deployment/tool/SLA fields | RETAIN_AS_ENTERPRISE_POLICY | enterprise governance posture, never compiler-owned |
| `data_classification` / permission-intent / tools (if source-declared) | DEFER | compiler slot exists only on source declaration |

`reduce_overlay(full_overlay)` removes exactly the compiler-emitted set
(`role_name`, `role_description`, `human_review_requirement`) and retains everything
else verbatim. In the four P3A scenarios the only field removed is `role_name`
(the overlays set no `role_description` / `human_review_requirement`); the AWC
adapter additionally stops synthesizing the base `evidence_extraction` capability
(now taken from the compiler).

## Merge is monotonic w.r.t. authority and security

- enterprise policy MAY narrow, strengthen, or add review;
- enterprise policy MAY NOT broaden authority (dispositions come from `classify_node`
  on the base graph, never from the overlay);
- enterprise policy MAY NOT erase a compiler human-review
  (`OVERLAY_REMOVES_HUMAN_REVIEW`, fail closed) or a governance boundary.
