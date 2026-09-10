// Bring Your Workflow view-models (ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md §22, BW-1 to
// BW-5). Projections of the untyped envelope `result` for the three workflow
// operations the screen consumes: validate, adapt, compare-adaptations. Every shape
// names only the public fields the screen renders; the decoders in api/decoders.ts
// validate presence at the boundary and fail closed. No domain value is computed here.

export interface WorkflowIntegrity {
  checked: boolean;
  source_digest?: string;
  computed_digest?: string;
  match?: boolean;
}

export interface ValidateWorkflowResult {
  validation_state: string;
  declared_contract_version: string;
  supported_version: boolean;
  supported_contracts: string[];
  integrity: WorkflowIntegrity;
  diagnostics: Array<Record<string, unknown>>;
}

export interface NodeDispositionView {
  node_id: string;
  source_node_kind: string;
  disposition: string;
  reason_codes: string[];
  role_id: string;
  is_agent_role: boolean;
}

export interface RoleRequirementView {
  role_id: string;
  role_name: string;
  source_node_id: string;
  source_node_kind: string;
  required_capabilities: string[];
}

export interface AdaptWorkflowResult {
  adapter_mode: string;
  ok: boolean;
  adaptation_fingerprint: string;
  adaptation_envelope_fingerprint: string;
  node_dispositions: NodeDispositionView[];
  role_requirements: RoleRequirementView[];
  non_agent_dispositions: unknown[];
  role_dependency_graph: unknown;
  diagnostics: Array<Record<string, unknown>>;
  adaptation_envelope: Record<string, unknown>;
}

export interface CompareAdaptationsResult {
  equivalence_state: string;
  report: Record<string, unknown>;
  v1_adaptation_fingerprint: string;
  v2_adaptation_fingerprint: string;
}

// -- Workflow drafts (Bring Your Workflow phase 3A, ADR §24) -------------------
// Projections of the v2 draft answers. A draft is a record, never a permission: its
// lifecycle is the constant DRAFT and any claimed owner carries PRESENTED_UNPROVEN.

export interface DraftRefusal {
  refused: true;
  code: string;
  reason: string;
}

export interface WorkflowDraftFields {
  draft_id: string;
  tenant_id: string;
  title: string;
  contract_version: string;
  workflow_digest: string;
  lifecycle: string;
  claimed_owner_ref: string;
  claimed_owner_assurance: string;
  registration_ref: string;
  registration_digest: string;
  supersedes: string;
  recorded_by: string;
  validated_by: string;
  notes: string;
  record_version: string;
}

export interface WorkflowDraftRecord {
  draft: WorkflowDraftFields;
  workflow: Record<string, unknown>;
}

export interface WorkflowDraftSaved {
  saved: true;
  draft_id: string;
  workflow_digest: string;
  lifecycle: string;
  lifecycle_note: string;
  record: WorkflowDraftRecord;
  record_digest: string;
  claimed_owner_status: string;
  recorded_by: string;
  validated_by: string;
  integrity: WorkflowIntegrity;
  confers: string;
}

export interface WorkflowDraftRow extends WorkflowDraftFields {
  superseded_by: string;
  record_digest: string;
}

export interface WorkflowDraftListing {
  count: number;
  include_superseded: boolean;
  lifecycle_note: string;
  claimed_owner_status: string;
  confers: string;
  result: WorkflowDraftRow[];
}

export interface WorkflowDraftRead {
  found: boolean;
  draft_id: string;
  record: WorkflowDraftRecord | null;
  lineage: string[];
  superseded_by: string;
}
