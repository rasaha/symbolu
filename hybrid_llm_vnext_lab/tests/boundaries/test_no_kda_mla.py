"""Boundary: the lab contains no KDA / MLA / Gated-DeltaNet / Mamba / MoE implementation. Stdlib.

This phase is slots-only; the modern recurrent core is a later, separate phase. Enforced by a
token scan of lab source (imports + class/def names), excluding audit/doc prose that legitimately
*names* these architectures.
"""
from __future__ import annotations

import ast
import pathlib

LAB = pathlib.Path(__file__).resolve().parents[2]
SRC_DIRS = [LAB / "src", LAB / "experiments" / "neural_slots_only", LAB / "experiments" / "five_seed_slots"]

FORBIDDEN_NAMES = {"KimiDeltaAttention", "KDA", "MLA", "MultiHeadLatentAttention",
                   "GatedDeltaNet", "Mamba", "Mamba2", "MambaMixer", "MoE",
                   "gated_deltanet", "kimi_delta", "mamba_ssm"}


def _defs_and_imports(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
            names |= {a.name for a in node.names}
    return names


def test_no_kda_mla_implementation_in_lab_source():
    offenders = []
    for d in SRC_DIRS:
        if not d.exists():
            continue
        for py in sorted(d.rglob("*.py")):
            names = _defs_and_imports(py)
            hits = names & FORBIDDEN_NAMES
            hits |= {n for n in names if any(t in n for t in ("mamba", "gated_deltanet", "kimi_delta"))}
            if hits:
                offenders.append((py.relative_to(LAB).as_posix(), sorted(hits)))
    assert not offenders, f"KDA/MLA/Mamba implementation found in lab source: {offenders}"


def _run():
    test_no_kda_mla_implementation_in_lab_source()
    print("no-kda-mla: 1 passed")


if __name__ == "__main__":
    _run()
