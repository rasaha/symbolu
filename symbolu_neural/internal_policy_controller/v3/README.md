# Internal Policy Controller v3

Corrected implementation of **draft → full Symbol-U state → ontology-driven policy →
LLM rewrite → independent judge**, fixing the v2 wiring defects found in
`../V2_AUDIT_AND_V3_PLAN.md`. **Self-contained** (local `llm.py`, `judge.py`,
`data.py` — relocated here from v2 during cleanup so the canonical line no longer
depends on deprecated code). v1/v2 kept intact only as the audited-defective record.

## Key fix: every claimed Symbol-U variable drives a distinct policy axis

`guna→tone`, `vritti→directness`, `kosha→reasoning_style`, `aspect_balance→caution`,
`guna_resonance→uncertainty`, `valence→speculation_reduction`. A **field-influence
self-check** (`cli check`) fails if any policy-driving variable is inert — the exact
defect that invalidated v2. `pse_*`, `kosha_resonance`, `valence_sign` are kept as
**diagnostic-only** (not claimed to drive policy).

## Commands

```bash
export PYTHONPATH=$(pwd)
python -m symbolu_neural.internal_policy_controller.v3.cli check     # self-check gate
python -m symbolu_neural.internal_policy_controller.v3.cli state     # state + policy per prompt
python -m symbolu_neural.internal_policy_controller.v3.cli run --backend mock   # plumbing
# real verdict (needs a key — absent in this sandbox):
export ANTHROPIC_API_KEY=...   # or MISTRAL_API_KEY
python -m symbolu_neural.internal_policy_controller.v3.cli run --backend anthropic
python symbolu_neural/internal_policy_controller/v3/tests/test_v3.py
```

## Status

Structural self-checks PASS (all 6 variables influence policy; 11/12 distinct
policies; no dead axes; relabel permutes guna+kosha+valence). **Quality verdict
UNTESTED** here (no API key) — run on a host with a key. See
`../INTERNAL_POLICY_CONTROLLER_V3_REPORT.md`.
