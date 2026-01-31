#!/usr/bin/env python3
"""
Setup script for CTM+ DeepSpeed integration.
"""

from setuptools import setup, find_packages

setup(
    name="ctm-plus-deepspeed",
    version="0.1.0",
    description="CTM+ intelligent memory offloading for DeepSpeed",
    author="CTM+ Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        # DeepSpeed is optional - only needed when integrating
    ],
    extras_require={
        "deepspeed": ["deepspeed>=0.9.0"],
        "dev": ["pytest", "pytest-cov"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
