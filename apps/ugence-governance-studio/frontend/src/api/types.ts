// Presentation view-models (§8).
//
// The API envelope is typed from the generated OpenAPI client. The backend
// intentionally types the envelope's `result` field as `Any` (planning results
// pass through AWC verbatim), so the shapes of the `result` payloads cannot be
// derived from the OpenAPI schema. These interfaces are hand-written PRESENTATION
// PROJECTIONS of that untyped `result` — the single documented exception to the
// "no any/unknown for canonical responses" rule (§8). They describe only the
// fields P3C renders; unknown extra fields are ignored. No field is computed.

export interface ApiResponseEnvelope<T> {
  api_version: string;
  request_id: string;
  operation: string;
  scenario_id: string | null;
  source_contract_version: string | null;
  awc_version: string;
  input_digests: Record<string, string>;
  result: T;
  diagnostics: Array<{ code: string; message: string; severity: string; field_path?: string | null }>;
  warnings: string[];
  maturity: Record<string, unknown>;
}

// -- operational -----------------------------------------------------------
export interface VersionInfo {
  api_distribution: string;
  api_distribution_version: string;
  api_product_version: string;
  api_contract_version: string;
  build_commit: string | null;
  build_id: string | null;
  awc_distribution_version: string;
  awc_contract_versions: string[];
  supported_workflow_contracts: string[];
  supported_awc_range: string;
  pinned_awc_version: string;
  awc_version_supported: boolean;
  compiler_distribution_version: string | null;
  compiler_contract_versions: string[];
  maturity: Record<string, boolean>;
  notice: Record<string, boolean>;
}

export interface ReadinessInfo {
  status: string;
  ready: boolean;
  checks: Record<string, unknown>;
}

// -- scenarios -------------------------------------------------------------
export interface ScenarioMeta {
  scenario_id: string;
  title: string;
  domain: string;
  description: string;
  workflow_contract_version: string;
  fixture_version: string | null;
  expected_plan_state: string;
  synthetic_data: boolean;
  supported_operations: string[];
}

export interface ScenariosResult {
  scenarios: ScenarioMeta[];
}

export interface ScenarioDetailResult {
  metadata: ScenarioMeta;
  manifest: Record<string, unknown>;
  workflow_identity: string | null;
  narrative: string | null;
  input_artifacts: string[];
  expected_outputs: string[];
  maturity_labels: Record<string, unknown>;
  synthetic_data_notice: string;
}

// -- workflow --------------------------------------------------------------
export interface WorkflowNode {
  node_id: string;
  kind: string;
  label: string;
  disposition: string; // compiler-side hint; the authoritative disposition is on NodeDisposition
  owning_capability?: string;
  authority_type?: string;
  input_object_ids?: string[];
  output_contract?: string;
  audit_requirements?: string[];
  failure_behavior?: string;
}

export interface WorkflowEdge {
  edge_id: string;
  kind: string;
  order: number;
  source_id: string;
  target_id: string;
}

export interface NodeDisposition {
  node_id: string;
  source_node_kind: string;
  disposition: string; // AWC-authoritative disposition (the 8 categories)
  reason_codes: string[];
  role_id: string;
  is_agent_role: boolean;
}

export interface Provenance {
  source_kind?: string;
  synthetic?: boolean;
  [k: string]: unknown;
}

export interface RoleRequirement {
  role_id: string;
  role_name: string;
  role_description: string;
  source_node_id: string;
  workflow_id: string;
  contract_version: string;
  required_capabilities: string[];
  optional_capabilities: string[];
  input_contract_refs: string[];
  output_contract_refs: string[];
  required_tools: string[];
  prohibited_tools: string[];
  domain_requirements: string[];
  data_classification: string;
  residency_constraints: string[];
  provider_constraints: string[];
  deployment_constraints: string[];
  required_permissions: string[];
  prohibited_permissions: string[];
  authority_ceiling: string;
  required_audit_capabilities: string[];
  required_security_classification: string;
  required_evidence_classes: string[];
  human_review_requirement: string;
  minimum_quality_constraint: unknown;
  maximum_latency_constraint: unknown;
  maximum_cost_constraint: unknown;
  authority_context: Record<string, unknown>;
  provenance: Provenance;
  source_package_digest: string;
  policy_refs: string[];
  evidence_refs: string[];
  role_fingerprint: string;
}

export interface WorkflowResult {
  scenario_id: string;
  workflow_identity: string;
  workflow_version: number;
  contract_version: string;
  source_package_digest: string;
  ir_version: string | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  structural_digest: string | null;
  node_dispositions: NodeDisposition[];
  role_requirements: RoleRequirement[];
  non_agent_dispositions: unknown[];
  adaptation_fingerprint: string;
}

// -- registry --------------------------------------------------------------
export interface AgentProfile {
  agent_id: string;
  agent_version: string;
  provider_id: string;
  agent_type: string;
  status: string;
  declared_capabilities: unknown[];
  measured_capabilities: unknown[];
  observed_capabilities: unknown[];
  supported_domains: string[];
  supported_tools: string[];
  input_contracts: string[];
  output_contracts: string[];
  requested_permissions: string[];
  maximum_authority_scope: string;
  supported_data_classifications: string[];
  residency: string;
  deployment_environment: string;
  security_classification: string;
  audit_capabilities: string[];
  valid_from: unknown;
  valid_until: unknown;
  provenance: Provenance;
  profile_fingerprint: string;
}

export interface CapabilityEvidence {
  evidence_id: string;
  agent_id: string;
  agent_version: string;
  capability_id: string;
  evidence_class: string;
  measurement_type: string;
  value: unknown;
  unit: string;
  benchmark_id: string;
  benchmark_version: string;
  dataset_ref: string;
  measured_at: unknown;
  valid_until: unknown;
  issuer: string;
  signature_or_digest: string;
  evidence_fingerprint: string;
}

export interface RegistrySnapshot {
  snapshot_id: string;
  registry_version: string;
  logical_time: number;
  agent_profiles: AgentProfile[];
  capability_evidence: CapabilityEvidence[];
  provenance: Provenance;
  snapshot_digest: string;
}

export interface RegistryResult {
  registry_snapshot: RegistrySnapshot;
}

// -- eligibility -----------------------------------------------------------
export type EligibilityState = "ELIGIBLE" | "INELIGIBLE" | "INDETERMINATE" | "INVALID_INPUT";

// The AWC engine serializes passed conditions as bare names but failed/unknown
// conditions as full ConditionResult objects. A condition is therefore either a
// string or an object carrying the condition name plus verdict/reason detail.
export interface ConditionResult {
  condition: string;
  verdict?: string;
  reason?: string;
  criticality?: string;
  detail?: string;
}
export type Condition = string | ConditionResult;

export interface AgentEligibilityResult {
  role_id: string;
  agent_id: string;
  agent_version: string;
  state: string;
  passed_conditions: Condition[];
  failed_conditions: Condition[];
  unknown_conditions: Condition[];
  elimination_reasons: string[];
  evidence_refs: string[];
  policy_refs: string[];
  result_fingerprint: string;
  profile_fingerprint?: string;
  role_fingerprint?: string;
}

export interface RoleEligibilityReport {
  role_id: string;
  outcome: string;
  results: AgentEligibilityResult[];
  eligible_agent_ids: string[];
  eliminated_agent_ids: string[];
  indeterminate_agent_ids: string[];
  report_fingerprint: string;
  snapshot_digest: string;
}

export interface EligibilityVerification {
  expected_fingerprint: string;
  observed_fingerprint: string;
  match: boolean;
}

export interface EligibilityResult {
  workflow_eligibility: { workflow_fingerprint: string; [k: string]: unknown };
  role_reports: RoleEligibilityReport[];
  verification?: EligibilityVerification;
}

// -- explanations ----------------------------------------------------------
export interface ExplanationAgent {
  agent_id: string;
  agent_version: string;
  state: string;
  passed_conditions: Condition[];
  failed_conditions: Condition[];
  unknown_conditions: Condition[];
  elimination_reasons: string[];
  evidence_refs: string[];
  policy_refs: string[];
  result_fingerprint: string;
}

export interface ExplanationRole {
  role_id: string;
  outcome: string;
  eligible_agent_ids: string[];
  eliminated_agent_ids: string[];
  indeterminate_agent_ids: string[];
  explanation: Record<string, unknown>;
  agents: ExplanationAgent[];
  report_fingerprint: string;
}

export interface ExplanationResult {
  roles: ExplanationRole[];
}
