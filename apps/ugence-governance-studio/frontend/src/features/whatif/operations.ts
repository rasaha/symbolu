// Single source of truth for the nine controlled what-if operations (§25, C2).
//
// Each spec declares its bounded controls and a pure `build()` that maps validated
// field values to the EXACT backend parameter names/types. The browser never
// computes a planning outcome here — it only assembles a validated request the
// backend evaluates on a temporary copy. Parameter names/types mirror the backend
// `apply_perturbation` contract (orchestration.py): provider, residency, ceiling,
// agent_version, permission, limit_pct, agent_id(+agent_version).
import type { WhatIfOperation } from "@/api/types-p3d";
import { WHAT_IF_OPERATIONS } from "@/api/types-p3d";

export const PERMISSION_CHOICES = ["read_context", "write_context", "invoke_tool"] as const;

export interface WhatIfOptions {
  providers: string[];
  residencies: string[];
  agentRefs: string[]; // "agent_id@agent_version"
  permissions: readonly string[];
}

export interface SelectControl {
  key: string;
  kind: "select";
  label: string;
  options: (o: WhatIfOptions) => string[];
}
export interface NumberControl {
  key: string;
  kind: "number";
  label: string;
  min: number;
  max?: number;
  integer: boolean;
}
export type WhatIfControl = SelectControl | NumberControl;

export type BuildResult = { params: Record<string, unknown> } | { error: string };

export interface OperationSpec {
  operation: WhatIfOperation;
  summary: string;
  controls: WhatIfControl[];
  build(values: Record<string, string>, o: WhatIfOptions): BuildResult;
}

// -- validation helpers ----------------------------------------------------
function reqSelect(values: Record<string, string>, key: string, choices: string[]): string | { error: string } {
  const v = values[key];
  if (v === undefined || v === "") return { error: `${key} is required` };
  if (!choices.includes(v)) return { error: `${key} "${v}" is not an allowed value` };
  return v;
}
function reqNumber(
  values: Record<string, string>,
  key: string,
  { min, max, integer }: { min: number; max?: number; integer: boolean },
): number | { error: string } {
  const raw = values[key];
  if (raw === undefined || raw.trim() === "") return { error: `${key} is required` };
  const n = Number(raw);
  if (!Number.isFinite(n)) return { error: `${key} must be a finite number` };
  if (integer && !Number.isInteger(n)) return { error: `${key} must be an integer` };
  if (n < min) return { error: `${key} must be >= ${min}` };
  if (max !== undefined && n > max) return { error: `${key} must be <= ${max}` };
  return n;
}
const isErr = (v: unknown): v is { error: string } => typeof v === "object" && v !== null && "error" in v;

// -- specs -----------------------------------------------------------------
const providerOpts = (o: WhatIfOptions) => o.providers;
const residencyOpts = (o: WhatIfOptions) => o.residencies;
const agentOpts = (o: WhatIfOptions) => o.agentRefs;
const permissionOpts = (o: WhatIfOptions) => [...o.permissions];

export const OPERATION_SPECS: Record<WhatIfOperation, OperationSpec> = {
  FORBID_PROVIDER: {
    operation: "FORBID_PROVIDER",
    summary: "Add a provider to the enterprise forbidden-providers list.",
    controls: [{ key: "provider", kind: "select", label: "provider", options: providerOpts }],
    build(v, o) {
      const provider = reqSelect(v, "provider", providerOpts(o));
      if (isErr(provider)) return provider;
      return { params: { provider } };
    },
  },
  REQUIRE_RESIDENCY: {
    operation: "REQUIRE_RESIDENCY",
    summary: "Require a data residency; only that residency becomes allowed.",
    controls: [{ key: "residency", kind: "select", label: "residency", options: residencyOpts }],
    build(v, o) {
      const residency = reqSelect(v, "residency", residencyOpts(o));
      if (isErr(residency)) return residency;
      return { params: { residency } };
    },
  },
  TIGHTEN_COST_CEILING: {
    operation: "TIGHTEN_COST_CEILING",
    summary: "Lower the team cost hard ceiling.",
    controls: [{ key: "ceiling", kind: "number", label: "cost ceiling", min: 0, integer: false }],
    build(v) {
      const ceiling = reqNumber(v, "ceiling", { min: 0, integer: false });
      if (isErr(ceiling)) return ceiling;
      return { params: { ceiling } };
    },
  },
  TIGHTEN_LATENCY_CEILING: {
    operation: "TIGHTEN_LATENCY_CEILING",
    summary: "Lower the team latency hard ceiling.",
    controls: [{ key: "ceiling", kind: "number", label: "latency ceiling", min: 0, integer: false }],
    build(v) {
      const ceiling = reqNumber(v, "ceiling", { min: 0, integer: false });
      if (isErr(ceiling)) return ceiling;
      return { params: { ceiling } };
    },
  },
  REVOKE_AGENT_VERSION: {
    operation: "REVOKE_AGENT_VERSION",
    summary: "Forbid a specific agent version.",
    controls: [{ key: "agent_version", kind: "select", label: "agent@version", options: agentOpts }],
    build(v, o) {
      const agent_version = reqSelect(v, "agent_version", agentOpts(o));
      if (isErr(agent_version)) return agent_version;
      return { params: { agent_version } };
    },
  },
  EXPIRE_EVIDENCE: {
    operation: "EXPIRE_EVIDENCE",
    summary: "Advance logical time past evidence validity (no parameters).",
    controls: [],
    build() {
      return { params: {} };
    },
  },
  TIGHTEN_PERMISSION_POLICY: {
    operation: "TIGHTEN_PERMISSION_POLICY",
    summary: "Mark a predefined permission as governance-owned.",
    controls: [{ key: "permission", kind: "select", label: "permission", options: permissionOpts }],
    build(v) {
      const permission = reqSelect(v, "permission", [...PERMISSION_CHOICES]);
      if (isErr(permission)) return permission;
      return { params: { permission } };
    },
  },
  TIGHTEN_PROVIDER_CONCENTRATION: {
    operation: "TIGHTEN_PROVIDER_CONCENTRATION",
    summary: "Lower the maximum provider-concentration percentage.",
    controls: [{ key: "limit_pct", kind: "number", label: "limit %", min: 0, max: 100, integer: true }],
    build(v) {
      const limit_pct = reqNumber(v, "limit_pct", { min: 0, max: 100, integer: true });
      if (isErr(limit_pct)) return limit_pct;
      return { params: { limit_pct } };
    },
  },
  REMOVE_CANDIDATE: {
    operation: "REMOVE_CANDIDATE",
    summary: "Remove a candidate agent (and its evidence) from the registry copy.",
    controls: [{ key: "candidate", kind: "select", label: "candidate (agent@version)", options: agentOpts }],
    build(v, o) {
      const candidate = reqSelect(v, "candidate", agentOpts(o));
      if (isErr(candidate)) return candidate;
      const at = candidate.indexOf("@");
      const agent_id = at >= 0 ? candidate.slice(0, at) : candidate;
      const agent_version = at >= 0 ? candidate.slice(at + 1) : "";
      return { params: { agent_id, agent_version } };
    },
  },
};

// Ordered specs matching the allowlisted operation order.
export const ORDERED_SPECS: OperationSpec[] = WHAT_IF_OPERATIONS.map((op) => OPERATION_SPECS[op]);

// Seed default field values for an operation so the displayed selection equals what
// will be submitted (selects default to their first option; numbers stay empty and
// therefore remain required — never silently defaulted).
export function seedDefaults(op: WhatIfOperation, o: WhatIfOptions): Record<string, string> {
  const out: Record<string, string> = {};
  for (const c of OPERATION_SPECS[op].controls) {
    if (c.kind === "select") {
      const opts = c.options(o);
      if (opts.length) out[c.key] = opts[0];
    }
  }
  return out;
}
