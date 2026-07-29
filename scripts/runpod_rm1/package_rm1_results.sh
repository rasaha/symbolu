#!/usr/bin/env bash
set -Eeuo pipefail
# ---------------------------------------------------------------------------
# package_rm1_results.sh — build a timestamped .tar.gz of ONLY the RM1 result
# artifacts, manifests, logs and scorecards. Excludes weights, HF cache, venv,
# repo source, and any credential/token. Emits SHA256SUMS and prints the path.
# ---------------------------------------------------------------------------
RM1_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${RM1_DIR}/common.sh"

rm1_make_dirs
STAMP="$(_c_ts)"
STAGE="${RM1_PACKAGES_DIR}/stage_${STAMP}"
ARCHIVE="${RM1_PACKAGES_DIR}/rm1_results_${STAMP}.tar.gz"
mkdir -p "${STAGE}/results" "${STAGE}/logs" "${STAGE}/meta"

banner "packaging RM1 results -> ${ARCHIVE}"

# --- sanitizer: strip any HF token pattern (and the literal token if set) ----
sanitize_into() {
  local src="$1" dst="$2"
  sed -E 's/hf_[A-Za-z0-9]{20,}/hf_REDACTED/g' "${src}" > "${dst}"
  if [[ -n "${HF_TOKEN:-}" ]]; then
    # redact the literal token if it ever appeared
    python3 - "$dst" <<'PYEOF' 2>/dev/null || true
import os, sys
p = sys.argv[1]
tok = os.environ.get("HF_TOKEN", "")
if tok:
    s = open(p, errors="ignore").read().replace(tok, "HF_TOKEN_REDACTED")
    open(p, "w").write(s)
PYEOF
  fi
}

# --- meta: manifest, commit, pip freeze -------------------------------------
[[ -f "${RM1_MANIFEST}" ]] && cp -f "${RM1_MANIFEST}" "${STAGE}/meta/runtime_manifest.txt"
[[ -f "${RM1_STATE_DIR}/pip_freeze.txt" ]] && cp -f "${RM1_STATE_DIR}/pip_freeze.txt" "${STAGE}/meta/pip_freeze.txt"
if [[ -d "${UGENCE_REPO_DIR}/.git" ]]; then
  {
    echo "branch: $(git -C "${UGENCE_REPO_DIR}" rev-parse --abbrev-ref HEAD)"
    echo "commit: $(git -C "${UGENCE_REPO_DIR}" rev-parse HEAD)"
    echo "commit_short: $(git -C "${UGENCE_REPO_DIR}" rev-parse --short HEAD)"
  } > "${STAGE}/meta/git_commit.txt"
fi

# --- results: smoke + full run directories (json/md/log/scorecard/taxonomy) --
copied_any=0
shopt -s nullglob
for d in "${RM1_RESULTS_DIR}"/smoke_seed_* "${RM1_RESULTS_DIR}"/full_*; do
  [[ -d "${d}" ]] || continue
  base="$(basename "${d}")"
  mkdir -p "${STAGE}/results/${base}"
  # copy only known small artifact types; never weights/caches
  for pat in "*.json" "*.jsonl" "*.md" "*.log" "*.txt"; do
    for f in "${d}"/${pat}; do
      [[ -f "${f}" ]] && cp -f "${f}" "${STAGE}/results/${base}/"
    done
  done
  copied_any=1
done
shopt -u nullglob
[[ "${copied_any}" -eq 1 ]] || log "WARNING: no smoke/full result directories found to package"

# note which full run is latest
if [[ -L "${RM1_RESULTS_DIR}/latest_full" ]]; then
  readlink -f "${RM1_RESULTS_DIR}/latest_full" > "${STAGE}/meta/latest_full.txt" 2>/dev/null || true
fi

# --- logs: sanitized copies of execution logs -------------------------------
shopt -s nullglob
for lf in "${RM1_LOG_DIR}"/*.log; do
  [[ -f "${lf}" ]] || continue
  sanitize_into "${lf}" "${STAGE}/logs/$(basename "${lf}")"
done
shopt -u nullglob

# --- checksums --------------------------------------------------------------
( cd "${STAGE}" && find . -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )

# --- archive ----------------------------------------------------------------
tar -C "${STAGE}" -czf "${ARCHIVE}" .
ARCHIVE_SHA="$(sha256sum "${ARCHIVE}" | awk '{print $1}')"
echo "${ARCHIVE_SHA}  $(basename "${ARCHIVE}")" > "${ARCHIVE}.sha256"

banner "package complete"
echo "archive: ${ARCHIVE}"
echo "sha256:  ${ARCHIVE_SHA}"
