# DilChat Backend — System Architecture

**Product:** DilChat (consumer couples compatibility & communication) · **Company:** Ugence Labs · **Site:** dilchat.com
**Status:** Design phase. No production code has been written. This document is a **design specification**, not an implementation.
**Authority:** This document is subordinate to [`DILCHAT_DECISION_LOG.md`](./DILCHAT_DECISION_LOG.md). Where a name, version, boundary, or technology choice appears here, it restates a decision made there; it does not re-decide. Conflicts are resolved in favor of the decision log.

> **Scope of this document.** Container/component structure, module boundaries, source layout, data flows, trust boundaries, sync/async split, client interaction patterns, caching, background jobs, observability, deployment, and the future module-extraction path. Endpoint shapes live in [`DILCHAT_API_SPEC.md`](./DILCHAT_API_SPEC.md); the consent state machine lives in [`DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`](./DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md); the ephemeris math lives in [`DILCHAT_ASTROLOGY_ENGINE_SPEC.md`](./DILCHAT_ASTROLOGY_ENGINE_SPEC.md).

---

## 0. Architectural principles (recap of binding decisions)

These are not re-litigated here; they frame every diagram below.

| # | Principle | Source |
|---|-----------|--------|
| P1 | **One deployable** FastAPI app; modules are in-process, isolated, and talk only through published service ports. | DEC-002 |
| P2 | **Strict dependency order.** `audit ← identity ← users ← birth_profiles ← astrology ← {guna_milan, moon_transits} ← couples ← consent ← {private_chat, shared_chat, journeys, agreements} ← ai_guidance ← feedback`. Lower may not import higher. | DEC-002 |
| P3 | **Postgres is the only source of truth.** Redis is cache + broker, never authoritative. | DEC-004, DEC-005 |
| P4 | **Deterministic calculation and LLM inference are separated.** The LLM never computes astronomy, nakshatra, Koota, or transit scores; it receives governed structured inputs and returns schema-validated text. | DEC-014, DEC-019 |
| P5 | **Three scopes** `PRIVATE_A`, `PRIVATE_B`, `SHARED`, enforced by an app-layer `ScopeContext` guard **and** Postgres RLS. Default deny. | DEC-012 |
| P6 | **Private → shared only via a `ConsentEvent`** producing a bounded, immutable `SharedArtifact`. Never a raw row copy. The other partner is never told a private conversation exists. | DEC-013 |
| P7 | **Provenance on every derived artifact.** `ephemeris_version=swe-2.10.03`, `ayanamsa=lahiri`, `rule_pack_id=ashtakoota_lahiri_classical_v1`, `transit_model_version=dilchat_transit_v1`, `interest_model_version=dilchat_interest_v1`, `prompt_pack_version=dilchat_prompts_v1`. | DEC-000 canonical identifiers |
| P8 | **Swiss Ephemeris runs in an isolated single-threaded process pool** with a Moshier fallback that is always explicitly labeled. FastAPI handlers never call `swe.*` directly. | DEC-007 |

---

## 1. System context

DilChat's backend is a single boundary that mediates between mobile/web clients, self-hosted astronomy, and a small set of external providers. No third-party service is the source of truth for user data, astronomy, or scores.

### External actors

| Actor | Role | Direction | Notes |
|-------|------|-----------|-------|
| **DilChat Mobile (React Native, iOS + Android)** | Primary client. Natal capture, chat, journeys, daily profile, consent UX. | ⇄ HTTPS/JSON | Short-lived ES256 access JWT + rotating opaque refresh (DEC-011). Biometric unlock is client-side only. |
| **DilChat Web (Next.js)** | Marketing site + account / consent / export / delete portal. | ⇄ HTTPS/JSON | SSR for marketing; authenticated portal shares the same API. (DEC-016) |
| **OIDC providers** (Sign in with Apple, Google) | Federated login. | ← redirect / token exchange | Backend verifies ID tokens; never stores provider passwords. (DEC-011) |
| **SMS provider** | Phone OTP delivery. | → outbound | One-time codes only; no message content leaves the boundary. |
| **AI provider** (Anthropic Claude default, via `AIProvider` port) | Structured natural-language guidance. | → outbound, zero-retention terms | Receives **only** minimized, consent-authorized, deterministic inputs (P4, DEC-014). |
| **Push service** (APNs / FCM) | Delivery of notifications. | → outbound | Privacy-preserving payloads; previews hidden by default (§8). |
| **Object storage (S3-compatible, India region)** | Export bundles, deletion tombstone manifests, ephemeris file provenance. | ⇄ internal | Pre-signed, expiring URLs. Not user-browsable. |

### Context diagram

```mermaid
graph TD
    subgraph Clients
        MOB["DilChat Mobile<br/>React Native (iOS/Android)"]
        WEB["DilChat Web<br/>Next.js portal + marketing"]
    end

    subgraph External["External providers"]
        OIDC["OIDC IdPs<br/>Apple · Google"]
        SMS["SMS provider<br/>(OTP)"]
        AI["AI provider<br/>Anthropic Claude"]
        PUSH["Push service<br/>APNs / FCM"]
    end

    subgraph DilChat["DilChat Backend (modular monolith)"]
        API["FastAPI app<br/>15 in-process modules"]
        PG[("PostgreSQL 16<br/>source of truth + RLS")]
        RDS[("Redis 7<br/>cache · broker · idempotency")]
        CALC["Ephemeris process pool<br/>pyswisseph / Moshier"]
        ARQ["arq workers<br/>transit · recalc · export · delete · ai_async"]
        OBJ[("Object storage<br/>exports · manifests")]
    end

    MOB -- "HTTPS/JSON · ES256 JWT" --> API
    WEB -- "HTTPS/JSON · ES256 JWT" --> API
    API -- "verify ID token" --> OIDC
    API -- "send OTP" --> SMS
    API -- "structured, minimized prompt" --> AI
    API -- "silent/hidden-preview push" --> PUSH
    PUSH -. "device token registration" .-> MOB

    API <--> PG
    API <--> RDS
    API -- "submit calc job" --> CALC
    API -- "enqueue" --> ARQ
    ARQ <--> PG
    ARQ <--> RDS
    ARQ -- "run calc" --> CALC
    ARQ -- "write bundle" --> OBJ
    API -- "issue pre-signed URL" --> OBJ
```

---

## 2. Container & component architecture

One process image runs in two roles selected at startup: **web role** (Uvicorn/Gunicorn serving FastAPI) and **worker role** (arq worker consuming queues). Both roles import the same `dilchat` package, share the same module services, and both talk to the **same** ephemeris process pool abstraction — so business logic is written once and called from either role.

```mermaid
graph TD
    subgraph Edge
        LB["Load balancer / TLS<br/>(India region)"]
    end

    subgraph WebRole["Web role — Gunicorn + Uvicorn workers"]
        RT["API / Router layer<br/>FastAPI routers · auth middleware · ScopeContext resolver"]
        subgraph Modules["Module services (in-process ports)"]
            M_ID["identity"]
            M_US["users"]
            M_BP["birth_profiles"]
            M_AS["astrology"]
            M_GM["guna_milan"]
            M_MT["moon_transits"]
            M_CP["couples"]
            M_CN["consent"]
            M_PC["private_chat"]
            M_SC["shared_chat"]
            M_JN["journeys"]
            M_AG["agreements"]
            M_AI["ai_guidance"]
            M_FB["feedback"]
            M_AU["audit"]
        end
        POOL_C["Ephemeris pool client<br/>(submit-only handle)"]
    end

    subgraph WorkerRole["Worker role — arq"]
        Q_TP["queue: transit_precompute"]
        Q_RC["queue: recalc"]
        Q_EX["queue: export"]
        Q_DF["queue: delete_finalize"]
        Q_AI["queue: ai_async"]
    end

    subgraph CalcPool["Ephemeris process pool (single-threaded procs)"]
        P1["worker proc 1<br/>swe.set_ephe_path/set_sid_mode once"]
        P2["worker proc 2"]
        P3["worker proc N"]
    end

    subgraph Data
        PG[("PostgreSQL 16<br/>per-module tables · RLS")]
        RDS[("Redis 7<br/>cache · arq broker · idempotency · rate limit")]
        OBJ[("Object storage<br/>exports · manifests")]
        EPH[["Ephemeris .se1 files<br/>baked in image, checksum-pinned"]]
    end

    AIP["AIProvider port → Claude adapter"]

    LB --> RT
    RT --> Modules
    Modules --> POOL_C
    POOL_C --> CalcPool
    M_AI --> AIP
    Modules --> PG
    Modules --> RDS
    RT --> RDS

    WorkerRole --> Modules
    WorkerRole --> CalcPool
    Q_EX --> OBJ
    Q_DF --> OBJ
    Q_AI --> AIP

    CalcPool --> EPH
    RDS -. "job broker" .- WorkerRole
```

**Component notes**
- **API / Router layer** — thin. It authenticates, resolves a `ScopeContext`, applies rate limits + idempotency, then delegates to exactly one module service per request. No business logic lives in routers.
- **Module services** — the unit of isolation. Each exposes a Python port (a `Protocol`/ABC) other modules call; each owns its tables; none reaches into another's schema (P1/P2).
- **Ephemeris process pool** — a `ProcessPoolExecutor` of single-threaded workers, each initializing Swiss Ephemeris global state (`set_ephe_path`, `set_sid_mode(SE_SIDM_LAHIRI)`) exactly once (P8, DEC-007). Both web and worker roles submit to it; neither calls `swe.*` inline.
- **arq worker role** — five named queues (§9). Cron entries live here (nightly transit precompute).
- **Redis** — three logically separate concerns keyed by prefix: `cache:*`, `arq:*`, `idem:*`, `rl:*`, `sess:*`. Flushing cache never touches the broker.

---

## 3. Module responsibilities

All 15 modules, in dependency order (a module may depend only on modules **below** it, P2). Table prefix always equals the module name.

| Module | Owns (tables / domain) | Key operations (service port) | Depends on |
|--------|------------------------|-------------------------------|------------|
| **audit** | `audit_event` (append-only, hash-chained) | `emit(actor, action, scope, target, metadata)`; `verify_chain()` | — (leaf; imported by all) |
| **identity** | `identity_user_credential`, `identity_session`, `identity_oidc_link`, `identity_otp_challenge` | `register`, `authenticate`, `issue_access_jwt`, `rotate_refresh`, `revoke_session`, `verify_oidc`, `start_otp/verify_otp` | audit |
| **users** | `users_profile`, `users_preferences`, `users_device` (push tokens), `users_locale` | `get_profile`, `update_profile`, `register_device`, `set_notification_prefs` | identity, audit |
| **birth_profiles** | `birth_profiles_record` (encrypted birth coords/time), `birth_profiles_place_resolution` | `capture_birth_data`, `resolve_place` (GeoNames), `resolve_timezone` (zoneinfo/tzdata-2025b), `get_natal_inputs` | users, audit |
| **astrology** | `astrology_natal_chart`, `astrology_calc_trace` (jsonb) | `compute_natal(birth_inputs) -> chart` (Moon rashi/nakshatra/pada, ascendant context); wraps the ephemeris pool | birth_profiles, audit |
| **guna_milan** | `guna_milan_scorecard`, `guna_milan_koota_detail` | `compute_scorecard(chart_a, chart_b, role_map, rule_pack) -> 0..36 + 8 kootas` (immutable per version tuple, DEC-019) | astrology, audit |
| **moon_transits** | `moon_transits_global_daily` (per date+ephemeris), `moon_transits_user_daily_profile` | `precompute_global(date)`, `build_user_daily(user, date) -> emotional/interest climate` (`dilchat_transit_v1`, `dilchat_interest_v1`) | astrology, audit |
| **couples** | `couples_couple`, `couples_membership` (role, status active/revoked), `couples_pair_invite` | `create_invite`, `accept_invite`, `verify_membership(user, couple)`, `unpair` (flips to revoked → cascade revoke) | moon_transits, guna_milan, audit |
| **consent** | `consent_event`, `consent_shared_artifact` (immutable), `consent_revocation` | `request_share`, `grant`, `project(private_ref) -> shared_artifact`, `revoke` (per DEC-013 state machine) | couples, audit |
| **private_chat** | `private_chat_thread` (scope PRIVATE_A or PRIVATE_B), `private_chat_message`, `private_chat_context_snapshot` | `post_turn`, `list_thread`, `build_minimized_context` (for AI), `nominate_for_share` | consent, audit |
| **shared_chat** | `shared_chat_thread` (scope SHARED), `shared_chat_message` | `post_shared_message`, `list_shared`, `render_artifact_reference` | consent, audit |
| **journeys** | `journeys_template`, `journeys_instance`, `journeys_step_state` | `start_journey`, `advance_step`, `record_reflection` (private-scoped) | consent, audit |
| **agreements** | `agreements_agreement`, `agreements_party_signoff`, `agreements_version` | `draft`, `propose`, `sign` (two-party per OQ-8), `supersede` | consent, audit |
| **ai_guidance** | `ai_guidance_request`, `ai_guidance_output` (schema-validated), `ai_guidance_validation_failure` | `guide(task, minimized_input, schema) -> validated_output`; enforces disclaimers & DEC-021 guardrails | private_chat, shared_chat, journeys, agreements, audit |
| **feedback** | `feedback_rating`, `feedback_report`, `feedback_living_signal` (behavioral) | `rate_output`, `submit_living_signal` (`dilchat_living_v1`, jointly-visible aggregate only, OQ-9) | ai_guidance, audit |

**Cross-module rule of thumb:** if module X needs data from module Y, it calls `Y.service.<op>()`; it never issues SQL against a `Y_*` table. The `.importlinter` contract makes an illegal import a build failure (DEC-002).

---

## 4. Package / source layout

Under `products/dilchat/src/dilchat/`. Every module folder has the **same five-file shape** so the boundary is legible and mechanically checkable.

```text
products/dilchat/
├── pyproject.toml            # requires-python >=3.12 (DEC-010); dist name ugence-dilchat
├── README.md
├── alembic.ini
├── .importlinter             # dependency-order contract (DEC-002)
├── docs/                     # this file + peers
├── migrations/               # Alembic versions (one head; per-module table prefixes)
├── rules/
│   └── ashtakoota_lahiri_classical_v1/
│       ├── kootas/*.json     # 8 Koota tables
│       └── sources.json      # cited classical authority (DEC-009, frozen after review)
├── ephemeris/                # .se1 files provenance manifest (files baked into image)
├── tests/
└── src/dilchat/
    ├── __init__.py
    ├── app.py                # FastAPI factory; mounts routers; role selector (web|worker)
    ├── worker.py             # arq WorkerSettings; queues + cron
    ├── settings.py           # pydantic-settings; env config
    │
    ├── shared/               # cross-cutting, importable by all modules
    │   ├── scope.py          # ScopeContext dataclass + guard (PRIVATE_A/B/SHARED, P5)
    │   ├── provenance.py     # Provenance tuple builder/validator (P7)
    │   ├── db.py             # async engine, session, RLS session-var setter (SET app.user_id)
    │   ├── ports.py          # base Protocols / port registry
    │   ├── errors.py         # typed error hierarchy → HTTP mapping
    │   ├── idempotency.py    # Redis idempotency-key helper
    │   ├── ratelimit.py      # Redis token bucket
    │   ├── jobs.py           # enqueue(job_name, **kwargs) broker abstraction (DEC-006)
    │   ├── observability.py  # structured logging, metrics, trace context
    │   └── security/
    │       ├── jwt_es256.py  # access token mint/verify
    │       └── crypto.py     # Argon2id, field encryption for birth coords
    │
    ├── astrology/
    │   └── engine/
    │       ├── pool.py       # ProcessPoolExecutor of single-threaded swe procs (P8)
    │       ├── swe_worker.py # per-process init: set_ephe_path/set_sid_mode(LAHIRI)
    │       ├── moshier.py    # fallback path (FLG_MOSELPH); explicit labeling
    │       ├── nakshatra.py  # rashi/nakshatra/pada boundary logic
    │       └── timezone.py   # zoneinfo + timezonefinder resolution
    │
    └── modules/
        ├── audit/            { router, service, repository, models, schemas }.py
        ├── identity/         { router, service, repository, models, schemas }.py
        ├── users/            { router, service, repository, models, schemas }.py
        ├── birth_profiles/   { router, service, repository, models, schemas }.py
        ├── astrology/        { router, service, repository, models, schemas }.py
        ├── guna_milan/       { router, service, repository, models, schemas }.py
        ├── moon_transits/    { router, service, repository, models, schemas }.py
        ├── couples/          { router, service, repository, models, schemas }.py
        ├── consent/          { router, service, repository, models, schemas }.py
        ├── private_chat/     { router, service, repository, models, schemas }.py
        ├── shared_chat/      { router, service, repository, models, schemas }.py
        ├── journeys/         { router, service, repository, models, schemas }.py
        ├── agreements/       { router, service, repository, models, schemas }.py
        ├── ai_guidance/      { router, service, repository, models, schemas }.py
        │   └── providers/    # anthropic.py (default), openai.py (alt), base.py (port)
        └── feedback/         { router, service, repository, models, schemas }.py
```

**File contract per module**
- `router.py` — FastAPI `APIRouter`; DTO in/out; no business logic. Resolves `ScopeContext`, delegates to `service`.
- `service.py` — the **published port** + implementation. Transaction boundaries, invariants, provenance stamping, `audit.emit`.
- `repository.py` — the **only** place that issues SQL for this module's tables; every method requires a `ScopeContext`.
- `models.py` — SQLAlchemy 2 ORM (async) for this module's tables (`<module>_*`).
- `schemas.py` — Pydantic v2 request/response + internal DTOs.

---

## 5. Data flows

### 5a. Natal chart calculation (sync fast-path)

```mermaid
sequenceDiagram
    autonumber
    participant C as Mobile client
    participant R as astrology.router
    participant BP as birth_profiles.service
    participant AS as astrology.service
    participant POOL as Ephemeris pool
    participant PG as Postgres
    participant AU as audit

    C->>R: POST /natal (birth date/time/place) + Idempotency-Key
    R->>R: resolve ScopeContext (user_id, scope=PRIVATE_x)
    R->>BP: get_natal_inputs(user_id)
    BP->>PG: read encrypted birth record, resolve place+tz
    BP-->>AS: birth_inputs (UTC instant, lat, lon, tz confidence)
    AS->>POOL: submit compute_moon(instant, LAHIRI)
    alt .se1 files present
        POOL-->>AS: Moon long, nakshatra, pada (ephemeris_provider=swiss)
    else files missing / load error
        POOL-->>AS: Moshier result (ephemeris_provider=moshier, lower confidence)
        POOL-->>AU: emit ops alert (fallback engaged)
    end
    AS->>AS: stamp provenance (swe-2.10.03, lahiri, ...)
    AS->>PG: upsert astrology_natal_chart + calc_trace(jsonb)
    AS->>AU: emit(natal.computed, scope, provenance)
    AS-->>R: NatalChart
    R-->>C: 200 NatalChart (or replay via Idempotency-Key)
```

### 5b. Couple pairing + consent to pair

```mermaid
sequenceDiagram
    autonumber
    participant A as Partner A (mobile)
    participant B as Partner B (mobile)
    participant CP as couples.service
    participant CN as consent.service
    participant PG as Postgres
    participant AU as audit
    participant PUSH as Push service

    A->>CP: create_invite() 
    CP->>PG: insert couples_pair_invite (code, expiry)
    CP->>AU: emit(couple.invite_created)
    CP-->>A: invite code / deep link
    A-->>B: shares code out-of-band
    B->>CP: accept_invite(code)
    CP->>PG: insert couples_couple + 2x couples_membership(active, roles)
    CP->>CN: open baseline SHARED scope for couple_id
    CP->>AU: emit(couple.paired)
    CP->>PUSH: notify A "You are now paired" (no content preview)
    CP-->>B: Couple{couple_id, members, roles}
    Note over CP,CN: verify_membership(user, couple) now returns active —<br/>SHARED scope becomes reachable for both
```

### 5c. Shared Guna Milan scorecard generation

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (either partner)
    participant R as guna_milan.router
    participant CP as couples.service
    participant AS as astrology.service
    participant GM as guna_milan.service
    participant PG as Postgres
    participant AU as audit

    C->>R: GET /couple/{id}/guna-milan
    R->>CP: verify_membership(user, couple) [SHARED gate]
    CP-->>R: active
    R->>GM: get_or_compute_scorecard(couple_id)
    GM->>PG: lookup existing scorecard for version tuple
    alt cached & version tuple matches
        GM-->>R: existing scorecard (immutable, DEC-019)
    else missing / rule_pack changed
        GM->>AS: get natal chart A, natal chart B
        AS-->>GM: chart_a, chart_b (Moon rashi/nakshatra + provenance)
        GM->>GM: apply rule_pack ashtakoota_lahiri_classical_v1<br/>(role_map: seeker/partner → bride/groom, DEC-009a)
        GM->>PG: insert guna_milan_scorecard(0..36) + 8 koota_detail rows
        GM->>AU: emit(guna_milan.computed, rule_pack_id)
        GM-->>R: scorecard
    end
    R-->>C: 200 Scorecard (classical score family only — AI may later explain)
```

### 5d. Nightly global transit precompute + per-user daily profile

```mermaid
sequenceDiagram
    autonumber
    participant CRON as arq cron (00:10 IST)
    participant TP as transit_precompute worker
    participant POOL as Ephemeris pool
    participant RDS as Redis cache
    participant PG as Postgres
    participant RC as build_user_daily (on-demand or fanned)
    participant U as User (first request of day)

    CRON->>TP: precompute_global(date=D)
    TP->>POOL: Moon ephemeris samples across day D
    POOL-->>TP: Moon longitude series, rashi/nakshatra transition times
    TP->>TP: stamp transit_model_version=dilchat_transit_v1
    TP->>PG: upsert moon_transits_global_daily(D, ephemeris_version)
    TP->>RDS: SET cache:transit:{D}:{ephemeris_version} (TTL ~48h)
    Note over TP,RDS: Global layer is user-independent → computed once per date

    U->>RC: GET /me/daily (date D)
    RC->>RDS: GET cache:daily:{user}:{D}
    alt per-user profile cached
        RDS-->>RC: user daily profile
    else miss
        RC->>RDS: GET cache:transit:{D}:{ephemeris_version} (global layer)
        RC->>PG: read user natal Moon (astrology)
        RC->>RC: derive emotional/interest climate (dilchat_interest_v1), clamp bounds (DEC-019)
        RC->>RDS: SET cache:daily:{user}:{D} (TTL to local midnight)
        RC->>PG: persist moon_transits_user_daily_profile
    end
    RC-->>U: DailyProfile (labeled DilChat model, not classical prediction)
```

### 5e. Private AI chat turn with context minimization (sync + timeout fallback)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (Partner A)
    participant R as private_chat.router
    participant PC as private_chat.service
    participant AS as astrology.service
    participant MT as moon_transits.service
    participant AI as ai_guidance.service
    participant PROV as AIProvider (Claude)
    participant PG as Postgres
    participant AU as audit

    C->>R: POST /private/threads/{id}/turn (message) [scope=PRIVATE_A]
    R->>PC: post_turn(scope_ctx, message)
    PC->>PG: append private_chat_message (PRIVATE_A only)
    PC->>PC: build_minimized_context()
    Note over PC: include ONLY: natal summary tokens, today's climate label,<br/>last N turns of THIS private thread. Exclude partner's private data,<br/>raw birth coords, cross-scope content (P4/P6).
    PC->>AS: natal summary (bounded)
    PC->>MT: today's climate label (bounded)
    PC->>AI: guide(task=private_reflection, minimized_input, output_schema)
    AI->>AI: attach disclaimers + DEC-021 guardrails to system prompt
    AI->>PROV: complete_structured(prompt_pack=dilchat_prompts_v1)  [timeout ~8s]
    alt provider returns within timeout & schema-valid
        PROV-->>AI: candidate output
        AI->>AI: validate against schema + safety filters
        AI->>PG: persist ai_guidance_output (+ prompt_pack_version)
        AI-->>PC: validated guidance
    else timeout / provider outage / schema-invalid
        AI->>PG: record ai_guidance_validation_failure or outage
        AI->>AU: emit(ai.degraded)
        AI-->>PC: deterministic-only fallback (climate + facts, no generative text)
    end
    PC->>AU: emit(private_chat.turn, scope=PRIVATE_A)
    PC-->>R: turn result
    R-->>C: 200 (AI text or graceful deterministic fallback)
```

### 5f. Private → shared consent projection

```mermaid
sequenceDiagram
    autonumber
    participant A as Partner A (mobile)
    participant PC as private_chat.service
    participant CN as consent.service
    participant SC as shared_chat.service
    participant PG as Postgres
    participant AU as audit
    participant PUSH as Push
    participant B as Partner B

    A->>PC: nominate_for_share(private_ref, projection_spec)
    Note over PC: projection_spec enumerates EXACTLY what leaves PRIVATE_A<br/>(e.g. a one-line agreed statement / summary) — never the raw thread
    PC->>CN: request_share(private_ref, projection_spec, scope PRIVATE_A→SHARED)
    CN->>PG: insert consent_event(status=pending, what/who/when/revocation)
    CN->>AU: emit(consent.requested)
    A->>CN: grant(consent_event_id)
    CN->>CN: project(private_ref, spec) → bounded SharedArtifact (immutable)
    CN->>PG: insert consent_shared_artifact (SHARED), link consent_event(granted)
    CN->>SC: publish artifact reference into shared thread
    SC->>PG: insert shared_chat_message referencing artifact
    CN->>AU: emit(consent.granted + artifact_id)
    CN->>PUSH: notify B "New shared note" (preview hidden)
    Note over B,CN: B sees ONLY the SharedArtifact.<br/>B is never told a private conversation exists (DEC-013).
    B-->>SC: reads SharedArtifact in SHARED scope
```

---

## 6. Trust boundaries

Boundaries are enforced, not assumed. Crossing any boundary requires an explicit, audited check.

```mermaid
flowchart TB
    subgraph B0["Untrusted zone"]
        CLIENT["Mobile / Web clients<br/>(user-controlled, biometrics stay here)"]
    end

    subgraph B1["Backend trust boundary"]
        direction TB
        EDGE["AuthN edge: verify ES256 JWT,<br/>resolve ScopeContext, rate-limit, idempotency"]

        subgraph SCOPES["Scope isolation (P5, DEC-012)"]
            PA["PRIVATE_A"]
            PB["PRIVATE_B"]
            SH["SHARED"]
        end

        subgraph DETERMINISTIC["Deterministic zone (authoritative math)"]
            ENGINE["astrology / guna_milan / moon_transits<br/>+ ephemeris process pool"]
        end

        GATE{{"Consent gate<br/>ConsentEvent → SharedArtifact (P6)"}}
    end

    subgraph B2["LLM boundary (untrusted output)"]
        LLM["AIProvider (Claude)<br/>governed input · schema-validated output"]
    end

    subgraph B3["Data-at-rest boundary"]
        PG[("Postgres + RLS<br/>SET app.user_id backstop")]
        OBJ[("Object storage<br/>pre-signed, expiring")]
    end

    CLIENT -->|"HTTPS only"| EDGE
    EDGE --> SCOPES
    PA -. "no direct read" .-> PB
    PA -->|"via GATE only"| SH
    PB -->|"via GATE only"| SH
    GATE --> SH
    SCOPES --> DETERMINISTIC
    DETERMINISTIC -->|"minimized, bounded facts"| LLM
    LLM -->|"validated text, never math"| SCOPES
    SCOPES --> PG
    ENGINE --> PG
    PG --> OBJ
```

**Boundary prose**

1. **Client ↔ backend.** Everything client-side is untrusted, including biometric unlock (never leaves the device; the backend only ever sees a rotating opaque refresh token, DEC-011). The edge verifies the ES256 access JWT, then constructs a `ScopeContext` server-side; a client can never assert its own scope.
2. **Per-module boundaries.** A module is a trust boundary against its siblings: illegal cross-module imports fail the `.importlinter` build, and repositories refuse cross-prefix SQL (P1/P2). This limits blast radius — a bug in `journeys` cannot silently read `identity_session`.
3. **PRIVATE_A / PRIVATE_B / SHARED isolation.** The two private scopes never read each other, full stop. The **only** path from a private scope to `SHARED` is the consent gate (P6). Postgres RLS is the backstop: even if the app guard were bypassed, `SET app.user_id` + row policies deny cross-scope rows (DEC-012).
4. **Deterministic-calc vs LLM.** The heavy line in the diagram. Everything left of the LLM boundary is authoritative and reproducible from the provenance tuple. The LLM receives only minimized, consent-authorized, deterministic facts and returns text that is **schema-validated and never fed back as truth** into scores (P4, DEC-014, DEC-019). An LLM outage degrades to deterministic-only responses, never to guessed astronomy.
5. **Data-at-rest.** Birth coordinates are field-encrypted (OQ-6); exports/manifests live in object storage reachable only via short-lived pre-signed URLs.

---

## 7. Synchronous vs. asynchronous operations

The rule: **user-blocking, fast, and bounded → sync**; **fan-out, slow, retriable, or scheduled → async**.

| Operation | Mode | Why |
|-----------|------|-----|
| Natal chart calculation | **Sync** (submit to pool, await, ~tens of ms) | One Moon position; user is waiting on capture; deterministic and cheap. |
| Guna Milan scorecard (first compute) | **Sync**, then cached immutable | Two charts + table lookups; fast; immutable per version tuple so it is computed once. |
| Per-user daily profile (cache miss) | **Sync** off the precomputed global layer | Global transit already async-precomputed; per-user derivation is a cheap join. |
| Nightly **global** transit precompute | **Async** (arq cron) | User-independent, heavy across the day's samples; amortized once per `date+ephemeris_version`. |
| Versioned recalculation sweep (new rule_pack / model) | **Async** (`recalc` queue) | Potentially every user; must be chunked, throttled, retriable; never blocks a request. |
| Private AI chat turn | **Sync with timeout (~8s) + deterministic fallback** | Conversational latency matters; but bounded so a slow provider degrades gracefully (§5e). |
| Long/streamed AI generation (e.g. journey synthesis) | **Async** (`ai_async` queue) → push/poll | Exceeds interactive budget; result delivered later. |
| Data export bundle | **Async** (`export` queue) → pre-signed URL | Cross-module gather + serialization; slow; user notified on completion. |
| Account/couple deletion finalize | **Async** (`delete_finalize` queue) | Multi-module cascade + tombstoning; must be transactional-safe and auditable. |
| Consent grant / projection | **Sync** | Small, transactional, must be immediately consistent (SHARED becomes visible at once). |
| Unpair / session revoke | **Sync** | Security-critical; must take effect immediately (DEC-012). |

---

## 8. Client ↔ backend interaction patterns

### Authentication & session (DEC-011)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant ID as identity.service
    participant PG as Postgres

    C->>ID: login (password / OIDC / OTP)
    ID->>ID: Argon2id verify OR verify OIDC ID token OR verify OTP
    ID->>PG: insert identity_session (hashed refresh, device, expiry)
    ID-->>C: access JWT (ES256, ~10 min) + opaque refresh
    Note over C: refresh stored behind biometric gate on-device
    loop every ~10 min or on 401
        C->>ID: POST /auth/refresh (opaque refresh)
        ID->>PG: look up + ROTATE session (old hash invalidated)
        ID-->>C: new access JWT + new refresh (rotation)
    end
    C->>ID: logout / unpair
    ID->>PG: mark session revoked (immediate)
```

- **Access token:** stateless ES256 JWT, ~10 min TTL, carries `user_id` + minimal claims. Public key served for verification; private key in KMS.
- **Refresh token:** opaque, rotating, stored **hashed** server-side as `identity_session` rows so any session revokes instantly (unpair/logout invariant, DEC-011/DEC-012).
- **Biometric unlock** gates the on-device refresh token only; the backend never sees biometrics.

### Offline caching (client responsibility, backend-supported)
- Immutable, provenance-stamped artifacts (natal chart, Guna Milan scorecard) are safely cacheable on-device **keyed by provenance tuple**; a version change invalidates them.
- The daily profile carries a `valid_until` (local midnight, OQ-7) so clients know when to refetch.
- All list endpoints support `ETag` / `If-None-Match` and cursor pagination so an offline client reconciles cheaply on reconnect.

### Push notification privacy (§ meets DEC-013)
- **Previews hidden by default.** Push payloads carry a **category + opaque reference**, never message text, partner identity, or artifact content. The client fetches details over the authenticated API after unlock.
- A "new shared note" push must **never** reveal that a private conversation exists (P6).
- Notification content preferences live in `users_preferences`; the user may opt into richer previews explicitly.

### Web ↔ backend (Next.js, DEC-016)
- Marketing pages are SSR/static and hit no authenticated API.
- The account/consent/export/delete portal uses the **same** API and the same ES256/refresh model, with tokens in httpOnly, `SameSite=Strict` cookies for the portal origin.

---

## 9. Caching, background jobs, resilience

### Caching strategy (Redis, P3 — never source of truth)

| Cache key | Contents | TTL / invalidation |
|-----------|----------|--------------------|
| `cache:transit:{date}:{ephemeris_version}` | Global daily Moon transit layer | ~48h; keyed by ephemeris_version so a bump auto-separates |
| `cache:daily:{user_id}:{date}` | Per-user daily profile | Until local midnight (OQ-7); or model-version bump |
| `cache:natal:{user_id}:{provenance_hash}` | Natal chart summary tokens | Invalidated only by provenance change |
| `idem:{route}:{idempotency_key}` | Stored response for replay | ~24h; enforces at-most-once for mutating POSTs |
| `rl:{principal}:{window}` | Rate-limit token bucket | Sliding window |
| `sess:{jti_or_hash}` | Hot session lookup (backed by Postgres) | Short; Postgres authoritative |

### Background-job strategy (arq, DEC-006)

Five named queues; the broker is abstracted behind `shared/jobs.py::enqueue(job_name, **kwargs)` so arq→Celery is a swap, not a rewrite.

```mermaid
graph LR
    subgraph Producers
        API["API layer"]
        CRON["arq cron"]
    end
    subgraph Queues["Redis-backed arq queues"]
        TP["transit_precompute"]
        RC["recalc"]
        EX["export"]
        DF["delete_finalize"]
        AI["ai_async"]
    end
    subgraph Consumers["Worker role"]
        W["arq workers"]
    end
    CRON --> TP
    API --> RC
    API --> EX
    API --> DF
    API --> AI
    TP --> W
    RC --> W
    EX --> W
    DF --> W
    AI --> W
```

| Queue | Trigger | Idempotency key | Retry / backoff |
|-------|---------|-----------------|-----------------|
| `transit_precompute` | Cron 00:10 IST + on-demand backfill | `(date, ephemeris_version)` upsert | 3 tries, exp backoff; on persistent fail → ops alert, per-user path can compute on demand |
| `recalc` | New `rule_pack_id` / model version | `(entity_id, target_version)` | Chunked, throttled; each chunk retriable; resumable cursor |
| `export` | User export request | `(request_id)` | 3 tries; partial artifacts discarded on failure, re-gathered |
| `delete_finalize` | Account/couple deletion | `(deletion_id)` | Must reach terminal state; retries until tombstoned; audited each step |
| `ai_async` | Long AI generation | `(request_id)` | Timeout + fallback like §5e; failure → deterministic result recorded |

**Idempotency.** Every mutating POST accepts an `Idempotency-Key`; the edge stores the response under `idem:*` and replays it on duplicate delivery — covering mobile retries over flaky networks.

### Failure modes & degradation

| Failure | Detection | Degradation |
|---------|-----------|-------------|
| `.se1` ephemeris files missing/corrupt | Pool worker init check + checksum | Fall back to **Moshier**, stamp `ephemeris_provider="moshier"`, lower confidence, ops alert — never an unlabeled result (DEC-007) |
| Ephemeris pool saturated | Submit queue depth / latency | Backpressure sync callers with 503 + Retry-After; shed to async where allowed |
| AI provider outage / timeout / schema-invalid | Per-call timeout + schema validation | **Deterministic-only response** (facts + climate, no generative text); record `ai_guidance_validation_failure`; emit `ai.degraded` (P4) |
| Redis unavailable | Health probe | Serve from Postgres (slower); disable idempotency-required mutations if the store is down (fail safe, not silent double-write) |
| Postgres primary failover | Replica lag / connection loss | Read-only degraded mode for cached artifacts; block mutations until primary restored (Postgres is the only truth, P3) |

---

## 10. Observability

- **Structured logs** — JSON, one event per request/job. Standard fields: `request_id`, `user_id` (never PII beyond id), `module`, `scope`, `provenance_hash`, `latency_ms`, `outcome`. Birth coordinates and message content are **never** logged.
- **Metrics** (Prometheus-style):
  - `calc_latency_ms` (histogram, labeled `engine=swiss|moshier`)
  - `ephemeris_fallback_total` (counter — alerts if > 0 sustained)
  - `cache_hit_ratio` per cache family (`transit`, `daily`, `natal`, `idem`)
  - `ai_validation_failure_rate`, `ai_timeout_total`, `ai_degraded_total`
  - `queue_depth` / `job_retry_total` per arq queue
  - `consent_projection_total`, `scope_denied_total` (RLS/guard denials — a spike is a red flag)
- **Audit event emission** — the `audit` module records a hash-chained, append-only `audit_event` for every security- or consent-relevant action (`natal.computed`, `couple.paired`, `consent.granted`, `ai.degraded`, `session.revoked`). `verify_chain()` detects tampering; auditability is a first-class product requirement, not a log.
- **Tracing** — W3C `traceparent` propagated from the edge through module services into the ephemeris pool submission and the AI call, so a single chat turn's fan-out (private_chat → astrology → moon_transits → ai_guidance → provider) is one trace.

---

## 11. Deployment topology & module extraction path

### Deployment (DEC-018, India-first per OQ-13)

```mermaid
graph TD
    subgraph Region["Cloud region: ap-south-1 / asia-south1 (India)"]
        LB["Load balancer + TLS"]
        subgraph BG["Blue/Green"]
            subgraph Blue["Blue (active)"]
                WB["Web role<br/>Gunicorn+Uvicorn (N replicas)"]
                KB["Worker role<br/>arq (M replicas)"]
            end
            subgraph Green["Green (standby → promoted)"]
                WG["Web role"]
                KG["Worker role"]
            end
        end
        PGm[("Postgres 16 primary<br/>+ PITR")]
        PGr[("Read replica")]
        RDS[("Redis 7<br/>cache + broker")]
        OBJ[("Object storage")]
        KMS["KMS<br/>ES256 signing key · field-encryption key"]
    end

    LB --> Blue
    LB -. "cutover" .-> Green
    Blue --> PGm
    Blue --> RDS
    KB --> PGm
    KB --> OBJ
    PGm --> PGr
    Blue --> KMS
```

- **Containerized (Docker).** One image, role selected by entrypoint (`web` vs `worker`). Ephemeris `.se1` files baked in at a pinned checksum (DEC-007).
- **Blue/green.** New version deployed to green, health-checked (including an ephemeris self-test and a golden-chart assertion), then load balancer cutover; old color kept warm for fast rollback. **Alembic migrations are expand/contract** so blue and green tolerate one schema step between them.
- **Single region for MVP**; data-model carries `couple_id`/`user_id` residency keys so later multi-region partitioning (GDPR/CCPA) is additive, not a rewrite (DEC-018).

### Module extraction path (how a module becomes a service later)

The modular monolith is deliberately shaped so extraction is mechanical, not archaeological. For any candidate module:

1. **The published interface already exists.** Callers use `Module.service` ports (Python `Protocol`s), never its tables (P1). Extraction replaces the in-process port implementation with a network client behind the *same* interface — callers do not change.
2. **Extract table ownership cleanly.** Because every table is prefixed with its module name and no other module issues SQL against it, the module's tables move to (or stay logically owned by) the new service without untangling shared schema.
3. **Introduce network transport.** Swap the in-process call for gRPC/HTTP behind the port. `shared/jobs.py` and `shared/ports.py` localize where transport is chosen, so the change is confined.
4. **Re-establish observability & auth across the wire.** Propagate `traceparent`, re-verify `ScopeContext` at the new service edge (it must not trust an upstream assertion), keep audit emission.

**Easy to extract (leaf-ward, few invariants):**
- `astrology` + the ephemeris pool — pure, deterministic, provenance-stamped; a natural first "calculation service." Its process-pool isolation is already a de-facto service boundary (P8).
- `moon_transits` — mostly reads astrology + a heavy async precompute; extracting it isolates the nightly compute cost.
- `ai_guidance` — already behind the `AIProvider` port and consumes only minimized inputs; extracting it hardens the LLM boundary (P4).

**Hard to extract (the couple-scope invariants, DEC-002/012/013):**
- `couples` + `consent` + the three scopes are the reason MVP is a monolith. Pairing, membership revocation, and the private→shared projection are **transactional invariants** that today hold inside one Postgres transaction. Splitting them across services turns "grant consent and publish exactly one bounded SharedArtifact, atomically, while the other partner is never told a private thread exists" into a distributed saga with compensation logic. That is a deliberate *do-not-extract-first* zone: `private_chat`/`shared_chat` may leave, but `couples`+`consent` stay co-located until there is a hard operational reason and a proven saga design.

Extraction order recommendation: `astrology` → `moon_transits` → `ai_guidance` first; keep `identity`/`couples`/`consent` as the transactional core last.

---

## 12. Cross-references

| Document | What it authoritatively defines |
|----------|--------------------------------|
| [`DILCHAT_DECISION_LOG.md`](./DILCHAT_DECISION_LOG.md) | **Canonical.** All decisions (DEC-001…DEC-021), canonical identifiers/provenance tuple, open questions. This architecture restates, never overrides. |
| [`DILCHAT_API_SPEC.md`](./DILCHAT_API_SPEC.md) / [`openapi/dilchat.openapi.yaml`](./openapi/dilchat.openapi.yaml) | Endpoint shapes, DTOs, error codes, idempotency headers referenced in §5 and §8. |
| [`DILCHAT_ASTROLOGY_ENGINE_SPEC.md`](./DILCHAT_ASTROLOGY_ENGINE_SPEC.md) | Ephemeris math, ayanamsa handling, nakshatra/pada boundaries, ambiguous-time handling behind §5a and the `astrology/engine`. |
| [`DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`](./DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md) | Full `ConsentEvent → SharedArtifact` state machine, scope guard details, retention/encryption behind §5f and §6. |
| [`DILCHAT_TEST_AND_VALIDATION_PLAN.md`](./DILCHAT_TEST_AND_VALIDATION_PLAN.md) | Golden-chart oracle validation (DEC-020) referenced by the blue/green health check in §11. |

---

*End of `DILCHAT_BACKEND_ARCHITECTURE.md`. Subordinate to the decision log; update in lockstep when a DEC changes.*
