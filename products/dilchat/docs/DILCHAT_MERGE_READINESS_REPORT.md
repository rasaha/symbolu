# DilChat — Merge-Readiness Report

> **Merge approval applies only to the internal DilChat technical and validation
> baseline. It does not approve user-facing Guna Milan, public astrology
> deployment, or production launch.**

This report records the final merge-readiness audit of the DilChat backend and
validation baseline into the repository's default branch. It is a repository
integration record only — no new DilChat functionality, no Guna Milan scoring, no
deployment.

---

## 1. Verified repository state

| Item | Value |
|------|-------|
| Repository | `rasaha/symbolu` (public) |
| Default branch (GitHub authoritative) | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Default-branch tip (pre-merge) | `fb68a842` |
| DilChat head branch | `claude/dilchat-backend-design-e0douc` |
| DilChat head (pre-sync) | `2e63d2f2` |
| Merge-base (fork point) | `379a6366` |
| Synced DilChat head (after integrating default) | `4d91d807` |
| Ahead / behind at audit start | 6 ahead / 33 behind default |

The default branch is **not** `main`; GitHub reports the repo `default_branch` as the
`setup-symbolu-monorepo` branch, which is the base used here.

## 2. Default-branch synchronization

The default branch had advanced 33 commits after the DilChat branch was created
(touching `packages/`, `cloud_*` controllers, root `conftest.py`, and non-DilChat
CI workflows). Integration strategy: a **non-fast-forward merge** of the default
branch into the DilChat branch (`4d91d807`).

- **Conflicts:** none. The DilChat branch changes only files under
  `products/dilchat/`; the default branch changed no DilChat file — **zero file
  overlap**, so the merge was automatic.
- Post-sync confirmations:
  - **One coherent migration lineage** — `dfd7ee81e09c → 9c2b82ab02d2 → a1b2c3d4e5f6 → b2c3d4e5f6a7` (single Alembic head; DilChat is the only Alembic project in the repo).
  - **No duplicated revision IDs.**
  - **No accidental root-package inclusion** — root `pyproject.toml` (`name="symbolu"`, `requires-python>=3.10`) does not reference DilChat; DilChat is self-contained with its own `pyproject.toml` (`requires-python>=3.12`).
  - **No Python-version conflict** — DilChat pins 3.12+ independently by design (documented in the DilChat README); the monorepo root pins 3.10+.
  - **No CI-workflow collision** — the DilChat branch adds no workflow; root `pytest` `testpaths=["tests"]` does not collect `products/dilchat/tests`.
  - **No unrelated file deletion** — the merge introduced additions only; `products/dilchat/` is byte-identical to `2e63d2f2`.

## 3. Diff scope

The pull-request diff (`fb68a842...4d91d807`) is **156 files, all within
`products/dilchat/`**. No file outside `products/dilchat/` is modified by the
DilChat branch.

- **Files outside `products/dilchat/`:** none.
- **New executables:** none. **Binary/db/artifact/ephemeris files:** none.

## 4. Validation commands, tool versions, results

Environment: local venv (Python 3.12.3) + local PostgreSQL 16.13 (port 5433, unix socket).

| Tool | Version |
|------|---------|
| Python | 3.12.3 |
| ruff | 0.16.1 |
| mypy | 2.3.0 |
| FastAPI | 0.141.1 |
| SQLAlchemy | 2.0.51 |
| Pydantic | 2.13.4 |
| PostgreSQL | 16.13 |

### A. Installation & static quality
- `pip install -e ".[test,dev]"` → **OK**
- `ruff check src tests scripts` → **All checks passed**
- `mypy src` → **Success: no issues in 53 source files**
- Import smoke (`import ugence_dilchat; create_app`) → **OK**
- FastAPI app construction → **OK**

### B. Tests
- Full DilChat suite (`pytest`) → **197 passed, 0 failed**
- Independent-reference astronomy, interval-boundary completeness, property-based, auth/session, authorization + existence-nondisclosure, RLS (non-owner), SECURITY DEFINER, rule-pack control + tamper-detection (12), no-Guna-route guard → all included and green.
- Provider/licensing subset (`-k "licens or swiss or fake or provider or synthetic or registry or config"`) → **21 passed**.

> Note: an initial run showed 15 failures caused solely by the local PostgreSQL
> server being down (connection refused). After restarting the server, the full
> suite passed 197/0. This was an environment condition, not a code regression.

### C. PostgreSQL
- Upgrade base→head, downgrade→base, re-upgrade→head → **all OK**
- Exactly **one** Alembic head: `b2c3d4e5f6a7`
- Existing migrations **not rewritten** (revision chain unchanged).
- Runtime roles `dilchat_app` / `dilchat_worker` / `dilchat_readonly`: **not** superuser, **not** BYPASSRLS, **not** table owners (all tables owned by `postgres`).
- `dilchat_secfn_owner`: BYPASSRLS (by design for SECURITY DEFINER) **and NOLOGIN**.
- RLS **enabled + forced** on all 10 tables (`users`, `user_sessions`, `birth_profiles`, `natal_chart_snapshots`, `couples`, `couple_memberships`, `couple_invitations`, `consent_events`, `shared_artifacts`, `audit_events`).

### D. OpenAPI
- Generated **OpenAPI 3.1.0**; validated with `openapi-spec-validator` → **VALID**.
- **19 paths**, none containing `guna`, `compatibility`, `kundli`, `match`, `milan`, or `ashtakoot`.
- Uncertainty schemas present: `NatalMoonResponse`, `FieldResultModel`, `UtcIntervalModel`. Structured problem+json error handling present (`errors.py`, covered by the suite).
- Path inventory: `/v1/auth/{login,logout,logout-all,refresh,register}`, `/v1/users/me`, `/v1/birth-profiles`, `/v1/birth-profiles/me`, `/v1/natal/moon`, `/v1/natal/moon/latest`, `/v1/couples/current`, `/v1/couples/invitations`, `/v1/couples/invitations/{token}/accept`, `/v1/couples/{couple_id}/unpair`, `/v1/consents`, `/v1/shared-artifacts`, `/v1/shared-artifacts/{artifact_id}`, `/v1/health`, `/v1/readiness`.

### E. Provider & licensing guards
- `fake` provider **refused** in `qa`, `staging`, `production` (ValidationError).
- `fake` results stamped `synthetic_calculation=true`; never persisted as authoritative.
- Unlicensed Swiss adapter **refused** in production (`swiss_production_licensed=false` → ValidationError); staging/production reject the free dev adapter.
- No silent provider fallback. Public production deployment remains **blocked** (DEC-007 / OQ-10).

### F. Guna fail-closed controls
- Rule-pack verdict **`RULE_PACK_BLOCKED`**; `pack_control.json` `derived_executable=false`, 6 blockers, **0 approved rules**, **4 unresolved conflict topics**.
- `manifest.executable=false`; all 6 parihara rules `enabled:false`.
- No source falsely frozen (overall `PENDING_ACQUISITION`; frozen set empty).
- No reviewer approval fabricated (`DILCHAT_GUNA_DOMAIN_REVIEW_RECORD.md` = `DOMAIN_REVIEW_PENDING`).
- `scripts/validate_rule_pack.py` → **PASSED**.
- No production source module computes a Guna score; no user-facing route returns one.

### G. Repository hygiene
- Secret scan → none. Database-file scan → none. Binary/build-artifact scan → none.
- Copyrighted-book/scan check → no Devanagari blocks, no verbatim book passages, no `.se1`/ephemeris data. (Long lines in the diff are original DilChat design prose.)
- Executable-file review → no new `100755` files.

## 5. Known unresolved external gates (do not block internal merge)

- Exact classical editions must be **acquired and frozen** (currently identified, `PENDING_ACQUISITION`).
- **Four source conflicts** unresolved (Vashya form, Yoni gradations, Gana Deva×Rakshasa, Bhakoot friendly-lord relief).
- **Qualified Jyotisha/Sanskrit domain review** pending (never fabricated).
- **Swiss production licensing** unresolved (AGPL vs Astrodienst professional license; DEC-007 / OQ-10).

These are external/product gates; the corresponding capabilities remain technically
disabled and fail closed.

## 6. Merge recommendation

**`MERGE_READY_WITH_NON_PRODUCTION_CONDITIONS`.**

All implementation and integration gates pass; the branch is cleanly mergeable
against the latest default branch. Guna authority and Swiss production licensing
remain unresolved, but the corresponding capabilities are technically disabled and
fail closed. The merge introduces an **internal experimental backend and
validation baseline only**.

## 7. Production-readiness disclaimer

This baseline is **not production-ready**. It contains no user-facing Guna Milan,
no compatibility endpoint, no AI relationship features, no frontend, no public
website, no production deployment resources, and no public Swiss Ephemeris service.
Merging it approves the internal technical and validation baseline **only**.
