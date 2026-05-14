#!/usr/bin/env bash
# v10 GPU validation — Cython evictor + hook-shape fix (the §11.3 row-2
# follow-up to v9's 0pp result).
#
# v9 verdict: Cython port held semantic correctness (swap_out/decode_token =
# 0.2769 matches v8) but recovered 0pp of throughput vs v8. The profile said
# CTM+ EVICTOR was 0.9% of wall; a C port of code that's 0.9% can't recover
# the missing 20%, so the §11.3 estimate of 5-10pp was over-optimistic.
#
# v10 tests the remaining §11.3 lever: replace register_forward_pre_hook
# with direct monkey-patch of module.forward so torch's _call_impl skips
# the _forward_pre_hooks dispatcher walk on every fire. Hooks fire ~1020/s
# in our test workload (1× model.forward + 28× rotary_emb per token,
# ~34 tokens/s); even small per-fire savings add up.
#
# Two predicted outcomes BEFORE the run (write these to §12.7 before
# reading the result):
#
#   Outcome A (5-8pp recovery): v10 tokens/sec lands ~73-76. §11.3 row-2
#     vindicated. Phase 4 still loses to LRU (~85) but is closer. The
#     case for shipping the algorithm strengthens; partner pitch shifts
#     from "negative result on chat_32k" to "throughput-competitive with
#     remaining gap structural to the patching approach."
#
#   Outcome B (0-2pp recovery): v10 tokens/sec lands ~67-69. §11.3 row-2
#     also wrong; the integration tax is structurally below the hook
#     layer. Narrative: "we exhausted the cheap throughput levers; the
#     algorithm wins on per-token swap (-11%) but the integration shape
#     cost (20%) is structural at this vLLM minor + Evictor-ABC patch
#     point." This is the durable negative result.
#
# Either outcome is a valid stopping point for Phase 4 throughput work.
#
# Usage:
#   bash CTM_plus/Bench/scripts/run_v10.sh                   # full batch (~$0.07)
#   bash CTM_plus/Bench/scripts/run_v10.sh --minimal         # ~$0.025, headline only
#   bash CTM_plus/Bench/scripts/run_v10.sh --skip-profile    # no py-spy
#   bash CTM_plus/Bench/scripts/run_v10.sh --skip-s137       # no variance seed

set -eo pipefail

MODE="full"
RUN_PROFILE=1
RUN_S137=1
for arg in "$@"; do
    case "$arg" in
        --minimal)        MODE="minimal"; RUN_PROFILE=0; RUN_S137=0 ;;
        --skip-profile)   RUN_PROFILE=0 ;;
        --skip-s137)      RUN_S137=0 ;;
        -h|--help)        grep '^#' "$0" | head -45; exit 0 ;;
        *)                echo "unknown flag: $arg" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BENCH_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BENCH_DIR}/../.." && pwd)"
KVPOLICY_DIR="${REPO_ROOT}/CTM_plus/KVPolicy"

MODEL_PATH="${MODEL_PATH:-/workspace/.hf_cache_phase4/qwen2.5-7b}"
CALIBRATION_PATH="${CALIBRATION_PATH:-/workspace/.calibration/qwen2.5-7b.qcenters.perlayer.json}"
LRU_BASELINE_DIR="${LRU_BASELINE_DIR:-${BENCH_DIR}/bench_out/4cell_lru_v3}"

OUT_SEED42="${BENCH_DIR}/bench_out/4cell_phase4_v10_fasthooks"
OUT_SEED137="${BENCH_DIR}/bench_out/4cell_phase4_v10_fasthooks_s137"
PROFILE_SVG="${OUT_SEED42}/v10_phase4.pyspy.svg"

echo "==> v10 batch ($MODE)"
echo "    repo:        ${REPO_ROOT}"
echo "    LRU baseline: ${LRU_BASELINE_DIR}"
[[ -d "${MODEL_PATH}" ]] || { echo "missing model: ${MODEL_PATH}" >&2; exit 1; }
[[ -f "${CALIBRATION_PATH}" ]] || { echo "missing calibration: ${CALIBRATION_PATH}" >&2; exit 1; }
mkdir -p "${OUT_SEED42}" "${OUT_SEED137}"

echo "==> [1/5] Build Cython .so"
(cd "${KVPOLICY_DIR}" && python3 setup.py build_ext --inplace) > /dev/null
# Smoke-test from inside KVPolicy so kv_policy is on sys.path without
# needing pip install -e. The real runner injects the path via
# ctm_bench.policies._add_kv_policy_to_path(); we mirror that with a
# PYTHONPATH prepend for this one-off check.
PYTHONPATH="${KVPOLICY_DIR}:${PYTHONPATH:-}" python3 -c "from kv_policy._ctm_evictor import CTMEvictorModernC; print('cython ok')"

echo "==> [2/5] Record build provenance"
{
    echo "# v10 build provenance"
    echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "git_commit: $(cd "${REPO_ROOT}" && git rev-parse HEAD)"
    echo "git_branch: $(cd "${REPO_ROOT}" && git rev-parse --abbrev-ref HEAD)"
    echo "flags: --phase4-cython-evictor --phase4-fast-hooks"
    echo "python: $(python3 --version)"
    echo "cython: $(python3 -c 'import Cython; print(Cython.__version__)')"
    echo "torch:  $(python3 -c 'import torch; print(torch.__version__)' 2>&1)"
    echo "vllm:   $(python3 -c 'import vllm; print(vllm.__version__)' 2>&1)"
    echo "py-spy: $(py-spy --version 2>&1 || echo NOT_INSTALLED)"
    ls -la "${KVPOLICY_DIR}/kv_policy"/_ctm_evictor*.so | sed 's/^/so: /'
} > "${OUT_SEED42}/build_provenance.txt"
cp "${OUT_SEED42}/build_provenance.txt" "${OUT_SEED137}/build_provenance.txt"

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
    --phase4-fast-hooks
    --output-dir "${OUT_SEED42}"
)

cd "${BENCH_DIR}"

if [[ "${RUN_PROFILE}" -eq 1 ]]; then
    echo "==> [3/5] v10 cell seed=42 + py-spy"
    py-spy record --output "${PROFILE_SVG}" --rate 100 --native --idle \
        -- "${RUN_CMD[@]}"
else
    echo "==> [3/5] v10 cell seed=42 (no py-spy)"
    "${RUN_CMD[@]}"
fi

if [[ "${RUN_S137}" -eq 1 ]]; then
    echo "==> [4/5] v10 cell seed=137 (variance)"
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
        --phase4-fast-hooks \
        --output-dir "${OUT_SEED137}"
else
    echo "==> [4/5] seed=137 skipped"
fi

echo "==> [5/5] Reader summary"
echo
echo "--- v10 seed=42 vs LRU v3 (headline) ---"
python3 -m ctm_bench.scripts.read_phase4_v5 \
    --phase4-dir "${OUT_SEED42}" \
    --phase2-dir "${LRU_BASELINE_DIR}" || true

V9_DIR="${BENCH_DIR}/bench_out/4cell_phase4_v9_cython"
if [[ -d "${V9_DIR}" ]]; then
    echo
    echo "--- v10 seed=42 vs v9 (the §11.3 row-2 delta) ---"
    echo "    Same Cython evictor on both sides. Only difference is"
    echo "    --phase4-fast-hooks on v10. tokens/sec delta IS the row-2"
    echo "    recovery. swap_out/decode_token should remain 0.2769."
    python3 -m ctm_bench.scripts.read_phase4_v5 \
        --phase4-dir "${OUT_SEED42}" \
        --phase2-dir "${V9_DIR}" || true
fi

if [[ "${RUN_S137}" -eq 1 ]]; then
    echo
    echo "--- v10 seed=137 vs LRU v3 (variance) ---"
    python3 -m ctm_bench.scripts.read_phase4_v5 \
        --phase4-dir "${OUT_SEED137}" \
        --phase2-dir "${LRU_BASELINE_DIR}" || true
fi

echo
echo "==> v10 batch complete. Map result against decision tree in"
echo "    PHASE4_GPU_FINDINGS §13, append §12.7, commit artefacts."
