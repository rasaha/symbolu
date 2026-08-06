from __future__ import annotations

import importlib
import random

import torch


def test_package_import_does_not_advance_python_or_torch_rng():
    random.seed(24680)
    torch.manual_seed(24680)
    python_before = random.getstate()
    torch_before = torch.random.get_rng_state().clone()
    module = importlib.import_module("experiments.single_hop_typed_vs_prose")
    importlib.reload(module)
    assert random.getstate() == python_before
    assert torch.equal(torch.random.get_rng_state(), torch_before)
