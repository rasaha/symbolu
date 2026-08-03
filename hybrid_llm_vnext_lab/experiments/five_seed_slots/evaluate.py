"""Re-export of the FROZEN neural_slots_only evaluation (no logic forked)."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "neural_slots_only"))
from evaluate import eval_suite, s_ablations  # noqa: F401,E402
