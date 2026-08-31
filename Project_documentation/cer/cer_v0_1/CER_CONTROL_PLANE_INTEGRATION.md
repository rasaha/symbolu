# CER Control-Plane Integration (Deliverable 6)

`cer_v0_1/control_plane.py`, `risk_tier.py`, `observation.py`. Grounded in the implemented, executed harness.

Labels: `FACT` · `RECOMMENDATION`.

## Pipeline
`FACT`. `run_control_plane(cer, now, ...)` runs, on the REAL frozen components, for a governed CER:
1. **Risk tier** — `risk_tier.enforce_tier`: authoritative tier from the **tool profile** (`kubernetes.scale` = GOVERNED). A CER self-asserting a weaker tier is rejected (`RiskTierViolation`). No model self-assertion.
2. **Context Minimization** — runs **only** where an ActionGate-shaped span context is present. CER V0.1 carries none, so it is honestly `SKIPPED_NO_ACTIONGATE_CONTEXT` (Context Minimization is not generalized beyond its implemented guarantee, per constraint).
3. **ActionGate (real)** — `gate.evaluate(env, policy, evidence, approvals, now, identity_profile="v2")` → outcome + v2 `action_hash`.
4. **ACP (real)** — `CloudShadowAdapter(enabled=True).observe(world, [candidate], authorization=verdict)` → operational decision + `cloud_recommendation`, composed with the ActionGate verdict.
5. **Composition** — `PROCEED` iff ActionGate authorized AND ACP safe. `eligible = (combined == PROCEED)`.
6. **Hypothetical execution identity** — bound to `(cer_digest, combined, action_hash)`, minted **only** when eligible. Never a real token; ACP is shadow-only.

## No runtime coupling
`FACT`. `run_control_plane` receives **only the CER**. There is no `runtime_type` parameter and no Ugence/LangGraph branch here or downstream (ActionGate/ACP import nothing runtime-specific). Verified by the ownership test.

## Measured outcomes (real components)
`FACT`:
- Authorized + safe (web 10→12, evidence bound to v2 hash): AG=`ALLOW`, ACP=`EXECUTE`, combined=`PROCEED`, **eligible=True**.
- Authorized but unsafe (recent action / freeze / oversized blast): AG=`ALLOW`, ACP=`HOLD`, combined=`HELD_BY_ACP`, eligible=False.
- Unauthorized: AG=`DENY`, combined=`BLOCKED_BY_AUTHORIZATION`.
Evidence is built **bound to the v2 action_hash** (`build_v2_evidence`), proving evidence binds correctly under the new identity profile.

## Risk-tiered fast path (documented, not overbuilt)
`FACT` (`risk_tier.py`). GOVERNED profiles (scale/rollout/delete) take the full path. LOW_RISK read-only profiles (get/list/logs) are registered to illustrate the fast-path contract; they are not exercised by the scale experiment. Unknown profile → GOVERNED (fail-safe). The tier is enterprise/tool-profile controlled; the runtime cannot self-assert a weaker tier.

## Observation return (loop, not waterfall)
`FACT` (`observation.py`). `GovernedExecutionResult.from_cp(...)` returns the composed result to the runtime; `observe_and_reflect(runtime, result)` yields the runtime's reflection + next step + memory update. Governance ends at eligibility; the runtime resumes ownership of observation/reflection/planning. Proven for both runtimes by `tests/test_observation_return.py`.

## Bypass prevention
`FACT`. In governed mode no governed action executes without an eligible composed result. The LangGraph adapter routes to `END` (never runs the real `k8s_scale` tool) unless `RESUME` with eligibility; a direct tool call outside the CER path mints no execution identity. Proven by `tests/test_e2e_governance.py::test_direct_bypass_blocked`.
