"""Generate a run manifest: identity, environment, frozen fingerprint, checksums.

The manifest ties a result set to the exact code (frozen fingerprint + git commit),
model (id + revision), config, and content checksums, so a result archive is
self-describing and tamper-evident. No secrets are included.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import runpod_common as RC


def _sha256(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def build_manifest(config=None) -> dict:
    config = config or RC.load_config()
    rd = RC.run_dir(config)
    recs = RC.read_records(RC.records_path(config))
    cfg_path = RC.config_path(config)
    run_cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}

    by_cell = {}
    for r in recs:
        by_cell.setdefault(f"{r['method']}@{r['budget']}", 0)
        by_cell[f"{r['method']}@{r['budget']}"] += 1

    checksums = {}
    for f in sorted(rd.glob("*")):
        if f.is_file() and f.name != "run_manifest.json":
            checksums[f.name] = _sha256(f)

    return {
        "run_id": config["run_id"],
        "run_kind": config["run_kind"],
        "model_id": config["model_id"],
        "model_revision": run_cfg.get("model_revision", "unknown"),
        "git": RC.git_state(),
        "frozen_fingerprint": RC.frozen_fingerprint()["fingerprint"],
        "actiongate_policy": RC.frozen_fingerprint()["policy"],
        "run_config": run_cfg,
        "n_records": len(recs),
        "records_per_cell": by_cell,
        "is_real": bool(recs) and all(r.get("is_real") for r in recs),
        "checksums": checksums,
        "note": ("SMOKE_ONLY / mock records are non-scientific."
                 if (config["run_kind"] == RC.RUN_KIND_SMOKE
                     or not (recs and all(r.get("is_real") for r in recs))) else ""),
    }


def main():
    config = RC.load_config()
    m = build_manifest(config)
    outp = RC.run_dir(config) / "run_manifest.json"
    RC.write_json_atomic(outp, m)
    print(f"wrote {outp}  (records={m['n_records']} is_real={m['is_real']})")


if __name__ == "__main__":
    main()
