# DilChat — Relationship Signal Fusion Requirements (V1)

**Product:** DilChat · **Company:** Ugence Labs
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** DEC-048 (see [`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md)).

> **Documentation only.** This document specifies *how* the four AI Assist
> components combine. It implements nothing. See
> [`DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md`](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md)
> for the components themselves and the founder decision.

---

## 1. Non-collapse principle

Guna and Moon signals **must not** be collapsed into one undifferentiated weighted
average. They answer **different questions**, operate on **different timescales**,
and carry **different precedence**:

| Signal | Question answered | Timescale | Role |
|--------|-------------------|-----------|------|
| **Guna** structural prior (`structural_relationship_prior_v1`) | "How should this person be approached within this relationship?" | Stable | Baseline **posture** |
| **Moon** receptivity (`moon_receptivity_context_v1`) | "What areas may be more or less receptive at the present time?" | Temporary / bounded | **Climate** modifier |
| **Conversation evidence** (`conversation_evidence_model_v1`) | "What has this person actually demonstrated?" | Accumulating; recency-weighted | **Source of truth**, progressively dominant |
| **Explicit preferences / boundaries** | "What has this person explicitly asked for or ruled out?" | Durable until changed | **Override** |
| **Safety policy** | "What must never be recommended?" | Absolute | **Hard override** |

The Moon signal **does not replace** the Guna signal. It re-weights *topic
approachability and tone at a point in time*; Guna sets the *relational posture*.

---

## 2. Signal hierarchy (composition order)

The guidance-fusion layer (`ai_assist_guidance_fusion_v1`) composes signals in
this order:

1. **Guna-derived model** determines the **baseline relational posture**.
2. **Conversation history** progressively **modifies and may override** that
   posture.
3. **Moon model** determines **current topic receptivity** and communication
   climate (applied as a bounded, temporary modifier).
4. **Explicit preferences and boundaries** override **both** Guna and Moon.
5. **Safety policies** override **every** personalization signal.
6. The **LLM** converts the resulting guidance state into natural-language
   suggestions — **only after** steps 1–5 have produced the guidance state.

```
                 ┌─────────────────────────────────────────────┐
  Guna prior ───▶│ baseline posture                            │
                 │   ▲ modified/overridden by                  │
  Conversation ──┼──▶│ observed evidence (progressively wins)  │
  evidence       │                                             │
  Moon climate ──┼──▶ bounded temporary topic/tone modifier    │
                 │                                             │
  Explicit pref ─┼──▶ overrides Guna + Moon                    │
  / boundary     │                                             │
  Safety ────────┼──▶ overrides everything                     │
                 └───────────────┬─────────────────────────────┘
                                 ▼
                        guidance state (deterministic)
                                 ▼
                        LLM wording (last step only)
```

---

## 3. Structural-prior weighting: 60 % → 30 %

The Guna-derived **structural prior** is weighted against explicit preferences and
observed conversation evidence. The weight is **conceptual guidance**, not a
frozen formula (the exact curve is an open question — OQ-AIA-1).

| Profile stage | Guna-derived structural prior | Explicit preferences + conversation evidence |
|---------------|------------------------------|----------------------------------------------|
| **New user (cold start)** | **60 %** | **40 %** (explicit preferences + early conversation evidence) |
| **Mature conversation profile** | **30 % floor** | **70 %** (explicit preferences + observed conversation evidence) |

**Rules governing the transition:**

- The reduction from **60 % to 30 %** must be **gradual**.
- It must be driven by **qualified evidence** (see §5), **not** by elapsed time or
  raw message count.
- The prior **never drops below the 30 % floor**. It always retains a residual
  cold-start-style influence, so a sparse or one-sided conversation history cannot
  erase the structural posture entirely.
- The prior **never exceeds 60 %** for an eligible cold-start profile.
- Moon receptivity is **not** part of this 60/40 → 30/70 split. It is applied
  **separately**, afterward, as a bounded temporary modifier (see §6).

**Eligibility for the 60 % cold-start weight** requires a usable birth-derived
structural prior (birth-profile-derived personalization is enabled and a
structural posture could be computed). If birth-derived personalization is
disabled or unavailable, the structural prior contributes **0 %** and the guidance
state is built from explicit preferences, conversation evidence, Moon climate,
and safety only. (Disabling birth-derived personalization is a required user
control — see the privacy doc.)

---

## 4. Progressive dominance of conversation evidence

Per DEC-048(10), **actual observed conversation behavior must progressively become
the dominant source of truth.** Concretely:

- As qualified evidence accumulates, the conversation-evidence contribution rises
  toward its 70 % share while the structural prior settles toward its 30 % floor.
- Where conversation evidence and the structural prior **conflict**, and the
  evidence is qualified and recent, **the evidence wins** (subject to the
  precedence order in §7).
- The structural prior is a **prior**, not a verdict: it seeds behavior before
  evidence exists and is progressively corrected by evidence, never the reverse.

---

## 5. Qualified conversation evidence

**Raw message count is not sufficient** to lower the Guna weight. Only *qualified*
evidence events move the weight. Examples of qualified evidence events:

- explicit statement of interest;
- explicit dislike or boundary;
- repeated enthusiasm for a topic;
- repeated low engagement;
- sustained responses rather than one-word replies;
- repeated topic recurrence across separate conversations;
- acceptance of an AI-generated suggestion;
- rejection or correction of an AI-generated suggestion;
- recurring preference for direct, playful, practical, affectionate, or
  low-pressure wording;
- repeated tension around a topic;
- successful repair after disagreement;
- user correction of an inferred preference.

### 5.1 Inferred-preference record

Each inferred preference should support fields such as:

| Field | Meaning |
|-------|---------|
| `topic_id` | The topic this preference concerns. |
| `relationship_domain` | Versioned domain (see product-requirements §4). |
| `scope` | Privacy scope (`PRIVATE_A` / `PRIVATE_B` / `SHARED`). |
| `source` | Origin of the evidence (chat, feedback, explicit statement). |
| `explicit_or_inferred` | Whether stated explicitly or inferred. |
| `confidence` | Confidence in the preference. |
| `evidence_count` | Number of qualified evidence events. |
| `positive_count` | Count of positive-signal events. |
| `negative_count` | Count of negative-signal events. |
| `last_observed_at` | Recency timestamp. |
| `decay_rate` | How the preference decays without reinforcement. |
| `corrected_by_user` | Whether the user corrected this inference. |
| `provenance_ids` | Links to the source evidence records. |

### 5.2 Evidence precedence within the evidence model

- **Explicit** preferences take precedence over **inferred** preferences.
- **Recent repeated** behavior takes precedence over the **static** Guna-derived
  prior.
- A single event is not "repeated"; qualification thresholds (count/quality) are
  an open question (OQ-AIA-2, OQ-AIA-3).

---

## 6. Moon receptivity as a bounded temporary modifier

- Moon receptivity is applied **separately** from the 60/40 → 30/70 structural
  split, **after** the posture-and-evidence guidance state is formed.
- It is a **bounded** modifier: its maximum magnitude is capped (the exact cap is
  OQ-AIA-4) so it can nudge timing/tone/approachability but cannot dominate the
  guidance state.
- It is **temporary**: each Moon context carries an **expiration timestamp** and
  is **recalculated** after expiry (expiration period is OQ-AIA-5).
- It **may** alter timing or wording; it **must not** invent a dislike, create an
  avoid topic on its own, or claim a person's inner emotional state (see the
  safety language in the privacy/provenance doc).

---

## 7. Recommendation precedence (authoritative order)

When signals conflict, resolve **strictly** in this order (highest wins):

1. **Safety restrictions.**
2. **Explicit user boundary.**
3. **Repeated observed behavior.**
4. **Explicit interest.**
5. **Recent shared-conversation context.**
6. **Current Moon receptivity.**
7. **Guna-derived structural prior.**

### 7.1 Required consequences

- A **favorable Guna pattern must not override an explicit dislike.**
- A **favorable Moon signal must not override a user boundary.**
- **Repeated positive conversation evidence must override a weak static
  mismatch.**
- **Moon climate may alter timing or wording, but must not invent a dislike.**
- **Guna may recommend a lower-pressure posture, but must not suppress a
  repeatedly enjoyed topic.**
- **Private information must not silently influence shared recommendations**
  (private→shared projection requires explicit consent — see the privacy doc).

> **Note on ordering vs. weighting.** The 60/40 → 30/70 split (§3) governs the
> *blend* of the structural prior with preferences/evidence in the normal case.
> The precedence order (§7) governs *conflict resolution*: a higher-precedence
> signal **overrides** rather than merely out-weighing a lower one. Both apply;
> precedence is the tie-breaker and the hard-override mechanism.

---

## 8. Versioning and reversibility

Every component is **independently versioned** so it can be tested, monitored, and
rolled back:

- `structural_relationship_prior_v1`
- `moon_receptivity_context_v1`
- `conversation_evidence_model_v1`
- `ai_assist_guidance_fusion_v1`

Additionally, the **fusion policy** (the weights, the decay behavior, and the
precedence order) is itself versioned (`fusion_policy_version`) and recorded in
provenance for every recommendation (see the privacy/provenance doc). Feature-flag
and rollback strategy is an open question (OQ-AIA-16).

---

## 9. What this document does not decide

The following are **open questions**, tracked in
[`DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md`](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md#open-questions)
and **not** silently resolved here:

- exact mathematical decay curve from 60 % to 30 % (OQ-AIA-1);
- minimum number and quality of evidence events before weight reduction
  (OQ-AIA-2);
- topic-confidence thresholds (OQ-AIA-3);
- maximum Moon modifier magnitude (OQ-AIA-4);
- Moon signal expiration period (OQ-AIA-5);
- inferred-preference retention and deletion periods (OQ-AIA-8).
