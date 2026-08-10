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

## Finding #I2 — One shared, framed canonicalization for gateway AND broker (N9)

**Context.** The gateway originally built the action hash through
`build_envelope` (which stamps wall-clock into hash-relevant fields) and the state
hash through ad-hoc string concatenation (`f"{ns}/{kind}/{name}@{rv}"`) — not the
length-prefixed framing the frozen spec mandates, and a second, divergent hashing
path from anything the broker could recompute.

**Resolution.** A single `canon` module now computes `action_hash`,
`manifest_digest`, and `state_hash` for **both** the gateway and the broker, over
the frozen JCS canonicalizer + length-prefixed `domain_digest` (N9). Wall-clock is
no longer an input to identity at all: the hash is a pure function of
`(cluster, namespace, api_group, api_version, kind, name, verb, manifest_digest,
policy_hash, state_present, state_rv)`, so an action's identity is stable across
submissions while a genuine state change (new `resourceVersion`) still changes it.
`test_parser_diff.py` asserts `gateway_core.canon is broker_core.canon` — exactly
one implementation.

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

## Finding #I5 — TokenRequest 600s floor; transactional teardown + reconciler (N2)

**Context.** Kubernetes TokenRequest has a 600s minimum lifetime, larger than the
application authorization window. The prior implementation tore the RBAC down in a
`finally` and raised `E_TEARDOWN` on failure **after** the cluster write had already
committed; `execute` then released the commit claim — a double-commit + residual
RBAC + missing-audit defect (independent review N2).

**Resolution.** Execution is now transactional. The mutation, once durable, is
**finalized and audited before teardown** and its commit claim is never released
(guarded on `result_hash IS NULL`). Teardown is a **separate** step; if it does not
confirm, the residual credential is written to a durable **orphan ledger**
(`replaystore.orphans`) and audited, then drained by `broker.reconcile()`, which
deletes + re-verifies each residual and runs `detect_divergence()`. Nothing is
swallowed, no successful execution loses its commit or audit, and reconciliation is
idempotent and testable (measured by `A19` end to end).

## Finding #I6 — Durable replay requires per-actor-unique nonces in tests

**Context.** Because the replay store is durable across runs, a test that reuses a
fixed approval nonce is (correctly) rejected as a replay on the *second* run,
which would fail the *legitimate* first action.

**Resolution.** Test nonces are derived from the per-run action hash (unique per
run), so the durable store's replay rejection is exercised without poisoning
legitimate first-use. This is a test-harness property; the enforcement is correct.

## Remediation of the independent architectural validation (N1–N11)

The independent review (`Project_documentation/action_gate_cyber/cyber_security/INDEPENDENT_ARCHITECTURAL_VALIDATION.md`) was
treated as authoritative. Each finding was addressed with executable evidence; the
scope was limited to those findings (no redesign, no new features).

### #I7 — Complete workload-surface policy, fail closed (N1)

`policy_semantic.check` previously inspected only `spec.containers`. It now validates
the **entire** pod workload surface — `containers` / `initContainers` /
`ephemeralContainers`, `env` / `envFrom` (secretRef/configMapRef), `volumes`
(hostPath / secret / projected-secret / csi / remote), `serviceAccountName`,
`automountServiceAccountToken`, `imagePullSecrets`, pod + container `securityContext`
(privileged / capabilities.add / allowPrivilegeEscalation / runAsRoot / procMount),
and host namespaces. Every level is checked against an **explicit allow-list**
(`SUPPORTED_FIELDS`); any field not modeled yields an `unrecognized_*` violation
(**fail closed**). Measured by `test_remediation.py` and the `A20/A21` channel
attacks (initContainer/envFrom now caught).

### #I8 — Broker independently recomputes the action identity (N5)

The broker no longer trusts the gateway-asserted `action_hash`/`manifest_digest`.
`_verify_action_identity` recomputes both from first principles using the broker's
**own** trusted cluster id, GVR table, and active policy hash; any mismatch is fatal
(`E_ACTION_HASH_MISMATCH` / `E_MANIFEST_DIGEST_MISMATCH` / `E_CLUSTER_MISMATCH` /
`E_GVR_MISMATCH`). Exact-action binding is now enforced where credentials are minted,
not merely asserted by the gateway. Measured by `A9/A14/A15`.

### #I9 — Commit↔audit atomicity + divergence detection (N3)

A commit finalization now stores the linking audit `seq`; `_finalize_and_audit`
appends the audit record then links it. `detect_divergence()` deterministically
reports a finalized commit lacking its audit record, or an audit COMMIT lacking a
finalized commit. Because the transport became multi-threaded (N4), `AuditLedger`
appends now run under `BEGIN IMMEDIATE` + an in-process lock so concurrent commits
cannot fork the hash chain. Measured by `test_remediation.py` and a post-run
`detect_divergence() == []` + `verify_audit().intact`.

### #I10 — Bounded transport, deterministic under overload (N4)

`rpc` now bounds every axis: `MAX_FRAME_BYTES` (rejects oversized frames before
allocation), `READ_TIMEOUT` (idle/slow-loris), a fixed worker pool +
`BoundedSemaphore` with immediate `E_OVERLOADED` shedding (back-pressure, no unbounded
queue), and a bounded accept backlog. Measured by `test_parser_diff.py`
(oversized/truncated/malformed rejection, back-pressure shedding) and `A24`.

### #I11 — SAN-based workload identity (N10)

The broker authenticates the gateway by its certificate **subjectAltName**
(`DNS:gateway` / `URI:spiffe://agw.local/gateway`), not the CN; the gateway verifies
the broker with `check_hostname=True`. A cert signed by the real CA but carrying the
wrong SAN is rejected (`E_TLS_IDENTITY`) — measured by `A7`.

### #I12 — Trust-root pinning + pinned crypto (N8)

Verifier keyrings load a root-owned, read-only `trust_manifest.json` written at key
genesis and refuse any public key whose SHA-256 fingerprint is unpinned or mismatched
(`crypto.PublicKeyring`, fail closed). `ecdsa` is pinned to a known-good minimum
version; below it, `ASYMMETRIC_AVAILABLE` is False → `ISOLATION_NOT_PROVEN`. Trust
establishment / rotation / failure are documented in the README. Measured by
`test_remediation.py`. *(The cluster-binary and PyPI **fetch** integrity — the other
half of the review's N8 — remains a documented supply-chain limitation; pinning here
covers the deployed trust base, not the build-time download.)*

### #I13 — Distributed replay across two brokers, shared store (N7)

`A31` runs a **second** broker instance on the **same** durable store and shows a
committed action's authz is rejected on replay (`E_NONCE_REPLAY`). This demonstrates
duplicate-execution rejection across instances sharing one store. *(True cross-host
distributed atomicity under partition/NFS remains an architectural limitation — the
store is still one SQLite file; see THREAT_MODEL.)*

### #I14 — Two latent bugs surfaced by the new tests (recorded)

- **Manifest aliasing:** `_conditional_write` shallow-copied the manifest and mutated
  the shared `metadata` sub-dict, corrupting the signed intent (broke the 2nd-broker
  replay signature). Fixed with `copy.deepcopy` before the CAS mutation.
- **Audit-chain fork under concurrency:** exposed by the multi-threaded transport;
  fixed as in #I9. Both were found and fixed within the N-series scope.

### #I15 — Harness readiness probe path (recorded, fixed)

`deploy.sh`/`restart.sh` checked `$RUN/gateway.sock` while the socket lives at
`$RUN/sock/gateway.sock`, so deploy always reported "not ready" (exit 1) even though
the services were up. Corrected to the real path so deployment is verifiable.

## Non-findings (checked)

- **Agent cannot interpose after approval.** Decision + execution happen in one
  gateway-side transaction; the agent never holds the gateway→broker authorization.
  A modified/retargeted action now fails **two** independent ways: a different action
  hash invalidates prior approvals, **and** the broker's independent recomputation
  rejects any signed intent whose contents don't match its identity (#I8). Measured
  by A14/A15.
- **Baselines measured, not asserted.** A/B/C are measured with a real
  namespace-edit token against the same cluster; D is the empirical red-team result.
