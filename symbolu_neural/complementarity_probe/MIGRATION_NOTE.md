# Migration Note — complementarity_probe vs the older detector files

**Decision deferred. Do not delete anything yet.**

## Why this directory exists

The older Symbol-U work lives in `symbolu_neural/clean_softmax/` (the "detector
files": grounding probes, capacity studies, typed-head ablations, generation
instrumentation). It judged Symbol-U primarily by **next-token prediction inside
a Transformer** and built machinery to *use* the variables before establishing
there was anything to use.

`SYMBOL_U_RESEARCH_STRATEGY.md` (in `clean_softmax/`) concluded that was a
category error: the first question is **measurement** — does `U` carry semantic
signal complementary to `E`? — not generation utility. This directory is the
clean-room implementation of that measurement, isolated so it can be evaluated on
its own merits.

## Isolation guarantees

- This package imports **only** `symbolu_core.formulas.*` (the real, shared
  mappers) and standard libs (`numpy`, optional `torch`/`transformers`).
- It does **not** import, modify, or depend on anything under
  `clean_softmax/`, the Hybrid Phase / Sovereign / JEPA code, or
  `train_unified_llm.py`.
- Nothing outside `symbolu_neural/complementarity_probe/` is changed by this work.

## Canonical status

| path | status |
|---|---|
| `symbolu_neural/clean_softmax/` (detector files) | **CANONICAL** — keep until this path proves itself |
| `symbolu_neural/complementarity_probe/` (this) | **EXPERIMENTAL** — replacement candidate |

## The later decision (NOT made now)

After a real `--embeddings hf` run of exp2 (and, if it passes, exp1's CONTINUE
branch), choose one of:

1. **Keep new path** — promote `complementarity_probe/` to canonical; the old
   detector files may then be deleted *if* nothing else depends on them.
2. **Delete older detector files** — only once (1) is decided and dependencies
   are checked.
3. **Merge selected pieces** — e.g. keep the old grounding harness (`run_grounding.py`)
   as the gate-1/existence probe and fold it under this directory's hierarchy.
4. **Abandon new path** — if measurement adds nothing the detector files didn't
   already establish.

**Gate for any deletion:** a real semantic-backend (`hf`) exp2 result exists and
is recorded in `RESULT_REPORT_TEMPLATE.md`. Until then, both paths coexist and
the old one is authoritative.
