"""Put the prior research packages on sys.path for READ-ONLY reuse.

This study is a separate package. It does not modify Quad production code, the MQAR benchmark,
the model/training/inference pipeline, the USE package, the perturbation-consistency package, or
the QGR package. It imports from them read-only:

  * qgr  (quad_generative_regularization)  -- authentic Quad model, deterministic MQAR, metrics
  * use  (quad_use_evaluator)              -- read-only capture, confidence baselines, metrics,
                                              OOF prediction, DeLong/bootstrap stats
  * qpc  (quad_perturbation_consistency)   -- semantic-equivalence perturbation machinery (for T)
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PKG)

for name in ("quad_generative_regularization", "quad_use_evaluator",
             "quad_perturbation_consistency"):
    d = os.path.join(_ROOT, name)
    if not os.path.isdir(d):
        raise RuntimeError(f"required prior package not found: {d!r}")
    if d not in sys.path:
        sys.path.insert(0, d)
