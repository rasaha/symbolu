#!/usr/bin/env bash
# v9 GPU validation — Cython evictor cell + py-spy attribution + variance seed.
#
# Answers three questions in a single ~$0.06 spot batch (chat_32k):
#
#   1. Does the §11.3 5-10pp Cython-port estimate hold on a real Qwen2.5-7B
#      streaming-chat workload?
#   2. If so, did the recovery come from where §11.3 predicted (CTM+ EVICTOR
#      frames shrinking from 0.9% -> <0.2%)? — answered by the py-spy SVG.
#   3. Is the headline tokens/sec robust to seed? — answered by the s137 cell.
#
# Pre-decided attribution table for the profile (write this in §12.6 BEFORE
# looking at the SVG so we can't post-hoc rationalise):
#
#   Frame              v8 baseline   v9 prediction if §11.3 right
#   CTM+ EVICTOR        0.9%          < 0.2%
#   TORCH _call_impl    15.0%         unchanged (hooks not touched)
#   OTHER (sched/alloc) 79.9%         small drop
#   Wall tokens/sec     68.26         76-81 (estimate)
#
# Per-cell artefact lives under bench_out/4cell_phase4_v9_cython{,_s137}/
# and the build provenance under bench_out/4cell_phase4_v9_cython/build_provenance.txt
#
# Usage on the pod:
#
#   pip install py-spy Cython     # one-time
#   bash CTM_plus/Bench/scripts/run_v9.sh                 # full batch
#   bash CTM_plus/Bench/scripts/run_v9.sh --minimal       # just seed 42, no profile, no seed 137
#   bash CTM_plus/Bench/scripts/run_v9.sh --skip-profile  # both seeds, no profile
#   bash CTM_plus/Bench/scripts/run_v9.sh --skip-s137     # profile + seed 42 only
#
# Pre-reqs: vLLM 0.7.3, /workspace/.hf_cache_phase4/qwen2.5-7b, and
# /workspace/.calibration/qwen2.5-7b.qcenters.perlayer.json from the v8 prep
# session. The Cython .so is built fresh inside this script so the artefact
# matches the recorded commit.

set -eo pipefail

# --------------------------------------------------------------------- #
# Flags
# --------------------------------------------------------------------- #
MODE="full"        # full | minimal
RUN_PROFILE=1
RUN_S137=1
for arg in "$@"; do
    case "$arg" in
        --minimal)        MODE="minimal"; RUN_PROFILE=0; RUN_S137=0 ;;
        --skip-profile)   RUN_PROFILE=0 ;;
        --skip-s137)      RUN_S137=0 ;;
        -h|--help)
            grep '^#' "$0" | head -40
            exit 0
            ;;
        *)
            echo "unknown flag: $arg" >&2
            exit 2
            ;;
    esac
done

# --------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------- #
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCH_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BENCH_DIR}/../.." && pwd)"
KVPOLICY_DIR="${REPO_ROOT}/CTM_plus/KVPolicy"

MODEL_PATH="${MODEL_PATH:-/workspace/.hf_cache_phase4/qwen2.5-7b}"
CALIBRATION_PATH="${CALIBRATION_PATH:-/workspace/.calibration/qwen2.5-7b.qcenters.perlayer.json}"
LRU_BASELINE_DIR="${LRU_BASELINE_DIR:-${BENCH_DIR}/bench_out/4cell_lru_v3}"

OUT_SEED42="${BENCH_DIR}/bench_out/4cell_phase4_v9_cython"
OUT_SEED137="${BENCH_DIR}/bench_out/4cell_phase4_v9_cython_s137"
PROFILE_SVG="${OUT_SEED42}/v9_phase4.pyspy.svg"

# --------------------------------------------------------------------- #
# Sanity checks
# --------------------------------------------------------------------- #
echo "==> v9 batch ($MODE)"
echo "    repo:        ${REPO_ROOT}"
echo "    model:       ${MODEL_PATH}"
echo "    calibration: ${CALIBRATION_PATH}"
echo "    LRU baseline (for reader): ${LRU_BASELINE_DIR}"
echo

[[ -d "${MODEL_PATH}" ]] || { echo "missing model dir: ${MODEL_PATH}" >&2; exit 1; }
[[ -f "${CALIBRATION_PATH}" ]] || { echo "missing calibration: ${CALIBRATION_PATH}" >&2; exit 1; }
[[ -d "${LRU_BASELINE_DIR}" ]] || \
    echo "warn: LRU baseline dir absent (${LRU_BASELINE_DIR}); reader step will warn"

mkdir -p "${OUT_SEED42}" "${OUT_SEED137}"

# --------------------------------------------------------------------- #
# Step 1 — build the Cython .so against the current commit
# --------------------------------------------------------------------- #
echo "==> [1/5] Building Cython extension"
(
    cd "${KVPOLICY_DIR}"
    python3 setup.py build_ext --inplace
)
# Smoke-test with PYTHONPATH prepend so kv_policy resolves regardless
# of cwd (the runner injects this path itself via
# ctm_bench.policies._add_kv_policy_to_path).
PYTHONPATH="${KVPOLICY_DIR}:${PYTHONPATH:-}" python3 -c "
from kv_policy._ctm_evictor import CTMEvictorModernC
ev = CTMEvictorModernC(num_blocks_capacity=8, block_size=16)
assert type(ev).__module__ == 'kv_policy._ctm_evictor', 'wrong module'
print('cython import ok:', type(ev).__module__ + '.' + type(ev).__name__)
"

# --------------------------------------------------------------------- #
# Step 2 — capture build provenance (commit, toolchain versions, .so path)
# --------------------------------------------------------------------- #
echo "==> [2/5] Recording build provenance"
{
    echo "# v9 build provenance"
    echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "git_commit: $(cd "${REPO_ROOT}" && git rev-parse HEAD)"
    echo "git_branch: $(cd "${REPO_ROOT}" && git rev-parse --abbrev-ref HEAD)"
    echo "git_status_short:"
    (cd "${REPO_ROOT}" && git status --short) | sed 's/^/  /'
    echo "python: $(python3 --version)"
    echo "cython: $(python3 -c 'import Cython; print(Cython.__version__)')"
    echo "gcc:    $(gcc --version | head -1)"
    echo "torch:  $(python3 -c 'import torch; print(torch.__version__)' 2>&1)"
    echo "vllm:   $(python3 -c 'import vllm; print(vllm.__version__)' 2>&1)"
    echo "py-spy: $(py-spy --version 2>&1 || echo NOT_INSTALLED)"
    echo "so:"
    ls -la "${KVPOLICY_DIR}/kv_policy"/_ctm_evictor*.so | sed 's/^/  /'
} > "${OUT_SEED42}/build_provenance.txt"
cp "${OUT_SEED42}/build_provenance.txt" "${OUT_SEED137}/build_provenance.txt"
echo "    wrote ${OUT_SEED42}/build_provenance.txt"

# --------------------------------------------------------------------- #
# Step 3 — v9 cell, seed 42 (headline). With or without py-spy attached.
# --------------------------------------------------------------------- #
RUN_CMD=(
    python3 -m ctm_bench.scripts.run_streaming
    --model "${MODEL_PATH}"
    --workload chat_32k --seed 42
    --gpu-memory-utilization 0.26 --swap-space-gb 16
    --arrival-rate 6.0 --arrival-alpha 1.5
    --max-requests 30 --max-wall-seconds 60
    --max-decode-tokens 2048
    --prompt-length-choices "8000,16000,24000,30000"
    --ctm-plus
    --phase4-trig-calibration "${CALIBRATION_PATH}"
    --phase4-window-interval 128
    --phase4-future-offsets "1,2,4,8,16"
    --phase4-capture-every-n 4
    --phase4-trig-blend-candidate-count 4
    --phase4-cython-evictor
    --output-dir "${OUT_SEED42}"
)

cd "${BENCH_DIR}"

if [[ "${RUN_PROFILE}" -eq 1 ]]; then
    echo "==> [3/5] v9 cell seed=42 with py-spy attached"
    echo "    profile: ${PROFILE_SVG}"
    # --rate 100  : 100Hz sampling (matches §11 settings)
    # --native    : include C-extension frames so the new C evictor frames
    #               are visible — without this the Cython class shows as
    #               a single opaque frame.
    # --idle      : include GIL/IO waits so scheduler+allocator are not
    #               undercounted.
    py-spy record \
        --output "${PROFILE_SVG}" \
        --rate 100 --native --idle \
        -- "${RUN_CMD[@]}"
else
    echo "==> [3/5] v9 cell seed=42 (no py-spy)"
    "${RUN_CMD[@]}"
fi

# --------------------------------------------------------------------- #
# Step 4 — v9 cell, seed 137 (variance bound). No profile; just measurement.
# --------------------------------------------------------------------- #
if [[ "${RUN_S137}" -eq 1 ]]; then
    echo "==> [4/5] v9 cell seed=137 (variance)"
    python3 -m ctm_bench.scripts.run_streaming \
        --model "${MODEL_PATH}" \
        --workload chat_32k --seed 137 \
        --gpu-memory-utilization 0.26 --swap-space-gb 16 \
        --arrival-rate 6.0 --arrival-alpha 1.5 \
        --max-requests 30 --max-wall-seconds 60 \
        --max-decode-tokens 2048 \
        --prompt-length-choices "8000,16000,24000,30000" \
        --ctm-plus \
        --phase4-trig-calibration "${CALIBRATION_PATH}" \
        --phase4-window-interval 128 \
        --phase4-future-offsets "1,2,4,8,16" \
        --phase4-capture-every-n 4 \
        --phase4-trig-blend-candidate-count 4 \
        --phase4-cython-evictor \
        --output-dir "${OUT_SEED137}"
else
    echo "==> [4/5] seed=137 cell skipped (--skip-s137 or --minimal)"
fi

# --------------------------------------------------------------------- #
# Step 5 — comparison reads
# --------------------------------------------------------------------- #
echo "==> [5/5] Reader summary"
echo
echo "--- v9 seed=42 vs LRU v3 (the headline) ---"
python3 -m ctm_bench.scripts.read_phase4_v5 \
    --phase4-dir "${OUT_SEED42}" \
    --phase2-dir "${LRU_BASELINE_DIR}" || true

V8_DIR="${BENCH_DIR}/bench_out/4cell_phase4_v8"
if [[ -d "${V8_DIR}" ]]; then
    echo
    echo "--- v9 seed=42 vs v8 (semantic no-op check) ---"
    echo "    swap_out/decode_token, trig_changed_pick/blend_calls,"
    echo "    blocks_captured, window_pruning_invocations should be"
    echo "    bit-equivalent to v8. tokens/sec is the only metric that"
    echo "    should differ — upward."
    python3 -m ctm_bench.scripts.read_phase4_v5 \
        --phase4-dir "${OUT_SEED42}" \
        --phase2-dir "${V8_DIR}" || true
else
    echo
    echo "    v8 dir absent (${V8_DIR}); skipping no-op cross-check"
fi

if [[ "${RUN_S137}" -eq 1 ]]; then
    echo
    echo "--- v9 seed=137 vs LRU v3 (variance) ---"
    python3 -m ctm_bench.scripts.read_phase4_v5 \
        --phase4-dir "${OUT_SEED137}" \
        --phase2-dir "${LRU_BASELINE_DIR}" || true
fi

echo
echo "==> v9 batch complete."
echo "    seed=42 artefact:  ${OUT_SEED42}"
if [[ "${RUN_S137}" -eq 1 ]]; then
    echo "    seed=137 artefact: ${OUT_SEED137}"
fi
if [[ "${RUN_PROFILE}" -eq 1 ]]; then
    echo "    profile SVG:       ${PROFILE_SVG}"
fi
echo
echo "Next steps:"
echo "  - Append §12.6 to PHASE4_GPU_FINDINGS.md with the v9 result table."
echo "  - Map the profile against the pre-decided attribution table at the"
echo "    top of this script. Record where the §11.3 estimate landed in the"
echo "    decision tree (§12 footer)."
echo "  - Commit bench_out/4cell_phase4_v9_cython{,_s137}/ + the SVG."
