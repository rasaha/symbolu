# CER V0.2 — Results (Deliverable 7)

Executed AFTER the preregistration (`CER_V0_2_PREREGISTRATION.md`, commit `91bfd4f`; fingerprints frozen at `c565681`). No threshold or expectation was tuned after observing final aggregates. All numbers are measured on real components in this environment.

Labels: `FACT` (measured) · `INTERPRETATION`.

---

## 1. Headline

`FACT`. A **second independent external runtime** (OpenAI Agents SDK `openai-agents==0.18.2`, real `Runner` loop + real `ResponseFunctionToolCall`/`ToolCallItem` interception) and a **second materially distinct actuation profile** (`kubernetes.rollout.v1`) were added **additively**. Across three runtimes deriving CERs through independent code paths with different provenance and objective prose, each profile yields one identical action identity, and the frozen ActionGate + ACP produce identical decisions:

```
scale.v1   base action_digest (v2) = 07f7a6aaf20a55a8f03fc31f232420774c7361264cabf66b3a2ac74ffd3f7b51
rollout.v1 base action_digest (v2) = 72ddae264f4bb757fdeb137bbea0d44dfb36bf60161571447a82be0695c770e3
Ugence == LangGraph == OpenAI-Agents  (per profile) : TRUE
scale digest == V0.1 scale digest                    : TRUE   (backward compatible)
scale digest == rollout digest                       : FALSE  (no cross-profile collision)
cross_profile_collisions                             : 0
```

## 2. Conformance run (final, `conformance/results.json`)
`FACT`. **20 / 20 corpus cases passed. all_passed = TRUE.** Three runner invocations are byte-identical (deterministic); wall-clock ≈ 3.5 s for the full 3-runtime × 2-profile × 20-case factorial. 47 frozen digest vectors. Per profile: scale 8/8, rollout 10/10, profile-agnostic (unsupported-profile / direct-bypass) 2/2.

| Metric | Result |
|---|---|
| Cross-runtime digest equivalence (expected-equal) | **11 / 11** |
| Expected-difference accuracy | **5 / 5** (changed target/replicas/image/strategy + same-intent-different-surface) |
| Invalid rejection (fail closed) | **4 / 4** (unsupported profile, unsupported extension, malformed payload, profile downgrade) |
| Cross-profile identity collisions | **0** |
| ActionGate verdict equivalence (across runtimes) | **15 / 15** CP-run cases |
| ACP verdict equivalence | **15 / 15** |
| Composition equivalence | **15 / 15** |
| Composed-class correctness (vs prereg) | **7 / 7** |
| Deterministic identity | **16 / 16** |
| Provenance invariance (per runtime) | **11 / 11** each (Ugence, LangGraph, OpenAI Agents) |
| State-drift rejection (stale case) | **1 / 1** (both layers reject) |
| Modified-action rejection | **4 / 4** |
| Evidence-transfer rejection (scale ev ↛ rollout) | **1 / 1** (fail closed) |
| Bypass prevention | **1 / 1** (no execution identity without an eligible composed result) |
| Observation-return | **1 / 1** (all runtimes reflect after the verdict) |
| Ownership violations (`ownership_no_runtime_switch`) | **0** (TRUE) |
| Authoritative behavior changes | **0** (ACP shadow-only; nothing actuated) |

## 3. Hypotheses — outcome
`FACT`:
- **H1** (second runtime via adapter, no CP branch) — **survived.** OpenAI Agents actually ran (`exec=True`, schema_ok 15/15); every CP-run case matched ActionGate = ACP = composition across all three runtimes (15/15); zero runtime tokens reach the control plane.
- **H2** (second profile without weakening identity/binding) — **survived.** `rollout.v1` carries identity-bearing fields absent from scale (image/manifest digest, strategy, maxSurge, maxUnavailable, timeout, rollback ref); no downgrade accepted (profile-downgrade case fails closed); exact-action binding intact (scale evidence/approval cannot authorize rollout, and vice-versa).
- **H3** (same envelope, identity rules, machinery, governance across profiles) — **survived.** One universal envelope, one v2 identity rule, one runner, one control plane serve both profiles; scale.v1 remains byte-identical to V0.1.

## 4. §9 cross-profile security assertions — all 10 met
`FACT` (each proven by an executed test in `tests/test_cross_profile_security.py`): scale evidence cannot authorize rollout (fail closed); rollout approval cannot authorize scale (fail closed); profile participates in domain separation (via `tool.tool_name`); identical field names create no collision; unsupported profiles fail closed; profile downgrade fails closed; V0.1/V0.2 cannot be confused (yet scale.v1 identity == V0.1); legacy ActionGate v1 remains verifiable and domain-separated from v2; provenance cannot alter the digest; material actuation changes always alter the digest. Runner: `cross_profile_collisions = 0`, `evidence_transfer_rejected = 1`, `invalid_ok = 4/4`.

## 5. Metrics (§8)

**Runtime execution** (this environment): all three runtimes executed real event loops — Ugence native producer, LangGraph 1.2.9 (`StateGraph`+`ToolNode`), OpenAI Agents 0.18.2 (`Runner` + real `ResponseFunctionToolCall`/`ToolCallItem`). Schema-valid 15/15 each; adapter information-loss 0; provenance-invariant 11/11 each. Deterministic byte-identical reruns; nothing actuated (ACP shadow-only).

**Test suites:** ActionGate reference **195 passed** (frozen); CER V0.1 **23 passed** (frozen, vectors fingerprint `3ec7f36d741f6302` unchanged); CER V0.2 **22 passed**. **Full regression: 240 passed.**

**Repository impact (this milestone, V0.2):**
| Component | Lines changed |
|---|---|
| ActionGate (`action_gate_ref/`) | **0** (frozen; `projection.py` fingerprint `ce458712…`, last touched in V0.1 Stage 1) |
| ACP (`autonomous_control_plane/cloud/`) | **0** (frozen; `adapter.py` fingerprint `8d334746…`, natively supports `CloudOperation.ROLLOUT`) |
| Context Minimization | **0** (not generalized) |
| CER V0.1 package | **0** (frozen; reused unchanged) |
| Second-runtime adapter (`openai_agents_adapter.py`) | **114 LOC** (new) |
| Second profile (`profiles/rollout.py`) | **96 LOC** (new) |
| New `cer_v0_2/` package total | **1,650 LOC** (envelope, profiles, three producers, control-plane harness, corpus, runner, tests) |
| Conformance vectors | V0.1 vectors untouched; **47** new V0.2 vectors added separately |

## 6. Verdicts (per frozen thresholds, §9 of the preregistration)

### Second-runtime interoperability → `SECOND_RUNTIME_INTEROPERABILITY_SUPPORTED`
`FACT`. OpenAI Agents SDK **actually ran** (real `openai-agents==0.18.2`), and every CP-run case had ActionGate = ACP = composition equivalence across runtimes (15/15, 100%). Not `BLOCKED_NO_SECOND_RUNTIME`; not `…_LIMITED`; not `…_NOT_SUPPORTED`.

### Multi-profile CER → `CER_MULTI_PROFILE_SUPPORTED_WITH_LIMITATIONS`
`FACT`. Both profiles validate, produce distinct non-colliding identities (0 collisions), preserve exact-action binding, and pass governance. Marked **WITH_LIMITATIONS** exactly per the preregistered qualifier because both profiles live within the **single frozen actuation family (Kubernetes)** — the demonstration has not yet crossed into a second actuation domain.

### Control-plane independence → `CONTROL_PLANE_REMAINS_RUNTIME_INDEPENDENT`
`FACT`. Zero runtime tokens (`langgraph`/`ugence`/`openai`/`runtime_type`/`crewai`) in the frozen ActionGate/ACP sources (`ownership_no_runtime_switch = TRUE`), and no `runtime_type` parameter reaches the control plane — it receives only the CER.

### CER draft maturity → `CER_V0_2_READY_FOR_EXTERNAL_REVIEW`
`FACT`, per the preregistered criteria, all met: two genuine external runtime mechanisms (LangGraph + OpenAI Agents) plus the native producer; two materially distinct profiles; no cross-profile collision; no runtime-specific control-plane logic; stable versioned identity semantics (v1/v2 domain-separated; scale.v1 == V0.1); conformance vectors present (47); clean backward compatibility (V0.1 suite + vectors preserved, 240 total pass); no unresolved high-severity security finding.
**INTERPRETATION / limitations (external *review*, not a finished standard, and NO industry-adoption / standards-body claim):** the two profiles are within one actuation family (Kubernetes); ACP over an authored fixture (no live cluster); ActionGate reference HMAC signing (not production asymmetric custody); deterministic model stubs drive both external runtimes (real event loops + real tool-call interception, no live LLM). These are the frozen §10 environment limitations, not defects.

## 7. Falsification outcome
`INTERPRETATION`. Each hypothesis was attacked: H1 with the added external runtime that could have diverged (it did not); H2 with a same-target rollout (could have collided with scale → did not), a profile-downgrade injection (rejected), and evidence/approval transfer between profiles (rejected fail-closed); H3 with a shared-machinery run that could have required a profile-specific fork of the envelope, identity rule, runner, or control plane (none needed). The negative controls — unsupported profile, unsupported extension, malformed payload, stale state, direct bypass — all failed closed. Within the frozen scope (Kubernetes scale + rollout, three runtimes, shadow-only ACP), none of H1/H2/H3 was falsified; all three **survived**.
