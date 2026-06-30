"""Guarded B0 entrypoint (PREREG_VARNA_PHONETIC_ALIGNMENT.md).

Loads the §17 frozen manifest, verifies every pinned sha256, validates the run
schema is loadable, and refuses to run unless ALL primary artifacts are frozen —
including the PRIMARY verdict-setting encoding **T_embed**. The categorical
encoding **T_cat** is sensitivity-only and can never substitute as primary.

This runner performs the GATING only. Even when the gate reports `ready`, the
alignment computation itself is intentionally NOT implemented here (a separate,
approval-gated step), so the runner still returns NOT_RUN — it never computes or
reports a T-vs-P alignment or a verdict. Stage A is untouched.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import manifest as MF  # noqa: E402


def _not_run(reason: str, readiness: dict | None = None) -> dict:
    out = {"status": "NOT_RUN", "reason": reason,
           "computed_alignment": False, "verdict": None}
    if readiness is not None:
        out["readiness"] = readiness
    return out


def run(manifest_path=None) -> dict:
    """Gate a B0 run from the frozen manifest. Always returns a status dict.

    NEVER computes alignment or emits a verdict. Returns NOT_RUN when the gate is
    not ready (missing/mismatched hashes, or T_embed not frozen) AND also when the
    gate IS ready (alignment computation is a separate approval-gated step).
    """
    try:
        m = MF.load_manifest() if manifest_path is None else MF.load_manifest(manifest_path)
    except FileNotFoundError:
        return _not_run("frozen manifest not found (PREREG §17 not frozen)")
    except json.JSONDecodeError as e:
        return _not_run(f"frozen manifest is not valid JSON: {e}")

    # the run schema must at least be loadable/parseable before any run
    try:
        MF.load_schema()
    except Exception as e:  # noqa: BLE001
        return _not_run(f"run-manifest schema unloadable: {e}")

    readiness = MF.check_readiness(m)
    if not readiness["ready"]:
        return _not_run("gate not ready: " + "; ".join(readiness["reasons"]), readiness)

    # Gate is READY (all hashes verified, T_embed frozen). The alignment path is
    # deliberately not implemented in the loader-wiring step: still NOT_RUN.
    return _not_run("all primary artifacts frozen and verified; alignment "
                    "computation not implemented in loader wiring (approval-gated)",
                    readiness)


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
