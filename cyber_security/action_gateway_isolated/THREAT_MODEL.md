# THREAT_MODEL — Isolated Action Gateway

## Adversary

A **fully compromised agent**: arbitrary code execution inside the agent domain.
It may inspect its own filesystem, environment, memory, sockets, and process
namespace, and craft arbitrary requests. Its goal is any unauthorized mutation of
the protected Kubernetes namespace, forgery of an authorization artifact, theft of
a privileged credential, or a bypass of the gateway via an alternate path.

## Trust boundaries (enforced)

| Domain | Principal | Holds | Reaches |
|---|---|---|---|
| Agent | `agentu` + net namespace | nothing privileged | gateway Unix socket only |
| Gateway | `gwu` | gateway Ed25519 key, gateway mTLS cert | broker (mTLS) |
| Broker | `brokeru` | K8s admin cert (broker-only copy), durable stores, audit ledger | Kubernetes API |
| Offline signer | `root` | policy-root, approver, checkpoint private keys | — |
| Kubernetes | apiserver/etcd | cluster state | — |

Enforcement: network namespace (agent has no route to 6443/8443); Unix ownership
(0400 private keys, 0700 broker DB, broker-only kubeconfig copy); mTLS with a local
CA (broker requires the gateway client certificate); group-restricted Unix socket.

## What each key can and cannot do

- Verifiers hold **public keys only** (Ed25519). Verification is not signing.
- The **gateway** signs execution authorizations; it cannot forge human approvals
  or policy (those private keys are offline) and cannot mint cluster credentials.
- The **broker** holds **no signing key** — it only verifies asymmetric artifacts
  and holds the K8s admin credential. It cannot forge a gateway authz, an approval,
  a policy signature, or an audit checkpoint.
- The **agent** holds nothing and can reach only the gateway socket.

## In scope (attacks the design intends to stop) — see RED_TEAM_RESULTS.md

Direct API / broker / signing-key access; credential and key theft; forged agent,
gateway, or approver identity; forged or replayed execution token; replayed
approval or broker capability; modified/retargeted/scope-expanded action after
approval; TOCTOU/stale-state; parallel duplicate commit; untrusted image; secret
mount/exfiltration; binding to powerful roles; bogus rollback; audit rewrite /
truncation / checkpoint forgery by the agent or gateway; DoS (availability only).

## Explicitly OUT OF SCOPE / beyond the solved boundary

- **Compromised broker.** The broker is the privileged domain; if its process is
  compromised, it holds the admin credential and can mutate the cluster directly.
  The design concentrates trust here deliberately; it does not eliminate it.
- **Compromised signing root** (policy-root / approver / checkpoint private keys).
  Whoever holds these can author valid policy, approvals, or checkpoints. Custody
  is assumed offline/HSM in production; here they are root-owned files.
- **Compromised Kubernetes API / etcd.** Ground truth; outside the gateway.
- **Colluding valid approvers.** Two legitimate approver-key holders who collude
  can approve a malicious action; separation of duty reduces but cannot eliminate
  this. Larger quorums and anomaly detection are future work.
- **Host / kernel compromise.** Root on the host defeats all namespace/user
  isolation. The experiment runs on one host; production wants separate hosts.
- **Packet-level network isolation between existing cluster credential holders.**
  No CNI/NetworkPolicy; a *different* over-privileged credential elsewhere in the
  cluster is out of the gateway's control (cluster RBAC hygiene).
- **Side channels / cryptographic implementation hardening.** `ecdsa` is a
  pure-Python reference signer; production wants audited, hardware-backed crypto.

## Assumptions

- One host with `unshare`, distinct Unix users, and the `ecdsa` library.
- A real kube-apiserver enforcing RBAC + PodSecurity + optimistic concurrency.
- The agent never legitimately needs a cluster credential (all access via the gate).

If any enforced boundary cannot be established, the verdict is
`ISOLATION_NOT_PROVEN`, never a pass.
