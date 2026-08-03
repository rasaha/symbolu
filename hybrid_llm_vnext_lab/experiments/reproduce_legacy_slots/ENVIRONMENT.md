# Reproduction Environment

Machine-readable: [`environment.lock.json`](environment.lock.json).

## Historical (from executable evidence / prose)

- CPU-only, **4 cores**, 15 GB RAM, **fp32** (`REPORT_ABC.md`: "CPU-only (4 cores), torch 2.13
  CPU, fp32, 3 seeds"; "HARDWARE CEILING: 4 CPU cores, 15 GB RAM, no GPU").
- torch version: reported **"torch 2.13 CPU"** — `INFERRED`/anomalous in the original note (2.13 is
  an unusual string), but **torch 2.13.0 does exist** and is what the current reproduction resolved
  to, so the major.minor **matches**.
- Determinism: `random.seed(s)` + `torch.manual_seed(s)`; data RNG `random.Random(seed*991+7)`;
  `torch.use_deterministic_algorithms` **not** set historically.

## Current reproduction

- python 3.11.15, **torch 2.13.0**, numpy 1.26.4, CPU fp32, `torch.set_num_threads(4)`.
- Env vars: `PYTHONHASHSEED=0 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
  NUMEXPR_NUM_THREADS=4`.
- Recorded at run time: `torch.__version__`, `torch.get_num_threads()`,
  `torch.are_deterministic_algorithms_enabled()`.

## Modes

- **HISTORICAL_COMPATIBILITY_MODE** (default): matches the historical numerical contract —
  `manual_seed` + `random.seed` only, `use_deterministic_algorithms` **not** forced, 4 threads,
  fp32. This is the mode used for the reproduction.
- **STRICT_DETERMINISTIC_MODE**: additionally `torch.use_deterministic_algorithms(True)`. Run only
  if it does not alter/block the historical code path; any divergence from
  HISTORICAL_COMPATIBILITY_MODE is recorded, not silently accepted. Not required for
  STATISTICAL_REPRODUCTION.

## Field evidence levels

See `environment.lock.json`: each field tagged `VERIFIED` / `INFERRED` / `NOT_FOUND` /
`CURRENT_REPRODUCTION_CHOICE`. `torch 2.13.0` matches the historical major.minor; Python version and
BLAS backend for the historical run are `NOT_FOUND`.
