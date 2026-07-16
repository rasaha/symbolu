#!/usr/bin/env bash
# Phase B — run the full kernel recovery/inspection audit on the pod and roll up a
# single verdict JSON. Read-only metadata inspection only. POD-ONLY.
#
#   PYBIN=/workspace/venv-vllm/bin/python3 ./run_recovery_audit.sh
# (PYBIN must be the forked-vLLM venv so vllm.vllm_flash_attn resolves to the int4 build.)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYBIN="${PYBIN:-python3}"
command -v "$PYBIN" >/dev/null 2>&1 || { echo "[warn] PYBIN='$PYBIN' not found; falling back to python3"; PYBIN="$(command -v python3 || true)"; }
[ -n "$PYBIN" ] || { echo "[UNAVAILABLE] no python3 on PATH — cannot run the audit"; exit 3; }
export PYBIN
echo "[info] using PYBIN=$PYBIN"
RUNS="$HERE/runs"; mkdir -p "$RUNS"

echo "== Phase B.0 — kernel environment =="; bash "$HERE/00_inspect_kernel_env.sh" || true
echo; echo "== Phase B.1 — build artifacts / source checkout =="; bash "$HERE/01_find_build_artifacts.sh" || true
echo; echo "== Phase B.2 — installed-kernel hashes + symbols =="; "$PYBIN" "$HERE/02_hash_installed_kernel.py" || true
echo; echo "== Phase B.3 — wheel metadata =="; "$PYBIN" "$HERE/03_extract_wheel_metadata.py" || true

echo; echo "== roll-up verdict =="
"$PYBIN" - "$RUNS" <<'PY'
import json, os, sys
runs = sys.argv[1]
def load(n):
    p = os.path.join(runs, n)
    try: return json.load(open(p))
    except Exception: return {"label": "NOT_RUN"}
env, art, hsh, whl = (load(n) for n in
    ("kernel_env.json", "build_artifacts.json", "installed_kernel_hashes.json", "wheel_metadata.json"))

has_op = False
try:
    has_op = any(o.get("has_fwd_kvcache_int4") for o in env.get("torch_ops", []) if isinstance(o, dict))
except Exception: pass
dev = art.get("dev_source_tree", {}) if isinstance(art, dict) else {}
src_present = bool(dev.get("present")) and dev.get("matches_720c948", False)
wheel_match = whl.get("provenance_match") if isinstance(whl, dict) else "UNKNOWN"

# Source-recovery gate (Phase D), decided from what the pod actually has.
if src_present and has_op:
    verdict = "SOURCE_RECOVERED_EXACT"
elif has_op:
    verdict = "BINARY_ONLY_PROVENANCE_KNOWN (working binary present; base checkout absent — reclone @ 720c948 + in-repo patches)"
elif src_present:
    verdict = "SOURCE_RECOVERED_PARTIAL (base checkout present; kernel not importable — rebuild+install)"
else:
    verdict = "INCONCLUSIVE (neither working binary nor base checkout on this pod — this is a fresh container; recover per kernel_provenance.json)"

rollup = {"label": "RECOVERY-AUDIT",
          "kernel_importable": has_op,
          "base_source_checkout_at_720c948": src_present,
          "wheel_provenance_match": wheel_match,
          "source_recovery_verdict": verdict,
          "note": "In-repo INT4 patch source (apply_phase*_patches.py) is ALWAYS available regardless "
                  "of pod state; this verdict is about the WORKING binary + base checkout on THIS pod."}
json.dump(rollup, open(os.path.join(runs, "recovery_verdict.json"), "w"), indent=2)
print(json.dumps(rollup, indent=2))
print(f"\n-> {os.path.join(runs, 'recovery_verdict.json')}")
print("\ncommit artifacts:  git add -f scripts/kvpro_kernel_recovery/runs/*.json")
PY
