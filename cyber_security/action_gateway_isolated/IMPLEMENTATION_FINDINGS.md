# IMPLEMENTATION_FINDINGS — Isolated Action Gateway

No frozen specification, and no existing package (`action_gate_ref`,
`action_gateway`, `action_gateway_mcp`, `action_gateway_k8s`), was modified by this
work — it is an additive package. Digest and action-hash semantics are reused
unchanged. Findings below record where the isolated deployment diverges from, or
constrains, the earlier design.

## Finding #I1 — HMAC stays intra-domain; cross-domain trust is Ed25519 only

**Context.** The frozen gate (`action_gate_ref.signing`) signs with shared-secret
HMAC, which the adversarial review correctly flagged: verification authority =
forgery authority. The task forbids altering frozen digest/action-hash semantics.

**Resolution.** The frozen HMAC scheme is retained **only inside the gateway
domain** (the gateway's internal decision bookkeeping) and is **never** trusted
across a trust boundary. Every artifact the broker relies on — the execution
authorization, the human approvals, the policy identity — is a **new Ed25519**
artifact verified with a public key. The broker holds no signing key. Consequently
the "verification = forgery" property does not hold at any boundary the adversary
can reach. Action-hash/canonicalization semantics are reused verbatim.

**Impact.** None to frozen semantics. The internal HMAC token is a local
implementation detail; the security decision rests on asymmetric signatures.

## Finding #I2 — Action identity must be deterministic for the approval flow

**Context.** `action_gateway.mapping.build_envelope` stamps wall-clock into
hash-relevant fields (delegation `exp`, `state_freshness.as_of`), so the same
logical action hashed differently on each submission — an approval bound to it
would not re-apply after escalation.

**Resolution.** The isolated gateway builds the *hash-relevant* envelope with a
fixed clock, so an action's identity is stable across submissions, while real time
is used only for the (non-hashed) authorization expiry and nonce. The real
`current_state_hash` still tracks live cluster state, so a genuine state change
still changes the action hash (correctly invalidating an approval). No frozen
field or semantic changed; only the clock *input* is deterministic.

## Finding #I3 — `ecdsa` (pure-Python) chosen; `cryptography` unavailable

**Context.** `cryptography`/`pynacl` require a working `cffi`/Rust backend that
this environment could not build. The `ecdsa` package (pure-Python, established;
Ed25519 + ECDSA) installs and runs.

**Resolution.** Ed25519 via `ecdsa` with PKCS#8 private-key encoding. It is an
established library, not hand-rolled primitives. If it is absent, `crypto.
ASYMMETRIC_AVAILABLE` is False and the verdict is forced to `ISOLATION_NOT_PROVEN`.

**Impact.** `ecdsa` is a reference-grade signer; production wants an audited,
hardware-backed implementation (HSM/KMS). Documented as a limitation.

## Finding #I4 — Isolation is namespace/user/mTLS-based, not container/CNI-based

**Context.** No container runtime (Docker/containerd) is available, so
kind/k3d/minikube and CNI-enforced NetworkPolicy cannot run.

**Resolution.** Genuine isolation via Linux **network namespaces** (`unshare
--net` gives the agent its own empty loopback — the apiserver and broker are
literally *Network unreachable*), **separate Unix users** (0400 key ownership),
and **mTLS**. This is real, enforced isolation — verified in the probe — but it is
single-host and does not use packet-level NetworkPolicy. A different, over-
privileged credential elsewhere in the cluster is outside the gateway's control.

**Impact.** The SUPPORTED verdict is scoped to what these mechanisms enforce on one
host (stated in THREAT_MODEL). Multi-host / CNI / kernel-isolation is future work.

## Finding #I5 — TokenRequest 600s floor; broker enforces the tighter window + teardown

**Context.** Kubernetes TokenRequest has a 600s minimum lifetime, larger than the
application authorization window.

**Resolution.** The broker enforces the tighter application expiry itself and tears
down the per-action RBAC (SA/Role/RoleBinding) immediately after a single use,
**verifying** the teardown (re-GET the SA) and raising `E_TEARDOWN` on failure —
never swallowing it. So a leaked SA token is inert once RBAC is revoked, well
inside the 600s window.

## Finding #I6 — Durable replay requires per-actor-unique nonces in tests

**Context.** Because the replay store is durable across runs, a test that reuses a
fixed approval nonce is (correctly) rejected as a replay on the *second* run,
which would fail the *legitimate* first action.

**Resolution.** Test nonces are derived from the per-run action hash (unique per
run), so the durable store's replay rejection is exercised without poisoning
legitimate first-use. This is a test-harness property; the enforcement is correct.

## Non-findings (checked)

- **Agent cannot interpose after approval.** Decision + execution happen in one
  gateway-side transaction; the agent never holds the gateway→broker authorization,
  so "modify/retarget after approval" reduces to submitting a different request
  (different action hash → prior approval invalid). Confirmed by A14/A15.
- **Baselines measured, not asserted.** A/B/C are measured with a real
  namespace-edit token against the same cluster; D is the empirical red-team result.
