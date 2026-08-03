# Neural Reproduction — Live State

**Date:** 2026-08-03 · Machine-readable: [`../artifacts/neural_reproduction_live_state.json`](../artifacts/neural_reproduction_live_state.json)

| Field | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-…` @ `b6fd6ca5` |
| Work branch | `claude/hybrid-llm-slots-neural-reproduction` (from `b6fd6ca5`) |
| PR #1294 | MERGED 2026-08-03T03:40:39Z |
| PR #1295 | MERGED 2026-08-03T04:12:55Z (into default `b6fd6ca5`) |
| Lab on default | present |
| Verifiers on base | audit 201/0 · lab 42/0 · stdlib 36/0 |
| Working tree at start | clean |

## Frozen historical artifact (must not change)

| | |
|---|---|
| `experiments/phase_lc/results/abc.json` git blob | `cbcd94f1` |
| SHA-256 | `b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482` |
| size | 23218 bytes |
| status | **UNMODIFIED** — the reproduction launcher refuses any `abc*` tag and writes only to unique tags + immutable lab dirs; a pre/post digest check guards every run |

## Environment (PyTorch AVAILABLE — not RESOURCE_BLOCKED)

- python **3.11.15**, **torch 2.13.0**, numpy **1.26.4**, CPU fp32, **4 threads**.
- Installed via `pip install --extra-index-url https://download.pytorch.org/whl/cpu 'numpy<2' 'torch==2.*'`.
- **torch 2.13.0 matches the historical report's "torch 2.13 CPU"** (same major.minor) — a close
  environment match. The `+cu130` build runs on CPU (no GPU present).
- Determinism: `torch.manual_seed` + `random.seed` (historical contract);
  `torch.use_deterministic_algorithms` not forced (HISTORICAL_COMPATIBILITY_MODE). See
  `../experiments/reproduce_legacy_slots/environment.lock.json`.

## Neural execution outcome

- **Neural parity (incubated vs historical `BindingSlots`): PASSED** within 1e-7 on forward,
  gradients, ablations, diagnostics, and state_dict → **NUMERICAL_PARITY** (see the parity report).
- **A-arm reproduction check:** the Phase-free A arm reproduces the historical A seed-0 to
  `params 2000392` (exact), `ppl256 128.4` (historical 128.45), `needle@d96 0.025` (historical 0.025)
  — the reproduction pipeline is faithful.
- **S-arm and A/B/C reproduction** executed on CPU; results and classifications in the S-arm and
  reproduction reports.

This phase is therefore an **executed neural result**, not a RESOURCE_BLOCKED plan.
