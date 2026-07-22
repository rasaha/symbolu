"""Make the prior, unmodified ``qgr`` research package importable (read-only reuse).

This new study is a *separate* package.  It does not modify any production code or any
previous research package.  It reuses the frozen prior infrastructure — the authentic
Quad-scoring model, the deterministic MQAR generator, the task loss, the metrics, and the
read-only causal-ablation tools — by placing the prior package directory on ``sys.path`` and
importing from it.  Nothing here writes to or mutates the prior package.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)                       # quad_perturbation_consistency/
_ROOT = os.path.dirname(_PKG)                       # repo root
QGR_DIR = os.path.join(_ROOT, "quad_generative_regularization")

if not os.path.isdir(os.path.join(QGR_DIR, "qgr")):
    raise RuntimeError(
        f"prior package not found at {QGR_DIR!r}; this study reuses it read-only")

if QGR_DIR not in sys.path:
    sys.path.insert(0, QGR_DIR)
