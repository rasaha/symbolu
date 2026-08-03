# Ugence AI Hiring (`ugence-ai-hiring`)

An AI-assisted hiring **governance** product. It provides canonical data
contracts, an audited workflow state machine, deterministic evidence
normalization and assessment, decision cases, governed action-request
preparation, and — enforced in types, services, persistence, and API
permissions, not merely documented — the hard separation between AI
recommendations (advisory) and human employment decisions (binding):

> AI evaluates evidence and produces **advisory** recommendations.
> Only an authenticated, authorized **human** actor may create a **binding**
> employment decision. An AI actor never can.

This distribution ships **no** AI scoring model, candidate-ranking algorithm,
résumé-evaluation model, fairness/bias model, LLM inference, or production
HRIS/ATS/offer/payroll adapter. It ships deterministic, offline, in-memory
adapters only and makes **no** production, scale, fairness, or legal-compliance
claim.

- **Distribution:** `ugence-ai-hiring`
- **Canonical import:** `ugence_ai_hiring`
- **Distribution version:** `0.1.1` (independent wheel packaging lifecycle)
- **Product version:** `0.6.0` (AI Hiring capability maturity, H0–H6)
- **Release classification:** `PACKAGE_READY_FOR_CONTROLLED_PILOT`
- **Production certified:** **No** (`version_info().production_certified == False`)

## Install

```bash
pip install ugence-ai-hiring
```

Editable (from the monorepo):

```bash
pip install -e packages/products/ai-hiring
```

Core dependencies: `pydantic>=2`, `ugence-decision-authority`,
`ugence-governance-provider-framework`, `ugence-governance-contracts`.

Optional extras (all optional; the core installs and runs without any of them):

```bash
pip install "ugence-ai-hiring[api]"          # FastAPI adapter
pip install "ugence-ai-hiring[tap]"          # canonical TAP -> ugence-tap-provider
pip install "ugence-ai-hiring[actiongate]"   # canonical ActionGate -> ugence-actiongate-provider
```

TAP and ActionGate are optional, dependency-injected governance providers — never
core dependencies. The extras resolve the canonical `ugence-tap-provider` /
`ugence-actiongate-provider` distributions. See
[`docs/PROVIDER_DEPENDENCY_MIGRATION.md`](docs/PROVIDER_DEPENDENCY_MIGRATION.md)
and [`docs/TAP_ACTIONGATE_DEPENDENCY_BOUNDARY.md`](docs/TAP_ACTIONGATE_DEPENDENCY_BOUNDARY.md).

## Quickstart

```python
from ugence_ai_hiring import build_in_memory_platform, version_info

platform = build_in_memory_platform()          # deterministic, in-memory
print(version_info().to_dict()["production_certified"])  # -> False
```

```bash
python -m ugence_ai_hiring version   # distribution + product metadata
python -m ugence_ai_hiring verify    # assert safety/governance invariants
python -m ugence_ai_hiring demo      # evidence → assessment → advisory rec → human decision
```

The demo runs fully offline with in-memory repositories and **stops before any
downstream enterprise action is executed**.

## Compatibility

Existing `import ai_hiring` code keeps working: the wheel ships a logic-free
`ai_hiring` compatibility facade that re-exports the identical objects from
`ugence_ai_hiring` (object identity and deep submodule paths preserved). See
[docs/MIGRATION_FROM_AI_HIRING.md](docs/MIGRATION_FROM_AI_HIRING.md).

## Governance boundaries

See [docs/GOVERNANCE_BOUNDARIES.md](docs/GOVERNANCE_BOUNDARIES.md). In brief: AI
output is advisory; binding decisions require an authenticated authorized human;
evidence / assessment / recommendation / decision / override / action request /
authorization response / execution are distinct records; the package prepares
and requests authorization for governed actions but never executes downstream
enterprise effects; and it makes no legal, fairness, or production claim.

## Documentation

Install, quickstart, API reference, architecture, configuration, security,
governance boundaries, deployment, operations, known limitations, versioning,
migration, packaging, and provenance guides live under [`docs/`](docs/).
