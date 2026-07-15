# CER V0.2 — Internal Executive Summary (Deliverable 16)

**What this milestone did:** extended the V0.1 cross-runtime proof along its two weakest axes — one runtime, one profile — by adding a **second independent external runtime** and a **second materially distinct actuation profile**, additively, with **zero** changes to the frozen ActionGate and ACP. The question was whether CER identity, exact-action binding, and control-plane independence hold when both the *producer* and the *action shape* vary.

Labels: `FACT` (measured/implemented) · `INTERPRETATION`.

---

## The result in one line
`FACT`. Three runtimes (native **Ugence**, real **LangGraph** 1.2.9, real **OpenAI Agents SDK** 0.18.2) each produced, per profile, the **identical** action identity — `kubernetes.scale` → `07f7a6aa…` (byte-identical to V0.1), `kubernetes.rollout` → `72ddae26…` — with **zero cross-profile collisions**, and the frozen ActionGate + ACP returned identical decisions across all three; scale evidence/approvals fail closed against rollout and vice-versa.

## Three hypotheses — all survived falsification
`FACT`. **H1** a second external runtime emits CER with no control-plane branch. **H2** a second materially distinct profile without weakening identity/binding. **H3** the same envelope, identity rule, machinery, and governance across both profiles. Each was attacked (a runtime that could diverge; a same-target rollout that could collide with scale; downgrade/evidence-transfer injections; a shared-machinery run that could have forced a per-profile fork). None was falsified.

## Four verdicts (per frozen thresholds)
1. **Second-runtime interoperability:** `SECOND_RUNTIME_INTEROPERABILITY_SUPPORTED` — OpenAI Agents actually ran; 15/15 verdict equivalence.
2. **Multi-profile CER:** `CER_MULTI_PROFILE_SUPPORTED_WITH_LIMITATIONS` — both profiles validate, distinct non-colliding identities, binding intact; WITH_LIMITATIONS because both are within one actuation family (Kubernetes).
3. **Control-plane independence:** `CONTROL_PLANE_REMAINS_RUNTIME_INDEPENDENT` — 0 runtime tokens in frozen AG/ACP; CP receives only the CER.
4. **Draft maturity:** `CER_V0_2_READY_FOR_EXTERNAL_REVIEW` — all preregistered criteria met; limitations enumerated; **no standards-body / industry-adoption claim**.

## What was built (5 staged, pushed commits)
`FACT`:
1. **Baseline freeze + selection** — froze V0.1; selected the second runtime by preference order (OpenAI Agents 0.18.2, the highest that actually installs and runs here) and the second profile (`kubernetes.rollout.v1`).
2. **Universal envelope + domain profiles** — one CloudEvents-style envelope; per-profile required/optional/**prohibited** fields; `scale.v1` proven byte-identical to V0.1, `rollout.v1` new; domain separation via `tool.tool_name` inside the hash.
3. **Three producers × two profiles** — real OpenAI Agents `Runner` loop with real `ResponseFunctionToolCall`/`ToolCallItem` interception, joining Ugence + real LangGraph; identical digest per profile.
4. **Factorial corpus + cross-profile security + runner + tests** — 20-case corpus, 47 frozen vectors, 10 §9 security assertions.
5. **Preregistration** (committed before the final run).
6. **Final benchmark + results** — 20/20 cases, 240 total tests pass, deterministic.

## Why identity held across a new profile without weakening binding
`FACT`. `rollout.v1` adds identity-bearing fields absent from scale (image/manifest digest, strategy, maxSurge/maxUnavailable, timeout, rollback ref). Domain separation comes from the profile's 1:1 `tool.tool_name` mapping (`scale`/`rollout`) inside the hashed payload — **not** from hashing the CER wrapper — so `scale.v1` identity is unchanged from V0.1 while `rollout.v1` is guaranteed distinct. Prohibited-field enforcement makes any profile downgrade fail closed. No semantic field was removed to force a match; no equivalent identity was claimed for different actuation surfaces.

## What did NOT change (constraints honored)
`FACT`. **ActionGate: 0 lines** (frozen, `projection.py` `ce458712…`). **ACP: 0 lines** (frozen, `adapter.py` `8d334746…`, natively supports `CloudOperation.ROLLOUT`). **CER V0.1 package: 0 lines** (reused unchanged; V0.1 vectors fingerprint `3ec7f36d…` untouched). **Context Minimization: 0 lines** (not broadened; honestly skipped where its span contract is absent). V0.1 identity frozen; exact-action binding not weakened; no runtime-specific CP branch; nothing actuated (ACP shadow-only). VC brief / pitchbook untouched.

## Honest limitations (`INTERPRETATION`)
Two profiles within a single actuation family (Kubernetes) — the reason the multi-profile verdict is qualified; ACP over an authored fixture (no live cluster); ActionGate reference HMAC signing (not production custody); deterministic model stubs drive both external runtimes (real event loops + real tool-call interception, no live LLM). These bound the *breadth* of the claim, not its *correctness*.

## Recommended next step
`INTERPRETATION`. The identity/binding/independence contract now holds across two runtimes-plus-native and two profiles. The next increment (a future milestone) is a profile in a **second actuation domain** (outside Kubernetes) to move the multi-profile verdict past `…_WITH_LIMITATIONS`, plus a live-cluster ACP path and production asymmetric signing. No standards-body or industry-adoption claim should be made before that breadth exists.

## Artifacts
`cer_v0_2/`: `CER_V0_1_BASELINE_FREEZE.md`, `CER_PROFILE_ARCHITECTURE.md`, `CER_KUBERNETES_ROLLOUT_PROFILE.md`, `SECOND_RUNTIME_ADAPTER.md`, `CER_CROSS_PROFILE_SECURITY.md`, `CER_V0_2_CONFORMANCE.md`, `CER_V0_2_PREREGISTRATION.md`, `CER_V0_2_RESULTS.md`, `cer_v0_2.schema.json`, `profiles/kubernetes.{scale,rollout}.v1.schema.json`, `envelope.py`, `actuation.py`, `profiles/`, `producers/` (ugence, langgraph_adapter, openai_agents_adapter), `control_plane.py`, `corpus.py`, `conformance/` (runner, vectors, results), `tests/`. Frozen, reused unchanged: ActionGate v2 profile + ACP cloud.
