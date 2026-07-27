"""
state.py — bounded, sequence-length-independent recurrent state for Phase v3.

State = complex phase memory S ∈ [B, banks, H, Dh] (complex64) plus a real amplitude
accumulator R ∈ [B, banks, H, Dh] (float32) used only by the detached normalizer. Size
is independent of N (the whole point). Carries a position counter for streaming.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
from torch import Tensor


@dataclass
class PhaseV3State:
    complex_memory: Tensor    # [B, banks, H, Dh] complex64
    amplitude_sum: Tensor     # [B, banks, H, Dh] float32
    position: int = 0

    def numel(self) -> int:
        return self.complex_memory.numel() + self.amplitude_sum.numel()

    def detach(self) -> "PhaseV3State":
        return PhaseV3State(self.complex_memory.detach(),
                            self.amplitude_sum.detach(), self.position)

    def to(self, device) -> "PhaseV3State":
        return PhaseV3State(self.complex_memory.to(device),
                            self.amplitude_sum.to(device), self.position)

    @staticmethod
    def zeros(B: int, banks: int, H: int, Dh: int, device=None) -> "PhaseV3State":
        return PhaseV3State(
            complex_memory=torch.zeros(B, banks, H, Dh, dtype=torch.complex64, device=device),
            amplitude_sum=torch.zeros(B, banks, H, Dh, dtype=torch.float32, device=device),
            position=0)

    def state_bytes(self) -> int:
        # complex64 = 8 bytes, float32 = 4 bytes
        return self.complex_memory.numel() * 8 + self.amplitude_sum.numel() * 4


@dataclass
class PhaseV3Output:
    output: Tensor
    state: Optional[PhaseV3State] = None
    features: Optional[dict] = None       # probe features (state / raw readout / selective readout)
    diagnostics: Optional[dict] = None
