"""Quad perturbation-consistency study (separate track; imports qgr as a read-only library)."""
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), _os.pardir, _os.pardir,
                                  "quad_generative_regularization"))

from .paired_mqar import gen_paired_batch, staged_partner, Paired
from .consistency import consistency_loss, pair_distribution, js_divergence, distribution_drift
from .train_sync import SyncConfig, train_sync_arm, ARMS
from . import diagnostics

__all__ = ["gen_paired_batch", "staged_partner", "Paired", "consistency_loss",
           "pair_distribution", "js_divergence", "distribution_drift",
           "SyncConfig", "train_sync_arm", "ARMS", "diagnostics"]
