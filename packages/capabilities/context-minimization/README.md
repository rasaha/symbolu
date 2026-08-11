# Ugence Context Minimization (v0.1 core)

**Deterministic, domain-neutral, extractive.** Given an *already-assembled*
context, Context Minimization reduces it by **extractive omission** while
preserving a **caller-defined deterministic equivalence condition**, and **fails
closed** whenever equivalence cannot be established.

- **Extractive, never generative.** It retains, removes, restores, or falls back
  to the full context. It never rewrites, paraphrases, summarizes, or synthesizes
  new text.
- **Creates no authority.** "Invariance" is defined **entirely** by the neutral
  oracle you supply. The minimizer compares the oracle's opaque equivalence key and
  never interprets it. It does **not** decide whether information was permitted to
  enter the context (that is *admission*, which happens upstream).
- **A leaf.** Imports **only the Python standard library** — never ActionGate, a
  product, a model, or a tokenizer.

## Two modes

| Mode | Entry point | Needs an oracle? | Guarantee |
| --- | --- | --- | --- |
| **Structural** | `structural_minimize(...)` / `deduplicate_context(...)` | No | *Structurally lossless*: removes exact-duplicate text / declared redundancy sets, keeping one representative. Narrower than full Context Minimization. |
| **Oracle-verified** | `minimize_context(...)` | **Yes** | *Equivalence-preserving relative to the supplied oracle*: extractive removal proven equivalent to the full context; restores or falls back otherwise. |

Structural deduplication alone is **not** authorization-preserving Context
Minimization — see `docs/STRUCTURAL_MINIMIZATION.md`.

## Token accounting (CM-TA1)

The neutral `token_accounting` module measures token consumption for every model API
attempt while keeping **three distinct quantities** separate: **context reduction**
(what the minimizer removed), the **complete-request estimate** (via an *injected*
counter — the core implements no tokenizer), and **provider-reported usage** (unknown
is `None`, never zero; authoritative for the response reconciled, **not** an invoice).
See `docs/TOKEN_ACCOUNTING.md`. Cross-package wiring to the Agent Runtime lives in the
separate `context-minimization-token-accounting-runtime` integration distribution.

## Quick start

```python
from ugence_context_minimization.api import (
    Context, ContextUnit, OracleEvaluation, minimize_context, structural_minimize,
)

ctx = Context(id="c1", correlation_id="corr-1", units=(
    ContextUnit(id="p",    text="deploy service to prod", source_type="state_fact", protected=True),
    ContextUnit(id="dup",  text="deploy service to prod", source_type="state_fact"),
    ContextUnit(id="fill", text="weekly sprint filler",   source_type="log_event"),
))

# Structural mode (no oracle):
print(structural_minimize(ctx, protected_ids=["p"]).surviving_ids)  # ('p', 'fill')

# Oracle-verified mode — you supply a neutral InvarianceOracle:
class MyOracle:
    def evaluate(self, context, *, evaluation_time=None):
        present = sorted({t for u in context.units for t in ("deploy",) if t in u.text.lower()})
        return OracleEvaluation(equivalence_key="|".join(present),
                                oracle_id="my-oracle", contract_version="1.0",
                                correlation_id=context.correlation_id)

r = minimize_context(ctx, oracle=MyOracle(), target_reduction=1.0,
                     protected_ids=["p"], evaluation_time=1.0)
print(r.surviving_ids, r.equivalence_status.value)
```

## Install / build / verify

```bash
python -m build packages/capabilities/context-minimization
python packages/capabilities/context-minimization/scripts/verify_context_minimization_distribution.py
```

## What this is not

Not authorization, not admission, not enforcement, not summarization/retrieval,
not a model, and **not** H22 orchestration. ActionGate is an *optional* concrete
oracle integration that lives **outside** this package. This release carries **no
live-enterprise validation** claim. See `docs/LIMITATIONS.md`.
