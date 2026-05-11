#!/usr/bin/env python3
"""Build script for the ``kv-policy`` package.

The C extension ``kv_policy._ctm_evictor`` is the Cython port of
``CTMEvictorModern`` — see ``Bench/bench_out/PHASE4_GPU_FINDINGS.md``
§11 for why the port exists. The extension is OPTIONAL: when Cython
is not available at install time, the package still builds and runs
with the pure-Python evictor (``CTMEvictorModernC`` aliases to the
Python class in that case).

Build locally:
    cd CTM_plus/KVPolicy && python3 setup.py build_ext --inplace

Build via pip install:
    pip install -e CTM_plus/KVPolicy
"""

from setuptools import setup, find_packages

try:
    from Cython.Build import cythonize
    ext_modules = cythonize(
        ["kv_policy/_ctm_evictor.pyx"],
        language_level=3,
        compiler_directives={
            "boundscheck": False,
            "wraparound": False,
            "initializedcheck": False,
        },
    )
except ImportError:
    # Cython not installed — ship without the extension. The pure-Python
    # fallback in ``kv_policy/vllm_evictor.py`` (CTMEvictorModernC =
    # CTMEvictorModern) keeps the public API stable.
    ext_modules = []

setup(
    name="kv-policy",
    version="0.2.0",
    description="Scoring-only KV cache eviction policy for LLM inference (research prototype)",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": ["pytest", "pytest-cov"],
        "ext": ["Cython>=3.0"],
    },
    ext_modules=ext_modules,
)
