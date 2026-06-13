# SAW-INT4 vs int4_protected — Qwen Head-to-Head (RESULTS)

**Status: NOT YET RUN — template to fill on the GPU pod.** Applies
`docs/KV_COMPRESSION_HEADTOHEAD_PROTOCOL.md`. No positioning language until measured.

## Provenance (verified from the repo, 2026-06-13)
- **SAW-INT4 repo:** `github.com/togethercomputer/saw-int4`
- **Commit:** `e51bfa7291d52cd14b86e4c6ded6c002d0444ff0`
- **BDR submodule:** `third_party/sglang-fast-rotation` → `github.com/jindajia/sglang-fork.git` branch `colm_rotation_fast` (pins in `SUBMODULE_VERSIONS.md`)
- **Method:** block-diagonal Hadamard rotation (BDR) on K + token-wise INT4, fused into SGLang.
- **Hardware (fill):** ______  • **GPU (fill):** ______  • **Date (fill):** ______

## ⚠️ Integration reality (decides the comparison shape)
- SAW-INT4 = **SGLang server** (`--kv-cache-dtype int4` + `HADAMARD=1`); accuracy via **GPQA / simple-evals**, throughput via **genai-bench**. Requirements: **MHA models only** (not MLA), prefill `fa3`, decode `triton`.
- int4_protected/KVPro = **vLLM/HF**, eval = needle/PPL/greedy.
- **No common harness.** Apples-to-apples ⇒ run a **shared metric (GPQA via simple-evals)** against **both** servers on the **same model**, plus measure memory + throughput on each.
- **Model note:** requested `Qwen/Qwen2.5-7B-Instruct` (GQA/MHA — should satisfy SAW's MHA requirement). SAW *tested* `Qwen3-4B-Thinking-2507` / `Qwen3-8B`. **Smoke-test on SAW's own model first** to confirm the kernel path, then switch to Qwen2.5-7B-Instruct for the comparison.

## Exact commands (run on the pod)

### 1. Clone + submodule
```bash
cd /workspace
git clone --recurse-submodules https://github.com/togethercomputer/saw-int4.git
cd saw-int4 && git rev-parse HEAD                 # expect e51bfa72…
git submodule update --init third_party/sglang-fast-rotation
```
### 2. Install BDR (SGLang fork)
```bash
cd third_party/sglang-fast-rotation/python
pip install -e ".[all]"
pip install --no-build-isolation "git+https://github.com/Dao-AILab/fast-hadamard-transform.git"
```
### 3. Smoke test — confirm the CUDA/kernel path (SAW's OWN model first)
```bash
# terminal 1 — BDR server
HADAMARD=1 HADAMARD_ORDER=128 python -m sglang.launch_server \
  --prefill-attention-backend fa3 --decode-attention-backend triton \
  --model-path "Qwen/Qwen3-4B-Thinking-2507" --port 30000 --kv-cache-dtype int4
# terminal 2 — smoke
pip install openai
python scripts/bdr_smoke_test.py --port 30000 --model "Qwen/Qwen3-4B-Thinking-2507"
```
**Record: did the BDR server start + smoke test return a coherent answer? (Y/N + error if N).**

### 4. Accuracy on Qwen2.5-7B-Instruct (BF16 / INT4 / BDR) via GPQA
```bash
git submodule update --init --checkout third_party/simple-evals
cd third_party/simple-evals && mkdir -p simple_evals && touch simple_evals/__init__.py
pip install openai pandas requests jinja2 tqdm numpy
# add a model alias for qwen2.5-7b in simple_evals.py (model="Qwen/Qwen2.5-7B-Instruct", max_tokens=32768)
# then, per mode (restart server with the right env + --kv-cache-dtype), point client at the port:
export OPENAI_BASE_URL="http://127.0.0.1:30000/v1"; export OPENAI_API_KEY="dummy"
python -m simple-evals.simple_evals --model qwen25_7b --eval gpqa --n-repeats 3
```
Server modes to sweep (restart between):  BF16 `HADAMARD=0 --kv-cache-dtype auto` | INT4 `HADAMARD=0 --kv-cache-dtype int4` | BDR `HADAMARD=1 ROTATE_V=0 HADAMARD_ORDER=128 --kv-cache-dtype int4`.

### 5. int4_protected on the SAME model + SAME GPQA
Run the int4_protected/KVPro vLLM server on `Qwen/Qwen2.5-7B-Instruct`, expose its OpenAI endpoint, and run the *same* `simple-evals gpqa --n-repeats 3` against it. (Plus its existing needle/greedy/PPL numbers for reference.)

### 6. Throughput + memory (each method, same client)
```bash
pip install genai-bench
genai-bench benchmark --api-backend sglang --api-base "http://127.0.0.1:30000" --api-key dummy \
  --api-model-name "Qwen/Qwen2.5-7B-Instruct" --model-tokenizer "Qwen/Qwen2.5-7B-Instruct" \
  --task text-to-text --traffic-scenario "D(256,1024)" --num-concurrency 32 \
  --max-time-per-run 5 --max-requests-per-run 256 --server-engine SGLang --server-gpu-count 1
```
Memory: record **measured** KV bytes/token incl. scales/metadata/padding/sidecars/temp buffers for each method (don't use paper ratios).

## Results table (fill)
Model: `Qwen/Qwen2.5-7B-Instruct` • GPU: ______ • context: ______

| method | GPQA (shared) | hard-needle | needle | greedy-agree vs bf16 | PPL | **bytes/token (measured)** | tokens/sec | p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| bf16 | | | | 1.000 | | | | |
| int4 (naive) | | | | | | | | |
| int4_protected / KVPro | | | | | | | | |
| SAW-INT4 (BDR) | | | | | | | | |

*SAW published reference (Qwen3-4B, not our model): BF16 GPQA 66.7 / INT4 0 / BDR 65.8; BDR tps ≈ INT4 ≈ BF16.*

## Decision outcome
**[ NOT YET RUN ]** — set one of, per protocol §make-or-break:
- **BUILD-FAILED** — SAW kernel/build/smoke did not work on the pod (attach error).
- **DOMINATED** — SAW-INT4 matches int4_protected quality (hard-needle within 2 pts / greedy within 1 pt / GPQA within noise) at **≤ memory and ≥ throughput** → int4_protected not a defensible format → pivot.
- **QUALITY-EDGE** — int4_protected beats SAW on hard-tail by **≥5 pts** (or SAW shows a quality cliff) → reposition claim to tail-quality, state the memory trade.
- **PARITY** — mixed → differentiate on integration/warm-tier.

## Next recommendation
**[ fill after measuring ]** — e.g. "DOMINATED → draft pivot to warm-tier systems story" or
"QUALITY-EDGE on hard-needle → that becomes the claim; verify on Mistral/Llama next; then GEAR."
Do NOT integrate GEAR until this SAW result is recorded.
