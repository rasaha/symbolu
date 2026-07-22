"""Quad perturbation-consistency study (separate package; reuses the prior qgr package read-only).

Falsification target: a same-head perturbation-consistency objective, using no retrieval
labels, can improve Quad generalisation beyond the task-only bounded baseline (BD-A).
The null hypothesis is that task-only learning already discovers the best retrieval
organisation and any explicit consistency objective reduces generalisation.
"""

from . import _qgr_path  # noqa: F401  (side-effect: put the prior qgr package on sys.path)
