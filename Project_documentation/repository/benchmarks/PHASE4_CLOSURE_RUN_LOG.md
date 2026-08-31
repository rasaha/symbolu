# Phase 4 Closure Run Log

**Status:** Partial live closure achieved. Extractor path verified live; vLLM path remains hard-blocked by this environment's sandbox (no CUDA, HF Hub proxy-blocked, vllm wheel version conflicts).

This file is the operational run log for Phase 4 closure attempts, following the same pattern as `Project_documentation/simulator/simulator/pcam/rtl/tests/FIRST_LIVE_RUN.md`. Future closure attempts should append to the "Run log" section at the bottom.

---

## Environment (this closure attempt)

| Property | Value |
|---|---|
| Python | 3.11.15 |
| OS | Linux 6.18.5 |
| GPU / CUDA | **None** |
| `torch` | 2.11.0+cu130 (installed via `pip install torch`) |
| `transformers` | 5.5.3 (installed via `pip install transformers`) |
| `vllm` | **Not installable** in this sandbox (see "vLLM block details" below) |
| HuggingFace Hub | **Proxy-blocked** — every `*.huggingface.co` and mirror host returns `403 host_not_allowed`. Only `pypi.org` is reachable. |

## What was closed live

### Extractor path — LIVE VERIFIED ✓

`benchmarks/pcam_trace_extract.py` successfully ran end-to-end against a real torch forward pass and emitted a real `TraceEvent` JSON file that replays cleanly through the existing Phase 3 tooling.

**Workaround for HF Hub block.** HuggingFace Hub is proxy-blocked in this sandbox, so `gpt2` (or any pretrained model) cannot be downloaded. To reach the extractor's full code path without faking results, a minimal real `GPT2LMHeadModel` + `PreTrainedTokenizerFast` were constructed in-process using `transformers` APIs and saved to `/tmp/phase4_live/local_gpt2/`:

- Tiny GPT2 config: `vocab_size=256`, `n_positions=64`, `n_embd=32`, `n_layer=2`, `n_head=2`, `attn_implementation='eager'`
- Character-level byte tokenizer (real `PreTrainedTokenizerFast`, 256 tokens)
- Random-initialized weights saved as `model.safetensors` (35,712 params)

This is a real torch model, not a mock or simulator, but the weights are random because no pretrained weights were reachable. The extracted attention signal is architecturally real (causal-attention structure is visible in the decreasing per-block mass) but is not semantically meaningful because the model is untrained. **A follow-up run on a machine with HF Hub access should re-execute this against a real pretrained model (e.g. `gpt2`) to confirm the extractor produces meaningful semantic output.**

#### Small real fix applied

The first extractor run failed with:

```
ValueError: The `output_attentions` attribute is not supported when using
the `attn_implementation` set to sdpa. Please set it to 'eager' instead.
```

This is a breaking change in `transformers` ≥ 4.36 where SDPA became the default attention kernel and does not return attention weights. The extractor's `from_pretrained` call was updated to pass `attn_implementation="eager"` alongside `output_attentions=True`, and an inline comment explains why. One-line diff in `benchmarks/pcam_trace_extract.py`.

#### Live command and real output

```
$ TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1 python benchmarks/pcam_trace_extract.py \
    --model /tmp/phase4_live/local_gpt2 \
    --prompt "The quick brown fox jumps over the lazy dog." \
    --block-size 4 \
    --out /tmp/phase4_live/real_trace.json

Loading weights: 100%|██████████| 28/28 [00:00<00:00, 5049.90it/s]
wrote 25 events (11 blocks, 44 tokens) from '/tmp/phase4_live/local_gpt2' to /tmp/phase4_live/real_trace.json
```

The emitted JSON has 25 `TraceEvent` records (11 `ensure_block` + 11 `on_block_attention` + register/phase/complete events). Per-block attention sums follow the expected causal-attention pattern:

```
block 0: 13.1673  ← attended to by all 44 tokens (causal prefix)
block 1:  8.0725
block 2:  5.9921
block 3:  4.6368
block 4:  3.6308
...
```

This monotone decrease is the real signature of causal self-attention over a 4-token block layout — each later block is attended to by progressively fewer queries. The weights are random but the architectural attention pattern is real.

#### Replay and compare verification

The real trace round-trips through both Phase 3 entry points:

```
$ python benchmarks/pcam_trace_replay.py --trace /tmp/phase4_live/real_trace.json --max-blocks 64
   events replayed: 25
   complete_sequence calls: 1
   step: 22 (11 ensures + 11 attention events — matches expectation)

$ python benchmarks/pcam_compare_baselines.py --trace /tmp/phase4_live/real_trace.json \
      --max-blocks 64 --include-inrepo-baselines
   All 6 policies (PCAM, LRU, LFU, SinkLRU, H2O, IndustryStyle) process the
   trace cleanly with zero evictions (the trace has no select_victims events,
   which is expected from the extractor; see below).
```

#### Known extractor behavior

The extractor emits `register_sequence`, `set_phase(DECODE)`, `ensure_block` (one per block), `on_block_attention` (one per block), and `complete_sequence`. It deliberately does NOT emit `select_victims` events, because those are a consumer concern — a benchmark that wants to exercise eviction decisions on an extracted trace can append them externally. This is documented in the extractor module docstring.

## What is still blocked

### vLLM path — HARD BLOCKED ✗

The `pcam_vllm_demo.py --real-vllm` path is not closeable in this sandbox. Three independent blocks apply, any one of which would be sufficient to prevent execution; all three present together:

1. **No CUDA hardware.** `nvidia-smi` is not present; `torch.cuda.is_available()` returns `False`. vLLM is a GPU-first inference engine; `LLM(...)` construction would fail on this machine even with a successful install.
2. **vllm wheel version conflicts.** `pip install vllm` in this sandbox hit a PyJWT conflict with the system package manager. Even `pip install --no-deps vllm` (which succeeds) leaves a vllm that requires `torch==2.10.0` and `transformers<5`, while the extractor path needs `torch 2.11` and `transformers 5.5`. The two cannot coexist in the same env without a virtualenv per path.
3. **HuggingFace Hub proxy block.** Even if vllm imported cleanly on CPU (it does not), `LLM(model="facebook/opt-125m")` would need to download weights from `huggingface.co`, which returns `403 host_not_allowed` for every HF endpoint and mirror tested.

**The fail-clean behavior is verified and correct.** Running `python benchmarks/pcam_vllm_demo.py --real-vllm --quiet` in this environment produces:

```
ERROR: vllm is not installed. Install with `pip install vllm` (requires a
CUDA-capable GPU and a supported CUDA runtime). The PCAM synthetic demo
path does not require vllm — run `python benchmarks/pcam_vllm_demo.py`
without --real-vllm to exercise the adapter without a real model.
rc=2
```

**What the first engineer with the right environment should do** (identical pattern to Phase 2.5 `FIRST_LIVE_RUN.md`):

```bash
# 1. Verify environment
nvidia-smi              # expect: a CUDA-capable GPU
python -c "import torch; print(torch.cuda.is_available())"  # expect: True

# 2. Install vllm in a clean virtualenv
python -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install vllm

# 3. Run the real path (small model, small prompts)
cd /path/to/symbolu
python benchmarks/pcam_vllm_demo.py --real-vllm \
    --model facebook/opt-125m \
    --prompt "Explain PCAM in one sentence." \
    --max-tokens 32 \
    --json /tmp/pcam_real_vllm.json

# 4. Record the resulting transcript and metrics in the Run log below.
```

Expected output structure: a "REAL vLLM (Shadow Mode)" banner, a table showing model / block_size / num_prompts / total_prompt_tokens / total_completion_tokens / derived_events, a list of victim IDs, tier hints, and a final policy stats snapshot. If any part of that fails, fix the smallest possible thing against the reference and re-run — do not weaken the test or the banner.

## Test state after closure

Full PCAM suite with the Phase 4 fix and environment-aware test markers:

```
$ python -m pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q
112 passed, 3 skipped in 1.97s
```

The 3 skips are:
1. `test_ensure_transformers_fails_clean` — skipped because torch + transformers ARE installed in this environment (the fail-clean path is only meaningful in a stripped env).
2. `test_extract_run_cli_fails_clean` — same reason.
3. `test_freq_sketch_rtl_parity` — Phase 2.5 cocotb wrapper, pre-existing skip, independent workstream.

A new positive test `test_ensure_transformers_available_succeeds_when_installed` was added to cover the complementary case: when the stack is present, the probe must return cleanly without raising.

## Files modified in this closure attempt

| File | Change |
|---|---|
| `benchmarks/pcam_trace_extract.py` | Added `attn_implementation="eager"` to the `AutoModelForCausalLM.from_pretrained` call so `output_attentions=True` works on transformers ≥4.36. Inline comment explains the SDPA-vs-eager distinction. |
| `simulator/pcam/tests/test_phase4_realtime.py` | Added a `_transformers_stack_installed()` helper and `@pytest.mark.skipif` decorators on the two extractor fail-clean tests so they skip cleanly when the stack is installed. Added a new `test_ensure_transformers_available_succeeds_when_installed` covering the complementary positive case. |
| `Project_documentation/simulator/simulator/pcam/rtl/tests/FIRST_LIVE_RUN.md` pattern | This file (new) — Phase 4 closure runbook. |

## Can Phase 4 be considered fully closed?

**No — partially closed.** 1 of 2 live paths is verified; 1 remains environmentally blocked.

| Path | Status | Blocker |
|---|---|---|
| `pcam_trace_extract.py` | ✓ LIVE VERIFIED | None — closed in this environment with a one-line real bug fix. |
| `pcam_vllm_demo.py --real-vllm` | ✗ BLOCKED | No CUDA hardware, vllm wheel version conflicts, HuggingFace Hub proxy-blocked. |

Closure of the vLLM path requires one run on any machine with:
- A CUDA-capable GPU (any supported architecture)
- `pip install vllm` in a clean virtualenv
- Network access to `huggingface.co` (or a pre-seeded model cache)

Pattern identical to Phase 2.5 RTL cosim closure. Estimated engineer-time: ~30 minutes once the environment is available.

---

## Next closure instructions — copy-pasteable runbooks

Two independent closures remain. Neither depends on the other; do them on whichever machine has the right environment first. Each runbook follows the same shape: prerequisites → install → run → expected output → what to record.

### A. vLLM real-runtime closure (requires CUDA GPU)

**Prerequisites**

- A CUDA-capable GPU with ≥ 4GB VRAM
- NVIDIA driver installed (`nvidia-smi` reports the GPU)
- Network access to `pypi.org` and `huggingface.co`
- The symbolu repo cloned locally

**Step 1: Verify the environment**

```bash
nvidia-smi
python3 -c "import torch; assert torch.cuda.is_available(), 'no CUDA'; print('CUDA ok:', torch.cuda.get_device_name())"
curl -sI https://huggingface.co/facebook/opt-125m/resolve/main/config.json | head -1
# expect: a GPU name, "CUDA ok: ...", and an HTTP 200 or 302 from huggingface.co
```

If any of these fail, stop — the vLLM path is not closable on this machine.

**Step 2: Install vLLM in a clean virtualenv**

Use a fresh virtualenv. vLLM pins `torch==2.10.0` and `transformers<5`, which conflict with what the extractor path uses; co-installing them in a single env is a known problem and the reason we isolate here.

```bash
cd /path/to/symbolu
python3 -m venv .venv-vllm
source .venv-vllm/bin/activate
pip install --upgrade pip
pip install vllm
python -c "import vllm; print('vllm:', vllm.__version__)"
```

**Step 3: Run the real-vLLM shadow mode demo**

```bash
python benchmarks/pcam_vllm_demo.py --real-vllm \
    --model facebook/opt-125m \
    --prompt "Explain PCAM in one sentence." \
    --prompt "Name three cache eviction algorithms." \
    --prompt "Summarize paged attention in one sentence." \
    --max-tokens 32 \
    --block-size 16 \
    --max-blocks 256 \
    --json /tmp/pcam_phase4_vllm_run.json
```

**Step 4: Expected output signature**

A clean run prints a `REAL vLLM (Shadow Mode)` banner followed by four tables:

```
=============================================
  PCAM vLLM Demo — REAL vLLM (Shadow Mode)
=============================================
NOTE: vLLM ran a real model on real inputs...

vLLM run
metric                   value
-----------------------  ----------------
model                    facebook/opt-125m
block_size               16
num_prompts              3
total_prompt_tokens      ~20-30
total_completion_tokens  ~90-100
derived events           ~110-130

Victim IDs selected during replay: N
  first 16: ...

Tier hints (first 20)
block_id  tier
--------  -----
0         HOT
...

Final policy stats
metric            value
----------------  -----
evictions         ...
gpu_blocks        ...
...
```

The JSON output at `/tmp/pcam_phase4_vllm_run.json` will contain the same data in machine-readable form. The `mode` field should be exactly `"real-vllm-shadow"`.

**Step 5: If it fails**

Three expected failure modes, in decreasing order of likelihood:

1. **Out of GPU memory.** Try a smaller model: `--model facebook/opt-125m` is the default; `--model gpt2` is smaller. Or drop `--max-tokens` to `16`.
2. **Model download blocked or slow.** Use a model you already have in the HF cache: `--model /path/to/local/hf/cache/models--facebook--opt-125m/snapshots/.../`.
3. **vLLM evictor ABC changed in a newer release.** `benchmarks/vllm_bridge.py` uses the public `vllm.LLM(...).generate(...)` API, not the Evictor ABC, so this should not break — but if it does, the fix is usually a one-line import-path adjustment against the current vllm version. **Debug against the reference, never against the test.** See "If parity fails" in `../simulator/pcam/rtl/tests/FIRST_LIVE_RUN.md` for the debugging discipline.

### B. Extractor real-pretrained-model closure (requires HF Hub access)

**Prerequisites**

- Any machine with Python 3.9+
- Network access to `huggingface.co` (or a pre-seeded HF cache at `~/.cache/huggingface/`)
- No GPU required — `gpt2` runs comfortably on CPU

**Step 1: Verify the environment**

```bash
cd /path/to/symbolu
curl -sI https://huggingface.co/gpt2/resolve/main/config.json | head -1
# expect: HTTP/1.1 200 OK  or  HTTP/1.1 302 Found
```

If the curl fails, use a pre-seeded HF cache or a machine with network access; do NOT fall back to a random-init model just to make the command succeed — the prior closure attempt already did that and the doc reflects it.

**Step 2: Install dependencies**

A separate virtualenv from the vLLM path is recommended to avoid the known `torch` version conflict:

```bash
python3 -m venv .venv-extractor
source .venv-extractor/bin/activate
pip install --upgrade pip
pip install torch transformers
python -c "import torch, transformers; print('torch:', torch.__version__, '/ transformers:', transformers.__version__)"
```

**Step 3: Run the extractor against real pretrained `gpt2`**

```bash
python benchmarks/pcam_trace_extract.py \
    --model gpt2 \
    --prompt "The quick brown fox jumps over the lazy dog." \
    --block-size 16 \
    --sink-tokens 4 \
    --out /tmp/pcam_phase4_gpt2_trace.json
```

**Step 4: Expected output signature**

```
wrote N events (M blocks, K tokens) from 'gpt2' to /tmp/pcam_phase4_gpt2_trace.json
```

For the default prompt (44 tokens) with `--block-size 16`, expect roughly:
- `K = 11` tokens (gpt2's BPE tokenizer is denser than character-level)
- `M = 1` block
- `N = 6` events (register + phase + 1 ensure + 1 attention + complete)

For longer prompts, scale linearly.

**Step 5: Verify the real trace replays through Phase 3 tooling**

```bash
# Replay the real trace — expect a clean report, no errors
python benchmarks/pcam_trace_replay.py \
    --trace /tmp/pcam_phase4_gpt2_trace.json \
    --max-blocks 256

# Compare against every baseline, including the in-repo ones
python benchmarks/pcam_compare_baselines.py \
    --trace /tmp/pcam_phase4_gpt2_trace.json \
    --max-blocks 256 \
    --include-inrepo-baselines \
    --json /tmp/pcam_phase4_gpt2_compare.json
```

**Step 6: Verify the attention signal is semantically meaningful, not random**

The prior sandbox closure extracted traces from a random-init model and the per-block attention mass still showed a monotone decrease (the architectural causal-attention signature). With a pretrained model you should expect the same monotone envelope, but with **variation within each block** that reflects the model's learned attention patterns. A useful one-liner:

```bash
python -c "
import json
d = json.load(open('/tmp/pcam_phase4_gpt2_trace.json'))
attns = [(e['args']['block_id'], round(e['args']['attention_sum'], 4))
         for e in d if e['kind'] == 'on_block_attention']
for bid, mass in sorted(attns):
    print(f'block {bid:3d}: {mass}')
"
```

A pretrained model's distribution will usually show:
- block 0 (containing the sink tokens + BOS) with clearly elevated mass
- non-monotone variation across later blocks reflecting content-dependent attention
- very low mass on blocks near the current generation position (they've been attended to by fewer queries in the causal mask)

If the distribution looks like a clean monotone line with no variation, the model may not be actually pretrained — double-check the `--model` argument.

**Step 7: If it fails**

1. **`OSError: Can't load the configuration of 'gpt2'`** — HF Hub is unreachable. Either fix the network (proxy, VPN, DNS) or pre-seed the HF cache from a different machine and re-run offline with `TRANSFORMERS_OFFLINE=1 HF_HUB_OFFLINE=1`.
2. **`ValueError: output_attentions is not supported when using attn_implementation=sdpa`** — already fixed in this commit (`attn_implementation="eager"` on line ~280 of `pcam_trace_extract.py`). If you see this on a fresh transformers install, the fix regressed and should be re-applied.
3. **Tokenizer errors on non-gpt2 models** — some models require `--trust-remote-code` which the extractor does not expose yet. If you need it, add it at the `from_pretrained` call and re-run; file a follow-up to promote it to a CLI flag.

### C. How to record the results in this file

Both runbooks conclude with a Run log entry below. The entry format is the same for both closures:

```
### YYYY-MM-DD — <short title>

- **engineer:** <name / handle>
- **env:** <OS, Python version, GPU if any, key package versions>
- **deps installed:** <commands you ran to install>
- **closure target:** <vllm | extractor | both>
- **result:** <one-line summary with exact numbers>
- **fixes landed:** <any code changes during the run, or "none">
- **regression result:** `pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q`
  output (N passed, M skipped)
- **Phase 4 closure state:** <updated count: "1 of 2" → "2 of 2", etc.>
```

Commit message (one commit per closure):

```
Phase 4 closure: <target> live-verified on <env>

<one-paragraph summary referencing the Run log entry>
```

Do not squash both closures into the same commit even if one engineer runs both — the audit trail is more valuable when each closure is a separate atomic commit.

---

## D. Phase 5 real-GPU verification (active-mode perf harness)

**Prerequisites**

- A CUDA-capable GPU with ≥ 4 GB VRAM (tested target: any Ampere/Ada/Hopper SKU, or Turing with FP16 fallback)
- NVIDIA driver installed (`nvidia-smi` reports the GPU)
- Network access to `pypi.org` **and** `huggingface.co`
- Linux recommended (vLLM's Windows support is limited)
- The symbolu repo cloned locally

**Step 1: Verify the environment**

```bash
# GPU probe
nvidia-smi | head -20

# CUDA visibility from Python
python3 -c "import torch; assert torch.cuda.is_available(), 'no CUDA'; \
             print('CUDA ok:', torch.cuda.get_device_name(0), '| mem:', \
                   torch.cuda.get_device_properties(0).total_memory // (1024**3), 'GB')"

# HuggingFace Hub reachability (the perf harness downloads a model)
curl -sI https://huggingface.co/facebook/opt-125m/resolve/main/config.json | head -1
# expect: HTTP/1.1 200 OK  or  HTTP/1.1 302 Found
```

If any probe fails, stop — Phase 5 is not closable on this machine.

**Step 2: Install vLLM in a dedicated virtualenv**

vLLM pins specific `torch` and `transformers` versions that conflict with the Phase 4 extractor's stack. Always use a fresh venv per path.

```bash
cd /path/to/symbolu
python3 -m venv .venv-pcam-phase5
source .venv-pcam-phase5/bin/activate
pip install --upgrade pip
pip install vllm

# Sanity: verify the installed vllm has the v1 core surface the bridge targets
python -c "
from vllm.v1.core.block_pool import BlockPool
from vllm.v1.core.kv_cache_utils import FreeKVCacheBlockQueue, KVCacheBlock
import vllm
print('vllm:', vllm.__version__)
print('v1 core: present')
print('FreeKVCacheBlockQueue methods:', [
    m for m in ('popleft_n', 'append', 'append_n', 'remove', 'get_all_free_blocks')
    if hasattr(FreeKVCacheBlockQueue, m)
])
"
```

If any of the `v1.core.block_pool` / `kv_cache_utils` imports fail, you are on an older vLLM release that does not support active mode. Either upgrade vLLM to ≥ 0.7.0 or stay on Phase 4 shadow mode.

**Step 3: Verify the bridge's version check accepts this vLLM**

```bash
python -c "
from benchmarks.vllm_active_bridge import check_vllm_active_mode_supported, VLLMVersionSupportError
try:
    check_vllm_active_mode_supported()
    print('check_vllm_active_mode_supported: PASS')
except VLLMVersionSupportError as e:
    print('check_vllm_active_mode_supported: FAIL —', e)
    raise SystemExit(1)
"
# expect: check_vllm_active_mode_supported: PASS
```

If this fails on a vLLM release whose v1 core import you just verified in Step 2, the method-surface probe inside `check_vllm_active_mode_supported` is rejecting a method the new release renamed. The fix is to update the `_required_queue_methods` tuple in `benchmarks/vllm_active_bridge.py` with the new names. Single-line change; record it in the Run log.

**Step 4: Run the Phase 5 perf harness with a small model and both policies**

```bash
python benchmarks/pcam_vllm_perf.py \
    --model facebook/opt-125m \
    --prompt "Explain PCAM in one sentence." \
    --prompt "Name three cache eviction algorithms." \
    --prompt "Summarize paged attention in one sentence." \
    --max-tokens 32 \
    --max-blocks 4096 \
    --sink-tokens 4 \
    --policy both \
    --json /tmp/pcam_phase5_perf.json
```

Keep the first run small: `facebook/opt-125m` is ~250 MB, three short prompts, 32 max tokens each. Total GPU time should be well under a minute on any modern GPU. Scale up only after this smoke test is green.

**Step 5: Expected output signature**

A clean run prints a `REAL SERVING METRICS` banner followed by two tables:

```
======================================================
  PCAM vLLM Perf — Real Serving Metrics
======================================================
NOTE: REAL SERVING METRICS from vllm.LLM.generate()...

policy   tps     wall_sec  mean_ms  p50_ms  p95_ms  prompt_toks  completion_toks
-------  ------  --------  -------  ------  ------  -----------  ---------------
default  NN.NN   X.XXXX    NNN.NN   NNN.NN  NNN.NN  ~25-40       96
pcam     NN.NN   X.XXXX    NNN.NN   NNN.NN  NNN.NN  ~25-40       96

PCAM throughput delta vs default LRU: +/−X.YZ%

Active-mode bridge stats (pcam run)
metric                value
--------------------  -----
popleft_n_calls       N
blocks_evicted        N
pcam_chosen_blocks    N
lru_fallback_blocks   N
append_events         N
```

And the JSON output at `/tmp/pcam_phase5_perf.json` contains the same data in machine-readable form, with two entries in `results[]` — one for `default` and one for `pcam` — each carrying the full `PolicyRunResult.summary()` shape.

**What to look for in the output:**

- Both policies finish without raising.
- The `pcam` run's `active_mode_stats` has `popleft_n_calls > 0` — confirms PCAM's `popleft_n` replacement was actually called (not bypassed).
- `pcam_chosen_blocks + lru_fallback_blocks = blocks_evicted` — the math adds up.
- The throughput delta line appears. The sign (+/−) is whatever the real measurement says — do NOT edit it to match a preferred narrative.

**Step 6: Common failure modes and the smallest fix for each**

1. **`VLLMBridgeUnavailable: vllm is not installed`** — The pytest wrapper check saw the wrong environment. Verify `which python` and `which pip` point at the venv, then re-run.

2. **`VLLMVersionSupportError: FreeKVCacheBlockQueue is missing methods required by the PCAM active-mode bridge`** — Upstream renamed a method. The error message lists exactly which methods went missing. Update `_required_queue_methods` in `benchmarks/vllm_active_bridge.py`, and correspondingly update the install path's method-hook assignments (`queue.popleft_n`, `queue.append`, `queue.append_n`) if the method names themselves changed.

3. **`VLLMVersionSupportError: Could not locate BlockPool on the vLLM LLM instance. Tried:`** — The `_find_block_pool` helper's candidate-path list doesn't know about your vLLM release's internal layout. Inspect the live engine interactively:

   ```python
   from vllm import LLM
   llm = LLM(model="facebook/opt-125m")
   # Dig for the block pool
   engine = llm.llm_engine
   print(dir(engine))  # look for kv_cache_manager, block_pool, scheduler, etc.
   ```

   Once you find the real path, append it to the `candidate_paths` list in `benchmarks/pcam_vllm_perf.py::_find_block_pool`. One-line change.

4. **Out of GPU memory** — Try `--max-tokens 16` first, or move to an even smaller model (`--model facebook/opt-350m` is sometimes smaller than opt-125m after quantization in certain vllm builds — verify on your hardware).

5. **`RuntimeError: remove() called on an invalid block`** — The bridge's `popleft_n` replacement handed a block to `queue.remove(block)` when the block's `prev_free_block` / `next_free_block` pointers were already `None`. This can happen if vLLM changed when it clears those pointers. Debug by adding a `print(block.block_id, block.prev_free_block, block.next_free_block)` immediately before `queue.remove(block)` and see which call corrupts the pointers.

6. **The `pcam` run finishes but `active_mode_stats["popleft_n_calls"] == 0`** — The monkey-patch didn't take effect for this particular `BlockPool`. Either `_find_block_pool` returned the wrong pool or vLLM created a second pool after install. Verify by printing `id(pool)` at install time and `id(llm.llm_engine.kv_cache_manager.block_pool)` just before generate(). They must match.

7. **The `pcam` throughput is significantly lower than `default`** — This is the known O(num_free_blocks) overhead of the active-mode `popleft_n` replacement. It is not a bug; it is the tradeoff the Phase 5 doc calls out explicitly. Record the overhead number in the Run log. If the overhead is material enough to hurt the acquisition pitch, that is Phase 6 optimization work, not a Phase 5 closure blocker.

**In all cases, debug against the Python reference and the parity harness — never against the report, the test, or the honesty banner.** If the fix is non-trivial (more than ~20 lines), file a follow-up rather than expanding Phase 5 scope inside the closure commit.

**Step 7: Record the result**

Append an entry to the Run log below following the template:

```
### YYYY-MM-DD — Phase 5 closure

- **engineer:** <name/handle>
- **env:** <OS, Python version, GPU model, CUDA version, vllm version>
- **deps installed:** <commands you ran>
- **model:** <model used for the run>
- **prompts:** <count and approximate total tokens>
- **policy:** both
- **result:** <one-line summary with numbers, e.g. "default 45 tps, pcam 41 tps, delta −8.9%">
- **bridge stats:** popleft_n_calls=N, blocks_evicted=N, pcam_chosen=N, lru_fallback=N
- **fixes landed:** <any code changes during the run, or "none">
- **regression:** `pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q` → N passed, M skipped
- **Phase 5 closure state:** CLOSED (first live active-mode run completed)
```

Also update `Project_documentation/repository/benchmarks/PCAM_PHASE5_REPORT.md`:

1. Flip the header status line from "pending one live run" to "CLOSED on YYYY-MM-DD".
2. Add a "Live active-mode serving results" section under "What has actually been measured" with the real throughput table, the delta percentage, and the bridge stats.
3. Keep all the honesty caveats exactly as they are. Do not delete the known-limitation list; those items remain even after the first live run (O(num_free) overhead, block-level-only scoring, single synthetic sequence id, narrow version window).

One commit per closure:

```
Phase 5 closure: first live active-mode vllm run on <env>

<one-paragraph summary referencing the Run log entry>
```

---

## Run log

Append to this section after each closure attempt.

### 2026-04-10 — extractor closed, vllm blocked

- **engineer:** PCAM software-product roadmap closure task
- **env:** sandbox, Linux 6.18.5, Python 3.11.15, no GPU
- **deps installed:** `pip install torch transformers` (2.11.0, 5.5.3)
- **extractor:** ✓ ran live against a local `GPT2LMHeadModel` (35,712 params, random-init, eager attention). 25 TraceEvents emitted, replay round-trip green, compare harness green on real trace.
- **vllm:** ✗ blocked. No CUDA, wheel version conflicts with installed torch, HF Hub proxy-blocked.
- **fixes landed:** `attn_implementation="eager"` added to extractor's `from_pretrained` call (1 line); pytest skipif markers on two now-unreachable fail-clean tests (5 lines); complementary positive test added (1 method).
- **regression result:** `pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q` → 112 passed, 3 skipped, 0 failed.
- **Phase 4 closure state:** 1 of 2 live paths closed. vLLM requires a different environment.

### 2026-04-10 — Phase 5 closure attempt: sandbox-blocked, runbook added

- **engineer:** PCAM software-product roadmap Phase 5 closure task
- **env:** sandbox, Linux 6.18.5, Python 3.11.15, `torch 2.11.0+cu130` (CPU), no CUDA, no `/dev/nvidia*`, no `/proc/driver/nvidia`, `nvidia-smi` not present, `torch.cuda.is_available() == False`
- **vllm:** not installed. Prior session attempts failed: PyJWT system-package conflict on full install; `--no-deps` install imports but is incompatible with the torch version needed by Phase 4's extractor and would fail at `LLM(...)` construction anyway because no CUDA hardware
- **HF Hub:** proxy-blocked (`huggingface.co` → `403 host_not_allowed`)
- **closure target:** `pcam_vllm_perf.py --policy both`
- **result:** ✗ not run. Environmental hard block on all three requirements simultaneously — GPU, vllm install, HF Hub access.
- **verification done in this attempt:**
  - Phase 5 unit tests still green: `pytest simulator/pcam/tests/test_phase5_active_mode.py -q` → 23 passed.
  - Perf harness fail-clean path verified: `python benchmarks/pcam_vllm_perf.py --policy both --prompt "hi" --quiet` → `ERROR: vllm is not installed...`, rc=2, banner and install hint correct.
  - `check_vllm_active_mode_supported()` raises `VLLMVersionSupportError` with the expected actionable message.
  - Full PCAM suite: `pytest simulator/pcam/tests/ simulator/pcam/rtl/tests/ -q` → 239 passed, 3 skipped, 0 failed.
- **fixes landed:** none (no code bugs found — the infrastructure is sound; only the environment is wrong).
- **docs landed:** this entry, plus section **D** above (Phase 5 real-GPU verification runbook) with seven numbered steps covering prerequisites, venv install, version check, harness invocation, expected output signature, common failure modes and their smallest fixes, and the result-recording template.
- **Phase 5 closure state:** LANDED, EXECUTION PENDING on any machine that has a GPU + vllm 0.7.0+ + HF Hub access. See section D above for the copy-pasteable runbook.

*(Next closure attempt: append here.)*
