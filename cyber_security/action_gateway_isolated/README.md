# Action Gateway — Isolated Compromised-Agent Experiment

Determines **mechanically** whether the Action Gateway architecture survives a
fully compromised agent, by building four **enforced** protection domains and
running a 30-attack red-team from inside a genuinely isolated agent.

**Result of the reference run:** `ISOLATED_GATE_THESIS_SUPPORTED` — 26/26 attacks
blocked with all seven prerequisites enforced (see `RED_TEAM_RESULTS.md`). This is
a *reference* result on a local control plane; the boundaries beyond a compromised
broker / signing root / cluster / colluding approvers remain out of scope.

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
| Gateway → broker | **mTLS** (broker requires CN=gateway client cert) | agent has no cert and no route |
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

## Broker, replay, TOCTOU, audit

- **Broker** mints a per-action ServiceAccount + `resourceNames`/verb-scoped Role +
  short-lived TokenRequest token, performs the write, and **verifies teardown**
  (a failure raises `E_TEARDOWN`, never swallowed). No bearer credential ever
  leaves the broker.
- **Durable replay** (`SQLite`): execution-token / approval nonces and the
  single-commit claim survive process restart and are shared across instances; a
  fresh correlation id cannot reset a global watermark.
- **TOCTOU**: writes are optimistic-concurrency (`resourceVersion` CAS on update,
  preconditions on delete, create-fails-if-present); a stale state assumption at
  commit yields `E_STALE_STATE`.
- **Audit** is an append-only, hash-chained SQLite ledger (WORM triggers) whose
  head is signed by a **separate** offline checkpoint key — so a compromised agent
  or gateway can neither rewrite records (no file access) nor re-sign checkpoints
  (no key).

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
