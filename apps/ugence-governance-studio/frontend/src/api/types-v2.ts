// View-model types for the v2 contract, derived from the GENERATED client.
//
// Every request body shape is taken from `@/generated/api-v2` rather than written
// here: a hand-written request type drifts the moment the contract moves, and the
// drift is invisible until a request is rejected at runtime.
//
// The response types below are the studio's own reading of the envelope's `result`
// field, which the contract types as `unknown` — the backend passes package results
// through intact rather than re-declaring them. They are narrow on purpose and are
// validated at the boundary by `decodeGap`.
import type { operations } from "@/generated/api-v2";

/**
 * The response envelope.
 *
 * Declared here rather than read from the generated contract because the studio API
 * does not type its 200 responses — every route emits `"schema": {}`. That is a
 * pre-existing property of v1, which v2 inherits by using the same envelope, and it
 * is why v1 also carries hand-written response view-models in `types.ts`.
 *
 * `[G]` The consequence is worth stating plainly: request bodies below are generated
 * and cannot drift, while this shape is the studio's own reading and could. Closing
 * it means declaring `response_model` on the routes so the contract describes the
 * envelope — a backend change, and a real improvement over v1 rather than parity
 * with it.
 */
export interface V2Envelope {
  api_version: string;
  request_id: string;
  operation: string;
  awc_version: string;
  result: unknown;
  diagnostics: { code: string; message: string; severity?: string }[];
  warnings: string[];
  maturity: Record<string, unknown>;
}

// -- request bodies, straight from the generated contract -------------------
type Body<O extends keyof operations> = operations[O] extends {
  requestBody: { content: { "application/json": infer B } };
}
  ? B
  : never;

export type ConstitutionValidateBody = Body<"v2_constitution_validate">;
export type ConstitutionPreflightBody = Body<"v2_constitution_preflight">;
export type PolicyPackBody = Body<"v2_policy_validate">;
export type PolicyCompileBody = Body<"v2_policy_compile">;
export type SimulateRunBody = Body<"v2_simulate_run">;
export type PublishShadowBody = Body<"v2_publish_shadow">;

// -- the gap contract -------------------------------------------------------
/**
 * Every v2 service reports a missing dependency the same way, and every screen
 * renders it rather than hiding it. `available: false` is not an error state and
 * not an empty state — it is a statement about this deployment that the operator
 * needs to see.
 */
export interface Unavailable {
  available: false;
  capability: string;
  reason: string;
  result: null;
}

export interface Available {
  available: true;
  [key: string]: unknown;
}

export type GapAware = Unavailable | Available;

export function isUnavailable(value: unknown): value is Unavailable {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as { available?: unknown }).available === false
  );
}

/** Narrow an unknown `result` into the gap contract, failing closed on anything else. */
export function decodeGap(result: unknown): GapAware {
  if (isUnavailable(result)) {
    return {
      available: false,
      capability: String((result as Unavailable).capability ?? "unknown"),
      reason: String((result as Unavailable).reason ?? "no reason reported"),
      result: null,
    };
  }
  if (typeof result === "object" && result !== null && (result as { available?: unknown }).available === true) {
    return result as Available;
  }
  // A result that reports neither is treated as unavailable rather than rendered as
  // success: a screen that showed an unrecognised shape as a result would be
  // inventing an answer the backend did not give.
  return {
    available: false,
    capability: "unrecognised_result",
    reason: "the API returned a result shape this build does not recognise",
    result: null,
  };
}

// -- screen-specific readings ----------------------------------------------
export interface ConstitutionValidation extends Available {
  validation_state: "VALID" | "INVALID";
  diagnostics: { code: string; message: string }[];
  digest: string;
  constitution_id?: string | null;
}

export interface PolicyCompileResult extends Available {
  success: boolean;
  logical_digest: string;
  workflow_ir: unknown;
  assurance_manifest: unknown;
  audit_schema: unknown;
  compiled_package: unknown;
}

export interface AuthorityPolicies extends Available {
  result: unknown[];
  /** Which registry answered. `InMemoryPolicyRegistry` shows one process's view. */
  registry_kind: string;
  identities_queried: string[];
}

export interface SimulationRun extends Available {
  execution_mode: string;
  instance_id: string;
  governance_hook_configured: boolean;
  /** True when a permissive test hook cleared the run. Never a governance result. */
  governance_hook_permissive: boolean;
  quanta: Record<string, unknown>[];
}
