"""Pytest config: make qpc and the qgr library importable; pin threads for determinism."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, os.pardir, "quad_generative_regularization"))

import torch  # noqa: E402
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
