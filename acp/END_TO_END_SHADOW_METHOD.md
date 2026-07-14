# End-to-End Shadow Method (V2.2 §7, §9)

How the integrated AI Control Plane benchmark runs and measures. Code:
`robotics_reliability_bench/acp_control_plane/{end_to_end_harness,run_control_plane_bench}.py`.
Results: `robotics_reliability_bench/results/acp_control_plane_results.json`.

## What is real

- **Context Minimization** — the real `actiongate_context_ablation.compressor.compress`,
  unchanged (pure, deterministic, offline; its fail-closed guard calls the real
  ActionGate to preserve the authorization decision).
- **ActionGate** — the real `action_gate_ref.gate.evaluate` + real K8s policy
  (V2.1 runner). Real envelope/policy/evidence/approvals/action-hash.
- **ACP** — the frozen ACP core + real `cloud_controller` (V2 adapter, V2.1
  integration).

## What is a deterministic stand-in (honestly labelled)

- **The LLM stage** is the repository's existing **deterministic offline reader**
  (`MockReader` mechanism): it reads the proposed action only from the spans that
  survived compression. Reason (frozen in the preregistration): no API key/model
  is available, AND a live sampling call is **non-deterministic**, which would
  violate the required end-to-end deterministic replay. This is a stand-in for the
  model, not a claim of model behaviour.
- **Deployment state** is authored on the real `action_gateway_k8s` fixture (no
  live cluster offline — inherited V2.1 limitation).

## Flow (per scenario, deterministic)

```
build_enterprise_context(op)                 # spans: critical + filler/history/redundant/stale/logs
  -> run_minimization(ctx, target_reduction) # REAL compress; report preservation
  -> context_digest(reduced spans)
  -> DeterministicReader.read(reduced)        # proposed KubernetesOperation | INSUFFICIENT_CONTEXT
  -> IntegratedShadowHarness.evaluate(op)      # REAL ActionGate + REAL ACP + composition (V2.1)
  -> verify_chain(context -> action -> candidate) # full-chain identity, fail-closed
  -> ControlPlaneRecord                         # bounded sink
```

Fixed clocks throughout (compressor `EVAL_NOW`; ActionGate `NOW`; ACP `now_s=0`),
so every run is byte-reproducible.

## The headline measure: downstream invariance under compression

Each scenario is run **twice** — at its compression budget and at 0 % (full
context) — and the downstream signature (proposed action, ActionGate outcome, ACP
recommendation, composition class, action hash, candidate identity) is compared.
Equality proves the compressed context dropped **nothing** either layer needed
(§10 I1/I2). Measured: **100 %**.

## Measures (§9)

**Context:** avg/min/max compression ratio; protected-span, ActionGate-span, and
ACP-span preservation rates; decision-invariant rate; deterministic replay.
**ActionGate:** outcome distribution; action-hash determinism; policy-replay + stale
detection (from commit revalidation). **ACP:** recommendation distribution;
operational holds; evidence coverage; deterministic replay. **Integrated:**
end-to-end class distribution; execution-eligibility distribution; downstream-
invariant-under-compression rate; identity consistency; duplicated-logic count (0);
ownership violations (0); shadow behaviour changes (0); composed latency
mean/p95/max. Determinism: the whole corpus is run twice and the downstream
signatures compared bit-for-bit.

## Commit-time revalidation (carried from V2.1)

Dedicated probes: a policy-version change → ActionGate rejects (I6); a
resourceVersion change → ACP rejects (I7); a manifest/patch mutation → both reject
(I8). Recorded per layer.

## Zero-impact guarantees (verified)

No Kubernetes API call (no client imported — asserted); no ActionGate token minted
or consumed; no cluster mutated (`cluster_mutated` always `False`); no authoritative
path changed (`authoritative_behavior_change_count = 0`); every record
`shadow_only`; exceptions contained → `SHADOW_ERROR`.

## Rollback & kill-switch

- **Kill switch:** `ControlPlaneHarness(enabled=False)` (default) — no work,
  returns `None`.
- **Rollback:** delete `robotics_reliability_bench/acp_control_plane/`; nothing in
  production imports it; Context Minimization, ActionGate, the frozen ACP core, the
  V2 cloud adapter, and the V2.1 integration are all untouched (only imported).
