// Typed HTTP client (§4, §8). Talks ONLY to the configured Governance Studio API.
// It fetches, validates compatibility, and returns typed view-models — it never
// computes a domain outcome. Filtering/sorting live in the UI, not here.
import { apiBaseUrl } from "@/lib/config";
import type {
  ApiResponseEnvelope,
  EligibilityResult,
  ExplanationResult,
  ReadinessInfo,
  RegistryResult,
  ScenarioDetailResult,
  ScenariosResult,
  VersionInfo,
  WorkflowResult,
} from "./types";

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly detail?: unknown;
  constructor(status: number, code: string, message: string, requestId?: string, detail?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.detail = detail;
  }
}

/**
 * The deployment request header (P3E §15). The private hosted profile refuses a
 * mutating `/api` request that does not carry it: a cross-origin request constraint,
 * not authorization. It rides every mutating request and no read, and only when the
 * API is this page's own origin, which is the only shape the hosted profile serves
 * (its CSP is `connect-src 'self'`). A cross-origin API such as the plain studio-api
 * allowlists `Content-Type` alone, and an extra header there would fail its CORS
 * preflight for nothing.
 */
export const DEPLOYMENT_REQUEST_HEADER = "X-Ugence-Request";
export const DEPLOYMENT_REQUEST_VALUE = "GovernanceStudio";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

export function deploymentHeaders(
  method: string | undefined,
  pageOrigin: string | undefined = globalThis.location?.origin,
  base: string = apiBaseUrl,
): Record<string, string> {
  if (SAFE_METHODS.has((method ?? "GET").toUpperCase())) return {};
  let apiOrigin: string;
  try {
    apiOrigin = new URL(base).origin;
  } catch {
    return {};
  }
  if (!pageOrigin || apiOrigin !== pageOrigin) return {};
  return { [DEPLOYMENT_REQUEST_HEADER]: DEPLOYMENT_REQUEST_VALUE };
}

async function request<T>(pathAndQuery: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${pathAndQuery}`, {
      ...init,
      headers: { Accept: "application/json", ...deploymentHeaders(init?.method), ...(init?.headers ?? {}) },
    });
  } catch (err) {
    throw new ApiClientError(0, "network_error", "the Governance Studio API is unreachable", undefined, err);
  }
  const text = await response.text();
  let body: unknown = undefined;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = undefined;
    }
  }
  if (!response.ok) {
    const errObj = (body as { error?: { code?: string; message?: string; request_id?: string } })?.error;
    throw new ApiClientError(
      response.status,
      errObj?.code ?? "http_error",
      errObj?.message ?? `request failed with status ${response.status}`,
      errObj?.request_id,
      body,
    );
  }
  return body as T;
}

async function envelope<T>(pathAndQuery: string, init?: RequestInit): Promise<ApiResponseEnvelope<T>> {
  return request<ApiResponseEnvelope<T>>(pathAndQuery, init);
}

// -- operational -----------------------------------------------------------
export const getHealth = () => request<{ status: string }>("/health");
export const getReady = () => request<ReadinessInfo>("/ready");
export const getVersion = () => request<VersionInfo>("/version");

// -- scenarios -------------------------------------------------------------
export const listScenarios = () =>
  envelope<ScenariosResult>("/api/v1/scenarios").then((e) => e.result);

export const getScenario = (id: string) =>
  envelope<ScenarioDetailResult>(`/api/v1/scenarios/${encodeURIComponent(id)}`).then((e) => e.result);

export const getScenarioWorkflow = (id: string) =>
  envelope<WorkflowResult>(`/api/v1/scenarios/${encodeURIComponent(id)}/workflow`).then((e) => e.result);

export const getScenarioRegistry = (id: string) =>
  envelope<RegistryResult>(`/api/v1/scenarios/${encodeURIComponent(id)}/registry`).then((e) => e.result);

export const getScenarioEligibility = (id: string, verifyExpected = true) =>
  envelope<EligibilityResult>(
    `/api/v1/scenarios/${encodeURIComponent(id)}/eligibility?verify_expected=${verifyExpected}`,
  ).then((e) => e.result);

// -- explanations (the only POST P3C uses) ---------------------------------
export const explainEligibility = (scenarioId: string, roleId?: string) =>
  envelope<ExplanationResult>("/api/v1/explanations/eligibility", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(roleId ? { scenario_id: scenarioId, role_id: roleId } : { scenario_id: scenarioId }),
  }).then((e) => e.result);

// -- P3D planning endpoints (decoded at the boundary) ----------------------
import {
  decodeAdaptWorkflow,
  decodeCompare,
  decodeCompareAdaptations,
  decodeExplainPlan,
  decodePlan,
  decodeRanking,
  decodeReplay,
  decodeValidateWorkflow,
  decodeWhatIf,
} from "./decoders";
import type { AdaptWorkflowResult, CompareAdaptationsResult, ValidateWorkflowResult } from "./types-bring";

export interface PlanSource {
  scenario_id: string;
  logical_time?: number;
  perturbation?: { operation: string; params: Record<string, unknown> };
}

const enc = encodeURIComponent;
const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getScenarioRanking = (id: string) =>
  envelope<unknown>(`/api/v1/scenarios/${enc(id)}/ranking`).then((e) => decodeRanking(e.result));

export const getScenarioPlan = (id: string) =>
  envelope<unknown>(`/api/v1/scenarios/${enc(id)}/plan`).then((e) => decodePlan(e.result));

export const explainPlan = (scenarioId: string) =>
  envelope<unknown>("/api/v1/explanations/plan", postJson({ scenario_id: scenarioId })).then((e) =>
    decodeExplainPlan(e.result),
  );

export const explainRanking = (scenarioId: string) =>
  envelope<unknown>("/api/v1/explanations/ranking", postJson({ scenario_id: scenarioId })).then(
    (e) => e.result,
  );

export const replayPlan = (scenarioId: string, expectedPlan?: Record<string, unknown>) =>
  envelope<unknown>(
    "/api/v1/plans/replay",
    postJson(expectedPlan ? { scenario_id: scenarioId, expected_plan: expectedPlan } : { scenario_id: scenarioId }),
  ).then((e) => decodeReplay(e.result));

export const comparePlans = (left: PlanSource, right: PlanSource) =>
  envelope<unknown>("/api/v1/plans/compare", postJson({ left, right })).then((e) => decodeCompare(e.result));

export const scenarioWhatIf = (id: string, operation: string, params: Record<string, unknown>) =>
  envelope<unknown>(`/api/v1/scenarios/${enc(id)}/what-if`, postJson({ operation, params })).then((e) =>
    decodeWhatIf(e.result),
  );

export const getScenarioExport = (id: string) =>
  envelope<Record<string, unknown>>(`/api/v1/scenarios/${enc(id)}/export`).then((e) => e.result);

// -- Bring Your Workflow (ADR §22, BW-3: validate, adapt, compare only) ------- //
// The operator's document is the request body and nothing else: no scenario id, no
// overlay, no URL. Each answer is the whole envelope (request id, awc version, input
// digests) with the result decoded, so the screen's downloadable report is the
// server's own record and not a reassembly.
export const validateWorkflow = (workflow: Record<string, unknown>, contractVersion: string, sourceDigest?: string) =>
  envelope<unknown>(
    "/api/v1/workflows/validate",
    postJson(sourceDigest ? { contract_version: contractVersion, workflow, source_digest: sourceDigest } : { contract_version: contractVersion, workflow }),
  ).then((e): ApiResponseEnvelope<ValidateWorkflowResult> => ({ ...e, result: decodeValidateWorkflow(e.result) }));

export const adaptWorkflow = (workflow: Record<string, unknown>, contractVersion: string) =>
  envelope<unknown>("/api/v1/workflows/adapt", postJson({ workflow, contract_version: contractVersion })).then(
    (e): ApiResponseEnvelope<AdaptWorkflowResult> => ({ ...e, result: decodeAdaptWorkflow(e.result) }),
  );

export const compareAdaptations = (v1Workflow: Record<string, unknown>, v2Workflow: Record<string, unknown>) =>
  envelope<unknown>("/api/v1/workflows/compare-adaptations", postJson({ v1_workflow: v1Workflow, v2_workflow: v2Workflow })).then(
    (e): ApiResponseEnvelope<CompareAdaptationsResult> => ({ ...e, result: decodeCompareAdaptations(e.result) }),
  );
