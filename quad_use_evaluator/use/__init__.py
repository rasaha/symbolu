"""Universal Semantic Evaluator (USE) — read-only post-inference correctness predictor.

USE observes a completed inference of the frozen Quad model and, without changing any
computation, extracts phase-like states from internal channels and runs the U1-U5 peer-to-peer
coherence dynamics on a detached copy. The study asks — and attempts to falsify — whether the
resulting USE-native signals predict answer correctness better than standard confidence
baselines. Null: internal coherence carries no predictive information beyond model confidence.
"""

from . import _qgr_path  # noqa: F401  (side-effect: put qgr on sys.path)
