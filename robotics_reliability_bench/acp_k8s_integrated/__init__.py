"""ACP V2.1 — live ActionGate + ACP composition for Kubernetes operations.

Runs the REAL frozen ActionGate authorization engine (`action_gate_ref`) AND the
REAL ACP cloud adapter (frozen ACP core + real `cloud_controller`) on the SAME
bound Kubernetes Deployment operation, in shadow mode, composing their two
verdicts deterministically. No cluster is mutated; neither layer is authoritative.

Offline/reproducible: a live/kind/k3d cluster is infeasible in this environment
(no kubectl/kind/k3d/k8s-client; network-gated binaries) — documented in
`LIVE_K8S_SHADOW_METHOD.md`. Deployment state is modelled from real repository
integration fixtures (`action_gateway_k8s` `web`/`gw-web`, ns `protected`,
replicas 1) with resourceVersion/availability authored and labelled honestly.
"""
