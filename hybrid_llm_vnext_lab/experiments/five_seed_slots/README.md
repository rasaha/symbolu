# Five-Seed Holdout Stability & Failure-Mode Validation

Runs the **frozen** Phase-free A / A+ / S arms on **five new holdout seeds (3,4,5,6,7)** and applies
pre-registered acceptance gates. Seeds 0–2 remain frozen and are reported separately; the verdict comes
from seeds 3–7. **No architecture change after viewing results.**

- `PRE_REGISTRATION.md` / `ACCEPTANCE_GATES.json` / `ACCEPTANCE_GATES.sha256` — frozen gates (integrity-checked).
- `FROZEN_CONFIG.json` — the frozen architecture/training config (verified from live code).
- `run.py` — driver that verifies pre-registration + frozen abc.json, then invokes the **frozen**
  `neural_slots_only` harness for the holdout seeds (no model logic forked) and writes immutable artifacts.
- `evaluate.py` / `ablate.py` — re-exports of the frozen evaluation + S ablations.
- `classify.py` — applies every gate → final classification + KDA-readiness.
- `compare.py` — supplementary 0–7 descriptive combination.
- `verify_preregistration.py` — fails if the gates change after commit or seeds ≠ [3,4,5,6,7].

Run (torch environment):
```
python run.py --run-id <id> --seeds 3,4,5,6,7 --steps 1200
python classify.py --results artifacts/<id>/five_seed_results.json
```

Not KDA/MLA/composition/streaming-slot-training/relational-redesign/packaging/Phase/H22.
