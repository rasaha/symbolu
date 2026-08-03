# Installation

`ugence-ai-hiring` is a pure-Python package. It requires **Python >= 3.10**.

The core ships **deterministic, offline, in-memory adapters only**. It is not
production certified and is intended for controlled-pilot evaluation.

## Install from a wheel

```bash
pip install ugence-ai-hiring
```

The canonical import name is `ugence_ai_hiring`:

```python
import ugence_ai_hiring
```

## Editable install from the monorepo

```bash
pip install -e packages/products/ai-hiring
```

## Ugence dependencies

The core has a small set of hard dependencies. There is **no** numpy, no AI/model
SDK (openai/anthropic/mistral/torch/transformers), no database driver, and no web
framework in the core.

- `pydantic>=2`
- `ugence-decision-authority>=1.0.0` — the domain-neutral governance kernel
- `ugence-governance-provider-framework>=0.1.0` — the provider framework
- `ugence-governance-contracts>=0.1.0` — neutral contracts

These Ugence packages must be resolvable from your package index.

## Optional extras

```bash
# HTTP API surface
pip install "ugence-ai-hiring[api]"      # fastapi>=0.100.0, uvicorn>=0.20.0

# Development tooling
pip install "ugence-ai-hiring[dev]"      # pytest, build

# Everything optional
pip install "ugence-ai-hiring[all]"      # fastapi, uvicorn
```

## Verify the install

```bash
python -m ugence_ai_hiring version
python -m ugence_ai_hiring verify
```

`verify` asserts the package's safety/governance invariants and prints PASS/FAIL.

## Backward-compatible import

The wheel also ships a logic-free `ai_hiring` compatibility facade, so
`import ai_hiring` continues to work and re-exports the same objects. See
[MIGRATION_FROM_AI_HIRING.md](MIGRATION_FROM_AI_HIRING.md).
