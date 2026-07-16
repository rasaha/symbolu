#!/usr/bin/env bash
# Phase B.0 — inspect the environment that holds the working int4 decode kernel.
# Reports import path, module file, version, exported functions, .so paths, CUDA
# extension names, linked libraries, and arch targets. Ordinary metadata + exported
# symbols only — NO binary reverse-engineering. Emits a JSON block; prints NOT_FOUND
# (never fabricated) when a probe can't resolve. POD-ONLY.
#
#   PYBIN=/workspace/venv-vllm/bin/python3 ./00_inspect_kernel_env.sh
set -u
PYBIN="${PYBIN:-python3}"
command -v "$PYBIN" >/dev/null 2>&1 || { echo "[warn] PYBIN='$PYBIN' not found; falling back to python3"; PYBIN="$(command -v python3 || true)"; }
[ -n "$PYBIN" ] || { echo "[UNAVAILABLE] no python3 on PATH"; exit 3; }
OUT="${OUT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/runs/kernel_env.json}"
mkdir -p "$(dirname "$OUT")"

"$PYBIN" - "$OUT" <<'PY'
import json, os, sys, importlib, subprocess
out_path = sys.argv[1]
rep = {"label": "POD-INSPECT", "python": sys.version.split()[0], "python_exe": sys.executable}

def _try(fn, default="NOT_FOUND"):
    try: return fn()
    except Exception as e: return f"NOT_FOUND ({type(e).__name__}: {e})"

# --- vllm_flash_attn module ---
def mod_info():
    m = importlib.import_module("vllm.vllm_flash_attn")
    info = {"module_file": getattr(m, "__file__", "NOT_FOUND"),
            "has_flash_attn_with_int4_kvcache": hasattr(m, "flash_attn_with_int4_kvcache")}
    # exported callables of interest
    names = [n for n in dir(m) if "int4" in n.lower() or "kvcache" in n.lower()]
    info["exported_int4_names"] = names
    return info
rep["vllm_flash_attn"] = _try(mod_info)

# --- the torch op (the actual kernel entry) ---
def op_info():
    import torch  # noqa
    ops = []
    for lib in ("_vllm_fa2_C", "_vllm_fa3_C"):
        try:
            o = getattr(torch.ops, lib)
            ops.append({"lib": lib, "has_fwd_kvcache_int4": hasattr(o, "fwd_kvcache_int4")})
        except Exception as e:
            ops.append({"lib": lib, "error": f"{type(e).__name__}: {e}"})
    return ops
rep["torch_ops"] = _try(op_info)

# --- .so files + arch targets + linked libs (ordinary metadata) ---
def so_info():
    base = os.path.dirname(importlib.import_module("vllm.vllm_flash_attn").__file__)
    sos = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".so"):
                p = os.path.join(root, f)
                entry = {"path": p, "size_mb": round(os.path.getsize(p) / 1e6, 1)}
                # arch targets via cuobjdump if available (metadata only)
                for tool, args, key in [
                    ("cuobjdump", ["--list-elf"], "cuobjdump_elf"),
                    ("ldd", [], "ldd"),
                ]:
                    try:
                        r = subprocess.run([tool, *args, p] if tool == "cuobjdump" else [tool, p],
                                           capture_output=True, text=True, timeout=60)
                        txt = (r.stdout or "") + (r.stderr or "")
                        if key == "cuobjdump_elf":
                            entry["sm_arch_targets"] = sorted(set(
                                s for s in txt.replace(".", " ").split() if s.startswith("sm_")))
                        else:
                            entry["linked_libs"] = [l.split()[0] for l in txt.splitlines()
                                                    if "=>" in l][:40]
                    except Exception:
                        entry.setdefault("tools_missing", []).append(tool)
                sos.append(entry)
    return sos or "NOT_FOUND (no .so under module dir)"
rep["shared_objects"] = _try(so_info)

json.dump(rep, open(out_path, "w"), indent=2)
print(json.dumps(rep, indent=2))
print(f"\n-> {out_path}")
PY
