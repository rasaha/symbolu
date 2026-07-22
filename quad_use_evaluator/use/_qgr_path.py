"""Put the prior, unmodified ``qgr`` research package on sys.path (read-only reuse).

This study is a *separate* package. It does not modify production code, the Quad model, the
architecture, or the inference pipeline. It reuses the frozen prior infrastructure (the
authentic Quad-scoring model, deterministic MQAR, metrics) read-only by importing from it.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PKG)
QGR_DIR = os.path.join(_ROOT, "quad_generative_regularization")

if not os.path.isdir(os.path.join(QGR_DIR, "qgr")):
    raise RuntimeError(f"prior package not found at {QGR_DIR!r}; this study reuses it read-only")
if QGR_DIR not in sys.path:
    sys.path.insert(0, QGR_DIR)
