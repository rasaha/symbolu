# Model Selection — Research / Product Separation

The canonical package contains **only** reusable product logic. Research, pilot, provider execution, and
evaluation stay outside it, as explicit consumers or as classified separate research algorithms.

## Outside the canonical package (kept as research)

| Location | What it is | Why it stays out |
|---|---|---|
| `execution_gate/{harness,baselines,scenarios,common_io}.py` | Local evaluation harness + synthetic scenario battery | Research/eval, not product; consumes the core via the compatibility surface |
| `execution_gate/frozen/replay_v1/**` | Replay determinism freeze | Generated evidence; self-contained; untouched |
| `model_selection_experiment/` | Synthetic benchmark/ablation harness + dict-based `route` engine + simulator/oracle/metrics | Genuinely different research algorithm (distinct I/O + multi-source fusion) |
| `model_selection_pilot/` | Real-provider shadow pilot; provider execution (`provider.py`, `execute.py`, credential-blocked); F1/F2/G engine | Provider execution + research; execution is a separate concern from selection |
| `model_selection_reconciliation/` | Policy A/B/C objective study over the experiment | Research variants; not production defaults |

Each sibling `__init__.py` now carries a header classifying it as research, intentionally separate from
`ugence_model_selection`, and stating that merging it would change behavior (out of scope).

## What a research experiment may supply to the canonical core

Candidates, policy configuration, synthetic measurements, alternate weights, and evaluation metrics —
i.e. it may *drive* the canonical eligibility/selection and *score* the outcome. It must not carry
another copy of the canonical eligibility or selection engine. The retained research engines are
classified as **distinct algorithms**, not copies of the canonical core (see `DUPLICATION_DISPOSITION.md`);
converging them onto the canonical core is a **future, evidence-backed** phase, not this structural one.

## Provider execution vs selection (kept distinct)

The pilot may continue to invoke providers after a selection, but that execution
(`model_selection_pilot/provider.py`, `execute.py`) is **not** in the canonical package. The boundary
holds: **Model Selection chooses within policy → routing dispatches → provider execution invokes.** The
canonical package owns only the first.

## Discipline restated

> Canonicalize the existing policy core first. Validate and improve Model Selection later.

Evidence for the capability remains primarily synthetic; no commercial model-quality or provider-
reliability claim is made or validated by this migration; the soft-by-default quality-floor gap is
unchanged.
