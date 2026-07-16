#!/usr/bin/env python3
"""Phase B.2 — hash the installed kernel .so files and list the INT4-KV-decode exported
symbols (ordinary metadata: sha256 + `nm`/`objdump` exported-symbol names). This pins the
EXACT installed binary so a rebuilt wheel can be compared for equivalence. NO binary
reverse-engineering beyond symbol names + hashes. POD-ONLY; prints NOT_FOUND cleanly.

  PYBIN=/workspace/venv-vllm/bin/python3 python 02_hash_installed_kernel.py
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT", os.path.join(_HERE, "runs", "installed_kernel_hashes.json"))


def _sha256(path, cap_mb=1024):
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk); n += len(chunk)
            if n > cap_mb * (1 << 20):
                return h.hexdigest() + f" (partial>{cap_mb}MB)"
    return h.hexdigest()


def _symbols(so_path):
    """Exported symbol names mentioning int4/kvcache (metadata only)."""
    for tool in (["nm", "-D", "--defined-only"], ["objdump", "-T"]):
        try:
            r = subprocess.run([*tool, so_path], capture_output=True, text=True, timeout=120)
            lines = (r.stdout or "").splitlines()
            hits = sorted({ln.split()[-1] for ln in lines
                           if ("int4" in ln.lower() or "kvcache" in ln.lower()
                               or "fwd_kvcache" in ln.lower())})
            if hits or lines:
                return {"tool": tool[0], "int4_kvcache_symbols": hits[:60],
                        "total_exported": len(lines)}
        except Exception:
            continue
    return "NOT_FOUND (no nm/objdump)"


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rep = {"label": "POD-INSPECT", "python_exe": sys.executable}
    try:
        base = os.path.dirname(importlib.import_module("vllm.vllm_flash_attn").__file__)
    except Exception as e:  # noqa: BLE001
        rep["error"] = f"vllm.vllm_flash_attn import failed: {e}"
        json.dump(rep, open(OUT, "w"), indent=2); print(json.dumps(rep, indent=2)); return 3
    rep["module_dir"] = base
    entries = []
    for root, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".so"):
                p = os.path.join(root, f)
                entries.append({"path": p, "size_mb": round(os.path.getsize(p) / 1e6, 1),
                                "sha256": _sha256(p), "symbols": _symbols(p)})
    rep["shared_objects"] = entries or "NOT_FOUND (no .so)"
    rep["note"] = ("sha256 pins the exact installed binary; compare a rebuilt wheel's .so to "
                   "confirm reproducibility. Symbol names confirm the int4 KV op is compiled in.")
    json.dump(rep, open(OUT, "w"), indent=2)
    print(json.dumps(rep, indent=2)); print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
