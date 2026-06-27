# Internal Policy Controller v2 (faithful redo)

A correct implementation of **draft → full Symbol-U analysis → policy translation →
LLM rewrite → independent judge**, fixing every defect the forensic audit found in
v1. No weights changed, no training, no regex editing.

See `../INTERNAL_POLICY_CONTROLLER_V2_REPORT.md` for the full write-up and the
v1→v2 fix table.

## Pipeline

```
prompt → LLM draft → compute_state(draft)            [Vritti/Guna/Kosha/Resonance/PSE]
       → translate(state) → PolicySpec               [explicit, label-semantic]
       → LLM rewrite under policy → final
       → independent LLM judge (rubric, draft-vs-final)
```

## Arms

`draft_only` · `generic_refine` · `nl_policy` · `sentiment_critic` ·
`random_policy` · `shuffled_symbolu` · `relabeled_symbolu` · `symbolu`.

## Two result tiers (kept separate for honesty)

- **STRUCTURAL (real, offline):** the Symbol-U state and per-arm policy are computed
  with no LLM, so **policy divergence** is a genuine result. v2's `relabeled`
  control diverges 0.583 from the real policy — a true ontology-sensitivity test
  (v1's was a 0.000 tautology).
- **QUALITY (needs a real LLM):** rewrite + judge require an API. The `mock` backend
  is plumbing-only and the pilot **refuses to emit a quality verdict**.

## Commands

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.v2.cli state          # state+policy per prompt
python -m symbolu_neural.internal_policy_controller.v2.cli run --backend mock   # plumbing
# real verdict (needs a key — absent in this sandbox):
export ANTHROPIC_API_KEY=...   # or MISTRAL_API_KEY
python -m symbolu_neural.internal_policy_controller.v2.cli run --backend anthropic
python symbolu_neural/internal_policy_controller/v2/tests/test_v2.py
```

## Honesty / limitations

No API key here ⇒ the quality question is **untested**; no scientific claim is made
from mock. Guna/Kosha are **derived from Vritti** (no canonical text→guna/kosha in
the repo) — documented via per-field `provenance`. Single seed/model when run; the
report lists the hardening (≥2 models, ≥3 seeds, human spot-check) for a publishable
result.

## Files

`symbolu_state.py` (full state + provenance) · `policy.py` (translation + 8 arms) ·
`llm.py` (anthropic/mistral/mock) · `judge.py` (independent rubric judge) ·
`data.py` (prompts) · `pilot.py` · `cli.py` · `tests/test_v2.py`.

Isolated; reuses only `complementarity_probe.backends` and `symbolu_core.formulas`.
v1 files untouched.
