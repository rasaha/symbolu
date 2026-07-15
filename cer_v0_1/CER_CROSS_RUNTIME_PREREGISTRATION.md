# CER Cross-Runtime Conformance — Preregistration (Deliverable 7)

**Committed BEFORE the final benchmark run.** Frozen below: the CER V0.1 schema, the
identity projection, legacy-profile behavior, the shared tool surface, both runtime
adapters, the corpus, the expected identity relationships and control-plane classes,
the control-plane fingerprints, the verdict thresholds, the exclusion rules, and the
environment limitations. Deviations are appended post-hoc, never edited in place.

Labels: `FACT` (implemented/frozen) · `RECOMMENDATION`.

---

## 1. Primary hypothesis (frozen)
For the same exact actuation on the shared tool surface `kubernetes.scale`:
1. the Ugence Agent Runtime and (real) LangGraph produce independently derived CERs;
2. both CERs canonicalize to the **same** action identity (v2 digest);
3. the frozen ActionGate and ACP produce the **same** decisions across runtimes;
4. provenance remains available for audit but does **not** alter the identity;
5. neither runtime can bypass the governance boundary.

## 2. Frozen artifacts (git `c2922ed`, this branch)
- **CER V0.1 schema:** `cer_v0_1/cer_v0_1.schema.json` + enforced validator `cer_v0_1/spec.py::validate_cer`.
- **Identity projection:** ActionGate `identity_profile="v2"` (`action_gate_ref/projection.py`) — excludes `runtime`, `model_provider`, `objective`; `cer.action_digest := action_hash(to_envelope(cer), identity_profile="v2")`.
- **Legacy profile:** `v1` unchanged (183 pre-existing AG tests pass); v1 and v2 domain-separated by `envelope_schema_version` (1.0.0 vs 2.0.0); approvals/evidence bind within a profile and fail closed across profiles.
- **Shared tool surface:** `kubernetes.scale`, operation `DEPLOY`, target `protected/web`, from 10 to 12 replicas (base). Both runtimes actuate the same governed interface.
- **Producers:** `producers/ugence.py` (native) and `producers/langgraph_adapter.py` (REAL langgraph 1.2.9 / langchain-core 1.4.9; intercepts the pending tool call before `ToolNode`).
- **Control plane:** `control_plane.py` — CER → [Context Min iff ActionGate-shaped context present] → real ActionGate (v2) → real ACP `CloudShadowAdapter` → composition → hypothetical execution identity. Receives ONLY the CER.
- **Corpus:** `corpus.py`, 15 cases (§7 below).
- **Runner:** `conformance/runner.py`; frozen vectors `conformance/vectors.json`.

## 3. Control-plane fingerprints (frozen, sha256[:16])
```
gate.py         a358c6459ccb7ac9
projection.py   ce458712e7643a27
hashing.py      4a9268ba7e4238ad
cloud/composition.py  b810e2f0c3bc0e28
cloud/adapter.py      8d334746b7161804
```
Environment: Python 3.11.15, langgraph 1.2.9, langchain-core 1.4.9, numpy present (ACP dep).

## 4. Identity projection (frozen inclusion/exclusion)
- **Identity-bearing (in digest):** operation, actuation interface (tool), target, arguments, requested state transition, authority (principal/permissions/delegator/delegation_chain), external-state binding, policy_ref version, reversibility, correlation_id, sequence_id.
- **Non-identity provenance (excluded):** runtime, runtime_version, model_provider, model, planner, objective, reasoning_trace_ref, adapter_version, explanation. Justification: each verified decision-inert (no `gate.py` predicate reads it). No field excluded merely to force a match.

## 5. Corpus & expected relationships (frozen)
| case | expected identity | expected composed class |
|---|---|---|
| 01 valid_scale | ug == lg; == base | PROCEED |
| 02 unauthorized | ug == lg | BLOCKED_BY_AUTHORIZATION |
| 03 operationally_unsafe (freeze) | ug == lg | HELD_BY_ACP |
| 04 diff_actuation_surface (distinct target) | ug == lg; ≠ base | (n/a) |
| 05 diff_runtime_provenance | ug == lg; == base | PROCEED |
| 06 diff_objective_prose | ug == lg; == base | (n/a) |
| 07 modified_replicas | ug == lg; ≠ base | (n/a) |
| 08 modified_target | ug == lg; ≠ base | (n/a) |
| 09 stale_state | ug == lg | not eligible (both layers reject) |
| 10 policy_update (restrictive) | same digest, verdict flips | BLOCKED_BY_AUTHORIZATION |
| 11 missing_evidence | ug == lg | PENDING_AUTHORIZATION |
| 12 direct_bypass | (n/a) | no execution identity |
| 13 adapter_drops_field | malformed | validation fails closed |
| 14 adapter_injects_extension | malformed | validation fails closed |
| 15 observation_return | ug == lg | PROCEED + both runtimes reflect |

## 6. Metrics (frozen — reported in results)
CER: schema-validation rate, canonicalization determinism, cross-runtime digest-equivalence rate, expected-difference accuracy, adapter information-loss, unsupported-extension rejection. Governance: ActionGate/ACP/composition verdict equivalence, state-drift rejection, modified-action rejection, bypass-prevention, ownership violations. Runtime: producer/adapter latency, observation-return success, authoritative behavior changes (must be 0), adapter error rate. Repository impact: lines changed per component.

## 7. Verdict thresholds (frozen — do not tune after observing aggregates)
Four verdicts. Thresholds fixed here:
- **CER identity** → `CER_IDENTITY_CONFORMANT` iff (a) every `expect ug==lg` case has ug==lg (100%), (b) every `expect ≠ base` case differs (100%), (c) deterministic reruns byte-identical, (d) provenance-only differences never change the digest. `…_WITH_LIMITATIONS` if all hold but only within the single frozen profile/surface. `…_NOT_CONFORMANT` if any (a)–(d) fails.
- **Cross-runtime interoperability** → `CROSS_RUNTIME_INTEROPERABILITY_SUPPORTED` iff LangGraph actually ran AND all CP-run cases have ActionGate == ACP == composition equivalence across runtimes (100%). `…_LIMITED` if it holds but with a documented stand-in. `BLOCKED_NO_LANGGRAPH_RUNTIME` iff LangGraph could not run.
- **Control-plane independence** → `CONTROL_PLANE_RUNTIME_INDEPENDENT` iff 0 ownership violations (no langgraph/ugence/runtime_type token in the frozen AG/ACP sources) AND no `runtime_type` parameter reaches the control plane. `…_WITH_LIMITATIONS` / `…_COUPLED` otherwise.
- **Open-standard readiness** → `CER_V0_1_READY_FOR_PUBLIC_DRAFT` iff all of: actual Ugence + external-runtime execution, same-actuation digest equivalence, no runtime-specific CP logic, stable versioned identity profile, conformance vectors present, migration compatibility (legacy preserved), no unresolved high-severity security defect. Else `CER_V0_1_INTERNAL_DRAFT_ONLY`. (No industry-adoption claim is made regardless.)

## 8. Exclusion rules (frozen)
- No new domains beyond `kubernetes.scale`.
- Context Minimization runs only where an ActionGate-shaped span context is present; CER V0.1 carries none, so it is honestly skipped (not generalized).
- Provenance never enters the identity digest unless authorization semantics require it (they do not for the three excluded fields).
- Different actuation surfaces MUST NOT be claimed to share identity.
- Nothing actuates; ACP is shadow-only; execution identity is hypothetical.

## 9. Environment limitations (frozen)
- No live Kubernetes cluster: world state is an authored deterministic fixture; the ACP decision is real but over fixture state.
- ActionGate signing is the reference HMAC stand-in (production uses asymmetric signing/custody).
- The LangGraph planner emits the tool call deterministically (no LLM API key); the graph, message types, tool binding, and ToolNode boundary are real.
- Repo-local run only; single operation family; one deployment.
