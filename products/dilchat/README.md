# DilChat — Backend Design Specification

**DilChat** is a mobile-first couples compatibility and communication product by
**Ugence Labs** (site: [dilchat.com](https://dilchat.com)). It begins with
traditional Vedic Guna Milan compatibility, then helps couples understand and
work through their differences using private AI conversations, a shared couple
workspace, guided conversations, compromise building, and jointly approved
agreements.

> **Product thesis:** *Other astrology applications tell couples whether they
> match. DilChat helps couples understand their differences and build
> compatibility together.*

## Status

**Design phase — specifications only.** This directory currently contains the
implementation-ready backend design. **No production backend code has been
written.** Implementation does not begin until these specifications are
reviewed and explicitly approved (see the roadmap's go/no-go gates).

## Three distinct concepts (never merged)

1. **Classical Compatibility** — traditional Ashtakoota Guna Milan (8 Kootas,
   max 36). Fixed by natal data + a versioned rule pack. AI may *explain* it but
   never recalculate or alter it.
2. **Daily Emotional & Interest Climate** — DilChat interpretations derived from
   the current sidereal Moon transit relative to each person's natal Moon. Not a
   classical guaranteed prediction.
3. **Living Compatibility** — derived from actual couple interactions,
   agreements, and consented feedback. Kept strictly separate from the classical
   Guna Milan score.

## Design documents (`docs/`)

| # | Document | Purpose |
|---|----------|---------|
| 1 | [DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md](docs/DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md) | Goals, personas, journeys, functional/non-functional requirements, MVP boundaries, non-goals, success criteria. |
| 2 | [DILCHAT_BACKEND_ARCHITECTURE.md](docs/DILCHAT_BACKEND_ARCHITECTURE.md) | System context, components, data flows, trust boundaries, Mermaid diagrams. |
| 3 | [DILCHAT_ASTROLOGY_ENGINE_SPEC.md](docs/DILCHAT_ASTROLOGY_ENGINE_SPEC.md) | Astronomy, sidereal config, Guna Milan algorithms, transit engine, interest themes, pseudocode, golden tests. |
| 4 | [DILCHAT_DATA_MODEL.md](docs/DILCHAT_DATA_MODEL.md) | ERD, tables, keys, private/shared ownership, encryption classification, retention, unpairing behavior. |
| 5 | [DILCHAT_API_SPEC.md](docs/DILCHAT_API_SPEC.md) | REST endpoints, schemas, auth, scopes, idempotency, errors, pagination, versioning. |
| 6 | [DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md](docs/DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md) | Three-scope model, consent state machine, threat model, abuse cases, encryption, audit. |
| 7 | [DILCHAT_AI_INTEGRATION_SPEC.md](docs/DILCHAT_AI_INTEGRATION_SPEC.md) | Allowed/prohibited AI tasks, structured schemas, prompt versioning, safety, human approval. |
| 8 | [DILCHAT_TEST_AND_VALIDATION_PLAN.md](docs/DILCHAT_TEST_AND_VALIDATION_PLAN.md) | Unit/integration/authorization/property/golden/DR tests. |
| 9 | [DILCHAT_IMPLEMENTATION_ROADMAP.md](docs/DILCHAT_IMPLEMENTATION_ROADMAP.md) | Phases A–G, dependencies, risks, gates, sprint breakdown, MVP cut line. |
| 10 | [DILCHAT_DECISION_LOG.md](docs/DILCHAT_DECISION_LOG.md) | **Canonical** architecture decisions and open questions. Read this first. |

OpenAPI contract: [`docs/openapi/dilchat.openapi.yaml`](docs/openapi/dilchat.openapi.yaml).
Versioned Guna Milan rule pack: [`rules/ashtakoota_lahiri_classical_v1/`](rules/ashtakoota_lahiri_classical_v1/).

### Pre-implementation verification audit

An independent audit reproduced every design claim from primary evidence. Start with the gate:

| Document | Verdict |
|----------|---------|
| [DILCHAT_IMPLEMENTATION_READINESS_GATE.md](docs/DILCHAT_IMPLEMENTATION_READINESS_GATE.md) | **CONDITIONALLY_READY** (13 gates) |
| [DILCHAT_ARTIFACT_VALIDATION_REPORT.md](docs/DILCHAT_ARTIFACT_VALIDATION_REPORT.md) | Machine-readable validity PASS |
| [DILCHAT_GUNA_RULE_TRACEABILITY_AUDIT.md](docs/DILCHAT_GUNA_RULE_TRACEABILITY_AUDIT.md) | RULE_PACK_BLOCKED |
| [DILCHAT_ASTRONOMY_REPRODUCIBILITY_AUDIT.md](docs/DILCHAT_ASTRONOMY_REPRODUCIBILITY_AUDIT.md) | REPRODUCIBLE_WITH_CONDITIONS |
| [DILCHAT_AUTHORIZATION_AND_LEAKAGE_AUDIT.md](docs/DILCHAT_AUTHORIZATION_AND_LEAKAGE_AUDIT.md) | AUTHZ_SOUND_WITH_FINDINGS |
| [DILCHAT_SCORE_SEPARATION_AUDIT.md](docs/DILCHAT_SCORE_SEPARATION_AUDIT.md) | ENFORCED_WITH_FINDINGS |
| [DILCHAT_LIVING_COMPATIBILITY_SAFETY_AUDIT.md](docs/DILCHAT_LIVING_COMPATIBILITY_SAFETY_AUDIT.md) | NEEDS_SAFEGUARDS_BEFORE_PHASE_G |

The audit added Decision-Log entries DEC-022…DEC-028 (fallback policy corrected; two new
authorization controls).

## Proposed placement in the monorepo

DilChat follows the self-contained `products/<name>/` convention already
established by `products/code-governance/`:

```
products/dilchat/
  README.md              # this file
  docs/                  # the 10 design documents + OpenAPI
  rules/                 # versioned Guna Milan rule packs (JSON)
  # src/, tests/, examples/, pyproject.toml  -> added at implementation time
```

## Canonical technology decisions (see the Decision Log)

Python 3.12+ · FastAPI · PostgreSQL 16 · Redis 7 · arq workers · Swiss
Ephemeris (`pyswisseph`) with Moshier fallback · Lahiri sidereal ayanamsa ·
self-managed auth (Argon2id + ES256 JWT + rotating refresh sessions) ·
AIProvider port (default Anthropic Claude) · React Native mobile · Next.js web ·
self-hosted geocoding/timezone. Modular monolith with 15 strongly isolated
modules and three enforced privacy scopes (`PRIVATE_A`, `PRIVATE_B`, `SHARED`).

## Reading order

1. `DILCHAT_DECISION_LOG.md` (the canon)
2. `DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md`
3. `DILCHAT_BACKEND_ARCHITECTURE.md`
4. `DILCHAT_DATA_MODEL.md` + `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`
5. `DILCHAT_ASTROLOGY_ENGINE_SPEC.md` + `rules/`
6. `DILCHAT_API_SPEC.md` + `DILCHAT_AI_INTEGRATION_SPEC.md`
7. `DILCHAT_TEST_AND_VALIDATION_PLAN.md`
8. `DILCHAT_IMPLEMENTATION_ROADMAP.md`
