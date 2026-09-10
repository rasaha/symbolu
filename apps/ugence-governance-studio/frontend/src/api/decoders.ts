// Strict presentation-boundary decoders (§6, §9). The OpenAPI envelope types the
// `result` field generically, so these adapters validate that the required PUBLIC
// fields are present and well-shaped before rendering. They contain NO domain
// calculation, preserve canonical values verbatim, and FAIL CLOSED (throw) rather
// than silently defaulting — surfacing a visible integrity error instead of an
// invented plan.
import type {
  CompareResult,
  ExplainPlanResult,
  PlanResult,
  RankingResult,
  ReplayResult,
  WhatIfResult,
} from "./types-p3d";
import type {
  AdaptWorkflowResult,
  CompareAdaptationsResult,
  DraftRefusal,
  NodeDispositionView,
  RoleRequirementView,
  ValidateWorkflowResult,
  WorkflowDraftFields,
  WorkflowDraftListing,
  WorkflowDraftRead,
  WorkflowDraftRecord,
  WorkflowDraftRow,
  WorkflowDraftSaved,
} from "./types-bring";

export class DecodeError extends Error {
  readonly field: string;
  constructor(field: string, message: string) {
    super(`contract decode failed at '${field}': ${message}`);
    this.name = "DecodeError";
    this.field = field;
  }
}

function obj(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new DecodeError(field, "expected an object");
  }
  return value as Record<string, unknown>;
}
function arr(value: unknown, field: string): unknown[] {
  if (!Array.isArray(value)) throw new DecodeError(field, "expected an array");
  return value;
}
function req(o: Record<string, unknown>, key: string, field: string): unknown {
  if (!(key in o)) throw new DecodeError(`${field}.${key}`, "missing required field");
  return o[key];
}
function num(value: unknown, field: string): number {
  if (typeof value !== "number") throw new DecodeError(field, "expected a number");
  return value;
}
function str(value: unknown, field: string): string {
  if (typeof value !== "string") throw new DecodeError(field, "expected a string");
  return value;
}

export function decodeRanking(result: unknown): RankingResult {
  const r = obj(result, "ranking");
  const rankings = arr(req(r, "rankings", "ranking"), "ranking.rankings");
  rankings.forEach((rk, i) => {
    const o = obj(rk, `ranking.rankings[${i}]`);
    req(o, "role_id", `ranking.rankings[${i}]`);
    str(req(o, "ranking_fingerprint", `ranking.rankings[${i}]`), `ranking.rankings[${i}].ranking_fingerprint`);
    const cands = arr(req(o, "ranked_candidates", `ranking.rankings[${i}]`), `ranking.rankings[${i}].ranked_candidates`);
    cands.forEach((c, j) => {
      const co = obj(c, `candidate[${i}.${j}]`);
      num(req(co, "rank", `candidate[${i}.${j}]`), `candidate[${i}.${j}].rank`);
      num(req(co, "total_score", `candidate[${i}.${j}]`), `candidate[${i}.${j}].total_score`);
      const crits = arr(req(co, "criterion_results", `candidate[${i}.${j}]`), `candidate[${i}.${j}].criterion_results`);
      crits.forEach((cr, k) => {
        const cro = obj(cr, `criterion[${i}.${j}.${k}]`);
        for (const f of ["normalized_bp", "weight_bp", "weighted_contribution_bp"]) {
          num(req(cro, f, `criterion[${i}.${j}.${k}]`), `criterion[${i}.${j}.${k}].${f}`);
        }
      });
    });
  });
  return result as RankingResult;
}

const PLAN_STATES = new Set([
  "COMPLETE",
  "PARTIAL",
  "NO_FEASIBLE_TEAM",
  "SEARCH_SPACE_EXCEEDED",
  "INVALID_INPUT",
]);

function validatePlan(plan: Record<string, unknown>, field: string): void {
  const state = str(req(plan, "plan_state", field), `${field}.plan_state`);
  if (!PLAN_STATES.has(state)) throw new DecodeError(`${field}.plan_state`, `unknown plan state ${state}`);
  str(req(plan, "plan_fingerprint", field), `${field}.plan_fingerprint`);
  arr(req(plan, "role_assignments", field), `${field}.role_assignments`);
  arr(req(plan, "permission_bound_proposals", field), `${field}.permission_bound_proposals`);
  arr(req(plan, "role_fallback_plans", field), `${field}.role_fallback_plans`);
  arr(req(plan, "team_constraint_results", field), `${field}.team_constraint_results`);
  arr(req(plan, "unfilled_roles", field), `${field}.unfilled_roles`);
  obj(req(plan, "search_statistics", field), `${field}.search_statistics`);
}

export function decodePlan(result: unknown): PlanResult {
  const r = obj(result, "plan");
  str(req(r, "plan_state", "plan"), "plan.plan_state");
  validatePlan(obj(req(r, "agent_team_plan", "plan"), "plan.agent_team_plan"), "plan.agent_team_plan");
  return result as PlanResult;
}

export function decodeExplainPlan(result: unknown): ExplainPlanResult {
  const r = obj(result, "explainPlan");
  str(req(r, "plan_state", "explainPlan"), "explainPlan.plan_state");
  obj(req(r, "selection_states", "explainPlan"), "explainPlan.selection_states");
  arr(req(r, "team_constraint_results", "explainPlan"), "explainPlan.team_constraint_results");
  arr(req(r, "permission_bound_proposals", "explainPlan"), "explainPlan.permission_bound_proposals");
  arr(req(r, "role_fallback_plans", "explainPlan"), "explainPlan.role_fallback_plans");
  return result as ExplainPlanResult;
}

export function decodeReplay(result: unknown): ReplayResult {
  const r = obj(result, "replay");
  str(req(r, "expected_plan_fingerprint", "replay"), "replay.expected_plan_fingerprint");
  str(req(r, "replayed_plan_fingerprint", "replay"), "replay.replayed_plan_fingerprint");
  if (typeof req(r, "match", "replay") !== "boolean") throw new DecodeError("replay.match", "expected a boolean");
  arr(req(r, "diagnostics", "replay"), "replay.diagnostics");
  return result as ReplayResult;
}

export function decodeCompare(result: unknown): CompareResult {
  const r = obj(result, "compare");
  const diff = obj(req(r, "diff", "compare"), "compare.diff");
  for (const f of ["assignment_changes", "constraint_changes", "permission_changes", "fallback_changes", "policy_digest_changes"]) {
    arr(req(diff, f, "compare.diff"), `compare.diff.${f}`);
  }
  str(req(diff, "diff_fingerprint", "compare.diff"), "compare.diff.diff_fingerprint");
  return result as CompareResult;
}

export function decodeWhatIf(result: unknown): WhatIfResult {
  const r = obj(result, "whatIf");
  validatePlan(obj(req(r, "baseline_plan", "whatIf"), "whatIf.baseline_plan"), "whatIf.baseline_plan");
  validatePlan(obj(req(r, "modified_plan", "whatIf"), "whatIf.modified_plan"), "whatIf.modified_plan");
  obj(req(r, "plan_diff", "whatIf"), "whatIf.plan_diff");
  obj(req(r, "perturbation_applied", "whatIf"), "whatIf.perturbation_applied");
  str(req(r, "baseline_state", "whatIf"), "whatIf.baseline_state");
  str(req(r, "modified_state", "whatIf"), "whatIf.modified_state");
  return result as WhatIfResult;
}

// -- Bring Your Workflow (ADR §22, BW-3) -------------------------------------- //

function bool(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") throw new DecodeError(field, "expected a boolean");
  return value;
}
function strList(value: unknown, field: string): string[] {
  return arr(value, field).map((v, i) => str(v, `${field}[${i}]`));
}
function records(value: unknown, field: string): Array<Record<string, unknown>> {
  return arr(value, field).map((v, i) => obj(v, `${field}[${i}]`));
}

export function decodeValidateWorkflow(result: unknown): ValidateWorkflowResult {
  const r = obj(result, "validate_workflow");
  const integrity = obj(req(r, "integrity", "validate_workflow"), "validate_workflow.integrity");
  return {
    validation_state: str(req(r, "validation_state", "validate_workflow"), "validate_workflow.validation_state"),
    declared_contract_version: str(req(r, "declared_contract_version", "validate_workflow"), "validate_workflow.declared_contract_version"),
    supported_version: bool(req(r, "supported_version", "validate_workflow"), "validate_workflow.supported_version"),
    supported_contracts: strList(req(r, "supported_contracts", "validate_workflow"), "validate_workflow.supported_contracts"),
    integrity: {
      checked: bool(req(integrity, "checked", "validate_workflow.integrity"), "validate_workflow.integrity.checked"),
      source_digest: typeof integrity.source_digest === "string" ? integrity.source_digest : undefined,
      computed_digest: typeof integrity.computed_digest === "string" ? integrity.computed_digest : undefined,
      match: typeof integrity.match === "boolean" ? integrity.match : undefined,
    },
    diagnostics: records(req(r, "diagnostics", "validate_workflow"), "validate_workflow.diagnostics"),
  };
}

export function decodeAdaptWorkflow(result: unknown): AdaptWorkflowResult {
  const r = obj(result, "adapt_workflow");
  const dispositions: NodeDispositionView[] = records(req(r, "node_dispositions", "adapt_workflow"), "adapt_workflow.node_dispositions").map((d, i) => {
    const f = `adapt_workflow.node_dispositions[${i}]`;
    return {
      node_id: str(req(d, "node_id", f), `${f}.node_id`),
      source_node_kind: str(req(d, "source_node_kind", f), `${f}.source_node_kind`),
      disposition: str(req(d, "disposition", f), `${f}.disposition`),
      reason_codes: strList(req(d, "reason_codes", f), `${f}.reason_codes`),
      role_id: str(req(d, "role_id", f), `${f}.role_id`),
      is_agent_role: bool(req(d, "is_agent_role", f), `${f}.is_agent_role`),
    };
  });
  const roles: RoleRequirementView[] = records(req(r, "role_requirements", "adapt_workflow"), "adapt_workflow.role_requirements").map((d, i) => {
    const f = `adapt_workflow.role_requirements[${i}]`;
    return {
      role_id: str(req(d, "role_id", f), `${f}.role_id`),
      role_name: str(req(d, "role_name", f), `${f}.role_name`),
      source_node_id: str(req(d, "source_node_id", f), `${f}.source_node_id`),
      source_node_kind: str(req(d, "source_node_kind", f), `${f}.source_node_kind`),
      required_capabilities: strList(req(d, "required_capabilities", f), `${f}.required_capabilities`),
    };
  });
  return {
    adapter_mode: str(req(r, "adapter_mode", "adapt_workflow"), "adapt_workflow.adapter_mode"),
    ok: bool(req(r, "ok", "adapt_workflow"), "adapt_workflow.ok"),
    adaptation_fingerprint: str(req(r, "adaptation_fingerprint", "adapt_workflow"), "adapt_workflow.adaptation_fingerprint"),
    adaptation_envelope_fingerprint: str(req(r, "adaptation_envelope_fingerprint", "adapt_workflow"), "adapt_workflow.adaptation_envelope_fingerprint"),
    node_dispositions: dispositions,
    role_requirements: roles,
    non_agent_dispositions: arr(req(r, "non_agent_dispositions", "adapt_workflow"), "adapt_workflow.non_agent_dispositions"),
    role_dependency_graph: req(r, "role_dependency_graph", "adapt_workflow"),
    diagnostics: records(req(r, "diagnostics", "adapt_workflow"), "adapt_workflow.diagnostics"),
    adaptation_envelope: obj(req(r, "adaptation_envelope", "adapt_workflow"), "adapt_workflow.adaptation_envelope"),
  };
}

export function decodeCompareAdaptations(result: unknown): CompareAdaptationsResult {
  const r = obj(result, "compare_adaptations");
  return {
    equivalence_state: str(req(r, "equivalence_state", "compare_adaptations"), "compare_adaptations.equivalence_state"),
    report: obj(req(r, "report", "compare_adaptations"), "compare_adaptations.report"),
    v1_adaptation_fingerprint: str(req(r, "v1_adaptation_fingerprint", "compare_adaptations"), "compare_adaptations.v1_adaptation_fingerprint"),
    v2_adaptation_fingerprint: str(req(r, "v2_adaptation_fingerprint", "compare_adaptations"), "compare_adaptations.v2_adaptation_fingerprint"),
  };
}

// -- Workflow drafts (Bring Your Workflow phase 3A, ADR §24) ------------------- //
// The v2 client has already narrowed `available`; these read the available answer and
// fail closed on any shape the backend did not promise. A typed refusal is returned as
// a value, not thrown: it is the server's answer, not a transport failure.

export function decodeDraftRefusal(result: unknown): DraftRefusal | null {
  const r = obj(result, "workflow_drafts");
  if (r.refused !== true) return null;
  return {
    refused: true,
    code: str(req(r, "code", "workflow_drafts"), "workflow_drafts.code"),
    reason: str(req(r, "reason", "workflow_drafts"), "workflow_drafts.reason"),
  };
}

function draftFields(value: unknown, field: string): WorkflowDraftFields {
  const d = obj(value, field);
  const text = (key: string) => str(req(d, key, field), `${field}.${key}`);
  const fields: WorkflowDraftFields = {
    draft_id: text("draft_id"),
    tenant_id: text("tenant_id"),
    title: text("title"),
    contract_version: text("contract_version"),
    workflow_digest: text("workflow_digest"),
    lifecycle: text("lifecycle"),
    claimed_owner_ref: text("claimed_owner_ref"),
    claimed_owner_assurance: text("claimed_owner_assurance"),
    registration_ref: text("registration_ref"),
    registration_digest: text("registration_digest"),
    supersedes: text("supersedes"),
    recorded_by: text("recorded_by"),
    validated_by: text("validated_by"),
    notes: text("notes"),
    record_version: text("record_version"),
  };
  // A record claiming any other lifecycle or assurance is not one this build can
  // show: the backend never writes one, so its arrival means something is wrong.
  if (fields.lifecycle !== "DRAFT") throw new DecodeError(`${field}.lifecycle`, `is ${fields.lifecycle}, not DRAFT`);
  if (fields.claimed_owner_assurance !== "PRESENTED_UNPROVEN") {
    throw new DecodeError(`${field}.claimed_owner_assurance`, `is ${fields.claimed_owner_assurance}, not PRESENTED_UNPROVEN`);
  }
  return fields;
}

function draftRecord(value: unknown, field: string): WorkflowDraftRecord {
  const r = obj(value, field);
  return { draft: draftFields(req(r, "draft", field), `${field}.draft`), workflow: obj(req(r, "workflow", field), `${field}.workflow`) };
}

export function decodeWorkflowDraftSaved(result: unknown): WorkflowDraftSaved {
  const f = "workflow_drafts.save";
  const r = obj(result, f);
  if (r.saved !== true) throw new DecodeError(f, "not a saved answer");
  const integrity = obj(req(r, "integrity", f), `${f}.integrity`);
  return {
    saved: true,
    draft_id: str(req(r, "draft_id", f), `${f}.draft_id`),
    workflow_digest: str(req(r, "workflow_digest", f), `${f}.workflow_digest`),
    lifecycle: str(req(r, "lifecycle", f), `${f}.lifecycle`),
    lifecycle_note: str(req(r, "lifecycle_note", f), `${f}.lifecycle_note`),
    record: draftRecord(req(r, "record", f), `${f}.record`),
    record_digest: str(req(r, "record_digest", f), `${f}.record_digest`),
    claimed_owner_status: str(req(r, "claimed_owner_status", f), `${f}.claimed_owner_status`),
    recorded_by: str(req(r, "recorded_by", f), `${f}.recorded_by`),
    validated_by: str(req(r, "validated_by", f), `${f}.validated_by`),
    integrity: {
      checked: bool(req(integrity, "checked", `${f}.integrity`), `${f}.integrity.checked`),
      source_digest: typeof integrity.source_digest === "string" ? integrity.source_digest : undefined,
      computed_digest: typeof integrity.computed_digest === "string" ? integrity.computed_digest : undefined,
      match: typeof integrity.match === "boolean" ? integrity.match : undefined,
    },
    confers: str(req(r, "confers", f), `${f}.confers`),
  };
}

export function decodeWorkflowDraftListing(result: unknown): WorkflowDraftListing {
  const f = "workflow_drafts.list";
  const r = obj(result, f);
  const rows: WorkflowDraftRow[] = arr(req(r, "result", f), `${f}.result`).map((row, i) => {
    const o = obj(row, `${f}.result[${i}]`);
    return {
      ...draftFields(o, `${f}.result[${i}]`),
      superseded_by: str(req(o, "superseded_by", f), `${f}.result[${i}].superseded_by`),
      record_digest: str(req(o, "record_digest", f), `${f}.result[${i}].record_digest`),
    };
  });
  return {
    count: num(req(r, "count", f), `${f}.count`),
    include_superseded: bool(req(r, "include_superseded", f), `${f}.include_superseded`),
    lifecycle_note: str(req(r, "lifecycle_note", f), `${f}.lifecycle_note`),
    claimed_owner_status: str(req(r, "claimed_owner_status", f), `${f}.claimed_owner_status`),
    confers: str(req(r, "confers", f), `${f}.confers`),
    result: rows,
  };
}

export function decodeWorkflowDraftRead(result: unknown): WorkflowDraftRead {
  const f = "workflow_drafts.read";
  const r = obj(result, f);
  const found = bool(req(r, "found", f), `${f}.found`);
  return {
    found,
    draft_id: str(req(r, "draft_id", f), `${f}.draft_id`),
    record: found ? draftRecord(req(r, "record", f), `${f}.record`) : null,
    lineage: found ? strList(req(r, "lineage", f), `${f}.lineage`) : [],
    superseded_by: found ? str(req(r, "superseded_by", f), `${f}.superseded_by`) : "",
  };
}
