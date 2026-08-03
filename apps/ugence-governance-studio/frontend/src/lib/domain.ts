// Deterministic presentation mappings (§13, §20). Every human-readable label is a
// fixed mapping of an API-provided code; unknown codes fall back to a normalized
// form of the raw code. NO reason, condition or disposition is invented here, and
// no LLM is involved.

export interface Descriptor {
  code: string;
  label: string;
  /** Tailwind text/border color token key under `state.*`. */
  tone: string;
  /** A non-color glyph so state is never conveyed by color alone (§23). */
  glyph: string;
}

// -- workflow node dispositions (the 8 canonical AWC categories) -----------
export const DISPOSITIONS: Record<string, Descriptor> = {
  AI_AGENT_ELIGIBLE: { code: "AI_AGENT_ELIGIBLE", label: "AI-agent role", tone: "eligible", glyph: "◆" },
  NO_AI_AGENT_REQUIRED: { code: "NO_AI_AGENT_REQUIRED", label: "No agent required", tone: "deterministic", glyph: "○" },
  DETERMINISTIC_SERVICE_PREFERRED: { code: "DETERMINISTIC_SERVICE_PREFERRED", label: "Deterministic service", tone: "deterministic", glyph: "▣" },
  HUMAN_AUTHORITY_REQUIRED: { code: "HUMAN_AUTHORITY_REQUIRED", label: "Human authority", tone: "authority", glyph: "◈" },
  HUMAN_REVIEW_REQUIRED: { code: "HUMAN_REVIEW_REQUIRED", label: "Human review", tone: "review", glyph: "⬡" },
  EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP: { code: "EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP", label: "Governance-owned", tone: "governance", glyph: "⬢" },
  UNSUPPORTED_NODE: { code: "UNSUPPORTED_NODE", label: "Unsupported", tone: "invalid", glyph: "▲" },
  INVALID_NODE: { code: "INVALID_NODE", label: "Invalid", tone: "ineligible", glyph: "✕" },
};

export function disposition(code: string): Descriptor {
  return DISPOSITIONS[code] ?? { code, label: normalizeCode(code), tone: "deterministic", glyph: "•" };
}

// -- eligibility states ----------------------------------------------------
export const ELIGIBILITY_STATES: Record<string, Descriptor> = {
  ELIGIBLE: { code: "ELIGIBLE", label: "Eligible", tone: "eligible", glyph: "✓" },
  INELIGIBLE: { code: "INELIGIBLE", label: "Ineligible", tone: "ineligible", glyph: "✕" },
  ELIMINATED: { code: "ELIMINATED", label: "Ineligible", tone: "ineligible", glyph: "✕" },
  INDETERMINATE: { code: "INDETERMINATE", label: "Indeterminate", tone: "indeterminate", glyph: "?" },
  INVALID_INPUT: { code: "INVALID_INPUT", label: "Invalid input", tone: "invalid", glyph: "!" },
};

export function eligibilityState(code: string): Descriptor {
  return ELIGIBILITY_STATES[code] ?? { code, label: normalizeCode(code), tone: "indeterminate", glyph: "?" };
}

// -- elimination reason codes → readable labels (deterministic) ------------
export const REASON_LABELS: Record<string, string> = {
  MISSING_REQUIRED_CAPABILITY: "Missing a required capability",
  CAPABILITY_EVIDENCE_EXPIRED: "Capability evidence has expired",
  DECLARED_ONLY_WHEN_MEASURED_REQUIRED: "Only declared evidence where measured evidence is required",
  INPUT_CONTRACT_INCOMPATIBLE: "Input contract is incompatible",
  OUTPUT_CONTRACT_INCOMPATIBLE: "Output contract is incompatible",
  TOOL_NOT_ALLOWED: "Uses a tool that is not allowed",
  PROVIDER_FORBIDDEN: "Provider is forbidden by enterprise policy",
  RESIDENCY_MISMATCH: "Residency does not satisfy the requirement",
  DEPLOYMENT_ENVIRONMENT_MISMATCH: "Deployment environment does not match",
  SECURITY_REQUIREMENT_NOT_MET: "Security requirement not met",
  SECURITY_CLASSIFICATION_INSUFFICIENT: "Security classification is insufficient",
  AUDIT_REQUIREMENT_NOT_MET: "Audit requirement not met",
  PERMISSION_REQUIREMENT_EXCEEDS_POLICY: "Required permissions exceed policy",
  AUTHORITY_REQUIREMENT_EXCEEDS_CEILING: "Authority requirement exceeds the ceiling",
  COST_CEILING_EXCEEDED: "Cost ceiling exceeded",
  LATENCY_CEILING_EXCEEDED: "Latency ceiling exceeded",
  QUALITY_FLOOR_NOT_MET: "Quality floor not met",
};

export function reasonLabel(code: string): string {
  return REASON_LABELS[code] ?? normalizeCode(code);
}

// -- evidence classes ------------------------------------------------------
export const EVIDENCE_CLASSES = ["DECLARED", "MEASURED", "OBSERVED"] as const;

// -- source provenance badges (§16) ----------------------------------------
export type SourceBadge = "COMPILER" | "ENTERPRISE_POLICY" | "AWC_DERIVED" | "DEFERRED" | "UNRESOLVED";

export const SOURCE_BADGE_LABELS: Record<SourceBadge, string> = {
  COMPILER: "Compiler",
  ENTERPRISE_POLICY: "Enterprise policy",
  AWC_DERIVED: "AWC-derived",
  DEFERRED: "Deferred",
  UNRESOLVED: "Unresolved",
};

// A condition is a bare name (passed) or a ConditionResult object (failed/unknown).
export function conditionName(c: unknown): string {
  if (typeof c === "string") return c;
  if (c && typeof c === "object" && "condition" in c) return String((c as { condition: unknown }).condition);
  return String(c);
}

export function conditionReason(c: unknown): string | undefined {
  if (c && typeof c === "object" && "reason" in c) {
    const r = (c as { reason?: unknown }).reason;
    return r ? String(r) : undefined;
  }
  return undefined;
}

export function normalizeCode(code: string): string {
  if (!code) return "—";
  const lower = code.replace(/_/g, " ").toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

// Human-readable "unresolved" rendering (§15). Distinguishes empty vs deferred.
export function displayOrUnresolved(value: unknown, kind: "list" | "scalar" = "scalar"): string {
  if (value === null || value === undefined || value === "") return "Not supplied";
  if (Array.isArray(value)) return value.length ? value.join(", ") : "None";
  if (kind === "scalar" && typeof value === "object") return JSON.stringify(value);
  return String(value);
}
