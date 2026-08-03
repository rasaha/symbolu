"""Boundary: the slots-only (S) neural experiment imports NO Phase anywhere. Stdlib (ast)."""
from __future__ import annotations

import ast
import pathlib

LAB = pathlib.Path(__file__).resolve().parents[2]
S_EXP = LAB / "experiments" / "neural_slots_only"

FORBIDDEN = {
    "symbolu.phase_transformer", "symbolu_core.phase_transformer",
    "PhaseAttentionLayer", "HybridPhaseTransformer", "BindingCachePhaseState",
    "BindingCacheTransformer", "RealPhase", "PhaseAttn", "PhaseLocal",
}


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    mods, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)
            names |= {a.name for a in node.names}
    return mods, names


def test_slots_only_experiment_is_phase_free():
    offenders = []
    for py in sorted(S_EXP.glob("*.py")):
        mods, names = _imports(py)
        hits = (mods | names) & FORBIDDEN
        hits |= {m for m in mods if "phase_transformer" in m}
        if hits:
            offenders.append((py.name, sorted(hits)))
    assert not offenders, f"Phase imports in slots-only experiment: {offenders}"


def test_s_model_uses_incubated_slots():
    src = (S_EXP / "models.py").read_text()
    assert "legacy_phase_lc_slots import BindingSlots" in src, \
        "S model must use the incubated Phase-free BindingSlots"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"slots-only-no-phase: {len(fns)} passed")


if __name__ == "__main__":
    _run()
