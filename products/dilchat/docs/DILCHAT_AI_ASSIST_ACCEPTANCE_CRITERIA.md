# DilChat — AI Assist Requirements & Acceptance Criteria (V1)

**Product:** DilChat · **Company:** Ugence Labs
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** DEC-048.

> **Documentation only.** These are requirements and acceptance criteria for
> *future* implementation. Nothing here is built or enabled. A machine-readable
> mirror of these requirements lives in
> [`ai_assist_requirements.json`](ai_assist_requirements.json).

Requirement identifier families:

| Family | Area |
|--------|------|
| `AIA-FUNC-*` | Functional behavior |
| `AIA-SIGNAL-*` | Signal composition / weighting |
| `AIA-MOON-*` | Moon receptivity context |
| `AIA-GUNA-*` | Guna structural prior / no user-visible score |
| `AIA-PRIV-*` | Privacy / consent / data scope |
| `AIA-SAFE-*` | Safety |
| `AIA-UX-*` | Overlay UI / UX |
| `AIA-AUDIT-*` | Provenance / auditability |
| `AIA-CALIB-*` | Versioned calibration defaults (tunable, not immutable) |
| `AIA-TEST-*` | Test obligations |

---

## 0. Two tiers: binding invariants vs. configurable calibration defaults

Requirements in this document fall into **two tiers**. A conformant
implementation must not confuse them.

### 0.1 Binding invariants (founder decisions — DEC-048)

These are **binding**. They cannot be changed by calibration, experimentation, or
configuration; changing any of them is a **new founder decision**, not a tuning
action.

| Invariant | Requirement |
|-----------|-------------|
| Guna structural-prior weight **starts at 60 %** for an eligible cold-start profile | AIA-SIGNAL-3 |
| Guna structural-prior weight **never drops below the 30 % floor** | AIA-SIGNAL-4 |
| Weight declines **only from qualified evidence** (never elapsed time / message count) | AIA-SIGNAL-5 |
| **Hierarchical Guna–Moon composition** — Guna sets posture, Moon is a separate bounded temporary modifier; never a single undifferentiated weighted average | AIA-SIGNAL-1, AIA-SIGNAL-2, AIA-MOON-1 |
| **Recommendation precedence order** (safety › explicit boundary › repeated observed behavior › explicit interest › recent context › Moon › Guna) | AIA-SIGNAL-8 |
| **Moon cannot independently create an avoid topic** | AIA-MOON-2 |
| **Safety and privacy constraints** override every personalization signal | AIA-SAFE-1…4, AIA-PRIV-1…6 |
| **No user-visible Guna score**; no classical-authority validation claim | AIA-GUNA-2…4 |

### 0.2 Configurable calibration defaults (versioned)

These are **initial calibration defaults**, carried in a **versioned calibration
profile** (`ai_assist_calibration_profile_v1`, recorded in provenance as
`calibration_profile_version`). They may be **tuned through controlled
evaluation** — offline evaluation, A/B or holdout experiments, monitored
rollout — **without changing the core architecture** and without a new founder
decision, **provided every binding invariant in §0.1 still holds**.

| Calibration default (initial) | Requirement | Constraint when tuning |
|-------------------------------|-------------|------------------------|
| Structural-posture sub-split — cold start **60/25/15**, mature **30/20/50** (Guna prior / explicit preferences / conversation evidence) | AIA-CALIB-1 | Totals must remain 60/40 (cold start) and 30/70 (mature); the 60 % start and 30 % floor are binding. |
| Moon modifier bound **0.80–1.20** in `TopicReceptivity = baseline_topic_affinity × moon_climate_modifier` | AIA-CALIB-2 | Must stay a bounded modifier that cannot overturn an explicit preference or strong behavioral evidence (precedence order still governs). |
| Decay curve / evidence thresholds / topic-confidence thresholds / Moon expiration | AIA-CALIB-3 | Bounded by the invariants; exact values are open (OQ-AIA-1…5). |

Tuning a calibration default requires a **calibration-profile version bump** and a
recorded rationale; it must never silently alter behavior or bypass §0.1.

---

## 1. Functional (`AIA-FUNC-*`)

- **AIA-FUNC-1** — AI Assist **never sends a message**; every message requires
  explicit manual user send.
- **AIA-FUNC-2** — The AI Assist overlay opens **only** on explicit user tap and
  **never** automatically.
- **AIA-FUNC-3** — The overlay presents **exactly one** AI recommendation and
  **never** duplicates recommendation text.
- **AIA-FUNC-4** — The overlay supports **insert into composer** and
  **rephrase / sentence-correction** as **user-controlled** actions.
- **AIA-FUNC-5** — The recommendation engine distinguishes and records the signal
  origin of each suggestion (direct conversation evidence, historical preference,
  inferred preference, Guna structural signal, Moon receptivity, LLM wording).
- **AIA-FUNC-6** — Output categories are Good Topics, Approach Gently, Give Space,
  and (conservative) Avoid Topics; sensitive/avoid categories appear only when
  supported by evidence.

## 2. Signal composition (`AIA-SIGNAL-*`)

- **AIA-SIGNAL-1** — Guna and Moon signals are **not** collapsed into one
  undifferentiated weighted average.
- **AIA-SIGNAL-2** — Composition follows the hierarchy: Guna posture →
  conversation history modifies/overrides → Moon climate modifier → explicit
  preferences/boundaries override both → safety overrides all → LLM wording last.
- **AIA-SIGNAL-3** — The structural-prior weight begins at **60 %** for an
  eligible cold-start profile.
- **AIA-SIGNAL-4** — The structural-prior weight **never drops below 30 %**.
- **AIA-SIGNAL-5** — The weight declines **only** from **qualified evidence**, not
  from elapsed time or raw message count.
- **AIA-SIGNAL-6** — Conversation evidence can **override** the static structural
  prior when qualified and recent.
- **AIA-SIGNAL-7** — Explicit preferences take precedence over inferred
  preferences; recent repeated behavior takes precedence over the static prior.
- **AIA-SIGNAL-8** — Recommendation precedence (highest first): safety →
  explicit boundary → repeated observed behavior → explicit interest → recent
  shared-conversation context → Moon receptivity → Guna structural prior.

## 3. Moon (`AIA-MOON-*`)

- **AIA-MOON-1** — Moon context is a **bounded, temporary** modifier and is
  applied **separately** from the structural-prior weighting.
- **AIA-MOON-2** — Moon context **cannot independently create an avoid topic**.
- **AIA-MOON-3** — Moon context **expires** and is **recalculated**; each context
  carries an expiration timestamp.
- **AIA-MOON-4** — Moon language estimates **conversational receptivity**, never a
  person's actual emotion, mental state, or a guaranteed outcome; only the allowed
  phrasings (privacy/provenance doc §4.1) are permitted.

## 4. Guna (`AIA-GUNA-*`)

- **AIA-GUNA-1** — The internal Guna Milan pattern logic is **proprietary and
  hidden** from users.
- **AIA-GUNA-2** — **No user-visible Guna score out of 36**, individual Koota
  scores, Dosha/Parihara results, source tables, or model weights are exposed
  (`USER_VISIBLE_GUNA_SCORE_DISABLED`).
- **AIA-GUNA-3** — **No compatibility score is shown** anywhere in AI Assist.
- **AIA-GUNA-4** — No claim that the model is an authoritative or universally
  accepted classical implementation; no claim of classical-authority validation
  (`CLASSICAL_GUNA_AUTHORITY_VALIDATION_BLOCKED` preserved).
- **AIA-GUNA-5** — The structural prior determines **posture only**, never whether
  the relationship is good, bad, successful, or destined to fail.

## 5. Privacy (`AIA-PRIV-*`)

- **AIA-PRIV-1** — Private content **cannot cross into shared recommendations
  without explicit consent**; private info never silently influences shared
  recommendations.
- **AIA-PRIV-2** — Partner A's private AI conversation is never used to advise
  Partner B (and vice versa).
- **AIA-PRIV-3** — Deleted history, revoked relationship context, unshared
  inferred preferences, private notes, and other couples' data are never used.
- **AIA-PRIV-4** — **Unpairing revokes** relationship-derived recommendation
  access; retained-after-unpair data requires a valid retention basis.
- **AIA-PRIV-5** — Users can disable birth-derived personalization, disable
  conversation-history personalization, correct inferred interests, remove
  inferred sensitivities, and delete learned preference data.
- **AIA-PRIV-6** — Users can understand the **broad category** of evidence behind
  a suggestion without the proprietary formula/weights being exposed.

## 6. Safety (`AIA-SAFE-*`)

- **AIA-SAFE-1** — Safety policies override every personalization signal.
- **AIA-SAFE-2** — Explicit boundaries override every astrological signal.
- **AIA-SAFE-3** — No deterministic mental-state claims, medical/psychological
  diagnosis, or guaranteed predictions are generated.
- **AIA-SAFE-4** — A topic enters "Avoid" **only** via explicit boundary,
  repeated strong negative behavioral evidence, an active unresolved conflict, or
  a safety restriction — never Guna/Moon alone.

## 7. UX (`AIA-UX-*`)

- **AIA-UX-1** — Overlay opens only on explicit tap; never auto-opens; partner
  chat context is retained behind it; a clear "AI ASSIST" heading is shown.
- **AIA-UX-2** — Exactly one AI recommendation is shown.
- **AIA-UX-3** — Recommendation text is not duplicated.
- **AIA-UX-4** — Good Topics are displayed **one item per line**; topic items do
  **not** use a two-column table.
- **AIA-UX-5** — AI-generated suggestions are clearly distinguished from partner
  messages, both visually and for assistive technology.
- **AIA-UX-6** — When no supported avoid topic exists, the UI shows "No clear
  topic to avoid from this conversation."
- **AIA-UX-7** — Accessible touch targets and screen-reader labels are provided;
  clean, mobile-first, rounded-card layout.
- **AIA-UX-8** — The approved chat-header template **avoids call and video-call
  icons**.

## 8. Auditability (`AIA-AUDIT-*`)

- **AIA-AUDIT-1** — Every recommendation exposes **structured provenance
  categories** internally (the nine categories in the privacy/provenance doc).
- **AIA-AUDIT-2** — Each recommendation records model/version fields, signal
  categories used, confidence, evidence counts, current Guna weight, reason for
  weight adjustment, generation timestamp, expiration timestamp, and user action.
- **AIA-AUDIT-3** — Unnecessary chain-of-thought / private model reasoning is
  **not** persisted.

## 8b. Calibration defaults (`AIA-CALIB-*`)

These requirements govern the **versioned, tunable** calibration defaults (§0.2).
They are **not** founder invariants; they are the initial values and the rules for
changing them.

- **AIA-CALIB-1** — The structural-posture sub-split defaults are **cold start
  60/25/15** and **mature 30/20/50** (Guna prior / explicit preferences /
  conversation evidence). These are versioned defaults; they may be tuned via
  controlled evaluation **so long as** the binding totals (60/40 and 30/70), the
  60 % cold-start start, and the 30 % floor are preserved (AIA-SIGNAL-3/4).
- **AIA-CALIB-2** — The Moon modifier default bound is **0.80–1.20** in
  `TopicReceptivity = baseline_topic_affinity × moon_climate_modifier`. It is a
  versioned default; it may be tuned via controlled evaluation **so long as** it
  remains a bounded modifier that cannot overturn an explicit preference or strong
  behavioral evidence, and cannot create an avoid topic (AIA-MOON-2).
- **AIA-CALIB-3** — All other numeric calibration parameters (decay curve,
  evidence-event thresholds, topic-confidence thresholds, Moon expiration period)
  are versioned defaults bounded by the §0.1 invariants; their exact values are
  open (OQ-AIA-1…5).
- **AIA-CALIB-4** — Calibration defaults are carried in a **versioned calibration
  profile** (`ai_assist_calibration_profile_v1`); any change bumps
  `calibration_profile_version`, is recorded with a rationale in provenance
  (AIA-AUDIT-2), and must leave every §0.1 invariant intact.

## 9. Test obligations (`AIA-TEST-*`)

- **AIA-TEST-1** — Tests prove the 60 % cold-start weight for an eligible profile.
- **AIA-TEST-2** — Tests prove the weight never drops below the 30 % floor.
- **AIA-TEST-3** — Tests prove the weight declines only from qualified evidence.
- **AIA-TEST-4** — Tests prove explicit boundaries override every astrological
  signal.
- **AIA-TEST-5** — Tests prove Moon context cannot independently create an avoid
  topic.
- **AIA-TEST-6** — Tests prove conversation evidence can override the static prior.
- **AIA-TEST-7** — Tests prove private content cannot enter shared recommendations
  without consent.
- **AIA-TEST-8** — Tests prove the AI never sends a message.
- **AIA-TEST-9** — Tests prove only one recommendation appears and text is not
  duplicated.
- **AIA-TEST-10** — Tests prove no compatibility score is shown.
- **AIA-TEST-11** — Tests prove unpairing revokes relationship-derived
  recommendation access.
- **AIA-TEST-12** — Tests prove temporary Moon context expires and is recalculated.
- **AIA-TEST-13** — Tests prove user corrections modify future inferred
  preferences.
- **AIA-TEST-14** — Tests prove no deterministic mental-state claims are generated.
- **AIA-TEST-15** — Tests prove a calibration-profile change (sub-split or Moon
  bound) **cannot** violate a §0.1 invariant: the 60 % start and 30 % floor hold,
  the binding totals (60/40, 30/70) hold, the precedence order holds, and Moon
  still cannot create an avoid topic — across the full allowed calibration range.

---

## Acceptance criteria (founder-level, must all hold)

The following acceptance criteria are the founder-level bar for the AI Assist
capability. Each maps to one or more `AIA-*` requirements above. **Tier** marks
whether the criterion is a **binding** founder invariant (§0.1) or a
**calibration** default check (§0.2). Binding criteria can never be relaxed by
tuning; calibration criteria assert the *initial* default **and** that tuning
stays within the invariants.

| # | Acceptance criterion | Tier | Maps to |
|---|----------------------|------|---------|
| 1 | Guna weight begins at **60 %** for an eligible cold-start profile | **Binding** | AIA-SIGNAL-3 |
| 2 | Guna weight **never drops below 30 %** | **Binding** | AIA-SIGNAL-4 |
| 3 | Weight declines **only from qualified evidence** | **Binding** | AIA-SIGNAL-5 |
| 4 | Explicit boundaries **override every astrological signal** | **Binding** | AIA-SAFE-2, AIA-SIGNAL-8 |
| 5 | Moon context **cannot independently create an avoid topic** | **Binding** | AIA-MOON-2, AIA-SAFE-4 |
| 6 | Conversation evidence **can override the static prior** | **Binding** | AIA-SIGNAL-6 |
| 7 | Recommendations **expose provenance categories internally** | **Binding** | AIA-AUDIT-1 |
| 8 | Private content **cannot cross into shared recommendations without consent** | **Binding** | AIA-PRIV-1 |
| 9 | AI **never sends a message** | **Binding** | AIA-FUNC-1 |
| 10 | **Only one recommendation** appears in the overlay | **Binding** | AIA-UX-2 |
| 11 | Good Topics are **displayed one item per line** | **Binding** | AIA-UX-4 |
| 12 | Recommendation text **is not duplicated** | **Binding** | AIA-UX-3 |
| 13 | **Compatibility score is not shown** | **Binding** | AIA-GUNA-3 |
| 14 | **Unpairing revokes** relationship-derived recommendation access | **Binding** | AIA-PRIV-4 |
| 15 | Temporary Moon context **expires and is recalculated** | **Binding** | AIA-MOON-3 |
| 16 | User corrections **modify future inferred preferences** | **Binding** | AIA-PRIV-5 |
| 17 | **No deterministic mental-state claims** are generated | **Binding** | AIA-SAFE-3, AIA-MOON-4 |
| 18 | Structural-posture sub-split **defaults** to 60/25/15 (cold start) and 30/20/50 (mature), and is tunable only within the binding totals | **Calibration** | AIA-CALIB-1 |
| 19 | Moon modifier **defaults** to the 0.80–1.20 bound and stays a bounded modifier when tuned | **Calibration** | AIA-CALIB-2 |
| 20 | Calibration changes **bump `calibration_profile_version`**, record a rationale, and preserve every §0.1 invariant | **Calibration** | AIA-CALIB-4, AIA-TEST-15 |

**Acceptance-criteria count: 20** (17 binding invariants + 3 calibration-default
checks).

---

## Open questions

These implementation choices are **unresolved** and must not be presented as
approved requirements. They are surfaced, not decided.

| ID | Open question |
|----|---------------|
| OQ-AIA-1 | Exact mathematical decay curve from 60 % to 30 %. |
| OQ-AIA-2 | Minimum number and quality of evidence events before weight reduction. |
| OQ-AIA-3 | Topic-confidence thresholds. |
| OQ-AIA-4 | Maximum Moon modifier magnitude. |
| OQ-AIA-5 | Moon signal expiration period. |
| OQ-AIA-6 | Topic-domain taxonomy ownership. |
| OQ-AIA-7 | User controls for disabling each personalization source. |
| OQ-AIA-8 | Inferred-preference retention and deletion periods. |
| OQ-AIA-9 | Recommendation feedback UI. |
| OQ-AIA-10 | Whether users see broad provenance labels. |
| OQ-AIA-11 | LLM provider and data-retention policy. |
| OQ-AIA-12 | Shared-chat retention policy. |
| OQ-AIA-13 | Abuse and coercion safeguards. |
| OQ-AIA-14 | Localization of sensitive-topic language. |
| OQ-AIA-15 | Evaluation metrics for recommendation quality. |
| OQ-AIA-16 | Rollback and feature-flag strategy. |
| OQ-AIA-17 | Whether "Avoid Topics" remains in V1 or is renamed "Approach Carefully." |

**Open-question count: 17.**
