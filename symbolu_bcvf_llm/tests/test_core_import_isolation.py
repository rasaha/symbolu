"""§2.8.2 / §2.9.4 tests 48–49: dependency isolation.

The kernel must import cleanly in environments where torch,
transformers, and datasets are absent. These tests block those
modules from sys.modules at the Python level and verify import still
works.
"""

from __future__ import annotations

import importlib
import sys


def _reimport_kernel_without(blocked: tuple[str, ...]) -> None:
    saved_blocked = {name: sys.modules.get(name) for name in blocked}
    saved_kernel = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name.startswith("symbolu_bcvf_llm")
    }
    try:
        for name in blocked:
            sys.modules[name] = None  # poison — any `import name` raises
        for name in list(saved_kernel):
            del sys.modules[name]
        importlib.import_module("symbolu_bcvf_llm.core")
    finally:
        for name, value in saved_blocked.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
        for name in list(sys.modules):
            if name.startswith("symbolu_bcvf_llm"):
                del sys.modules[name]
        for name, value in saved_kernel.items():
            sys.modules[name] = value


def test_kernel_import_without_torch():
    _reimport_kernel_without(("torch",))


def test_kernel_import_without_transformers():
    _reimport_kernel_without(("transformers",))
