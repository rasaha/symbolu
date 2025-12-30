"""
SymbolU12 CUDA Extension Package
================================

Hardware-accelerated Sattvic State Evolution for the 124-dimensional
cognitive manifold.

Features:
    - Fused CUDA kernels for <200μs latency
    - Ghost Buffer for temporal motion tracking
    - Cosine Similarity coherence to Sattvic Seed
    - R-Matrix integrity verification
    - Automatic CPU fallback for non-GPU systems
    - Sattvic Seal cryptographic proof

Usage:
    from symbolu.experimental.cuda import SymbolU12Manifold

    # Initialize manifold
    manifold = SymbolU12Manifold(batch_size=1)
    manifold.initialize_sattvic()
    manifold = manifold.cuda()  # Move to GPU if available

    # Run evolution step
    delta = model.predict_delta(input_tokens)
    output_G, integrity_flags = manifold.step(delta)

    # Generate cryptographic proof
    seal = manifold.generate_seal(generated_text)

Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30
"""

import torch
from typing import Optional

# Version info
__version__ = "1.0.0"

# Check for CUDA extension
_CUDA_EXT_AVAILABLE = False
_CUDA_EXT_ERROR = None

try:
    import symbol_u12_cuda as _cuda_ext
    _CUDA_EXT_AVAILABLE = True

    # Re-export constants from extension
    INTEGRITY_OK = _cuda_ext.INTEGRITY_OK
    COHERENCE_FAILURE = _cuda_ext.COHERENCE_FAILURE
    MOTION_OVERDRIVE = _cuda_ext.MOTION_OVERDRIVE
    TRACE_COLLAPSE = _cuda_ext.TRACE_COLLAPSE
    ENTROPY_SPIKE = _cuda_ext.ENTROPY_SPIKE
    MANIFOLD_DIM = _cuda_ext.MANIFOLD_DIM

    # Re-export functions
    step_evolution = _cuda_ext.step_evolution
    step_evolution_single = _cuda_ext.step_evolution_single
    decode_integrity_flags = _cuda_ext.decode_integrity_flags

except ImportError as e:
    _CUDA_EXT_ERROR = str(e)

    # Fallback constants
    INTEGRITY_OK = 0x00
    COHERENCE_FAILURE = 0x01
    MOTION_OVERDRIVE = 0x02
    TRACE_COLLAPSE = 0x04
    ENTROPY_SPIKE = 0x08
    MANIFOLD_DIM = 124

# Import Python components (always available)
from .manifold import (
    SymbolU12Manifold,
    SattvicSeal,
    generate_sattvic_seal,
    IntegrityFlag,
    R_BLOCK_SIZE,
)


def is_cuda_available() -> bool:
    """Check if CUDA is available for acceleration."""
    return torch.cuda.is_available()


def is_extension_available() -> bool:
    """Check if the compiled CUDA extension is available."""
    return _CUDA_EXT_AVAILABLE


def get_extension_error() -> Optional[str]:
    """Get the error message if extension failed to load."""
    return _CUDA_EXT_ERROR


def get_device_info() -> dict:
    """Get information about available compute devices."""
    info = {
        'cuda_available': torch.cuda.is_available(),
        'extension_available': _CUDA_EXT_AVAILABLE,
        'extension_error': _CUDA_EXT_ERROR,
        'version': __version__,
    }

    if torch.cuda.is_available():
        info['cuda_device_count'] = torch.cuda.device_count()
        info['cuda_device_name'] = torch.cuda.get_device_name(0)
        info['cuda_memory_total'] = torch.cuda.get_device_properties(0).total_memory

    return info


def build_extension():
    """
    Build the CUDA extension if not already built.

    Run this from the symbolu/experimental/cuda directory:
        python setup.py build_ext --inplace

    Or install the package:
        pip install -e symbolu/experimental/cuda
    """
    import subprocess
    import os

    cuda_dir = os.path.dirname(os.path.abspath(__file__))
    setup_py = os.path.join(cuda_dir, 'setup.py')

    if not os.path.exists(setup_py):
        raise FileNotFoundError(f"setup.py not found at {setup_py}")

    print(f"Building CUDA extension from {cuda_dir}")
    result = subprocess.run(
        ['python', 'setup.py', 'build_ext', '--inplace'],
        cwd=cuda_dir,
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print("Build failed!")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        raise RuntimeError("Extension build failed")

    print("Build successful!")
    print(result.stdout)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Core classes
    'SymbolU12Manifold',
    'SattvicSeal',
    'IntegrityFlag',

    # Functions
    'generate_sattvic_seal',
    'is_cuda_available',
    'is_extension_available',
    'get_device_info',
    'build_extension',

    # Constants
    'MANIFOLD_DIM',
    'R_BLOCK_SIZE',
    'INTEGRITY_OK',
    'COHERENCE_FAILURE',
    'MOTION_OVERDRIVE',
    'TRACE_COLLAPSE',
    'ENTROPY_SPIKE',

    # Version
    '__version__',
]
