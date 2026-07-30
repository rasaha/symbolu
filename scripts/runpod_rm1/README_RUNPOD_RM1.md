# RM1 on RunPod — execution package

These scripts run the **existing, frozen** RM1 real-model harness
(`experiments/hybrid_token_event_attention/real_model/`) on a **CUDA GPU** RunPod machine. They do
**not** modify the harness, the controlled experiment code, the canonical result JSON, the existing
RM1 reports, the event models, TAP, Decision Governance, or ActionGate. They only provision the pod,
run the harness against an actual open-weight model, verify the run, and package the results.

> The harness itself decides whether a real model executed. If a real model cannot be loaded it emits
> `RESOURCE_BLOCKED` and these scripts fail the run (they never accept a MOCK result as evidence).

## Persistent layout (all under `/workspace`)

| purpose | path |
|---|---|
| repository | `/workspace/ugence` |
| output root | `/workspace/ugence_rm1` |
| virtualenv | `/workspace/ugence_rm1/venv` |
| HF cache | `/workspace/ugence_rm1/cache/huggingface` |
| logs | `/workspace/ugence_rm1/logs` |
| results | `/workspace/ugence_rm1/results` |
| packages | `/workspace/ugence_rm1/packages` |

Nothing durable is written under `/tmp`.

## Files

| script | role |
|---|---|
| `common.sh` | shared config, defaults, directory contract, helpers (sourced) |
| `bootstrap_runpod.sh` | validate env, record hardware, clone/update repo, build venv, install deps, verify imports + CUDA, run the 27 tests, check the canonical hash, write the runtime manifest (no experiment) |
| `run_rm1_smoke.sh` | two actual-model smoke runs (seeds `RM1_SEED`, `RM1_SECOND_SEED`), each hard-verified |
| `run_rm1_full.sh` | the full held-out run (only after smokes verify); `results/full_<UTC>` + `latest_full` symlink |
| `verify_rm1_results.sh` | Python-based inspection + acceptance scorecard (MET / NOT MET / NOT MEASURABLE) |
| `package_rm1_results.sh` | timestamped `.tar.gz` of results/logs/manifests + `SHA256SUMS` |
| `run_all_rm1.sh` | the single command: bootstrap → smoke → verify → full → verify → package |
| `resume_rm1.sh` | resume after interruption (skips completed stages) |
| `env.example` | template environment file (copy to `env.local`; git-ignored) |

## Required / optional environment variables

**Required:** `UGENCE_REAL_MODEL_ID` (a Hugging Face repo id or a local model directory). There is
**no fake default model** — the scripts refuse to run without it.

**Recommended:** `UGENCE_MODEL_REVISION` (pin an exact commit sha for reproducibility).

**Auth:** `HF_TOKEN` — only for gated models. It is passed to the harness through the environment and
is **never echoed, logged, or packaged**; the verifier and packager actively scan for and redact any
token leakage.

**Repo/branch:** `UGENCE_REPO_URL` (needed for the first clone), `UGENCE_REPO_DIR`
(default `/workspace/ugence`), `UGENCE_BRANCH` (default
`claude/rm1-real-model-validation-yfn2gx`).

**Run knobs (defaults):** `RM1_OUTPUT_ROOT=/workspace/ugence_rm1`, `RM1_DEVICE=cuda`,
`RM1_DTYPE=auto`, `RM1_LOAD_IN_4BIT=0`, `RM1_MAX_INPUT_TOKENS=4096`, `RM1_MAX_NEW_TOKENS=512`,
`RM1_SMOKE_LIMIT=10`, `RM1_SEED=101`, `RM1_SECOND_SEED=202`, `RM1_CLARIFICATION_LIMIT=1`,
`RM1_FULL_LIMIT` (unset → full held-out set).

## Step-by-step on RunPod

1. **Create a CUDA GPU pod** (for a 7B model: ≥ 16 GB VRAM for bf16/fp16, or use 4-bit for ~6 GB).
2. **Attach persistent storage at `/workspace`.**
3. **Open the web terminal.**
4. **Clone the repository** (first time only):
   ```bash
   git clone <repository-url> /workspace/ugence
   ```
5. **Checkout the RM1 branch:**
   ```bash
   git -C /workspace/ugence checkout claude/rm1-real-model-validation-yfn2gx
   ```
   (`bootstrap_runpod.sh` also does this; the manual step just lets you reach the scripts.)
6. **Copy the env template to a non-committed file and edit it:**
   ```bash
   cp /workspace/ugence/scripts/runpod_rm1/env.example /workspace/ugence/scripts/runpod_rm1/env.local
   ```
7. **Set the model id, revision and optional token** in `env.local`:
   ```bash
   export UGENCE_REPO_URL="<repository-url>"
   export UGENCE_REAL_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
   export UGENCE_MODEL_REVISION="<commit-sha>"
   export HF_TOKEN="<token-if-gated>"     # only if required
   ```
8. **Run everything** (foreground):
   ```bash
   bash /workspace/ugence/scripts/runpod_rm1/run_all_rm1.sh
   ```
   or **detached** (survives a closed terminal):
   ```bash
   nohup bash /workspace/ugence/scripts/runpod_rm1/run_all_rm1.sh \
     > /workspace/ugence_rm1/logs/run_all.nohup.log 2>&1 &
   ```
9. **Monitor logs:**
   ```bash
   tail -f /workspace/ugence_rm1/logs/run_all.nohup.log
   ```
10. **Resume after an interruption** (skips completed smoke/full, never overwrites a completed full):
    ```bash
    bash /workspace/ugence/scripts/runpod_rm1/resume_rm1.sh
    # or re-run everything; completed stages are skipped:
    bash /workspace/ugence/scripts/runpod_rm1/run_all_rm1.sh
    # to force fresh runs:
    bash /workspace/ugence/scripts/runpod_rm1/run_all_rm1.sh --force
    ```
11. **Locate results:**
    - per-run dirs: `/workspace/ugence_rm1/results/smoke_seed_*`, `/workspace/ugence_rm1/results/full_*`
    - newest full run: `/workspace/ugence_rm1/results/latest_full`
    - each dir holds `REAL_MODEL_RESULTS.json`, `REAL_MODEL_TRACES.jsonl`,
      `REAL_MODEL_VALIDATION_REPORT.md`, `RESOURCE_MANIFEST.json`, `QUARANTINE.jsonl`,
      `rm1_scorecard.{json,txt}`, `rm1_failure_taxonomy.json`.
12. **Package results** (also done by `run_all_rm1.sh`):
    ```bash
    bash /workspace/ugence/scripts/runpod_rm1/package_rm1_results.sh
    # -> /workspace/ugence_rm1/packages/rm1_results_<UTC>.tar.gz (+ .sha256)
    ```
13. **Shut down the pod** once the archive is downloaded.

## Execution modes

### Non-quantized (default, recommended)

Full-precision weights on the GPU (`RM1_DTYPE=auto` picks bf16 when the device supports it, else
fp16):

```bash
export RM1_LOAD_IN_4BIT=0
export RM1_DTYPE=auto
bash scripts/runpod_rm1/run_all_rm1.sh
```

### Explicit 4-bit (opt-in only)

4-bit is **never** selected silently. Request it explicitly; `bitsandbytes` is then installed by
bootstrap and the harness loads the model in 4-bit **only on CUDA**:

```bash
export RM1_LOAD_IN_4BIT=1
bash scripts/runpod_rm1/run_all_rm1.sh
```

Trade-off: 4-bit cuts VRAM (~6 GB for a 7B model) at some quality cost. Use it when VRAM is tight;
prefer the non-quantized path when the GPU can hold the full-precision weights.

## What "verified" means

A run passes only if the harness reports `actual_model_execution = VERIFIED`, the backend is **not**
MOCK, the requested model id matches, and proof-of-execution (model class, revision, parameter count,
logits shape, generated token ids, device, dtype) is recorded — with a CUDA device on
`RM1_DEVICE=cuda`. The verifier additionally confirms the frozen canonical hash is unchanged, all
JSON parses, the trace JSONL is non-empty and valid, no token leaked, and no MOCK result is treated
as scientific evidence. Pre-registered acceptance criteria are printed as `MET` / `NOT MET` /
`NOT MEASURABLE`; a `NOT MET` criterion is a scientific outcome and does not fail the pipeline, but
any integrity/validity violation does.

## Scope

RM1 tests an actual frozen token-language model inside the external governed dual-domain
architecture. It does not validate FSCS, model-weight adaptation, production deployment, or universal
superiority of event attention.
