#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="ctm-plus-eviction",
    version="0.2.0",
    description="Adaptive multi-signal eviction policy for research and benchmarking",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "dev": ["pytest", "pytest-cov"],
    },
)
