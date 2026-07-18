# ACP V2.2 — Preregistration (Integrated AI Control Plane Validation)

**Committed BEFORE the final end-to-end run.** Frozen below: the workflow, the
pipeline, the layers and their frozen sources, the corpus, the identity binding,
the metrics, the invariants, the verdict rules, and the exclusions. Deviations are
appended post-hoc, never edited in place.

**This milestone is integration evidence only.** Do NOT modify: the Context
Minimization algorithm, the ActionGate runtime, the frozen ACP V1 core, or any
existing benchmark result. Everything is shadow-only; no layer becomes
authoritative; no production execution; no benchmark tuning.

---

## 1. The pipeline (frozen)

```
Original Context
  -> Context Minimization (REAL)  -> Reduced Context
  -> LLM stage (deterministic)    -> Proposed Action (KubernetesOperation)
  -> ActionGate (REAL)            -> Authorized?
  -> ACP (REAL)                   -> Operationally safe?
  -> Hypothetical Execution (eligible iff both pass; never actually executed)
```

No layer may bypass, duplicate, or become authoritative. Everything is shadow-only.

## 2. Workflow (frozen)

One real enterprise workflow: **Kubernetes Deployment scale / rollout** on the
real `action_gateway_k8s` fixture Deployment (`web`, ns `protected`,
`replicas: 1`). Each context includes repeated context, policy, deployment
history, rollout state, approvals, and operational evidence.

## 3. Layers + frozen sources (frozen)

| layer | real implementation | authoritative? |
|---|---|---|
| Context Minimization | `actiongate_context_ablation.compressor.compress` (unchanged) | no (shadow) |
| LLM stage | deterministic offline reader (repo `MockReader` mechanism) | no |
| ActionGate | `action_gate_ref.gate.evaluate` + `action_gateway_k8s.policy` | no (shadow here) |
| ACP | frozen ACP V1 core + real `cloud_controller` | no (shadow) |

**LLM-stage rationale (frozen):** no API key / model is available, AND a live
sampling call is non-deterministic, which would violate the required end-to-end
**deterministic replay**. So the LLM stage is the repository's existing
deterministic offline reader (reads the proposed action only from what survived
compression). Labelled honestly; not presented as a live model.

## 4. Identity binding (frozen)

`context digest -> action hash (ActionGate) -> ACP candidate identity ->
hypothetical execution identity`. Schemas are NOT merged. `verify_chain` fails
closed (`CONTEXT_IDENTITY_MISMATCH`) if the action ActionGate + ACP evaluate is
not exactly the action the reader derived from the reduced context. The
ActionGate↔ACP sub-binding is the V2.1 `(manifest_digest, current_state_hash)`
anchor (`COMPOSITION_IDENTITY_MISMATCH` on divergence).

## 5. Corpus (frozen, 15 scenarios)

healthy rollout · stale context · compressed-with-history-removed · authorization
denial · operational hold · both block · policy update · rollout cooldown ·
modified manifest · stale resourceVersion · missing evidence · rollback
unavailable · blackout window · malformed context · identity mismatch. Provenance
labels LIVE / LOCAL / FIXTURE / AUTHORED / SYNTHETIC. Each names its expected
end-to-end class (`LIVE_K8S_SCENARIO_CORPUS` analogue in
`END_TO_END_SHADOW_METHOD.md`).

## 6. Metrics (frozen)

**Context:** token reduction (avg/min/max), protected-span preservation, ActionGate-
span preservation, ACP-span preservation, decision-invariant rate, deterministic
replay. **ActionGate:** outcome distribution, action-hash determinism, policy-replay
+ stale detection. **ACP:** recommendation distribution, operational holds, evidence
coverage, deterministic replay. **Integrated:** end-to-end class distribution,
**downstream-invariant-under-compression rate** (headline), execution-eligibility
distribution, identity consistency, duplicated-logic count (0), ownership
violations (0), composed latency, shadow behaviour changes (0).

## 7. Invariants (frozen — must all hold)

I1 compressed context never removes authorization-critical info; I2 never removes
operational-safety info; I3 ActionGate never grants operational approval; I4 ACP
never grants authorization; I5 all identities remain bound; I6 policy updates
invalidate authorization; I7 resourceVersion updates invalidate ACP; I8 modified
manifests invalidate both; I9 shadow mode never changes execution; I10 all runs
deterministic. I1/I2 are proven by **downstream invariance**: compressed vs
uncompressed yields the identical proposed action + ActionGate outcome + ACP
recommendation + composition.

## 8. Verdict rules (frozen)

- **Context layer** → `AUTHORIZED_CONTEXT_SUPPORTED` iff protected-span
  preservation is 100 %, I1 + I2 hold, and real compression > 0.
- **Action layer** → `DETERMINISTIC_AUTHORIZATION_SUPPORTED` iff action-hash is
  deterministic and policy updates invalidate authorization (I6).
- **Operational layer** → `OPERATIONAL_SAFETY_SUPPORTED` iff ACP is deterministic
  and resourceVersion updates invalidate ACP (I7).
- **Integrated stack** → `AI_CONTROL_PLANE_SUPPORTED` iff all invariants pass, 0
  corpus mismatches, and every layer is real; `…_WITH_LIMITATIONS` if it holds but
  a layer rests on a documented stand-in (the deterministic reader for the LLM, no
  live cluster); `…_NOT_SUPPORTED` if any invariant fails.

## 9. Exclusions (frozen)

No live LLM (unavailable + would break deterministic replay); the LLM stage is a
deterministic reader. No live/kind cluster (infeasible offline). Deployment state
authored on the real fixture. ActionGate signing is the HMAC stand-in. One
operation family, one Deployment. Token counts use the compressor's regex
tokenizer (approximation, not a model BPE). Decision-grade integration evidence,
not certification; no production enforcement.
