# Ugence Governance Studio API (P3B)

A deterministic, **offline** demonstration API over the merged Agent Workforce
Composer (AWC) `workflow_ir.v1` / `workflow_ir.v2` planning surface. It is a
**thin orchestration + serialization layer**: every planning operation is
delegated to the public `ugence-agent-workforce-composer` package, and the API
adds no eligibility, ranking, composition, permission, fallback, replay or
comparison logic of its own.

- Distribution: `ugence-governance-studio-api`
- Python namespace: `ugence_governance_studio_api`
- Version: `0.1.0` (product `0.1.0`)
- API contract: `governance_studio.api.v1`
- AWC dependency: `ugence-agent-workforce-composer>=0.2.1`

Synthetic demonstration data · planning only · **no agent execution, no
permission granting, no business-action authorization**.

## What it exposes

Scenario discovery & execution, workflow validation/adaptation (v1 + v2),
v1/v2 adaptation comparison, hard-constraint eligibility, candidate ranking,
team composition, permission-bound proposals, fallback planning, AgentTeamPlan,
explanation projections, deterministic replay, plan comparison, controlled
what-if perturbations, artifact export, and health/readiness/version metadata.

See [`../docs/API_ENDPOINTS.md`](../docs/API_ENDPOINTS.md) for the full list.

## Quick start

```bash
# from the repo root (dev mode; sources wired via conftest / PYTHONPATH)
pip install "pydantic>=2" fastapi uvicorn httpx
export PYTHONPATH=apps/ugence-governance-studio/backend/src:\
packages/capabilities/agent-workforce-composer/src

# run the offline CLI
python -m ugence_governance_studio_api.cli version
python -m ugence_governance_studio_api.cli run-scenario procurement
python -m ugence_governance_studio_api.cli serve   # 127.0.0.1:8000
```

Installed (`pip install .`) the console script `ugence-governance-studio-api`
provides the same commands.

## Layout

```
backend/
├── pyproject.toml
├── src/ugence_governance_studio_api/
│   ├── app.py              # create_app(settings) factory
│   ├── api/                # routers (thin)
│   ├── contracts/          # request/response envelopes (strict)
│   ├── services/           # AWC orchestration, scenario execution, explanations
│   ├── scenarios/          # read-only scenario catalog (bundled fixtures)
│   ├── security/           # headers, body-size limit, auth/rate-limit seams
│   ├── serialization/      # canonical JSON (presentation only)
│   ├── settings.py  version.py  cli.py  openapi.py
│   └── data/               # bundled read-only P3A + v2 conformance fixtures
├── scripts/                # verify_openapi.py, public_api_snapshot.py, verify_distribution.py
└── tests/
```

## Recording seams need a vocabulary configured (breaking, from this change)

The registry, data-use and vendor seams record governed labels, and since those packages
took their vocabulary bindings (`VV-A` to `VV-E`, authorized by `PUB-2`) a label on a new
record must name the published vocabulary it was written against. `PUB-2` forbids
defaulting an absent reference to the current vocabulary, so this app does not invent
one.

`build_studio_context` therefore takes four more optional dependencies:

| Parameter | Seam | Vocabulary |
|---|---|---|
| `system_classification_vocabulary` | registry | `eu-ai-act-system-classification` |
| `data_classification_vocabulary` | data use | `data-classification` |
| `data_use_purpose_vocabulary` | data use | `data-use-purpose` |
| `vendor_posture_vocabulary` | vendor | `vendor-dependency-assessment-state` |

Each is the *package's own* `VocabularyBinding(vocabulary, version,
specification_digest)`. Data use needs **both** of its two: `VV-D` makes them
independent, so a deployment that configures one and not the other has configured
neither.

**A deployment that upgrades without configuring these keeps working and stops
recording.** A seam handed a store but no vocabulary reports itself unavailable and names
the gap, exactly as it already does when handed no store — reads are unaffected. That is
this app's existing rule applied to a new dependency, not a new one: a service handed
nothing never substitutes a stub.

The vocabulary is deployment configuration rather than a request field. The v2 contract
is frozen, and which taxonomy an organization records against belongs to the deployment
rather than to the call; whether an administrator should be able to override it per
request is a product question and is not settled here.

## Determinism & boundaries

Identical logical inputs always produce identical AWC results and fingerprints.
`request_id` and server timing are excluded from logical fingerprints. The API
performs no external network access, no shell/subprocess execution, no arbitrary
file access, and no dynamic code execution during domain evaluation. See
[`../docs/DETERMINISM.md`](../docs/DETERMINISM.md) and
[`../docs/SECURITY_BOUNDARY.md`](../docs/SECURITY_BOUNDARY.md).

## Verification

```bash
python -m pytest apps/ugence-governance-studio/backend/tests           # unit/API suite
python apps/ugence-governance-studio/backend/scripts/verify_openapi.py  # OpenAPI drift
python apps/ugence-governance-studio/backend/scripts/verify_distribution.py  # isolated wheel
```
