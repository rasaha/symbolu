from setuptools import find_packages, setup


setup(
    name="ctm_bench",
    version="0.1.0",
    description=(
        "CTM+ tier-aware inference benchmark harness (Mode A — synthetic). "
        "Drives LRU / FIFO / CTM+ against a multi-tier cache + long-context "
        "workloads; reports per-tier byte counters."
    ),
    packages=find_packages(exclude=("tests", "tests.*")),
    python_requires=">=3.10",
    install_requires=[],  # Stdlib only — kv_policy is loaded lazily.
    extras_require={
        "ctm_plus": ["kv_policy"],   # Sibling package; install with pip install -e CTM_plus/KVPolicy/
        "test": ["pytest>=7.0"],
    },
    entry_points={
        "console_scripts": [
            "ctm-bench = ctm_bench.__main__:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
