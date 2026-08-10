# CER Identity Profile (Deliverable 2 — identity model)

How a CER's identity is defined, what it excludes, hashing, replay, versioning. Grounded in the implemented ActionGate identity-profile **v2** (`action_gate_ref/projection.py`) and `cer_v0_1/spec.py`.

Labels: `FACT` (implemented + tested) · `RECOMMENDATION`.

---

## 1. Identity definition

`FACT`. `CER.action_digest := ActionGate.action_hash(to_envelope(CER), identity_profile="v2")`.

The CER identity is **not** a second, parallel hashing scheme — it is *defined as* the ActionGate v2 action identity of the actuation the CER describes. Consequence proven in the smoke test and e2e tests: `gate.evaluate(...).action_hash == CER.action_digest`. One actuation ⇒ one identity, used identically by the runtime, ActionGate (binding), and the audit record.

## 2. What defines identity vs what must never

`FACT` (`projection.project_action_payload`, profile v2). Identity is a pure function of the actuation + authority + state binding + policy:
- **In the hash:** agent_identity.{id,key_id}, delegator, delegation_chain, tool, operation, target_resource, arguments, credential_scope, current_state_hash, state_freshness, reversibility, policy_version, correlation_id, sequence_id (+ rollback_plan/linked_ticket/expected_effects_digest when present).
- **Excluded (v2 provenance):** `runtime`, `model_provider`, `objective` — the three decision-inert provenance fields removed in this milestone.
- **Excluded (v2 base, inherited from v1):** action_id, timestamp, agent_identity.sig, approvals, attestation.

`RECOMMENDATION` / justification: only the three named provenance fields were removed, and only after auditing them decision-inert (no `gate.py` predicate reads them). No field was removed "to make hashes match." `correlation_id`/`sequence_id` remain in identity; the two runtimes carry them from the **shared** actuation request, so they correlate the same logical action honestly rather than being excluded.

## 3. Hashing

`FACT` (`action_gate_ref/hashing.domain_digest`):
```
digest = H( LP("SYMBOLU/ACTIONGATE/ACTION/v1") || LP(canon_ver="1") || LP(schema_ver="2.0.0") || LP(canonical_bytes) )
LP(x) = uint64_be(len(x)) || x ;  H = SHA-256 (default), algorithm-prefixed
```
`canonical_bytes` = JCS canonicalization of the v2-projected payload. The `schema_ver="2.0.0"` frame element is what domain-separates a v2 digest from a v1 digest of the same envelope — they are always different values (tested: `test_v1_and_v2_are_domain_separated`).

## 4. Replay

`FACT` / `RECOMMENDATION`. Identity stability and replay defense are **orthogonal**:
- The *same* `action_digest` may legitimately recur (a later RETRY of the same action) — identity does not forbid repetition.
- Replay is defended at *authorization*: single-use nonce on approvals (`approval.verify_approval` step 4) + commit-time state revalidation (ACP `ReferenceCommitRevalidator`) + `external_state_binding` (stale `resource_version`/`state_hash` invalidates). So a replayed CER against changed state is rejected by state binding, not by identity.

## 5. Versioning

`FACT`. Three independent axes, never conflated:
- `cer_version` = "0.1" (this envelope spec).
- `profile` = "cer.k8s.scale/0.1" (domain action semantics).
- `policy_ref.version` (enterprise policy).
Plus the ActionGate identity profile `v2` (fixed for CER V0.1). A future breaking identity change = a new `envelope_schema_version` (e.g. "3.0.0") and thus a new digest namespace — old and new never collide (the same discipline that separates v1 from v2 today).

## 6. Cross-runtime property (the hypothesis)

`FACT` (proven in Stage 1 tests + Stage 7 run):
- Same actuation, different runtime/model/objective → **same** `action_digest`.
- Any identity-bearing change (operation, target, arguments, credential_scope, state binding, reversibility, policy) → **different** `action_digest`.
- v1 (legacy) still includes provenance and is byte-identical to historical behavior; v1 and v2 are never confusable.
