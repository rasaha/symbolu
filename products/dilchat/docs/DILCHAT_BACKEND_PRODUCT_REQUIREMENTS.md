# DilChat — Backend Product Requirements Document (PRD)

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Document type:** Product Requirements (design phase — DESIGN ONLY, no production code)
**Status:** Draft for review · **Owner:** Principal Technical PM
**Canonical reference:** [`DILCHAT_DECISION_LOG.md`](./DILCHAT_DECISION_LOG.md) — all names, versions, module boundaries, and technology choices are fixed there; this PRD cites the log and never re-decides.

> **Claim labels used throughout this document**
> Every substantive claim is tagged with exactly one of:
> - **[Traditional Vedic rule]** — an established classical Jyotish rule DilChat encodes faithfully.
> - **[DilChat proprietary interpretation]** — a DilChat-authored model or presentation, explicitly *not* classical prediction.
> - **[Technical assumption]** — an engineering assumption to be validated in build.
> - **[Product decision requiring founder approval]** — a strategy call reserved for the founder.

---

## 0. The three concepts that must never be merged (invariant)

DilChat keeps **three separate compatibility concepts** distinct in data, versioning, storage, presentation, and AI handling. This is the product's defining invariant (see DEC-019). Merging any two is a release-blocking defect.

| # | Concept | Source of truth | Version tuple field | Mutability | AI role |
|---|---------|-----------------|---------------------|------------|---------|
| 1 | **Classical Compatibility** — Ashtakoota Guna Milan | 8 Kootas, max score 36, computed from fixed natal data + rule pack | `rule_pack_id = ashtakoota_lahiri_classical_v1` | **Immutable** for a given natal-data + version tuple | AI may *explain*, **never alter** — **[Traditional Vedic rule]** |
| 2 | **Daily Emotional & Interest Climate** | Sidereal Moon transit vs natal Moon, per user, per day | `transit_model_version = dilchat_transit_v1`, `interest_model_version = dilchat_interest_v1` | Recomputed daily; personalization clamps presentation only | AI may *interpret within bounds* — **[DilChat proprietary interpretation]** |
| 3 | **Living Compatibility** | Actual couple behavior, agreements, feedback | `living_compat_model_version = dilchat_living_v1` | Evolves from consented behavioral data; **never feeds back into (1)** | AI may *summarize consented aggregate* — **[DilChat proprietary interpretation]** |

**Language rule (enforced in copy + AI guardrails):** Concept (2) is *interpretation*, never *classical prediction*. Concept (3) is *behavioral*, never *astrological*. Concept (1) is *classical*, never *personalized*.

---

## 1. Product goals & core thesis

### 1.1 Core thesis

> **Other astrology apps tell couples whether they match. DilChat helps couples understand their differences and build compatibility together.**

DilChat treats a Guna Milan score as a **starting conversation**, not a verdict. The product's center of gravity is the *communication and agreement* layer (private reflection → shared understanding → dual-approved agreements → measurable Living Compatibility), with classical astrology as a respected, faithfully-computed anchor rather than a gate on the relationship.

### 1.2 Strategic goals

| Goal ID | Goal | Why it matters |
|---------|------|----------------|
| G-1 | Deliver a **reproducible, provenance-stamped** classical Guna Milan scorecard | Trust: the same natal data + version tuple must always yield the same 36-point result — **[Traditional Vedic rule]** faithfully encoded |
| G-2 | Reframe compatibility from *verdict* to *shared growth* | Product differentiation and the core thesis |
| G-3 | Enforce **hard privacy boundaries** between `PRIVATE_A`, `PRIVATE_B`, `SHARED` | Safety for at-risk users; consent-gated projection (DEC-013) |
| G-4 | Keep classical / daily-climate / living compatibility **strictly separated** | DEC-019 invariant; integrity of the classical tradition |
| G-5 | Ship an **India-first** experience (English MVP, Hindi-ready) | Market fit + DPDP posture (OQ-13, DEC-018) |
| G-6 | Provide **AI guidance that never oversteps** safety constraints | DEC-021; brand and legal survival |

### 1.3 Measurable objectives (MVP target window: first 90 days post-launch)

| Obj ID | Objective | Metric | Target |
|--------|-----------|--------|--------|
| OBJ-1 | Reproducibility of classical scores | % of recomputations bit-identical for same natal+version tuple | **100%** |
| OBJ-2 | Pairing activation | % of initiators whose invited partner completes pairing | ≥ **55%** — **[Product decision requiring founder approval]** (target) |
| OBJ-3 | Scorecard delivery | % of paired couples who view the shared scorecard within 24h of pairing | ≥ **80%** |
| OBJ-4 | Daily engagement | % of paired users who open a daily Moon-interest profile ≥ 3×/week | ≥ **35%** |
| OBJ-5 | Guidance helpfulness | Mean thumbs-up rate on AI guidance turns | ≥ **70%** |
| OBJ-6 | Agreement completion | % of started guided journeys reaching a dual-approved agreement | ≥ **25%** |
| OBJ-7 | Privacy incidents | Confirmed cross-scope data leaks | **0** (release-blocking) |
| OBJ-8 | Natal calc latency | p95 natal chart computation | ≤ **1.5 s** — **[Technical assumption]** |

---

## 2. User personas

### 2.1 Persona A — The Initiator ("Ananya")

| Attribute | Detail |
|-----------|--------|
| Who | 24–34, urban India, in a committed or seriously-dating relationship; comfortable with astrology as culturally meaningful, not dogma |
| **Goals** | Understand her relationship beyond a "match/no-match" number; get her partner to engage; work on friction points constructively |
| **Pains** | Existing apps feel like fortune-telling or feel judgmental; hard to get a partner to install anything; fears her private notes being exposed |
| **Key journeys** | Registration → birth profile → invite partner → view shared scorecard → start a guided journey → propose an agreement |
| Success signal | Partner pairs; couple reaches at least one dual-approved agreement |

### 2.2 Persona B — The Invited Partner ("Rohan")

| Attribute | Detail |
|-----------|--------|
| Who | 26–36; installs *because invited*, lower baseline interest, skeptical of astrology apps |
| **Goals** | Low-friction join; understand what he's agreeing to share; not feel surveilled or graded |
| **Pains** | Doesn't want to hand over birth data to a black box; worried the app "reports" on him to his partner |
| **Key journeys** | Accept invite → register → birth profile → consent review → view shared scorecard → respond in shared chat |
| Success signal | Completes birth profile *and* explicitly reviews consent scopes before any sharing |

### 2.3 Persona C — The Prospective / Dating User ("Meera") — private preview

| Attribute | Detail |
|-----------|--------|
| Who | Single or early-dating; wants a **private preview** of compatibility with a prospective match *without* creating a shared workspace or contacting anyone |
| **Goals** | Explore a hypothetical pairing privately; learn what the Kootas mean; decide whether to pursue |
| **Pains** | Doesn't want the other person notified; doesn't want to be pushed into a "match marketplace" |
| **Key journeys** | Registration → own birth profile → **private preview** using entered prospective birth data → read explanations → optionally, later, invite the real person |
| Constraint | Preview is **single-user, private-only**; it never contacts, notifies, or reveals anything to the prospective person (DEC-013; OQ-3) — **[Product decision requiring founder approval]** (scope confirmed OQ-3) |
| Success signal | Understands Koota meanings; no unwanted outbound contact ever occurs |

### 2.4 Persona D — The Privacy-Sensitive / At-Risk User ("Sara")

| Attribute | Detail |
|-----------|--------|
| Who | In a relationship where privacy and physical safety matter; may fear coercion or monitoring |
| **Goals** | A truly private space to reflect; certainty that a partner cannot see her private notes or even know they exist; fast, clean exit |
| **Pains** | Fear that "couple app" means "shared everything"; fear that leaving leaves a trace; fear of an abuser reading AI chats |
| **Key journeys** | Registration → biometric lock → private chat/journaling → (optional) selective consented sharing → rapid unpair + revoke + export/delete |
| Hard requirements | Partner is **never** told a private conversation exists (DEC-013); unpairing revokes shared access **immediately** (DEC-012); AI must never pressure her to stay (DEC-021) |
| Success signal | Can use private space with zero leakage and exit without residue |

---

## 3. Core user journeys

Each journey is a numbered step list. Steps map to modules (in `code font`). All shared steps assume an active, non-revoked couple membership (DEC-012).

### 3.1 Flagship milestone journey (verbatim)

> **"Two users independently create birth profiles, securely pair, and receive a reproducible shared Guna Milan scorecard plus individual daily Moon-interest profiles, with private and shared authorization boundaries enforced."**

This is the MVP's defining success milestone; Journeys J-1 → J-5 below realize it end to end.

### 3.2 J-1 — Registration & account creation

1. User opens app, chooses email+password / Google / Apple / phone-OTP (`identity`, DEC-011).
2. Password hashed with Argon2id; or OIDC/OTP verified (`identity`).
3. Access token (10-min ES256 JWT) + rotating opaque refresh token issued; refresh stored hashed as a `Session` row (`identity`).
4. On mobile, user may enable biometric unlock — a *client-side* gate over the local refresh token; backend never sees biometrics (DEC-011).
5. `users` profile row created (display name, locale default `en-IN`).
6. Standing astrology disclaimer surfaced and acknowledgment recorded (`audit`, DEC-021).

### 3.3 J-2 — Birth profile creation

1. User enters birth date, birth time (with a "time unknown/approximate" option), and birthplace (`birth_profiles`).
2. Birthplace resolved to authoritative coordinates via bundled GeoNames (`geonames-2025-Q3`); optional online typeahead is UX only (DEC-017).
3. Coordinates → IANA zone via `timezonefinder`; local→UTC via `zoneinfo` over `tzdata-2025b`; ambiguous/nonexistent local times handled explicitly and lower birth-time confidence rather than guessing (DEC-017).
4. `astrology` module computes the natal chart on the single-threaded Swiss Ephemeris worker pool: sidereal (Lahiri) Moon longitude → rashi, nakshatra, pada; ascendant context computed and stored (interpreted post-MVP, OQ-4) (DEC-007/008).
5. Natal artifact stamped with the full provenance tuple (`ephemeris_version`, `ayanamsa`, `zodiac`, etc.) and confidence level.
6. Exact birth coordinates encrypted at rest with restricted access; only coarse current location retained for daily presentation (DEC-017, OQ-6).

### 3.4 J-3 — Secure pairing

1. Initiator (Persona A) creates a couple workspace and generates a **single-use, expiring invite** (`couples`).
2. Invite delivered out-of-band (share sheet / link); no partner contact info is required to exist in DilChat.
3. Invited partner (Persona B) registers/authenticates (J-1) and redeems the invite.
4. Both partners must be present and authenticated for the couple to reach `active`; membership rows created with roles mapped neutrally to classical bride/groom ordering per rule pack (DEC-009a, OQ-2).
5. `consent` module presents the scope model (`PRIVATE_A`, `PRIVATE_B`, `SHARED`) and what pairing does and does **not** share; both acknowledge before any shared computation.
6. Default: **nothing private is shared**; only data each user explicitly authorizes for `SHARED` becomes visible to the other (DEC-013).

### 3.5 J-4 — Shared Guna Milan scorecard

1. On `active` couple, `guna_milan` requests both natal Moon-based inputs from `astrology` (never raw private data beyond what the score needs).
2. Ashtakoota computed across all **8 Kootas** using rule pack `ashtakoota_lahiri_classical_v1`, max **36** (DEC-009) — **[Traditional Vedic rule]**.
3. Result is **deterministic and reproducible**: same natal data + same version tuple ⇒ identical score (OBJ-1); the tuple is stamped on the scorecard.
4. Scorecard rendered as a `SHARED` artifact visible to both, with per-Koota explanations from `interpretation_pack_version = dilchat_interp_v1` (DEC-019).
5. Safety-constrained presentation applied: **Nadi** shown only as *traditional constitutional compatibility* (never medical/genetic/fertility/health); **Yoni** only in consensual adult romantic framing (DEC-021).
6. AI may *explain* any Koota on request but the numeric score is immutable and never altered (DEC-019).

### 3.6 J-5 — Daily Moon-interest profile

1. Nightly job precomputes global sidereal Moon transit positions (`moon_transits`, arq cron, DEC-006).
2. Per user per local day (boundary = local midnight, OQ-7), `moon_transits` derives the transiting Moon's relationship to that user's **natal Moon**.
3. `dilchat_transit_v1` extracts transit features; `dilchat_interest_v1` scores interest themes → a **Daily Emotional & Interest Climate** profile (concept 2) — **[DilChat proprietary interpretation]**, explicitly not classical prediction.
4. Next rashi/nakshatra transition times within the day are surfaced (OQ-7).
5. Profile is **per-user** (each partner's own), presented as DilChat interpretation with the standing disclaimer.
6. Read path is cache-served for low latency (Redis, DEC-005); authoritative state remains in Postgres.

### 3.7 J-6 — Private AI chat (reflection space)

1. User opens their private space (`private_chat`, scope `PRIVATE_A` or `PRIVATE_B`).
2. `ai_guidance` calls the `AIProvider` port (default Anthropic Claude, DEC-014) with **only** the minimum authorized context; the AI receives governed structured inputs and **never computes** astronomy, Kootas, or transit scores.
3. AI responses schema-validated and stamped with `prompt_pack_version = dilchat_prompts_v1`.
4. Guardrails enforce DEC-021: AI must never infer infidelity, sexual consent, or psychiatric diagnosis, and never pressure the user to stay in an unsafe relationship.
5. Private content is **never** visible to the partner and the partner is **never** told this conversation exists (DEC-013).
6. Nothing here becomes shared except via an explicit ConsentEvent (J-9 / DEC-013).

### 3.8 J-7 — Shared chat

1. Both partners converse in the `shared_chat` (`SHARED` scope) space.
2. Messages are jointly visible by design; there is no private-to-shared leakage path other than consented projection.
3. AI guidance in shared chat is *couple-facing* and neutral; it never impersonates a partner (Non-Goal NG-7).
4. Shared chat can seed a guided journey (J-8).

### 3.9 J-8 — Guided journey

1. A couple starts a structured `journeys` flow on a friction theme (e.g., finances, family, communication cadence).
2. Each partner may reflect **privately** first (`private_chat`) before anything is shared.
3. The journey proposes a **compromise** frame drawing on the differences surfaced by the scorecard and daily climate — reframing difference as buildable, per the core thesis.
4. AI assists both partners within safety bounds (DEC-021).

### 3.10 J-9 — Compromise → dual-approved agreement

1. One partner drafts an agreement statement (`agreements`).
2. Sharing it is a first-class **ConsentEvent** producing an immutable, bounded **SharedArtifact** — a summary/agreed statement, never a raw private stream (DEC-013).
3. **Important agreements require two-party approval** (OQ-8): the agreement is not `active` until both explicitly approve.
4. Approvals, timestamps, authorship, and revocation policy are recorded immutably (`audit`).
5. Either party may revoke per the recorded revocation policy; revocation is honored immediately.

### 3.11 J-10 — Living Compatibility

1. `feedback` collects consented behavioral signals: agreement adherence, journey completion, ratings (`living_compat`, DEC-019).
2. `dilchat_living_v1` computes **Living Compatibility** (concept 3) as a **jointly-visible aggregate only**; each partner's private inputs/ratings stay private (OQ-9) — **[DilChat proprietary interpretation]**.
3. Living Compatibility **never** feeds back into the classical Guna Milan score or astrology history (DEC-019).
4. Behavioral personalization may adjust presentation of the daily climate (concept 2) within clamped bounds, never rewriting concept (1).

### 3.12 J-11 — Exit (unpair, revoke, export, delete)

1. Either partner may unpair; membership flips to `revoked` and the scope guard denies shared access immediately (DEC-012).
2. User may request data export; an arq job bundles the user's data (`audit`, DEC-006).
3. User may request deletion; deletion is finalized via a background sweep; at-risk exit leaves no partner-visible trace beyond what was already consented and shared.

---

## 4. Functional requirements (FR)

Testable acceptance criterion (AC) per requirement. Grouped by module. Priority: **P0** = MVP-blocking, **P1** = MVP, **P2** = post-MVP.

### 4.1 `identity`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0101 | Email+password registration with Argon2id hashing | P0 | New account created; stored hash verifies with Argon2id; plaintext never persisted |
| FR-0102 | OIDC login for Google and Apple | P0 | Valid OIDC token yields a session; Apple offered whenever any social login is offered |
| FR-0103 | Phone/OTP login | P1 | Correct OTP within TTL creates session; expired/incorrect OTP rejected and rate-limited |
| FR-0104 | Short-lived ES256 access token (10 min) | P0 | Token expires ≤ 10 min; expired token rejected with 401 |
| FR-0105 | Rotating opaque refresh tokens stored hashed | P0 | Refresh rotates on use; prior refresh invalidated; only hash stored |
| FR-0106 | Immediate session revocation | P0 | Revoking a session denies further use within one request cycle |
| FR-0107 | Biometric unlock is client-side only | P0 | No biometric data reaches backend; backend logs contain none |

### 4.2 `users`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0201 | Create/edit user profile (display name, locale) | P0 | Profile persists; locale defaults `en-IN`; edits audited |
| FR-0202 | Standing disclaimer acknowledgment | P0 | First-run disclaimer recorded in `audit`; unacknowledged users cannot view astrology outputs |
| FR-0203 | Locale selection English / Hindi-ready | P1 | English served; Hindi locale selectable and resolves to translated strings when present |

### 4.3 `birth_profiles`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0301 | Capture birth date/time/place | P0 | Values persisted; invalid dates rejected |
| FR-0302 | "Time unknown/approximate" handling | P0 | Missing/approx time lowers confidence flag; no silent default time used |
| FR-0303 | Authoritative geocoding via GeoNames | P0 | Stored coordinates come from `geonames-2025-Q3` or user confirmation, not an online API |
| FR-0304 | Historical local→UTC conversion | P0 | Conversion uses `tzdata-2025b`; ambiguous/nonexistent times flagged, not guessed |
| FR-0305 | Encrypt exact birth coordinates at rest | P0 | Exact coordinates encrypted; only coarse location readable for daily presentation |
| FR-0306 | Optional ascendant field captured now | P1 | Ascendant stored; not interpreted in MVP (OQ-4) |

### 4.4 `astrology`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0401 | Compute sidereal (Lahiri) natal Moon rashi/nakshatra/pada | P0 | Output matches golden-chart vectors within boundary tolerance; ayanamsa = Lahiri stamped |
| FR-0402 | Provenance tuple on every artifact | P0 | Every chart carries `ephemeris_provider/version`, `ayanamsa`, `zodiac` |
| FR-0403 | Moshier fallback with labeling | P0 | If `.se1` files absent, output stamped `ephemeris_provider="moshier"`, confidence lowered, ops alert emitted; never unlabeled |
| FR-0404 | Single-threaded calculation worker pool | P0 | No concurrent mutation of Swiss Ephemeris global state; async handlers never call `swe.*` directly |
| FR-0405 | Reproducibility | P0 | Same natal input + version tuple ⇒ byte-identical chart output |

### 4.5 `guna_milan`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0501 | Compute all 8 Kootas, max 36 | P0 | Scorecard shows 8 Kootas summing to ≤ 36; matches rule-pack tables — **[Traditional Vedic rule]** |
| FR-0502 | Rule-pack provenance stamped | P0 | Scorecard carries `rule_pack_id = ashtakoota_lahiri_classical_v1` |
| FR-0503 | Draft rule packs blocked from user-facing reports | P0 | A pack with `draft: true` cannot render a user-facing scorecard (DEC-009) |
| FR-0504 | Neutral role mapping to bride/groom ordering | P0 | Directional Kootas (Tara, Bhakoot, Graha Maitri) computed via rule-pack ordering; product stores neutral `seeker`/`partner` roles (OQ-2) |
| FR-0505 | Nadi safety framing | P0 | Nadi text never contains medical/genetic/fertility/pregnancy/health language (DEC-021) |
| FR-0506 | Yoni safety framing | P0 | Yoni text appears only in consensual adult romantic framing (DEC-021) |
| FR-0507 | Score immutability | P0 | AI/behavioral layers cannot change a computed score; recompute only on version-tuple change |
| FR-0508 | Private preview scorecard (Persona C) | P1 | Single-user preview computes a scorecard from entered prospective data with **no** outbound contact/notification (OQ-3) |

### 4.6 `moon_transits`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0601 | Nightly global transit precompute | P0 | arq cron populates global transit cache before local-midnight rollovers |
| FR-0602 | Per-user daily climate from transit vs natal Moon | P0 | Daily profile derived from transiting Moon vs that user's natal Moon; labeled interpretation, not prediction — **[DilChat proprietary interpretation]** |
| FR-0603 | Interest-theme scoring | P1 | `dilchat_interest_v1` produces themed interest scores stamped with model version |
| FR-0604 | Local-midnight day boundary + transition times | P0 | Profile keyed to local midnight; next rashi/nakshatra transition times surfaced (OQ-7) |
| FR-0605 | Provenance + disclaimer | P0 | Profile carries `transit_model_version` and standing disclaimer |

### 4.7 `couples`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0701 | Single-use expiring invite | P0 | Invite is redeemable once, expires after TTL; reuse rejected |
| FR-0702 | Both partners required for `active` | P0 | Couple reaches `active` only after both authenticated members join |
| FR-0703 | Immediate unpair/revocation | P0 | Unpair flips membership to `revoked`; shared access denied within one request cycle |
| FR-0704 | Neutral role assignment | P0 | Members assigned neutral roles; no gender required to be entered |

### 4.8 `consent`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0801 | Scope model presented before sharing | P0 | User sees `PRIVATE_A/PRIVATE_B/SHARED` explanation before first shared computation |
| FR-0802 | ConsentEvent as first-class record | P0 | Each share creates a ConsentEvent recording what/who/when/revocation policy (DEC-013) |
| FR-0803 | Consent-gated projection only | P0 | No raw private row becomes shared; only bounded, enumerated SharedArtifacts (DEC-013) |
| FR-0804 | Revocation honored | P0 | Revoking a ConsentEvent removes shared visibility per its policy immediately |
| FR-0805 | Partner never told a private convo exists | P0 | No API/UX surface reveals existence of a partner's private conversation (DEC-013) |

### 4.9 `private_chat`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-0901 | Private reflection space per user | P0 | Messages scoped `PRIVATE_A`/`PRIVATE_B`; partner reads never return them |
| FR-0902 | AI guidance with minimum context | P0 | Provider receives only authorized minimum context; no astronomy/Koota computation delegated to AI (DEC-014) |
| FR-0903 | Safety guardrails | P0 | AI refuses to infer infidelity, sexual consent, psychiatric diagnosis, or pressure user to stay (DEC-021) |

### 4.10 `shared_chat`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1001 | Jointly-visible couple chat | P0 | Both members read/write; scope `SHARED` |
| FR-1002 | AI never impersonates a partner | P0 | AI turns are clearly system-attributed; never authored as either partner (NG-7) |

### 4.11 `journeys`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1101 | Structured guided journey on a theme | P1 | Journey has ordered steps; state persists per couple |
| FR-1102 | Private-first reflection option | P1 | Each partner can reflect privately before any sharing |
| FR-1103 | Compromise framing | P1 | Journey surfaces a compromise frame referencing scorecard/daily differences |

### 4.12 `agreements`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1201 | Draft agreement statement | P1 | Author creates a draft; visible only per consent |
| FR-1202 | Two-party approval for important agreements | P1 | Agreement `active` only after both approve (OQ-8) |
| FR-1203 | Immutable approval record | P1 | Authorship, approvals, timestamps, revocation policy recorded immutably in `audit` |
| FR-1204 | Neutral one-party shared summaries | P2 | Neutral summaries allow one-party authorship + partner visibility, no approval (OQ-8) |

### 4.13 `ai_guidance`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1301 | Provider abstraction via port | P0 | Swapping adapter (Claude↔OpenAI) requires no caller change (DEC-014) |
| FR-1302 | Schema-validated structured outputs | P0 | Every AI output validates against its schema before use; invalid output rejected |
| FR-1303 | Prompt-pack provenance | P0 | Outputs carry `prompt_pack_version = dilchat_prompts_v1` |
| FR-1304 | Zero-retention/no-train provider terms | P0 | Only providers with confirmed zero-retention/no-train terms used in production (DEC-014) — **[Product decision requiring founder approval]** on final vendor |
| FR-1305 | AI never alters classical scores | P0 | AI can explain a Koota; cannot change its value (DEC-019) |

### 4.14 `feedback` / Living Compatibility

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1401 | Guidance thumbs-up/down capture | P1 | Each AI turn ratable; ratings stored with turn + version |
| FR-1402 | Living Compatibility aggregate | P1 | `dilchat_living_v1` produces a jointly-visible aggregate; private inputs stay private (OQ-9) |
| FR-1403 | No feedback into classical score | P0 | Living Compatibility never mutates Guna Milan or astrology history (DEC-019) |

### 4.15 `audit`

| FR | Requirement | Priority | Acceptance criterion |
|----|-------------|----------|----------------------|
| FR-1501 | Immutable audit of consent/pairing/agreements | P0 | Append-only records for consent events, membership changes, approvals |
| FR-1502 | Data export | P1 | Export job bundles a user's data on request (DEC-006) |
| FR-1503 | Deletion finalization | P1 | Deletion sweep removes user data; at-risk exit leaves no new partner-visible trace |
| FR-1504 | Disclaimer/acknowledgment log | P0 | Disclaimer acknowledgments recorded and queryable |

---

## 5. Non-functional requirements (NFR)

| NFR | Category | Requirement / target | Acceptance criterion | Label |
|-----|----------|----------------------|----------------------|-------|
| NFR-01 | Performance — natal calc | Natal chart p95 ≤ 1.5 s, p99 ≤ 3 s | Load test on worker pool meets p95/p99 | [Technical assumption] |
| NFR-02 | Performance — daily profile read | Daily Moon-interest read p95 ≤ 300 ms (cache-served) | Cache-hit read meets p95 | [Technical assumption] |
| NFR-03 | Performance — API general | Read API p95 ≤ 400 ms; write API p95 ≤ 800 ms | k6/Locust run at target RPS | [Technical assumption] |
| NFR-04 | Performance — Guna Milan | Scorecard compute p95 ≤ 500 ms (excludes cold natal calc) | Meets p95 with warmed natal inputs | [Technical assumption] |
| NFR-05 | Availability | ≥ 99.5% monthly for core API (single-region MVP) | Uptime SLO tracked; error budget defined | [Technical assumption] |
| NFR-06 | Scalability | Support 100k registered users / 30k active couples at launch envelope; horizontal stateless API scaling | Autoscale under load test; Postgres/Redis sized | [Technical assumption] |
| NFR-07 | Scalability — transit precompute | Nightly global transit precompute completes within a bounded window before earliest local-midnight rollover | Job SLA met with headroom | [Technical assumption] |
| NFR-08 | Security — transport | TLS 1.2+ everywhere; HSTS on web portal | Scanner confirms; no plaintext endpoints | [Technical assumption] |
| NFR-09 | Security — at rest | Postgres encryption at rest; exact birth coordinates field-encrypted; secrets in a managed vault | Coordinates unreadable without key; secret scan clean | [Technical assumption] |
| NFR-10 | Security — authz defense in depth | App scope guard (default deny) + Postgres RLS backstop | Bypassing app layer still denied by RLS (DEC-012) | [Technical assumption] |
| NFR-11 | Security — authn | Argon2id params meet OWASP guidance; ES256 keys rotated; rate-limited auth | Params reviewed; rotation runbook exists | [Technical assumption] |
| NFR-12 | Privacy — scope isolation | Zero cross-scope leakage between `PRIVATE_A`/`PRIVATE_B`/`SHARED` | Adversarial scope tests pass; OBJ-7 = 0 incidents | [Technical assumption] |
| NFR-13 | Privacy — data minimization | Retain exact coordinates only while needed; coarse location thereafter (OQ-6) | Storage audit confirms coarse-only post-derivation | [DilChat proprietary interpretation] (policy) |
| NFR-14 | Privacy — provider data handling | AI provider zero-retention/no-train; minimum context only | Contract terms recorded; payload audit confirms minimum context | [Product decision requiring founder approval] |
| NFR-15 | Accessibility | WCAG 2.1 AA for web portal; dynamic type, screen-reader labels, sufficient contrast on mobile | Accessibility audit passes AA | [Technical assumption] |
| NFR-16 | Localization | India-first; English (`en-IN`) at launch; Hindi (`hi-IN`) string infrastructure ready, content phased | All user-facing strings externalized; Hindi locale loads translated strings where present | [Product decision requiring founder approval] on Hindi launch timing |
| NFR-17 | Observability | Structured logs, request tracing, metrics on latency/errors/queue depth, ephemeris-fallback alerts | Dashboards + alerts live pre-launch; Moshier fallback alarms (FR-0403) | [Technical assumption] |
| NFR-18 | Cost | Ephemeris/geo/tz self-hosted (no recurring per-call astrology/geocoding fees); AI cost budgeted per active user | Cost model reviewed; no recurring third-party astrology API in prod (DEC-007/017/020) | [Technical assumption] |
| NFR-19 | Data residency | India-region hosting for India-first launch; design for later multi-region | Deployed in `ap-south-1`/`asia-south1` (OQ-13, DEC-018) | [Product decision requiring founder approval] + legal |
| NFR-20 | Reproducibility (cross-cutting) | All generated artifacts carry the full provenance tuple; recompute is deterministic | Recompute of any artifact reproduces prior output for same version tuple | [Technical assumption] |
| NFR-21 | Recoverability | Postgres PITR; documented RPO ≤ 15 min, RTO ≤ 4 h | Restore drill meets RPO/RTO | [Technical assumption] |

---

## 6. MVP boundaries (in / out) mapped to roadmap phases A–G

**Roadmap phases** (delivery order):

| Phase | Theme | Primary modules |
|-------|-------|-----------------|
| **A** | Identity & accounts | `identity`, `users`, `audit` |
| **B** | Birth profiles & astrology engine | `birth_profiles`, `astrology` |
| **C** | Classical Guna Milan | `guna_milan` |
| **D** | Pairing & consent | `couples`, `consent` |
| **E** | Daily Moon-interest + chat | `moon_transits`, `private_chat`, `shared_chat`, `ai_guidance` |
| **F** | Journeys, agreements, living compatibility | `journeys`, `agreements`, `feedback` |
| **G** | Hardening, Hindi, observability, exit | cross-cutting |

**MVP = Phases A–F reaching the flagship milestone (§3.1) + core of G.**

| Capability | In / Out of MVP | Phase | Notes |
|------------|-----------------|-------|-------|
| Email/Google/Apple/phone auth | **In** | A | DEC-011 |
| Biometric client unlock | **In** | A | Client-side only |
| Birth profile + geocoding + tz | **In** | B | Self-hosted datasets (DEC-017) |
| Natal Moon rashi/nakshatra/pada (Lahiri) | **In** | B | DEC-008 |
| Moshier fallback | **In** | B | DEC-007 |
| 8-Koota Guna Milan scorecard (36) | **In** | C | DEC-009; rule pack must exit `draft` |
| Private compatibility preview (Persona C) | **In** | C | Single-user, no outbound contact (OQ-3) |
| Secure pairing + scopes + consent | **In** | D | DEC-012/013 |
| Shared scorecard artifact | **In** | D | Consent-gated (DEC-013) |
| Daily Moon-interest profile | **In** | E | DEC-019 concept 2 |
| Private AI chat | **In** | E | DEC-014/021 |
| Shared chat | **In** | E | — |
| Guided journeys | **In** | F | — |
| Dual-approved agreements | **In** | F | OQ-8 |
| Living Compatibility aggregate | **In** | F | OQ-9 |
| Feedback capture | **In** | F | — |
| Data export / deletion | **In (core)** | G | DEC-006 |
| Hindi content | **Partial** | G | Infrastructure in MVP; full content phased (NFR-16) |
| Observability + fallback alerts | **In** | G | NFR-17 |
| Ascendant-based daily interpretation | **Out** | post-MVP | Field captured now (OQ-4) |
| Tithi scoring | **Out** | post-MVP | Computed/stored now, surfaced later (OQ-5) |
| Alternative ayanamsas (Raman/KP) | **Out** | post-MVP | Rule-pack variants (DEC-008) |
| Asteroids / `seas_*` files | **Out** | post-MVP | DEC-007 |
| Multi-region / international launch | **Out** | post-MVP | India-first (OQ-13) |
| Matchmaking marketplace | **Out (never)** | — | Non-Goal NG-1 |
| Muhurta / electional, Dasha, remedies (gemstones/pujas) | **Out** | post-MVP | Requires domain review |

---

## 7. Explicit NON-GOALS

| NG | Non-goal | Rationale |
|----|----------|-----------|
| NG-1 | DilChat is **not a dating/matchmaking marketplace** | Product is for existing/serious couples + private preview; no partner-discovery graph (OQ-3) |
| NG-2 | **No medical, genetic, fertility, pregnancy, or health advice** — Nadi never mapped to any of these | Hard safety constraint (DEC-021); Nadi = *traditional constitutional compatibility* only |
| NG-3 | **No astrology as evidence** for medical, psychiatric, employment, credit, insurance, or legal decisions | Standing disclaimer; DEC-021 |
| NG-4 | **No surveillance of a partner** | No feature lets one partner monitor, track, or read the other's private space |
| NG-5 | Partner is **never notified that a private conversation exists** | DEC-013 |
| NG-6 | **No auto-sharing of private content** — sharing is always an explicit ConsentEvent | DEC-013 |
| NG-7 | **AI never impersonates a partner** | AI turns are system-attributed; never authored as either partner |
| NG-8 | AI **never infers infidelity, sexual consent, or psychiatric diagnosis**, and never pressures a user to stay in an unsafe relationship | DEC-021 |
| NG-9 | Yoni interpretations are **never sexualized outside a consensual adult romantic context** | DEC-021 |
| NG-10 | DilChat does **not** call a recurring third-party astrology API in production | Astronomy computed in-house (DEC-007/020) |
| NG-11 | AI does **not** compute astronomy, nakshatra, Guna Milan, transit, or Koota values | Deterministic services own those; AI receives governed inputs (DEC-014) |
| NG-12 | Classical Guna Milan score is **not personalized or altered** by behavior or AI | DEC-019 invariant |

---

## 8. Success criteria & KPIs

| KPI | Definition | Target | Source |
|-----|------------|--------|--------|
| **Activation** | Both partners paired **and** shared scorecard viewed | ≥ 80% of paired couples view scorecard within 24h (OBJ-3) | `couples`, `guna_milan`, `audit` |
| **Pairing conversion** | Invited partner completes pairing | ≥ 55% (OBJ-2) | `couples` |
| **Reproducibility** | Recomputations bit-identical for same natal+version tuple | 100% (OBJ-1) | `astrology`, `guna_milan` |
| **Privacy incidents** | Confirmed cross-scope leaks | **0** — release-blocking (OBJ-7, NFR-12) | Security tests, `audit` |
| **Guidance accuracy/helpfulness** | Thumbs-up rate on AI guidance turns | ≥ 70% (OBJ-5) | `feedback` |
| **Daily engagement** | Users opening daily profile ≥ 3×/week | ≥ 35% (OBJ-4) | `moon_transits` |
| **Agreement completion** | Journeys reaching dual-approved agreement | ≥ 25% (OBJ-6) | `agreements` |
| **Natal calc latency** | p95 natal computation | ≤ 1.5 s (OBJ-8, NFR-01) | Observability |
| **Fallback rate** | Requests served by Moshier fallback | ≤ 0.5% (alarmed) | FR-0403, NFR-17 |
| **Safe exit** | Unpair→revoke honored within one request cycle | 100% | `couples`, tests |

**Guardrail KPIs (must not regress):** privacy incidents = 0; classical-score mutation events = 0; AI safety-guardrail violations = 0.

---

## 9. Assumptions & dependencies

### 9.1 Technical assumptions

| ID | Assumption |
|----|------------|
| TA-1 | Swiss Ephemeris (`swe-2.10.03`) via `pyswisseph` with Moshier fallback delivers Moon longitude sufficient for rashi/nakshatra/pada boundaries (DEC-007). |
| TA-2 | Single-threaded worker pool safely serializes Swiss Ephemeris global-state access at target throughput (DEC-007). |
| TA-3 | `geonames-2025-Q3` + `timezonefinder` + `tzdata-2025b` cover supported birth years/places with acceptable accuracy (DEC-017). |
| TA-4 | PostgreSQL 16 RLS + application scope guard together prevent cross-scope leakage (DEC-012). |
| TA-5 | Redis 7 cache serves daily profiles within NFR-02; Postgres remains sole source of truth (DEC-005). |
| TA-6 | arq handles nightly precompute, recalculation sweeps, export, and deletion at launch scale (DEC-006, Proposed). |
| TA-7 | React Native (Expo) is adequate for the mobile client; backend stays a clean HTTP/JSON API regardless (DEC-015, Proposed). |
| TA-8 | Latency targets (NFR-01–04) are achievable in a single India region (DEC-018). |

### 9.2 Unverified astrology-domain assumptions (**Requires domain review**)

| ID | Assumption |
|----|------------|
| DA-1 | The 8-Koota Ashtakoota tables in `ashtakoota_lahiri_classical_v1` will be sourced from one named classical authority (recommend B. V. Raman) and frozen after expert sign-off (DEC-009, OQ-1) — **[Traditional Vedic rule]** pending citation. |
| DA-2 | Bride/groom directional logic (Tara, Bhakoot, Graha Maitri) is retained but mapped to neutral `seeker`/`partner` roles per rule pack; the classical role↔partner mapping needs expert confirmation (DEC-009a, OQ-2). |
| DA-3 | Lahiri ayanamsa is the correct default basis for Guna Milan for the target market (DEC-008) — **[Traditional Vedic rule]**. |
| DA-4 | Daily climate derived from transiting Moon vs natal Moon is a defensible **[DilChat proprietary interpretation]**, explicitly distinct from any classical Gochara prediction (DEC-019). |
| DA-5 | MVP daily interpretation uses natal-Moon house (not ascendant); ascendant interpretation deferred (OQ-4). |
| DA-6 | Nadi presented purely as constitutional compatibility (no health mapping) remains faithful enough to be acceptable to domain reviewers (DEC-021) — needs confirmation. |

### 9.3 Legal / licensing questions (**Requires legal review**)

| ID | Question |
|----|----------|
| LQ-1 | Swiss Ephemeris licensing: obtain Astrodienst professional/commercial license before public launch; AGPL build + Moshier fallback used only in interim development (DEC-007, OQ-10). |
| LQ-2 | AI provider zero-retention/no-training contractual terms for user content (DEC-014, OQ-12). |
| LQ-3 | Social IdP (Apple/Google) and SMS provider data-sharing terms (DEC-011). |
| LQ-4 | India DPDP Act compliance for consent, minors, export/deletion, and data residency; GDPR/CCPA if international (DEC-018, OQ-13). |
| LQ-5 | Exact wording of the standing astrology disclaimer and safety notices (DEC-021). |
| LQ-6 | Sensitive-data handling posture for birth data + relationship content under Indian law. |

### 9.4 Product decisions requiring founder approval

| ID | Decision |
|----|----------|
| PD-1 | Final Guna Milan classical source authority for `..._v1` (DEC-009, OQ-1) — **[Product decision requiring founder approval]**. |
| PD-2 | Confirm target segment = committed/married + seriously dating, with single-user private preview for prospective matches (OQ-3). |
| PD-3 | Two-party approval threshold for "important" vs one-party neutral summaries (OQ-8). |
| PD-4 | Living Compatibility visibility = jointly-visible aggregate only (OQ-9). |
| PD-5 | India-first launch and India-region residency (OQ-13, DEC-018). |
| PD-6 | Hindi content launch timing (MVP infrastructure vs phased content, NFR-16). |
| PD-7 | Final AI vendor selection under zero-retention terms (DEC-014, OQ-12). |
| PD-8 | Activation/conversion targets (OBJ-2 and related) as committed OKRs. |

### 9.5 Cross-module dependency order (from DEC-002)

`audit` ← `identity` ← `users` ← `birth_profiles` ← `astrology` ← {`guna_milan`, `moon_transits`} ← `couples` ← `consent` ← {`private_chat`, `shared_chat`, `journeys`, `agreements`} ← `ai_guidance` ← `feedback`. A module may depend only on modules lower in this order; an import-linter contract enforces it.

---

## 10. Traceability — the DilChat design-document suite

This PRD is document **2 of 10**. It defines *what* and *why*; the sibling docs define *how*. On any conflict, the **Decision Log is canonical**.

| # | Document | Relationship to this PRD |
|---|----------|--------------------------|
| 1 | `DILCHAT_DECISION_LOG.md` | **Canonical.** All versions/names/decisions cited here originate there. |
| 2 | `DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md` | **This document** — goals, personas, journeys, FR/NFR, MVP, non-goals, KPIs. |
| 3 | `DILCHAT_BACKEND_ARCHITECTURE.md` | Realizes §4/§5 as the modular monolith (DEC-002); module extraction path. |
| 4 | `DILCHAT_API_SPEC.md` (+ `openapi/dilchat.openapi.yaml`) | HTTP contract for the FRs; design source of the OpenAPI. |
| 5 | `DILCHAT_DATA_MODEL.md` | Tables per module, scope columns (`PRIVATE_A/PRIVATE_B/SHARED`), RLS policies (DEC-012). |
| 6 | `DILCHAT_ASTROLOGY_ENGINE_SPEC.md` | Natal calc, ayanamsa, ephemeris/fallback, tz handling for §3.3/§4.4 (DEC-007/008/017). |
| 7 | `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md` | Consent state machine + SharedArtifact projection behind §3.4/§3.10 (DEC-013). |
| 8 | `DILCHAT_AI_GUIDANCE_SPEC.md` | Provider port, prompt packs, guardrails for §3.7/§4.13 (DEC-014/021). |
| 9 | `DILCHAT_TEST_AND_VALIDATION_PLAN.md` | Golden charts, reproducibility, adversarial scope tests, oracle validation (DEC-020) — verifies the ACs here. |
| 10 | `DILCHAT_ROADMAP_AND_OPERATIONS.md` | Phases A–G (§6), observability, cost, residency, runbooks (DEC-006/018). |

**Traceability rule:** every FR-#### and NFR-#### in this document is expected to appear (by ID) in at least the API spec (4), data model (5), and test plan (9). The test plan (9) is the authority that each acceptance criterion here is actually verified.

---

*End of DilChat Backend Product Requirements Document. Design phase — no production code authored. All astrology claims carry their tradition/interpretation labels; all safety constraints of DEC-021 are binding on implementation.*
