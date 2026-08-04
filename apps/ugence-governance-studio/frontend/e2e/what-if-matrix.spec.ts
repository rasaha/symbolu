import { test, expect, request as pwRequest } from "@playwright/test";

// C2 — exercise all nine controlled what-if operations against the REAL backend and
// prove: every operation returns HTTP 200; the baseline fingerprint is identical
// across all nine (the frozen scenario is never mutated); each perturbation yields a
// distinct modified plan.
const API = "http://127.0.0.1:8000";
const SCENARIO = "procurement";

test("all nine what-if operations map correctly against the real backend", async () => {
  const api = await pwRequest.newContext({ baseURL: API });

  const regRes = await api.get(`/api/v1/scenarios/${SCENARIO}/registry`);
  expect(regRes.ok()).toBeTruthy();
  const profiles = (await regRes.json()).result.registry_snapshot.agent_profiles as Array<{
    agent_id: string; agent_version: string; provider_id: string; residency: string;
  }>;
  const providers = [...new Set(profiles.map((p) => p.provider_id))].sort();
  const residencies = [...new Set(profiles.map((p) => p.residency).filter(Boolean))].sort();
  const first = profiles[0];

  const cases: Array<{ operation: string; params: Record<string, unknown> }> = [
    { operation: "FORBID_PROVIDER", params: { provider: providers[0] } },
    { operation: "REQUIRE_RESIDENCY", params: { residency: residencies[0] } },
    { operation: "TIGHTEN_COST_CEILING", params: { ceiling: 1.0 } },
    { operation: "TIGHTEN_LATENCY_CEILING", params: { ceiling: 100.0 } },
    { operation: "REVOKE_AGENT_VERSION", params: { agent_version: `${first.agent_id}@${first.agent_version}` } },
    { operation: "EXPIRE_EVIDENCE", params: {} },
    { operation: "TIGHTEN_PERMISSION_POLICY", params: { permission: "invoke_tool" } },
    { operation: "TIGHTEN_PROVIDER_CONCENTRATION", params: { limit_pct: 25 } },
    { operation: "REMOVE_CANDIDATE", params: { agent_id: first.agent_id, agent_version: first.agent_version } },
  ];

  const baselines = new Set<string>();
  const modified = new Set<string>();
  for (const c of cases) {
    const res = await api.post(`/api/v1/scenarios/${SCENARIO}/what-if`, { data: c });
    expect(res.status(), `${c.operation} status`).toBe(200);
    const r = (await res.json()).result;
    expect(r.baseline_plan.plan_fingerprint, `${c.operation} baseline fp`).toBeTruthy();
    expect(r.modified_plan.plan_fingerprint, `${c.operation} modified fp`).toBeTruthy();
    expect(r.plan_diff, `${c.operation} diff`).toBeTruthy();
    baselines.add(r.baseline_plan.plan_fingerprint);
    modified.add(r.modified_plan.plan_fingerprint);
  }

  // immutable baseline: one and only one baseline fingerprint across all nine
  expect(baselines.size, "distinct baseline fingerprints").toBe(1);
  // each perturbation actually changed the plan
  expect(modified.size, "distinct modified fingerprints").toBe(cases.length);
  await api.dispose();
});
