#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="ctm-plus-kv-simulator",
    version="0.3.0",
    description="KV cache eviction policy simulator for LLM inference (research tool)",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": ["pytest", "pytest-cov"],
    },
)
