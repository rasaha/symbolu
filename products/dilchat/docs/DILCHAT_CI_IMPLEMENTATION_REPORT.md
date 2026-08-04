# DilChat — CI Implementation Report

Dedicated GitHub Actions quality gate for the merged DilChat internal backend
baseline (`products/dilchat/`). This gate validates the **actual merged package**
(not a reduced substitute) and enforces the DilChat fail-closed boundaries. It is
an **internal development gate only** — it does not enable, test, or imply
user-facing Guna Milan, public astrology deployment, or production launch.

## Verified starting state

| Item | Value |
|------|-------|
| Repository | `rasaha/symbolu` |
| Authoritative default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default tip (start) | `36d2a340` (merged PR #1336) |
| Working branch | `dilchat-ci-baseline` (from the default) |
| `products/dilchat/` on default | present (157 files) |
| Existing DilChat workflow | none (this adds the first) |
| Alembic head | `b2c3d4e5f6a7` (single) |
| Baseline tests | 197 passed (ruff clean, mypy clean) |
| Guna/compatibility route | none |

The `dilchat-guna-domain-authority` branch was **not** modified.

## Workflow

- **Path:** `.github/workflows/dilchat-ci.yml`
- **Triggers:**
  - `pull_request` targeting the authoritative default branch;
  - `push` to `claude/setup-symbolu-monorepo-**`;
  - `workflow_dispatch`.
- **Path filters:** `products/dilchat/**`, `.github/workflows/dilchat-ci.yml`.
  The root `conftest.py` is **not** included: DilChat tests run from
  `products/dilchat` with the package's own pytest rootdir/config, so the root
  conftest does not affect DilChat test execution. No unrelated package-only
  change triggers this workflow.
- **Permissions:** `contents: read` only (no write scopes, no secrets, no
  `pull_request_target`, no deployment).
- **Concurrency:** superseded runs on the same ref are cancelled.
- **Runtime:** Ubuntu (GitHub-hosted), Python **3.12**, PostgreSQL **16** service
  container. No multi-version matrix (DilChat pins `>=3.12` and tests one runtime).

## Jobs

### `static` — static quality
- `pip install -e ".[test,dev]"`
- `ruff check src tests scripts`
- `mypy src`
- import smoke (`import ugence_dilchat; create_app`)
- FastAPI app-construction smoke (asserts OpenAPI 3.1)

### `postgres-and-tests` — migrations + full suite
- PostgreSQL 16 service (`dilchat_test`, user `postgres`, **test-only** static
  password `dilchat_ci_test_pw`, port 5432) with a `pg_isready` health check, plus
  an explicit asyncpg readiness wait. **Not** tied to the dev machine's port 5433.
- `pip install -e ".[test,dev,swiss]"` — `swiss` (pyswisseph) is installed so the
  committed Swiss **dev-only** tests run instead of being `importorskip`-skipped.
- Migrations: `upgrade head` → confirm **exactly one** Alembic head →
  `downgrade base` → `upgrade head`.
- **No-silent-skip guard:** asserts the `postgres`-marked tests are actually
  collected (fails if the DB env/service is missing).
- Full suite: `pytest --strict-markers -ra --junitxml=…` (JUnit artifact).
- **No-unexpected-skip guard:** fails if any test is `skipped`/`xfailed` (all deps
  are present in CI, so the committed suite must be 197 passed / 0 skipped).

### `contract-and-guards` — OpenAPI + Guna fail-closed
- `pip install -e ".[test,dev]"` plus `openapi-spec-validator` (no `openapi`
  extra exists; the validator is installed explicitly, not via a guessed extra).
- OpenAPI generation + script no-Guna guard (`ugence_dilchat.scripts_openapi`).
- **OpenAPI 3.1 validation** (`openapi-spec-validator`) + **route-schema
  inspection**: rejects any path *or* operationId/summary/description/tag containing
  `guna`, `compatibility`, `kundli`, `milan`, `ashtakoot`, `koota`, `kuta`,
  `dosha`, `matchmaking` (stronger than path-only string matching).
- **Rule-pack validation** (`scripts/validate_rule_pack.py`): JSON validity,
  duplicate keys, checksums, score maxima, component total = 36, reference
  integrity, executable-state consistency, parihara-disabled, manual-case status.
- **Guna fail-closed guards:** `RULE_PACK_BLOCKED` (derived `executable:false`,
  non-empty blockers), 0 approved rules, ≥1 unresolved conflict topic, all parihara
  disabled, no source `FROZEN`, review record `DOMAIN_REVIEW_PENDING`, and no
  Guna-scoring function in `src/`.
- **Provider/licensing fail-closed guard:** production/staging refuse `fake`;
  production refuses unlicensed Swiss.

## Installation command

From `products/dilchat` (clean environment):
- static: `pip install -e ".[test,dev]"`
- tests: `pip install -e ".[test,dev,swiss]"`
- contract: `pip install -e ".[test,dev]" && pip install "openapi-spec-validator>=0.7"`

## PostgreSQL service configuration

`postgres:16`, DB `dilchat_test`, user `postgres`, **test-only** password
`dilchat_ci_test_pw`, port `5432:5432`, health-checked with `pg_isready`. URLs:
`postgresql+asyncpg://postgres:dilchat_ci_test_pw@localhost:5432/dilchat_test`
(both `DILCHAT_DATABASE_URL` and `DILCHAT_TEST_DATABASE_URL`).
`DILCHAT_ENVIRONMENT=test` for the whole workflow.

## Test count & migration behaviour (local baseline)

- **197 passed, 0 failed, 0 skipped, 0 xfailed** (182 SQLite/no-server + 15
  `postgres`-marked; Swiss dev tests run because `pyswisseph` is installed).
- Migration cycle `upgrade → downgrade base → re-upgrade`: clean; **one** head
  `b2c3d4e5f6a7`; no existing migration rewritten.
- OpenAPI 3.1.0 validated; 19 paths; no Guna/compatibility exposure.
- Guna fail-closed and provider/licensing guards: PASSED.

## Artifact policy

- Uploaded: JUnit XML (`dilchat-junit`), generated OpenAPI JSON (`dilchat-openapi`),
  retention **14 days**.
- **Never** uploaded: PostgreSQL data directories, env files, credentials,
  birth-profile data, private/shared sensitive payloads, source-book scans, or
  ephemeris binaries.
- No coverage threshold added (none exists in the DilChat config).

## Swiss / astronomy policy in CI

- CI is classified `test`; the free Swiss edition is used only under the documented
  dev/test boundary. No production-license flag is set. `fake` is used only where
  tests require synthetic behaviour. Independent-reference tests use the committed
  Astropy/ERFA fixtures (astropy is **not** installed at runtime — the fixtures are
  frozen). No ephemeris files or copyrighted data are committed or uploaded.

## CI bring-up corrections (first real run)

The first GitHub Actions run surfaced two genuine defects, both fixed (no gate
weakened):

1. **RLS / SECURITY DEFINER tests could not connect on CI.** Their raw-asyncpg
   `_dsn()` helper read the host only from the URL query string (defaulting to the
   `/tmp` Unix socket) and ignored the TCP netloc host/port/password. With the CI
   service URL (`…@localhost:5432/…`) they fell back to a nonexistent socket and
   raised `FileNotFoundError`. Fixed in `tests/security/test_rls.py` and
   `tests/security/test_security_definer.py`: `_dsn()` now honours the netloc
   host/port/password with the query params still taking precedence (so the local
   socket-style URL is unchanged). This is a test-support fix — no model,
   migration, or app behaviour changed.
2. **`pytest | tee` masked failures.** The step ran under `bash -e {0}` (no
   `pipefail`), so `tee`'s exit 0 hid pytest's non-zero exit and the job went green
   despite 14 failing tests. Fixed by `set -o pipefail` in the test step, so a test
   failure now fails the job.

Both were verified locally against a TCP (netloc) PostgreSQL URL — the CI-shaped
scenario — yielding **197 passed, 0 skipped**.

## Known limitations

- The three jobs each install the package independently (no shared build cache
  beyond pip's wheel cache); this keeps jobs isolated at a small time cost.
- A JPL-DE (Skyfield) astronomy cross-check remains a future tightening
  (download blocked in the current environments); the Astropy/ERFA fixtures are the
  committed independent reference.
- This gate is not (yet) a required status check under branch protection; making it
  required is a separate repository-policy decision.

## Local reproduction

```bash
cd products/dilchat
python3.12 -m venv .venv && . .venv/bin/activate
# static
pip install -e ".[test,dev]"
ruff check src tests scripts && mypy src
# postgres + tests (point at any PostgreSQL 16)
pip install -e ".[test,dev,swiss]"
export DILCHAT_ENVIRONMENT=test
export DILCHAT_DATABASE_URL='postgresql+asyncpg://postgres:PW@HOST:PORT/dilchat_test'
export DILCHAT_TEST_DATABASE_URL="$DILCHAT_DATABASE_URL"
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest --strict-markers -q
# contract + guards
pip install "openapi-spec-validator>=0.7"
python scripts/validate_rule_pack.py
```

## CI status at completion

Authoritative status is the GitHub Actions **`dilchat-ci`** run on the PR head and,
after merge, on the default branch. Local reproduction of every job command passed
(ruff clean, mypy clean, 197 passed / 0 skipped, migration cycle clean, OpenAPI 3.1
valid, all fail-closed guards passed, `actionlint` clean). The GitHub run IDs and
conclusions are recorded in the task's final report and the PR checks.
