# DilChat Backend (Ugence Labs)

DilChat is a mobile-first couples compatibility and communication product
([dilchat.com](https://dilchat.com)). This package is the **backend foundation**
built in the first bounded implementation phase (**Phase A + the non-blocked
parts of Phase B**).

> **Status: Phase A/B foundation — NOT production-ready.**
> This package deliberately contains **no** user-facing Guna Milan, Living
> Compatibility, AI/LLM guidance, daily transits, shared/private chat,
> agreements, mobile/web clients, billing, or production-deployment code. See the
> design and audit documents under [`docs/`](docs/) and the phase report,
> [`docs/DILCHAT_PHASE_A_B_IMPLEMENTATION_REPORT.md`](docs/DILCHAT_PHASE_A_B_IMPLEMENTATION_REPORT.md).

## What this package implements

- FastAPI application factory (`/v1`), health + readiness probes, structured
  problem+json errors, request correlation IDs, environment separation.
- PostgreSQL foundation (SQLAlchemy 2 async, Alembic migrations) with the 10
  authorized entities: `users`, `user_sessions`, `birth_profiles`,
  `natal_chart_snapshots`, `couples`, `couple_memberships`, `couple_invitations`,
  `consent_events`, `shared_artifacts`, `audit_events`.
- Self-managed identity: Argon2id passwords, ES256 access tokens, rotating opaque
  refresh sessions with reuse detection and revocation.
- Birth profiles with historical-timezone local→UTC conversion (ambiguous /
  nonexistent time handling; unknown time never fabricated) and confidence
  propagation.
- A replaceable **AstrologyProvider** interface governed by an environment policy
  (DEC-029): the `fake` provider is a **synthetic test/local-development stub**
  (never production-safe, refused in qa/staging/production, stamped
  `synthetic_calculation=true`, never persisted as authoritative). Natal Moon is
  evaluated as an **uncertainty interval** (EXACT / APPROXIMATE / UNKNOWN) with
  per-field `STABLE/AMBIGUOUS/INDETERMINATE` statuses and exact half-open rational
  boundary arithmetic — no single point estimate for uncertain input.
- **PostgreSQL row-level security** backstop on all 10 tables (non-owner runtime
  roles, ENABLE+FORCE, transaction-local context), proven via a non-owner role.

> **Phase A/B hardening** (provider safety, birth-time uncertainty, exact
> boundaries, RLS, fixture integrity) is recorded in
> [`docs/DILCHAT_PHASE_A_B_HARDENING_REPORT.md`](docs/DILCHAT_PHASE_A_B_HARDENING_REPORT.md)
> and Decision-Log entries DEC-029…DEC-035.
- A pure **three-scope authorization** model (`PRIVATE_A`/`PRIVATE_B`/`SHARED`),
  default-deny, existence non-disclosure (404 not 403), and background-job
  scope re-validation (DEC-027).
- Couple/invitation/consent primitives and immutable, self-contained shared
  artifacts (DEC-028). Append-only audit that never stores secrets or raw
  sensitive payloads.

## Swiss Ephemeris — DEVELOPMENT-ONLY licensing notice

This package can use the **Swiss Ephemeris** (via `pyswisseph`) **only for
internal development, tests, and reference validation**. `pyswisseph` wraps the
**AGPL-3.0** edition of the Swiss Ephemeris.

- It is **disabled by default** (`DILCHAT_ASTROLOGY_PROVIDER=fake`,
  `DILCHAT_ENABLE_SWISS_EPHEMERIS=false`).
- The configuration and provider registry **refuse to enable it in any
  `staging`/`production` environment** (see `config.py` and
  `astrology/registry.py`).
- Public or proprietary production deployment remains **blocked** until Ugence
  Labs either satisfies the AGPL obligations **or** obtains the Swiss Ephemeris
  Professional License (DEC-007 / OQ-10). The free edition is **not** an
  unrestricted commercial license.
- No production deployment manifest or public Swiss Ephemeris service is included
  in this phase. `.se1` data files are not committed.

## Requirements

- Python **3.12+** (this product is pinned independently of the monorepo root).
- PostgreSQL **16** for real use and migration/integration tests.

## Install

```bash
cd products/dilchat
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[test,dev]"       # add ,swiss for the dev-only Swiss adapter
```

## Local development

```bash
# 1. Start a throwaway local PostgreSQL (dev only; not a production manifest).
bash scripts/dev_db.sh
export DILCHAT_DATABASE_URL='postgresql+asyncpg://postgres@/dilchat_dev?host=/tmp&port=5433'
export DILCHAT_ENVIRONMENT=development

# 2. Apply migrations.
alembic upgrade head

# 3. Run the API.
uvicorn ugence_dilchat.app:create_app --factory --port 8080
# Health:    GET http://localhost:8080/v1/health
# Readiness: GET http://localhost:8080/v1/readiness
# OpenAPI:   http://localhost:8080/v1/openapi.json  (or `dilchat-openapi`)
```

## Environment variables

See [`.env.example`](.env.example) for the full reference (all prefixed
`DILCHAT_`). Key ones: `DILCHAT_ENVIRONMENT`, `DILCHAT_DATABASE_URL`,
`DILCHAT_ACCESS_TOKEN_PRIVATE_KEY_PEM` (required in staging/production),
`DILCHAT_ASTROLOGY_PROVIDER`, `DILCHAT_ENABLE_SWISS_EPHEMERIS`,
`DILCHAT_SWISS_EPHEMERIS_MODE`.

## Migrations

```bash
alembic upgrade head            # apply
alembic downgrade base          # roll back
alembic revision --autogenerate -m "message"   # new migration (review before commit)
```

## Tests

```bash
# Fast suite (SQLite in-memory; no server needed):
pytest -m "not postgres"

# Full suite incl. PostgreSQL migration test:
export DILCHAT_TEST_DATABASE_URL='postgresql+asyncpg://postgres@/dilchat_test?host=/tmp&port=5433'
pytest

# Lint & types:
ruff check src tests
mypy src
```

Golden astrology fixtures under `tests/fixtures/` are **development validation
only** (computed with Swiss Moshier mode) and are **not** evidence that the draft
Guna rule pack is correct.

## Layout

```
products/dilchat/
  pyproject.toml  alembic.ini  .env.example
  src/ugence_dilchat/   app.py config.py errors.py db.py base.py
    api/ (routes)  services/  repositories/  infrastructure/ (orm)
    security/  astrology/  audit/  jobs/  domain/
  migrations/           Alembic env + versioned migrations
  tests/                unit/ integration/ security/ fixtures/
  scripts/              dev_db.sh
  rules/                versioned Guna Milan rule pack (DRAFT, gated out)
  docs/                 design + audit documents
```
