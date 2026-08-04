# DilChat — Phase A/B Hardening Report

**Scope:** A narrowly-bounded correction/hardening pass over the Phase A/B
foundation. No Guna Milan, daily transit, AI, Living Compatibility, frontend, or
production deployment. Five areas: provider safety, birth-time uncertainty,
category-boundary arithmetic, PostgreSQL RLS, and fixture integrity.

## 1. Verified starting state

| Check | Result |
|-------|--------|
| Branch | `claude/dilchat-backend-design-e0douc` |
| Starting HEAD | `56cf19bf` (expected) |
| Default tip | `379a6366` |
| `56cf19bf` / `f9d3ac46` reachable | yes / yes |
| Working tree | clean |
| Out-of-scope work present | none |
| PostgreSQL | 16.13 (local cluster on :5433) |
| Swiss Ephemeris | `pyswisseph 2.10.03` (Moshier, dev-only) |

## 2. Baseline quality gates (before changes)

`ruff` clean · `mypy` clean (52 files) · **119 passed, 1 skipped** · OpenAPI 3.1,
19 paths, no Guna route. Preserved as the baseline.

## 3. Defects confirmed & corrected

| # | Area | Defect | Correction |
|---|------|--------|-----------|
| A | Provider safety | `fake` described as "production-safe"; no env policy | DEC-029 policy matrix; startup+readiness fail-safe; synthetic marking; no fake authoritative persistence |
| B | Birth-time | UNKNOWN collapsed to one noon chart; APPROXIMATE unmodeled | DEC-031/032 interval model + interval-evaluation service + per-field statuses + Guna eligibility |
| C | Boundaries | `1e-6` epsilon snap-up | DEC-033 exact half-open rational `Decimal` arithmetic |
| D | RLS | No database RLS (app-layer only) | DEC-034 roles + ENABLE/FORCE RLS + policies, proven via non-owner role |
| E | Fixtures | Self-generated goldens implied as validation | DEC-035 `REGRESSION_FIXTURE` vs `INDEPENDENT_REFERENCE_FIXTURE`; PENDING surfaced |

## 4. Migrations added (forward-only; initial migration untouched)

| Revision | Purpose |
|----------|---------|
| `dfd7ee81e09c` | initial (unchanged) |
| `9c2b82ab02d2` | birth-time uncertainty + provider safety columns; single-value natal columns → nullable; `NOT(synthetic AND authoritative)` check; **marks legacy noon rows `requires_recalculation`** (never silently reinterpreted) |
| `a1b2c3d4e5f6` | RLS: context/membership helper functions, 3 runtime roles, ENABLE+FORCE + 14 policies |

Verified on PostgreSQL 16: **upgrade → downgrade(base) → re-upgrade** all clean.

## 5. Provider policy (Area A)

| Environment | Permitted providers |
|-------------|---------------------|
| test | `fake` |
| development | `fake` or Swiss dev adapter |
| qa | Swiss dev adapter (`fake` only with `allow_fake_in_qa`) |
| staging | approved real provider only (`swiss` + `swiss_production_licensed`) |
| production | approved licensed real provider only |

Enforced twice (config validation + registry). Fake stamps
`synthetic_calculation=true`, `provider_kind=SYNTHETIC`; snapshots of fake output are
`synthetic=true, test_only=true, authoritative=false` (DB check + service guard
`SYNTHETIC_PERSIST_FORBIDDEN`). Readiness returns 503 if a production-like env has a
fake/absent provider. No silent fallback; provider is not swapped mid-request.

## 6. Uncertainty model (Area B)

- **EXACT** → single UTC instant (ambiguous/nonexistent still detected); all fields
  `EXACT`.
- **APPROXIMATE** → explicit `uncertainty_minutes` (1..720; never defaulted);
  interval `[t−u, t+u]` in UTC.
- **UNKNOWN** → the whole local civil day `[00:00, next 00:00)`; 23/24/25-h days
  handled.

**Interval-evaluation service** (`astrology/interval.py`): samples the real provider
on a 30-min grid with **adaptive densification** (guaranteeing the step stays below
one pada width so no category is skipped), classifies each sample with the exact
Decimal arithmetic, and reports per-field `EXACT/STABLE/AMBIGUOUS/INDETERMINATE`
with `possible_values` and an explanation trace. Deterministic for the same inputs
and provider version; raises `EPHEMERIS_UNAVAILABLE` if the provider fails.
Uncertainty is never expressed as an invented probability.

**Guna eligibility metadata** (no engine): `ELIGIBLE`,
`INELIGIBLE_AMBIGUOUS_NAKSHATRA`, `INELIGIBLE_AMBIGUOUS_REQUIRED_INPUT`,
`INELIGIBLE_MISSING_TIME`, `REQUIRES_USER_REVIEW`.

## 7. Boundary arithmetic (Area C)

`normalize_longitude → [0,360)`, convert **once** to `Decimal` (9 fractional
digits), then `floor(lon·12/360)`, `floor(lon·27/360)`,
`(floor(lon·108/360) mod 4)+1` over half-open intervals. No epsilon reassignment;
360°→0°; negative/over-360 normalized; trace records the normalized decimal. Tests
use representable Decimal values at exact integer boundaries and immediately
either side, plus Hypothesis property tests.

## 8. RLS model (Area D)

- **Roles:** `dilchat_app`, `dilchat_worker`, `dilchat_readonly` — all
  `NOSUPERUSER NOBYPASSRLS`, no ownership. Append-only tables grant no UPDATE/DELETE.
- **Context:** transaction-local `set_config(..., true)` for
  `app.current_user_id` / `app.current_actor_type` / `app.current_couple_id`
  (DEC-030) — no pool leakage.
- **Policies (14):** owner-only for `users`/`user_sessions` (+ pre-auth `auth`
  carve-out), `birth_profiles`, `natal_chart_snapshots`; active-membership (via
  SECURITY DEFINER `app_is_active_member`) for `couples`, `couple_memberships`,
  `consent_events`, `shared_artifacts`; inviter-only for `couple_invitations`
  (token acceptance via SECURITY DEFINER `app_find_invitation`); own-row read +
  insert-only for `audit_events`.
- **Excluded from user-context RLS:** none — all 10 tables are covered. The
  `auth` actor carve-out on `users`/`user_sessions` is the documented exception
  supporting pre-authentication register/login/refresh.

### Non-owner RLS test evidence (`tests/security/test_rls.py`, 7 tests, all pass)

Run under `SET LOCAL ROLE dilchat_app`/`dilchat_worker` (never as owner):
owner-private access succeeds; cross-private returns 0 rows; active member sees the
shared artifact, stranger sees 0; former member loses access after unpair;
invitations cannot be enumerated but token lookup works; a stale worker cannot
INSERT after revocation (WITH CHECK); runtime role cannot DISABLE RLS or DROP a
policy; runtime role cannot UPDATE immutable shared artifacts or DELETE audit rows;
transaction-local context does not persist on the connection after commit.

## 9. Fixture classification (Area E)

`tests/fixtures/golden_charts.json` → `REGRESSION_FIXTURE` (provider version +
derivation method recorded; change-detection only).
`tests/fixtures/independent_reference_charts.json` → `INDEPENDENT_REFERENCE_FIXTURE`
schema + harness, **empty**, status `INDEPENDENT_REFERENCE_VALIDATION_PENDING`. The
harness test reports **XFAIL** while empty, so the pending external validation is
explicit. No independent values were fabricated.

## 10. API changes

- Birth profile accepts `uncertainty_minutes`; returns `utc_interval` +
  `uncertainty_minutes`.
- Natal response is uncertainty-aware: `utc_interval`, `moon_longitude_start/end`,
  `moon_rashi|nakshatra|pada` as `{status, value|possible_values}`,
  `guna_eligibility`, `synthetic_calculation`, `authoritative`, `test_only`,
  provenance with `provider_kind`. No single-longitude "answer" for uncertain input.
- Structured errors added: `MISSING_APPROXIMATION_INTERVAL`,
  `PROVIDER_NOT_PERMITTED`, `SYNTHETIC_PERSIST_FORBIDDEN`, `UNCERTAIN_CLASSIFICATION`
  (plus the existing ambiguous/nonexistent/provider-unavailable).
- No Guna route. OpenAPI 3.1 regenerated & validated (19 paths, 23 schemas,
  uncertainty schemas present).

## 11. Test commands & exact results

```
$ ruff check src tests                 → All checks passed!
$ mypy src                             → Success: no issues found in 53 source files
$ pytest -m "not postgres"            → (SQLite) all pass
$ DILCHAT_TEST_DATABASE_URL=… pytest  → 146 passed, 1 xfailed
$ pip install -e .  (clean venv)       → import OK
$ dilchat-openapi                      → OpenAPI 3.1.0, 19 paths, no guna, uncertainty schemas
```

**147 tests** (unit 96 / integration 29 / security 22). 1 **xfail** =
`INDEPENDENT_REFERENCE_VALIDATION_PENDING` (deliberate, not hidden). PostgreSQL
migration + RLS tests included.

## 12. Unresolved external gates (do not block this hardening task)

- **Independent astronomical validation** — `INDEPENDENT_REFERENCE_VALIDATION_PENDING`.
- **Swiss Ephemeris production license** — dev/test only (DEC-007/OQ-10).
- **Guna authoritative source** — `RULE_PACK_BLOCKED`; no engine implemented.

## 13. Deviations from design

- Enum-as-String+CHECK and a `UTCDateTime` decorator retained for SQLite-test
  portability; RLS/migration DDL is PostgreSQL-only (SQLite no-ops).
- `users`/`user_sessions` carry a pre-auth `auth`-actor RLS carve-out (documented)
  to support register/login/refresh before a user context exists.
- Field-level envelope encryption of SENSITIVE columns remains a later-phase item
  (columns classified; values never logged).

## 14. Founder decision surfaced

**OQ-14** — whether ended couples retain read access to previously-approved shared
artifacts. Current RLS **revokes** shared read on unpair; retained-history is a
founder decision (DEC-034).

## 15. Verdict

**`PHASE_A_B_HARDENING_COMPLETE_WITH_EXTERNAL_VALIDATION_PENDING`.** All five
hardening areas are implemented; ruff/mypy/tests/migrations/RLS(non-owner)/OpenAPI
gates pass. Independent astronomical reference validation remains an explicit,
visible external condition (XFAIL), so the stricter `PHASE_A_B_HARDENING_COMPLETE`
is intentionally not claimed.

### Maximum next phase permitted (do not start now)

Freeze and verify the selected *Muhurta Chintamani* and B. V. Raman source
editions, complete verse/page-to-rule traceability, obtain qualified domain
sign-off, and then implement the internal classical Guna Milan engine.
