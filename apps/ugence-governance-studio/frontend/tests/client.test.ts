import { describe, expect, it } from "vitest";
import hash from "../src/generated/openapi.hash.json";

// Generated-client freeze (§8, §28).
describe("generated OpenAPI client", () => {
  it("pins the source OpenAPI sha256 and contract version", () => {
    expect(hash.source_openapi_sha256).toBe(
      "dc309eab216e1a4c2f63f286887a4ef218a96ac34f8fa8614bff176db7c36656",
    );
    expect(hash.api_contract_version).toBe("governance_studio.api.v1");
  });

  it("includes every operation P3C consumes", () => {
    const required = [
      "get_health",
      "get_ready",
      "get_version",
      "list_scenarios",
      "get_scenario",
      "get_scenario_workflow",
      "get_scenario_registry",
      "get_scenario_eligibility",
      "explain_eligibility",
    ];
    for (const op of required) expect(hash.operation_ids).toContain(op);
  });
});
