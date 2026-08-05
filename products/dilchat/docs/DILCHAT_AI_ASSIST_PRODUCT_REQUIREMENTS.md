# DilChat AI Assist — Product Requirements (V1 direction)

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** Approved (see `DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md`, and
Decision-Log **DEC-048**).

> **Documentation only.** This package captures the founder-approved V1 direction
> for DilChat's future *AI Assist* capability and converts it into an
> implementation-ready requirements set. It **does not** implement chat, AI Assist,
> Guna scoring, Moon-climate calculations, recommendation logic, APIs, database
> models, migrations, mobile screens, or production deployment. Nothing here
> enables a runtime rule pack, changes an existing historical decision, or claims
> classical-authority validation.

## Reading order

| Doc | Purpose |
|-----|---------|
| **This document** | Founder decision, conceptual model, posture taxonomy, topic domains, output categories, example behavior, product disclosure. |
| [`DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md`](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md) | Four versioned components, the signal hierarchy, the 60 %→30 % structural-prior weighting, qualified-evidence rules, and recommendation precedence. |
| [`DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md`](DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md) | The approved chat-overlay UI template and content structure. |
| [`DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md`](DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md) | Data scope, consent, Moon-climate safety language, provenance, auditability. |
| [`DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md`](DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md) | Phase 2 → 3 → 4A–4D sequencing and gating. |
| [`DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md`](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md) | `AIA-*` functional / non-functional / privacy / safety / UX / audit / test requirements and acceptance criteria. |

Related existing docs (unchanged by this package): the canonical
[`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md), the
[authority gate](DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md), the
[Guna founder decisions](DILCHAT_GUNA_FOUNDER_DECISIONS.md), and the
[implementation roadmap](DILCHAT_IMPLEMENTATION_ROADMAP.md).

---

## 1. Founder product decision (V1 direction)

For **DilChat V1**, the founder has approved the following direction. This is a
*new* decision that revises the V1 product direction; it **does not** rewrite or
invalidate any prior historical decision (see §9 and the classical-authority
track in `DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md`).

1. **No external Jyotisha or Sanskrit authority reviewer is required** before the
   internal personalization model may be used. (This is distinct from the
   classical-authority track, which stays blocked — see §9.)
2. The internal Guna Milan pattern-matching logic will remain **proprietary and
   hidden from users**.
3. DilChat will **not expose**:
   - a Guna score out of 36;
   - individual Koota scores;
   - Dosha or Parihara results;
   - classical source tables;
   - internal model weights;
   - any claim that the model is an authoritative or universally accepted
     classical implementation.
4. Guna-derived signals are used as **one internal personalization input**, not as
   a verdict on the relationship.
5. Guna-derived signals have a **strong cold-start role** for new users, when no
   conversation evidence exists yet.
6. As real conversation evidence accumulates, **observed behavior becomes
   increasingly important**.
7. The **current relative Moon movement** to the natal chart supplies a *separate,
   temporary* emotional-receptivity signal — never a claim about actual emotion.
8. Guna and Moon signals must be **composed together**, not treated as competing,
   interchangeable scores.
9. The recommendation engine must **also** use:
   - current conversation context;
   - prior shared conversations;
   - explicit interests;
   - explicit boundaries;
   - inferred topic preferences;
   - reaction to prior suggestions;
   - recurring communication patterns.
10. **Actual observed conversation behavior must progressively become the dominant
    source of truth.**

The formal decision record is **DEC-048** ("V1 hidden Guna structural prior
combined with Moon receptivity and conversation evidence"), recorded in
[`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md) and expanded in
[`DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md`](DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md).

---

## 2. Core conceptual model — four separately versioned components

AI Assist is composed of **four independently versioned components**. Each has its
own version string so it can be tested, monitored, rolled back, and audited
separately. (See `DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md` for how they
combine and `DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md` for how each is
recorded in provenance.)

### A. Structural relationship prior — `structural_relationship_prior_v1`

- **Primary input:** internal Guna Milan pattern-matching features (proprietary,
  hidden).
- **Purpose:** determine the **baseline relational posture** — estimate whether a
  recommendation should be:
  - warmer or more reserved;
  - intimate or low-pressure;
  - direct or gradual;
  - playful or serious;
  - reassuring or spacious;
  - personal or practical.
- **Stability:** relatively **stable** over time.
- **Never** produces a compatibility verdict, score, or claim that the
  relationship is good, bad, successful, or destined to fail.

### B. Moon receptivity context — `moon_receptivity_context_v1`

- **Primary inputs may include:**
  - current sidereal Moon sign;
  - current Nakshatra and pada;
  - current Moon position relative to each natal Moon / natal chart;
  - relevant deterministic timing relationships approved for the product;
  - calculation timestamp and astronomy-model version.
- **Purpose:** estimate **temporary receptivity conditions** — identify subject
  areas that may be easier or harder to approach at that time, and adjust tone,
  timing, intimacy, pressure, and topic approachability.
- **Nature:** **temporary and time-bound**; it expires and is recalculated.
- It **must not** claim direct knowledge of a person's actual emotion. It
  estimates *conversational receptivity*, not inner emotional state. See the
  allowed/prohibited language in
  [`DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md`](DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md).

### C. Conversation evidence model — `conversation_evidence_model_v1`

- **Inputs:**
  - current shared conversation;
  - prior shared conversations;
  - explicit topic interests;
  - explicit dislikes or boundaries;
  - repeated positive engagement;
  - repeated low engagement;
  - disagreement patterns;
  - accepted and rejected AI suggestions;
  - preferred communication style;
  - recency and frequency of evidence.
- **Purpose:** learn what the person has **actually demonstrated**, and override
  incorrect static assumptions as evidence accumulates.

### D. Guidance fusion layer — `ai_assist_guidance_fusion_v1`

- **Purpose:** combine the structural posture, current topic receptivity,
  conversation evidence, explicit preferences, and safety/privacy constraints into
  a single **user-reviewable conversation guidance** state.
- The **LLM may generate wording only after** the deterministic and evidence-based
  context has been assembled. The LLM writes *language*; it does not decide the
  guidance state.

> **Conceptual separation of questions each component answers**
> - **Guna** (structural prior): *"How should this person be approached within
>   this relationship?"*
> - **Moon** (receptivity context): *"What areas may be more or less receptive at
>   the present time?"*
> - **Conversation evidence:** *"What has this person actually demonstrated?"*

---

## 3. Structural posture taxonomy (internal)

The structural model resolves to one of the following internal posture states.
These are **internal** labels; they are never shown to users as a rating.

- `OPEN_AND_WARM`
- `GENTLY_PERSONAL`
- `NEUTRAL_AND_CURIOUS`
- `PRACTICAL_AND_LIGHT`
- `LOW_PRESSURE`
- `ALLOW_SPACE`

**Wording rule:** never use "distant" (or similar deficit language) as
user-facing wording. `ALLOW_SPACE` is the internal name for the most reserved
posture; user-facing copy uses supportive phrasing (see the overlay spec).

The structural model **may influence**:

- degree of intimacy;
- depth of personal disclosure;
- directness;
- emotional intensity;
- pacing;
- question style;
- amount of pressure;
- whether practical or emotional framing is preferable.

The structural model **must not** determine whether the relationship is good,
bad, successful, or destined to fail.

---

## 4. Topic-domain taxonomy (versioned)

DilChat defines a **versioned** topic-domain taxonomy. Ownership of the taxonomy
and its version cadence is an open question (see
[open questions](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md#open-questions), OQ-AIA-6).

**Initial domains (V1 candidate set):**

- affection and intimacy;
- rest and wellbeing;
- family and home;
- money and security;
- career and ambition;
- travel and adventure;
- social connection;
- conflict and repair;
- future planning;
- play and humor;
- spirituality and meaning;
- personal space;
- everyday logistics;
- shared memories;
- learning and interests.

For each **candidate topic**, the system should be able to represent:

| Field | Meaning |
|-------|---------|
| `topic` | The concrete topic under consideration. |
| `relationship_domain` | One of the versioned domains above. |
| `structural_posture` | The posture the structural prior suggests for this person. |
| `current_receptivity` | The temporary Moon-derived climate for this domain. |
| `observed_interest` | Interest inferred/observed from conversation evidence. |
| `explicit_preference` | An explicit like/dislike/boundary if stated. |
| `confidence` | Confidence in the topic recommendation. |
| `evidence_count` | Count of qualified evidence events supporting it. |
| `recommended_approach` | Good / gently / space / avoid + tone guidance. |
| `provenance` | Structured provenance categories (see privacy/provenance doc). |
| `expiration_or_decay` | When temporary/climate signals expire or decay. |
| `safety_or_boundary_status` | Whether a safety or boundary rule applies. |

---

## 5. Signal composition (summary)

Guna and Moon must **not** be collapsed into one undifferentiated weighted
average. The full model, weights, and precedence live in
[`DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md`](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md).
In brief:

1. The **Guna-derived** model determines the **baseline relational posture**.
2. **Conversation history** progressively modifies and may **override** that
   posture.
3. The **Moon** model determines **current topic receptivity** and communication
   climate.
4. **Explicit preferences and boundaries override both** Guna and Moon.
5. **Safety policies override every** personalization signal.
6. The **LLM** converts the resulting guidance state into natural-language
   suggestions.

Structural-prior weighting (conceptual): **60 %** at eligible cold start,
declining to a **30 % floor** as *qualified* conversation evidence accumulates —
gradually, and never on elapsed time or raw message count alone. An illustrative
finer split of the remaining share is 25 %/15 % (explicit preferences / early
evidence) at cold start moving to 20 %/50 % at maturity — see
[fusion §3](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md#3-structural-prior-weighting-60--30).
Moon receptivity is applied **separately** as a **bounded, temporary modifier**
(`TopicReceptivity = baseline_topic_affinity × moon_climate_modifier`, proposed
initial bound 0.80–1.20) and never replaces the Guna signal.

---

## 6. AI Assist output categories

The AI Assist overlay should eventually support these categories. The overlay
layout is specified in
[`DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md`](DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md).

### A. Good Topics
Topics with positive current-conversation evidence, known or inferred interest, a
suitable structural posture, and sufficient present receptivity.

### B. Approach Gently
Topics that may be valid but require softer wording, less pressure, reduced
intimacy, careful timing, or acknowledgement of sensitivity.

### C. Give Space
Used when the present communication climate supports lower pressure, fewer
questions, practical rather than emotional wording, and allowing the partner time
to respond.

### D. Avoid Topics *(used conservatively)*
A topic may enter **Avoid Topics** *only* because of:

- an explicit user boundary;
- repeated strong negative behavioral evidence;
- an active unresolved conflict involving that subject;
- a safety restriction.

**Guna or Moon signals alone must never classify a topic as "Avoid."** When no
supported avoid-topic evidence exists, the UI states:

> "No clear topic to avoid from this conversation."

Do **not** generate an avoid topic merely to fill the interface.

> **Open naming question (OQ-AIA-17):** whether "Avoid Topics" remains in V1 or is
> renamed "Approach Carefully." Not decided here.

---

## 7. Example recommendation behavior

When the partner says:

> "We went hiking in the hills. Views were amazing!"

**Strong direct conversation evidence already exists.** A valid recommendation may
be:

> "That sounds beautiful. What was your favorite part of the trail?"

The system **should not** rely on Guna or Moon to override this direct evidence.

A **deeper** question such as:

> "Did the experience make you think differently about your life?"

should be suggested **only when**:

- the structural posture supports personal depth;
- the current Moon receptivity supports reflective discussion;
- prior conversation evidence shows that deeper questions are welcomed.

The recommendation engine must **distinguish** and record which of these produced
a suggestion:

- direct conversation evidence;
- historical preference;
- inferred preference;
- Guna-derived structural signal;
- Moon-derived receptivity;
- LLM-generated wording.

---

## 8. Product disclosure

The internal logic may remain proprietary and hidden, but the product **should
disclose the broad categories** of personalization. Recommended disclosure copy:

> "DilChat may personalize conversation suggestions using shared conversation
> patterns, stated preferences, interaction feedback, optional birth-profile
> patterns, and current astrological timing signals."

DilChat must **not** present:

- an authoritative Guna score;
- a scientific-validation claim;
- a guarantee of emotional receptivity;
- a guarantee of relationship success;
- any hidden claim that classical-authority review has been completed.

---

## 9. Relationship to the existing Guna authority track

This V1 direction runs on a **separate track** from the classical
source-validation work. The historical status of that work is **preserved
unchanged**; this package does not mark it validated.

**A. Classical authority track** (unchanged, still blocked)
- exact source acquisition; textual traceability; expert review; optional future
  user-visible classical report;
- **remains blocked** unless separately resumed
  (`GUNA_AUTHORITY_VALIDATION_BLOCKED`, `RULE_PACK_BLOCKED`; see the authority gate
  and DEC-042…DEC-047).

**B. V1 proprietary personalization track** (this package)
- uses internal Guna-derived pattern features;
- does **not** expose the classical score;
- does **not** claim authoritative classical validation;
- may proceed as a **founder-approved experimental personalization prior**;
- must be **versioned, tested, monitored, and reversible**.

**Status constants introduced by this package (documentation status, not runtime
enablement):**

| Status | Meaning |
|--------|---------|
| `CLASSICAL_GUNA_AUTHORITY_VALIDATION_BLOCKED` | Classical authority track stays blocked (unchanged). |
| `CLASSICAL_RULE_PACK_NON_EXECUTABLE` | The classical rule pack stays non-executable (unchanged). |
| `HEURISTIC_GUNA_STRUCTURAL_PRIOR_V1_APPROVED_FOR_REQUIREMENTS` | The V1 structural prior is approved **for requirements documentation**, not for runtime. |
| `USER_VISIBLE_GUNA_SCORE_DISABLED` | No user-visible Guna score is approved. |

**No existing runtime rule pack is enabled by this task.**

---

## 10. Explicit non-goals of this package

- No chat, AI Assist, Guna scoring, Moon calculation, recommendation logic, API,
  database model, migration, or mobile screen is implemented.
- No runtime rule pack is enabled; `pack_control.json` and its fail-closed
  invariant are untouched.
- No classical source text is added; no edition is frozen.
- No historical decision is rewritten; DEC-048 is **added** as the new V1
  direction alongside the preserved classical-authority record.
