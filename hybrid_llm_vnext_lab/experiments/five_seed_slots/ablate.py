"""Re-export of the FROZEN S-arm ablations (slots_off/randomized_address/shuffle_values/
write_gate_zero + diagnostic slot_keys_randomized). No logic forked."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "neural_slots_only"))
from evaluate import s_ablations  # noqa: F401,E402
