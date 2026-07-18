"""Guarded runner — consults the readiness gate; always NOT_RUN in this task.

Calls manifest.check_readiness. Returns NOT_RUN unless the frozen bundle is READY — AND
even when READY, still returns NOT_RUN because real experiment execution is not implemented
yet. Computes no scores, loads no embeddings, calls no network/LLM, reads no real data
(the default frozen dir does not exist), writes no result artifacts. Stage A not imported.
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import manifest as MF  # noqa: E402

DEFAULT_FROZEN_DIR = _HERE / "frozen"


def run(frozen_dir=None) -> dict:
    frozen_dir = pathlib.Path(frozen_dir) if frozen_dir is not None else DEFAULT_FROZEN_DIR
    if not frozen_dir.exists():
        return {"status": "NOT_RUN", "reason": "no frozen bundle (synthetic scaffold only)",
                "computed": False, "result": None,
                "readiness": {"status": "NOT_READY", "reasons": ["frozen dir missing"]}}

    readiness = MF.check_readiness(frozen_dir)
    if readiness["status"] != "READY":
        return {"status": "NOT_RUN",
                "reason": "readiness gate NOT_READY: " + "; ".join(readiness["reasons"]),
                "computed": False, "result": None, "readiness": readiness}

    # Gate READY, but experiment execution is intentionally NOT implemented in this task.
    return {"status": "NOT_RUN",
            "reason": "bundle READY but experiment execution is not implemented (validation-only task)",
            "computed": False, "result": None, "readiness": readiness}


if __name__ == "__main__":
    import json
    print(json.dumps(run(), indent=2))
