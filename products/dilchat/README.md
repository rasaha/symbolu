# DilChat Backend (Ugence Labs)

[![dilchat-ci](https://github.com/rasaha/symbolu/actions/workflows/dilchat-ci.yml/badge.svg?branch=claude%2Fsetup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF)](https://github.com/rasaha/symbolu/actions/workflows/dilchat-ci.yml)

DilChat is a mobile-first couples compatibility and communication product
([dilchat.com](https://dilchat.com)). This package is the **backend foundation**
built in the first bounded implementation phase (**Phase A + the non-blocked
parts of Phase B**).

> The `dilchat-ci` badge reflects the **internal development baseline** gate only
> (static quality, PostgreSQL migrations + full tests, OpenAPI + Guna fail-closed
> guards). It is **not** a production-readiness signal — Guna Milan remains
> **blocked and non-executable**.

> **Status: internal development baseline — NOT production-ready.**
> - **Internal development baseline** (backend + validation infrastructure only).
> - **Guna authority: BLOCKED** — classical editions not frozen, four source
>   conflicts unresolved, qualified Jyotisha/Sanskrit review pending.
> - **Rule pack: non-executable** (`RULE_PACK_BLOCKED`; `executable:false`, all
>   parihara disabled, 0 rules approved).
> - **Swiss production licensing: unresolved** (AGPL vs professional license; DEC-007/OQ-10).
> - **User-facing compatibility: disabled** — no Guna score, no compatibility
>   endpoint, no report is produced or exposed.
>
> This package deliberately contains **no** user-facing Guna Milan, Living
> Compatibility, AI/LLM guidance, daily transits, shared/private chat,
> agreements, mobile/web clients, billing, or production-deployment code. See the
> design and audit documents under [`docs/`](docs/) (indexed by
> [`docs/DILCHAT_DOCS_INDEX.md`](docs/DILCHAT_DOCS_INDEX.md)), the phase report
> [`docs/DILCHAT_PHASE_A_B_IMPLEMENTATION_REPORT.md`](docs/DILCHAT_PHASE_A_B_IMPLEMENTATION_REPORT.md),
> and the merge record
> [`docs/DILCHAT_MERGE_READINESS_REPORT.md`](docs/DILCHAT_MERGE_READINESS_REPORT.md).

> **AI Assist V1 direction — documentation only (DEC-048).** A founder-approved
> requirements package describes DilChat's future *AI Assist* capability: a
> **hidden** Guna structural prior (starting at **60 %**, declining to a **30 %**
> floor on qualified evidence), a **separate, temporary** Moon-receptivity signal,
> and **progressively dominant** conversation evidence — with **no user-visible
> Guna score** and **no** claim of classical-authority validation. This is
> **requirements/architecture only**; no AI Assist, chat, scoring, Moon
> calculation, API, model, or migration is implemented, and no runtime Guna rule
> pack is enabled. Start at
> [`docs/DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md`](docs/DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md).
> Next engineering phase remains **Mobile Phase 2 (device/native hardening)**, then
> secure shared chat, then AI Assist.

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

### Astrology & Guna authority validation

Prior-phase astronomy/security evidence:
[independent astronomy](docs/DILCHAT_INDEPENDENT_ASTRO_REFERENCE_VALIDATION.md) (PASS, ≤ 19.8″ vs Astropy/ERFA),
[interval completeness](docs/DILCHAT_INTERVAL_BOUNDARY_COMPLETENESS_PROOF.md) (PROVEN_WITH_LIMITATIONS),
[SECURITY DEFINER / RLS](docs/DILCHAT_SECURITY_DEFINER_RLS_AUDIT.md) (HARDENED).

**Guna source acquisition, adjudication & sign-off preparation (this phase).**
Four separate verdicts — see
[the authority gate](docs/DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md):

| Axis | Verdict |
|------|---------|
| Technical validation | `VALIDATION_INFRASTRUCTURE_COMPLETE` |
| Astronomy | `ASTRONOMY_VALIDATION_PASS_WITH_BOUNDARY_CONDITIONS` |
| Guna authority | **`GUNA_AUTHORITY_VALIDATION_BLOCKED`** |
| Rule pack | **`RULE_PACK_BLOCKED`** |

| Workstream | Document |
|------------|----------|
| Source acquisition (real editions identified, none frozen) | [DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md](docs/DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md) · [DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md](docs/DILCHAT_GUNA_SOURCE_EDITION_FREEZE.md) · [`GUNA_SOURCE_MANIFEST.json`](rules/sources/GUNA_SOURCE_MANIFEST.json) |
| v1 tradition scope | [DILCHAT_GUNA_V1_TRADITION_SCOPE.md](docs/DILCHAT_GUNA_V1_TRADITION_SCOPE.md) |
| Rule adjudication ledger + 4 conflict dossiers | [DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md](docs/DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md) · [DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md](docs/DILCHAT_GUNA_RULE_TRACEABILITY_MATRIX.md) |
| Parihara adjudication (ordered deterministic) | [DILCHAT_PARIHARA_ADJUDICATION_REPORT.md](docs/DILCHAT_PARIHARA_ADJUDICATION_REPORT.md) |
| Manual calculation cases (24 / all 22 categories) | [DILCHAT_GUNA_MANUAL_CALCULATION_REPORT.md](docs/DILCHAT_GUNA_MANUAL_CALCULATION_REPORT.md) |
| Domain review (pending) | [DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md](docs/DILCHAT_GUNA_DOMAIN_REVIEW_PACKAGE.md) · [DILCHAT_GUNA_DOMAIN_REVIEW_RECORD.md](docs/DILCHAT_GUNA_DOMAIN_REVIEW_RECORD.md) |
| Founder decisions (FD-1…FD-10) | [DILCHAT_GUNA_FOUNDER_DECISIONS.md](docs/DILCHAT_GUNA_FOUNDER_DECISIONS.md) |
| Machine-readable pack controls | [`pack_control.json`](rules/ashtakoota_muhurta_chintamani_raman_v1/pack_control.json) · `scripts/validate_rule_pack.py` |

Decision-Log entries DEC-036…DEC-046, OQ-15. The classical Guna rule pack
`ashtakoota_muhurta_chintamani_raman_v1` is **draft, non-executable** and cannot
back user-facing output until source editions are frozen, the four source
conflicts are resolved, manual cases are reviewer-verified, and a qualified
Jyotisha/Sanskrit reviewer signs off. The earlier `ashtakoota_lahiri_classical_v1`
pack is retained as deprecated draft evidence.
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
