# Kubernetes Operation Identity Binding (V2.1 §4)

Proves that the ActionGate authorization and the ACP operational-safety
evaluation refer to the **same exact Kubernetes action** — without merging the two
decision schemas. Code:
`robotics_reliability_bench/acp_k8s_integrated/identity_binding.py`.

## Single source of truth

`KubernetesOperation` carries every fact about one proposed Deployment operation:
cluster, namespace, deployment, verb (SCALE/ROLLOUT/DELETE), current/desired
replicas, resourceVersion, generation, and the operational-state fields ACP needs
(availableReplicas, readiness plasticity, cooldown age, dependency health, freeze,
rollback ref). From this **one** object we build both:

- the ActionGate envelope (`actiongate_runner.run_actiongate`) → real
  `action_hash`, `manifest_digest`, `current_state_hash`;
- the ACP `CloudWorldState` + `CloudActionCandidate` → `candidate.identity`,
  `world.version`.

## The cross-layer anchor: `(manifest_digest, current_state_hash)`

Both values are computed with the **real ActionGate conventions**, so ACP can
reproduce ActionGate's exact bytes:

- `manifest_digest = domain_digest("SIMULATION", canonical_manifest_json)`
  (`action_gateway_k8s/mapping.py:121`) — the patch digest. Carried on both the
  ActionGate envelope arguments and the `CloudActionCandidate`.
- `current_state_hash = "sha256:" + domain_digest("ACTION",
  "{ns}/Deployment/{name}@{resourceVersion}")`
  (`action_gateway_k8s/server.py:75-85`, `K8sStateOracle`). ACP recomputes it from
  its own `world.resource_version`; it must equal ActionGate's or the two are not
  the same operation.

## Shared identifiers (not a schema merge)

Each layer keeps its own decision identity (`action_hash` vs
`candidate.identity` — deliberately different). The composition **links** them via:

- `shared_operation_digest` — over `{cluster, namespace, deployment, kind, verb,
  manifest_digest, current_replicas, desired_replicas}`;
- `shared_state_version` — over `{cluster, namespace, deployment,
  resourceVersion, generation}`;
- `CompositionIdentity(action_hash, candidate_identity, operation_digest,
  state_version)` and its own `.identity` digest.

## `bind()` — the fail-closed check

`bind(op, ag, candidate, world)` independently re-derives the shared facts from
**each layer's own artifacts** and returns a `CompositionIdentity` only if all of
these agree; otherwise `(None, reason)`:

| check | fails with |
|---|---|
| namespace across op / AG / candidate / world | `NAMESPACE_MISMATCH` |
| target name == deployment across all | `TARGET_MISMATCH` |
| AG operation == expected; candidate CloudOperation == expected | `OPERATION_MISMATCH` |
| `ag.manifest_digest == candidate.manifest_digest` | `MANIFEST_DIGEST_MISMATCH` |
| ACP-recomputed `current_state_hash == ag.current_state_hash` | `RESOURCE_VERSION_MISMATCH` |
| candidate current→desired == op transition | `TRANSITION_MISMATCH` |

Any mismatch → the composition class is `COMPOSITION_IDENTITY_MISMATCH` and the
operation is not eligible (proven by the `composition_identity_mismatch` corpus
scenario, which injects a divergent ACP patch digest).

## Why this matters

The whole value of a two-layer stack collapses if the layers silently evaluate
*different* actions (e.g. ActionGate authorizes patch A while ACP judges patch B
safe). The binding makes that impossible to miss: the layers either provably agree
on target + operation + patch + resourceVersion + transition, or the composed
result is `COMPOSITION_IDENTITY_MISMATCH` and fails closed.
