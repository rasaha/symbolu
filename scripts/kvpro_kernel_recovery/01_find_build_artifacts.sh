#!/usr/bin/env bash
# Phase B.1 — locate build artifacts + source checkouts of the int4 fork on the pod:
# the /workspace/dev checkout at SHA 720c948, built wheels, patch files, build logs,
# and the vendored backup. Read-only discovery; prints what exists vs NOT_FOUND.
# POD-ONLY. Emits runs/build_artifacts.json.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${OUT:-$HERE/runs/build_artifacts.json}"; mkdir -p "$(dirname "$OUT")"
PYBIN="${PYBIN:-python3}"

# Candidate locations (from KERNEL_6C3C_RUNBOOK.md provenance).
DEV_TREE="${DEV_TREE:-/workspace/dev/vllm-flash-attn-dev}"
BUILD_LOGS="${BUILD_LOGS:-/workspace/dev/build-logs}"
VENV="${VENV:-/workspace/venv-vllm}"

"$PYBIN" - "$OUT" "$DEV_TREE" "$BUILD_LOGS" "$VENV" <<'PY'
import json, os, sys, subprocess
out_path, dev_tree, build_logs, venv = sys.argv[1:5]
rep = {"label": "POD-INSPECT"}

def exists(p): return os.path.exists(p)

# --- dev source checkout + its HEAD SHA (the base fork @ 720c948) ---
def dev_info():
    if not exists(dev_tree):
        return {"present": False, "path": dev_tree, "note": "NOT_FOUND — clone base fork per kernel_provenance.json"}
    d = {"present": True, "path": dev_tree}
    try:
        r = subprocess.run(["git", "-C", dev_tree, "log", "-1", "--format=%H %ci %s"],
                           capture_output=True, text=True, timeout=30)
        d["head"] = r.stdout.strip() or r.stderr.strip()
        d["matches_720c948"] = d["head"].startswith("720c948")
    except Exception as e:
        d["head"] = f"NOT_FOUND ({e})"
    # int4 source files present?
    csrc = os.path.join(dev_tree, "csrc", "flash_attn", "src")
    d["int4_sources_present"] = {f: exists(os.path.join(csrc, f)) for f in (
        "int4_inline.h", "int4_packed_load.h",
        "flash_fwd_split_hdim128_bf16_int4kv_sm80.cu",
        "flash_fwd_split_hdim128_bf16_int4kv_packed_sm80.cu")}
    return d
rep["dev_source_tree"] = dev_info()

# --- built wheels ---
def wheels():
    found = []
    for base in (dev_tree, build_logs, "/workspace", os.path.expanduser("~")):
        if not exists(base): continue
        for root, _dirs, files in os.walk(base):
            if root.count(os.sep) - base.count(os.sep) > 3: continue  # shallow
            for f in files:
                if f.endswith(".whl") and "flash_attn" in f:
                    p = os.path.join(root, f)
                    found.append({"path": p, "size_mb": round(os.path.getsize(p) / 1e6, 1)})
    return found or "NOT_FOUND"
rep["wheels"] = wheels()

# --- build logs + vendored backup ---
rep["build_logs_dir"] = {"present": exists(build_logs), "path": build_logs,
    "entries": (sorted(os.listdir(build_logs))[:40] if exists(build_logs) else "NOT_FOUND")}
backup = os.path.join(build_logs, "vllm_flash_attn_vendored_backup")
rep["vendored_backup"] = {"present": exists(backup), "path": backup}

# --- pip cache (wheels only, metadata) ---
def pip_cache():
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "cache", "dir"],
                           capture_output=True, text=True, timeout=30)
        d = r.stdout.strip()
        hits = []
        if d and exists(d):
            for root, _dirs, files in os.walk(d):
                for f in files:
                    if "flash_attn" in f and f.endswith(".whl"):
                        hits.append(os.path.join(root, f))
        return {"dir": d or "NOT_FOUND", "flash_attn_wheels": hits or "none"}
    except Exception as e:
        return f"NOT_FOUND ({e})"
rep["pip_cache"] = pip_cache()

# --- in-repo patch scripts (source-of-truth for the int4 additions) ---
repo = os.environ.get("SYMBOLU_REPO", "/workspace/symbolu")
patchdir = os.path.join(repo, "CTM_plus", "Bench", "scripts")
rep["in_repo_patch_scripts"] = ([f for f in sorted(os.listdir(patchdir))
                                 if f.startswith("apply_phase") and f.endswith((".py", ".sh"))]
                                if exists(patchdir) else "NOT_FOUND")

json.dump(rep, open(out_path, "w"), indent=2)
print(json.dumps(rep, indent=2)); print(f"\n-> {out_path}")
PY
