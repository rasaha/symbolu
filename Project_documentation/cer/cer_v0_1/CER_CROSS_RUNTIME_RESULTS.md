# CER Cross-Runtime Conformance — Results (Deliverable 8)

Executed AFTER the preregistration (`CER_CROSS_RUNTIME_PREREGISTRATION.md`, commit `917beab`). Thresholds were NOT tuned after observing aggregates. All numbers are measured on real components in this environment.

Labels: `FACT` (measured) · `INTERPRETATION`.

---

## 1. Headline

`FACT`. For the same exact actuation (`kubernetes.scale`, `protected/web`, 10→12) the native **Ugence** producer and the **real LangGraph** adapter (langgraph 1.2.9), deriving CERs through independent code paths and stamping different provenance + different objective prose, produced the **identical** action identity, and the frozen ActionGate + ACP produced identical decisions:

```
base action_digest (v2) = 07f7a6aaf20a55a8f03fc31f232420774c7361264cabf66b3a2ac74ffd3f7b51
Ugence digest == LangGraph digest : TRUE
```

## 2. Conformance run (final, `conformance/results.json`)
`FACT`. **15 / 15 corpus cases passed. all_passed = TRUE.** Two runner invocations are byte-identical (deterministic).

| Metric | Result |
|---|---|
| Cross-runtime digest equivalence | **10 / 10** expected-equal cases equal |
| Expected-difference accuracy | **6 / 6** (modified/different-surface cases differ from base) |
| ActionGate verdict equivalence (across runtimes) | **12 / 12** CP-run cases |
| ACP verdict equivalence | **12 / 12** |
| Composition equivalence | **12 / 12** |
| Composed-class correctness (vs prereg) | **7 / 7** |
| State-drift rejection (stale case) | **1 / 1** (both layers reject) |
| Bypass prevention | **1 / 1** (no execution identity without an eligible composed result) |
| Unsupported-extension rejection | **1 / 1** (fail closed) |
| Adapter information-loss (dropped field) | detected + rejected (fail closed) |
| Observation-return | **1 / 1** (both runtimes reflect after the verdict) |
| Ownership violations | **0** |
| Authoritative behavior changes | **0** (ACP shadow-only; nothing actuated) |

## 3. Required conformance assertions (§11) — all met
`FACT`:
- same actuation from Ugence and LangGraph → **same** CER action digest ✓
- runtime/model/objective provenance differences → **no** digest change ✓ (cases 05, 06)
- target/operation/arguments/state-binding/authority changes → **different** digest ✓ (cases 04, 07, 08)
- ActionGate verdicts match across runtimes ✓ (12/12)
- ACP verdicts match across runtimes ✓ (12/12)
- composed execution eligibility matches ✓ (12/12)
- evidence binds correctly under v2; an approval bound under v2 fails closed under v1 ✓ (`test_identity_profile_v2`, `test_e2e_governance`)
- stale state invalidates both paths ✓ (case 09)
- no runtime-specific branch in the control plane ✓ (0 ownership violations; no `langgraph`/`ugence`/`runtime_type` token in `gate.py`/`projection.py`/`composition.py`/`adapter.py`)
- direct tool bypass blocked in governed mode ✓ (case 12; the real langgraph tool never executes in shadow)
- execution result returns to runtime observation/reflection ✓ (case 15)
- deterministic reruns byte-identical ✓
- legacy and v2 identity profiles cannot be confused ✓ (domain-separated; cross-profile approval fails closed)

## 4. Metrics (§12)

**Runtime latency** (mean, this environment): Ugence producer ≈ **0.006 ms**; real LangGraph adapter ≈ **6.25 ms** (a real graph invocation); control plane (ActionGate + ACP + compose) ≈ **3.11 ms**. Adapter error rate 0; authoritative behavior changes 0.

**Test suites:** ActionGate reference **195 passed** (183 pre-existing unchanged + 12 new v2). CER package **23 passed**.

**Repository impact (this milestone):**
| Component | Lines changed |
|---|---|
| ActionGate (`action_gate_ref/`) | 4 files, +118 / −13 (the sanctioned v2 identity profile) |
| ACP | **0** (no core defect found) |
| Context Minimization | **0** (not generalized) |
| Agent Runtime (`agentic/`) | **0** (extended via the new `cer_v0_1/` package, not modified) |
| New `cer_v0_1/` package | 1,636 LOC (producers, adapter, control-plane harness, corpus, runner, tests) |
| Legacy conformance vectors | untouched; new CER vectors added separately |

## 5. Verdicts (per frozen thresholds)

### CER identity → `CER_IDENTITY_CONFORMANT_WITH_LIMITATIONS`
`FACT`. All identity criteria hold at 100% (provenance-excluded, identity-bearing changes detected, deterministic, domain-separated, legacy preserved). Marked WITH_LIMITATIONS because the demonstration is within the **single frozen profile/surface** (`kubernetes.scale`) — exactly the preregistered condition for this qualifier.

### Cross-runtime interoperability → `CROSS_RUNTIME_INTEROPERABILITY_SUPPORTED`
`FACT`. LangGraph **actually ran** (real langgraph 1.2.9 / langchain-core 1.4.9), and every CP-run case had ActionGate = ACP = composition equivalence across runtimes (100%). Not `BLOCKED_NO_LANGGRAPH_RUNTIME`; not `LIMITED`.

### Control-plane independence → `CONTROL_PLANE_RUNTIME_INDEPENDENT`
`FACT`. Zero ownership violations (no `langgraph`/`ugence`/`runtime_type` token in the frozen ActionGate/ACP sources) and no `runtime_type` parameter reaches the control plane — it receives only the CER.

### Open-standard readiness → `CER_V0_1_READY_FOR_PUBLIC_DRAFT`
`FACT`, per the preregistered criteria, all met: actual Ugence + external-runtime execution; same-actuation digest equivalence; no runtime-specific CP logic; stable versioned identity profile (v1/v2 domain-separated); conformance vectors present; migration compatibility (legacy preserved, 195 pass); no unresolved high-severity security defect.
**INTERPRETATION / limitations (public *draft*, not a finished standard, and NO industry-adoption claim):** demonstrated on ONE actuation surface; ACP over an authored fixture (no live cluster); ActionGate reference HMAC signing (not production asymmetric custody); the LangGraph planner selects the tool deterministically (real graph, no live LLM). These are the frozen §9 environment limitations, not defects.

## 6. Falsification outcome
`INTERPRETATION`. The primary hypothesis was attacked with a negative-control case (04, different actuation surface → must differ), malformed-adapter cases (13, 14 → fail closed), a bypass case (12), and a policy-update case (10). None falsified the hypothesis: identity is equivalent across runtimes for the same actuation and correctly distinct for different actuations; the control plane is runtime-independent; bypass and malformed inputs fail closed. Within the frozen scope, the hypothesis **survived**.
