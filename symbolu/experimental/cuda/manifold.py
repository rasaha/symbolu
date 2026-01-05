"""
SymbolU12 Manifold - Python Orchestrator
=========================================

High-level Python class for managing the 124-dimensional cognitive manifold.
Handles initialization, state evolution, and Sattvic Seal generation.

Features:
    - Ghost Buffer (S_prev) management for temporal tracking
    - Sattvic Seed (S_0) initialization
    - Automatic CUDA/CPU dispatch
    - Cryptographic Sattvic Seal for integrity proof

Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30.16, 30.25
"""

import hashlib
import base64
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple
from enum import IntFlag

import torch
import torch.nn as nn

# Try to import the CUDA extension
try:
    import symbol_u12_cuda
    _CUDA_EXT_AVAILABLE = True
except ImportError:
    _CUDA_EXT_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

MANIFOLD_DIM = 124  # [Phoneme(44), Topic(64), Ontology(12), Dynamics(4)]
R_BLOCK_SIZE = 9    # 3x3 rotation matrix flattened

# Integrity flags (must match symbol_u12_types.h)
class IntegrityFlag(IntFlag):
    OK = 0x00
    COHERENCE_FAILURE = 0x01
    MOTION_OVERDRIVE = 0x02
    TRACE_COLLAPSE = 0x04
    ENTROPY_SPIKE = 0x08


# =============================================================================
# SATTVIC SEAL
# =============================================================================

@dataclass
class SattvicSeal:
    """Cryptographic proof of axiomatic integrity."""
    trace_score: float
    coherence_score: float
    motion_score: float
    entropy_score: float
    state_hash: str
    anchor_id: str
    seal: str
    integrity_flags: int
    verified: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'trace_score': self.trace_score,
            'coherence_score': self.coherence_score,
            'motion_score': self.motion_score,
            'entropy_score': self.entropy_score,
            'state_hash': self.state_hash,
            'anchor_id': self.anchor_id,
            'seal': self.seal,
            'integrity_flags': self.integrity_flags,
            'verified': self.verified,
            'timestamp': self.timestamp,
        }

    @property
    def status(self) -> str:
        """Human-readable status."""
        if self.verified:
            return "VERIFIED"
        flags = IntegrityFlag(self.integrity_flags)
        return f"BREACH: {flags.name}"


def generate_sattvic_seal(
    manifold_state: torch.Tensor,
    text_output: str,
    trace_score: float,
    coherence_score: float,
    motion_score: float,
    entropy_score: float,
    integrity_flags: int,
    anchor_id: str = "S0_DEFAULT_V1"
) -> SattvicSeal:
    """
    Generate cryptographic proof of axiomatic integrity.

    Args:
        manifold_state: Final S_t state tensor [124] or [B, 124]
        text_output: Generated text response
        trace_score: R-Matrix integrity score
        coherence_score: Cosine similarity to S_0
        motion_score: Euclidean velocity
        entropy_score: Information disorder
        integrity_flags: Bitmask of integrity violations
        anchor_id: Identifier for the S_0 seed

    Returns:
        SattvicSeal with cryptographic proof
    """
    # Handle batched input
    if manifold_state.dim() == 2:
        manifold_state = manifold_state[0]

    # 1. Geometric fingerprint of the thought
    state_bytes = manifold_state.detach().cpu().numpy().tobytes()
    state_hash = hashlib.sha256(state_bytes).hexdigest()

    # 2. Integrity payload
    payload = {
        "state_hash": state_hash,
        "trace": f"{trace_score:.6f}",
        "coherence": f"{coherence_score:.6f}",
        "motion": f"{motion_score:.6f}",
        "entropy": f"{entropy_score:.6f}",
        "flags": integrity_flags,
        "anchor_id": anchor_id,
        "text_hash": hashlib.sha256(text_output.encode()).hexdigest()
    }

    # 3. Generate seal
    payload_str = json.dumps(payload, sort_keys=True)
    seal_hash = hashlib.sha256(payload_str.encode()).digest()
    seal = base64.b64encode(seal_hash).decode()

    return SattvicSeal(
        trace_score=trace_score,
        coherence_score=coherence_score,
        motion_score=motion_score,
        entropy_score=entropy_score,
        state_hash=state_hash[:16] + "...",
        anchor_id=anchor_id,
        seal=f"SATTVIC_SEAL:{seal}",
        integrity_flags=integrity_flags,
        verified=(integrity_flags == 0),
    )


# =============================================================================
# SYMBOLU12 MANIFOLD
# =============================================================================

class SymbolU12Manifold(nn.Module):
    """
    124-dimensional cognitive manifold with Ghost Buffer and Sattvic Anchor.

    The manifold maintains:
        - S_0: Immutable Sattvic Seed (ground truth anchor)
        - S_t: Current live state
        - S_prev: Ghost Buffer for temporal motion tracking
        - R_block: R-Matrix for geometric integrity

    Uses register_buffer to ensure tensors move with model but aren't optimized.
    """

    def __init__(
        self,
        dim: int = MANIFOLD_DIM,
        batch_size: int = 1,
        device: Optional[torch.device] = None,
        anchor_id: str = "S0_DEFAULT_V1"
    ):
        super().__init__()
        self.dim = dim
        self.batch_size = batch_size
        self.anchor_id = anchor_id
        self._device = device or torch.device('cpu')

        # 1. FIXED ANCHOR: The Sattvic Seed (immutable ground truth)
        self.register_buffer("S_0", torch.zeros(batch_size, dim))

        # 2. GHOST BUFFER: Previous state for Motion calculation
        self.register_buffer("S_prev", torch.zeros(batch_size, dim))

        # 3. LIVE STATE: Current manifold position
        self.register_buffer("S_t", torch.zeros(batch_size, dim))

        # 4. R-BLOCK: Flattened R_int @ R_ext^T for integrity check
        self.register_buffer("R_block", torch.zeros(batch_size, R_BLOCK_SIZE))

        # Default Guna weights
        self.w_S = 0.9
        self.w_R = 1.05
        self.w_T = 0.6
        self.lambda_ = 0.05
        self.threshold = 0.30

        self.is_initialized = False

    def initialize_sattvic(self, seed: Optional[torch.Tensor] = None):
        """
        Initialize manifold to balanced 'Shunya' (zero-point) state.

        Args:
            seed: Optional custom S_0 tensor [batch, dim]
        """
        with torch.no_grad():
            if seed is not None:
                assert seed.shape == (self.batch_size, self.dim)
                self.S_0.copy_(seed)
            else:
                # Uniform distribution across dimensions
                self.S_0.fill_(1.0 / (self.dim ** 0.5))

            # Anchor current and previous to seed
            self.S_t.copy_(self.S_0)
            self.S_prev.copy_(self.S_0)

            # R-block starts as identity (perfect alignment)
            # Identity 3x3 flattened: [1,0,0, 0,1,0, 0,0,1]
            identity = torch.tensor([1, 0, 0, 0, 1, 0, 0, 0, 1], dtype=torch.float32)
            self.R_block.copy_(identity.unsqueeze(0).expand(self.batch_size, -1))

            self.is_initialized = True

    def set_weights(
        self,
        w_S: float = 0.9,
        w_R: float = 1.05,
        w_T: float = 0.6,
        lambda_: float = 0.05,
        threshold: float = 0.30
    ):
        """Set Guna modulation weights."""
        self.w_S = w_S
        self.w_R = w_R
        self.w_T = w_T
        self.lambda_ = lambda_
        self.threshold = threshold

    def step(
        self,
        delta: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Execute one step of Sattvic State Evolution.

        Args:
            delta: [batch, dim] Model's predicted state change

        Returns:
            (output_G, integrity_flags) tensors
        """
        if not self.is_initialized:
            raise RuntimeError("Manifold not initialized. Call initialize_sattvic() first.")

        # Ensure delta matches batch size
        if delta.dim() == 1:
            delta = delta.unsqueeze(0)
        assert delta.size(0) == self.batch_size

        # Use CUDA extension if available
        if _CUDA_EXT_AVAILABLE:
            output_G, integrity_flags = symbol_u12_cuda.step_evolution(
                self.S_t,
                self.S_prev,
                self.S_0,
                self.R_block,
                delta,
                self.w_S,
                self.w_R,
                self.w_T,
                self.lambda_,
                self.threshold
            )
        else:
            # Pure Python fallback
            output_G, integrity_flags = self._python_fallback(delta)

        return output_G, integrity_flags

    def _python_fallback(
        self,
        delta: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Pure Python implementation for when CUDA extension is not available.
        """
        with torch.no_grad():
            batch_size = delta.size(0)

            # Layer 1: State Evolution with Persistence
            S_new = self.S_t + delta + self.lambda_ * (self.S_0 - self.S_t)

            # Layer 2A: Motion (before updating S_prev)
            M = torch.norm(S_new - self.S_prev, dim=-1)

            # Update Ghost Buffer
            self.S_prev.copy_(self.S_t)
            self.S_t.copy_(S_new)

            # Layer 2B: Coherence via Cosine Similarity
            dot = torch.sum(S_new * self.S_0, dim=-1)
            mag_t = torch.norm(S_new, dim=-1)
            mag_0 = torch.norm(self.S_0, dim=-1)
            Cs = dot / (mag_t * mag_0 + 1e-9)

            # Layer 2C: Entropy
            p = torch.abs(S_new)
            p_norm = p / (p.sum(dim=-1, keepdim=True) + 1e-9)
            H = -torch.sum(p_norm * torch.log(p_norm + 1e-9), dim=-1)
            H = H / torch.log(torch.tensor(float(self.dim)))

            # Layer 3: R-Matrix Trace
            trace = (self.R_block[:, 0] + self.R_block[:, 4] + self.R_block[:, 8] + 1) / 4

            # Build integrity flags
            integrity_flags = torch.zeros(batch_size, dtype=torch.int32, device=delta.device)
            integrity_flags = torch.where(Cs < 0.3, integrity_flags | 0x01, integrity_flags)
            integrity_flags = torch.where(M > 2.5, integrity_flags | 0x02, integrity_flags)
            integrity_flags = torch.where(trace < self.threshold, integrity_flags | 0x04, integrity_flags)
            integrity_flags = torch.where(H > 0.95, integrity_flags | 0x08, integrity_flags)

            # Layer 4: Guna Modulation
            S_raw = Cs * (1.0 - H)
            R_raw = M * (1.0 - torch.abs(H - 0.5))
            T_raw = H * (1.0 - Cs)

            total = S_raw + R_raw + T_raw + 1e-9
            S = S_raw / total
            R = R_raw / total
            T = T_raw / total

            output_G = (self.w_S * S) + (self.w_R * R) + (self.w_T * T)

            return output_G, integrity_flags

    def get_metrics(self) -> Dict[str, torch.Tensor]:
        """
        Calculate current manifold metrics.

        Returns:
            Dictionary with coherence, motion, entropy, and trace values.
        """
        with torch.no_grad():
            # Coherence
            dot = torch.sum(self.S_t * self.S_0, dim=-1)
            mag_t = torch.norm(self.S_t, dim=-1)
            mag_0 = torch.norm(self.S_0, dim=-1)
            Cs = dot / (mag_t * mag_0 + 1e-9)

            # Motion (from previous step)
            M = torch.norm(self.S_t - self.S_prev, dim=-1)

            # Entropy
            p = torch.abs(self.S_t)
            p_norm = p / (p.sum(dim=-1, keepdim=True) + 1e-9)
            H = -torch.sum(p_norm * torch.log(p_norm + 1e-9), dim=-1)
            H = H / torch.log(torch.tensor(float(self.dim)))

            # Trace
            trace = (self.R_block[:, 0] + self.R_block[:, 4] + self.R_block[:, 8] + 1) / 4

            return {
                'coherence': Cs,
                'motion': M,
                'entropy': H,
                'trace': trace,
            }

    def generate_seal(self, text_output: str) -> SattvicSeal:
        """
        Generate a Sattvic Seal for the current state.

        Args:
            text_output: The generated text response

        Returns:
            SattvicSeal with cryptographic proof
        """
        metrics = self.get_metrics()

        # Calculate integrity flags
        flags = 0
        if metrics['coherence'].mean().item() < 0.3:
            flags |= IntegrityFlag.COHERENCE_FAILURE
        if metrics['motion'].mean().item() > 2.5:
            flags |= IntegrityFlag.MOTION_OVERDRIVE
        if metrics['trace'].mean().item() < self.threshold:
            flags |= IntegrityFlag.TRACE_COLLAPSE
        if metrics['entropy'].mean().item() > 0.95:
            flags |= IntegrityFlag.ENTROPY_SPIKE

        return generate_sattvic_seal(
            manifold_state=self.S_t,
            text_output=text_output,
            trace_score=metrics['trace'].mean().item(),
            coherence_score=metrics['coherence'].mean().item(),
            motion_score=metrics['motion'].mean().item(),
            entropy_score=metrics['entropy'].mean().item(),
            integrity_flags=flags,
            anchor_id=self.anchor_id,
        )

    def reset(self):
        """Reset manifold to Sattvic Seed state."""
        with torch.no_grad():
            self.S_t.copy_(self.S_0)
            self.S_prev.copy_(self.S_0)

    def to(self, device: torch.device) -> 'SymbolU12Manifold':
        """Move manifold to specified device."""
        self._device = device
        return super().to(device)

    def forward(self, delta: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward pass - wrapper around step() for nn.Module compatibility."""
        return self.step(delta)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'SymbolU12Manifold',
    'SattvicSeal',
    'generate_sattvic_seal',
    'IntegrityFlag',
    'MANIFOLD_DIM',
    'R_BLOCK_SIZE',
]
