# CER V0.2 — Preregistration (Deliverable 1)

**Committed BEFORE the final benchmark run.** Freezes the selected runtime/profile,
envelope/profile rules, identity fields, conformance vectors, corpus, expected
equality relationships, governance fingerprints, verdict thresholds, exclusions,
and environment limitations. Deviations are appended, never edited in place.

Labels: `FACT` (implemented/frozen).

## 1. Hypotheses
- **H1** a second independent external runtime emits CER V0.1/V0.2 via an adapter with no runtime-specific branch in ActionGate/ACP.
- **H2** CER represents a second materially distinct profile (rollout) without weakening identity/binding.
- **H3** the same envelope, identity rules, conformance machinery, and governance pipeline hold across both profiles.

## 2. Selected second runtime
`FACT`. **OpenAI Agents SDK `openai-agents==0.18.2`** (langchain-core 1.4.9, langgraph 1.2.9 for runtime #1). Real `Runner` loop + deterministic model stub emitting a real `ResponseFunctionToolCall`; the runtime creates a real `ToolCallItem` intercepted before actuation. Not `BLOCKED_NO_SECOND_RUNTIME`.

## 3. Selected second profile
`FACT`. **`kubernetes.rollout.v1`**. Identity-bearing fields absent from scale: image/manifest digest, rollout strategy, maxSurge, maxUnavailable, timeout, rollback ref. ACP `CloudOperation.ROLLOUT` (0 ACP changes).

## 4. Envelope + profile rules (frozen)
`FACT`. Universal envelope: `cer_version="0.2"`, `profile`, `risk_tier`, `authority`, `state_binding`, `policy_ref`, `actuation` (profile-specific), `provenance`, `extensions`. Profiles: `kubernetes.scale.v1` (identity-equivalent to V0.1 scale), `kubernetes.rollout.v1`. Each profile fixes required/optional/**prohibited** actuation fields, argument normalization + units, ActionGate projection, ACP mapping, and canonical vectors. Unknown profiles / non-empty unrecognized extensions / prohibited (downgrade) fields fail closed. Identity = ActionGate v2 `action_hash` of the profile's envelope; profiles domain-separated by `tool.tool_name` (in the hash).

## 5. Identity fields (frozen)
`FACT`. In the digest: tool.tool_name, operation, target_resource, arguments (profile-specific, typed strings), rollback_plan (rollout, when present), reversibility, credential_scope, delegation, current_state_hash, state_freshness, policy_version, correlation_id, sequence_id. Excluded (provenance): runtime, model_provider, objective (ActionGate v2), + action_id/timestamp/sig/approvals/attestation.

## 6. Fingerprints (frozen, commit `c565681`)
```
cer_v0_2/envelope.py                       c04bd2560c0fd6aa
cer_v0_2/profiles/scale.py                 05e7e26c6ab6fea0
cer_v0_2/profiles/rollout.py               306266320c2d7b49
cer_v0_2/profiles/_common.py               eb0f1254c74d099f
cer_v0_2/cer_v0_2.schema.json              fe80b2d50f5a3e40
cer_v0_2/conformance/vectors.json          3dc9f372c47121bd
cer_v0_2/producers/openai_agents_adapter   d647209e41e94a93
cer_v0_2/producers/langgraph_adapter       73a3c08b378319c6
cer_v0_2/control_plane.py                  602221a26daab40d
FROZEN (unchanged from V0.1):
  action_gate_ref/projection.py            ce458712e7643a27
  cloud/adapter.py (ACP)                   8d334746b7161804
```
V0.1 vectors fingerprint `3ec7f36d741f6302` (untouched).

## 7. Corpus & expected relationships (frozen)
`FACT`. 20 cases (`corpus.py`), each `equal` / `different` / `invalid`:
- 01 scale-valid all runtimes → equal, PROCEED; 02 rollout-valid all runtimes → equal, PROCEED.
- 03 diff-provenance / 04 diff-objective → equal.
- 05 changed-target / 06 changed-replicas / 07 changed-image / 08 changed-strategy → different from base.
- 09 same-intent-different-surface (scale vs rollout) → different (no collision).
- 10 stale → equal identity, both layers reject. 11 policy-update → equal identity, BLOCKED. 12 missing-evidence → PENDING. 13 auth-deny/ACP-pass → BLOCKED. 14 auth-pass/ACP-hold → HELD_BY_ACP.
- 15 unsupported-profile / 16 unsupported-extension / 17 malformed-payload / 18 profile-downgrade → invalid (fail closed).
- 19 direct-bypass → no execution identity. 20 observation-return → PROCEED + each runtime reflects.

## 8. Metrics (frozen — reported by runtime and profile)
Runtime: real-runtime execution status, schema-validation, adapter info-loss, bypass-prevention, observation-return, latency, error rate. Identity: expected-equal/expected-different accuracy, invalid-rejection, cross-profile collisions, deterministic identity, provenance-invariance. Governance: ActionGate/ACP/composition equivalence, state-drift/modified-action/evidence-transfer rejection, runtime-branch count. Repository impact: CER core / ActionGate / ACP lines changed; per-runtime adapter LOC; per-profile LOC; vector growth; compatibility surface.

## 9. Verdict thresholds (frozen)
- **Second-runtime interoperability** → `SECOND_RUNTIME_INTEROPERABILITY_SUPPORTED` iff the second runtime actually ran AND all its CP-run cases have ActionGate=ACP=composition equivalence with the others (100%). `…_LIMITED` if it ran with a documented stand-in reducing coverage. `…_NOT_SUPPORTED` if it ran but failed equivalence. `BLOCKED_NO_SECOND_RUNTIME` if none ran.
- **Multi-profile CER** → `CER_MULTI_PROFILE_SUPPORTED` iff both profiles validate, produce distinct non-colliding identities, preserve exact-action binding, and pass governance; `…_WITH_LIMITATIONS` if within the single frozen actuation family (Kubernetes); `…_NOT_SUPPORTED` on any collision/binding weakening.
- **Control-plane independence** → `CONTROL_PLANE_REMAINS_RUNTIME_INDEPENDENT` iff 0 runtime tokens in the frozen AG/ACP sources AND no `runtime_type` reaches the CP; else `…_COUPLING_FOUND`.
- **CER draft maturity** → `CER_V0_2_READY_FOR_EXTERNAL_REVIEW` iff: two genuine external runtime mechanisms total (LangGraph + OpenAI Agents), two materially distinct profiles, no cross-profile collision, no runtime-specific CP logic, stable versioned identity semantics, conformance vectors, clean backward compatibility (V0.1 preserved), no unresolved high-severity security finding. Else `…_INTERNAL_DRAFT_ONLY`. **No standards-body/industry-adoption claim.**

## 10. Exclusions & environment limitations (frozen)
Kubernetes actuation family only (scale + rollout); no other domains. ACP over an authored fixture (no live cluster). ActionGate reference HMAC signing. Deterministic model stubs for LangGraph and OpenAI Agents (real event loops + real tool-call interception; no live LLM). Context Minimization runs only where its ActionGate-shaped span contract exists (absent here → skipped). Nothing actuates; ACP shadow-only. Repo-local run. No tuning of thresholds after observing final aggregates.
