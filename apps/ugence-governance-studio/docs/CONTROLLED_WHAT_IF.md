# Controlled What-If (P3D)

Only the nine allowlisted bounded operations: FORBID_PROVIDER, REQUIRE_RESIDENCY,
TIGHTEN_COST_CEILING, TIGHTEN_LATENCY_CEILING, REVOKE_AGENT_VERSION,
EXPIRE_EVIDENCE, TIGHTEN_PERMISSION_POLICY, TIGHTEN_PROVIDER_CONCENTRATION,
REMOVE_CANDIDATE. Controls are constrained (dropdowns from the pinned
registry/allowed values, validated numeric inputs) — no arbitrary JSON, policy
text, URL, code or fixture mutation. Baseline and modified plans are shown side by
side with the API plan diff and a Reset to baseline action (clears only client
presentation state). Persistent clarification: *What-if analysis evaluates a
temporary copied scenario. It does not modify the frozen scenario, enterprise
policy, registry or any production system.*
