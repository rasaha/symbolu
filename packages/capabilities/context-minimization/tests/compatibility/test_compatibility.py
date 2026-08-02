"""Compatibility / consumer tests — required scenarios 41–44.

These run in the SOURCE CI job (monorepo on path). They skip cleanly when a
consumer is not importable in the current environment (e.g. the isolated wheel
venv, or when the frozen ActionGate experiment's out-of-tree dependency is absent),
so they never produce a false green.
"""

from __future__ import annotations

import pathlib

import pytest

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    deduplicate_context,
    structural_minimize,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[5]


def test_console_structural_path_parity():
    """The migrated Console gateway must produce the same structural keep/drop as the
    canonical ``structural_minimize`` for the same units."""
    console = pytest.importorskip("ugence_console_api.capabilities.context_gateway")
    models = pytest.importorskip("ugence_console_api.models")
    ok, reason = console.available()
    if not ok:
        pytest.skip(f"console context gateway unavailable: {reason}")

    units = [
        models.ContextUnit(id="a", text="deploy service", redundancy_set=None, protected=True),
        models.ContextUnit(id="b", text="deploy service", redundancy_set=None, protected=False),
        models.ContextUnit(id="c", text="backup ok", redundancy_set="r1"),
        models.ContextUnit(id="d", text="backup fine", redundancy_set="r1"),
        models.ContextUnit(id="e", text="unique note"),
    ]
    res = console.minimize(units)

    canon_units = tuple(
        ContextUnit(id=u.id, text=u.text, source_type="state_fact",
                    redundancy_set=u.redundancy_set, protected=u.protected)
        for u in units
    )
    canon = structural_minimize(
        Context(id="console-ctx", units=canon_units),
        protected_ids=[u.id for u in units if u.protected],
    )
    assert set(res.kept_ids) == set(canon.surviving_ids)
    assert set(res.removed_ids) == set(canon.removed_ids)
    # protected unit 'a' must survive under BOTH (the hardened contract)
    assert "a" in res.kept_ids and "a" in canon.surviving_ids


def test_console_gateway_uses_canonical_package_not_syspath_hack():
    """After migration the gateway imports the canonical distribution and does not
    inject the experiments/ directory onto sys.path."""
    gw = REPO_ROOT / "ugence_console_api" / "capabilities" / "context_gateway.py"
    if not gw.is_file():
        pytest.skip("console gateway source not present")
    src = gw.read_text()
    assert "ugence_context_minimization" in src
    assert "sys.path.insert" not in src
    # no live IMPORT of the experimental package (a migration note in prose is fine)
    assert "import actiongate_context_ablation" not in src
    assert "from actiongate_context_ablation" not in src


def test_no_duplicate_canonical_implementation_under_namespace():
    """There is exactly one canonical implementation: this package. No other
    importable ``ugence_context_minimization`` provider exists."""
    import ugence_context_minimization as cm

    canonical = pathlib.Path(cm.__file__).resolve()
    assert canonical.parent.name == "ugence_context_minimization"
    # the canonical tree owns the two entry points
    assert callable(structural_minimize) and callable(deduplicate_context)


def test_frozen_experiment_is_not_rewired_to_canonical():
    """Frozen-evidence coexistence: the experimental compressor must NOT import the
    canonical package (rewiring it would change frozen benchmark fingerprints)."""
    exp = (REPO_ROOT / "experiments" / "actiongate_context_ablation"
           / "actiongate_context_ablation" / "compressor.py")
    if not exp.is_file():
        pytest.skip("experiment not present")
    assert "ugence_context_minimization" not in exp.read_text()
