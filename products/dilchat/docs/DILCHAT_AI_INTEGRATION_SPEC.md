# DilChat — AI Integration Specification

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Owning module:** `ai_guidance` (see DILCHAT_DECISION_LOG.md §0, DEC-014)
**Status of this document:** Design phase. No production code has been written.
**Canonical provenance:** `prompt_pack_version = dilchat_prompts_v1`

> This specification is subordinate to `DILCHAT_DECISION_LOG.md`. Where this
> document names a module, version string, scope, or technology, the value is
> authoritative because the decision log fixed it (DEC-001 … DEC-021). This
> document does **not** re-decide those; it specifies **how the AI layer behaves**
> within them.

> **Labeling convention used throughout.** Every substantive statement is tagged
> so reviewers can route it:
> **[Traditional Vedic rule]** — a classical rule the deterministic engine encodes;
> **[DilChat interpretation]** — a proprietary DilChat mapping/opinion, never a
> classical claim;
> **[Technical]** — an engineering decision;
> **[Safety]** — a guardrail;
> **[Requires legal review]** / **[Requires domain review]** — an open dependency.

---

## Table of contents

1. Role of AI & the deterministic/LLM boundary
2. Allowed AI tasks (input/output JSON Schemas + examples)
3. Prohibited tasks (detection + refusal)
4. Context minimization — the ContextBuilder
5. Structured output & validation pipeline
6. Hallucination containment
7. Prompt-versioning strategy
8. Content moderation & safety
9. Privacy controls
10. Human approval requirements
11. Failure modes & degradation
12. Appendix A — shared schema fragments
13. Appendix B — error codes

---

## 1. Role of AI in DilChat & the deterministic/LLM boundary

### 1.1 What the AI layer is for

DilChat's astronomy, classical compatibility, and daily-climate numbers are
produced by **deterministic, versioned services** (`astrology`, `guna_milan`,
`moon_transits`, and the interest/living models — DEC-007, DEC-009, DEC-019).
These services are the **single source of numeric truth**.

The AI layer (`ai_guidance`, DEC-014) exists to do exactly one class of work:
**turn already-computed, governed, structured data into humane, well-scoped
natural language** — explanations, gentle conversation scaffolding, neutral
summaries, and structured drafts that a human must approve. It is a *translator
and facilitator*, never a *calculator* and never an *oracle*.

> **[DilChat interpretation]** The product opinion is that couples do not need
> another number; they need help *talking*. The AI's job is communication
> scaffolding on top of governed facts — not divination.

### 1.2 The hard boundary (invariant)

> **INVARIANT AI-1 (no recomputation).** The AI layer MUST NOT calculate,
> re-derive, adjust, round, re-weight, or "correct" any planetary position,
> nakshatra, pada, rashi, Koota value, Guna Milan total, transit score, interest
> score, or living-compatibility score. Every such number reaching the AI is an
> **input it may cite but never mutate**. **[Technical][Traditional Vedic rule]**

> **INVARIANT AI-2 (explain, never alter).** The AI **may EXPLAIN a Guna Milan
> score** — what a Koota measures, what a given raw value tends to mean for
> day-to-day conversation — but it **must never recalculate or alter it**, and
> must never present its explanation as if it changed the score. The number in
> the explanation is copied verbatim from the deterministic input and cited by
> field name. **[Traditional Vedic rule][Safety]**

### 1.3 Value → producer table

| Value / artifact | Produced by (authoritative) | AI role |
|---|---|---|
| Planetary/Moon longitude, ascendant | `astrology` (Swiss Ephemeris / Moshier, DEC-007) | none — never computed by AI |
| Nakshatra, pada, rashi assignment | `astrology` | none — never computed by AI |
| Individual Koota raw scores (Varna, Vashya, Tara, Yoni, Graha Maitri, Gana, Bhakoot, Nadi) | `guna_milan` (`ashtakoota_lahiri_classical_v1`, DEC-009) | **EXPLAIN only** (task `explain_guna_component`) |
| Ashtakoota total (0–36) | `guna_milan` | **EXPLAIN only** — never re-summed |
| Daily transit features / phase | `moon_transits` (`dilchat_transit_v1`, DEC-019) | consume as input to `daily_climate_summary` |
| Daily emotional/interest climate scores (12 interests) | `dilchat_interest_v1` | consume as input; may rank/label themes |
| Living-compatibility aggregate | `dilchat_living_v1` | consume as jointly-visible aggregate only (OQ-9) |
| Nakshatra/Koota → domain wording mappings | `interpretation` pack (`dilchat_interp_v1`) | consume as input; AI phrases, does not invent |
| Plain-language explanation of a score | **AI** (`ai_guidance`) | **produces** |
| Conversation preview / opener / FFANR split | **AI** | **produces** |
| Compromise options, mutual-understanding summary | **AI** (human-approved) | **produces draft** |
| Agreement draft | **AI** (dual-approved) | **produces draft** |
| Consent to share private → shared | `consent` module (DEC-013) | never bypassed by AI |
| Crisis / abuse resource routing | `ai_guidance` safety layer + human/crisis referral | surfaces resources, never diagnoses |

Anything in the left column that is a **number or a classical assignment** is
frozen before it reaches AI. Anything the AI "produces" is **language about**
those frozen facts, schema-validated and provenance-stamped.

---

## 2. Allowed AI tasks

Each allowed task has: a stable `task` name, a **strict input JSON Schema**, a
**strict output JSON Schema** (JSON Schema draft 2020-12), an example, and an
autonomy level (see §10). All schemas below set `"additionalProperties": false`
at the top level and on nested objects unless noted — unknown fields are a
validation failure, not silently ignored.

**Shared output requirement.** *Every* task output object MUST include the three
required fields defined once in Appendix A and referenced here:

- `provenance` — who/what/which-version produced it (Appendix A.1);
- `disclaimers` — array of standing disclaimers applicable to the output (A.2);
- `safety` — the safety object (flags, crisis_resources, escalate) (A.3, §8).

For brevity, task output schemas below use `$ref` to the Appendix A definitions
rather than re-inlining them. The `$defs` are considered bundled into every task
schema at validation time.

### 2.1 `explain_guna_component`

**Purpose.** Explain ONE Ashtakoota Koota's already-computed score in plain
language, and say what it tends to mean for day-to-day conversation. **EXPLAIN
only — never recompute (INVARIANT AI-2).**
**Autonomy:** suggest-only.
**Scope:** `SHARED` (Guna Milan is couple-level classical data, already
consent-appropriate to both partners).

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:explain_guna_component:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "component", "raw_score", "max_score",
               "classifications", "rule_provenance"],
  "properties": {
    "task": { "const": "explain_guna_component" },
    "component": {
      "type": "string",
      "enum": ["varna", "vashya", "tara", "yoni",
               "graha_maitri", "gana", "bhakoot", "nadi"]
    },
    "raw_score": { "type": "number", "minimum": 0 },
    "max_score": { "type": "number", "exclusiveMinimum": 0 },
    "classifications": {
      "type": "object",
      "description": "Deterministic labels the guna_milan module already assigned. AI copies, never derives.",
      "additionalProperties": false,
      "properties": {
        "seeker_label": { "type": "string" },
        "partner_label": { "type": "string" },
        "relation_label": { "type": "string" },
        "flag": { "type": "string", "enum": ["ok", "caution", "dosha_present"] }
      },
      "required": ["flag"]
    },
    "rule_provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["rule_pack_id", "ayanamsa", "zodiac"],
      "properties": {
        "rule_pack_id": { "const": "ashtakoota_lahiri_classical_v1" },
        "ayanamsa": { "const": "lahiri" },
        "zodiac": { "const": "sidereal" },
        "source_citation": { "type": "string" }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:explain_guna_component:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "component", "cited_score", "cited_max",
               "explanation", "what_it_means_for_conversation",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "component": { "type": "string" },
    "cited_score": {
      "type": "number",
      "description": "MUST equal input.raw_score exactly. Post-filter rejects mismatch."
    },
    "cited_max": { "type": "number" },
    "explanation": { "type": "string", "minLength": 1, "maxLength": 900 },
    "what_it_means_for_conversation": {
      "type": "string", "minLength": 1, "maxLength": 700
    },
    "traditional_vs_dilchat": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "traditional_rule": { "type": "string" },
        "dilchat_reading": { "type": "string" }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

#### Example input

```json
{
  "task": "explain_guna_component",
  "component": "nadi",
  "raw_score": 0,
  "max_score": 8,
  "classifications": {
    "seeker_label": "aadi",
    "partner_label": "aadi",
    "relation_label": "same_nadi",
    "flag": "dosha_present"
  },
  "rule_provenance": {
    "rule_pack_id": "ashtakoota_lahiri_classical_v1",
    "ayanamsa": "lahiri",
    "zodiac": "sidereal",
    "source_citation": "OQ-1 pending domain sign-off"
  }
}
```

#### Example output

```json
{
  "kind": "dilchat_interpretation",
  "component": "nadi",
  "cited_score": 0,
  "cited_max": 8,
  "explanation": "The app calculated Nadi at 0 of 8 because both charts fall in the same Nadi group (Aadi). In the classical Ashtakoota system, matching Nadi is treated as a caution point (a 'dosha') and scores zero.",
  "what_it_means_for_conversation": "This is a traditional flag, not a verdict about your relationship. It can be a useful prompt to talk about long-term wellbeing and lifestyle habits as a team — nothing more specific than that.",
  "traditional_vs_dilchat": {
    "traditional_rule": "[Traditional Vedic rule] Same Nadi scores 0/8 and is classically noted as Nadi dosha.",
    "dilchat_reading": "[DilChat interpretation] DilChat treats this only as a conversation starter about shared habits; it is never health, fertility, or medical guidance (DEC-021)."
  },
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1",
    "task": "explain_guna_component",
    "provider": "anthropic",
    "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T09:12:00Z",
    "input_fields_cited": ["raw_score", "max_score", "classifications.flag"],
    "computed_by_deterministic_service": true
  },
  "disclaimers": [
    "Astrology guidance only; not medical, psychiatric, fertility, legal, or financial advice (DEC-021).",
    "The compatibility number was computed by DilChat's astrology engine, not by AI. AI only explained it."
  ],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

> **[Safety]** Note the Nadi example deliberately routes away from medical/fertility
> language per DEC-021. The post-filter (§8) blocks Nadi explanations that use
> health/fertility/genetic vocabulary regardless of what the model returns.

### 2.2 `daily_climate_summary`

**Purpose.** Summarize ONE user's `DailyPersonalProfile` features plus their 12
interest scores into a short, gentle daily read.
**Autonomy:** suggest-only.
**Scope:** `PRIVATE_A` **or** `PRIVATE_B` — a user's own daily profile only.
Never blended with the partner's private profile.

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:daily_climate_summary:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "profile", "interest_scores", "model_provenance"],
  "properties": {
    "task": { "const": "daily_climate_summary" },
    "profile": {
      "type": "object",
      "additionalProperties": false,
      "required": ["local_date", "moon_house", "phase", "features"],
      "properties": {
        "local_date": { "type": "string", "format": "date" },
        "moon_house": { "type": "integer", "minimum": 1, "maximum": 12 },
        "phase": { "type": "string" },
        "features": {
          "type": "object",
          "description": "Named scalar features in [0,1] from dilchat_transit_v1. No raw coordinates permitted.",
          "additionalProperties": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "interest_scores": { "$ref": "dilchat:ai:defs#/$defs/interest_scores_12" },
    "model_provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["transit_model_version", "interest_model_version"],
      "properties": {
        "transit_model_version": { "const": "dilchat_transit_v1" },
        "interest_model_version": { "const": "dilchat_interest_v1" }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:daily_climate_summary:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "summary", "top_themes", "gentle_suggestion",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "summary": { "type": "string", "minLength": 1, "maxLength": 500 },
    "top_themes": {
      "type": "array", "minItems": 1, "maxItems": 3,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["theme", "score"],
        "properties": {
          "theme": { "type": "string" },
          "score": { "type": "number", "minimum": 0, "maximum": 1 }
        }
      }
    },
    "gentle_suggestion": { "type": "string", "minLength": 1, "maxLength": 280 },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

#### Example input

```json
{
  "task": "daily_climate_summary",
  "profile": {
    "local_date": "2026-08-04",
    "moon_house": 4,
    "phase": "waxing_gibbous",
    "features": { "emotional_intensity": 0.72, "restlessness": 0.31, "warmth": 0.66 }
  },
  "interest_scores": {
    "connection": 0.81, "rest": 0.55, "adventure": 0.22, "home": 0.74,
    "creativity": 0.40, "learning": 0.33, "finances": 0.18, "health": 0.29,
    "family": 0.63, "intimacy": 0.58, "work": 0.35, "spirituality": 0.47
  },
  "model_provenance": {
    "transit_model_version": "dilchat_transit_v1",
    "interest_model_version": "dilchat_interest_v1"
  }
}
```

#### Example output

```json
{
  "kind": "dilchat_interpretation",
  "summary": "Today reads as an inward, home-leaning day for you — DilChat's model shows higher emotional warmth and a pull toward connection and domestic comfort, with adventure and money matters low on your radar.",
  "top_themes": [
    { "theme": "connection", "score": 0.81 },
    { "theme": "home", "score": 0.74 },
    { "theme": "family", "score": 0.63 }
  ],
  "gentle_suggestion": "If it fits your day, a slow evening at home together may land well right now.",
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1",
    "task": "daily_climate_summary",
    "provider": "anthropic",
    "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T06:30:00Z",
    "input_fields_cited": ["interest_scores.connection", "interest_scores.home",
                           "interest_scores.family", "profile.features.warmth"],
    "computed_by_deterministic_service": true
  },
  "disclaimers": [
    "This is DilChat's daily-climate model (dilchat_transit_v1), not a classical prediction and not a forecast of events."
  ],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.3 `likely_attention_themes`

**Purpose.** From the 12 interest scores, produce a ranked, confidence-tagged
list of themes a person may be leaning toward.
**Autonomy:** suggest-only.
**Scope:** `PRIVATE_A` or `PRIVATE_B` (own interest vector only).

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:likely_attention_themes:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "interest_scores", "model_provenance"],
  "properties": {
    "task": { "const": "likely_attention_themes" },
    "interest_scores": { "$ref": "dilchat:ai:defs#/$defs/interest_scores_12" },
    "model_provenance": {
      "type": "object",
      "additionalProperties": false,
      "required": ["interest_model_version"],
      "properties": {
        "interest_model_version": { "const": "dilchat_interest_v1" }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:likely_attention_themes:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "ranked_themes", "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "ranked_themes": {
      "type": "array", "minItems": 1, "maxItems": 12,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["theme", "cited_score", "confidence"],
        "properties": {
          "theme": { "type": "string" },
          "cited_score": { "type": "number", "minimum": 0, "maximum": 1 },
          "confidence": { "type": "string", "enum": ["low", "medium", "high"] }
        }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[Technical]** Ranking must be a stable sort by `cited_score` descending; the
> post-filter recomputes the ordering from `cited_score` and rejects any output
> whose order disagrees. `confidence` is banded by score spread: ties within
> 0.05 are demoted to `low`. This keeps the AI from inventing a false precision.

#### Example output (abbreviated)

```json
{
  "kind": "dilchat_interpretation",
  "ranked_themes": [
    { "theme": "connection", "cited_score": 0.81, "confidence": "high" },
    { "theme": "home", "cited_score": 0.74, "confidence": "medium" },
    { "theme": "family", "cited_score": 0.63, "confidence": "medium" }
  ],
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "likely_attention_themes",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T06:31:00Z",
    "input_fields_cited": ["interest_scores.*"], "computed_by_deterministic_service": true
  },
  "disclaimers": ["Themes reflect DilChat's interest model, not a prediction of behavior."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.4 `conversation_preview`

**Purpose.** Given a topic and **only the mutually consented SHARED context**,
tell a couple what to expect, tone tips, and pitfalls before they talk.
**Autonomy:** suggest-only.
**Scope:** `SHARED` **only** — the ContextBuilder (§4) refuses to populate this
task from any `PRIVATE_*` source. Never one partner's private data.

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:conversation_preview:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "topic", "shared_context", "consent_ref"],
  "properties": {
    "task": { "const": "conversation_preview" },
    "topic": { "type": "string", "minLength": 1, "maxLength": 200 },
    "shared_context": {
      "type": "object",
      "additionalProperties": false,
      "description": "SHARED-scope only. Both partners' consented context, symmetric.",
      "properties": {
        "shared_climate": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "partner_a_top_themes": { "type": "array", "items": { "type": "string" }, "maxItems": 3 },
            "partner_b_top_themes": { "type": "array", "items": { "type": "string" }, "maxItems": 3 }
          }
        },
        "shared_guna_flags": {
          "type": "array",
          "items": { "type": "string", "enum": ["ok", "caution", "dosha_present"] }
        }
      }
    },
    "consent_ref": {
      "type": "object",
      "additionalProperties": false,
      "required": ["consent_event_id", "both_consented"],
      "properties": {
        "consent_event_id": { "type": "string" },
        "both_consented": { "const": true }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:conversation_preview:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "what_to_expect", "tone_tips", "pitfalls",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "what_to_expect": { "type": "string", "minLength": 1, "maxLength": 600 },
    "tone_tips": {
      "type": "array", "minItems": 1, "maxItems": 5,
      "items": { "type": "string", "maxLength": 200 }
    },
    "pitfalls": {
      "type": "array", "minItems": 1, "maxItems": 5,
      "items": { "type": "string", "maxLength": 200 }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

#### Example input/output (abbreviated)

```json
{
  "task": "conversation_preview",
  "topic": "how we split weekends",
  "shared_context": {
    "shared_climate": {
      "partner_a_top_themes": ["home", "rest"],
      "partner_b_top_themes": ["adventure", "connection"]
    },
    "shared_guna_flags": ["ok", "caution"]
  },
  "consent_ref": { "consent_event_id": "cev_8812", "both_consented": true }
}
```

```json
{
  "kind": "dilchat_interpretation",
  "what_to_expect": "You two may be pulling in slightly different directions this week — one of you toward rest at home, the other toward getting out and doing something together. That is a difference in preference, not a conflict.",
  "tone_tips": ["Name what you each want before proposing a plan.",
                "Assume good intent — this is about energy, not rejection."],
  "pitfalls": ["Framing 'stay in' vs 'go out' as a win/lose choice.",
               "Reading low energy as low interest in the relationship."],
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "conversation_preview",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T07:00:00Z",
    "input_fields_cited": ["shared_context.shared_climate"],
    "computed_by_deterministic_service": true
  },
  "disclaimers": ["Based only on context you both chose to share."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.5 `gentle_opener`

**Purpose.** Offer 1–3 non-manipulative ways to open a conversation.
**Autonomy:** suggest-only. **Scope:** `SHARED`, or the requesting user's own
`PRIVATE_*` (an opener the user drafts for themselves; never sent automatically).

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:gentle_opener:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "topic", "scope"],
  "properties": {
    "task": { "const": "gentle_opener" },
    "topic": { "type": "string", "minLength": 1, "maxLength": 200 },
    "scope": { "type": "string", "enum": ["PRIVATE_A", "PRIVATE_B", "SHARED"] },
    "desired_tone": {
      "type": "string",
      "enum": ["warm", "neutral", "playful", "repair"],
      "default": "warm"
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:gentle_opener:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "openers", "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "openers": {
      "type": "array", "minItems": 1, "maxItems": 3,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["text", "why_it_is_gentle"],
        "properties": {
          "text": { "type": "string", "minLength": 1, "maxLength": 300 },
          "why_it_is_gentle": { "type": "string", "maxLength": 200 }
        }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[Safety]** The output post-filter runs a **manipulation classifier** over
> `openers[].text`: guilt-tripping, ultimatums, coercion, love-bombing framing,
> or any opener that implies leverage is rejected as `AI_SAFETY_BLOCKED`.
> "Non-manipulative" is not a stylistic hope — it is enforced.

#### Example output

```json
{
  "kind": "dilchat_interpretation",
  "openers": [
    { "text": "I've been thinking about how we do weekends and I'd love to hear what you'd want an ideal one to look like. Can we talk about it?",
      "why_it_is_gentle": "Invites their view first; no demand or blame." },
    { "text": "No agenda — I just want to understand what recharges you lately.",
      "why_it_is_gentle": "Curiosity-led, lowers defensiveness." }
  ],
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "gentle_opener",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T07:05:00Z",
    "input_fields_cited": ["topic"], "computed_by_deterministic_service": false
  },
  "disclaimers": ["Suggestions only; you choose whether and how to say anything."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.6 `ffanr_separation`

**Purpose.** Take ONE user's own private message and separate it into **Facts /
Feelings / Assumptions / Needs / Requests** to help them see their own message
clearly before deciding what (if anything) to share.
**Autonomy:** suggest-only.
**Scope:** the requesting user's own `PRIVATE_A` or `PRIVATE_B` **only**. Output
stays in that private scope. The result is **never** auto-shown to the partner or
posted to `SHARED` — surfacing it requires a `consent` ConsentEvent (DEC-013).

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:ffanr_separation:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "scope", "message"],
  "properties": {
    "task": { "const": "ffanr_separation" },
    "scope": { "type": "string", "enum": ["PRIVATE_A", "PRIVATE_B"] },
    "message": { "type": "string", "minLength": 1, "maxLength": 4000 }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:ffanr_separation:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "facts", "feelings", "assumptions", "needs", "requests",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "facts":       { "type": "array", "items": { "type": "string", "maxLength": 300 } },
    "feelings":    { "type": "array", "items": { "type": "string", "maxLength": 300 } },
    "assumptions": { "type": "array", "items": { "type": "string", "maxLength": 300 } },
    "needs":       { "type": "array", "items": { "type": "string", "maxLength": 300 } },
    "requests":    { "type": "array", "items": { "type": "string", "maxLength": 300 } },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[Safety]** `assumptions` must be phrased as the *author's* assumptions
> ("I'm assuming that…"), never as asserted facts about the partner's motives.
> The post-filter rejects any `assumptions[]` entry phrased as a claim about the
> partner's intent (guards the prohibited "motive-mind-reading" task, §3).

#### Example input/output

```json
{
  "task": "ffanr_separation",
  "scope": "PRIVATE_A",
  "message": "You never text me back during the day and I feel like work matters more to you than I do. I need to feel prioritized. Can you just send one message at lunch?"
}
```

```json
{
  "kind": "dilchat_interpretation",
  "facts": ["Messages sent during the workday often are not answered until evening."],
  "feelings": ["Hurt", "Lonely during the day"],
  "assumptions": ["I'm assuming the delay means work is more important to you than I am — I don't actually know that."],
  "needs": ["To feel prioritized and thought of during the day."],
  "requests": ["Would you be willing to send one short message around lunch?"],
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "ffanr_separation",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T07:20:00Z",
    "input_fields_cited": ["message"], "computed_by_deterministic_service": false
  },
  "disclaimers": ["This stays private to you. Nothing is shared with your partner unless you choose to share it."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.7 `compromise_options`

**Purpose.** Given **both partners' stated needs from SHARED scope**, propose
2–4 balanced options with tradeoffs.
**Autonomy:** suggest-only (options are proposals; adopting one is a human act).
**Scope:** `SHARED` only — both needs must already be consented to shared scope.

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:compromise_options:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "partner_a_need", "partner_b_need", "consent_ref"],
  "properties": {
    "task": { "const": "compromise_options" },
    "partner_a_need": { "type": "string", "minLength": 1, "maxLength": 600 },
    "partner_b_need": { "type": "string", "minLength": 1, "maxLength": 600 },
    "constraints": {
      "type": "array", "items": { "type": "string", "maxLength": 200 }, "maxItems": 6
    },
    "consent_ref": {
      "type": "object",
      "additionalProperties": false,
      "required": ["consent_event_id", "both_consented"],
      "properties": {
        "consent_event_id": { "type": "string" },
        "both_consented": { "const": true }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:compromise_options:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "options", "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "dilchat_interpretation" },
    "options": {
      "type": "array", "minItems": 2, "maxItems": 4,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["label", "description", "serves_a", "serves_b", "tradeoffs"],
        "properties": {
          "label": { "type": "string", "maxLength": 80 },
          "description": { "type": "string", "maxLength": 400 },
          "serves_a": { "type": "string", "maxLength": 200 },
          "serves_b": { "type": "string", "maxLength": 200 },
          "tradeoffs": {
            "type": "array", "minItems": 1, "maxItems": 4,
            "items": { "type": "string", "maxLength": 200 }
          }
        }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[DilChat interpretation]** Balance requirement: every option MUST address both
> `serves_a` and `serves_b` non-trivially. The post-filter rejects an option set
> where any option leaves one partner's need entirely unserved AND no other option
> compensates — DilChat does not surface one-sided "compromises."

#### Example output (abbreviated)

```json
{
  "kind": "dilchat_interpretation",
  "options": [
    { "label": "Alternate weekends",
      "description": "One weekend leans restful-at-home, the next leans out-and-active, chosen in advance.",
      "serves_a": "Guaranteed recovery weekends.",
      "serves_b": "Guaranteed shared outings.",
      "tradeoffs": ["Less spontaneity", "Requires planning ahead"] },
    { "label": "Split the day",
      "description": "Quiet mornings at home, one outing in the afternoon.",
      "serves_a": "Protected downtime.",
      "serves_b": "Still gets an activity together.",
      "tradeoffs": ["Neither gets a full day of their preference"] }
  ],
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "compromise_options",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T07:40:00Z",
    "input_fields_cited": ["partner_a_need", "partner_b_need"],
    "computed_by_deterministic_service": false
  },
  "disclaimers": ["Options are starting points, not recommendations about who is right."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.8 `summarize_mutual_understanding`

**Purpose.** Produce a **neutral shared summary** of where the couple currently
agrees/differs — a **candidate `SharedArtifact`**, NOT auto-posted.
**Autonomy:** human-approve (author review before it becomes a SharedArtifact —
OQ-8).
**Scope:** `SHARED`.

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:summarize_mutual_understanding:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "shared_points", "consent_ref"],
  "properties": {
    "task": { "const": "summarize_mutual_understanding" },
    "shared_points": {
      "type": "array", "minItems": 1, "maxItems": 40,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["text", "origin"],
        "properties": {
          "text": { "type": "string", "maxLength": 500 },
          "origin": { "type": "string", "enum": ["a", "b", "both"] }
        }
      }
    },
    "consent_ref": {
      "type": "object", "additionalProperties": false,
      "required": ["consent_event_id", "both_consented"],
      "properties": {
        "consent_event_id": { "type": "string" },
        "both_consented": { "const": true }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:summarize_mutual_understanding:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "candidate_artifact", "requires_author_review",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "candidate_shared_artifact" },
    "requires_author_review": { "const": true },
    "candidate_artifact": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "agreements", "differences", "open_questions"],
      "properties": {
        "title": { "type": "string", "maxLength": 120 },
        "agreements":     { "type": "array", "items": { "type": "string", "maxLength": 300 } },
        "differences":    { "type": "array", "items": { "type": "string", "maxLength": 300 } },
        "open_questions": { "type": "array", "items": { "type": "string", "maxLength": 300 } }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[Technical][Safety]** `requires_author_review` is a `const: true` in the
> schema so the artifact **cannot** be represented as pre-approved. The
> `shared_chat` module refuses to persist a SharedArtifact whose source AI output
> lacks a subsequent author-approval ConsentEvent. Neutrality is checked by the
> output moderator: the summary must attribute each point to `a`/`b`/`both` and
> must not adjudicate correctness.

#### Example output (abbreviated)

```json
{
  "kind": "candidate_shared_artifact",
  "requires_author_review": true,
  "candidate_artifact": {
    "title": "Where we are on weekends",
    "agreements": ["We both want weekends to feel like 'us' time."],
    "differences": ["A leans toward rest at home; B leans toward going out."],
    "open_questions": ["How do we handle a weekend when one of us is exhausted?"]
  },
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "summarize_mutual_understanding",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T08:00:00Z",
    "input_fields_cited": ["shared_points"], "computed_by_deterministic_service": false
  },
  "disclaimers": ["Draft summary for your review. It becomes shared only after you approve it."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.9 `draft_agreement`

**Purpose.** Produce a **structured agreement draft** for **DUAL approval** —
never auto-approved, never binding, routed through the `agreements` module.
**Autonomy:** dual-approve (both partners must approve — OQ-8).
**Scope:** `SHARED`.

#### Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:draft_agreement:input:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["task", "topic", "agreed_points", "consent_ref"],
  "properties": {
    "task": { "const": "draft_agreement" },
    "topic": { "type": "string", "minLength": 1, "maxLength": 200 },
    "agreed_points": {
      "type": "array", "minItems": 1, "maxItems": 30,
      "items": { "type": "string", "maxLength": 400 }
    },
    "consent_ref": {
      "type": "object", "additionalProperties": false,
      "required": ["consent_event_id", "both_consented"],
      "properties": {
        "consent_event_id": { "type": "string" },
        "both_consented": { "const": true }
      }
    }
  }
}
```

#### Output schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "dilchat:ai:draft_agreement:output:v1",
  "type": "object",
  "additionalProperties": false,
  "required": ["kind", "requires_dual_approval", "draft",
               "provenance", "disclaimers", "safety"],
  "properties": {
    "kind": { "const": "agreement_draft" },
    "requires_dual_approval": { "const": true },
    "draft": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "clauses", "review_by", "revocable"],
      "properties": {
        "title": { "type": "string", "maxLength": 120 },
        "clauses": {
          "type": "array", "minItems": 1, "maxItems": 30,
          "items": {
            "type": "object",
            "additionalProperties": false,
            "required": ["id", "text"],
            "properties": {
              "id": { "type": "string" },
              "text": { "type": "string", "maxLength": 400 }
            }
          }
        },
        "review_by": { "type": "string", "format": "date", "nullable": true },
        "revocable": { "const": true }
      }
    },
    "provenance": { "$ref": "dilchat:ai:defs#/$defs/provenance" },
    "disclaimers": { "$ref": "dilchat:ai:defs#/$defs/disclaimers" },
    "safety": { "$ref": "dilchat:ai:defs#/$defs/safety" }
  }
}
```

> **[Safety][Technical]** `requires_dual_approval` and `revocable` are `const: true`.
> The `agreements` module creates the agreement in `state = draft` and transitions
> to `active` **only** after two distinct approval ConsentEvents (one per partner).
> No AI output can set an agreement active. Drafts are explicitly **not legal
> instruments** (disclaimer required). **[Requires legal review]** for jurisdictional
> wording under DPDP/GDPR.

#### Example output (abbreviated)

```json
{
  "kind": "agreement_draft",
  "requires_dual_approval": true,
  "draft": {
    "title": "Weekend rhythm — trial for one month",
    "clauses": [
      { "id": "c1", "text": "Saturday mornings are unstructured downtime at home." },
      { "id": "c2", "text": "We plan one shared outing each weekend, chosen by Thursday." },
      { "id": "c3", "text": "Either of us can call a 'rest weekend' with no guilt, up to once a month." }
    ],
    "review_by": "2026-09-04",
    "revocable": true
  },
  "provenance": {
    "prompt_pack_version": "dilchat_prompts_v1", "task": "draft_agreement",
    "provider": "anthropic", "model_id": "claude-<pinned-at-build>",
    "generated_at": "2026-08-04T08:20:00Z",
    "input_fields_cited": ["agreed_points"], "computed_by_deterministic_service": false
  },
  "disclaimers": ["A relationship draft for you both to review, edit, and approve. Not a legal contract. Either of you can decline or revoke."],
  "safety": { "flags": [], "escalate": false, "crisis_resources": [] }
}
```

### 2.10 Task autonomy summary

See §10 for the authoritative autonomy table and human-approval state machine.

---

## 3. Prohibited tasks

These are **never** offered as tasks and are actively blocked at both input and
output. Each row lists the **rationale**, the **detection** mechanism, and the
**refusal** behavior. Detection runs in two places: (a) the **task router**
refuses to instantiate a prohibited task; (b) the **input moderator** and
**output post-filter** (§5, §8) block prohibited *content* even when it appears
inside an allowed task (e.g., a user's private message that asks the AI to infer
infidelity).

| # | Prohibited task | Rationale | Detection | Refusal behavior |
|---|---|---|---|---|
| P1 | Deterministic claims about a person's **motives** ("he ignored you because he doesn't care") | Mind-reading is unfalsifiable and corrosive; violates neutrality | Motive-attribution classifier on outputs; `assumptions` must be self-owned (§2.6) | Rewrite as author's assumption or block `AI_SAFETY_BLOCKED`; return neutral reframe |
| P2 | **Infidelity inference** from charts, timing, or behavior | DEC-021; catastrophic, unverifiable, weaponizable | Keyword+intent classifier (affair/cheating/loyalty-from-astrology) on input & output | Hard refuse; surface neutral message: DilChat cannot and will not judge fidelity; offer to help talk about trust |
| P3 | **Sexual-consent inference** ("your charts say she wants…") | DEC-021; consent is never inferable; safety-critical | Consent-inference classifier; Yoni context guard | Hard refuse; restate consent must be explicit and human; no chart-based inference ever |
| P4 | **Psychiatric diagnosis** ("you have anxiety/NPD/bipolar") | DEC-021; medical scope; unlicensed | Clinical-term classifier on outputs | Block; replace with non-diagnostic language; if self-harm/crisis signals, escalate per §8 |
| P5 | **Fertility / pregnancy prediction** (esp. from Nadi) | DEC-021; medical + emotionally hazardous | Nadi-medical guard + fertility keyword classifier | Hard refuse; Nadi rendered as constitutional-compatibility language only |
| P6 | **Medical advice from Nadi** (health, genetics, treatment) | DEC-021 | Same Nadi-medical guard | Hard refuse; disclaimer; suggest a qualified professional |
| P7 | **Financial predictions as fact** ("you'll get money in October") | DEC-021; astrology must not drive financial decisions | Finance-forecast classifier | Block; reframe as non-predictive; disclaimer |
| P8 | Advice **pressuring someone to remain in an unsafe relationship** | DEC-021; safety-critical | Abuse/danger classifier on input; coercion classifier on output | Never counsel staying; surface domestic-abuse resources (§8); escalate=true; do NOT diagnose |
| P9 | **Automatic disclosure of private info** to partner or shared room | DEC-013; core privacy invariant | Scope guard (§4/§9); no task writes across scope without ConsentEvent | Structurally impossible; attempt logged as `AI_SCOPE_VIOLATION`, request aborted |
| P10 | Declaring one partner **right/wrong solely from astrology** | DEC-019/DEC-021; astrology is not a verdict | Adjudication classifier on outputs | Block; reframe as difference, not fault |

> **[Safety]** Prohibited-content detection is **fail-closed**: if a classifier
> errors or times out, the content is treated as blocked, not passed. A blocked
> output NEVER reaches the user unrendered; the user sees a neutral, non-alarming
> message and, where relevant (P8), resources.

### 3.1 Refusal message principles

- Neutral, non-shaming, brief.
- Never repeat the prohibited inference even to deny it in detail.
- Always offer a constructive, allowed alternative ("I can't judge that, but I
  can help you two talk about trust").
- For safety-critical categories (P8, and self-harm signals), attach
  `crisis_resources` and set `escalate: true`.

---

## 4. Context minimization — the ContextBuilder

Every AI call is preceded by the **ContextBuilder**, the only component allowed
to assemble the context envelope handed to the provider adapter. It enforces
**minimum authorized context** (DEC-013, DEC-014).

### 4.1 Principles

1. **Allow-list per task, not deny-list.** Each task declares exactly which
   fields it may receive. Anything not listed is dropped. Default deny.
2. **Scope isolation.** The `ScopeContext` (DEC-012) determines which scope's
   data may be read. A `PRIVATE_A` task can never receive `PRIVATE_B` data and
   vice-versa. `SHARED` tasks receive only data with a valid ConsentEvent.
3. **Never the other partner's private data.** No task, ever, mixes one
   partner's private content into the other's context or into a shared context
   without a ConsentEvent covering exactly that projection.
4. **Never raw birth coordinates.** Exact latitude/longitude and precise birth
   time are **stripped** (DEC-021, OQ-6). The AI receives only derived,
   already-computed labels (nakshatra name, house number, Koota flags), never the
   inputs from which astronomy was computed.
5. **PII redaction.** Names, phone numbers, emails, addresses, government IDs,
   and free-text birthplaces are redacted/placeholdered (`{{partner}}`,
   `{{self}}`) before egress. The AI does not need real names to do its job.
6. **No IDs that enable joins.** Internal `user_id` / `couple_id` are replaced by
   opaque per-request pseudonyms; the AI never receives durable identifiers.

### 4.2 Envelope shape

```json
{
  "envelope_version": "ctx_v1",
  "task": "<task-name>",
  "scope": "PRIVATE_A | PRIVATE_B | SHARED",
  "consent_event_id": "<required for SHARED tasks, else null>",
  "redaction_map_applied": true,
  "fields": { "...allow-listed task fields only..." }
}
```

The envelope carries **no** raw coordinates, **no** durable IDs, **no** other
partner's private data. The ContextBuilder computes a SHA-256 of the redacted
envelope for audit (§9) — the hash, not the content, is logged.

### 4.3 Task → allowed context fields

| Task | Scope | Allowed context fields | Explicitly forbidden |
|---|---|---|---|
| `explain_guna_component` | SHARED | `component`, `raw_score`, `max_score`, `classifications.*`, `rule_provenance.*` | birth data, coordinates, partner private text |
| `daily_climate_summary` | PRIVATE_A/B | own `profile.{local_date,moon_house,phase,features}`, own `interest_scores(12)`, `model_provenance` | coordinates, exact birth time, partner's profile |
| `likely_attention_themes` | PRIVATE_A/B | own `interest_scores(12)`, `interest_model_version` | any partner data, coordinates |
| `conversation_preview` | SHARED | `topic`, `shared_context.*` (symmetric consented), `consent_ref` | any PRIVATE_* field, either partner's raw messages |
| `gentle_opener` | own/SHARED | `topic`, `scope`, `desired_tone` | partner's private content |
| `ffanr_separation` | PRIVATE_A/B (own) | own `message` (the author's own text) | partner's messages, shared room content |
| `compromise_options` | SHARED | `partner_a_need`, `partner_b_need` (both consented), `constraints`, `consent_ref` | private messages behind those needs |
| `summarize_mutual_understanding` | SHARED | `shared_points[]` (consented), `consent_ref` | private originals of shared points |
| `draft_agreement` | SHARED | `topic`, `agreed_points[]` (consented), `consent_ref` | private negotiation history |

> **[Technical]** The allow-list is defined as data (per-task field manifest),
> version-pinned with the prompt pack. Adding a field to a task's context is a
> prompt-pack change (§7) and is auditable — you cannot widen context silently in
> code.

---

## 5. Structured output & validation pipeline

Every AI call flows through this fixed pipeline. No stage may be skipped; the
output of a skipped or failed stage is **never** shown to a user.

```
  caller (ai_guidance service method)
        │
        ▼
  [1] Task router ── refuses prohibited tasks (§3), resolves task manifest
        │
        ▼
  [2] ContextBuilder ── scope guard + allow-list + PII redaction (§4)
        │
        ▼
  [3] Input moderation ── self-harm/abuse/crisis + prohibited-content scan (§8)
        │      └── on crisis signal: attach resources, may short-circuit to safe response
        ▼
  [4] Provider adapter (AIProvider port) ── Anthropic Claude default (DEC-014)
        │      structured-output request with task OUTPUT schema
        ▼
  [5] JSON Schema validation (draft 2020-12) ── strict, additionalProperties:false
        │      └── on failure → repair loop (see 5.1)
        ▼
  [6] Safety post-filter ── grounding check (§6) + moderation (§8) + task invariants
        │      └── e.g. cited_score == input.raw_score; manipulation/adjudication blocks
        ▼
  [7] Provenance stamping ── prompt_pack_version, model_id, input_fields_cited, timestamp
        │
        ▼
  [8] Persist (audit + result) ── result stored scoped; audit stores hashes only (§9)
        │
        ▼
  caller receives VALIDATED, STAMPED output only
```

### 5.1 Validation-failure handling

1. **Schema validation fails** (stage 5): the adapter re-requests with a
   **repair prompt** that includes the validation errors and the schema, asking
   the model to emit only conformant JSON. Retry up to **N = 2** times
   (configurable; default 2, so 3 total attempts).
2. **Still failing after N retries:** the pipeline returns a **deterministic
   fallback** where one exists (e.g., `explain_guna_component` falls back to a
   templated, non-AI explanation stitched from the deterministic
   `interpretation` pack `dilchat_interp_v1`; `likely_attention_themes` falls
   back to a pure sort of the input scores with fixed confidence banding).
3. **No safe fallback exists:** the pipeline returns a graceful error
   `AI_VALIDATION_FAILED` to the caller; the UI shows "We couldn't prepare this
   right now" — **never** the unvalidated model text.
4. **Safety post-filter fails** (stage 6): treated as non-retryable for the
   offending content; return `AI_SAFETY_BLOCKED` with a neutral message (and
   resources if a safety category triggered). A repair retry is allowed **once**
   for pure formatting/grounding mismatches (e.g., miscited score) but never for
   moderation blocks.

> **INVARIANT AI-3 (no unvalidated egress).** Unvalidated or unstamped model
> output is NEVER shown to a user, stored as a result, posted to any scope, or
> included in another AI call. **[Technical][Safety]**

### 5.2 Provider adapter contract (AIProvider port)

```
complete_structured(
    task: TaskName,
    envelope: ContextEnvelope,      # from ContextBuilder, already minimized
    output_schema: JSONSchema,      # task output schema
    system_prompt: str,             # from prompt pack dilchat_prompts_v1
) -> RawModelOutput                 # unvalidated; pipeline stages 5-7 finalize
```

Adapters (Anthropic default, OpenAI alternate — DEC-014) are interchangeable and
must not embed task logic; they translate the port call to the vendor API and
back. Model IDs are pinned at build time and recorded in provenance.

---

## 6. Hallucination containment

> **INVARIANT AI-4 (grounding).** The AI may reference **only** values present in
> its structured input envelope. It must not introduce new astrological "facts,"
> new scores, new nakshatra/Koota claims, or numbers not in the input.
> **[Technical][Safety][Traditional Vedic rule]**

Containment mechanisms:

1. **Grounding check (post-filter, stage 6).** Every numeric or classical token
   in the output is checked against the input envelope. `cited_score`,
   `cited_max`, and any Koota/house/theme value must appear in the input. Novel
   astrological terms not present in the input `classifications`/`interpretation`
   mapping are flagged and the output rejected (`AI_GROUNDING_FAILED`, repairable
   once).
2. **Field citation.** Every output carries `provenance.input_fields_cited` — the
   exact input paths the explanation draws on. Empty citations on an
   explanation-type task is a validation failure.
3. **Refusal to compute.** System prompts instruct: "You are given final numbers.
   You never compute, re-sum, re-weight, or infer new numbers. If asked to, refuse
   and state the app computed it." The router also blocks any user instruction
   that asks the model to calculate (P-series adjacent).
4. **Low-confidence handling.** When inputs are sparse/ambiguous, the output must
   lower confidence (`confidence: "low"`) or reduce specificity rather than
   fabricate. The interest-theme banding (§2.3) demotes near-ties to `low`.
5. **"The app calculated X" framing.** Explanations MUST attribute numbers to the
   deterministic engine ("The app calculated Nadi at 0 of 8…"), never to the AI's
   own reasoning. The post-filter checks explanation text for first-person
   computation claims ("I calculated", "I estimate the score") and rejects them.
6. **No external knowledge injection.** The model must not import astrology
   "facts" from its training data that are not in the input rule/interpretation
   pack — DilChat's classical claims come only from `ashtakoota_lahiri_classical_v1`
   / `dilchat_interp_v1`, never from the model's memory. **[Traditional Vedic rule]**

---

## 7. Prompt-versioning strategy

### 7.1 Prompt packs

All prompts ship as an immutable, versioned **prompt pack**. MVP pack:
`dilchat_prompts_v1` (DEC-001 §0). A prompt pack contains, per task:

- the **system prompt** (role, grounding rules, refusal rules, tone);
- the **output schema reference** and repair-prompt template;
- the **context field manifest** (the §4.3 allow-list for that task);
- **few-shot exemplars** (grounded, safe);
- **safety directives** (the §3 refusals inlined per task).

```
prompt_packs/
  dilchat_prompts_v1/
    pack.json                 # id, created_at, model_targets, checksum
    tasks/
      explain_guna_component.system.md
      explain_guna_component.manifest.json
      daily_climate_summary.system.md
      ... (one per task)
    CHANGELOG.md
```

### 7.2 Storage & integrity

- Packs are checked into the repo and baked into the container image at a pinned
  **checksum** (mirrors the ephemeris-file pinning discipline, DEC-007).
- The running pack id + checksum are asserted at startup; mismatch is a hard
  boot failure.
- **[Technical]** Packs are content-addressed; a changed prompt = a new pack
  version. Prompts are never edited in place in production.

### 7.3 Provenance & audit

- `prompt_pack_version` (`dilchat_prompts_v1`) is stamped on **every** output
  (`provenance.prompt_pack_version`) and written to the audit log with the
  request (§9). This is a hard requirement (schema `const`).
- Given any stored AI result, the exact system prompt, schema, and manifest that
  produced it are reconstructable from the pinned pack version.

### 7.4 A/B, rollout, rollback

- **A/B:** a new pack (e.g., `dilchat_prompts_v2`) can be served to a cohort via
  a feature flag; both versions are valid, and outputs are tagged with the pack
  that produced them, so metrics attribute correctly.
- **Rollback:** because packs are immutable and version-stamped, rollback is a
  flag flip back to `dilchat_prompts_v1`; no data migration, and historical
  outputs remain correctly attributed.
- **Changelog:** every pack carries `CHANGELOG.md` describing what changed and
  why, reviewed like code. Safety-relevant prompt changes require a safety sign-off.

---

## 8. Content moderation & safety

Two moderation gates wrap every call: **input** (stage 3) and **output**
(stage 6). Both are fail-closed (§3).

### 8.1 Input moderation

Scans the user's own text (e.g., `ffanr_separation.message`) and task inputs for:

- **Self-harm / suicidality** signals.
- **Domestic abuse / danger** signals (threats, control, fear, physical harm).
- **Crisis** signals (acute distress).
- **Prohibited-content requests** (asking the AI to infer infidelity, diagnose,
  predict fertility, etc. — §3).

On a self-harm or abuse/danger signal, the pipeline **short-circuits** the normal
task: instead of (or alongside) the task output, it returns a **resource-first
safe response** with `safety.escalate = true` and populated `crisis_resources`.
It **does not diagnose** and does not tell the user what is "wrong" with them or
their partner.

### 8.2 Output moderation

Scans the model output for: manipulation (§2.5), adjudication/blame (P10),
motive-attribution (P1), clinical/medical/fertility/financial-forecast language
(P4–P7), prohibited inferences (P2, P3, P8), and any content that would disclose
private data across scope (P9). Any hit → `AI_SAFETY_BLOCKED` + neutral message
(+ resources if a safety category).

### 8.3 The `safety` object schema (Appendix A.3)

```json
{
  "$id": "dilchat:ai:defs#/$defs/safety",
  "type": "object",
  "additionalProperties": false,
  "required": ["flags", "escalate", "crisis_resources"],
  "properties": {
    "flags": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["self_harm", "abuse_or_danger", "crisis", "medical",
                 "sexual_content", "minor_safety", "prohibited_inference", "none"]
      }
    },
    "escalate": {
      "type": "boolean",
      "description": "true → surface human/crisis resources and route to safe response."
    },
    "crisis_resources": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["label", "region", "contact"],
        "properties": {
          "label": { "type": "string" },
          "region": { "type": "string", "description": "e.g. IN (India-first, OQ-13)" },
          "contact": { "type": "string", "description": "phone/URL of a vetted resource" },
          "kind": { "type": "string", "enum": ["hotline", "text_line", "web", "emergency"] }
        }
      }
    }
  }
}
```

### 8.4 Self-harm / domestic-abuse disclosure pathway

1. Signal detected by input moderation (or user self-discloses mid-task).
2. Pipeline attaches region-appropriate `crisis_resources` (India-first per
   OQ-13; internationalized as markets expand — **[Requires legal review]** and
   **[Requires domain review]** for vetted local resources).
3. `safety.escalate = true`; response leads with support and resources, in
   plain, non-clinical, non-alarming language.
4. **No diagnosis, no medical advice** (DEC-021). DilChat surfaces *resources*,
   never a determination that the user "has" a condition or that the partner "is"
   an abuser.
5. For domestic-abuse signals, the AI **never** counsels remaining in an unsafe
   relationship (P8) and never pressures a decision either way; it points to
   help and affirms the user's safety and autonomy.
6. Escalation is logged as a safety event (hashes/flags only, no raw content —
   §9); a human-review/crisis-referral queue is notified per the ops runbook.

> **[Safety][Requires legal review]** The exact resource list, mandatory-reporting
> posture, and any duty-to-warn considerations are jurisdiction-specific and must
> be settled with counsel before launch (DEC-018, DEC-021).

---

## 9. Privacy controls

Privacy at the AI boundary is enforced structurally, not by prompt alone.

1. **Scope enforcement at the AI boundary.** The ContextBuilder (§4) is the sole
   path to an AI call and applies the `ScopeContext` (DEC-012). A `PRIVATE_A`
   task physically cannot load `PRIVATE_B` rows; a `SHARED` task requires a valid
   ConsentEvent. Any attempt to cross scope aborts as `AI_SCOPE_VIOLATION` and is
   audited. **[Technical]**
2. **No cross-couple data.** Context for a call is bounded to a single
   `couple_id`/user; there is no task whose input spans couples. Model calls are
   stateless per request — no conversation carryover that could leak between
   couples.
3. **Provider retention/training terms.** The provider must offer **zero-retention
   / no-training** API terms for user content (DEC-014, OQ-12). Until contractually
   confirmed and recorded, this is **[Requires legal review]**. The adapter sets
   the vendor flags that disable retention/training where the API exposes them.
4. **Never train on user content.** DilChat does not use user content to train or
   fine-tune any model, first- or third-party.
5. **AI logs never store raw private content.** Audit/observability logs store:
   task name, scope, prompt_pack_version, model_id, the **SHA-256 of the redacted
   envelope**, validation/safety outcomes, token counts, latency, and error
   codes — **not** the message text, not the summary text, not the coordinates.
   Raw request/response bodies are not persisted to logs. Results themselves are
   stored in the owning module's scoped tables (subject to RLS, DEC-012), not in
   the AI log. **[Technical][Safety]**
6. **Redaction before egress.** Names/PII are placeholdered before the envelope
   leaves the ContextBuilder (§4.1). Even the provider never receives real names,
   phone numbers, addresses, or exact birth coordinates.
7. **Deletion & export.** AI-produced results are ordinary scoped rows and are
   included in the user's export/delete flows (DEC-011); because logs hold only
   hashes, deletion of the underlying content leaves no reconstructable copy in
   logs.

---

## 10. Human approval requirements

Nothing the AI produces takes effect on its own. Three autonomy levels:

- **suggest-only** — shown to the requesting user in their own scope; no state
  change to shared data; user may copy/edit/ignore.
- **human-approve** — becomes a shared artifact only after the **author** reviews
  and approves (OQ-8).
- **dual-approve** — takes effect only after **both partners** approve (OQ-8).

> **INVARIANT AI-5 (no auto-post).** No AI output is posted to the SHARED room,
> shown to the partner, or made binding automatically. Every crossing of a scope
> boundary is a human-authorized ConsentEvent (DEC-013). **[Safety]**

### 10.1 Task → autonomy level

| Task | Autonomy | What a human must do before it takes effect |
|---|---|---|
| `explain_guna_component` | suggest-only | nothing (informational, SHARED-appropriate) |
| `daily_climate_summary` | suggest-only | nothing (own private view) |
| `likely_attention_themes` | suggest-only | nothing (own private view) |
| `conversation_preview` | suggest-only | nothing (from already-consented shared context) |
| `gentle_opener` | suggest-only | user chooses to send; never auto-sent |
| `ffanr_separation` | suggest-only | stays private; sharing needs a ConsentEvent |
| `compromise_options` | suggest-only | couple chooses; adopting an option is a human act |
| `summarize_mutual_understanding` | **human-approve** | author reviews/edits before it becomes a SharedArtifact |
| `draft_agreement` | **dual-approve** | both partners approve; `agreements` sets active only then |

> **[Product/Safety]** The AI **never impersonates a partner.** Openers, FFANR
> outputs, and drafts are always presented as *the user's own* material to review,
> never delivered to the partner as if the partner (or the app) authored a message
> on someone's behalf.

---

## 11. Failure modes & degradation

DilChat remains useful when the AI is unavailable, because the **numbers are
deterministic and do not depend on AI** (DEC-019).

| Failure | Behavior | User-facing result |
|---|---|---|
| **Provider outage / 5xx** | Circuit breaker opens; AI tasks return `AI_UNAVAILABLE`; deterministic services keep serving scores, daily profiles, Guna Milan | Numbers/labels still shown; explanations show a templated deterministic fallback (`dilchat_interp_v1`) where one exists, else a "explanations temporarily unavailable" notice |
| **Timeout** | Per-call deadline (default 8s soft / 15s hard); on breach, abort and treat as `AI_UNAVAILABLE`; no partial/streamed output is rendered | Same as outage |
| **Validation failure after N retries** | `AI_VALIDATION_FAILED`; deterministic fallback or graceful error (§5.1) | Never raw model text |
| **Safety block** | `AI_SAFETY_BLOCKED`; neutral message (+ resources if safety category) | No prohibited content shown |
| **Rate limiting** | Per-user and global token/request budgets (Redis counters, DEC-005); over-budget calls queue or return `AI_RATE_LIMITED` with retry-after | Deterministic content unaffected; AI extras deferred |
| **Cost controls** | Daily per-user and global spend caps; low-value repeat calls served from a short-TTL cache keyed by the redacted-envelope hash; degrade to deterministic-only when cap hit | Graceful; core product intact |

Degradation principle: **the deterministic layer is the product's floor.** AI is
an enhancement on top; losing it must never take down scores, daily profiles,
consent flows, or safety resources. **[Technical][Safety]**

---

## Appendix A — Shared schema fragments

Bundled `$defs` (JSON Schema draft 2020-12) referenced by every task output.

### A.1 `provenance`

```json
{
  "$id": "dilchat:ai:defs#/$defs/provenance",
  "type": "object",
  "additionalProperties": false,
  "required": ["prompt_pack_version", "task", "provider", "model_id",
               "generated_at", "input_fields_cited", "computed_by_deterministic_service"],
  "properties": {
    "prompt_pack_version": { "const": "dilchat_prompts_v1" },
    "task": { "type": "string" },
    "provider": { "type": "string", "enum": ["anthropic", "openai"] },
    "model_id": { "type": "string", "description": "Pinned at build time." },
    "generated_at": { "type": "string", "format": "date-time" },
    "input_fields_cited": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Exact input paths the output draws on (grounding, §6)."
    },
    "computed_by_deterministic_service": {
      "type": "boolean",
      "description": "true when the output explains numbers produced by a deterministic module."
    }
  }
}
```

### A.2 `disclaimers`

```json
{
  "$id": "dilchat:ai:defs#/$defs/disclaimers",
  "type": "array",
  "minItems": 1,
  "items": { "type": "string", "maxLength": 400 },
  "description": "Standing disclaimers (DEC-021). Wording Requires legal review."
}
```

### A.3 `safety`

See §8.3 for the full `safety` object schema (`dilchat:ai:defs#/$defs/safety`).

### A.4 `interest_scores_12`

```json
{
  "$id": "dilchat:ai:defs#/$defs/interest_scores_12",
  "type": "object",
  "additionalProperties": false,
  "description": "Exactly the 12 DilChat interest themes (dilchat_interest_v1). Values in [0,1].",
  "required": ["connection", "rest", "adventure", "home", "creativity",
               "learning", "finances", "health", "family", "intimacy",
               "work", "spirituality"],
  "properties": {
    "connection":   { "type": "number", "minimum": 0, "maximum": 1 },
    "rest":         { "type": "number", "minimum": 0, "maximum": 1 },
    "adventure":    { "type": "number", "minimum": 0, "maximum": 1 },
    "home":         { "type": "number", "minimum": 0, "maximum": 1 },
    "creativity":   { "type": "number", "minimum": 0, "maximum": 1 },
    "learning":     { "type": "number", "minimum": 0, "maximum": 1 },
    "finances":     { "type": "number", "minimum": 0, "maximum": 1 },
    "health":       { "type": "number", "minimum": 0, "maximum": 1 },
    "family":       { "type": "number", "minimum": 0, "maximum": 1 },
    "intimacy":     { "type": "number", "minimum": 0, "maximum": 1 },
    "work":         { "type": "number", "minimum": 0, "maximum": 1 },
    "spirituality": { "type": "number", "minimum": 0, "maximum": 1 }
  }
}
```

> **[Technical]** The 12 interest theme names are owned by `dilchat_interest_v1`;
> if that model's taxonomy changes, this `$def` and the prompt pack change
> together as a versioned unit (§7).

---

## Appendix B — Error codes

| Code | Meaning | User-facing? | Retryable |
|---|---|---|---|
| `AI_VALIDATION_FAILED` | Output failed schema validation after N repairs, no fallback | Graceful notice | no (fallback attempted first) |
| `AI_GROUNDING_FAILED` | Output referenced values absent from input (§6) | Graceful notice | once (repair) |
| `AI_SAFETY_BLOCKED` | Moderation blocked input or output (§3, §8) | Neutral message (+resources) | no |
| `AI_SCOPE_VIOLATION` | Attempt to cross a privacy scope (§4, §9) | Generic error | no (aborted, audited) |
| `AI_UNAVAILABLE` | Provider outage/timeout/circuit-open (§11) | Deterministic fallback | later |
| `AI_RATE_LIMITED` | Per-user/global budget exceeded (§11) | Retry-after | later |

---

## Cross-references

- `DILCHAT_DECISION_LOG.md` — DEC-013 (consent projection), DEC-014 (AI port),
  DEC-019 (score-family separation), DEC-021 (Nadi/Yoni/medical safety),
  OQ-8 (approval), OQ-9 (living-compat visibility), OQ-12 (provider/retention),
  OQ-13 (India-first).
- `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md` — ConsentEvent/SharedArtifact state
  machine (referenced by §2.8, §2.9, §4, §10).
- `DILCHAT_ASTROLOGY_ENGINE_SPEC.md` / `guna_milan` module — the deterministic
  producers of every number the AI may only explain.

**End of DILCHAT_AI_INTEGRATION_SPEC.md** · `prompt_pack_version = dilchat_prompts_v1`
