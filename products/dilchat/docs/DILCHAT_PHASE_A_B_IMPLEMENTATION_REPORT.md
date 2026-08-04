# DilChat — Phase A / Phase B (non-blocked) Implementation Report

> **Hardening update (Phase A/B):** Superseded in part by the Phase A/B hardening pass. See `DILCHAT_PHASE_A_B_HARDENING_REPORT.md` and Decision-Log DEC-029…DEC-035.

**Scope:** First bounded backend implementation — Phase A plus the explicitly
non-blocked parts of Phase B. **No** user-facing Guna Milan, Living Compatibility,
AI guidance, chat, agreements, or production deployment.

## 1. Verified starting state (live-state gate)

| Check | Result |
|-------|--------|
| Branch | `claude/dilchat-backend-design-e0douc` |
| HEAD at start | `f9d3ac46` (the expected prior audit commit) |
| Default branch tip | `379a6366` (`claude/setup-symbolu-monorepo-…`) |
| Working tree | clean |
| `f9d3ac46` reachable | yes (it was HEAD) |
| Design + audit docs | all 17 present |
| Prior implementation under `products/dilchat/` | none (clean slate) |
| Monorepo DB conventions | none (no SQLAlchemy/Alembic anywhere) — DilChat introduces its own stack |
| Env | Python 3.12.3 present; PostgreSQL 16 available; `pyswisseph 2.10.03` (dev-only) |

**Discrepancies:** none. State matched expectations.

## 2. Implementation scope delivered

Modular monolith (one FastAPI app, Python 3.12) under
`products/dilchat/src/ugence_dilchat/`:

- **FastAPI foundation** — app factory, `/v1` prefix, `/v1/health`,
  `/v1/readiness`, problem+json error model with canonical codes, correlation-ID
  middleware, structured logging with redaction, `pydantic-settings` config with
  environment separation and production guards. Route handlers hold no business
  logic (they delegate to services via a DI `ServiceRegistry`).
- **PostgreSQL foundation** — SQLAlchemy 2 async, Alembic migrations, per-request
  transaction boundary + standalone `transaction()` for jobs, repository
  abstractions, UUID PKs, UTC-aware timestamps (portable `UTCDateTime`),
  version-tuple uniqueness and CHECK constraints.
- **Identity & users** — Argon2id, ES256 access JWT, rotating opaque refresh
  sessions, reuse detection (chain revocation), logout / logout-all, default-deny
  auth dependency with server-side session validation.
- **Birth profiles** — versioned; historical IANA tz local→UTC; ambiguous
  (requires resolution) and nonexistent local times rejected explicitly; unknown
  time never fabricated (no UTC instant, lowered confidence); confidence
  propagation.
- **Astrology provider interface** — `AstrologyProvider` port + `Provenance`;
  deterministic default `FakeAstrologyProvider`; dev/test `SwissEphemerisProvider`
  (Lahiri, longitude normalized to [0,360), explicit `swieph`/`moshier` mode, no
  silent fallback, production-disabled).
- **Natal Moon derivation** — deterministic rashi/nakshatra/pada with a documented
  boundary snap-up policy and reproducible trace; immutable snapshots idempotent
  by version tuple.
- **Three-scope authorization** — pure `authorize*` functions (default-deny,
  404-not-403 existence non-disclosure), shared access requires active membership,
  background-job write-time re-validation (DEC-027).
- **Couple / invitation / consent** — single-use expiring invitations, explicit
  authenticated acceptance, immediate unpair revocation, consent events, and
  immutable self-contained shared artifacts with no cross-private FK (DEC-028).
- **Audit** — append-only, sensitive-value-free (provenance whitelisted).

## 3. Files added

52 source modules (`src/ugence_dilchat`, ~3.77k LOC), 14 test modules
(`tests/`, ~1.22k LOC), 1 Alembic migration, packaging + config
(`pyproject.toml`, `alembic.ini`, `.env.example`, `.gitignore`),
`scripts/dev_db.sh`, this report, and README rewrite. No files outside
`products/dilchat/` were changed.

## 4. Architecture implemented

```
api/routes → api/deps (ServiceRegistry) → services/* → repositories/* → infrastructure/orm
                     │                          │
              security/* (tokens, scope)   astrology/* (provider, derivation)
                     │
                  audit/*, jobs/*, domain/enums
```

Layering is one-directional (routes → services → repositories → ORM). External
boundaries (astrology, tokens, geocoding-ready) are interfaces.

## 5. Database tables & migration

Tables (Alembic revision `dfd7ee81e09c`, `down_revision = None`): `users`,
`user_sessions`, `birth_profiles`, `natal_chart_snapshots`, `couples`,
`couple_memberships`, `couple_invitations`, `consent_events`, `shared_artifacts`,
`audit_events`. Verified to **apply to a clean PostgreSQL 16**, **downgrade to
base**, and **re-apply** (test `test_migrations_apply_downgrade_reapply`, and CLI).

## 6. API routes (19)

```
GET  /v1/health                                 GET  /v1/readiness
POST /v1/auth/register  POST /v1/auth/login  POST /v1/auth/refresh
POST /v1/auth/logout    POST /v1/auth/logout-all
GET  /v1/users/me
POST /v1/birth-profiles  GET /v1/birth-profiles/me  PATCH /v1/birth-profiles/me
POST /v1/natal/moon      GET /v1/natal/moon/latest
POST /v1/couples/invitations  POST /v1/couples/invitations/{token}/accept
POST /v1/couples/{couple_id}/unpair  GET /v1/couples/current
POST /v1/consents  POST /v1/shared-artifacts  GET /v1/shared-artifacts/{artifact_id}
```

**No Guna Milan / compatibility route exists** (guarded by
`test_no_guna_route_registered` and the OpenAPI generator).

## 7. Authorization model

Pure decision functions in `security/scope.py`: `authorize_private` (owner-only,
else `DENY_NOT_FOUND`), `authorize_shared` (active membership; non-member →
`DENY_NOT_FOUND`, revoked → `DENY_FORBIDDEN`), `authorize_job_write` (DEC-027).
Default-deny throughout; cross-private access returns 404, never 403.

## 8. Astrology provider & Swiss Ephemeris mode used

- **Default / production-safe:** `FakeAstrologyProvider` (`fake`), deterministic,
  clearly non-astronomical.
- **Development/tests:** `SwissEphemerisProvider` in **`moshier`** mode
  (`pyswisseph-2.10.03`, Lahiri) — used to generate the golden fixtures and in
  golden tests. `swieph` mode is present and **fails explicitly** without `.se1`
  files (no silent fallback), proven by `test_swieph_mode_fails_explicitly_…`.

## 9. Swiss Ephemeris development-only licensing boundary

AGPL dev edition, **disabled by default**, **refused in staging/production** by
both `config.py` (validation) and `astrology/registry.py` (build guard), proven by
`tests/unit/test_licensing_guard.py`. No production Swiss service or deployment
manifest was created. Production use remains **blocked** pending AGPL compliance
or a Professional License (DEC-007 / OQ-10).

## 10. Test commands & exact results

```
# fast suite (SQLite in-memory)
$ pytest -m "not postgres"           → 113 passed, 1 skipped
# full suite (with PostgreSQL migration test)
$ DILCHAT_TEST_DATABASE_URL=postgresql+asyncpg://… pytest   → 119 passed
$ ruff check src tests               → All checks passed!
$ mypy src                           → Success: no issues found in 52 source files
$ pip install -e .  (clean venv)     → import OK, console script present
$ dilchat-openapi                    → openapi 3.1.0, 19 paths, no guna route
```

Coverage by suite: **unit 83**, **integration 21**, **security 15** (total 119).
Highlights: derivation boundary/normalization + Hypothesis property tests; birth
time DST ambiguous/nonexistent/unknown; token rotation + reuse; invitation
single-use/expiry; unpair revokes shared access immediately; consent → immutable
artifact; artifact survives private-source deletion; existence non-disclosure
(404); revoked/expired sessions; stale background-job scope revalidation; audit
has no sensitive values; golden charts (dev-validation) + determinism.

## 11. Unresolved blockers (external launch gates — do NOT block Phase A/B)

- **Guna Milan authoritative source** — rule pack remains `RULE_PACK_BLOCKED`
  (draft, sources unverified). Parsed/validated in isolation only; no user-facing
  score. Structural draft test marked DRAFT_UNVERIFIED.
- **Swiss Ephemeris production license** — unresolved; free edition dev/test only.

## 12. Deviations from the approved design

- **DB portability:** models use a `UTCDateTime` decorator and store enums as
  `String` + CHECK (not native PG ENUM) so the fast test suite can run on SQLite
  while production remains PostgreSQL. Migration DDL is unaffected (timestamptz).
- **Boundary policy made explicit:** a longitude within the 1e-6° storage
  precision below a rashi/nakshatra/pada boundary snaps to the higher bucket
  (documented in `astrology/derivation.py`); this makes the irrational
  nakshatra/pada boundaries deterministic. Consistent with the design's
  "epsilon + defined tolerance" intent.
- **Unknown birth time:** natal derivation uses an **explicit, flagged**
  noon-UTC assumption (`time_assumption = ASSUMED_NOON_UTC_UNKNOWN_PRECISION`) with
  low confidence — never silent, never presented as exact.
- **Rate limiting:** deferred; the error model (`RATE_LIMITED`) and per-request
  correlation hooks exist as the integration point.

## 13. Security findings (from this phase's own tests)

None outstanding. All authorization, existence-non-disclosure, session-revocation,
stale-job, input-validation, and no-sensitive-logging tests pass. Field-level
encryption of SENSITIVE columns (birth coordinates/time, credential hashes) is
classified in the model (`info={"classification": …}`) but envelope encryption is
a later-phase item (documented; values are never logged).

## 14. Verdict & next allowed phase

**Verdict: `PHASE_A_B_COMPLETE_WITH_CONDITIONS`.** All authorized implementation
and quality gates pass; the only open items are the two **external** launch gates
(Guna authoritative source, Swiss production license), which by the task's own
rule do not block internal Phase A/B.

**Maximum next-phase recommendation (do not start now):** proceed to authoritative
Guna-rule verification and, after that gate clears, implement the internal
classical Guna Milan engine and shared compatibility report.
