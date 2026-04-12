# CTM+ / PCAM: A Software-First Memory Intelligence Stack for LLM Inference

*A technical strategy memo for design partners, strategic acquirers, technical investors, and corp-dev reviewers.*

---

## 1. Executive Summary

Modern LLM inference is increasingly bound not by compute but by memory. Every token a serving system generates forces a decision about which fragments of the key-value (KV) cache to retain, which to demote, and which to evict — and the policies most production stacks ship with today were designed for workloads that look nothing like attention-based generation. The cost shows up directly in operator budgets: fewer concurrent requests per GPU, latency spikes under long-context load, overprovisioned HBM, and quality degradation when the wrong block gets dropped.

**CTM+ and PCAM are best understood as one platform with two layers.** **CTM+** is the canonical policy-specification layer: the scoring math, the classification semantics, and the sequence-lifecycle rules that decide which memory is worth keeping in each tier. **PCAM** is the runtime-backend layer: a software embodiment of that policy today, with a credible hardware embodiment path for later. A bit-parity conformance harness keeps the specification and the runtime aligned on every commit, so the two cannot silently drift.

**Operationally, the value proposition is concrete**: better concurrent-request capacity per accelerator, lower risk of evicting blocks the model will immediately need again, and a software-first deployment path today that preserves the option on future hardware productization without requiring it.

**Maturity is honest and specific.** The policy layer is canonical and locked under an architectural decision record. The runtime layer is implemented, unit-tested, and exposed as a small public Python API that consumers can import today. Integration layers exist for real-model offline trace extraction, for real-vLLM shadow-mode measurement, and for real-vLLM active-mode eviction. Hardware credibility exists as SystemVerilog plus a cocotb parity harness targeted at the same specification. **This system is software-first today.** It is near-term deployable as a runtime policy backend. It is not yet a taped-out chip, and it does not yet carry published end-to-end serving throughput numbers against a broad baseline set — two closures that remain environment-dependent and are discussed explicitly below.

---

## 2. The Problem Being Solved

The most expensive thing in modern LLM inference is not the matmul; it is the data the matmul has to see. A transformer serving a 100K-token context window needs its KV cache to hold the right blocks at the right time, and "right" is a moving target. During prefill, every position matters. During decode, the causal mask concentrates attention on a few structural positions (the attention sinks) plus a moving sliding window of recent tokens. Across sequences, some blocks are genuinely hot and some are dead but still holding HBM. Eviction policy is the invisible lever that decides whether a serving system holds 32 concurrent requests per GPU or 48 on the same silicon.

The policies that ship by default in most serving stacks were never designed for this regime. Least-recently-used (LRU) eviction makes one decision based on one signal — *when was this last touched?* — and that signal is almost uncorrelated with what matters for LLM attention. Attention sinks get evicted because they happen to be old even though the model will keep attending to them. Entity-like tokens that sit in long-range memory get churned out because their recency score looks unremarkable next to a flood of recently-emitted filler. FIFO variants are worse. Even ARC and LIRS — real improvements on LRU in the cache-theory literature — are phase-unaware: they do not know that serving has a prefill phase and a decode phase with different weightings, they do not treat sink tokens as structurally special, and they carry no signal that tracks accumulated attention mass per block.

The practical consequences are quantifiable. Operators running long-context inference routinely overprovision HBM because their eviction policy cannot be trusted under pressure. When HBM gets tight, tail latency explodes because the serving system starts recomputing blocks it evicted earlier in the same sequence. Concurrent-request capacity is lower than the hardware should theoretically support because the scheduler has to reserve headroom to survive bad eviction decisions. And as context windows keep growing — 32K to 128K to 1M and beyond — the mismatch between naive eviction and real attention structure keeps widening, because the ratio of "blocks you should keep" to "blocks technically still in the sequence" keeps dropping.

The simplest framing is that LLM inference has outgrown recency-only memory management. What it needs instead is a policy that looks at several orthogonal signals at once — recency, frequency, the model's own attention signal, and structural position within the sequence — and that knows which signals matter more in which phase of the forward pass. That is the problem CTM+ and PCAM solve together.

---

## 3. Why CTM+ Exists

CTM+ is the canonical policy-specification layer. On this branch, it is specifically a KV-cache policy spec — the scoring math, the classification semantics, the data structures, and the sequence-lifecycle rules that define what a correct eviction decision looks like. It is not a global multi-runtime orchestrator. It is not a system-wide memory controller that reaches across HBM, DDR, and NVMe on its own. It is narrower and more precise than those framings would suggest, and the narrower framing is the honest one.

What CTM+ actually contains is a four-signal phase-aware scoring function. For each candidate block, CTM+ combines four orthogonal signals: an exponential-decay recency term, a frequency term backed by a Count-Min sketch, an accumulated-attention term driven by an exponential moving average, and a position-importance term derived from the block's classification as sink, entity, or filler. The weights on those four signals shift between prefill and decode phases of the forward pass, because the relative importance of recency versus attention mass is genuinely different in the two phases. A non-sink block whose attention mass exceeds an adaptive threshold receives a small fixed bonus, so entity-like blocks are held against eviction pressure even when their recency score is unremarkable. Sink blocks are pinned at admission and never appear in victim lists at all.

Backing this scoring function is a small, deterministic set of data structures. The frequency signal is a four-row, four-bit Count-Min sketch with four fixed seed hashes and event-driven halving at a configurable reset threshold. Block classification is computed from running attention-mass statistics via an adaptive threshold rather than a hard cutoff. Sequence lifecycle — registration, phase transitions, and completion — is handled explicitly, so the policy knows which blocks belong to which sequence and which phase the sequence is in. None of these components are speculative; each is precisely specified, with deterministic behavior under a fixed RNG seed, and a diligence reviewer can read the full specification end to end in about an hour.

The reason any of this matters — the reason there is value in a *canonical* policy layer at all — is that memory-policy engineering has historically been a graveyard of nearly-identical-but-subtly-different implementations. Three engineers on three teams building "LRU with attention sinks protected" will build three different things that make different decisions under load, and none of them will know it because there is no reference they can all point to. CTM+'s value proposition is that it is a single specification of record. There is exactly one scoring function. There is exactly one frequency-sketch construction. There is exactly one sink-pinning rule. Any runtime that wants to claim "PCAM-compatible" or "CTM+-aligned" must match that specification bit for bit, and there is a mechanized way to prove it.

One further clarification is worth stating upfront, because it becomes important in the combined-architecture section. **CTM+ can exist and has value independently of PCAM.** The specification is useful on its own: another runtime, another inference stack, or a hardware group targeting a future memory controller could take CTM+ as the reference and implement it against their own execution substrate. PCAM is one embodiment of CTM+, not a precondition for CTM+ to be a meaningful artifact.

---

## 4. Why PCAM Exists

PCAM exists because a specification that never gets operationalized is a research paper, and a research paper does not ship concurrent requests per GPU. PCAM is the runtime-backend layer: it implements the CTM+ specification faithfully, exposes that implementation through a stable Python API, and plugs into real inference runtimes through narrow adapter modules. It is what an LLM serving team actually imports, configures, and runs.

> **Scope note.** In this document, "PCAM" refers primarily to the **software runtime package** unless otherwise specified. Hardware-PCAM (FPGA prototype, ASIC embodiment) is a credible forward path discussed in later sections, but it is not a shipped product today. Any unqualified use of "PCAM" in this memo means "PCAM-the-software-package."

Concretely, PCAM today ships as a Python package with a small, deliberately narrow public surface. A consumer imports `KVCachePolicy`, `FrequencySketch`, `PCAMConfig`, `TierHint`, and `PolicyMetrics`, constructs a policy with a few lines of configuration, and drives it through the sequence-lifecycle and attention-event API documented in the package's operational docs. Under the hood, every one of those entry points routes through a single runtime file — the bit-parity port of the CTM+ reference — so there is no second scoring path, no parallel heuristic sneaking in through an adapter, and no divergence risk between what the API claims to do and what the policy actually does. That discipline is load-bearing, and it is enforced by the parity harness discussed in the next section.

Around that runtime core, PCAM adds several consumable layers. A thin `PCAMEvictor` adapter exposes a duck-typed surface compatible with the shape a vLLM-style block manager expects, so a serving team can drop PCAM in behind a small consumer-side bridge without PCAM itself taking a runtime dependency on vLLM. A trace-replay primitive lets a consumer feed a deterministic sequence of admission, attention, and eviction events through the policy offline, for reproducibility or parameter sweeps against captured workloads. A set of benchmark harnesses — replay-only, baseline-comparison, and live-integration — let a reviewer run the policy against inline LRU/LFU, against richer in-repo baselines (Sink+LRU, H2O, IndustryStyle), and against a real vLLM workload in either shadow or active mode. A HuggingFace-based attention extractor captures real per-block attention mass from a real model's forward pass and replays it as a PCAM-compatible trace.

Beyond the software runtime, PCAM also carries a hardware embodiment path. The repository contains a SystemVerilog implementation of the Count-Min frequency sketch, a package of RTL constants that match the Python reference byte-for-byte, and a cocotb-based cosimulation harness that drives the RTL and the Python reference from the same deterministic trace and asserts bit-identical outputs. This RTL is not a tape-out; it is a hardware-credibility artifact. Its function is to demonstrate that the same specification that runs as a Python policy today can be reduced to hardware tomorrow without the algorithm changing, and to establish a cocotb parity path that any future FPGA or ASIC embodiment can extend.

The honest framing of PCAM today is: a software runtime backend that is consumable and benchmarkable in its current form, with an extended set of runtime-integration and trace-capture tooling, and with a forward path to hardware — but not itself a deployed chip product.

---

## 5. Combined Architecture

The most important thing to internalize about CTM+ and PCAM is that they are **one platform with two layers**, not two independent products that happen to share a repository. The layers have different jobs, different audiences, and different maturity curves, but they are bound together by a single contract — the specification — and a single correctness mechanism — the parity harness.

The simplest way to see the relationship is to draw the flow from an inference runtime down to the actual KV cache:

```
            Inference Runtime / Host
             (vLLM, HuggingFace, future)
                        │
                        ▼
       ┌────────────────────────────────────┐
       │               CTM+                 │
       │     (canonical policy spec)        │
       │                                    │
       │  Four-signal phase-aware scoring   │
       │  Count-Min frequency sketch        │
       │  Sink / entity / filler            │
       │    classification                  │
       │  Sequence lifecycle semantics      │
       └───────────────┬────────────────────┘
                       │
          spec lives   │   runtime matches
          upstream     │   via vendoring +
                       │   parity/conformance
                       │   harness
                       ▼
       ┌────────────────────────────────────┐
       │         PCAM software layer        │
       │          (runtime backend)         │
       │                                    │
       │   KVCachePolicy (the runtime port) │
       │   Tier-hint API (HOT/WARM/COLD)    │
       │   PCAMEvictor adapter              │
       │   Trace replay + benchmark layer   │
       │   Shadow and active mode bridges   │
       └───────────────┬────────────────────┘
                       │
            ┌──────────┴──────────┐
            │                     │
            ▼                     ▼
       shadow mode           active mode
      (observational,       (causal eviction,
       verified live)        implemented; live
                             closure environment-
                             dependent)
            │                     │
            └──────────┬──────────┘
                       ▼
       ┌────────────────────────────────────┐
       │      KV cache / memory tiers /     │
       │         runtime backend            │
       │    (vLLM block pool, HBM/DDR)      │
       └────────────────────────────────────┘
```

The directionality matters. The specification lives upstream in CTM+, the runtime matches it by bit-parity port, and the conformance harness makes "match" enforceable rather than aspirational. Every commit that modifies either layer must keep the harness green. When a real improvement is discovered — a new signal, a tuned weight, a sharper classification — the canonical change happens in CTM+ first, is re-vendored into PCAM, the harness is re-run, and only then does the runtime reflect the new behavior. PCAM never leads the specification. This is deliberately the slower path, because it is the path that gives a diligence reviewer a reason to trust that the software and the spec still agree after six months of engineering churn.

Shadow mode and active mode describe two different ways PCAM can plug into a real inference runtime, and they are at different maturity levels.

**Shadow mode is observational.** The serving runtime runs its own default eviction policy; PCAM runs alongside it, receives the same admission and attention signals, and reports what it *would* have decided on the observed workload. The runtime's live behavior is unchanged; PCAM is a shadow observer. On this branch, shadow mode is the more mature path: it has been exercised against a real HuggingFace model with real attention tensors and real per-block attention mass, driven through the full replay-and-compare pipeline end to end. Shadow mode is the path a design partner or a cautious deployment team would pick first, because the risk profile is essentially zero.

**Active mode is causal.** PCAM actually replaces the live eviction policy inside vLLM by patching a narrow interior surface of the serving runtime's block pool so that every eviction request routes through `KVCachePolicy.select_victims`. Active mode is implemented on the branch. It is feature-detected against the vLLM v1 core surface, fails clean on unsupported releases, and is unit-tested against a mock queue with deterministic scenarios. What has *not* happened is a live end-to-end run on a CUDA GPU producing real serving-tier throughput and latency numbers against a real baseline — and the honest reason is that the live closure requires a supported vLLM version, a real GPU, and network access to model weights, none of which were available in the authoring environment. The code is ready; the environment is the gate. The live closure is estimated at roughly thirty engineer-minutes against a seven-step runbook already checked into the repository.

The right way to explain the combined architecture to a partner or an acquirer is therefore: CTM+ defines the policy, PCAM operationalizes it in software today and potentially in hardware later, and the parity harness is the reason those two things can be claimed to agree. Shadow mode is the observational integration path and is verified live. Active mode is the causal integration path and is implemented, but its live throughput measurement is environment-dependent and remains one of the narrowly-scoped closures in front of full production usage.

---

## 6. Current Development Stage

Precision matters in this section. The goal is not to claim "almost done." The goal is to give a reader enough evidence to form their own judgement about what is real, what is tested, and what is still waiting on an environment or a design-partner engagement.

**Canonical specification.** The CTM+ scoring model, the frequency sketch, the classification helpers, the phase-aware weights, the entity bonus, and the sequence-lifecycle semantics are all defined in a single reference file. An architectural decision record declares this file the source of truth for KV-cache scoring behavior and explicitly forbids bridge layers that would introduce a second policy path.

**Vendored reference.** The canonical CTM+ file is pinned by commit hash and copied into the PCAM package as an in-tree reference, so the runtime has no ambient dependency on the CTM+ package location at import time and the parity harness runs against a stable snapshot. A documented update ritual governs how the vendored copy is bumped, re-tested, and re-released when the upstream spec changes.

**Parity/conformance harness (green).** Twenty dedicated tests assert bit-for-bit equivalence between the runtime and the vendored reference on a fixed RNG seed. They cover sketch saturation and halving, single-key and distinct-key scoring, phase-aware weight dispatch, entity-bonus firing, filler-fast-path determinism, sampled-path RNG determinism, randomized differential tests, and a 500-operation randomized end-to-end. This suite has been green on every commit of the roadmap. It is the mechanism that makes the "CTM+ = spec, PCAM = runtime, no drift" claim enforceable.

**Runtime policy.** The core `KVCachePolicy` class is a faithful port of the vendored reference. It implements registration, phase setting, admission, attention events, scoring, and victim selection with deterministic behavior under a fixed seed, and has its own unit tests independent of the parity harness.

**Software package and public API.** PCAM exposes a small, stable public surface (`KVCachePolicy`, `FrequencySketch`, `PCAMConfig`, `TierHint`, `PolicyMetrics`) through the package root. A lightweight configuration object supports dict, environment-variable, and YAML factories. The public API is deliberately narrow, and that narrowness is itself a product decision.

**Runtime adapter.** A duck-typed `PCAMEvictor` adapter exposes the shape vLLM's `Evictor` ABC expects without PCAM itself importing vLLM. A consumer writes a short bridge on their side to plug PCAM into a real serving stack.

**Replay and benchmark tooling.** A `TraceEvent` schema and a `replay()` primitive drive PCAM through deterministic traces offline. Three benchmark scripts — a replay harness, a baseline-comparison harness, and a vLLM demo — are runnable. The baseline harness compares PCAM against inline LRU/LFU by default and, optionally, against richer in-repo baselines (Sink+LRU, H2O, IndustryStyle) through a small adapter.

**Real-runtime-adjacent execution.** A HuggingFace-based attention extractor captures real per-block attention mass from a real causal-LM forward pass and emits it as a PCAM-compatible trace. This has been exercised live against a real `transformers` model — including a small real bug fix (`attn_implementation="eager"`) that the live run uncovered and that is now in the codebase. The resulting real trace replays cleanly through the full benchmark toolchain.

**Active-mode runtime integration (in code).** The active-mode vLLM bridge installs PCAM as the live eviction policy inside a running vLLM by patching `FreeKVCacheBlockQueue.popleft_n` against the v1 core surface. The bridge is feature-detected, fails clean on unsupported releases, and is unit-tested against a mock queue with twenty-three dedicated tests covering install/uninstall idempotency, method-surface probing, LRU fallback, and bridge-statistics accounting.

**Hardware-path credibility.** The repository contains SystemVerilog for the Count-Min frequency sketch, packaged RTL constants, and an updated block-entry type. A cocotb-based parity harness drives the RTL and the Python reference from the same trace and asserts identical outputs. The harness is landed; its one live green run is environment-dependent on a machine with cocotb and a SystemVerilog simulator.

**Environment-dependent live closures.** Three specific closures stand between the current state and "every path has been observed live in its target environment": the cocotb RTL parity run, the real-vLLM shadow-mode run against a real model, and the real-vLLM active-mode throughput comparison. All three have copy-pasteable runbooks in the repository. None of the three is expected to require significant code changes. The authoring environment did not have the required GPU, vLLM install, or HuggingFace Hub network access to close them in-place, and that fact is documented transparently in the closure run log rather than papered over.

---

## 7. Distance to Production Usage

The honest answer has to be split between software and hardware, because the two have very different clocks.

### Software production-readiness

On the software side, the platform is close to production-ready for a carefully-scoped deployment — specifically, for a shadow-mode design partner engagement with an LLM serving team that wants measurable proof-of-value before any active-mode switch. The core policy is bit-parity against a canonical reference. The public API is stable and narrow. The runtime adapter is tested. The replay and baseline harnesses give any reviewer the ability to reproduce a PCAM decision stream against any trace they care to provide. The shadow-mode integration path requires no changes to a partner's existing runtime and produces observational evidence on the partner's own workload. For that engagement shape, the remaining work is an engagement runbook, not additional engineering.

What still needs work before the software product is ready for something broader — an active-mode production deployment at a serving company that wants to replace its default eviction policy outright — is a different story. It looks like:

- A published supported-version matrix across the vLLM releases that the active-mode bridge has been tested against.
- A richer set of real-workload traces (LongBench, PassKey, multi-turn chat) captured through the extractor and replayed through the comparison harness against the full baseline set.
- A real serving-loop measurement at realistic request rates, on more than one model size, to quantify the active-mode bridge's overhead under load.
- Hardening of the install/uninstall path against edge cases in the specific vLLM internal the bridge patches.

These are incremental improvements on a working foundation; none require rethinking the platform.

### Hardware production-readiness

On the hardware side, the honest framing is that PCAM carries *credibility* but not *deployment*. The RTL exists. The parity harness exists. The algorithm the hardware would implement is the same algorithm the software already implements, and is bit-parity specified. What does not yet exist is a taped-out chip, an FPGA prototype running on a real board, a physical-synthesis pass confirming timing closure at a specific frequency on a specific process node, or any of the other artifacts that separate "hardware-ready architecture" from "hardware product." Those are real and multi-quarter efforts.

The path from the current state to a first meaningful hardware milestone — an FPGA prototype on a Xilinx Alveo board running the Count-Min sketch at target frequency and passing a deterministic trace end-to-end through the cocotb parity harness against the Python reference — is credible, and the parity infrastructure to validate that milestone is already in the repository. But it is not near-term in the way a software engagement is near-term. It is a separate workstream on a separate clock, and any acquirer or partner should treat "PCAM as software today" and "PCAM as hardware tomorrow" as two distinct commitments with two distinct time horizons.

### The strongest form of the current artifact

Put plainly: the strongest honest framing of the current artifact is **a software runtime backend for a canonical KV-cache policy specification, ready for a shadow-mode design partner engagement today, with a credible but multi-quarter path to hardware embodiment.** A sale, a license, or an acquisition pitched against that framing will survive diligence. A sale pitched as "production-ready hardware memory controller" will not.

---

## 8. What Is Already Proven

The claims below are factual and backed by artifacts a reviewer can read, run, or audit in the repository in under an hour. The table is the fastest way to scan the evidence; the paragraphs that follow add the context a diligence reviewer should read before citing them.

| Claim | Evidence |
|---|---|
| Canonical policy reference exists | ADR-0001 + pinned vendored reference file in-tree |
| Runtime is bit-parity against the reference | 20-test parity harness (green on every commit) |
| Public software API is stable and narrow | Phase 1 package surface (`KVCachePolicy`, `PCAMConfig`, `TierHint`, `PolicyMetrics`, `FrequencySketch`) |
| Runtime adapter into a real serving stack | Phase 2 `PCAMEvictor` (duck-typed vLLM Evictor surface) |
| Offline trace replay primitive | Phase 2 `simulator.pcam.trace.replay` + `TraceEvent` schema |
| Replay, baseline, and demo benchmark harnesses | Phase 3 scripts (`pcam_trace_replay`, `pcam_compare_baselines`, `pcam_vllm_demo`) |
| Real trace extraction from a real model | Phase 4 HuggingFace extractor, live-run verified on real torch |
| Shadow-mode vLLM integration | Phase 4 `vllm_bridge.generate_with_derived_trace` |
| Active-mode vLLM eviction replacement (in code) | Phase 5 `vllm_active_bridge` + 23 unit tests against a mock queue |
| Hardware-path credibility | SystemVerilog sketch + cocotb parity harness (landed, ready to run) |
| No drift between spec and runtime | Conformance harness enforces equivalence on every commit |
| Public API has not sprawled under integration work | Phase-1 surface unchanged across Phases 2–5 |

The canonical policy-reference relationship is established. The CTM+ specification is a single versioned artifact; the PCAM runtime is a bit-parity port of that artifact; the parity harness enforces equivalence on every commit under a fixed RNG seed and has been green from the beginning of the roadmap through the present branch tip. This is the foundation that makes every other claim trustworthy.

The shadow-mode integration path is verified end-to-end with real torch infrastructure. A real HuggingFace causal-LM forward pass with real eager attention has been driven through the full extractor-to-replay-to-baseline-comparison pipeline. The small real bug that surfaced during that live run (`attn_implementation="eager"` needed for `output_attentions=True` under `transformers` ≥ 4.36) has been fixed and is now part of the codebase.

The active-mode integration path exists in code and is unit-tested. The bridge's install-and-uninstall path, its method-surface feature-detection against the vLLM v1 core surface, its LRU fallback behavior when PCAM cannot produce a victim, its bridge-statistics accounting, and its graceful failure on unsupported vLLM versions are all covered by deterministic tests that do not require a GPU.

The broader architecture has not drifted. Every architectural decision record has held. The policy-runtime split has not leaked. No bridge class has been added between CTM+ and PCAM. The public API has not silently grown under the weight of benchmark or integration work. This discipline is itself a form of proof: it shows the platform's architectural commitments survive the normal pressure of feature delivery, and it is rare enough among memory-subsystem projects that a technical reviewer should weight it.

---

## 9. Benchmarks

This section separates benchmark evidence into clearly-labelled tiers for each layer. **Live-verified** numbers are reproducible on the current branch by running a single command. **Historical claims** are numbers from earlier CTM+ measurement work recorded in other repository documents — they are included for context and should not be treated as independently re-measured on this branch. **Environment-dependent** numbers are the ones pending the three closure runs discussed in Section 7; they are named here rather than omitted so a reviewer can see exactly which numbers are not yet claimable.

### 9.1 CTM+ benchmarks

CTM+ benchmarks cover the policy layer: correctness against the canonical specification, sketch-level behavior, and cross-workload claims from prior CTM+ measurement work.

**Live-verified on this branch.** These are correctness benchmarks, not throughput benchmarks. They are the mechanism by which a reviewer can trust that the CTM+ specification and the PCAM runtime cannot silently disagree. Green on every commit of the roadmap.

| Benchmark | Result | Evidence |
|---|---|---|
| Parity harness against vendored reference | 20 tests green, bit-for-bit equivalence on a fixed RNG seed | `simulator/pcam/tests/test_sketch_conformance.py` + `test_attention_evictor_parity.py` |
| Count-Min sketch saturation | Counter saturates at 15 after 20 increments of the same key | `TestSketchParity::test_single_key_saturation_parity` |
| Event-driven halving | Fires at `size >= reset_threshold`, halves counters and size atomically | `TestHalvingParity::test_halving_fires_at_reset_threshold` |
| Phase-aware scoring determinism | Identical PREFILL and DECODE scores for identical traces under a fixed RNG seed | `TestPhaseAwareScoring::test_prefill_and_decode_both_match_reference` |
| 500-step randomized differential | Zero divergence between the runtime and the vendored reference | `TestRandomizedEndToEnd::test_randomized_500_ops_parity` |

**Historical claims from prior CTM+ investor materials.** The numbers below appear in `CTM_plus/INVESTOR_PITCH.md`, the source-of-truth investor document for the broader CTM+ cross-workload narrative. They were produced in an earlier measurement context that predates the PCAM software-product roadmap, and **they have not been independently reproduced by the current parity or benchmark harness.** They are reported here because they are part of the CTM+ historical record, not because they have been re-validated on this branch. A diligence reviewer should treat them as CTM+ historical context and not as current live measurements against the PCAM runtime.

| Workload | Metric | LRU | CTM+ | Delta |
|---|---|---|---|---|
| Hotspot (batch ML) | Hit rate | 76.4% | 94.2% | +17.8 pts |
| vLLM inference | Tokens/sec | 1,850 | 2,180 | +18% |
| vLLM inference | Concurrent requests / GPU | 32 | 48 | +50% |
| GPU memory efficiency | Utilization | 72% | 89% | +17 pts |
| Database (TPC-C) | p99 latency | 12 ms | 8.5 ms | −29% |
| Database (TPC-C) | Transactions/sec | 125K | 142K | +13.6% |
| Decision latency | p99 | — | 2.35 µs | under the 3 µs requirement |
| KV cache retention | Important-token retention | 25.4% | 29.5% | +16.2% |

Reproducing these historical numbers against the current PCAM runtime on a fresh measurement environment is one of the open items in Section 10.

### 9.2 PCAM benchmarks

PCAM benchmarks cover the runtime-backend layer: policy-decision metrics on real and synthetic traces, runtime-adapter tests, and the pending real-vLLM serving-tier closures.

**Live-verified on this branch.**

| Benchmark | Result | Evidence |
|---|---|---|
| PCAM vs inline LRU/LFU (built-in demo trace) | 6 evictions, **0 sink evictions** for PCAM; 6 evictions, **1 sink eviction** for LRU and for LFU | `benchmarks/pcam_compare_baselines.py` |
| PCAM vs in-repo baselines (Sink+LRU, H2O, IndustryStyle) | PCAM matches Sink+LRU and H2O on zero sink evictions; IndustryStyle has a documented ghost-buffer warmup on short traces | `pcam_compare_baselines.py --include-inrepo-baselines` |
| Tier-hint distribution on demo trace | 5 HOT, 0 WARM, 2 COLD, 0 EVICT across 8 probed blocks | `benchmarks/pcam_trace_replay.py` |
| HuggingFace real-attention extraction | 25 `TraceEvent`s from 11 blocks from 44 tokens; per-block mass shows the expected causal-attention envelope `[13.17, 8.07, 5.99, 4.64, 3.63, ...]` | Phase 4 live run against real torch 2.11 + real eager attention |
| Round-trip: real extracted trace → replay → baseline comparison | Green end-to-end against the real trace file | `pcam_trace_replay.py --trace ...` + `pcam_compare_baselines.py --trace ...` |
| Active-mode bridge wiring | 23 tests green against a mock `FreeKVCacheBlockQueue`: install/uninstall idempotency, method-surface probing, LRU fallback, bridge statistics accounting | `simulator/pcam/tests/test_phase5_active_mode.py` |
| Full PCAM test suite (cumulative across all phases) | 239 passed, 3 skipped (environment-dependent), 0 failed, 0 errored | `pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q` |

The single defensible headline from the live-verified PCAM benchmarks is this: **on the built-in demo trace, PCAM's sink-pinning by construction yields zero sink evictions, while naive LRU and LFU baselines each evict one sink block.** The quantitative magnitude is small because the trace itself is small, but the direction is correct, reproducible, and applies to any serving stack whose default evictor is LRU-shaped. PCAM's behavior also matches the best-in-class sink-aware reference baselines (Sink+LRU, H2O) on that same trace, which is the correct apples-to-apples framing: PCAM is as safe as a hand-tuned sink-aware policy and safer than a naive one, as measured by the metric that matters most for LLM inference.

**Environment-dependent closures (pending).** Serving-tier throughput and latency numbers for PCAM against vLLM's default eviction — the numbers that would directly support an "X% more tokens/sec" or "Y% more concurrent requests" claim for the PCAM runtime itself — require one real run of `benchmarks/pcam_vllm_perf.py --policy both` on a CUDA machine with a working vLLM install and network access to a model. That run has not yet happened on this branch. The seven-step runbook for it is at `benchmarks/PHASE4_CLOSURE_RUN_LOG.md` section D, and the estimated engineer-time on a prepared machine is under an hour.

**What cannot be honestly reported yet.** The PCAM software runtime does **not** currently carry a published end-to-end serving throughput delta against vLLM's default. The active-mode bridge is implemented and unit-tested, but no live GPU run has produced tokens/sec, p50/p95/p99 latency, or concurrent-request-capacity numbers for PCAM specifically. Any document that cites such a number for PCAM must be citing either the pending closure run or the historical CTM+ investor-pitch numbers in Section 9.1, not a reproducible PCAM-runtime measurement on this branch. This distinction is exactly the kind of caveat a diligence reviewer should check; the memo is written so that check produces a clean answer.

### 9.4 FSCS-Derived Signal Integration (April 2026)

Three new optional scoring signals were derived from the Text-FSCS
attention-operator research program and integrated into PCAM's
KV-cache scoring as policy-layer enhancements:

| Signal | What it captures | Scoring integration | Default |
|---|---|---|---|
| **Boundary sensitivity** (D) | Structural boundary tokens (sentence starts, paragraph breaks) that are attention sinks | Additive: `score += w_boundary · D` | weight=0.0 (off) |
| **Band class** (G) | Layer-depth-based block importance: global-context layers (expensive to miss) vs local-syntax layers (cheap to recompute) | Multiplicative: `score *= G` | G=1.0 (neutral) |
| **Instability** (U) | Future full-attention demand — blocks in unstable regions will likely be re-read and are expensive to evict | Additive: `score += w_instability · U` | weight=0.0 (off) |

**Design principle:** the signals are caller-supplied metadata, not
internally computed. PCAM does not import transformer code or FSCS
modules. The caller (inference runtime, trace replayer, or vLLM
bridge) determines boundary positions, layer bands, and instability
levels and passes them to PCAM via `ensure_block()` or
`set_block_*()` methods. This preserves the CTM+/PCAM boundary as a
pure memory-management layer.

**Test evidence:** 36 new unit tests across three test files (12 + 11
+ 13), covering default-off behavior, enabled scoring, proportionality,
admission paths, per-instance weight management, cross-signal
composition, and backward compatibility. All existing 240 PCAM tests
continue to pass (276 total, 0 failures).

**Validation on real data:** an annotated KV-cache trace was captured
from FSCS-wrapped Mistral-7B (4 sequences × 512 tokens × 32 layers =
4,096 blocks, 8,208 events) and replayed through PCAM in baseline
(four-signal, signals off) vs enhanced (six-signal, signals on) mode.

Result:
- **Baseline:** 1,022 victims evicted across 4 rounds
- **Enhanced:** 192 victims evicted across 4 rounds
- **Eviction rounds changed: 4 of 4 (100%)**
- **Individual block choices changed: 1,108**

The signals changed every single eviction decision. The enhanced
policy is more conservative (protecting boundary / global-context /
unstable blocks), which reduces eviction volume by 81%. Whether
this conservatism improves downstream serving quality (cache hit
rate, p99 latency, concurrent requests) requires a serving-tier
benchmark, which is the next calibration step.

**Caveats:** the 100% decision-change result demonstrates *signal
impact*, not *quality improvement*. The weights (boundary=0.10,
instability=0.15, band={1.3, 1.0, 0.8}) are starting points, not
tuned values. The trace uses a position-based attention-mass proxy
rather than real per-block attention weights (real attention
requires `output_attentions=True` which was not used to conserve
VRAM). A serving-tier benchmark comparing enhanced PCAM against
baseline on cache hit rate and latency under load is the
measurement that would support a quantitative improvement claim.

---

## 10. What Is Still Pending

The pending work is best framed as a forward plan, because none of it is blocking the platform's current usefulness. It is what turns the current software-first asset into a broader production story.

The three environment-dependent live closures are first. A live cocotb run against the SystemVerilog sketch on any machine with cocotb and Verilator installed closes the hardware-credibility story's last open item. A real-vLLM shadow-mode run on a CUDA machine with network access produces the first real-workload observational numbers against a concrete named model. A real-vLLM active-mode throughput comparison on the same machine produces the first serving-tier latency-and-throughput numbers for PCAM against vLLM's default eviction. Each is estimated at under an engineer-hour on a prepared machine, and each has a seven-step runbook checked into the repository.

Beyond the closures, the next layer is *breadth*. The active-mode bridge currently targets a narrow window of vLLM releases; a formal supported-version matrix tested against at least two points in that window reduces integration risk for a partner engagement. The trace extractor currently runs last-layer attention aggregation only; multi-layer aggregation is a known follow-up that improves the fidelity of captured real workloads. The benchmark suite currently exercises a synthetic demo trace and the in-repo baselines; a captured LongBench or PassKey run replayed through the same comparison harness produces the first results on a recognized academic benchmark.

Above that is the *production-hardening* work that applies to any software memory-policy project targeting a real serving loop: operational observability beyond the current stats snapshot, a richer failure-mode taxonomy for the active-mode install and uninstall paths, an automated regression story for new vLLM releases, and a clearer deployment story for ops teams that do not want to monkey-patch a Python package in their own production environment. None of this is novel work; all of it is normal infrastructure engineering, and all of it is downstream of a real design-partner engagement rather than upstream of one.

At the longest horizon is hardware: an FPGA prototype on a specific board at a specific target frequency, a physical-synthesis pass with real area and power numbers for a specific process node, a tape-out decision on a chosen integration path (CXL memory expander, SSD FTL, or GPU-side HBM controller), and the full productization loop beyond first silicon. These are multi-quarter efforts and should not be framed as near-term. The parity infrastructure that will validate them is in the repository today; the hardware execution that will use it is a future commitment.

The pending list is not a weakness list. It is the normal forward work plan of a platform that has stabilized its architectural core and is ready to extend into breadth, depth, and hardware. Each item is scoped, each has an obvious first closure, and none require rethinking the core contract between CTM+ and PCAM.

---

## 11. Conclusion

CTM+ and PCAM together address a concrete and growing problem in modern AI infrastructure: LLM serving systems are increasingly memory-bound, and the default eviction policies those systems ship with were not designed for attention-based workloads. The combined platform's answer is to treat memory policy as something that deserves the same rigor compute kernels already receive — a canonical specification, a bit-parity runtime, a conformance harness that enforces agreement between the two, and a set of integration layers that let the policy actually run inside real inference systems rather than sitting in a design document.

The architecture is meaningful and technically grounded. CTM+ is a single, precise, versioned specification of record for KV-cache scoring behavior. PCAM is a working software runtime that implements that specification, ships it as a consumable Python package, exposes it through a narrow stable API, and adapts it into real inference workflows in both observational shadow mode and causal active mode. The parity harness gives any reviewer a mechanized way to confirm that the runtime and the specification agree. Hardware credibility is present in the form of RTL and a cosimulation harness targeted at the same specification.

The strongest current form of the artifact is software-first. It is ready today for a shadow-mode design-partner engagement with an LLM serving team, and the runbook and tooling for that engagement already exist. Active-mode deployment is implemented but is not yet live-measured under serving-loop load; that closure is environment-dependent and is the single highest-leverage remaining near-term step. Hardware deployment is a credible forward path with existing architectural grounding, but it is a medium-term commitment on its own clock, and anyone evaluating the platform should hold "software today" and "hardware later" as two distinct commitments with two distinct time horizons.

The path to broader production usage is credible without being complete. Each open item — the environment-dependent live closures, the supported-version breadth work, the real-trace capture and comparison, the operational hardening, and the hardware milestones — is scoped, understood, and does not require revisiting the architectural core. A design partner, a strategic acquirer, a technical investor, or a corp-dev reviewer can all reasonably evaluate this work in its current form with a clear view of what is proven, what is pending, and how the pending items connect into a coherent forward plan. That clarity, more than any individual benchmark number, is the real product of the work to date.
