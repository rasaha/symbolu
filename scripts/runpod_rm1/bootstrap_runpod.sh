#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# bootstrap_runpod.sh — prepare a CUDA RunPod for the RM1 real-model run.
# Does NOT run the real-model experiment. It validates env, records hardware,
# clones/updates the repo, builds the venv, installs deps, verifies imports and
# CUDA, runs the 27 existing tests, checks the canonical hash, and writes the
# runtime manifest.
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

banner "RM1 bootstrap — validate + provision (no experiment)"

# 1. required env ------------------------------------------------------------
rm1_require_model_id
if [[ ! -d "${UGENCE_REPO_DIR}/.git" && -z "${UGENCE_REPO_URL}" ]]; then
  die "repository absent at ${UGENCE_REPO_DIR} and UGENCE_REPO_URL not set"
fi

# 2. persistent directories --------------------------------------------------
rm1_make_dirs
log "output root: ${RM1_OUTPUT_ROOT}"

# 3. detect + record hardware ------------------------------------------------
banner "hardware / host inspection"
HW_TMP="$(mktemp)"
{
  echo "== RM1 runtime manifest =="
  echo "generated_utc: $(_c_ts)"
  echo
  echo "[host]"
  echo "hostname: $(hostname 2>/dev/null || echo unknown)"
  echo "uname: $(uname -a 2>/dev/null || echo unknown)"
  echo "host_ram: $(free -h 2>/dev/null | awk '/Mem:/{print $2" total, "$7" available"}' || echo unknown)"
  echo "disk_workspace: $(df -h /workspace 2>/dev/null | awk 'NR==2{print $2" total, "$4" free"}' || echo unknown)"
  echo "python: $(python3 --version 2>&1 || echo unknown)"
  echo
  echo "[gpu]"
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "gpu_names:"
    nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader 2>/dev/null \
      | sed 's/^/  - /'
    echo "gpu_count: $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ')"
    echo "nvidia_driver: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1)"
  else
    echo "nvidia-smi: NOT FOUND (no GPU visible at bootstrap time)"
  fi
} | tee "${HW_TMP}"

# 4/5. clone or update -------------------------------------------------------
banner "repository: clone / update"
if [[ ! -d "${UGENCE_REPO_DIR}/.git" ]]; then
  log "cloning ${UGENCE_REPO_URL} -> ${UGENCE_REPO_DIR}"
  git clone "${UGENCE_REPO_URL}" "${UGENCE_REPO_DIR}"
  git -C "${UGENCE_REPO_DIR}" fetch origin
  git -C "${UGENCE_REPO_DIR}" checkout "${UGENCE_BRANCH}"
else
  log "repository present; requiring clean working tree before update"
  rm1_require_clean_tree
  git -C "${UGENCE_REPO_DIR}" fetch origin
  git -C "${UGENCE_REPO_DIR}" checkout "${UGENCE_BRANCH}"
  git -C "${UGENCE_REPO_DIR}" pull --ff-only origin "${UGENCE_BRANCH}"
fi

# 6. record exact branch + commit -------------------------------------------
GIT_COMMIT="$(git -C "${UGENCE_REPO_DIR}" rev-parse HEAD)"
GIT_BRANCH="$(git -C "${UGENCE_REPO_DIR}" rev-parse --abbrev-ref HEAD)"
log "branch=${GIT_BRANCH} commit=${GIT_COMMIT}"

# 7. virtual environment -----------------------------------------------------
banner "python virtual environment"
if [[ ! -x "${RM1_VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${RM1_VENV_DIR}"
fi
PY="${RM1_VENV_DIR}/bin/python"

# 8. base tooling ------------------------------------------------------------
"${PY}" -m pip install --upgrade pip setuptools wheel

# 9. real-model requirements -------------------------------------------------
REQ_FILE="${UGENCE_REPO_DIR}/experiments/hybrid_token_event_attention/real_model/requirements-real-model.txt"
[[ -f "${REQ_FILE}" ]] || die "requirements file not found: ${REQ_FILE}"
"${PY}" -m pip install -r "${REQ_FILE}"

# 10. bitsandbytes only when 4-bit requested ---------------------------------
if [[ "${RM1_LOAD_IN_4BIT}" == "1" ]]; then
  banner "installing bitsandbytes (RM1_LOAD_IN_4BIT=1)"
  "${PY}" -m pip install "bitsandbytes>=0.43"
else
  log "skipping bitsandbytes (RM1_LOAD_IN_4BIT!=1)"
fi

# 11/12. verify imports + CUDA ----------------------------------------------
banner "verify imports + CUDA"
IMPORT_TMP="$(mktemp)"
"${PY}" - <<'PYEOF' | tee "${IMPORT_TMP}"
import importlib, json
info = {}
for name in ("torch", "transformers", "accelerate", "safetensors"):
    mod = importlib.import_module(name)
    info[name] = getattr(mod, "__version__", "unknown")
import torch
info["cuda_available"] = bool(torch.cuda.is_available())
info["cuda_device_count"] = torch.cuda.device_count() if torch.cuda.is_available() else 0
if torch.cuda.is_available():
    info["cuda_devices"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    try:
        info["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
    except Exception:
        info["bf16_supported"] = None
print(json.dumps(info, indent=2))
if not info["cuda_available"]:
    raise SystemExit("CUDA is NOT available — RM1 requires a CUDA GPU. Aborting bootstrap.")
PYEOF

# 13. run the 27 existing tests ---------------------------------------------
banner "existing test suites (27 tests)"
( cd "${UGENCE_REPO_DIR}" && PYTHONPATH="${UGENCE_REPO_DIR}" "${PY}" -m unittest \
    experiments.hybrid_token_event_attention.tests.test_hybrid \
    experiments.hybrid_token_event_attention.real_model.tests.test_real_model_harness )
# tests write in-repo artifacts; restore the tree so it stays clean
rm1_restore_repo_tree

# 14. canonical hash guard ---------------------------------------------------
banner "canonical controlled-result hash"
rm1_check_canonical_hash

# 15. write runtime manifest -------------------------------------------------
banner "writing runtime manifest"
{
  cat "${HW_TMP}"
  echo
  echo "[repository]"
  echo "repo_dir: ${UGENCE_REPO_DIR}"
  echo "branch: ${GIT_BRANCH}"
  echo "commit: ${GIT_COMMIT}"
  echo
  echo "[python_packages]"
  cat "${IMPORT_TMP}"
  echo
  echo "[venv]"
  echo "venv: ${RM1_VENV_DIR}"
  echo "pip_freeze -> ${RM1_STATE_DIR}/pip_freeze.txt"
  echo
  echo "[config]"
  echo "model_id: ${UGENCE_REAL_MODEL_ID}"
  echo "model_revision: ${UGENCE_MODEL_REVISION:-<unset>}"
  echo "device: ${RM1_DEVICE}"
  echo "dtype: ${RM1_DTYPE}"
  echo "load_in_4bit: ${RM1_LOAD_IN_4BIT}"
  echo "max_input_tokens: ${RM1_MAX_INPUT_TOKENS}"
  echo "max_new_tokens: ${RM1_MAX_NEW_TOKENS}"
  echo "canonical_hash_ok: yes"
  echo "tests_passed: yes (27)"
} > "${RM1_MANIFEST}"
"${PY}" -m pip freeze > "${RM1_STATE_DIR}/pip_freeze.txt"
rm -f "${HW_TMP}" "${IMPORT_TMP}"

log "runtime manifest -> ${RM1_MANIFEST}"
banner "bootstrap complete (no experiment executed)"
