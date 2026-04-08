#!/usr/bin/env python3
"""
CTM+ Standard Trace Benchmark Runner.

Compares CTM+ against LRU, ARC, and S3-FIFO on industry-standard
trace profiles from MSR Cambridge, Twitter, and Meta/CacheLib.

Usage:
    python run_benchmarks.py                           # All 7 traces
    python run_benchmarks.py --quick                   # Quick (50k events)
    python run_benchmarks.py --traces msr_src1_0       # Single trace
    python run_benchmarks.py --json results.json       # Export JSON
    python run_benchmarks.py --trace-dir ./traces/     # Real trace files
    python run_benchmarks.py --list                    # List profiles
"""

import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ctm_plus.benchmarks import main

if __name__ == "__main__":
    sys.exit(main())
