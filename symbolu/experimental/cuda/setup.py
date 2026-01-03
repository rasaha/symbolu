"""
SymbolU12 CUDA Extension - Build Configuration
===============================================

Builds the symbol_u12_cuda PyTorch C++ extension.

Usage:
    # Install in development mode
    pip install -e .

    # Or build directly
    python setup.py build_ext --inplace

Requirements:
    - PyTorch >= 1.10
    - CUDA Toolkit (for GPU support)
    - C++ compiler (gcc/clang on Linux, MSVC on Windows)

Reference: docs/GOOGLE_ARCHITECTURE_PROPOSALS.md Section 30.6
"""

import os
import sys
from setuptools import setup, find_packages

# Check if CUDA is available
try:
    import torch
    from torch.utils.cpp_extension import BuildExtension, CUDAExtension, CppExtension
    CUDA_AVAILABLE = torch.cuda.is_available()
except ImportError:
    print("PyTorch not found. Please install PyTorch first.")
    sys.exit(1)

# Get the directory containing this setup.py
HERE = os.path.dirname(os.path.abspath(__file__))

# Compiler flags
extra_compile_args = {
    'cxx': ['-O3', '-std=c++17'],
}

# NVCC flags (only if CUDA is available)
if CUDA_AVAILABLE:
    extra_compile_args['nvcc'] = [
        '-O3',
        '--use_fast_math',
        '-std=c++17',
        # Target multiple GPU architectures for broader compatibility
        '-gencode=arch=compute_70,code=sm_70',  # Volta (V100)
        '-gencode=arch=compute_75,code=sm_75',  # Turing (RTX 20xx)
        '-gencode=arch=compute_80,code=sm_80',  # Ampere (A100, RTX 30xx)
        '-gencode=arch=compute_86,code=sm_86',  # Ampere (RTX 30xx laptop)
        '-gencode=arch=compute_89,code=sm_89',  # Ada Lovelace (RTX 40xx)
        '-gencode=arch=compute_90,code=sm_90',  # Hopper (H100)
    ]

# Source files
sources = [
    os.path.join(HERE, 'binding.cpp'),
    os.path.join(HERE, 'sattva_guna_core.cu'),
]

# Include directories
include_dirs = [HERE]

# Define the extension
if CUDA_AVAILABLE:
    print("CUDA detected - building with GPU support")
    ext_modules = [
        CUDAExtension(
            name='symbol_u12_cuda',
            sources=sources,
            include_dirs=include_dirs,
            extra_compile_args=extra_compile_args,
        )
    ]
else:
    print("CUDA not detected - building CPU-only version")
    # For CPU-only build, we exclude the .cu file and use only C++
    ext_modules = [
        CppExtension(
            name='symbol_u12_cuda',
            sources=[os.path.join(HERE, 'binding.cpp')],
            include_dirs=include_dirs,
            extra_compile_args=extra_compile_args,
            define_macros=[('CPU_ONLY', '1')],
        )
    ]

setup(
    name='symbol_u12_cuda',
    version='1.0.0',
    author='SymbolU12 Team',
    description='CUDA-accelerated Sattvic State Evolution for SymbolU12',
    long_description="""
    SymbolU12 CUDA Extension
    ========================

    High-performance CUDA kernels for the Sattvic State Evolution and
    Guna Modulation. Provides:

    - Fused Layer 1 (State Evolution) and Layer 2 (Guna Modulation)
    - Ghost Buffer for temporal motion tracking
    - Cosine Similarity coherence calculation
    - R-Matrix integrity verification with bitmask reporting
    - Automatic CPU fallback for non-GPU systems

    Target latency: <200μs per batch (vs 2-5ms for PyTorch baseline)
    """,
    ext_modules=ext_modules,
    cmdclass={'build_ext': BuildExtension},
    python_requires='>=3.8',
    install_requires=[
        'torch>=1.10',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: C++',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ],
)
