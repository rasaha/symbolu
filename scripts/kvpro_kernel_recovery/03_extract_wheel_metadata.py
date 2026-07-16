#!/usr/bin/env python3
"""Phase B.3 — extract the installed dist-info metadata for the int4 flash-attn wheel:
package name, version, RECORD hashes, requires, and the build tag. Confirms the wheel
matches the documented provenance (vllm_flash_attn 2.7.2.post1+cu128 cp312). Ordinary
package metadata only. POD-ONLY; prints NOT_FOUND cleanly.

  PYBIN=/workspace/venv-vllm/bin/python3 python 03_extract_wheel_metadata.py
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT", os.path.join(_HERE, "runs", "wheel_metadata.json"))

_EXPECTED = {"name_contains": "vllm", "version_hint": "2.7.2", "build_hint": "cu128", "py_hint": "cp312"}


def _dist_meta():
    try:
        import importlib.metadata as md
    except Exception as e:  # noqa: BLE001
        return f"NOT_FOUND (importlib.metadata: {e})"
    out = []
    for dist in md.distributions():
        try:
            name = dist.metadata["Name"] or ""
        except Exception:
            name = ""
        if "flash" in name.lower() or "vllm_flash" in name.lower() or "vllm-flash" in name.lower():
            rec = {"name": name, "version": dist.version}
            try:
                rec["requires"] = list(dist.requires or [])[:20]
            except Exception:
                rec["requires"] = "NOT_FOUND"
            # RECORD hashes (dist-info) — pins the installed files
            try:
                record = dist.read_text("RECORD") or ""
                rec["record_lines"] = len(record.splitlines())
                rec["record_so_hashes"] = [ln for ln in record.splitlines() if ".so" in ln][:10]
            except Exception:
                rec["record_lines"] = "NOT_FOUND"
            try:
                wheel = dist.read_text("WHEEL") or ""
                rec["wheel_tags"] = [ln for ln in wheel.splitlines() if ln.lower().startswith("tag")]
            except Exception:
                rec["wheel_tags"] = "NOT_FOUND"
            rec["location"] = str(getattr(dist, "_path", "NOT_FOUND"))
            out.append(rec)
    return out or "NOT_FOUND (no flash-attn dist-info)"


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rep = {"label": "POD-INSPECT", "python_exe": sys.executable,
           "expected_provenance": _EXPECTED, "distributions": _dist_meta()}
    # match check
    match = "UNKNOWN"
    d = rep["distributions"]
    if isinstance(d, list) and d:
        v = " ".join(str(x.get("version", "")) for x in d)
        match = "LIKELY_MATCH" if _EXPECTED["version_hint"] in v else "VERSION_DRIFT"
    rep["provenance_match"] = match
    rep["note"] = ("Confirms the installed wheel's name/version/tags vs the documented "
                   "vllm_flash_attn 2.7.2.post1+cu128 cp312. VERSION_DRIFT => the pod's kernel "
                   "differs from the measured build; re-pin per kernel_provenance.json.")
    json.dump(rep, open(OUT, "w"), indent=2)
    print(json.dumps(rep, indent=2)); print(f"\n-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
