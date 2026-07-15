#!/usr/bin/env bash
# Find a python interpreter whose torch can actually SEE the GPU (i.e. its torch CUDA build matches
# the pod's driver). Use the one printing gpu_visible=True as PYBIN for run_all.sh / the calibrator.
set -uo pipefail
echo "GPU driver:"; nvidia-smi --query-gpu=driver_version,name --format=csv,noheader 2>/dev/null | sed 's/^/  /' || echo "  (no nvidia-smi)"
echo
echo "python interpreters + torch GPU visibility:"
# de-dup candidate interpreters from PATH + common venv/conda locations
mapfile -t CANDS < <({ which -a python3 python3.10 python3.11 python3.12 2>/dev/null;
  ls /workspace/*/bin/python3 /opt/*/bin/python3 /root/*/bin/python3 \
     /usr/bin/python3 /usr/local/bin/python3 2>/dev/null; } | sort -u)
FOUND=""
for p in "${CANDS[@]}"; do
  [[ -x "$p" ]] || continue
  out=$("$p" - <<'PY' 2>/dev/null
import torch
print(f"torch {torch.__version__}  built-for-cuda {torch.version.cuda}  gpu_visible {torch.cuda.is_available()}")
PY
)
  if [[ -z "$out" ]]; then echo "  $p : (no torch)"; continue; fi
  echo "  $p : $out"
  if [[ "$out" == *"gpu_visible True"* && -z "$FOUND" ]]; then FOUND="$p"; fi
done
echo
if [[ -n "$FOUND" ]]; then
  echo "USE THIS ->  PYBIN=$FOUND bash run_all.sh --model Qwen/Qwen2.5-7B-Instruct --mask \"\$PROTECT_MASK_PATH\" --quick-quality"
  echo "  (and for the mask:  $FOUND calibrate_mask_hf.py --model Qwen/Qwen2.5-7B-Instruct --output \"\$PROTECT_MASK_PATH\" --protect-fraction 0.04 )"
else
  echo "NO interpreter can see the GPU. Either the driver is too old for every installed torch, or"
  echo "the KVPro/vLLM env isn't on this pod. Options:"
  echo "  * locate it:  find / -maxdepth 6 -name vllm -type d 2>/dev/null; ls -d /workspace/*/ /opt/*/ 2>/dev/null"
  echo "  * or install a driver-matching torch, e.g. (driver 12.8 -> cu124/cu128):"
  echo "      pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu124"
fi
