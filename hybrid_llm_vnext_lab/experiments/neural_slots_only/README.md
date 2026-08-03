# Slots-Only (S) Neural Attribution Experiment

**Phase-free.** Answers whether bounded slots **learn** the beyond-window retrieval capability
with **no Phase present during training** (init / forward / backprop / eval / params / imports).

- `models.py` — Phase-free A / S / A+ arms; reuses the incubated `BindingSlots` (byte-identical,
  Phase-free) + a windowed softmax attention identical to the historical `SoftmaxAttn`.
- `tasks_adapter.py` — read-only import of the historical `experiments/phase_lc/tasks.py` (corpus,
  tokenizer, task generators). Nothing writes to the historical tree.
- `evaluate.py` — eval suite + native and extended (wrapper) S ablations.
- `run.py` — trains A / S / A+, seeds 0,1,2, 1200 steps; `--check-environment`; exits non-zero if
  torch is absent.
- `compare.py` — S−A / S−A+ deltas, ablation collapse, and the pre-registered verdict.
- `PRE_REGISTRATION.md` / `config.json` — hypotheses H1–H5, matched design, decision rule.
- `artifacts/<run-id>/` — immutable results.

Run:
```
OMP_NUM_THREADS=4 python run.py --run-id <id> --seeds 0,1,2 --steps 1200
python compare.py --results artifacts/<id>/slots_only_results.json
```

No Phase is imported anywhere here (enforced by `tests/boundaries/test_slots_only_no_phase.py`).
This is not a package, not KDA/MLA, not five-seed validation.
