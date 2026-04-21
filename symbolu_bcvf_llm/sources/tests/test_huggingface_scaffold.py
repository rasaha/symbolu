"""§4.4 HuggingFaceSource scaffold tests — delayed-import discipline.

The scaffold should import cleanly (no torch/transformers needed
to import the module), fail with a clear RuntimeError when
instantiated without torch, and not be importable from the
kernel-level __init__ chain (§2.8.2 / §2.9 import-isolation).
"""

from __future__ import annotations

import importlib
import sys
from unittest import mock


def test_huggingface_source_module_imports_without_torch():
    """Importing the scaffold module must not require torch/transformers.

    The `TYPE_CHECKING` guard keeps the type-only imports behind a
    constant that is False at runtime; the runtime imports live
    inside `__init__` and method bodies and fire only on use.
    """
    # Save and remove any prior loads so the importlib re-executes
    # the module body.
    saved = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name.startswith("symbolu_bcvf_llm.sources")
    }
    for name in list(saved):
        del sys.modules[name]
    try:
        # Force an environment where torch / transformers are absent.
        with mock.patch.dict(sys.modules, {"torch": None, "transformers": None}):
            mod = importlib.import_module("symbolu_bcvf_llm.sources.huggingface")
            assert hasattr(mod, "HuggingFaceSource")
    finally:
        for name in list(sys.modules):
            if name.startswith("symbolu_bcvf_llm.sources"):
                del sys.modules[name]
        for name, val in saved.items():
            sys.modules[name] = val


def test_huggingface_source_constructor_raises_clearly_without_torch():
    """Instantiation should raise a RuntimeError that names torch/transformers."""
    # Re-import in an isolated environment where `torch` is blocked.
    saved = {
        name: sys.modules[name]
        for name in list(sys.modules)
        if name.startswith("symbolu_bcvf_llm.sources")
    }
    for name in list(saved):
        del sys.modules[name]
    prior_torch = sys.modules.get("torch")
    try:
        sys.modules["torch"] = None  # poison — `import torch` raises
        mod = importlib.import_module("symbolu_bcvf_llm.sources.huggingface")

        # Fabricate minimal dummy args; they never get used because
        # the constructor raises before touching them.
        class DummyModel:
            config = type("C", (), {"vocab_size": 8})()

            def parameters(self):
                raise AssertionError("should not be reached")

        class DummyTok:
            def __len__(self):
                return 8

            eos_token_id = None

            def encode(self, text, add_special_tokens=True):
                return [0, 1]

        import pytest

        with pytest.raises(RuntimeError, match="torch"):
            mod.HuggingFaceSource(
                model=DummyModel(),
                tokenizer=DummyTok(),
                prompt="hello",
                L=5,
            )
    finally:
        if prior_torch is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = prior_torch
        for name in list(sys.modules):
            if name.startswith("symbolu_bcvf_llm.sources"):
                del sys.modules[name]
        for name, val in saved.items():
            sys.modules[name] = val
