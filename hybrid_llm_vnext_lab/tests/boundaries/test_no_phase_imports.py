"""Boundary enforcement (AST-based) — the incubation core must not touch Phase or torch.

Runnable stdlib (uses the `ast` module). Enforces:
  * no src/ file imports any Phase implementation module or name;
  * the stdlib reference / baseline / instrumentation / contracts import NO torch (they must
    run without PyTorch);
  * the lab contains no packaging metadata (pyproject / wheel / setup).
"""
from __future__ import annotations

import ast
import pathlib

LAB_ROOT = pathlib.Path(__file__).resolve().parents[2]  # tests/boundaries/<file> -> lab root
SRC = LAB_ROOT / "src"

FORBIDDEN_PHASE = {
    "symbolu.phase_transformer",
    "symbolu_core.phase_transformer",
    "PhaseAttentionLayer",
    "HybridPhaseTransformer",
    "BindingCachePhaseState",
    "BindingCacheTransformer",
}

STDLIB_ONLY = {
    "binding_slots/slot_reference.py",
    "local_baseline/window_reference.py",
    "instrumentation/invariants.py",
    "instrumentation/probes.py",
    "contracts/memory.py",
}


def _imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    mods, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module)
            for a in node.names:
                names.add(a.name)
    return mods, names


def test_no_phase_imports_anywhere_in_src():
    offenders = []
    for py in sorted(SRC.rglob("*.py")):
        mods, names = _imports(py)
        hits = (mods | names) & FORBIDDEN_PHASE
        # also catch dotted phase modules defensively
        hits |= {m for m in mods if "phase_transformer" in m}
        if hits:
            offenders.append((py.relative_to(LAB_ROOT).as_posix(), sorted(hits)))
    assert not offenders, f"Phase imports found in src/: {offenders}"


def test_stdlib_modules_do_not_import_torch():
    offenders = []
    for rel in STDLIB_ONLY:
        mods, _ = _imports(SRC / rel)
        if any(m == "torch" or m.startswith("torch.") or m == "numpy" for m in mods):
            offenders.append(rel)
    assert not offenders, f"stdlib modules must not import torch/numpy: {offenders}"


def test_torch_modules_are_isolated_and_phase_free():
    # the two incubated torch copies may import torch, but must NOT import Phase
    for rel in ("binding_slots/legacy_phase_lc_slots.py", "binding_slots/bounded_binding_slots.py"):
        mods, names = _imports(SRC / rel)
        assert not ((mods | names) & FORBIDDEN_PHASE), f"{rel} imports Phase"
        assert not any("phase_transformer" in m for m in mods), f"{rel} imports phase_transformer"


def test_no_packaging_metadata_in_lab():
    forbidden = ["pyproject.toml", "setup.py", "setup.cfg"]
    present = [f for f in forbidden if (LAB_ROOT / f).exists()]
    assert not present, f"lab must not contain packaging metadata: {present}"
    # no wheel/sdist build artifacts either
    assert not list(LAB_ROOT.rglob("*.whl")), "lab must not contain wheels"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"boundaries: {len(fns)} passed")


if __name__ == "__main__":
    _run()
