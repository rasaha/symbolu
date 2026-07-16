#!/usr/bin/env python3
"""Phase D — xmin decomposition audit.

Tests whether the production per-block per-channel K XMIN factors as u_d + v_b
(additive) or a pre-registered linear rank-R SVD (R∈{2,4}). Thin CLI over
structure.py. xmin is NOT dropped silently — its remaining cost is reported honestly
(bytes retained per block) and a systematic per-channel bias check flags any channel
the decomposition consistently mis-reconstructs.

  python analyze_xmin_structure.py --manifest capture.pt --out-json xmin_structure.json
  python analyze_xmin_structure.py --synthetic factorable       # CPU self-check
"""
import sys

try:
    from . import structure
except ImportError:  # pragma: no cover
    import structure  # type: ignore

if __name__ == "__main__":
    sys.exit(structure.main(kind="xmin"))
