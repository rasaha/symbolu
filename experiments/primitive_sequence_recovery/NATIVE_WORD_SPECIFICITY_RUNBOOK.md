# RunPod Runbook — Native Sanskrit Word-Specificity Blind Evaluator Run

Execute the frozen v2 study yourself on a GPU pod. Four strictly separated phases: **(1) preflight & hash
verification → (2) response collection (no answer key) → (3) raw-evidence freeze → (4) offline scoring after the
freeze.** Nothing here changes any frozen packet, prompt, mapping, parser, word set, candidate order, or success
criterion.

- Packet freeze commit: **`42f38d57`** · Pre-run audit: **`fc15a0d8`** · Branch: **`claude/symbolu-adversarial-eval-zevb4h`**
- Harness commit: this commit (see final report). All scripts live in `experiments/primitive_sequence_recovery/`.

## 0. Before you start — decisions only you can make

1. **Evaluator models.** Edit `evaluator_manifest.template.yaml` (or `.json`) → save as `evaluator_manifest.yaml`.
   The protocol requires **≥3 blind LLM evaluators from ≥3 distinct families, each disjoint from the paraphrase
   *authoring* family (Anthropic / Claude)**. The template ships confirmed-compatible open families used elsewhere in
   this repo — **Llama, Gemma, Qwen** — as a **starting point you must confirm**; pin each `revision` to a commit SHA.
   No model is chosen for you and none is ever silently substituted.
2. **Backend.** `transformers` (self-contained HF load) or `vllm_openai` (you launch a LOCAL vLLM server and set
   `base_url`). vLLM gives a real per-call socket timeout and faster throughput; Transformers needs no server.
3. **GPU fit.** See §2. 8–9B bf16 fits a single 24 GB card; 14B needs ~40 GB (or `tensor_parallel_size: 2`, or swap to
   a 7B Qwen).

## 1. Detect the pod (paste all three)

```bash
nvidia-smi
python -c "import torch; print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_properties(0).total_memory)"
df -h
```

## 2. VRAM & disk estimates (no assumption about your pod type)

| model size | bf16 weights | practical VRAM (weights+KV, len 4096) | fits |
|---|---|---|---|
| 7–9B | ~14–18 GB | ~20–24 GB | single 24 GB (A10/L4/3090/4090) |
| 12–14B | ~24–28 GB | ~34–40 GB | single A100-40G, or `tensor_parallel_size: 2` on 2×24 GB |

- Run **one model at a time** (sequential); you do not need all three resident at once.
- **Disk:** each model download is ~15–30 GB → budget **≥150 GB** for three models + HF cache. The raw evidence
  itself is tiny (~a few MB). Check with `df -h`; if a download fails with "no space left", delete
  `$HF_HOME/hub/models--*` for a model you've finished.

## 3. Clone / update, environment, dependencies

```bash
# 1. Clone/update
cd /workspace
git clone https://github.com/rasaha/symbolu.git 2>/dev/null || true
cd symbolu
git fetch origin
git checkout claude/symbolu-adversarial-eval-zevb4h
git pull --ff-only

# 2. Confirm commit (must contain 42f38d57 and fc15a0d8 in history)
git rev-parse HEAD

# 3. Environment
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r experiments/primitive_sequence_recovery/native_ws_requirements.txt

# 4. Caches (keep big downloads on the pod volume) + HF auth for gated models (Llama/Gemma are gated)
export HF_HOME=/workspace/hf_cache
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
mkdir -p $HF_HOME
huggingface-cli login        # paste a token that has ACCEPTED the license for each gated model, or:
# export HF_TOKEN=hf_xxx

# 5. Prepare your manifest (edit models/revisions/backend, then save as evaluator_manifest.yaml)
cd experiments/primitive_sequence_recovery
cp evaluator_manifest.template.yaml evaluator_manifest.yaml
# ... edit evaluator_manifest.yaml ...
```

## 4. Preflight (zero model calls; aborts nonzero on any failure)

```bash
python run_native_word_specificity_preflight.py \
  --expected-packet-commit 42f38d57 \
  --expected-audit-commit fc15a0d8 \
  --manifest evaluator_manifest.yaml \
  --output-root native_ws_raw_evidence
```
Proceed only if `"all_pass": true`.

## 5. Freeze presentation orders (per-evaluator, deterministic; zero model calls)

```bash
python build_native_word_specificity_presentation_orders.py \
  --manifest evaluator_manifest.yaml \
  --output-dir native_ws_presentation_orders
```

## 6. Dry run per evaluator (loads the model; writes to a NON-evidence dir)

```bash
python run_native_word_specificity_evaluators.py \
  --manifest evaluator_manifest.yaml --evaluator-id eval_1 \
  --presentation-order native_ws_presentation_orders/eval_1_order.json \
  --output-dir native_ws_raw_evidence/eval_1 --dry-run --dry-run-n 5
# confirm parsed_ok == dry_run_n and the output landed in ..._eval_1__DRYRUN_NONEVIDENCE (NOT the official dir)
```

## 7. Official response collection — one evaluator at a time (resumable)

```bash
python run_native_word_specificity_evaluators.py \
  --manifest evaluator_manifest.yaml --evaluator-id eval_1 \
  --presentation-order native_ws_presentation_orders/eval_1_order.json \
  --output-dir native_ws_raw_evidence/eval_1
# ... repeat for eval_2, eval_3 (and eval_4 if you added it). If a pod restarts, re-run the SAME command
# with --resume appended; completed trials are skipped, none duplicated.
```
Each writes `native_ws_raw_evidence/<id>/responses.jsonl` (incremental, fsync'd) + `run_manifest.json` (resolved
model id/revision/config). The runner never computes accuracy and never loads the answer key.

## 8. Freeze the raw evidence (no model calls; no key)

```bash
python freeze_native_word_specificity_raw_evidence.py \
  --evidence-root native_ws_raw_evidence \
  --manifest evaluator_manifest.yaml
# writes native_ws_raw_evidence/raw_evidence_freeze.json ; proceed only if "frozen": true and >=3 distinct families
```

## 9. Commit the raw evidence (preserve outputs if the pod stops)

```bash
cd /workspace/symbolu
git add experiments/primitive_sequence_recovery/native_ws_raw_evidence \
        experiments/primitive_sequence_recovery/native_ws_presentation_orders
git commit -m "Freeze native Sanskrit word-specificity raw evaluator evidence"
git push -u origin claude/symbolu-adversarial-eval-zevb4h
```

## 10. Score — ONLY after the raw freeze (verifies hashes, then loads the key)

```bash
cd experiments/primitive_sequence_recovery
python score_native_word_specificity.py \
  --evidence-root native_ws_raw_evidence \
  --out native_ws_analysis/native_word_specificity_analysis.json
```
It re-verifies every freeze hash **before** touching the answer key, then computes the frozen primary contrast
(BCa 95% CI + permutation), per-arm Clopper–Pearson CIs, per-family direction, the precommitted flagged-word
sensitivity analysis, position/shortcut diagnostics, and the frozen outcome taxonomy.

## 11. Commit the analysis

```bash
cd /workspace/symbolu
git add experiments/primitive_sequence_recovery/native_ws_analysis
git commit -m "Analyze native Sanskrit word-specificity evaluator run"
git push
```

## Model-loading robustness (backend: transformers)

Supports bf16/fp16 (`dtype`), `trust_remote_code`, `device_map="auto"`, and `tensor_parallel_size` (via
`device_map` sharding across visible GPUs). An **OOM is an explicit abort** (`ModelAbort`) — the runner never
downgrades to a different model. Resolved model id + commit revision are recorded in every record and in
`run_manifest.json`. For a **strict per-call timeout**, prefer `backend: vllm_openai`: launch a LOCAL server, e.g.

```bash
python -m vllm.entrypoints.openai.api_server --model <id> --dtype bfloat16 \
  --tensor-parallel-size 1 --max-model-len 4096 --port 8000    # set base_url: http://127.0.0.1:8000 in the manifest
```

## Output directory schema

```
native_ws_presentation_orders/
  <eval_id>_order.json                # {evaluator_id, seed, n_items, order:[trial_id,...]}
  presentation_orders_index.json      # per-evaluator seed + sha256
native_ws_raw_evidence/
  <eval_id>/
    responses.jsonl                   # one record/line: trial_id, evaluator_id, model_id, model_revision,
                                       #   prompt_sha256, status(answered|invalid|missing), parsed_choice,
                                       #   attempts, raw_responses[], errors[], latency_s
    run_manifest.json                 # resolved model id/revision + runtime config + operational counts (no accuracy)
  <eval_id>__DRYRUN_NONEVIDENCE/      # dry-run only; NEVER scored
  raw_evidence_freeze.json            # completeness + per-evaluator canonical sha256 + combined hash + FROZEN flag
native_ws_analysis/
  native_word_specificity_analysis.json   # primary/secondary/flagged/diagnostics/outcome taxonomy
```

## Guardrails baked into the harness

Collector loads **only** `evaluator_facing/trials.json` and never references the answer key; the answer key is read
**only** by the scorer, **after** the freeze hashes verify; scoring **refuses** to run without a valid freeze; the
official evidence dir refuses overwrite unless `--resume`; dry-run output is a separate non-evidence dir; writes are
atomic + fsync'd for restart safety. No accuracy is ever computed during collection.
