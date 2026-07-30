/**
 * Console API client — talks to ugence_console_api (proxied under /api in dev).
 */

const BASE = import.meta.env.VITE_CONSOLE_API_URL || '/api';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// ---- types (mirror ugence_console_api/models.py) ------------------------- //
export interface ModuleInfo {
  key: string;
  name: string;
  layer: string;
  capability: string;
  maturity: string;
  wiring: 'loop' | 'standalone' | 'read-only';
  question: string;
}

export interface ScenarioSummary {
  id: string;
  title: string;
  description: string;
}

export interface StageResult {
  stage: string;
  capability: string;
  module: string;
  module_maturity: string;
  question: string;
  decision: string;
  summary: string;
  detail: Record<string, unknown>;
}

export interface GovernedLoopResult {
  correlation_id: string;
  cer_id: string;
  mode: string;
  stages: StageResult[];
  final_disposition: string;
  would_execute: boolean;
  recorded: boolean;
}

export interface AuditEntry {
  stage: string;
  module: string;
  decision: string;
  summary: string;
  detail: Record<string, unknown>;
}

export interface AuditChain {
  correlation_id: string;
  cer_id: string;
  mode: string;
  final_disposition: string;
  entries: AuditEntry[];
}

export interface Health {
  status: string;
  version: string;
  modules: Record<string, { available: boolean; reason: string }>;
}

export const api = {
  health: () => get<Health>('/health'),
  modules: () => get<ModuleInfo[]>('/v1/modules'),
  scenarios: () => get<ScenarioSummary[]>('/v1/scenarios'),
  runScenario: (id: string) =>
    post<GovernedLoopResult>(`/v1/governed-loop/scenario/${id}`),
  auditIds: () => get<string[]>('/v1/audit'),
  auditChain: (correlationId: string) =>
    get<AuditChain>(`/v1/audit/${correlationId}`),
};
