#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="kv-policy",
    version="0.2.0",
    description="Scoring-only KV cache eviction policy for LLM inference (research prototype)",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": ["pytest", "pytest-cov"],
    },
)
