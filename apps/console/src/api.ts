/**
 * Console API client — talks to ugence_console_api (proxied under /api in dev).
 *
 * The packaged service serves five routes and no more (ruling CP-3, asserted by
 * `packages/integration/console-api/tests/test_served_surface.py`). Under ruling MA-4
 * this client calls exactly those five: `/v1/modules` and `/v1/scenarios` were withheld
 * by CP-3 and are no longer called from here. A view that used to read them shows a
 * typed gap instead.
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
  /** CP-4: the service declares its audit ceiling in the health body and on every answer. */
  audit_ceiling: string;
  modules: Record<string, { available: boolean; reason: string }>;
}

export const api = {
  health: () => get<Health>('/health'),
  runScenario: (id: string) =>
    post<GovernedLoopResult>(`/v1/governed-loop/scenario/${id}`),
  auditIds: () => get<string[]>('/v1/audit'),
  auditChain: (correlationId: string) =>
    get<AuditChain>(`/v1/audit/${correlationId}`),
};
