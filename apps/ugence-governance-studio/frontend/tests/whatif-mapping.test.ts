import { describe, expect, it } from "vitest";
import {
  OPERATION_SPECS,
  ORDERED_SPECS,
  PERMISSION_CHOICES,
  seedDefaults,
  type WhatIfOptions,
} from "@/features/whatif/operations";
import { WHAT_IF_OPERATIONS } from "@/api/types-p3d";

const OPTIONS: WhatIfOptions = {
  providers: ["openai", "anthropic", "cohere"],
  residencies: ["EU", "US", "IN"],
  agentRefs: ["agent_alpha@1.0.0", "agent_beta@2.1.0"],
  permissions: PERMISSION_CHOICES,
};

// Exact request mapping expected per operation (§C2). Param NAMES and TYPES mirror
// the backend apply_perturbation contract, NOT the UI labels.
const OK = (params: Record<string, unknown>) => ({ params });
const CASES: Record<string, { values: Record<string, string>; expect: Record<string, unknown>; paramKeys: string[]; paramTypes: Record<string, string> }> = {
  FORBID_PROVIDER: { values: { provider: "anthropic" }, expect: { provider: "anthropic" }, paramKeys: ["provider"], paramTypes: { provider: "string" } },
  REQUIRE_RESIDENCY: { values: { residency: "EU" }, expect: { residency: "EU" }, paramKeys: ["residency"], paramTypes: { residency: "string" } },
  TIGHTEN_COST_CEILING: { values: { ceiling: "12.5" }, expect: { ceiling: 12.5 }, paramKeys: ["ceiling"], paramTypes: { ceiling: "number" } },
  TIGHTEN_LATENCY_CEILING: { values: { ceiling: "800" }, expect: { ceiling: 800 }, paramKeys: ["ceiling"], paramTypes: { ceiling: "number" } },
  REVOKE_AGENT_VERSION: { values: { agent_version: "agent_beta@2.1.0" }, expect: { agent_version: "agent_beta@2.1.0" }, paramKeys: ["agent_version"], paramTypes: { agent_version: "string" } },
  EXPIRE_EVIDENCE: { values: {}, expect: {}, paramKeys: [], paramTypes: {} },
  TIGHTEN_PERMISSION_POLICY: { values: { permission: "invoke_tool" }, expect: { permission: "invoke_tool" }, paramKeys: ["permission"], paramTypes: { permission: "string" } },
  TIGHTEN_PROVIDER_CONCENTRATION: { values: { limit_pct: "40" }, expect: { limit_pct: 40 }, paramKeys: ["limit_pct"], paramTypes: { limit_pct: "number" } },
  REMOVE_CANDIDATE: { values: { candidate: "agent_alpha@1.0.0" }, expect: { agent_id: "agent_alpha", agent_version: "1.0.0" }, paramKeys: ["agent_id", "agent_version"], paramTypes: { agent_id: "string", agent_version: "string" } },
};

describe("C2 — what-if request mapping (all nine operations)", () => {
  it("exactly nine operations, in the allowlisted order", () => {
    expect(ORDERED_SPECS.map((s) => s.operation)).toEqual([...WHAT_IF_OPERATIONS]);
    expect(Object.keys(OPERATION_SPECS).sort()).toEqual([...WHAT_IF_OPERATIONS].sort());
  });

  for (const op of WHAT_IF_OPERATIONS) {
    const c = CASES[op];
    describe(op, () => {
      it("builds the exact operation payload with exact param names", () => {
        const r = OPERATION_SPECS[op].build(c.values, OPTIONS);
        expect(r).toEqual(OK(c.expect));
        if ("params" in r) {
          expect(Object.keys(r.params).sort()).toEqual([...c.paramKeys].sort());
          for (const k of c.paramKeys) expect(typeof r.params[k]).toBe(c.paramTypes[k]);
        }
      });

      it("declares only the controls it needs", () => {
        const keys = OPERATION_SPECS[op].controls.map((ctl) => ctl.key);
        // control keys are unique and relevant; EXPIRE_EVIDENCE has none
        expect(new Set(keys).size).toBe(keys.length);
        if (op === "EXPIRE_EVIDENCE") expect(keys).toEqual([]);
        else expect(keys.length).toBeGreaterThan(0);
      });

      it("ignores stale parameters from other operations", () => {
        // foreign keys from OTHER operations present, but THIS operation's own
        // values win — build must serialize only this operation's params.
        const foreign = { provider: "openai", residency: "US", ceiling: "1", limit_pct: "2", candidate: "agent_beta@2.1.0", permission: "read_context" };
        const polluted = { ...foreign, ...c.values };
        const r = OPERATION_SPECS[op].build(polluted, OPTIONS);
        // still valid, and only THIS operation's keys are serialized
        expect("params" in r).toBe(true);
        if ("params" in r) {
          for (const k of Object.keys(r.params)) expect(c.paramKeys).toContain(k);
        }
      });
    });
  }

  it("seedDefaults picks the first allowed option for selects and leaves numbers empty", () => {
    expect(seedDefaults("FORBID_PROVIDER", OPTIONS)).toEqual({ provider: "openai" });
    expect(seedDefaults("TIGHTEN_COST_CEILING", OPTIONS)).toEqual({}); // number stays required
    expect(seedDefaults("REMOVE_CANDIDATE", OPTIONS)).toEqual({ candidate: "agent_alpha@1.0.0" });
    expect(seedDefaults("EXPIRE_EVIDENCE", OPTIONS)).toEqual({});
  });
});

describe("C2 — negative cases (bounded input, allowlist rejection)", () => {
  const err = (op: string, values: Record<string, string>) => {
    const r = OPERATION_SPECS[op as keyof typeof OPERATION_SPECS].build(values, OPTIONS);
    expect("error" in r).toBe(true);
  };

  it("missing required select", () => err("FORBID_PROVIDER", {}));
  it("missing required number", () => err("TIGHTEN_COST_CEILING", {}));
  it("provider not in pinned registry rejected", () => err("FORBID_PROVIDER", { provider: "rogue-provider" }));
  it("agent not in pinned registry rejected", () => err("REVOKE_AGENT_VERSION", { agent_version: "ghost@0.0.0" }));
  it("candidate not in pinned registry rejected", () => err("REMOVE_CANDIDATE", { candidate: "ghost@0.0.0" }));
  it("arbitrary permission text rejected", () => err("TIGHTEN_PERMISSION_POLICY", { permission: "sudo_everything" }));
  it("malformed number rejected", () => err("TIGHTEN_COST_CEILING", { ceiling: "abc" }));
  it("negative number rejected", () => err("TIGHTEN_COST_CEILING", { ceiling: "-5" }));
  it("non-integer percentage rejected", () => err("TIGHTEN_PROVIDER_CONCENTRATION", { limit_pct: "12.5" }));
  it("out-of-range percentage rejected", () => err("TIGHTEN_PROVIDER_CONCENTRATION", { limit_pct: "150" }));

  it("switching operation then building uses only the new operation's schema (no cross-operation params)", () => {
    // simulate REMOVE_CANDIDATE values leaking into a FORBID_PROVIDER build
    const r = OPERATION_SPECS.FORBID_PROVIDER.build({ candidate: "agent_alpha@1.0.0", provider: "cohere" }, OPTIONS);
    expect(r).toEqual({ params: { provider: "cohere" } });
  });
});
