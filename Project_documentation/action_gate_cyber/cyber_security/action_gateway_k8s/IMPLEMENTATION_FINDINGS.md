# Implementation Findings — Action Gateway Kubernetes deployment

Contradictions, ambiguities, and narrow resolutions the real-cluster enforcement
deployment exposed. No frozen specification was changed. Where the runtime gateway
(`action_gateway`) was touched, the changes are additive and do not alter any
frozen hash, approval, token, evidence, or decision-outcome semantics.

Frozen sources: `../ACTION_GATE_SPECIFICATION.md`,
`../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`, `../AGENT_ACTION_ADMISSIBILITY_MVP.md`.
Reused packages: `../action_gate_reference/action_gate_ref` (via `action_gateway`),
`../action_gateway`, `../action_gateway_mcp`.

---

## Finding #K1 — Kubernetes cannot bind every application-level field (trust boundary)

**Clause.** Task §3 requires the capability to be bound to action hash, execution-
token digest, tool, operation, namespace, resource kind/name, verb, expiry, nonce,
policy hash, and decision-record hash — "If Kubernetes cannot cryptographically
bind every application-level field, enforce the remainder in the trusted broker/
adapter and document the trust boundary precisely."

**What Kubernetes binds natively** (proven against the real cluster): namespace,
resource, name (via RBAC `resourceNames`, for get/update/patch/delete), verb,
subject (ServiceAccount), and token expiry (TokenRequest).

**What the trusted broker + adapter bind** (not expressible in RBAC): action hash,
execution-token digest, nonce, policy hash, decision-record hash, tool, operation.
These live in `KubernetesCredentialBroker` (which mints only for a verified
execution token and records the metadata) and `KubernetesAdapter` (which issues
only the exact approved object path). **Trust boundary:** an attacker who fully
compromises the broker process could forge these; the cluster alone does not
prevent it. Production requires broker isolation + HSM/KMS-backed signing.

**Sub-case — `create` and `resourceNames`.** RBAC `resourceNames` does not
constrain the `create` verb (an object has no name before creation), so for
create/apply the exact name is enforced by the adapter (it only ever issues the
approved object path), while RBAC still binds namespace + resource + verb. Proven:
a scoped token for one resource is 403 on a different name and a different
namespace (`test_scoped_token_cannot_touch_other_resource`).

**Frozen semantics changed?** No.

---

## Finding #K2 — Control-plane-only cluster (no kubelet/scheduler/controller-manager)

**Context.** No container runtime (Docker/containerd) is available in the
environment, so `kind`/`k3d`/`minikube` cannot run. A REAL control plane
(`etcd` + `kube-apiserver`, downloaded from `dl.k8s.io`/the etcd GCS mirror) is
provisioned instead. This is a genuine Kubernetes API server — RBAC, TokenRequest,
server-side dry-run, PodSecurity admission, and optimistic-concurrency all run for
real — but it has no kubelet/scheduler/controller-manager.

**Consequences (documented honestly):**
- Workloads do not actually *schedule*; Deployment/Pod objects are created,
  validated, and admission-controlled, but no pods run. The security thesis is
  about API-level mutation control, which is fully exercised.
- No ServiceAccount controller ⇒ `default` service accounts are created explicitly
  by the fixtures script.
- No CNI ⇒ `NetworkPolicy` objects can be created but are **not enforced**; network
  isolation is therefore **not** proven at the packet level (see #K3).

**Not a silent fallback.** `cluster.is_available()` gates all cluster-dependent
tests; when no control plane is reachable they are SKIPPED, never falsely passed.

**Frozen semantics changed?** No.

---

## Finding #K3 — Network/egress isolation is credential-based, not packet-enforced

**Clause.** Task §4 asks to demonstrate the agent cannot bypass the gateway and
call the protected API directly, using "the strongest isolation available locally."

**What is proven** against the real cluster: (a) the agent environment holds **no**
kubeconfig and **no** bearer token (`test_no_durable_credential`,
`k17`); (b) an anonymous request to the protected API is rejected (403); (c) a bare
ServiceAccount token *without* the broker-minted Role is rejected (403)
(`test_anonymous_and_bare_token_denied`, `k16`). So without a credential the agent
cannot mutate the protected namespace — enforcement comes from **credential
control**, as the thesis requires.

**What is NOT proven:** packet-level network isolation (separate network
namespaces / NetworkPolicy / firewall). Without a CNI or container isolation in
this environment, NetworkPolicy is not enforced and the apiserver is reachable on
loopback. A production deployment must add real network enforcement; a passing
local test does **not** prove network isolation.

**Frozen semantics changed?** No.

---

## Finding #K4 — Kubernetes-specific admission expressed as required evidence (no gate bypass)

**Clause.** Task §8: "Kubernetes-specific checks … must not bypass the frozen gate."

**Resolution.** The frozen gate has a fixed fact set and cannot learn new facts
(privileged, wildcard-RBAC, …). So Kubernetes risk checks are expressed as
*required evidence*: the custom policy rule set (built with the frozen rule schema)
requires `MUST_HAVE kubernetes_admission` (hard). The deterministic admission
checker produces that evidence **only** when no violation is found; a violation
withholds it, so the **gate itself** DENYs (hard `MUST_HAVE` unmet). Manifest-level
risks (privileged, hostNetwork) are ALSO rejected by the real apiserver at
server-side dry-run — defence in depth. The gate remains the sole decision
authority; the k8s checks feed it, never bypass it.

**Frozen semantics changed?** No — a custom *signed* bundle uses only existing
operators; `Gateway` gained an additive `policy_bundle=` parameter.

---

## Finding #K5 — Manifests carry bare JSON numbers; bound as a canonical string

**Clause.** The Action Profile forbids bare JSON numbers in a hashed envelope, but
Kubernetes manifests contain them (`replicas`, ports, limits).

**Resolution.** The manifest is serialized to a deterministic JSON **string**
(`manifest_json`) and its digest recorded (`manifest_digest`); both are string
values covered by the action hash, so any manifest change is detected
(`test_manifest_digest_binding`). Returned API objects are likewise stringified
before the frozen result-hasher sees them.

**Frozen semantics changed?** No.

---

## Finding #K6 — SA-token minimum lifetime (600s) exceeds the execution-token TTL

**Context.** The Kubernetes TokenRequest API enforces a 600s minimum token
lifetime; the execution-token TTL defaults to 300s.

**Resolution.** The broker enforces the tighter execution-token expiry itself
(`ScopedCredential.expires_at = token.expiration`, checked in `validate/redeem`),
and tears down the per-action RBAC (SA/Role/RoleBinding) immediately after a single
use, so a leaked SA token cannot be replayed at the cluster even within its 600s
window. Single-use is thus enforced at three layers: execution-token nonce,
capability `_used` set, and RBAC teardown.

**Frozen semantics changed?** No.

---

## Additive changes to `action_gateway` (no frozen semantics affected)

- `Gateway(policy_bundle=…)` / `Gateway.restore(policy_bundle=…, adapters=…)` — allow
  a custom signed policy + custom adapters (needed for the Kubernetes rule set and
  the real adapter). Default behaviour unchanged; existing suites remain green.
- The gateway's `MockStateOracle` is replaced *per instance* with a real
  `K8sStateOracle` (live resourceVersion) so both the submitted envelope's
  `current_state_hash` and the commit-time TOCTOU re-read reflect real cluster
  state. The gateway's oracle interface is unchanged.
