#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# resume_rm1.sh — resume an interrupted RM1 run. Skips a fully-provisioned
# bootstrap and already-completed smoke/full runs; never overwrites a completed
# full run. For a forced re-run use run_all_rm1.sh --force instead.
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

rm1_require_model_id
rm1_make_dirs
rm1_export_runtime_env

# skip bootstrap only if the venv is present, imports work, CUDA is up, and the
# manifest + canonical hash are intact; otherwise (re)bootstrap.
need_bootstrap=1
if [[ -x "${RM1_VENV_DIR}/bin/python" && -f "${RM1_MANIFEST}" ]]; then
  if "${RM1_VENV_DIR}/bin/python" - <<'PYEOF' >/dev/null 2>&1
import importlib
for n in ("torch", "transformers", "accelerate", "safetensors"):
    importlib.import_module(n)
import torch
raise SystemExit(0 if torch.cuda.is_available() else 1)
PYEOF
  then
    need_bootstrap=0
  fi
fi

if [[ "${need_bootstrap}" -eq 1 ]]; then
  banner "resume: environment not ready — running bootstrap"
  bash "${RM1_DIR}/bootstrap_runpod.sh"
else
  banner "resume: environment ready — skipping bootstrap"
  rm1_check_canonical_hash
fi

banner "resume: smoke (completed runs skipped)"
bash "${RM1_DIR}/run_rm1_smoke.sh"

banner "resume: full (completed run kept)"
bash "${RM1_DIR}/run_rm1_full.sh"

banner "resume: package"
bash "${RM1_DIR}/package_rm1_results.sh"

log "resume complete"
