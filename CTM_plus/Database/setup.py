#!/usr/bin/env python3
"""
Setup script for CTM+ Database integration.
"""

from setuptools import setup, find_packages

setup(
    name="ctm-plus-db",
    version="0.1.0",
    description="CTM+ intelligent buffer pool management for databases",
    author="CTM+ Team",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    extras_require={
        "postgres": ["psycopg2-binary"],
        "redis": ["redis"],
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
        "Topic :: Database",
    ],
)
