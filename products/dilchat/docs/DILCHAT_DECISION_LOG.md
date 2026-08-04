# DilChat Backend — Architecture Decision Log

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Status of this document:** Design phase. No production code has been written.
**Repository placement:** `products/dilchat/` (mirrors the existing `products/code-governance/` self-contained-product convention in this monorepo).

> This document is the **canonical reference** for all other DilChat design
> documents. Names, versions, module boundaries, and technology choices defined
> here are authoritative; the other specs cite this log rather than re-deciding.

## How to read a decision

Each decision has a **status**:

| Status | Meaning |
|--------|---------|
| **Accepted** | Decided for the MVP. Build to it. |
| **Proposed** | Recommended default; open to challenge before code starts. |
| **Deferred** | Explicitly out of scope for MVP; revisit post-MVP. |
| **Requires domain review** | Needs a Vedic-astrology domain expert to confirm. |
| **Requires legal review** | Needs counsel (licensing, privacy, jurisdiction). |
| **Requires founder approval** | Product-strategy call reserved for the founder. |

Decisions are labeled as **[Technical]**, **[Traditional Vedic rule]**,
**[DilChat proprietary interpretation]**, or **[Product]** so reviewers can route
them.

---

## 0. Canonical identifiers (authoritative)

Every generated artifact (chart, report, daily profile) MUST carry the provenance
tuple below. These strings are the single source of truth for versioning across
all documents.

| Field | MVP value | Notes |
|-------|-----------|-------|
| `ephemeris_provider` | `swiss` | Fallback: `moshier` (built-in, no data files) |
| `ephemeris_version` | `swe-2.10.03` | Pinned Swiss Ephemeris release |
| `ayanamsa` | `lahiri` | `SE_SIDM_LAHIRI` |
| `zodiac` | `sidereal` | |
| `rule_pack_id` | `ashtakoota_lahiri_classical_v1` | Guna Milan rule pack |
| `transit_model_version` | `dilchat_transit_v1` | Daily transit feature extraction |
| `interpretation_pack_version` | `dilchat_interp_v1` | Koota → domain mappings |
| `interest_model_version` | `dilchat_interest_v1` | Interest-theme scoring |
| `living_compat_model_version` | `dilchat_living_v1` | Behavioral scoring |
| `prompt_pack_version` | `dilchat_prompts_v1` | AI prompt templates |
| `geo_dataset_version` | `geonames-2025-Q3` | Geocoding snapshot |
| `tz_dataset_version` | `tzdata-2025b` | IANA time-zone database |

**Module canonical names (15):** `identity`, `users`, `birth_profiles`,
`astrology`, `guna_milan`, `moon_transits`, `couples`, `consent`, `private_chat`,
`shared_chat`, `journeys`, `agreements`, `ai_guidance`, `feedback`, `audit`.

**Three privacy scopes:** `PRIVATE_A`, `PRIVATE_B`, `SHARED`.

**Python package:** `dilchat` · **Distribution name:** `ugence-dilchat`.

---

## DEC-001 — Repository placement & product boundary
**Status:** Accepted · **[Technical]**

DilChat is a self-contained product at `products/dilchat/`, following the
`products/code-governance/` pattern (`src/dilchat/`, `docs/`, `tests/`,
`examples/`, `pyproject.toml`, `README.md`). It does **not** import from the
Symbolu AGI research packages; it is a commercially independent consumer product
that happens to share the monorepo.

**Conflict identified & resolved:** The monorepo root `pyproject.toml` pins
`requires-python = ">=3.10"`. DilChat pins **`>=3.12`** in its own product
`pyproject.toml` (see DEC-010). This is intentional isolation, not a regression;
DilChat's package is not listed in the root `[tool.setuptools.packages.find]`
include list and is built/tested independently.

**Rejected:** placing DilChat at repo root or under `apps/` — those are internal
Ugence governance tools; consumer product code stays under `products/`.

---

## DEC-002 — Service decomposition: modular monolith
**Status:** Accepted · **[Technical]**

MVP is a **modular monolith**: one deployable FastAPI application, with strongly
isolated in-process modules that communicate only through published module
interfaces (function-call ports), never by reaching into each other's tables.

Enforcement rules:
- Each module owns its own tables (table-name prefix = module name).
- Cross-module reads go through the owning module's service interface, not raw SQL.
- A module may depend only on modules listed below it in the dependency order.
- An import-linter contract (`.importlinter`) forbids illegal cross-module imports.

**Dependency order (lower may not import higher):**
`audit` ← `identity` ← `users` ← `birth_profiles` ← `astrology` ←
{`guna_milan`, `moon_transits`} ← `couples` ← `consent` ←
{`private_chat`, `shared_chat`, `journeys`, `agreements`} ← `ai_guidance` ← `feedback`.

**Rejected:** microservices for MVP — no operational need, and the couple-scope
authorization invariants are far easier to prove inside one transaction boundary.
Extraction path documented in `DILCHAT_BACKEND_ARCHITECTURE.md §Module extraction`.

---

## DEC-003 — Backend framework: FastAPI
**Status:** Accepted · **[Technical]**

FastAPI + Pydantic v2 + Uvicorn/Gunicorn. Consistent with existing monorepo usage
(`ugence_console_api`, `apps/console`). Async-first to match the transit/AI I/O
profile. OpenAPI generated from the app; the hand-authored spec in
`DILCHAT_API_SPEC.md` / `openapi/dilchat.openapi.yaml` is the design contract.

**Rejected:** Django (heavier, sync-first ORM), Litestar (smaller ecosystem).

---

## DEC-004 — Database: PostgreSQL 16
**Status:** Accepted · **[Technical]**

PostgreSQL 16. Rationale: strong transactional guarantees for consent/pairing,
row-level security (RLS) as defense-in-depth for scope isolation, `jsonb` for
calculation traces and rule-pack payloads, `pgcrypto` availability, mature
point-in-time recovery. SQLAlchemy 2.x (async) + Alembic migrations.

**Rejected:** MongoDB (weak cross-document transactions for consent flows),
MySQL (weaker `jsonb`/RLS story).

---

## DEC-005 — Cache & queue broker: Redis 7
**Status:** Accepted · **[Technical]**

Redis 7 for: global-transit cache, rate-limit counters, idempotency keys,
short-lived session lookups, and the background-job broker. Redis is a cache and
broker only — never the source of truth. All authoritative state is in Postgres.

---

## DEC-006 — Background workers: arq
**Status:** Proposed · **[Technical]**

**arq** (async, Redis-backed) for background jobs and cron-style scheduling
(nightly global-transit precompute, versioned recalculation sweeps, data-export
bundling, deletion finalization). Chosen over Celery because it is async-native
(matches FastAPI), lightweight, and has first-class cron jobs.

**Fallback if arq proves limiting at scale:** Celery + Redis. The job interface
(`enqueue(job_name, **kwargs)`) is abstracted so the broker/runner can be swapped
without touching callers.

**Rejected for MVP:** Temporal/durable-execution engines — overkill until
multi-step sagas appear.

---

## DEC-007 — Ephemeris: Swiss Ephemeris (pyswisseph) with Moshier fallback
**Status:** Accepted (engine) · **Requires legal review** (license) · **[Technical]**

Astronomy is computed in-house via **`pyswisseph`** (Python binding to Swiss
Ephemeris), running inside the `astrology` module. No recurring third-party
astrology API is used in production (an external API may be used **only** as a
development validation oracle — see DEC-020).

- **Ephemeris files:** `semo_*.se1` (Moon) and `sepl_*.se1` (planets, for
  ascendant/house context) covering the supported birth-year range, baked into
  the container image at a pinned checksum. `seas_*.se1` only if asteroids are
  later needed (not MVP).
- **Fallback:** the built-in **Moshier** analytical ephemeris (`swe.FLG_MOSELPH`),
  which needs no data files. Moon longitude accuracy (~arcminutes) is more than
  sufficient for rashi/nakshatra/pada boundaries. If the `.se1` files are
  unavailable at startup, the engine degrades to Moshier and stamps
  `ephemeris_provider="moshier"` on outputs, lowering confidence and emitting an
  ops alert. It never silently produces an unlabeled result.
- **Thread/process safety:** the Swiss Ephemeris C library holds global state
  (ayanamsa mode, ephemeris path) and is **not** thread-safe for concurrent
  mutation. DilChat wraps it behind a **single-threaded calculation worker pool**
  (dedicated process pool; each process sets `swe.set_ephe_path` /
  `swe.set_sid_mode` once at init and never mutates mid-request). Calls are
  submitted to this pool; the FastAPI async handlers never call `swe.*` directly.

**LICENSING (must resolve before launch):** Swiss Ephemeris is dual-licensed —
**AGPL-3.0** or a **paid Astrodienst professional license**. Operating DilChat as
a hosted service over an AGPL build has copyleft/network-use implications for the
surrounding proprietary code. **Recommendation:** obtain the Astrodienst
professional/commercial license before public launch; until then, development may
proceed on the AGPL build within an isolated module, and the Moshier fallback
(public-domain lineage) is retained as a licensing safety valve. → **Requires
legal review.**

---

## DEC-008 — Ayanamsa: Lahiri (configurable, versioned)
**Status:** Accepted · **[Traditional Vedic rule]**

Default sidereal ayanamsa is **Lahiri** (`SE_SIDM_LAHIRI`), the Indian
government / Rashtriya Panchang standard and the most common basis for Guna
Milan. The ayanamsa is a versioned input (`ayanamsa="lahiri"`) recorded on every
chart; alternative ayanamsas (Raman, KP) are post-MVP rule-pack variants, never
silently mixed.

---

## DEC-009 — Guna Milan rule-pack source
**Status:** Requires domain review · **Requires founder approval** · **[Traditional Vedic rule]**

The MVP ships one rule pack, `ashtakoota_lahiri_classical_v1`, encoding the
standard eight-Koota Ashtakoota tables. The **exact textual source** (e.g., a
named authority such as B. V. Raman's *Muhurta*/*Hindu Predictive Astrology*
tables, or another agreed classical reference) must be fixed and cited in
`rules/ashtakoota_lahiri_classical_v1/sources.json` before the pack is frozen.
Until a domain expert signs off, the pack is marked `draft: true` and cannot be
used for a user-facing report. See **Open Questions OQ-1**.

Sub-decision **DEC-009a — Directional (bride/groom) logic:** Tara and Bhakoot (and
Graha Maitri in some schools) are computed with defined ordering. **Recommendation:**
retain classical bride/groom directionality but capture partner *roles* neutrally
(`role: "seeker" | "partner"` mapped to bride/groom per the rule pack) so the
product is not forced to assign gender. Which partner maps to which classical role
is a rule-pack + product decision. → **Requires domain review** (OQ-2).

---

## DEC-010 — Language/runtime: Python 3.12+
**Status:** Accepted · **[Technical]**

DilChat targets **Python 3.12+** (per-product pin), for `zoneinfo` maturity,
`tomllib`, typing improvements, and faster interpreter. See DEC-001 for the
monorepo-pin conflict resolution.

---

## DEC-011 — Authentication & session model
**Status:** Accepted (core) · **Requires legal review** (social IdP terms) · **[Technical]**

Self-managed identity in the `identity` module (couples data is too sensitive to
hand wholesale to a third-party auth SaaS, and we need fine control over session
revocation and export/delete):

- **Password hashing:** Argon2id (`argon2-cffi`).
- **Access tokens:** short-lived (10 min) JWT (asymmetric ES256), stateless.
- **Refresh tokens:** opaque, rotating, stored server-side (hashed) as `Session`
  rows so any session can be revoked immediately (invariant: unpairing and
  logout must revoke fast).
- **Social / federated login:** OIDC for **Sign in with Apple** (required by App
  Store when other social login is offered) and **Google**; phone/OTP via an SMS
  provider; email via magic-link or password. Provider-specific data-sharing
  terms → **Requires legal review**.
- **Biometric unlock** is a client-side gate only (Face ID / fingerprint unlocks
  a locally stored refresh token); the backend never sees biometrics.

**Rejected for MVP:** Auth0/Cognito/Firebase Auth as the primary store — revisit
only if self-managed ops cost proves high.

---

## DEC-012 — Multi-tenant / scope authorization model
**Status:** Accepted · **[Technical]**

Authorization is **policy-based row-level**, not enterprise multi-tenant. Every
row belonging to user or couple data carries an owning scope
(`PRIVATE_A | PRIVATE_B | SHARED`) and an owning `user_id` and/or `couple_id`.

Two enforcement layers (defense in depth):
1. **Application scope guard** — a mandatory `ScopeContext` (authenticated
   `user_id`, active `couple_id`, resolved scope) is threaded into every query
   through repository helpers that refuse unscoped access. Default deny.
2. **PostgreSQL RLS** — session `SET app.user_id` drives RLS policies on
   scope-bearing tables as a backstop if the app layer is bypassed.

Couple membership is re-verified on every shared-data request; unpairing flips
membership to `revoked` and the guard denies immediately.

---

## DEC-013 — Content movement private → shared: consent-gated projection
**Status:** Accepted · **[Technical + Product]**

Private content never becomes shared by an ordinary row copy. Sharing is a
first-class **ConsentEvent** that produces an immutable **SharedArtifact** — a
bounded, explicitly enumerated projection (e.g., a summary, an agreed statement),
never the raw private message stream. The ConsentEvent records exactly what was
shared, by whom, when, and its revocation policy. The other partner is never told
that a private conversation exists. Full state machine in
`DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`.

---

## DEC-014 — AI provider abstraction
**Status:** Accepted (abstraction) · **Requires legal review** (retention terms) · **[Technical]**

The `ai_guidance` module depends on an `AIProvider` **port**, not a concrete
vendor. Adapters implement `complete_structured(task, input, schema) -> validated
output`. Default adapter: **Anthropic Claude** (latest available model at build
time); OpenAI adapter as an alternate. The provider is passed only the minimum
authorized context (DEC-013) and receives **governed structured inputs from
deterministic services** — it never computes astronomy, nakshatra, Guna Milan,
transit scores, or Koota values.

**Data handling:** the chosen provider must offer **zero-retention / no-training**
API terms for user content; confirm and record the contractual terms →
**Requires legal review**. All AI outputs are schema-validated before use and
carry `prompt_pack_version` provenance.

---

## DEC-015 — Mobile client framework: React Native
**Status:** Proposed · **[Product/Technical]**

React Native (Expo managed workflow recommended) for iOS + Android from one
codebase, matching the "primary clients iOS and Android" requirement and the
team's existing React/TypeScript familiarity (`frontend/` uses React). Biometric
unlock via `expo-local-authentication`. This is a client assumption; it does not
constrain the backend, which is a clean HTTP/JSON API.

**Alternative if native performance/SDK depth is needed:** native Swift + Kotlin.

---

## DEC-016 — Web: Next.js for marketing + account portal
**Status:** Proposed · **[Technical]**

dilchat.com marketing site and the web account/consent/export portal use
**Next.js** (SSR/SEO for marketing; secure account management). This differs from
the internal `frontend/` (Vite SPA) intentionally: the internal tool has no SEO
need, the consumer marketing site does.

---

## DEC-017 — Geocoding & historical timezone: self-hosted datasets
**Status:** Proposed · **[Technical]**

No recurring third-party geocoding API as source of truth (cost + birthplace is
sensitive PII). Stack:
- **Geocoding:** bundled **GeoNames** cities dataset (`geonames-2025-Q3`) for
  place → coordinates, served locally. An optional online provider (Mapbox/Google)
  may power *typeahead search UX only*, with the authoritative coordinate stored
  from the local dataset or user confirmation.
- **Coordinate → IANA zone:** `timezonefinder` (offline).
- **Historical local→UTC:** Python `zoneinfo` over pinned **`tzdata-2025b`**,
  which encodes historical offset/DST rules. Ambiguous (fall-back) and
  nonexistent (spring-forward) local times are handled explicitly (see
  `DILCHAT_ASTROLOGY_ENGINE_SPEC.md`), lowering birth-time confidence rather than
  guessing silently.

---

## DEC-018 — Hosting & data residency
**Status:** Proposed · **Requires legal review** · **[Technical]**

Containerized (Docker) deployment on a managed cloud. **Recommendation:** launch
in a single region matching the primary market. If **India-first** (OQ-13), host
in an India region (e.g., AWS `ap-south-1` / GCP `asia-south1`) for latency and
data-residency posture under India's DPDP Act. International launch adds GDPR/CCPA
obligations and possibly regional data partitioning → **Requires legal review**.

---

## DEC-019 — Classical vs. derived score separation (invariant)
**Status:** Accepted · **[Traditional Vedic rule + DilChat proprietary]**

Three score families are stored and versioned **separately** and never merged:
1. **Classical Compatibility** — Ashtakoota Guna Milan (0–36), fixed by natal data
   + rule pack. Immutable once computed for a given version tuple. AI may explain,
   never alter.
2. **Daily Emotional & Interest Climate** — `dilchat_transit_v1` /
   `dilchat_interest_v1` derived interpretations. Labeled DilChat models, not
   classical predictions.
3. **Living Compatibility** — `dilchat_living_v1`, from consented behavioral data.
   Never feeds back into (1).

Behavioral personalization can adjust presentation of (2) within clamped bounds
but can **never** rewrite (1) or astrology history.

---

## DEC-020 — External astrology API: development oracle only
**Status:** Accepted · **[Technical]**

A third-party astrology API (or a reference desktop tool such as Swiss
Ephemeris test vectors / a panchang) may be used **only** in the test suite as a
cross-validation oracle for golden charts. It is never called from production
code paths. See `DILCHAT_TEST_AND_VALIDATION_PLAN.md`.

---

## DEC-021 — Nadi / Yoni / medical & consent safety constraints
**Status:** Accepted · **Requires legal review** · **[DilChat proprietary interpretation + Product]**

Hard product/safety constraints, enforced in the interpretation layer and AI
guardrails:
- **Nadi** is never translated into medical, genetic, fertility, pregnancy, or
  health language. It is presented as *traditional constitutional compatibility*
  only.
- **Yoni** interpretations apply only in a consensual adult romantic context and
  are never sexualized outside it.
- Astrology outputs carry a standing disclaimer and must never be usable as
  evidence for medical, psychiatric, employment, credit, insurance, or legal
  decisions.
- AI must never infer infidelity, sexual consent, psychiatric diagnosis, or
  pressure a user to remain in an unsafe relationship.

→ Wording of disclaimers **Requires legal review**.

---

## Decisions index

| ID | Decision | Status |
|----|----------|--------|
| DEC-001 | Repo placement `products/dilchat/` | Accepted |
| DEC-002 | Modular monolith | Accepted |
| DEC-003 | FastAPI | Accepted |
| DEC-004 | PostgreSQL 16 | Accepted |
| DEC-005 | Redis 7 | Accepted |
| DEC-006 | arq workers | Proposed |
| DEC-007 | Swiss Ephemeris + Moshier fallback | Accepted / legal review |
| DEC-008 | Lahiri ayanamsa | Accepted |
| DEC-009 | Rule-pack source | Domain review / founder approval |
| DEC-010 | Python 3.12+ | Accepted |
| DEC-011 | Self-managed auth + OIDC | Accepted / legal review |
| DEC-012 | Policy-based row-level authz + RLS | Accepted |
| DEC-013 | Consent-gated projection | Accepted |
| DEC-014 | AI provider port | Accepted / legal review |
| DEC-015 | React Native | Proposed |
| DEC-016 | Next.js web | Proposed |
| DEC-017 | Self-hosted geo/tz | Proposed |
| DEC-018 | Hosting & residency | Proposed / legal review |
| DEC-019 | Score-family separation | Accepted |
| DEC-020 | External API = oracle only | Accepted |
| DEC-021 | Nadi/Yoni/medical safety | Accepted / legal review |

## Open Questions & Founder Decisions (bounded recommendations)

| OQ | Question | Recommendation (bounded) |
|----|----------|--------------------------|
| OQ-1 | Exact Guna Milan source | Adopt one named classical authority (recommend B. V. Raman tables) for `..._v1`; freeze after domain review. |
| OQ-2 | Retain bride/groom directionality | Yes, but store neutral roles mapped to classical ordering per rule pack. |
| OQ-3 | Married vs dating vs prospective | Launch for **committed/married + seriously dating** couples; single-user "preview" supports prospective matches without a shared workspace. |
| OQ-4 | Ascendant-based daily interpretation | **Post-MVP.** MVP uses natal-Moon house; ascendant optional field captured now, interpreted later. |
| OQ-5 | Tithi in MVP | **Post-MVP** for scoring; compute & store tithi/phase now (cheap), surface later. |
| OQ-6 | Retain exact location after natal calc | Retain coordinates only while needed; after natal derivation, keep **coarse** current location for daily presentation, encrypt exact birth coordinates and restrict access. |
| OQ-7 | Daily refresh at local midnight vs Moon transitions | **Local midnight** primary boundary + surface next rashi/nakshatra transition times within the day. |
| OQ-8 | Couple summaries one- or two-party approval | **Important agreements: two-party.** Neutral shared summaries: one-party author + partner visibility, no approval. |
| OQ-9 | Living Compatibility visibility | **Jointly-visible aggregate** only; each partner's private inputs/ratings stay private. |
| OQ-10 | Swiss Ephemeris licensing | Obtain Astrodienst professional license before launch; Moshier fallback interim. |
| OQ-11 | Geocoding provider vs self-hosted | Self-hosted GeoNames authoritative; optional online typeahead for UX only. |
| OQ-12 | AI provider & retention | Anthropic Claude with zero-retention/no-train terms; abstract behind port. |
| OQ-13 | India-only vs international | **India-first** launch (residency + market fit); design data model for later multi-region. |

---

# Reconsideration Audit (DEC-022 … DEC-028)

> Added by the independent pre-implementation verification audit (HEAD `9bedde0a`).
> These are **new** entries appended to preserve history — earlier decisions are not
> rewritten. Each load-bearing decision from §DEC-001–021 was re-examined against
> security, implementation effort, operational burden, and vendor dependency. Most were
> **Confirmed**; one (fallback policy) was **Corrected**; two new controls were added to
> close findings from the authorization/leakage audit.

## DEC-022 — Authentication: self-managed vs managed IdP (reconsidered)
**Status:** Accepted — **Confirms DEC-011 with an added guardrail** · **[Technical]**

| Dimension | Self-managed (DEC-011) | Managed IdP (Auth0/Cognito/Clerk/Firebase) |
|-----------|------------------------|---------------------------------------------|
| Security | Full control of session revocation & existence non-disclosure; but we own crypto-handling risk | Vendor-hardened auth; but coarse session control and data leaves our residency boundary |
| Effort | Higher (build refresh rotation, OIDC) | Lower initial |
| Ops burden | We run the auth store | Vendor runs it |
| Vendor dependency | None | High; migration is painful |
| Data residency (India, OQ-13) | In-house, clean | Region availability varies; DPDP exposure |

**Decision:** **Keep self-managed identity** (couples data + instant revocation + residency +
existence non-disclosure need fine control), **but** mandate **vetted libraries** — `argon2-cffi`
(Argon2id), `authlib` for OIDC, `PyJWT`/`python-jose` for ES256 — and **prohibit hand-rolled token
crypto**. A managed IdP remains a documented fallback if ops cost proves high.
**Migration path:** the `identity` module already sits behind a service interface; swapping to a
managed IdP later means reimplementing that interface, not touching callers.

## DEC-023 — Geocoding: self-hosted vs privacy-minimized external (reconsidered)
**Status:** Accepted — **Confirms DEC-017 with clarified privacy rule** · **[Technical]**

| Dimension | Self-hosted GeoNames (DEC-017) | Privacy-minimized external geocoder |
|-----------|-------------------------------|--------------------------------------|
| Security/Privacy | Birthplace PII never leaves infra | Even "minimized" queries send partial location to a third party |
| Effort | Dataset ingest + periodic refresh | Low |
| Ops burden | Maintain GeoNames snapshot (`geonames-2025-Q3`) | None |
| Vendor dependency | None | Per-call dependency + ToS/retention risk |

**Decision:** **Keep self-hosted GeoNames as the authoritative coordinate source.** An optional
online typeahead may power *search UX only* under a strict rule: **no birthplace string is sent to
an external provider once the user has begun entering true birth data unless they opt in; nothing is
stored provider-side; the authoritative lat/long always comes from the local dataset or explicit
user confirmation.** No correction to DEC-017; privacy rule made explicit.

## DEC-024 — Ephemeris fallback policy: per-artifact-class (CORRECTION to DEC-007)
**Status:** Accepted — **Corrects the blanket fallback in DEC-007** · **Requires domain/QA confirmation of epsilon** · **[Technical]**

DEC-007 specified a single Moshier fallback with a flat ×0.97 confidence for *all* outputs. The
astronomy reproducibility audit found this too coarse for the **binding, immutable classical Guna
Milan scorecard**, where a Moon sitting within a Moshier-error-width of a rashi/nakshatra/pada
boundary could land in the wrong bucket.

| Artifact class | Fallback policy (corrected) |
|----------------|------------------------------|
| Daily Moon climate (non-binding) | Moshier fallback **allowed** with visible provenance + lowered confidence (as before) |
| Classical Guna Milan binding scorecard | **Fail-closed to Swiss** when natal Moon is within a safety-epsilon (sized ≥ Moshier worst-case Moon error, confirmed empirically in golden tests) of ANY rashi/nakshatra/pada boundary; otherwise may compute under Moshier **but** the report is marked `provisional` with `recompute_pending_swiss=true` and is recomputed when Swiss is available |
| Any classical output | **Never** emit an unlabeled Moshier-based binding score |

**Decision:** adopt the per-artifact-class policy above. The astrology engine spec's flat-penalty
text is superseded for binding classical reports. Golden tests must measure Moshier's worst-case
Moon deviation to fix the safety-epsilon. (Swiss Ephemeris licensing remains a separate blocker,
DEC-007/OQ-10.)

## DEC-025 — Authorization: RLS + app-layer vs app-only (reconsidered)
**Status:** Accepted — **Confirms DEC-012** · **[Technical]**

| Dimension | App-layer only | App-layer + Postgres RLS (DEC-012) |
|-----------|----------------|-------------------------------------|
| Security | Single point of failure; one missed check = leak | Defense-in-depth; DB refuses even if app check is missed |
| Effort | Lower | RLS policy authoring + tests |
| Ops burden | Lower | Manage `SET app.user_id` per connection; pooling care |
| Vendor dependency | None | None (native Postgres) |

**Decision:** **Keep both.** Given existence non-disclosure and the couples-data blast radius, the
RLS backstop is justified. App-layer `ScopeContext` is the **primary** gate (owns the 404-vs-403
existence logic); RLS is the **defense-in-depth** net. RLS policies are a required test target
(authorization tests, `DILCHAT_TEST_AND_VALIDATION_PLAN.md`). Connection-pool `SET app.user_id`
correctness is a Phase-D checklist item.

## DEC-026 — Python 3.12 isolation in a 3.10+ monorepo (reconsidered)
**Status:** Accepted — **Confirms DEC-010/DEC-001** · **[Technical]**

| Option | Trade-off |
|--------|-----------|
| Isolate DilChat at 3.12 (chosen) | Matches `products/*` independence convention; own CI/venv; slight toolchain divergence |
| Align DilChat down to 3.10 | Loses `zoneinfo`/`tomllib` maturity relied on by the astrology tz layer |
| Bump whole monorepo to 3.12 | Cleanest long-term but out of scope for this product and risks unrelated packages |

**Decision:** **Keep the 3.12 product isolation.** DilChat is excluded from the root
`[tool.setuptools.packages.find]` and built/tested on its own 3.12 CI lane.
**Migration path:** if/when the monorepo baseline is raised to 3.12, the isolation collapses to a
no-op — no DilChat code change required.

## DEC-027 — Background jobs re-validate scope at write time (NEW — closes AUTHZ-1)
**Status:** Accepted · **[Technical/Security]**

The authorization/leakage audit found a gap: an in-flight `arq` job (daily-profile precompute, async
AI, export) that began before a couple unpairs could write shared/couple data after membership is
revoked. **Decision:** every background job carries its `ScopeContext` and **re-validates couple
membership and scope at the moment of write, inside the same transaction** (not only at enqueue). If
membership is `revoked`, the write is rejected and an `audit` event is emitted. Shared writes are
impossible post-unpair. This must be specified before Phase D/E implementation.

## DEC-028 — SharedArtifacts are immutable snapshots, not live private pointers (NEW — closes AUTHZ-2)
**Status:** Accepted · **[Technical/Security]**

The audit flagged under-specification of "shared agreement references deleted private source
content." **Decision:** a `SharedArtifact` (including agreement bodies and shared summaries) stores an
**immutable snapshot of the bounded, consented content at consent time**. It never holds a live
pointer into private-scope rows. Therefore deleting a private source **never** cascades to, breaks, or
re-exposes a shared artifact, and a shared artifact can never be used to reconstruct private content
beyond what was consented. Enforced by the consent-projection design (DEC-013) and a
no-foreign-key-from-shared-to-private rule in the data model.

## Reconsideration outcome summary

| ID | Subject | Outcome |
|----|---------|---------|
| DEC-022 | Auth model | Confirmed (guardrail added) |
| DEC-023 | Geocoding | Confirmed (privacy rule explicit) |
| DEC-024 | Ephemeris fallback | **Corrected** (per-artifact-class) |
| DEC-025 | RLS + app authz | Confirmed |
| DEC-026 | Python 3.12 isolation | Confirmed |
| DEC-027 | Job scope re-validation | **New control** (AUTHZ-1) |
| DEC-028 | Shared snapshots | **New control** (AUTHZ-2) |
