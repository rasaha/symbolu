# Action Gateway — Isolated Compromised-Agent Experiment

Determines **mechanically** whether the Action Gateway architecture survives a
fully compromised agent, by building four **enforced** protection domains and
running a fully-executed compromised-agent red-team from inside a genuinely isolated
agent.

**Result of the reference run:** `ISOLATED_GATE_THESIS_SUPPORTED` — **27/27 attacks
blocked, all executed and measured (no asserted passes)**, with all seven
prerequisites enforced (see `RED_TEAM_RESULTS.md`). This is a *reference* result on a
local control plane; the boundaries beyond a compromised broker / signing root /
cluster / colluding approvers remain out of scope.

The enforcement path was hardened against the independent architectural validation
(`../INDEPENDENT_ARCHITECTURAL_VALIDATION.md`, findings N1–N11); see
`IMPLEMENTATION_FINDINGS.md`.

## What the adversarial review demanded, and what this builds

The review found two load-bearing gaps: (1) shared HMAC signing makes verification
authority forgery authority; (2) agent, gateway, broker, signing keys, and the
privileged Kubernetes credential were not separated into enforced domains. This
package fixes both and tests the result.

```
Fully compromised agent   (netns + unprivileged user; holds nothing)
        │ authenticated requests only (Unix socket, group-restricted)
        ▼
Isolated gateway          (gwu; holds only the gateway signing key)
        │ Ed25519-signed authorization only, over mTLS
        ▼
Isolated broker/execution (brokeru; sole holder of the K8s admin credential)
        │ short-lived, resource/verb-scoped, single-use capability
        ▼
Protected Kubernetes API  (real etcd + kube-apiserver; RBAC + PodSecurity)
```

## Isolation mechanism (all real, all enforced)

| Boundary | Mechanism | Proven |
|---|---|---|
| Agent → network | Linux **network namespace** (`unshare --net`) | apiserver:6443 and broker:8443 are *Network unreachable* |
| Agent → files/keys | Separate **Unix users** + 0400 ownership | every private key / kubeconfig / DB read = `PermissionError` |
| Agent → gateway | **Unix domain socket**, group `agwsock`, 0660 | the only reachable channel |
| Gateway → broker | **mTLS**, broker requires the gateway **SAN** (`DNS:gateway` / `URI:spiffe://…/gateway`), not the CN | a CA-signed wrong-SAN cert → `E_TLS_IDENTITY`; agent has no cert and no route |
| Broker → K8s | mTLS admin cert (broker-only copy) | agent/gateway cannot read it |

Container tooling is unavailable in this environment, so isolation uses Linux
namespaces + users + mTLS rather than containers. What is and isn't enforced is
stated explicitly in `THREAT_MODEL.md` and `IMPLEMENTATION_FINDINGS.md`.

## Asymmetric authorization (Ed25519, verification ≠ forgery)

Every cross-domain artifact is Ed25519-signed (`ecdsa` library; no hand-rolled
crypto). Verifiers hold **public keys only**. Distinct custody per purpose:

| key | private holder | who verifies |
|---|---|---|
| `policy_root` | offline (root) | broker (public) |
| `gateway` (execution authz) | gateway (gwu) | broker (public) |
| `approver:*` (human approval) | offline (root) | gateway + broker (public) |
| `checkpoint` (audit) | offline (root) | anyone (public) |

The gateway cannot forge approvals or policy; the broker holds no signing key (it
only verifies); the agent holds nothing. The frozen HMAC scheme stays *inside* the
gateway domain and is never trusted across a boundary (see IMPLEMENTATION_FINDINGS).

### Trust roots are pinned (establishment · rotation · failure)

- **Establishment.** At key genesis the offline root writes `pub/trust_manifest.json`
  — the SHA-256 fingerprint of every purpose's public key. `deploy.sh` sets it
  root-owned + read-only (`0444`) so the pins cannot be rewritten by the gateway,
  broker, or agent.
- **Enforcement.** `crypto.PublicKeyring` refuses to trust any public key that is not
  in the manifest or whose fingerprint does not match — **fail closed**. Verification
  of an unpinned/mismatched key simply returns False.
- **Rotation.** Regenerate the affected keypair under offline-root custody and
  rewrite the manifest (`crypto.write_trust_manifest`); distribute the new public key.
  Until the manifest is updated, the new key is untrusted (fail closed), so rotation
  is atomic from the verifier's point of view.
- **Crypto pin.** `ecdsa` is pinned to a known-good minimum version; below it,
  `ASYMMETRIC_AVAILABLE` is False and the verdict is forced to `ISOLATION_NOT_PROVEN`
  (never a silent downgrade).
- *Out of scope:* the integrity of the **download** of the cluster binaries and the
  `ecdsa` wheel is a build-time supply-chain concern (documented limitation); the
  pinning above anchors the **deployed** trust base.

## Broker, replay, TOCTOU, audit

- **Independent recomputation.** Before acting, the broker recomputes the action
  hash, manifest digest, target identity, namespace, GVR, and policy binding from its
  **own** trusted inputs (via the shared `canon` module) and rejects any mismatch
  (`E_ACTION_HASH_MISMATCH` / `E_MANIFEST_DIGEST_MISMATCH` / …). Exact-action binding
  is enforced by the component that mints credentials, not asserted by the gateway.
- **Broker** mints a per-action ServiceAccount + `resourceNames`/verb-scoped Role +
  short-lived TokenRequest token and performs the write. No bearer credential ever
  leaves the broker.
- **Transactional teardown.** After a durable mutation, the commit is **finalized and
  audited before teardown**, and its claim is never released. If teardown does not
  confirm, the residual credential is written to a durable **orphan ledger** and
  audited, then drained by `broker.reconcile()` (delete + re-verify + divergence
  check). No successful execution loses its commit or audit; reconciliation is
  idempotent.
- **Durable replay** (`SQLite`): execution-token / approval nonces and the
  single-commit claim survive process restart and are shared across instances (a
  second broker on the same store rejects a replay with `E_NONCE_REPLAY`); a fresh
  correlation id cannot reset a global watermark.
- **TOCTOU**: writes are optimistic-concurrency (`resourceVersion` CAS on update,
  preconditions on delete, create-fails-if-present); a stale state assumption at
  commit yields `E_STALE_STATE`.
- **Audit** is an append-only, hash-chained SQLite ledger (WORM triggers) whose
  head is signed by a **separate** offline checkpoint key. Appends are serialized
  (`BEGIN IMMEDIATE` + in-process lock) so the multi-threaded broker cannot fork the
  chain. A commit and its audit record are linked by `seq`, and `detect_divergence()`
  deterministically flags a commit without audit (or vice-versa).

## Semantic policy — validated workload surface (fail closed)

`policy_semantic.check` validates the **complete** pod workload surface against an
explicit allow-list; any field it does not model produces an `unrecognized_*`
violation (**fail closed**). Enforced fields (`policy_semantic.SUPPORTED_FIELDS`):

| group | fields (dangerous values flagged) |
|---|---|
| pod spec | `containers`, `initContainers`, `ephemeralContainers`, `volumes`, `serviceAccountName`/`serviceAccount`, `automountServiceAccountToken`, `hostNetwork`/`hostPID`/`hostIPC`, `shareProcessNamespace`, `hostUsers`, `securityContext`, `imagePullSecrets` (+ modeled scheduling/lifecycle fields) |
| container (all three lists) | `image` (pinned-digest required), `env` (secretKeyRef → `secret_env`), `envFrom` (secretRef → `secret_envfrom`), `securityContext`, … |
| volume | `hostPath` → `host_path`, `secret`/projected-secret → `secret_mount`, `csi` → `csi_volume`, remote block sources → `remote_volume`; benign `emptyDir`/`configMap`/`downwardAPI`/`pvc`/`ephemeral` pass |
| securityContext (pod + container) | `privileged`, `capabilities.add`, `allowPrivilegeEscalation`, `runAsNonRoot=false`/`runAsUser=0`, `procMount` |

Both the gateway (to gate the decision) and the broker (defence in depth) run this
same check. `SUPPORTED_FIELDS` is asserted by the unit tests, so the documented
surface cannot silently drift from the enforced one.

## Bounded transport (deterministic under overload)

The agent↔gateway and gateway↔broker RPC is bounded on every axis (`rpc.py`):
`MAX_FRAME_BYTES` (oversized frames rejected before allocation), `READ_TIMEOUT`
(idle/slow-loris), a fixed worker pool + `BoundedSemaphore` that immediately replies
`E_OVERLOADED` when at capacity (back-pressure — no unbounded queue), and a bounded
accept backlog. Overload fails deterministically (shed or connection reset), never a
hang; malformed/truncated frames raise deterministically.

## Run it

```bash
# 1. bring up the real control plane (from the sibling package)
(cd ../action_gateway_k8s && bash scripts/cluster_up.sh && bash scripts/cluster_fixtures.sh)
# 2. deploy the four isolated domains (root: creates users, keys, certs, services)
sudo bash scripts/deploy.sh
# 3. run the compromised-agent experiment + mechanical verdict
sudo python3 -m action_gateway_isolated.run          # prints JSON, writes redteam_results.json
# 4. baseline comparison
sudo python3 -m action_gateway_isolated.cli baselines
# teardown
sudo bash scripts/teardown.sh
```

## Tests

```bash
python3 -m pytest tests/test_unit.py -q          # crypto/replay/authz/policy/audit (no cluster)
python3 -m pytest tests/test_remediation.py -q   # N1 fail-closed, N2 orphans, N3 divergence, N8 pinning
python3 -m pytest tests/test_parser_diff.py -q   # N9/N11 canonicalization + N4 bounded transport
python3 -m pytest tests/test_isolation_e2e.py -q # SKIPs unless the stack is deployed (=> NOT_PROVEN)
```
A skipped isolation test is **not** a pass — it maps to `ISOLATION_NOT_PROVEN`.

## Verdict semantics (preregistered)

- `ISOLATED_GATE_THESIS_SUPPORTED` — separate domain, no agent creds/keys, network
  denied, asymmetric verification separation, durable replay across restart/multi-
  instance, conditional writes close TOCTOU, no attack causes unauthorized
  mutation, audit unforgeable by agent/gateway, all against real components.
- `ISOLATED_GATE_THESIS_NOT_SUPPORTED` — any attack causes unauthorized mutation
  or authorization forgery.
- `ISOLATION_NOT_PROVEN` — the environment cannot enforce the required boundaries
  (missing crypto lib, no netns, no users, no cluster). Never converted to a pass.

## Limitations / out of scope (see THREAT_MODEL.md)

A compromised **broker**, a compromised **signing root**, a compromised
**Kubernetes API/etcd**, and **colluding valid approvers** are outside the solved
boundary. Isolation is namespace/user/mTLS-based (no container runtime, no CNI);
packet-level NetworkPolicy is not used. `ecdsa` is a pure-Python signer (a
reference choice); production wants HSM/KMS-backed keys and hardened broker
isolation.
