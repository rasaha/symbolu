# PCAM Phase 1 — Public API

**Status:** Phase 1 complete
**Scope:** consumable software surface only — no runtime integration, no benchmarks
**Contract:** [`docs/design/ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Update ritual (vendored reference):** [`VENDORED_REFERENCE_UPDATE_RITUAL.md`](VENDORED_REFERENCE_UPDATE_RITUAL.md)

---

## What Phase 1 ships

A small, stable, importable Python surface for the PCAM KV-cache policy:

```python
from simulator.pcam import (
    KVCachePolicy,      # the runtime policy
    FrequencySketch,    # 4-row 4-bit Count-Min sketch (ported)
    InferencePhase,     # PREFILL / DECODE
    PositionClass,      # SINK / RECENT / ENTITY / FILLER
    PCAMConfig,         # config object for KVCachePolicy
    TierHint,           # HOT / WARM / COLD / EVICT placement hint
    PolicyMetrics,      # tiny snapshot/delta wrapper around get_stats
)
```

That's the entire Phase 1 surface. Anything not in this list is either
internal, deferred to a later phase, or part of the pre-existing
simulator framework.

## Source-of-truth contract (unchanged from ADR-0001)

- **Specification reference:** the vendored copy at
  `simulator/pcam/reference/attention_evictor_vendored.py`. Read-only;
  edited only via the update ritual.
- **Runtime policy:** `simulator/pcam/kv_policy.py::KVCachePolicy`. This
  is the one and only runtime scoring/eviction implementation.
- **Conformance mechanism:** the parity harness at
  `simulator/pcam/tests/test_sketch_conformance.py` and
  `simulator/pcam/tests/test_attention_evictor_parity.py`. The
  harness imports the vendored reference directly and asserts
  bit-parity against the runtime policy on a fixed RNG seed.

There is **no bridge class** between the reference and the runtime
policy. The two are kept in sync by the harness, not by a runtime
adapter. Adding a bridge would reintroduce the drift risk the ADR
exists to prevent.

## Quick start

```python
from simulator.pcam import PCAMConfig, InferencePhase, TierHint

# 1. Build a policy from a config object
cfg = PCAMConfig(max_blocks=4096, sink_tokens=4)
policy = cfg.build_policy()

# 2. Drive the policy from a runtime
policy.register_sequence(seq_id=1)
policy.set_phase(seq_id=1, phase=InferencePhase.DECODE)
policy.ensure_block(block_id=0, sequence_id=1, positions=[0, 1, 2, 3])
policy.on_block_attention(block_id=0, attention_sum=0.42, sequence_id=1)

# 3. Ask for tier-placement hints
hint = policy.classify_tier(block_id=0)
assert hint is TierHint.HOT  # sink blocks always clamp to HOT

batch = policy.tier_hints([0, 1, 9999])
# {0: HOT, 1: ..., 9999: EVICT}

# 4. Ask for victims
victims = policy.select_victims(count=4)
```

## `PCAMConfig`

Frozen dataclass mirroring the `KVCachePolicy` constructor exactly.
Three factories:

- `PCAMConfig.from_dict(d)` — builds from a plain dict; rejects unknown
  keys with `TypeError` (typos fail loudly).
- `PCAMConfig.from_env(prefix="PCAM_")` — reads
  `PCAM_MAX_BLOCKS`, `PCAM_SINK_TOKENS`, etc., from the environment.
- `PCAMConfig.from_yaml(path)` — soft dependency on PyYAML; raises
  `RuntimeError` with an install hint if PyYAML is not importable.

Plus:

- `cfg.to_dict()` — round-trips with `from_dict`.
- `cfg.build_policy()` — convenience constructor for `KVCachePolicy`.

The defaults match the canonical reference and must not drift from
the runtime policy without an ADR amendment.

## `TierHint` and the tier-hint API

```python
class TierHint(Enum):
    HOT   = "HOT"    # score >= 0.7  → keep in HBM
    WARM  = "WARM"   # 0.3 <= score < 0.7 → OK in DRAM
    COLD  = "COLD"   # 0.0 <  score < 0.3 → can demote to slower tier
    EVICT = "EVICT"  # score <= 0.0       → unknown / safe to drop
```

Two methods on `KVCachePolicy`:

- `classify_tier(block_id) -> TierHint` — single-block classification.
- `tier_hints(block_ids) -> dict[int, TierHint]` — batched.

**Sink clamp.** A block whose `is_sink` is true (positions <
`sink_tokens` at admission) classifies as `HOT` regardless of its
score, because `select_victims` will never evict it and a memory
controller consuming these hints must not demote it. This is the
*only* clamp; raw `score_block` otherwise drives the classification.

**No second scoring system.** `classify_tier` calls `score_block`
directly. The four-signal phase-aware formula in ADR-0001 is the only
scoring function in PCAM. Tier classification is observational only —
it does not influence eviction.

**Thresholds are introspectable** as class-level constants
(`KVCachePolicy.TIER_HOT_THRESHOLD`, `KVCachePolicy.TIER_WARM_THRESHOLD`)
so downstream consumers can align their own placement logic without
re-implementing the cutpoints.

## `PolicyMetrics`

Dependency-free observability wrapper around `policy.get_stats()`:

- `PolicyMetrics(policy).snapshot() -> dict` — returns a fresh shallow
  copy of the current stats.
- `PolicyMetrics(policy).delta(prev) -> dict` — computes per-key
  numeric deltas vs a previous snapshot. Non-numeric or absent keys
  are silently dropped.

No Prometheus, no OpenTelemetry, no exporter. Callers convert to
whatever format they need. If you find yourself wanting an exporter
*here*, build it on top instead — that's a Phase 2+ concern.

## What Phase 1 explicitly does NOT add

- No `score_for_demotion` — `score_block` is the only scorer.
- No `score_blocks` batch API — add only if profiling justifies it.
- No `export_sequence_state` — versioning trap; no concrete use case.
- No bridge class between CTM+ and PCAM.
- No runtime backend adapters (vLLM, SGLang, TGI, DeepSpeed) — Phase 2.
- No benchmark harness — Phase 3.
- No new RTL — the existing RTL from earlier phases is unchanged.
- No changes to ADR-0001 substance — only the operational note from
  Phase 0 is present.

## Naming note: `PCAMConfig` vs `PCAMSimulatorConfig`

`PCAMConfig` was previously the package-root export name for the
*simulator framework* config (`simulator/pcam/core/config.py`). Phase 1
re-points the package-root name `PCAMConfig` at the *KV-cache policy*
config so that the public API matches the documented Phase 1 surface.

The simulator framework config is unchanged in `core/config.py` — only
its package-root export name changed. It is now exported as
`PCAMSimulatorConfig`. Two benchmark files
(`benchmarks/pcam_vllm_harness.py`, `benchmarks/pcam_flops_to_roi.py`)
were updated to use the explicit name. Internal simulator imports
(`from simulator.pcam.core.config import PCAMConfig`) are unaffected
and continue to work.

## What's next (Phase 2 preview)

Phase 2 will add:

- vLLM runtime adapter at `simulator/pcam/integrations/vllm.py`
- attention-trace ingestion utility (`pcam.trace.Replay` or similar)
- victim-selection callback path tied to vLLM's `BlockSpaceManager`

It will *not* expand the public Phase 1 surface. Anything new in
Phase 2 belongs under a clearly-namespaced submodule.
