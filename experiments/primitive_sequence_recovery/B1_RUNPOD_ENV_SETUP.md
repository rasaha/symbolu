# B1 RunPod Environment Setup

Seamless environment setup for running the **frozen B0 evaluation** (`run_b1_generation.py`) on a
fresh RunPod session. Captures the exact known-good stack so the next pod is one command, not the
dependency whack-a-mole we hit the first time.

**Not a frozen B0 artifact.** This document/scripts do not run a model, generate, score, or unblock
Track B. `torch`/`torchvision`/`torchaudio`/`accelerate`/`nltk` are **not** locked fields;
`transformers 5.13.0` and `tokenizers 0.22.2` **are** (they must match `TRACK_B_RUNTIME_MODEL_LOCK.yaml`).

---

## TL;DR — one command

```bash
cd "$(git rev-parse --show-toplevel)"          # repo root (NOT a nested subdir)
bash experiments/primitive_sequence_recovery/setup_b1_runpod.sh
```

It installs the matched torch trio + locked backend + companions + cmudict, verifies `cuda True`,
and runs the runner's frozen-integrity gate. Then run the smoke (see bottom).

---

## What the environment needs

| Component | Version | Locked? | Why |
|---|---|---|---|
| `torch` | `2.8.0+cu128` | no | must match the pod driver's CUDA (see below) |
| `torchvision` | `0.23.0+cu128` | no | transformers eagerly imports it at model-load |
| `torchaudio` | `2.8.0+cu128` | no | transformers imports it via `loss_rnnt` at model-load |
| `transformers` | `5.13.0` | **yes** | locked backend |
| `tokenizers` | `0.22.2` | **yes** | locked backend |
| `accelerate` | latest | no | required by `device_map="auto"` |
| `nltk` + `cmudict` corpus | latest | no | **true G2P** for conditioning (ARPAbet→varṇa); hard-abort if missing |
| `pyyaml` | latest | no | runner reads the YAML runtime lock |
| `huggingface_hub` | latest | no | model resolution/download |

The two locked models (auto-downloaded by transformers at their locked revisions):
- `mistralai/Mistral-7B-Instruct-v0.3` @ `c170c708c41dac9275d15a8fff4eca08d52bab71`
- `Qwen/Qwen2.5-7B-Instruct` @ `a09a35458c702b33eeacc393d103063234e8bc28`

---

## Manual steps (if you don't use the script)

```bash
# 1. matched torch trio — pick cuXXX to match the pod driver (see "Driver matching")
pip install --index-url https://download.pytorch.org/whl/cu128 \
    torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0

# 2. locked backend + companions
pip install -r experiments/primitive_sequence_recovery/b1_runpod_requirements.txt

# 3. cmudict corpus for true G2P
python3 -c "import nltk; nltk.download('cmudict'); from nltk.corpus import cmudict; cmudict.dict(); print('cmudict ok')"

# 4. verify
python3 -c "import torch,torchvision,torchaudio,transformers,tokenizers,accelerate; \
print('torch',torch.__version__,'| cuda',torch.cuda.is_available(),'| transformers',transformers.__version__,'| tokenizers',tokenizers.__version__)"
# want: cuda True | transformers 5.13.0 | tokenizers 0.22.2
```

---

## Driver matching (the thing that bit us)

`torch` must be built for a CUDA version **≤** the pod driver's max. Check it:

```bash
nvidia-smi | sed -n '3p'      # -> "... CUDA Version: 12.8"
```

| Driver "CUDA Version" | Use torch wheel index | `CU=` for the script |
|---|---|---|
| 12.8 (e.g. NVIDIA 570.x) | `cu128` (**default**) | `CU=cu128` |
| 12.4–12.6 | `cu124` / `cu126` | `CU=cu124` |
| 13.0+ | `cu130` | `CU=cu130` |

All **three** torch packages must be the **same** `cuXXX` build. A mismatch is what produced
`operator torchvision::nms does not exist` and `libcudart.so.13: cannot open shared object file`.

---

## Known pitfalls

1. **Wrong directory.** Always `cd "$(git rev-parse --show-toplevel)"`. The repo root is the git
   toplevel; a nested `symbolu/symbolu` subdir will make relative paths (and the runner) "not found."
2. **`pip install vllm` breaks CUDA.** vLLM drags `torch` back to `cu130`, which fails on a 12.8
   driver (`cuda False`). Do **not** install vLLM in this env — the runner only needs `transformers`.
   If you want vLLM, isolate it in its own venv.
3. **Missing `nltk`/`cmudict` → hard abort.** Conditioning uses true G2P and refuses to run without it
   (`G2P_UNAVAILABLE → ABORT`). That is intentional (no romanized fallback). Install nltk + cmudict.
4. **`accelerate` missing → `device_map` ValueError.** Install `accelerate`.

---

## Run

```bash
cd "$(git rev-parse --show-toplevel)"

# smoke (3 rows) — proves models load, G2P works, chat-template path is sane
python3 experiments/primitive_sequence_recovery/run_b1_generation.py --limit 3 --out /tmp/b1_smoke.jsonl
cat /tmp/b1_smoke.jsonl

# full frozen run (3,600 rows), resumable
python3 experiments/primitive_sequence_recovery/run_b1_generation.py \
    --out experiments/primitive_sequence_recovery/b1_raw_outputs.jsonl --resume
```

The runner re-verifies all 11 frozen hashes before loading anything (aborts `INVALID_POSTHOC` on any
mismatch), requires `cuda True` and `transformers==5.13.0`, and writes **raw outputs only** — no
scoring, no packets, no verdict. `B0 FROZEN · Track B BLOCKED` until a separate scoring gate.
