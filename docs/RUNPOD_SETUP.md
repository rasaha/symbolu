# RunPod setup — CSR Phase 2B real-Mistral run (reproducible)

One-command env so a fresh pod can produce a **`production_valid=True`** Phase 2B-v2 trace
(`robustness_eval_v2.json`), the input for P-B and Phase 4 work.

## Base image assumptions
- A **RunPod "PyTorch 2.x / CUDA 12.1" template** is strongly preferred — `torch` + GPU work out of the
  box and you only add the text libs. A bare Ubuntu/Python image works too but you must install a
  CUDA-matched torch yourself (below).
- **NVIDIA driver must be ≥ CUDA 12.1** (12.4 is fine). Check with `nvidia-smi`.

## CUDA / cu121 note (the trap that cost us three pods)
Do **NOT** run `pip install -U torch`. On these pods it pulls a **cu130** build that needs a newer
driver than the pod has → `torch.cuda.is_available() == False`, **and** a mismatched `torchvision` →
`RuntimeError: operator torchvision::nms does not exist`, which crashes `transformers` /
`sentence-transformers` imports and silently forces the **stub** backend. Always install the **cu121**
wheels pinned below.

## Exact install
```bash
# from the repo root, one command:
bash scripts/setup_runpod_phase2b.sh
# or manually:
pip install --index-url https://download.pytorch.org/whl/cu121 torch==2.4.1 torchvision==0.19.1
pip install "transformers>=4.40,<4.46" accelerate sentence-transformers sentencepiece protobuf
# or:
pip install -r requirements-gpu.txt
```
Working stack: `torch==2.4.1 (cu121)` · `torchvision==0.19.1` · `transformers>=4.40,<4.46` ·
`accelerate` · `sentence-transformers` · `sentencepiece` · `protobuf`.

Verify before running anything:
```bash
python -c "import torch,transformers,sentence_transformers; from transformers import AutoModelForCausalLM; print('cuda', torch.cuda.is_available())"   # must print cuda True, no traceback
```

## Hugging Face auth (Mistral is gated)
Accept the license at huggingface.co/mistralai/Mistral-7B-Instruct-v0.3, then:
```bash
export HF_TOKEN=hf_xxxx
huggingface-cli login --token $HF_TOKEN
```

## Validation command (must reproduce production_valid=True)
```bash
export CSR_LLM_MODEL="mistralai/Mistral-7B-Instruct-v0.3"
python scripts/cg_wrapper_ablation/csr_match_filter/eval_framed_answers_robustness.py \
  --data   scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_eval_v2_rubricv2.jsonl \
  --rubric scripts/cg_wrapper_ablation/csr_match_filter/eval_data/framed_answer_rubric_v2.yaml \
  --answer-backends mistral --judge-backend deterministic --semantic-backend real \
  --arms base,framed --write-traces --out robustness_eval_v2.json
```
**Success looks like:**
- `frame=transformers:sentence-transformers/all-MiniLM-L6-v2` (NOT `hashing`)
- `ANSWER BACKEND: local_hf (mistral)  production_valid=True` (NOT `stub … False`)
- base arm reproduces the validated run exactly (primary **0.609**, rejected-avoidance **0.855**,
  factuality **0.945**); `polysemy_ok=True`; `robust=True`.

## Common failure modes → fix
| symptom | cause | fix |
|---|---|---|
| `frame=hashing`, `ANSWER BACKEND: stub … production_valid=False` | torch/transformers not importable | install the cu121 stack above |
| `operator torchvision::nms does not exist` | torch↔torchvision mismatch (e.g. `pip -U torch`) | pin `torch==2.4.1 torchvision==0.19.1` (cu121) |
| `torch … cuda False` + "NVIDIA driver too old (12040)" | cu130 torch on a 12.4 driver | reinstall cu121 torch, or use a PyTorch 12.1 template |
| `Cannot instantiate this tokenizer from a slow version` / `requires the protobuf library` | tokenizer deps missing | `pip install sentencepiece protobuf` |
| `401 / gated / Cannot access` on model download | Mistral is gated, no token | accept license + `HF_TOKEN` (above) |
| metrics/imports drift between pods | transformers version drift | pin `transformers>=4.40,<4.46` (see `requirements-gpu.txt`) |

## Persistence (so you don't redo this)
`runs/` is **gitignored**; a fresh pod loses it. Either write outputs to a **non-ignored path**
(repo root, e.g. `--out robustness_eval_v2.json`) and commit them, or mount a **RunPod network volume**
at `/workspace` so `runs/` survives pod stops.
