# Limitations & evidence status

## Maturity

`IMPLEMENTED_AND_CI_VERIFIED`. **Not** pilot-validated, **not** production-certified. No
live-provider validation is performed by this package.

## Evidence tiers

| Concern | Status | Evidence |
|---|---|---|
| Implemented | ✅ | `src/ugence_model_selection/` — gate, policy, authority, registry, states, reason codes, fingerprint. |
| Unit-tested | ✅ | 72 tests: eligibility aggregation, the authority contract, the capability floor and its boundary, determinism, packaging and import boundaries. |
| Deterministic | ✅ | `tests/test_determinism.py` — repeated evaluation yields identical records and fingerprints; condition order is pinned; registry insertion order does not change ranking; staleness is measured against the supplied `now`. |
| Leaf-boundary enforced | ✅ | `tests/packaging/test_boundaries.py` — every module's imports scanned, plus an isolated-subprocess probe for indirect reach, plus a no-system-clock scan. |
| Public API pinned | ✅ | `artifacts/public_api.json` (33 names) compared on every run. |
| Non-compensatory eligibility | ✅ | Enforced structurally; the floor is unrescuable at a quality weight of 10,000. |
| **Model-quality claims** | ❌ **none made** | The capability prior is a caller-supplied number. This package neither computes, validates nor benchmarks it. |
| **Provider-reliability claims** | ❌ **none made** | `reliability_floor` compares a supplied signal to a configured threshold; no real reliability is established. |
| Live-provider validated | ❌ | Not performed. |
| Pilot-validated | ❌ | Not performed. |
| Production-certified | ❌ | Not performed. |

## What the demonstrated evidence is

**Primarily synthetic.** The suites exercise deterministic policy behaviour over
constructed candidates and signals. They prove the mechanism — that eligibility precedes
ranking, that failures are non-compensatory, that decisions replay — and prove nothing
about which model is actually better for any task.

## Specific limitations

- **The floor is only as good as its input.** A `quality` signal with generous
  `PROVIDER_DECLARED` evidence and a long TTL will pass a floor it should not. The
  capability enforces the comparison, not the honesty of the number.
- **No cross-request state.** Each evaluation is independent. There is no rate-limit
  memory, no circuit breaker, no cooldown, no learning from `last_failure_reason`; the
  registry stores those fields but the gate does not read them.
- **`normalize_raw` is a heuristic.** Raw provider strings are matched by substring. An
  unrecognized string becomes `POLICY_STATE_UNKNOWN`, which is fail-closed and therefore
  safe, but it is not a parser and it is not exhaustive.
- **Cost is a projection.** `projected_cost_within_limit` multiplies declared per-token
  prices by requested and estimated token counts. It is not a quote, not a bill, and does
  not account for caching, batching or discounts.
- **`ExecutableRegistry` is in-memory.** No persistence, no concurrency control, no live
  catalog refresh.
- **The `execution_gate` root namespace is a compatibility surface**, logic-free and
  identity-preserving. Its `harness`, `baselines`, `scenarios` and `frozen/replay_v1` tree
  are a research/evaluation harness, not part of this distribution's evidence.
- **Deprecated aliases are retained**: `ModelSelector` → `ModelAuthority`,
  `ModelSelectionService` → `ModelAuthorityService`, `ModelAuthorizationPolicy` →
  `PolicyWeights`. They are the same objects, asserted by identity in the public-API
  tests. Prefer the Authority names.
