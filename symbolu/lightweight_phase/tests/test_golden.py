"""Freeze gate — current code must reproduce the frozen golden vectors bit-for-bit
(to 1e-5 rounding). A silent change to frozen forward behavior fails here.

If a change is intentional, it requires a version bump + regenerating goldens via
``python -m symbolu.lightweight_phase.freeze --write`` (see freeze discipline in
the stage reports).
"""

from pathlib import Path

import pytest
import torch

from symbolu.lightweight_phase import freeze

GOLDEN = Path(freeze.__file__).resolve().parent / "golden_vectors.pt"


@pytest.mark.skipif(not GOLDEN.exists(), reason="golden vectors not generated")
def test_manifest_source_hashes_and_goldens_match():
    assert freeze.verify(), "freeze drift detected — see stdout"


@pytest.mark.skipif(not GOLDEN.exists(), reason="golden vectors not generated")
def test_phase_core_reproduces_golden_output():
    raw = torch.load(GOLDEN, weights_only=True)
    golden = freeze.build_golden()
    # exact-to-tolerance reproduction of the Stage 1 output
    assert torch.allclose(golden["v1.0-phase-core"]["raw"]["out1"],
                          raw["v1.0-phase-core::out1"], atol=1e-5)
    assert torch.allclose(golden["v1.3-transformer"]["raw"]["logits"],
                          raw["v1.3-transformer::logits"], atol=1e-5)
