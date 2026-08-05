# DilChat — AI Assist Privacy, Provenance, and Safety (V1)

**Product:** DilChat · **Company:** Ugence Labs
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** DEC-048.

> **Documentation only.** No data pipeline, model, storage, or policy engine is
> implemented here. This document defines the required data scope, consent,
> Moon-climate safety language, provenance, and auditability that any future
> implementation must satisfy.

Builds on the existing
[`DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`](DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md)
and the three-scope authorization model (`PRIVATE_A` / `PRIVATE_B` / `SHARED`).
This document adds the AI-Assist-specific requirements.

---

## 1. Data scope

### 1.1 AI Assist **may** use

- the current shared partner conversation;
- prior shared conversations;
- explicit shared preferences;
- consented interaction feedback;
- optional birth-profile-derived signals (structural prior; Moon context);
- current deterministic Moon context.

### 1.2 AI Assist **must not** use

- Partner A's **private** AI conversation to advise Partner B;
- Partner B's **private** AI conversation to advise Partner A;
- private notes;
- unshared inferred preferences;
- deleted conversation history;
- revoked relationship context;
- data from **another couple**;
- information retained after unpairing **without a valid retention basis**.

**Private-to-shared projection requires explicit consent.** Private information
must **not** silently influence shared recommendations. Any path that would take a
`PRIVATE_A`/`PRIVATE_B`-scoped signal into a `SHARED` recommendation requires a
recorded, explicit consent event.

---

## 2. User controls (must eventually exist)

Users must eventually be able to:

- **disable birth-derived personalization** (structural prior + Moon context);
- **disable conversation-history personalization**;
- **correct inferred interests**;
- **remove inferred sensitivities**;
- **delete learned preference data**;
- **understand the broad category of evidence** behind a suggestion.

The exact proprietary formula, feature values, Koota tables, and internal weights
**need not** be exposed. (Per-source control granularity is an open question,
OQ-AIA-7; retention/deletion periods OQ-AIA-8.)

**Interaction with weighting:** disabling birth-derived personalization sets the
structural-prior contribution to 0 % (see
[signal fusion §3](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md#3-structural-prior-weighting-60--30));
disabling conversation-history personalization removes the conversation-evidence
contribution and the progressive-dominance behavior. Safety and explicit
boundaries continue to apply regardless.

---

## 3. Provenance and auditability

Every generated AI Assist recommendation should be traceable to **structured
provenance** — the broad categories of evidence, not raw model internals.

### 3.1 Provenance categories

- `CURRENT_SHARED_CHAT`
- `PRIOR_SHARED_CHAT`
- `EXPLICIT_PREFERENCE`
- `INFERRED_SHARED_PREFERENCE`
- `USER_FEEDBACK`
- `GUNA_STRUCTURAL_PRIOR`
- `MOON_RECEPTIVITY_CONTEXT`
- `SAFETY_POLICY`
- `BOUNDARY_RULE`

### 3.2 Per-recommendation record — store or calculate

| Field | Meaning |
|-------|---------|
| `recommendation_id` | Unique ID for the recommendation. |
| `model_version` | Guidance/LLM composition version. |
| `guna_feature_version` | `structural_relationship_prior_v1` (or successor). |
| `moon_calculation_version` | `moon_receptivity_context_v1` + astronomy-model version. |
| `conversation_evidence_version` | `conversation_evidence_model_v1`. |
| `fusion_policy_version` | `ai_assist_guidance_fusion_v1` precedence/composition version (binding structure). |
| `calibration_profile_version` | `ai_assist_calibration_profile_v1` — the versioned, tunable calibration defaults (sub-splits, Moon bound, thresholds) applied to this recommendation. |
| `signal_categories_used` | Which provenance categories contributed. |
| `confidence` | Confidence in the recommendation. |
| `evidence_counts` | Qualified-evidence counts behind it. |
| `current_guna_weight` | The structural-prior weight applied (60 %…30 %). |
| `reason_for_weight_adjustment` | Why the weight sits where it does (qualified-evidence summary). |
| `generation_timestamp` | When generated. |
| `expiration_timestamp` | Expiry for temporary climate signals. |
| `user_action` | `accepted` / `edited` / `rejected` / `ignored` / `corrected`. |

### 3.3 What must **not** be persisted

- Unnecessary **chain-of-thought** or private model reasoning.
- Raw sensitive payloads beyond what the existing audit model permits (the
  existing audit is append-only and never stores secrets or raw sensitive
  payloads — that constraint continues to hold).

---

## 4. Moon-climate safety language

The Moon model estimates **conversational receptivity, not actual inner emotional
state**. Language must reflect that.

### 4.1 Allowed

- "A gentler opening may work better."
- "Familiar or reassuring subjects may be easier to approach."
- "Consider keeping the question low-pressure."
- "This may be a better time for practical rather than highly personal
  discussion."

### 4.2 Prohibited

- "Your partner is emotionally unstable today."
- "The Moon guarantees conflict."
- "Your partner will reject this topic."
- "Do not discuss money because of today's Moon."
- deterministic claims about a person's mental state;
- medical or psychological diagnosis;
- guaranteed predictions.

### 4.3 Structural rule

- The Moon signal **may** alter timing, tone, intimacy, pressure, and topic
  approachability.
- The Moon signal **must not** independently create an "Avoid" topic, invent a
  dislike, or assert a person's actual emotion or mental state.

---

## 5. Safety precedence

Safety policies **override every personalization signal** (see
[signal fusion §7](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md#7-recommendation-precedence-authoritative-order)).
In precedence order, **safety restrictions** rank first, then **explicit user
boundary**, then observed behavior, explicit interest, recent context, Moon
receptivity, and finally the Guna structural prior. No favorable astrological
signal can override a boundary or a safety restriction.

Abuse and coercion safeguards (e.g. ensuring AI Assist cannot be used to pressure,
monitor, or manipulate a partner) are an open question requiring dedicated design
(OQ-AIA-13) and must be resolved before the AI Assist overlay ships.

---

## 6. Unpairing and revocation

- **Unpairing revokes relationship-derived recommendation access.** After
  unpairing, relationship-scoped conversation evidence and shared inferred
  preferences must no longer feed recommendations.
- Data **retained after unpairing** requires a **valid retention basis**; absent
  one, it must not be used.
- **Revoked relationship context** and **deleted conversation history** must not be
  used as evidence.

---

## 7. Disclosure (non-deceptive)

Product disclosure names the **broad categories** of personalization without
exposing the proprietary internals (see
[product requirements §8](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md#8-product-disclosure)).
DilChat must not present an authoritative Guna score, a scientific-validation
claim, a guarantee of emotional receptivity or relationship success, or any hidden
claim that classical-authority review has been completed.

---

## 8. Open questions (privacy/safety subset)

Tracked in
[`DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md`](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md#open-questions);
not decided here:

- per-source personalization controls (OQ-AIA-7);
- inferred-preference retention and deletion periods (OQ-AIA-8);
- whether users see broad provenance labels (OQ-AIA-10);
- LLM provider and data-retention policy (OQ-AIA-11);
- shared-chat retention policy (OQ-AIA-12);
- abuse and coercion safeguards (OQ-AIA-13);
- localization of sensitive-topic language (OQ-AIA-14).
