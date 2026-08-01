"""Execute every canonical example and assert it succeeds.

Loads each `examples/*.py` module and runs its `main()`, asserting a 0 exit.
Guarantees the examples stay runnable against the public API as the package
evolves. (The distribution verifier additionally runs them against the installed
wheel.)
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

EXAMPLES_DIR = pathlib.Path(__file__).resolve().parents[2] / "examples"
EXAMPLES = sorted(p.name for p in EXAMPLES_DIR.glob("*.py"))


def _load(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(f"_example_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_examples_present():
    assert set(EXAMPLES) == {
        "minimal_story_evaluation.py", "proposed_action_evaluation.py",
        "policy_pack_compilation.py", "replay_smoke.py"}


@pytest.mark.parametrize("name", EXAMPLES)
def test_example_runs(name):
    module = _load(EXAMPLES_DIR / name)
    assert hasattr(module, "main"), f"{name} has no main()"
    assert module.main() == 0, name
