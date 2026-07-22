"""Pytest config: make this package importable, put the prior qgr package on sys.path, pin threads."""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qpc  # noqa: F401,E402  (side-effect: qgr on sys.path)

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
torch.use_deterministic_algorithms(False)
