# Test Collection Hygiene — Root Cause and Fix

*Phase 1 deliverable.*

## Original collision mechanism

Three independent, script-style research packages —
`execution_gate/`, `model_selection_pilot/`, `model_selection_experiment/` — each contained
top-level modules with **identical names**: `baselines`, `common`, `harness`, `metrics`,
`policy`, `registry`. Their test files bootstrapped imports with:

```python
PKG = os.path.dirname(HERE)
sys.path.insert(0, PKG)
import policy as pol        # bare, top-level name
```

Under pytest's default `prepend` import mode, Python's **global `sys.modules` cache** binds a
bare name like `policy` to whichever package imported it first. When all three suites were
collected in one process, the second and third suites received the *first* package's
`policy`/`common`/… — and, worse, **in-function ("late") imports** such as
`from common import TASK_CLASSES` inside a test helper resolved to the wrong package at call
time. Result: `ImportError`/`AttributeError` during collection and spurious failures at run
time. Each suite passed only when run alone.

Two isolation hacks (a root `pytest_collectstart` sys.modules eviction, and per-package
autouse fixtures) were tried and rejected: they could not correct late in-function imports
without fighting each other across the collection vs. call phases. The correct fix is
**unambiguous module identities**.

## Fix (package-qualified imports; no scientific logic changed)

1. Added `__init__.py` to each package and each `tests/` directory, making them real
   packages with unique dotted identities.
2. Converted every **intra-package sibling import** (in modules and test files) from bare
   top-level form to absolute package-qualified form:
   - `import policy as pol` → `from model_selection_pilot import policy as pol`
   - `from common import X` → `from model_selection_pilot.common import X`
   Only import statements changed; **no scientific logic was touched**.
3. Set `--import-mode=importlib` in `pyproject.toml [tool.pytest.ini_options] addopts`.
4. Standalone scripts now run as modules: `python3 -m execution_gate.harness` (and likewise
   for the pilot/experiment harnesses) instead of `python3 harness.py`.

**Behavior preservation verified:** `execution_gate/results/evaluation.json` is byte-identical
after the refactor; the pilot harness reproduces the same SELF_TEST cost-guard figure
($1.3594); the experiment harness reproduces the same mature-regime numbers
(`dRegret=-0.0066`, `dQok=0.027`). The refactor is packaging-only.

## Files changed

27 files (import lines only) across the three packages + their test files, plus 6 new
`__init__.py` files and the `addopts` line in `pyproject.toml`. No frozen scientific logic,
data, thresholds, scorers, or results were modified.

## Commands and counts

**Root-level command that now succeeds for the three research suites:**

```
python3 -m pytest execution_gate/tests model_selection_pilot/tests model_selection_experiment/tests
```

- Together: **53 passed** (previously: collection errors).
- Individually: execution_gate **21**, model_selection_pilot **17**, model_selection_experiment **15**.
- Skipped/xfailed: **0**. Remaining warnings: none from these suites.

## Out of scope (not masked)

Plain `pytest` from the repository root also collects the pre-existing `tests/` tree
(`testpaths = ["tests"]`), which has **146 collection errors** and ~11,949 tests. These errors
are **pre-existing and unrelated** to the packaging collision (missing optional dependencies
in `tests/unit/ontology/`, `tests/unit/tools/`, mechanical pipeline, etc.). They predate this
research track. Per the requirement not to suppress legitimate failures, they are **left
visible and untouched** — they are a separate maintenance concern, not part of this
packaging fix. The `--import-mode=importlib` default is a safe, general improvement and does
not hide them.
