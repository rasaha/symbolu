#!/usr/bin/env bash
# =============================================================================
# RunPod execution script — CG signal-governance pilot (first true 30-50 run)
# =============================================================================
# Runbook: experiments/signal_gov/CG_PILOT_RUNBOOK.md
# This runs the real CG checkpoint path (--mode real_cg with MistralCGAdapter),
# caches features, and replays offline. It does NOT claim any result — a 30-50
# scenario pilot is underpowered (the report says so automatically).
#
# Edit the env vars in section 5, then:  bash experiments/signal_gov/runpod_cg_pilot.sh
# =============================================================================
set -euo pipefail

# ----- 1. System package assumptions -----------------------------------------
# RunPod GPU pods are Ubuntu with NVIDIA driver + CUDA + a CUDA build of PyTorch
# preinstalled (use a "PyTorch" template). We only add git/venv/zip if missing.
# (RunPod runs as root, so no sudo.)
echo "== 1. system packages =="
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv || {
  echo "ERROR: nvidia-smi failed — this is not a GPU pod."; exit 1; }
command -v git >/dev/null 2>&1 || { apt-get update && apt-get install -y git; }
command -v zip >/dev/null 2>&1 || { apt-get update && apt-get install -y zip; }
python3 -m venv --help >/dev/null 2>&1 || { apt-get update && apt-get install -y python3-venv; }

# ----- 2. Git checkout --------------------------------------------------------
echo "== 2. git checkout =="
export REPO_DIR="${REPO_DIR:-/workspace/symbolu}"
export REPO_BRANCH="${REPO_BRANCH:-claude/determined-lamport-n7w0wm}"  # change to main once merged
if [ ! -d "$REPO_DIR/.git" ]; then
  git clone --depth 1 --branch "$REPO_BRANCH" --single-branch \
    https://github.com/rasaha/symbolu.git "$REPO_DIR"
fi
cd "$REPO_DIR"
git fetch --depth 1 origin "$REPO_BRANCH" && git checkout "$REPO_BRANCH" && git pull --ff-only || true
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

# ----- 3. Python venv (inherits the pod's preinstalled CUDA torch) ------------
echo "== 3. venv =="
python3 -m venv --system-site-packages .venv-signalgov
# shellcheck disable=SC1091
source .venv-signalgov/bin/activate
python -m pip install -U pip wheel

# ----- 4. Dependency install --------------------------------------------------
echo "== 4. dependencies =="
# Harness + agentic signal path: numpy, matplotlib, pytest. CG inference:
# transformers + accelerate (device_map=auto). torch is expected from the pod;
# install a CUDA build yourself only if the next check says it is missing.
python -m pip install "numpy>=1.23" "matplotlib>=3.6" "pytest>=7.4" \
                      "transformers>=4.40" "accelerate>=0.28" "huggingface_hub>=0.23"
# bitsandbytes only needed for --cg-quantize 4bit/8bit:
if [ "${CG_QUANTIZE:-4bit}" = "4bit" ] || [ "${CG_QUANTIZE:-}" = "8bit" ]; then
  python -m pip install "bitsandbytes>=0.43" || echo "WARN: bitsandbytes install failed (see troubleshooting)"
fi

# ----- 5. Required environment variables --------------------------------------
echo "== 5. env vars =="
# Base backbone (HF id or local HF dir) that the CG wrapper wraps:
export CG_BASE_MODEL="${CG_BASE_MODEL:-mistralai/Mistral-7B-v0.3}"
# REQUIRED: the TRAINED CG state-dict (e.g. checkpoints_unified/best_model.pt). EDIT THIS.
# NOTE: CG_BASE_MODEL alone does NOT contain the trained CG head.
export CG_STATE_DICT="${CG_STATE_DICT:-EDIT_ME/path/to/best_model.pt}"
# Optional:
export CG_QUANTIZE="${CG_QUANTIZE:-4bit}"          # 4bit | 8bit | "" (fp16, ~15GB)
export CG_DEVICE="${CG_DEVICE:-auto}"              # auto | cuda:0 | ...
export CG_PILOT_OUT="${CG_PILOT_OUT:-runs/cg_pilot}"
export CG_ALLOW_UNTRAINED="${CG_ALLOW_UNTRAINED:-}"  # set to 1 to bypass the trained-head check (plumbing only)
# HuggingFace token (only if the base model is gated):
export HF_TOKEN="${HF_TOKEN:-}"
export HUGGING_FACE_HUB_TOKEN="${HUGGING_FACE_HUB_TOKEN:-$HF_TOKEN}"
# export CUDA_VISIBLE_DEVICES=0                     # pin a GPU if multi-GPU

if [ "$CG_STATE_DICT" = "EDIT_ME/path/to/best_model.pt" ] || [ -z "$CG_STATE_DICT" ]; then
  echo "ERROR: set CG_STATE_DICT to your TRAINED CG state-dict (e.g. checkpoints_unified/best_model.pt)."
  echo "       CG_BASE_MODEL is only the base backbone; it does NOT contain the trained CG head."
  exit 1
fi

# ----- 6. Smoke tests (no GPU needed; validates harness + CG signal plumbing) -
echo "== 6. smoke tests =="
python -m pytest experiments/signal_gov/tests/test_smoke.py \
                 experiments/signal_gov/tests/test_realcg_smoke.py \
                 experiments/signal_gov/tests/test_pilot_assembly.py -q
# (equivalent make targets: make signal-gov-smoke / signal-gov-realcg-smoke)

# ----- 7. State-dict + import-stack validation (verifies a TRAINED CG head) ----
echo "== 7. checkpoint + import validation =="
[ -e "$CG_STATE_DICT" ] || { echo "ERROR: CG_STATE_DICT not found: $CG_STATE_DICT"; exit 1; }
if [ -e "$CG_BASE_MODEL" ]; then echo "base model: local path ($CG_BASE_MODEL)";
else echo "base model: HF id '$CG_BASE_MODEL' (downloads; needs HF_TOKEN if gated)"; fi
python - <<'PY'
import importlib, importlib.util, os, sys
ok = True
for m in ("torch", "transformers", "numpy"):
    if importlib.util.find_spec(m) is None:
        print(f"MISSING: {m}"); ok = False
import torch
print("torch", torch.__version__, "| cuda available:", torch.cuda.is_available())
try:
    importlib.import_module("symbolu_training.training.unified.mistral_wrapper")
    print("MistralCGWrapper: importable")
except Exception as e:
    print("MistralCGWrapper import FAILED:", e); ok = False
# Verify the state-dict has a TRAINED CG head (loads only the dict; no model build).
from experiments.signal_gov.cg_checkpoint import unwrap_state_dict, verify_cg_state_dict
sd = unwrap_state_dict(torch.load(os.environ["CG_STATE_DICT"], map_location="cpu", weights_only=False))
v = verify_cg_state_dict(sd)
print("CG state-dict:", v.summary)
if not (v.has_cg_keys and v.is_trained) and not os.environ.get("CG_ALLOW_UNTRAINED"):
    print("ERROR: state-dict looks vanilla/untrained. Set CG_ALLOW_UNTRAINED=1 to override (plumbing only).")
    ok = False
from experiments.signal_gov.dataset import load_dataset
from collections import Counter
scn = load_dataset("pilot_30_50")
print("pilot_30_50:", len(scn), dict(Counter(s.category for s in scn)),
      "unsafe=", sum(s.unsafe_label for s in scn))
sys.exit(0 if ok else 1)
PY

# ----- 8. Pilot command (GPU; loads TRAINED CG head, writes features.jsonl) ----
echo "== 8. CG pilot run =="
python -m experiments.signal_gov.run_experiment \
  --dataset pilot_30_50 \
  --mode real_cg \
  --checkpoint "$CG_BASE_MODEL" \
  --cg-state-dict "$CG_STATE_DICT" \
  --cg-quantize "$CG_QUANTIZE" \
  --cg-device "$CG_DEVICE" \
  ${CG_ALLOW_UNTRAINED:+--allow-untrained-cg-head} \
  --out "$CG_PILOT_OUT"

# ----- 9. Offline replay (no GPU; metric-identical from the cache) ------------
echo "== 9. offline replay =="
python -m experiments.signal_gov.run_experiment \
  --dataset pilot_30_50 \
  --mode cached \
  --features "$CG_PILOT_OUT/features.jsonl" \
  --out "${CG_PILOT_OUT}_replay"

# ----- 10. Package outputs ----------------------------------------------------
echo "== 10. package outputs =="
STAMP="$(date +%Y%m%d_%H%M%S)"
tar -czf "cg_pilot_${STAMP}.tgz" "$CG_PILOT_OUT" "${CG_PILOT_OUT}_replay"
zip -r   "cg_pilot_${STAMP}.zip" "$CG_PILOT_OUT" "${CG_PILOT_OUT}_replay" >/dev/null
echo "Artifacts: cg_pilot_${STAMP}.tgz / .zip"
echo "Report:    $CG_PILOT_OUT/experiment_report.md  (read the Power & significance note)"
echo "DONE. This is an underpowered pilot — do not claim a result; see CG_PILOT_RUNBOOK.md sec 8-9."

# =============================================================================
# 11. TROUBLESHOOTING  (reference — these lines are comments; run as needed)
# =============================================================================
# CUDA OOM (torch.cuda.OutOfMemoryError / "CUDA out of memory"):
#   export CG_QUANTIZE=4bit            # ~5GB; re-run section 8
#   # or 8bit (~8GB), or pin a bigger/idle GPU:
#   export CUDA_VISIBLE_DEVICES=0
#   # the decision-point prompts are short by design; no batch knob is needed.
#
# Missing HF token (401/403, "gated repo", "Token is required"):
#   export HF_TOKEN=hf_xxx ; export HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
#   huggingface-cli login   # interactive alternative
#
# Missing base model / state-dict:
#   ls -la "$CG_STATE_DICT"           # trained state-dict must exist (local .pt)
#   # CG_BASE_MODEL is an HF id or local dir; verify access + HF_TOKEN if gated.
#
# Untrained / vanilla CG head (run refuses to start: "looks vanilla/untrained"):
#   # Section 7 AND the run fail closed when the state-dict has no CG-head keys or a
#   # zero phase_adapter output. Point CG_STATE_DICT at a TRAINED *_model.pt
#   # (e.g. checkpoints_unified/best_model.pt). To run anyway (PLUMBING ONLY):
#   export CG_ALLOW_UNTRAINED=1
#
# bitsandbytes failure ("CUDA Setup failed", "libbitsandbytes... not found",
# wrong CUDA version):
#   python -m pip install -U bitsandbytes
#   python -m bitsandbytes               # diagnostics
#   # if it still fails, drop quantization and use fp16 (needs ~15GB VRAM):
#   export CG_QUANTIZE="" ; # re-run section 8 without --cg-quantize effect
#
# Import errors:
#   "No module named experiments/agentic/symbolu_training":
#       cd "$REPO_DIR" && export PYTHONPATH="$PWD:$PYTHONPATH"   # run from repo root
#   "torch required" / MistralCGWrapper import FAILED:
#       re-run section 4; confirm section 7 prints torch + MistralCGWrapper OK
#   transformers/accelerate device_map errors:
#       python -m pip install -U "transformers>=4.40" "accelerate>=0.28"
#   Validate the torch-free wiring first (no GPU):
#       make signal-gov-realcg-smoke
# =============================================================================
