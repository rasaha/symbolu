// P3D presentation view-models (§6, §9). Projections of the untyped envelope
// `result` for planning endpoints. Every shape describes only the public fields
// P3D renders; strict decoders (api/decoders.ts) validate presence at the
// boundary and fail closed. No domain value is computed here.

// -- ranking ---------------------------------------------------------------
export interface CriterionResult {
  criterion: string;
  metric: string;
  raw_value: unknown;
  normalized_bp: number;
  weight_bp: number;
  weighted_contribution_bp: number;
  evidence_refs: string[];
  explanation: string;
}

export interface RankedCandidate {
  role_id: string;
  agent_id: string;
  agent_version: string;
  rank: number;
  total_score: number;
  tie_group: string | number | null;
  tie_break_values: unknown;
  criterion_results: CriterionResult[];
  evidence_refs: string[];
  policy_refs: string[];
  result_fingerprint: string;
}

export interface RoleRanking {
  role_id: string;
  ranked_candidates: RankedCandidate[];
  eligible_candidate_count: number;
  excluded_candidate_count: number;
  ranking_fingerprint: string;
  role_fingerprint: string;
}

export interface RankingResult {
  rankings: RoleRanking[];
  verification?: { match: boolean; expected_fingerprint: string; observed_fingerprint: string };
}

// -- composition / plan ----------------------------------------------------
export interface RoleAssignment {
  role_id: string;
  primary_agent_id: string;
  primary_agent_version: string;
  total_score: number;
  proposed_permission_bound_ref: string;
  fallback_plan_ref: string;
  assignment_explanation: unknown;
  assignment_fingerprint: string;
}

export interface CategorizedPermission {
  permission: string;
  category: string;
  detail: string;
}

export interface PermissionProposal {
  role_id: string;
  agent_id: string;
  agent_version: string;
  proposed_permissions: string[];
  categorized: CategorizedPermission[];
  proposed_authority_scope: string;
  feasible: boolean;
  infeasible_reasons: string[];
  requires_human_review: boolean;
  notice: string;
  proposal_fingerprint: string;
}

export interface FallbackCandidate {
  agent_id: string;
  agent_version: string;
  rank: number;
  ranking_score: number;
  fallback_order: number;
  selection_reason: string;
  failure_domain_comparison: unknown;
  fallback_fingerprint: string;
}

export interface FallbackPlan {
  role_id: string;
  primary_agent_id: string;
  primary_agent_version: string;
  fallback_state: string;
  candidates: FallbackCandidate[];
  plan_fingerprint: string;
}

export interface TeamConstraint {
  constraint: string;
  satisfied: boolean;
  measured_value: unknown;
  limit_value: unknown;
  detail: string;
}

export interface TeamObjective {
  objective: string;
  raw_value: unknown;
  normalized_value: unknown;
  weight: unknown;
  weighted_contribution: unknown;
  evidence_refs: string[];
  explanation: string;
}

export interface SearchStatistics {
  algorithm: string;
  search_space_size: number;
  assignments_explored: number;
  assignments_pruned: number;
  feasible_team_count: number;
  optimality_status: string;
  termination_reason: string;
}

export interface AgentTeamPlan {
  plan_id: string;
  plan_state: string;
  workflow_identity: string;
  role_assignments: RoleAssignment[];
  permission_bound_proposals: PermissionProposal[];
  role_fallback_plans: FallbackPlan[];
  team_constraint_results: TeamConstraint[];
  team_objective_results: TeamObjective[];
  search_statistics: SearchStatistics;
  total_team_score: number;
  unfilled_roles: string[];
  human_review_requirements: unknown[];
  selection_explanation: unknown;
  plan_fingerprint: string;
  registry_snapshot_digest: string;
}

export interface PlanResult {
  plan_state: string;
  agent_team_plan: AgentTeamPlan;
  composition: Record<string, unknown>;
  replay_record: Record<string, unknown>;
  verification?: { match: boolean; expected_fingerprint: string; observed_fingerprint: string };
}

// selection states (from explanations/plan)
export type SelectionState = "INELIGIBLE" | "ELIGIBLE_NOT_SELECTED" | "SELECTED_PRIMARY" | "SELECTED_FALLBACK";

export interface ExplainPlanResult {
  plan_state: string;
  workflow_identity: string;
  selection_states: Record<string, Record<string, string>>;
  role_assignments: RoleAssignment[];
  team_constraint_results: TeamConstraint[];
  team_objective_results: TeamObjective[];
  permission_bound_proposals: PermissionProposal[];
  role_fallback_plans: FallbackPlan[];
  unfilled_roles: string[];
  search_statistics: SearchStatistics;
  total_team_score: number;
  plan_fingerprint: string;
}

// -- replay ----------------------------------------------------------------
export interface ReplayResult {
  expected_plan_fingerprint: string;
  replayed_plan_fingerprint: string;
  match: boolean;
  plan_state: string;
  replay_record: Record<string, unknown>;
  diagnostics: Array<{ code: string; message: string; severity: string }>;
}

// -- comparison ------------------------------------------------------------
export interface PlanDiff {
  same_workflow: boolean;
  workflow_mismatch: boolean;
  plan_a_fingerprint: string;
  plan_b_fingerprint: string;
  assignment_changes: unknown[];
  score_delta: unknown;
  constraint_changes: unknown[];
  permission_changes: unknown[];
  fallback_changes: unknown[];
  policy_digest_changes: unknown[];
  snapshot_changed: boolean;
  diff_fingerprint: string;
}

export interface CompareResult {
  diff: PlanDiff;
  same_workflow: boolean;
  workflow_mismatch: boolean;
  plan_a_fingerprint: string;
  plan_b_fingerprint: string;
  snapshot_changed: boolean;
}

// -- what-if ---------------------------------------------------------------
export interface WhatIfResult {
  baseline_plan: AgentTeamPlan;
  modified_plan: AgentTeamPlan;
  plan_diff: PlanDiff;
  perturbation_applied: { operation: string; params: Record<string, unknown> };
  changed_input_digests: Record<string, string>;
  explanation: ExplainPlanResult;
  baseline_state: string;
  modified_state: string;
}

export const WHAT_IF_OPERATIONS = [
  "FORBID_PROVIDER",
  "REQUIRE_RESIDENCY",
  "TIGHTEN_COST_CEILING",
  "TIGHTEN_LATENCY_CEILING",
  "REVOKE_AGENT_VERSION",
  "EXPIRE_EVIDENCE",
  "TIGHTEN_PERMISSION_POLICY",
  "TIGHTEN_PROVIDER_CONCENTRATION",
  "REMOVE_CANDIDATE",
] as const;
export type WhatIfOperation = (typeof WHAT_IF_OPERATIONS)[number];
