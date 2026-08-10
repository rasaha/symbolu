# PCAM Phase 2 — Runtime Integration

**Status:** Phase 2 complete
**Scope:** vLLM adapter + offline trace replay
**Contract:** [`docs/design/ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Phase 1 reference:** [`PHASE1_PUBLIC_API.md`](PHASE1_PUBLIC_API.md)

---

## What Phase 2 ships

Two new modules. Nothing else.

### 1. vLLM integration adapter

```python
from simulator.pcam.integrations.vllm import PCAMEvictor, make_pcam_evictor
from simulator.pcam import PCAMConfig, InferencePhase

evictor = make_pcam_evictor(PCAMConfig(max_blocks=4096, sink_tokens=4))
evictor.register_sequence(seq_id=1, phase=InferencePhase.DECODE)
evictor.admit_block(block_id=10, sequence_id=1, positions=[100], vllm_block=my_block)
evictor.on_attention(block_id=10, attention_sum=0.42, sequence_id=1)
victims = evictor.select_victims(count=4)
hints = evictor.tier_hints([10, 11, 12])
```

### 2. Offline trace replay utility

```python
from simulator.pcam import PCAMConfig
from simulator.pcam.trace import EventKind, TraceEvent, replay

events = [
    TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": 1}),
    TraceEvent(EventKind.SET_PHASE, {"seq_id": 1, "phase": "DECODE"}),
    TraceEvent(EventKind.ENSURE_BLOCK,
               {"block_id": 10, "sequence_id": 1, "positions": [100]}),
    TraceEvent(EventKind.ON_BLOCK_ATTENTION,
               {"block_id": 10, "attention_sum": 0.5, "sequence_id": 1}),
    TraceEvent(EventKind.SELECT_VICTIMS, {"count": 1}),
]
policy = PCAMConfig(max_blocks=64).build_policy()
result = replay(policy, events)
print(result.victim_lists)
print(result.final_stats)
```

That's it. No new package-root exports, no new config classes, no new
runtime adapters beyond vLLM.

## Architectural rules (unchanged from Phases 0 and 1)

1. **No bridge class.** The vendored reference is the specification,
   `simulator/pcam/kv_policy.py::KVCachePolicy` is the runtime, the
   conformance harness is the only sync mechanism.
2. **No second policy implementation.** `PCAMEvictor` and `replay`
   both delegate to `KVCachePolicy`. There is exactly one scoring
   function in PCAM, in exactly one file.
3. **No package-root API expansion.** `PCAMEvictor`, `make_pcam_evictor`,
   `EventKind`, `TraceEvent`, `ReplayResult`, and `replay` are reachable
   only via `simulator.pcam.integrations.vllm` and `simulator.pcam.trace`.
   Import paths for the Phase 1 surface (`KVCachePolicy`, `PCAMConfig`,
   `TierHint`, `PolicyMetrics`, etc.) are unchanged.
4. **No hard runtime dependency on vLLM.** The integration module
   imports nothing from `vllm` and is fully usable in environments
   where `vllm` is not installed. See "vLLM coupling story" below.

## vLLM coupling story

`PCAMEvictor` is a duck-typed adapter. It exposes the shape vLLM's
`Evictor` ABC expects (`__contains__`, `__len__`, `num_blocks`, plus
admission, attention, and eviction methods) without subclassing the
ABC, importing the `vllm` package, or taking any runtime dependency on
vLLM internals.

To plug PCAM into a real vLLM serving stack, the consumer writes a
small bridge class that subclasses `vllm.core.evictor.Evictor` and
forwards each abstract method to the corresponding `PCAMEvictor`
method. That bridge is roughly 20 lines and belongs in the consumer's
code, not in the PCAM package, because **PCAM does not depend on
vLLM**. A reference shape lives in the docstring of
`simulator/pcam/integrations/vllm.py` and can be lifted verbatim.

Why this design?

- **Release-safety.** PCAM ships as a small Python package with no
  vLLM dependency in `requirements.txt` or `pyproject.toml`. CI runs
  every test, including the integration tests, in environments
  without vLLM installed.
- **Test simplicity.** The Phase 2 tests instantiate `PCAMEvictor`
  directly and exercise every surface — including the vLLM-shaped
  duck-type methods — using bare Python.
- **No version coupling.** vLLM's `Evictor` ABC has changed shape
  between releases. A duck-typed adapter is immune to those changes
  as long as the consumer's bridge keeps up; a hard subclass would
  not be.

## Trace event schema

Seven event kinds, each mirroring a `KVCachePolicy` method:

| `EventKind` | `args` keys | Wraps |
|---|---|---|
| `register_sequence` | `seq_id` | `register_sequence(seq_id)` |
| `set_phase` | `seq_id`, `phase` (str or `InferencePhase`) | `set_phase(seq_id, phase)` |
| `ensure_block` | `block_id`, `sequence_id`, `positions` | `ensure_block(...)` |
| `on_block_attention` | `block_id`, `attention_sum`, `sequence_id` | `on_block_attention(...)` |
| `select_victims` | `count` | `select_victims(count)` |
| `complete_sequence` | `seq_id` | `complete_sequence(seq_id)` |
| `tier_hints` | `block_ids` | `tier_hints(block_ids)` |

`TraceEvent.from_dict` and `TraceEvent.to_dict` provide JSON-friendly
round-trips, so a trace can be loaded from a `.json` file with
`json.load(f)` and a list comprehension. No custom serializer is
required.

`replay(policy, events)` returns a `ReplayResult` with four captured
output streams (`victim_lists`, `tier_hint_results`,
`completed_sequences`, `final_stats`) plus an `event_count` for
sanity checking. Unknown phase strings and unknown event kinds raise
loudly so malformed traces fail fast.

## What Phase 2 explicitly does NOT add

- **No SGLang / TGI / DeepSpeed adapters.** Build them only when a
  real design partner asks. Phase 2 non-goal.
- **No benchmark suite.** That belongs to Phase 3. The trace replay
  primitive is the foundation a benchmark suite will sit on, but the
  benchmark itself is out of scope.
- **No vLLM hard dependency.** See "vLLM coupling story" above.
- **No new package-root exports.** Phase 1 surface is preserved
  exactly.
- **No new policy methods on `KVCachePolicy`.** Phase 2 only consumes
  the existing surface; it does not add to it.
- **No CTMPlusPCAMBridge.** Forbidden by ADR-0001.

## What's next

- **Phase 2.5 — RTL parity via cosimulation.** Highest-leverage
  acquisition-readiness item. Adds a cocotb-driven harness that
  replays a deterministic trace through both `freq_sketch.sv` and
  `simulator.pcam.kv_policy.FrequencySketch` and asserts bit-identical
  outputs. Independent workstream from runtime integration.
- **Phase 3 — measurement.** Build a `pcam_vllm_demo.py` and a
  `pcam_compare_baselines.py` on top of `simulator.pcam.trace.replay`.
  Publish a quality-vs-baseline benchmark report. Targets Llama-70B,
  LongBench, PassKey, needle-in-a-haystack.
