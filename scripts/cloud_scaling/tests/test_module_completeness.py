"""The module-completeness gate: discovery reconciled against declaration.

``module_order`` used to be a curated list nothing checked. Five flat adopters could
survive that by eyeball; a nested package cannot — a module added under ``planning/``
after adoption would have escaped the inventory silently, and the sweep would have kept
publishing coverage over a package that had quietly grown past it. The gate rules
(2026-08-31): every discovered production module is either walked by the inventory or
excluded with a concrete reason, and anything else fails the run.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SWEEP = REPO / "scripts" / "cloud_scaling" / "guard_sweep.py"

_spec = importlib.util.spec_from_file_location("_guard_sweep_completeness", SWEEP)
guard_sweep = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = guard_sweep
_spec.loader.exec_module(guard_sweep)


def _config(tmp_path, monkeypatch, **overrides):
    src = tmp_path / "pkg" / "src" / "synthetic"
    src.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(guard_sweep, "REPO", tmp_path)
    fields = dict(
        key="synthetic",
        package_dir="pkg",
        dist_name="synthetic",
        mint_site="",
        module_order=(),
        refusal_calls=frozenset(),
        tuple_refusals=False,
        recorded=(),
    )
    fields.update(overrides)
    return guard_sweep.PackageConfig(**fields), src


def test_discovery_is_recursive(tmp_path, monkeypatch):
    config, src = _config(tmp_path, monkeypatch)
    (src / "top.py").write_text("x = 1\n", encoding="utf-8")
    (src / "planning").mkdir()
    (src / "planning" / "__init__.py").write_text("", encoding="utf-8")
    (src / "planning" / "deep.py").write_text("y = 2\n", encoding="utf-8")
    assert guard_sweep._production_modules(config) == (
        "planning/__init__.py",
        "planning/deep.py",
        "top.py",
    )


def test_an_undeclared_module_is_a_failure_not_a_note(tmp_path, monkeypatch):
    config, src = _config(tmp_path, monkeypatch, module_order=("top.py",))
    (src / "top.py").write_text("x = 1\n", encoding="utf-8")
    (src / "later.py").write_text("y = 2\n", encoding="utf-8")
    problems = guard_sweep.undeclared_modules(config)
    assert problems["undeclared"] == ["later.py"]


def test_every_disagreement_kind_is_named(tmp_path, monkeypatch):
    config, src = _config(
        tmp_path,
        monkeypatch,
        module_order=("top.py", "gone.py", "both.py"),
        excluded_modules={
            "both.py": "also ordered",
            "phantom.py": "names no file",
            "silent.py": "   ",
        },
    )
    for name in ("top.py", "both.py", "silent.py"):
        (src / name).write_text("x = 1\n", encoding="utf-8")
    problems = guard_sweep.undeclared_modules(config)
    assert problems["missing"] == ["gone.py"]
    assert problems["orphan_exclusions"] == ["phantom.py"]
    assert problems["double_listed"] == ["both.py"]
    assert problems["unreasoned_exclusions"] == ["silent.py"]
    assert problems["undeclared"] == []


def test_a_declared_package_reconciles_clean(tmp_path, monkeypatch):
    config, src = _config(
        tmp_path,
        monkeypatch,
        module_order=("top.py",),
        excluded_modules={"version.py": "the version constant; zero guards"},
    )
    (src / "top.py").write_text("x = 1\n", encoding="utf-8")
    (src / "version.py").write_text("__version__ = '1'\n", encoding="utf-8")
    assert all(not v for v in guard_sweep.undeclared_modules(config).values())


def test_every_adopter_reconciles_clean():
    """The gate is retroactive: all five ruled adopters must already satisfy it.

    Their ``excluded_modules`` entries were written from a measurement (zero
    refusal-shaped guards and zero raises in every excluded module), not from
    confidence; this pins that the declarations and the trees stay reconciled.
    """

    for key, config in guard_sweep.PACKAGES.items():
        problems = {
            kind: entries
            for kind, entries in guard_sweep.undeclared_modules(config).items()
            if entries
        }
        assert not problems, f"{key}: {problems}"


def test_every_excluded_adopter_module_reason_still_holds():
    """The exclusions' stated reason, measured rather than trusted — and there are two
    kinds of reason making two different checkable claims.

    A flat adopter's exclusion says "nothing here": zero refusal-shaped guards and
    zero raises, as before. A *phased* adopter's exclusion (the controller's, ruling 3)
    says "deferred, and here is its measured refusal surface": the module is outside
    the phase boundary and its reason discloses the raise count. For those, the
    checkable claim is that the disclosed count still matches the tree — a deferred
    module that grows a refusal gains it silently unless the number is re-measured, so
    a drifted count fails here and forces the disclosure (and the phase plan) to be
    updated rather than trusted."""

    import ast
    import re

    for key, config in guard_sweep.PACKAGES.items():
        visible, _ = guard_sweep._helper_analysis(config)
        for module, reason in config.excluded_modules.items():
            tree = ast.parse((config.src / module).read_text(encoding="utf-8"))
            raises = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Raise))
            deferred = re.search(
                r"deferred to a later ratified.*carries (\d+) raise statements", reason
            )
            if deferred:
                declared = int(deferred.group(1))
                assert raises == declared, (
                    f"{key}:{module} discloses {declared} raise statements but the "
                    f"tree carries {raises}; the deferred surface drifted and the "
                    "disclosure (and the phase plan) must be re-measured"
                )
                continue
            shaped = sum(
                1
                for n in ast.walk(tree)
                if isinstance(n, ast.If)
                and guard_sweep._refusal_shape(n, config, visible[module])
            )
            assert raises == 0 and shaped == 0, (
                f"{key}:{module} carries {shaped} refusal-shaped guards and {raises} "
                "raises; its exclusion reason no longer holds"
            )
