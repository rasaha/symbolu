"""Tests for the guarded A′ readiness entrypoint (no A′ execution).

    python3 experiments/a_prime/test_readiness.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from common import config as cfgmod          # noqa: E402
from run_a_prime import check_readiness       # noqa: E402


def _check(name: str, ok: bool) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        raise AssertionError(name)


def test_default_is_not_run() -> None:
    r = check_readiness(cfgmod.AprimeConfig())
    _check("default config -> NOT_RUN", r["status"] == "NOT_RUN")
    _check("missing lists E/Y/phonology + license", len(r["missing"]) == 4)


def test_partial_still_not_run() -> None:
    with tempfile.TemporaryDirectory() as d:
        e = Path(d) / "e.csv"; e.write_text("x")
        cfg = cfgmod.AprimeConfig(e_path=str(e), license_acknowledged=True)
        r = check_readiness(cfg)
        _check("partial inputs -> NOT_RUN", r["status"] == "NOT_RUN")
        _check("Y and phonology still flagged missing", len(r["missing"]) == 2)


def test_complete_is_ready_but_gated() -> None:
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for k in ("e", "y", "phon"):
            p = Path(d) / f"{k}.csv"; p.write_text("x"); paths[k] = str(p)
        cfg = cfgmod.AprimeConfig(e_path=paths["e"], y_path=paths["y"],
                                  phonology_path=paths["phon"], license_acknowledged=True)
        r = check_readiness(cfg)
        _check("complete + licensed -> READY_BUT_GATED", r["status"] == "READY_BUT_GATED")
        _check("no missing inputs", r["missing"] == [])


def test_license_required() -> None:
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for k in ("e", "y", "phon"):
            p = Path(d) / f"{k}.csv"; p.write_text("x"); paths[k] = str(p)
        cfg = cfgmod.AprimeConfig(e_path=paths["e"], y_path=paths["y"],
                                  phonology_path=paths["phon"], license_acknowledged=False)
        r = check_readiness(cfg)
        _check("inputs present but no license -> NOT_RUN", r["status"] == "NOT_RUN")
        _check("license flagged", any("license" in m for m in r["missing"]))


def main() -> None:
    print("A′ readiness guard tests (no A′ execution)\n")
    test_default_is_not_run()
    test_partial_still_not_run()
    test_complete_is_ready_but_gated()
    test_license_required()
    print("\nAll readiness-guard tests passed. A′ not executed; guard returns NOT_RUN by default.")


if __name__ == "__main__":
    main()
