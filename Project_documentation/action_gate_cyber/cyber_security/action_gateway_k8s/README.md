# Action Gateway K8s — Bypass-Resistant Kubernetes Enforcement (Local Reference Deployment)

The first enforcement deployment against a **real, disposable, local Kubernetes
control plane**. It proves that an autonomous agent cannot modify the protected
Kubernetes namespace except through the admissibility gateway and a **broker-
issued, short-lived, action-bound credential**. Reuses the frozen gate
(`action_gate_ref`), the runtime gateway (`action_gateway`), and the MCP mapping/
audit patterns (`action_gateway_mcp`) — no security primitive is re-implemented.

> **This is a local reference deployment.**
> - Real production requires hardened broker isolation, HSM/KMS-backed keys, secure
>   workload identity, real network enforcement, and operational controls.
> - Mock adapters/fixtures are not production cloud integrations.
> - **A passing local test does not prove universal Kubernetes security.**
> - MCP remains one transport adapter; **the security property comes from
>   credential and network control, not from protocol interception alone.**

## Threat model

The adversary is a compromised / misaligned autonomous agent that can craft
arbitrary tool calls. It must not be able to mutate the protected namespace except
through an admissible, approved, exactly-bound action. Assumptions: the gateway,
broker, and adapter run in a trusted domain the agent cannot reach; the agent holds
**no** cluster credential. Out of scope: an attacker who compromises the broker
process itself (see Trust boundaries), or the host network stack.

## Trust boundaries

| Component | Trust | Holds |
|-----------|-------|-------|
| Agent | untrusted | tool requests only — **no kubeconfig, no token** |
| Gateway / broker / adapter | trusted | admin identity (to mint scoped tokens), decision/token/audit logic |
| Protected Kubernetes API | authority | RBAC, admission, TokenRequest, dry-run |

Kubernetes natively binds namespace, resource, name (get/update/patch/delete),
verb, subject, and expiry. Application-level fields (action hash, token digest,
nonce, policy hash, decision-record hash) are bound in the trusted broker/adapter —
an explicit trust boundary (see `IMPLEMENTATION_FINDINGS.md#K1`).

## Cluster setup

No container runtime is available here, so a real **control plane** (`etcd` +
`kube-apiserver`) is provisioned directly (downloaded from `dl.k8s.io` + the etcd
GCS mirror). It runs real RBAC, TokenRequest, server-side dry-run, PodSecurity
admission, and optimistic concurrency — but no kubelet/scheduler/controller-manager
(workloads don't schedule; objects are created/validated/admission-controlled). See
`IMPLEMENTATION_FINDINGS.md#K2`.

```bash
cd cyber_security/action_gateway_k8s
bash scripts/cluster_up.sh        # idempotent: download bins, gen PKI, start etcd+apiserver
bash scripts/cluster_fixtures.sh  # protected + sandbox namespaces + fixtures
# ... or via the CLI:  python3 -m action_gateway_k8s.cli env-up
bash scripts/cluster_down.sh      # teardown + wipe state
```

Namespaces: `protected` (restricted PodSecurity, the only *mutable* namespace) and
`sandbox`. Fixtures: `app-config` (ConfigMap), `web` (Deployment + Service),
`app-secret` (Secret, never exportable through the gateway).

## Gateway and broker flow

```
agent tool call
   │  prepare  → validate + map → canonical envelope (bound: cluster, ns, group/
   │             version, kind, name, manifest digest, verb, scope, state hash,
   │             rollback, policy version) → submit (real current-state hash)
   │  evaluate → frozen gate: MUST_HAVE kubernetes_admission (hard) +
   │             REQUIRE_SIMULATION + (delete) rollback + dual-control approver
   │  dry-run  → REAL server-side dry-run → bound structured simulation evidence
   │  approve  → exact-action, exact-policy approval (destructive)
   │  execute  → verify token (action/policy/state/nonce) → broker mints a
   │             per-action ServiceAccount + resource-scoped Role + short-lived
   │             TokenRequest token → adapter performs the REAL API op with that
   │             single-use capability → RBAC torn down → audit
   ▼
protected Kubernetes API
```

Every stage is recorded in two tamper-evident audit chains (protocol +
enforcement), verified after each append.

## Isolation model (what is proven)

- **No durable credential** in the agent environment (no kubeconfig/token/files).
- **Anonymous** direct API access → 403.
- **Bare ServiceAccount token** (without the broker-minted Role) → 403.
- Scoped capability is **namespace-, resource-, name-, verb-, subject-, and expiry-
  bound** (a token for one resource is 403 on another name/namespace).

**Not proven** (honest): packet-level network isolation. Without a CNI/container
isolation, NetworkPolicy is not enforced. Isolation here is **credential-based**.
See `IMPLEMENTATION_FINDINGS.md#K3`.

## Policy examples (`policy.py` + admission checks)

Signed Kubernetes bundle (frozen rule schema): DEPLOY requires
`kubernetes_admission` + server-side dry-run; DB_DELETE additionally requires a
rollback attestation + dual-control approval. Deterministic admission checks
(withhold the admission evidence, so the **gate** denies): deny cluster-admin /
wildcard RBAC, deny mutation outside the allowed namespace, deny privileged
containers, deny hostNetwork/PID/hostPath, deny public Service exposure, require
resource limits. Secret export via `kubernetes.get` is denied. Privileged/
hostNetwork are **also** rejected by the real apiserver at dry-run (defence in
depth).

## Dry-run semantics

`kubernetes.apply`/`delete` bind a **real** server-side dry-run
(`?dryRun=All`) result as structured simulation evidence: producer/version, action
hash, manifest digest, state hash, validity interval, affected resources, predicted
object, defaulting changes, warnings, and unknown effects — never a bare
safe/unsafe boolean. Changing the manifest or current state changes the action hash
and unbinds the evidence.

## Local demo & tests

```bash
python3 demos/run_demos.py          # 18 real-cluster demonstrations (SKIP if no cluster)
python3 -m pytest -q                # unit (no cluster) + e2e (SKIP if no cluster)

# CLI (file-backed session; never prints tokens/secrets)
python3 -m action_gateway_k8s.cli env-up
python3 -m action_gateway_k8s.cli start
python3 -m action_gateway_k8s.cli prepare --tool kubernetes.apply --args \
  '{"namespace":"protected","kind":"ConfigMap","name":"cm","manifest":{"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"cm","namespace":"protected"},"data":{"a":"b"}}}'
python3 -m action_gateway_k8s.cli evaluate req-1     # -> SIMULATE_AND_RETRY
python3 -m action_gateway_k8s.cli dry-run  req-1     # -> ALLOW (real dry-run)
python3 -m action_gateway_k8s.cli execute  req-1     # -> COMPLETED (live)
python3 -m action_gateway_k8s.cli verify
```

CLI commands: `env-up, env-status, env-down, start, list-tools, list-protected,
prepare, evaluate, dry-run, escalations, approve, execute, convergence, audit,
verify, metrics, demos`.

The eighteen demonstrations: read a deployment; apply a safe deployment after
dry-run; apply a config map; reject privileged; reject wildcard RBAC; reject
outside-namespace mutation; require approval before delete; execute the approved
delete; reject modified manifest / modified target / replayed token / replayed
capability / expired capability / TOCTOU / concurrent duplicate; reject direct API
access; prove no durable credential; detect predicted-vs-actual divergence.

## Package layout

```
action_gateway_k8s/
  cluster.py      control-plane lifecycle + availability + admin client
  kubeclient.py   shell-free REST client (CA + client-cert/bearer)
  broker.py       KubernetesCredentialBroker (SA+Role+RoleBinding+TokenRequest)
  adapter.py      real KubernetesAdapter (redeem capability -> API op -> teardown)
  mapping.py      tool -> canonical envelope (fail-closed); manifest bound as string
  policy.py       signed k8s bundle + deterministic admission checks
  simulation.py   real server-side dry-run -> bound structured evidence
  server.py       K8sGateway orchestration + real state oracle + convergence
  cli.py          file-backed JSON CLI
scripts/          cluster_up.sh / cluster_fixtures.sh / cluster_down.sh
demos/            18 real-cluster demonstrations
tests/            test_unit.py (no cluster) + test_e2e.py (cluster-gated, SKIP if down)
IMPLEMENTATION_FINDINGS.md
```

## Limitations

Control-plane-only cluster (no scheduling); credential-based isolation only (no
packet-level network enforcement, no CNI); mock fixtures; the broker's application-
level bindings depend on broker-process integrity; single reference apiserver on
loopback. See `IMPLEMENTATION_FINDINGS.md`.

## Teardown

```bash
bash scripts/cluster_down.sh   # or: python3 -m action_gateway_k8s.cli env-down
```
Stops the apiserver + etcd and wipes `/tmp/k8sref` state (binaries cached in
`/opt/k8s-ref/bin` are reused on the next `cluster_up`).

## Production gaps

Real short-lived workload identity + HSM/KMS-backed signing; a hardened, isolated
broker service (out-of-process, least-privilege); real network enforcement
(NetworkPolicy + CNI, egress control, proxy-only API access); durable, access-
controlled audit storage; per-cluster policy governance; and validation across the
full Kubernetes resource surface (this reference covers a representative subset).
