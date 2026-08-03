#!/usr/bin/env python3
"""Run all stdlib (torch-free) lab tests without pytest.

Discovers tests/**/test_*.py, imports each, runs its test_* functions, and reports.
The torch parity test self-reports RESOURCE_BLOCKED and does not fail the run.
Exit code is nonzero if any assertion fails.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import traceback

LAB_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB_ROOT))
TESTS = LAB_ROOT / "tests"

# torch-dependent files that must not fail the stdlib run (they self-skip)
TORCH_DEPENDENT = {"tests/parity/test_torch_reference_parity.py"}


def _load(path: pathlib.Path):
    # ensure each test dir is importable and _lab is resolvable
    sys.path.insert(0, str(path.parent))
    sys.path.insert(0, str(TESTS))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    total, failed = 0, 0
    for path in sorted(TESTS.rglob("test_*.py")):
        rel = path.relative_to(LAB_ROOT).as_posix()
        torch_dep = rel in TORCH_DEPENDENT
        try:
            mod = _load(path)
        except Exception:
            print(f"IMPORT-FAIL {rel}")
            traceback.print_exc()
            failed += 1
            continue
        fns = [(k, v) for k, v in vars(mod).items()
               if k.startswith("test_") and callable(v)]
        for name, fn in fns:
            total += 1
            try:
                fn()
            except NotImplementedError:
                if torch_dep:
                    print(f"  SKIP {rel}::{name} (RESOURCE_BLOCKED: torch)")
                    total -= 1
                    continue
                failed += 1
                print(f"  FAIL {rel}::{name} (NotImplementedError)")
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f"  FAIL {rel}::{name}: {e}")
                traceback.print_exc()
        print(f"ok {rel} ({len(fns)} fns)")
    print(f"\nstdlib tests: {total} run, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
