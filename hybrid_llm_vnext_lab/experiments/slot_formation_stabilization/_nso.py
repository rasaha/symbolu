"""Collision-proof loader for the FROZEN neural_slots_only harness modules.

Both experiments/phase_lc/models.py and experiments/neural_slots_only/models.py are named
`models`; in a shared test runner a bare `import models` can resolve to the wrong one. This loader
imports the neural harness's models/evaluate under UNIQUE module names from explicit file paths, so
the stabilization runner and tests always get the intended (Phase-free) S architecture and eval.
No frozen file is modified.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parents[1]
NEURAL = LAB / "experiments" / "neural_slots_only"
PHASE_LC = LAB.parent / "experiments" / "phase_lc"
for p in (str(LAB), str(NEURAL), str(PHASE_LC), str(HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load(alias, path):
    spec = importlib.util.spec_from_file_location(alias, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


# tasks_adapter is unique to the neural harness; register it under its bare name so that
# evaluate's internal `import tasks_adapter as TA` resolves to this same instance.
tasks_adapter = _load("tasks_adapter", NEURAL / "tasks_adapter.py")
models = _load("nso_models", NEURAL / "models.py")
evaluate = _load("nso_evaluate", NEURAL / "evaluate.py")
tasks = tasks_adapter.T  # the frozen phase_lc tasks module
