# SAW-INT4 vs int4_protected — Qwen Head-to-Head (RESULTS)

**Status: MEASURED — QUALITY-EDGE (2026-06-13).** SAW-INT4/BDR **does not generalize
to Qwen2.5-7B-Instruct** (collapses to 0% retrieval) although it works on the Qwen3
model SAW tuned. int4_protected re-measurement on this harness pending (see §Open item).
Applies `docs/KV_COMPRESSION_HEADTOHEAD_PROTOCOL.md`.

## TL;DR (measured this session, A100-80GB, SGLang fork, seed 0)
| model | mode | needle | hard-needle | provenance |
|---|---|---|---|---|
| Qwen2.5-7B-Instruct | **BF16** | **1.000** | **1.000** | measured, 40 prompts, ctx≈120 sent. |
| Qwen2.5-7B-Instruct | naive INT4 | **0.000** | **0.000** | measured, 10 prompts, ctx=4 — multilingual word-salad |
| Qwen2.5-7B-Instruct | **SAW-INT4 (BDR)** | **0.000** | **0.000** | measured, 40@ctx≈120 **and** 5+5@ctx=4 — digit-repetition garbage |
| Qwen3-4B-Thinking-2507 (SAW's own) | SAW-INT4 (BDR) | **1.000** | **1.000** | measured CONTROL — validates harness + fork path |

- **The collapse is real, not a harness artifact:** identical prompts/seed/client give BF16
  1.000 and the Qwen3-4B BDR control 1.000. Only INT4-KV on Qwen2.5-7B fails.
- **BDR is engaging, not silently falling back to naive:** its failure signature (digit
  repetition) differs from naive INT4's (foreign-word salad, e.g. `pérdida`/`若您`). The
  rotation runs; it just doesn't rescue this model.
- **Decision rule → QUALITY-EDGE (scoped to Qwen2.5-7B):** SAW exhibits a total quality
  cliff (1.0→0.0) on this model that BF16 handles perfectly. SAW's ~2× density advantage is
  moot where it returns garbage. This proves **model-transfer fragility**, NOT broad
  superiority — the edge is "wins where cheap rotation fails," and the breadth of that set is
  **unproven** (n=1). (Was the make-or-break test for int4_protected as a format.)

### ⚠️ Honest caveats
- **Launch recipe:** used `HADAMARD=1 HADAMARD_ORDER=128` (head_dim=128), the **same flags
  that work on Qwen3-4B**. If SAW ships a Qwen2.5-specific rotation config we didn't find,
  that could change the result — but out-of-the-box with their documented Qwen3 recipe, BDR
  does not transfer. Hadamard is parameter-free (no calibration), so there is no obvious
  per-model tuning knob we skipped.
- **int4_protected not yet re-measured on THIS harness/model** (see §Open item). Its
  near-bf16 quality is from prior CTM_plus/Bench validation (needle 15/15, greedy
  bit-identical on the portfolio models). The QUALITY-EDGE claim rests on (a) SAW's measured
  collapse here + (b) int4_protected's prior validation; closing (b) on Qwen2.5-7B with this
  client makes the table fully symmetric.

## Provenance (verified from the repo, 2026-06-13)
- **SAW-INT4 repo:** `github.com/togethercomputer/saw-int4`
- **Commit:** `e51bfa7291d52cd14b86e4c6ded6c002d0444ff0`
- **BDR submodule:** `third_party/sglang-fast-rotation` → `github.com/jindajia/sglang-fork.git` branch `colm_rotation_fast` (pins in `SUBMODULE_VERSIONS.md`)
- **Method:** block-diagonal Hadamard rotation (BDR) on K + token-wise INT4, fused into SGLang.
- **GPU:** 1× NVIDIA A100-SXM4-80GB • **Driver:** 550.127.05 • **CUDA:** 12.4 • **Date:** 2026-06-13

## Build + smoke (DONE)
- Build: `pip install -e ".[all]"` + fast-hadamard-transform — **OK**.
- BDR server launched on `Qwen/Qwen3-4B-Thinking-2507` (`HADAMARD=1 HADAMARD_ORDER=128`,
  `--kv-cache-dtype int4`, prefill fa3 / decode triton). KV pool: **51.5 GB** (K 25.78 + V 25.78,
  1.50M tokens) → INT4 KV ≈ 34 KB/token across all layers.
- `scripts/bdr_smoke_test.py`: **PASS** — coherent CoT, correct GPQA answer **A** (vs plain INT4's
  known collapse → confirms BDR active, not naive INT4). CUDA/kernel path **works**.
- **Note:** server reserves ~72/82 GB (SGLang KV pool) at 0% util when idle — by design; must
  stop it before launching int4_protected on the same GPU (run methods sequentially).

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

## Results table (measured 2026-06-13)
GPU: 1× A100-SXM4-80GB • SGLang fork `colm_rotation_fast` • client: `ndol.experiments.openai_kv_eval` (temp 0, seed 0)

| model | method | needle | hard-needle | n prompts / ctx | notes |
|---|---|---|---|---|---|
| Qwen2.5-7B-Instruct | bf16 | **1.000** | **1.000** | 40 / ~120 sent | clean exact answers |
| Qwen2.5-7B-Instruct | int4 (naive) | **0.000** | **0.000** | 10 / 4 sent | word-salad collapse (`pérdida`,`若您`) |
| Qwen2.5-7B-Instruct | SAW-INT4 (BDR) | **0.000** | **0.000** | 40 / ~120 **+** 5+5 / 4 sent | digit-repetition garbage; rotation active |
| Qwen2.5-7B-Instruct | int4_protected / KVPro | _pending_ | _pending_ | — | re-measure on this client (Open item) |
| Qwen3-4B-Thinking-2507 | SAW-INT4 (BDR) | **1.000** | **1.000** | 5+5 / 4 sent (max_tok 1024) | CONTROL — harness + fork path valid |

Run artifacts on pod: `/workspace/run_bf16.jsonl`, `run_int4.jsonl`, `run_bdr.jsonl`,
`run_bdr_short.jsonl`, `run_bdr_qwen3.jsonl`.

*SAW published reference (Qwen3-4B, not Qwen2.5-7B): BF16 GPQA 66.7 / INT4 0 / BDR 65.8 — consistent
with our Qwen3-4B BDR control working; the new datum is that this does NOT transfer to Qwen2.5-7B.*

## Decision outcome
**QUALITY-EDGE (with caveat).** SAW-INT4/BDR shows a **total quality cliff on Qwen2.5-7B-Instruct**
(needle 1.0→0.0) that BF16 does not, on a model int4_protected is validated to handle. Per protocol
§make-or-break, "SAW shows a quality cliff int4_protected doesn't" ⇒ QUALITY-EDGE. NOT DOMINATED
(SAW does not match quality on this model), NOT BUILD-FAILED (build/smoke + Qwen3-4B control all pass).

**Defensible claim (scoped to what is measured):** *int4_protected delivers a quality-safe 1.8× KV
reduction that survived a hard failure case for cheap rotation-only INT4 — Qwen2.5-7B hard-needle
retrieval collapsed to 0% under SAW-BDR while BF16 and (per prior validation) int4_protected retained
retrieval.* Do **not** claim "across mainstream models" until the Mistral/Llama replication runs —
this is n=1. Do **not** claim "SAW can't enter vLLM/LMCache"; correct wording is "SAW is
SGLang-oriented; LMCache/vLLM warm-tier compatibility is unproven for it."

## Open item (to make the table fully symmetric)
Run int4_protected's vLLM server on `Qwen/Qwen2.5-7B-Instruct`, expose its OpenAI endpoint, and run
the **same** client (`openai_kv_eval run --label int4_protected --seed 0`) + `compare --ref bf16`.
Expected (per prior validation): needle/hard ≈ bf16. That closes caveat (b) and confirms int4_protected
holds where SAW collapses.

## Next recommendation — reordered (the next risk is no longer "SAW beat us")
With QUALITY-EDGE banked on Qwen2.5-7B, the live risks to the thesis are: (a) is the SAW failure
**broad or Qwen2.5-specific?** (b) does **CacheGen** already own the warm-tier niche? (c) does
int4_protected hold **throughput/p99** in paged serving? Priority stack:

1. **Breadth test — SAW on one non-Qwen3 mainstream model** (Mistral-7B-Instruct or
   Llama-3.1-8B-Instruct), same hard/normal-needle harness. Broad collapse ⇒ "cheap rotation-only
   INT4 has broad transfer cliffs" (strong). Works there ⇒ moat is Qwen2.5-style-specific (narrow).
   Both outcomes are decision-useful. Cheap, highest information — do FIRST.
2. **int4_protected vs CacheGen inside LMCache/vLLM** — the REAL warm-tier incumbent (LMCache's own
   KV→bitstream codec for offload/reuse), not SAW. Long-prefix reuse workload; measure bytes stored,
   TTFT-with-reuse, NVMe/PCIe transfer volume, p95/p99 under concurrency, cost/repeated-query;
   quality only as a sanity check. This is the comparison that decides whether the warm-tier claim
   is real.
3. **int4_protected decode throughput/p99 in a paged/fused stack** (bf16 vs naive int4 vs
   int4_protected) — the unmeasured axis it could still lose on; SAW is paged+fused-native.
4. **Close the symmetry gap** — int4_protected vLLM on Qwen2.5-7B via the same client (`--label
   int4_protected --seed 0`) + `compare --ref bf16`.
5. **THEN GEAR.** Do NOT integrate GEAR until 1–2 are recorded.

**Reframe Test B (warm-tier reuse) as a SYSTEMS benchmark, not a quality re-test:** for a fixed codec,
store→NVMe→reload is byte round-tripping — quality after reload ≈ quality without it (already covered
by the needle test, since the needle lives in the reused prefix). The real metrics are bytes /
transfer / TTFT / p99 / cost; quality is a sanity check guarding against dtype/chunking/partial-load
bugs in the storage path.
