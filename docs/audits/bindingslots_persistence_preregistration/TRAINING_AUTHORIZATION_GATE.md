# Training authorization gate

Training the six-arm persistence matrix (A+/R0/O1/O1R/H1/H2 × seeds 23–27, 30 runs) requires a
**separate explicit authorization**. It is intentionally not runnable from this PR:

- `runner_stub.py` refuses to run and returns non-zero.
- The CI workflow has **no training job**; only torch-free integrity + the small non-interference
  fixture run automatically.
- `verify_persistence_prereg.py` fails if any training-result file appears.

When authorized, the training phase must: preserve every frozen definition here; train A+ per seed;
use the frozen classifier and same-seed A+ threshold; record the full checkpoint cadence incl. step
700; and produce curated, hashed per-seed artifacts sufficient to reconstruct the verdict — with no
tuning, no best-checkpoint selection, and no outcome-based seed replacement. Until then, this remains
preregistration only, and KDA validation stays blocked.
