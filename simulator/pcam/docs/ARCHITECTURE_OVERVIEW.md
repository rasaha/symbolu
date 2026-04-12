# PCAM Architecture Overview — CTM+ / PCAM Relationship

**Purpose:** Single source of truth for how CTM+ and PCAM relate on this branch. Every other PCAM doc, pitch deck, and acquisition artifact should align to this page. If any of them disagree, this page is authoritative.

**Scope:** This document describes what is *actually implemented* on the current branch. It does not describe aspirational extensions (global system orchestration, multi-runtime controllers, learned policies, etc.). Those belong in roadmap documents, not here.

**Audience:** engineers, technical diligence reviewers, partner / corp-dev audiences.

---

## Canonical relationship (one paragraph)

**CTM+ is the canonical KV-cache policy specification. PCAM is the runtime backend that implements it bit-for-bit, exposes it through a small Python API, and plugs into inference runtimes through narrow adapters. The two are kept in sync by a parity harness.**

That sentence is the claim every other PCAM document is allowed to make. Any stronger claim (e.g. "CTM+ is a multi-runtime memory orchestrator" or "PCAM is a full vLLM replacement") overclaims what is currently in the branch and should not be used in external communication without first promoting the underlying code.

## Architecture diagram

```
             Inference Runtime / Host
              (vLLM, HuggingFace, future)
                       │
                       ▼
      ┌─────────────────────────────────────┐
      │               CTM+                  │
      │    (canonical policy spec)          │
      │                                     │
      │   Phase-aware scoring (4 base +      │
      │     3 optional FSCS-derived)       │
      │     Base: recency, frequency,       │
      │       attention, position           │
      │     Opt: boundary, band class,      │
      │       instability (default-off)     │
      │   Count-Min frequency sketch        │
      │     (4 rows × 4-bit counters,       │
      │      fixed seed hashes,             │
      │      event-driven halving)          │
      │   Sink / entity / filler            │
      │     classification                  │
      │   Sequence lifecycle semantics      │
      │     (register / set_phase /         │
      │      complete)                      │
      │                                     │
      │   Vendored into PCAM at pinned      │
      │   commit; parity harness keeps      │
      │   the runtime in sync.              │
      └──────────────┬──────────────────────┘
                     │
      spec lives     │    runtime matches
      upstream       │    via vendoring +
                     │    parity harness
                     ▼
      ┌─────────────────────────────────────┐
      │         PCAM software layer         │
      │          (runtime backend)          │
      │                                     │
      │   KVCachePolicy                     │
      │     score_block / select_victims    │
      │     sink pinning                    │
      │     filler fast path                │
      │   Tier hints                        │
      │     classify_tier / tier_hints      │
      │     HOT / WARM / COLD / EVICT       │
      │   PCAMEvictor                       │
      │     duck-typed vLLM Evictor surface │
      │   Trace replay                      │
      │     simulator.pcam.trace.replay     │
      │   Benchmark / demo layers           │
      │     pcam_trace_replay               │
      │     pcam_compare_baselines          │
      │     pcam_vllm_demo                  │
      │     pcam_vllm_perf                  │
      └──────────────┬──────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
     shadow mode          active mode
    (observational)     (causal eviction)
                     │
           verified live         implemented + unit-
           against real          tested; one live
           torch and real        GPU run still
           vLLM traces           pending for full
                                 closure
          │                     │
          └──────────┬──────────┘
                     ▼
      ┌─────────────────────────────────────┐
      │     KV cache / memory tiers /       │
      │        runtime backend              │
      │  (vLLM block pool, HBM/DDR, ...)    │
      └─────────────────────────────────────┘
```

## Clarifications (stated explicitly to prevent drift)

1. **CTM+ on this branch is the KV-cache scoring policy specification, nothing more.** The file at `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` is 506 lines of scoring logic, sketch math, classification helpers, and sequence lifecycle — all per-process, per-policy, per-sequence. It does **not** orchestrate multiple inference runtimes, does **not** make tier-placement decisions across HBM / DDR / NVMe on its own, and does **not** coordinate with a system-wide controller. Any doc or pitch that describes CTM+ as a "global orchestrator" or "system-level memory controller" is overclaiming what is in the branch today.

2. **PCAM is the consumable runtime backend.** It is the object a real inference runtime imports and calls. Every entry point (the Phase 1 public API, the Phase 2 `PCAMEvictor` adapter, the Phase 3 benchmark scripts, the Phase 4 vLLM bridge, the Phase 5 active-mode installer) routes through `simulator/pcam/kv_policy.py::KVCachePolicy`. There is exactly one scoring function, in exactly one file. No bridge class. No second policy implementation.

3. **Shadow mode is observational and already verified.** Phase 2 through Phase 4 ran real torch forward passes (HuggingFace `gpt2`-shape model, real attention tensors, real TraceEvent emission) and replayed the resulting traces through `KVCachePolicy`. The policy reported what it *would* have done on observed workloads; it did not change the runtime's own eviction. Shadow mode is the "proof of value via parallel deployment" story.

4. **Active mode is implemented and unit-tested, but one live GPU run is still pending.** Phase 5 added a monkey-patch against vLLM's v1 `FreeKVCacheBlockQueue.popleft_n` so PCAM's decisions drive live eviction — this turns the arrow from PCAM into the KV cache from observational into causal. The bridge is feature-detected against the vLLM v1 core surface, fails clean on unsupported releases, and has 23 unit tests green against a mock `FreeKVCacheBlockQueue`. What remains is one real `pcam_vllm_perf.py --policy both` run on a CUDA machine with vllm 0.7.0+ installed — the runbook for that closure lives at `benchmarks/PHASE4_CLOSURE_RUN_LOG.md` section D.

5. **FSCS-derived scoring signals are optional policy extensions, not transformer modifications.** Three signals from the Text-FSCS attention-operator research (boundary sensitivity, band class, instability) were integrated into PCAM's `score_block()` as caller-supplied metadata. PCAM does NOT import any FSCS module, does NOT run transformer attention code, and does NOT compute these signals internally. The inference runtime or trace capture tool sets them via `ensure_block(boundary_score=, band_class=, instability_hint=)` or `set_block_*()` methods. When no signals are set, scoring is unchanged from the four-signal ADR-0001 model. Validated on a real Mistral-7B annotated trace: 100% of eviction rounds changed with signals active (1,108 different block choices across 4 rounds). 276 total tests pass, 36 of which cover the new signals. The signals are in `kv_policy.py` alongside the existing scoring code; no separate module, no separate config file, no new dependency.

6. **The parity harness is the only synchronization mechanism.** There is no bridge class between CTM+ and PCAM. ADR-0001 explicitly forbids one. When CTM+ changes upstream, the update ritual is: re-vendor the reference file, re-run the parity harness, fix any runtime divergence against the reference (never the other way around), bump the PCAM version, commit. This is why it is correct to say "CTM+ is the spec" and "PCAM is the runtime": the code path from spec to runtime goes through vendoring plus a 20-test bit-parity check, not through an adapter layer.

## Source-of-truth pointers

| Artifact | What it is | Location |
|---|---|---|
| ADR-0001 | The contract that declares CTM+ the spec and forbids a bridge | [`docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md`](../../../docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md) |
| Upstream reference | The CTM+ source file (the spec itself) | `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` |
| Vendored reference | Pinned in-tree copy of the spec, with commit-hash header | [`../reference/attention_evictor_vendored.py`](../reference/attention_evictor_vendored.py) |
| Update ritual | Six-step procedure for bumping the vendored reference | [`VENDORED_REFERENCE_UPDATE_RITUAL.md`](VENDORED_REFERENCE_UPDATE_RITUAL.md) |
| Runtime policy | The PCAM implementation (bit-parity port of the vendored reference) | [`../kv_policy.py`](../kv_policy.py) |
| Parity harness | 20 tests asserting runtime ↔ reference equivalence on a fixed seed | [`../tests/test_sketch_conformance.py`](../tests/test_sketch_conformance.py), [`../tests/test_attention_evictor_parity.py`](../tests/test_attention_evictor_parity.py) |
| Phase 1 public API | `KVCachePolicy`, `PCAMConfig`, `TierHint`, `PolicyMetrics` | [`PHASE1_PUBLIC_API.md`](PHASE1_PUBLIC_API.md) |
| Phase 2 runtime integration | `PCAMEvictor`, trace replay | [`PHASE2_RUNTIME_INTEGRATION.md`](PHASE2_RUNTIME_INTEGRATION.md) |
| Phase 3 benchmarks | Replay scripts, baseline comparison | [`PHASE3_BENCHMARKS.md`](PHASE3_BENCHMARKS.md) |
| Phase 4 real-runtime (shadow) | vLLM bridge, HuggingFace trace extractor | [`PHASE4_REAL_RUNTIME.md`](PHASE4_REAL_RUNTIME.md) |
| Phase 5 active mode | Monkey-patch installer, perf harness | [`PHASE5_ACTIVE_MODE.md`](PHASE5_ACTIVE_MODE.md) |
| Phase 5 benchmark report | Acquisition-facing summary with the active-mode status | [`../../../benchmarks/PCAM_PHASE5_REPORT.md`](../../../benchmarks/PCAM_PHASE5_REPORT.md) |
| Closure run log | Live-run runbooks + dated attempts for Phase 2.5 / 4 / 5 closures | [`../../../benchmarks/PHASE4_CLOSURE_RUN_LOG.md`](../../../benchmarks/PHASE4_CLOSURE_RUN_LOG.md) |
| FSCS signal tests (Stage 1-3) | 36 tests covering boundary, band class, instability signals | [`../tests/test_boundary_signal.py`](../tests/test_boundary_signal.py), [`../tests/test_band_class_signal.py`](../tests/test_band_class_signal.py), [`../tests/test_instability_signal.py`](../tests/test_instability_signal.py) |
| Annotated trace capture | Captures FSCS-derived signals from Mistral-7B into a replayable trace | [`../../../benchmarks/pcam_fscs_trace_capture.py`](../../../benchmarks/pcam_fscs_trace_capture.py) |
| Baseline vs enhanced replay | Compares eviction decisions with signals on vs off | [`../../../benchmarks/pcam_fscs_replay_compare.py`](../../../benchmarks/pcam_fscs_replay_compare.py) |

## What this document does not say

Kept in a separate section so nothing in the diagram or the claims above can be misread as asserting any of the following:

- **Not** claimed: CTM+ orchestrates multiple inference runtimes.
- **Not** claimed: PCAM has fully replaced vLLM's default eviction in a measured live production workload. (Shadow mode is verified; active mode's GPU closure is still pending.)
- **Not** claimed: PCAM supports every vLLM release. (The Phase 5 bridge targets vLLM ≥ 0.7.0's v1 core and fails clean on older or refactored releases.)
- **Not** claimed: PCAM has published throughput wins over LRU under load. (Shadow-mode policy-decision metrics are verified; real serving-tier throughput measurement is pending Phase 5 closure.)
- **Not** claimed: the attention signal in Phase 4's HuggingFace extractor closure was semantically meaningful. (It was structurally correct but the weights were random because HF Hub was sandbox-blocked during the closure; a follow-up run against real pretrained `gpt2` is documented in the closure runbook.)

Any future doc or pitch that wants to make a stronger claim than the diagram and the source-of-truth pointers above must first cite the code path and the test that proves it. If such a code path does not yet exist, the right response is to build it — not to edit this page.
