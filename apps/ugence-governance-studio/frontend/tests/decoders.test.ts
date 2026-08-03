import { describe, expect, it } from "vitest";
import {
  DecodeError,
  decodeCompare,
  decodePlan,
  decodeRanking,
  decodeReplay,
  decodeWhatIf,
} from "@/api/decoders";
import procRanking from "./fixtures/procurement.ranking.json";
import procPlan from "./fixtures/procurement.plan.json";
import procReplay from "./fixtures/procurement.replay.json";
import procCompare from "./fixtures/procurement.compare.json";
import procWhatIf from "./fixtures/procurement.whatif.json";
import cyberPlan from "./fixtures/cybersecurity_no_feasible_team.plan.json";

describe("P3D boundary decoders (§6)", () => {
  it("accepts valid public ranking/plan/replay/compare/what-if payloads", () => {
    expect(decodeRanking(procRanking).rankings.length).toBeGreaterThan(0);
    expect(decodePlan(procPlan).agent_team_plan.plan_state).toBe("COMPLETE");
    expect(decodePlan(cyberPlan).agent_team_plan.plan_state).toBe("NO_FEASIBLE_TEAM");
    expect(decodeReplay(procReplay).match).toBe(true);
    expect(decodeCompare(procCompare).diff.diff_fingerprint).toBeTruthy();
    expect(decodeWhatIf(procWhatIf).baseline_state).toBeTruthy();
  });

  it("fails closed when a mandatory ranking field is missing", () => {
    const bad = { rankings: [{ role_id: "r", ranking_fingerprint: "f", ranked_candidates: [{ rank: 1 }] }] };
    expect(() => decodeRanking(bad)).toThrow(DecodeError);
  });

  it("fails closed when a mandatory plan field is missing", () => {
    const bad = { plan_state: "COMPLETE", agent_team_plan: { plan_state: "COMPLETE" } };
    expect(() => decodePlan(bad)).toThrow(DecodeError);
  });

  it("rejects an unknown plan state (incompatible shape)", () => {
    const bad = JSON.parse(JSON.stringify(procPlan));
    bad.agent_team_plan.plan_state = "TOTALLY_MADE_UP";
    expect(() => decodePlan(bad)).toThrow(/unknown plan state/);
  });

  it("rejects a non-object result", () => {
    expect(() => decodeRanking(null)).toThrow(DecodeError);
    expect(() => decodePlan("nope")).toThrow(DecodeError);
  });

  it("does not domain-default: missing replay match throws instead of assuming false", () => {
    const bad = { expected_plan_fingerprint: "a", replayed_plan_fingerprint: "b", diagnostics: [] };
    expect(() => decodeReplay(bad)).toThrow(/match/);
  });
});
