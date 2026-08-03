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
