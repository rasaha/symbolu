"""Pytest config: make the package importable and pin CPU threads for determinism."""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
torch.use_deterministic_algorithms(False)  # CPU ops here are already deterministic
