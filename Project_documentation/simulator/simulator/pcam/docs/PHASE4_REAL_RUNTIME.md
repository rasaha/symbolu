# PCAM Phase 4 — Real-Runtime Measurement

**Status:** Phase 4 complete for the executable pieces (in-repo baseline adapter, derived-trace reconstruction, pure-Python attention-to-block conversion). Real vLLM and HuggingFace executions are landed ready-to-run but require external dependencies not available in the current dev environment.
**Scope:** real-vLLM shadow mode, HuggingFace trace extractor, in-repo baseline adapter, acquisition-facing benchmark report.
**Contract:** [`docs/design/ADR-0001`](../../../../repository/docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md)
**Depends on:** Phase 0–3 (vendored reference, public API, integration surface, replay infrastructure).

---

## What Phase 4 ships

| Artifact | Role | Runs in this env? |
|---|---|---|
| `benchmarks/vllm_bridge.py` | Real vLLM shadow-mode helper. Lazy imports vllm; derives `TraceEvent` lists from observed sequence shapes. | Structural / pure-Python logic: yes. Real `LLM.generate()`: **no** (vllm absent). |
| `benchmarks/pcam_vllm_demo.py` (upgraded) | Adds a real `--real-vllm` path that calls the bridge, replays the derived trace through `KVCachePolicy`, and reports shadow-mode results. | Synthetic walkthrough: yes. `--real-vllm`: **fails clean** with install hint. |
| `benchmarks/pcam_trace_extract.py` | HuggingFace-based real attention-trace extractor using `AutoModelForCausalLM(output_attentions=True)`. | Pure-Python helpers: yes. Full model run: **fails clean** (torch + transformers absent). |
| `benchmarks/pcam_compare_baselines.py` (upgraded) | Adds `InRepoBaselineAdapter` + `--include-inrepo-baselines` flag. Wires `SinkLRU`, `H2O`, `IndustryStyle` from `simulator/pcam/baselines/` through the Phase 1 trace path. | **Yes.** Fully live and verified. |
| `benchmarks/PCAM_PHASE4_REPORT.md` | Acquisition-facing static report summarizing every measurement Phase 4 could produce. | N/A (read-only artifact). |
| `simulator/pcam/tests/test_phase4_realtime.py` | 22 focused tests covering the new surfaces, with mock attention tensors for the HF extractor helpers. | **Yes.** 22/22 green. |

## Three honesty tiers

Phase 4 extends the Phase 3 honesty framing with a new tier — **"real-dependency code path that this environment cannot execute"** — and introduces explicit opt-in for the Phase 4 comparison extras.

| Tier | Examples | What it proves |
|---|---|---|
| **Replay-only** (Phase 3) | `pcam_trace_replay.py`, default `pcam_compare_baselines.py`, `pcam_vllm_demo.py` synthetic walkthrough | PCAM's scoring decisions on a deterministic trace. Zero external dependencies. |
| **In-repo richer baselines** (Phase 4, live) | `pcam_compare_baselines.py --include-inrepo-baselines` | PCAM's decisions alongside sink-aware reference heuristics (`SinkLRU`, `H2O`, `IndustryStyle`) on the same trace. Adapter correctness is verified by tests. |
| **Real runtime** (Phase 4, ready-to-run) | `pcam_vllm_demo.py --real-vllm`, `pcam_trace_extract.py` | Would produce real-workload results on real inputs. Currently requires `pip install vllm` + GPU or `pip install torch transformers`. Fails clean when missing. |

The explicit rule is: **any numbers emitted by any script carry a tier label.** `pcam_vllm_demo.py --real-vllm` prints a `REAL vLLM (Shadow Mode)` banner; the replay-only scripts print `REPLAY-ONLY`; the compare script shows a per-row `source` column (`runtime` / `inline` / `in-repo`). A reader never has to guess.

## What real-vLLM shadow mode does (and does not do)

**Shadow mode** in Phase 4 means:

1. Run a real `vllm.LLM.generate(prompts)` with `vllm`'s default evictor.
2. Observe `(prompt_token_count, completion_token_count)` per sequence.
3. Derive a `TraceEvent` list from those shapes — one block per `block_size` tokens, first block pinned as sink, one uniform-weight attention event per generated token.
4. Replay the derived trace through `KVCachePolicy` via `simulator.pcam.trace.replay`.
5. Report what PCAM *would* have done on the observed workload.

This is what the cloud-controller branch earlier in the roadmap called "proof of value via shadow deployment" — run the policy in parallel with the incumbent system, compare decisions, never touch production.

**Shadow mode deliberately does NOT:**

- Monkey-patch `vllm.core.evictor_v2.Evictor` or any vllm internals. vLLM's evictor ABC has changed shape across releases, and a hard subclass would be brittle. A future "active mode" phase will add that bridge; it is explicitly scoped out of Phase 4.
- Capture per-layer attention mass from the model forward pass. That would require attention-output hooks inside vLLM's paged-attention kernel, which is not exposed in the public API. The HuggingFace extractor (`pcam_trace_extract.py`) provides that richer signal against a separate model run.
- Report throughput, latency, or quality numbers from the real vLLM run. The shadow-mode output is about policy decisions, not serving outcomes. Wiring up throughput comparisons would require a real eviction-policy replacement in vllm, which is Phase 5 scope.

## What the in-repo baseline adapter does

`InRepoBaselineAdapter` wraps a `BaselineController` from `simulator/pcam/baselines/` and presents the same `_BaselineBase` surface the inline LRU/LFU baselines use. The key mapping:

| TraceEvent | In-repo `record_access` call |
|---|---|
| `register_sequence(seq_id)` | Updates the adapter's `_last_seq_id` so subsequent calls carry the right `sequence_id` field. |
| `ensure_block(block_id, sequence_id, positions)` | `record_access(query_block=block_id, accessed_blocks=[block_id], attention_scores={block_id: 0.0}, sequence_id=seq_id)` |
| `on_block_attention(block_id, attention_sum, sequence_id)` | `record_access(query_block=block_id, accessed_blocks=[block_id], attention_scores={block_id: attention_sum}, sequence_id=seq_id)` |
| `select_victims(count)` | `select_evictions(num_to_evict=count, sequence_id=_last_seq_id)` |

**Sink semantics note.** The in-repo baselines take `num_sinks` in their `ControllerConfig` and pin the first `num_sinks` **block_ids** they see. PCAM pins blocks whose **admission positions** contain indices `< sink_tokens`. On the demo trace where the sink block is admitted first with `block_id=0`, the two agree (`num_sinks=1` pins block 0). On more complex traces where non-sink blocks could be admitted before the sink, they can disagree. The adapter uses `num_sinks=1` as a conservative default and documents this explicitly.

**IndustryStyle warmup.** `IndustryStyleController` has a ghost-buffer cooldown and may return an empty victim list on short traces (it did on the demo trace — 0 evictions, not a bug). The test suite asserts this behavior explicitly.

## Live verified measurements

With `--include-inrepo-baselines` on the built-in demo trace (119 events, `max_blocks=128`, `sink_tokens=4`):

```
policy                   source   evictions  sink_evictions  attn_cost   live_blocks
-----------------------  -------  ---------  --------------  ----------  -----------
PCAM                     runtime  6          0               0.0060      0
LRU                      inline   6          1               0.0050      23
LFU                      inline   6          1               0.0050      23
SinkLRU (in-repo)        in-repo  6          0               0.0060      23
H2O (in-repo)            in-repo  6          0               0.0060      23
IndustryStyle (in-repo)  in-repo  0          0               0.0000      29
```

Read these numbers as:

- **PCAM and the sink-aware in-repo baselines** (`SinkLRU`, `H2O`) all show zero sink evictions. This is the "PCAM is equivalent to best-in-class sink pinning" signal. Good for acquirer-facing positioning: "we match the state-of-the-art sink baselines and are also instrumented for tier hints and shadow deployment."
- **Naive inline baselines** (`LRU`, `LFU`) each evict one sink block. This is the "sink-unaware policies hemorrhage attention sinks" signal. Good for showing new customers why sink-unaware caching is a problem.
- **`IndustryStyle` reporting zero evictions** is the documented warmup-cooldown behavior. Not a bug; flagged explicitly in the doc and in the test.
- **PCAM's `live_blocks=0` in the replay final state** is because the demo trace ends with a `complete_sequence` event that frees every block it admitted. The baselines don't act on `complete_sequence`, so their live counts stay at 23–29. Not apples-to-apples in the final-state column; fully apples-to-apples in `evictions` / `sink_evictions` / `attention_weighted_cost`.

## What you need to run the real paths

### `pcam_vllm_demo.py --real-vllm`

- `pip install vllm`
- A CUDA-capable GPU with enough VRAM for the chosen model (default `facebook/opt-125m` fits on any 4GB+ card)
- Optional: `--model`, `--prompt` (repeatable), `--max-tokens`, `--block-size`, `--dtype`, `--trust-remote-code`

Example invocation once dependencies are present:

```bash
python benchmarks/pcam_vllm_demo.py --real-vllm \
    --model facebook/opt-125m \
    --prompt "Explain PCAM in one sentence." \
    --prompt "Summarize paged attention in one sentence." \
    --max-tokens 64 \
    --json /tmp/pcam_real_vllm.json
```

### `pcam_trace_extract.py`

- `pip install torch transformers`
- CPU-only works for small models; GPU is faster if available
- Default model is `gpt2` (fits on CPU in ~1GB)

```bash
python benchmarks/pcam_trace_extract.py \
    --model gpt2 \
    --prompt "The quick brown fox jumps over the lazy dog." \
    --out /tmp/real_trace.json
```

Then replay the real trace through any Phase 3 script:

```bash
python benchmarks/pcam_trace_replay.py --trace /tmp/real_trace.json
python benchmarks/pcam_compare_baselines.py --trace /tmp/real_trace.json --include-inrepo-baselines
```

## What remains after Phase 4

- **Live execution of `pcam_vllm_demo.py --real-vllm`.** The code is landed, the tests verify fail-clean behavior, and the bridge correctly derives traces from simulated vLLM outputs in unit tests. What remains is *one green run on a machine with vllm installed* — identical to the Phase 2.5 closure pattern. When that happens, record the result in a new `benchmarks/PHASE4_FIRST_REAL_VLLM_RUN.md` runbook (create alongside the report).
- **Live execution of `pcam_trace_extract.py`.** Same pattern — the helpers are unit-tested with mock tensors, but the full HuggingFace run needs torch + transformers installed.
- **Active-mode vllm integration (Phase 5).** A `vllm.core.evictor_v2.Evictor` subclass that forwards to `PCAMEvictor`, plus a monkey-patch that installs it as the active eviction policy. This would turn shadow-mode measurements into real throughput/latency comparisons. The bridge reference shape already lives in the docstring of `simulator/pcam/integrations/vllm.py`; wiring it as a real evictor is ~50 lines of consumer code plus version-compatibility testing.
- **Richer trace datasets.** LongBench, PassKey, needle-in-a-haystack runs captured via the HuggingFace extractor and checked in as fixture traces under `benchmarks/traces/`. The current demo trace is a 119-event synthetic scenario; real workload traces would produce more representative baseline comparisons.
- **Throughput / latency comparison story.** Phase 4 reports policy decisions only. A real throughput story requires (a) active-mode vllm integration and (b) a real serving loop with timed request generation. That is Phase 5+ work.

## What Phase 4 explicitly does NOT add

- No new runtime adapters beyond vLLM. SGLang / TGI / DeepSpeed stay deferred; add only when a design partner asks.
- No package-root API expansion. All Phase 4 symbols live under `benchmarks/` or in `_report.py` (private). `simulator.pcam.*` public surface is unchanged.
- No bridge class between CTM+ and PCAM. Forbidden by ADR-0001.
- No changes to ADR-0001, the vendored reference, the parity harness, the Phase 1 public API, the Phase 2 integration surface, or the Phase 3 default report.
- No hard dependency on `vllm`, `torch`, `transformers`, or `numpy`. Every script in `benchmarks/` imports cleanly in a pure-Python environment and fails clean at the method-call boundary when a runtime dependency is missing.
