# DilChat — AI Assist Chat Overlay Spec (V1)

**Product:** DilChat · **Company:** Ugence Labs
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** DEC-048.

> **Documentation only.** This document specifies the approved chat-overlay UI
> template discussed with the founder. It contains **no** mobile screen code, no
> component implementation, and no production UI. It describes required behavior
> and layout so the future Phase 4D implementation can be built against it.

Cross-references:
[product requirements](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md) ·
[signal fusion](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md) ·
[privacy/provenance/safety](DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md) ·
existing [mobile architecture](DILCHAT_MOBILE_ARCHITECTURE.md).

---

## 1. Invocation and context

The AI Assist overlay:

- appears **over the chat screen only after the user explicitly taps "AI Assist"**;
- **never opens automatically**;
- **retains the partner-chat context behind it** (the conversation stays visible
  or immediately returnable; the overlay is a layer, not a navigation away);
- shows a clear **"AI ASSIST"** heading.

---

## 2. Content structure

The overlay content structure should include, in order:

1. **Good Topics** — one line item per row.
2. **Approach Gently**, **Give Space**, or **Avoid Topics** — as supported by
   evidence, one line item per row.
3. **One** concise **AI recommendation**.
4. **Suggested wording** or a **rephrased message**.
5. An explicit **user-controlled insert or rephrase action**.

### 2.1 Topic list rules

- Present **Good Topics** as **one line item per row** (a list, not a grid).
- Present sensitive or avoid topics as **one line item per row**.
- **Do not** use a two-column table for topic items.
- Show sensitive/avoid categories **only when supported by evidence** (see §4).

### 2.2 Recommendation rules

- Show **only one** AI recommendation.
- **Never duplicate** the same recommendation; recommendation text must not be
  repeated within the overlay.

---

## 3. Actions (user-controlled only)

- Provide a **rephrase / sentence-correction** action.
- Support **inserting** suggested wording into the composer.
- **Never send a message automatically.** The AI never sends.
- The user must **review and manually send** every message.
- Clearly **distinguish AI-generated suggestions from partner messages** (visual
  treatment, labeling, and screen-reader semantics).

---

## 4. Output categories in the overlay

Category selection follows the recommendation precedence and the conservative
"Avoid" rule (see [signal fusion §7](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md#7-recommendation-precedence-authoritative-order)
and [product requirements §6](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md#6-ai-assist-output-categories)):

| Category | Shown when |
|----------|-----------|
| **Good Topics** | Positive current-conversation evidence, known/inferred interest, suitable posture, sufficient present receptivity. |
| **Approach Gently** | Valid topic that needs softer wording, less pressure, reduced intimacy, careful timing, or acknowledgement of sensitivity. |
| **Give Space** | Present climate supports lower pressure, fewer questions, practical rather than emotional wording, and time to respond. |
| **Avoid Topics** *(conservative)* | **Only** an explicit boundary, repeated strong negative behavioral evidence, an active unresolved conflict on that subject, or a safety restriction. Guna/Moon alone **never** qualify. |

**Empty avoid state (required copy):** when no supported avoid-topic evidence
exists, the UI states:

> "No clear topic to avoid from this conversation."

Never fabricate an avoid topic to fill the interface.

> **Open naming question (OQ-AIA-17):** "Avoid Topics" may be renamed "Approach
> Carefully" in V1. Not decided here.

---

## 5. Chat-header template constraints

For the **current approved chat-header template**:

- **Avoid call and video-call icons** in the header.
- Retain a **clean, mobile-first, rounded-card** layout.
- Keep the header focused on the partner-chat context and the AI Assist entry
  point.

---

## 6. Layout, accessibility, and platform fit

- **Mobile-first**, rounded-card layout consistent with the existing Phase 1
  mobile app (React Native + Expo; see
  [mobile architecture](DILCHAT_MOBILE_ARCHITECTURE.md)).
- **Accessible touch targets** (adequate minimum size and spacing).
- **Screen-reader labels** for every item, action, and the AI/partner
  distinction.
- AI suggestions must be **programmatically distinguishable** from partner
  messages for assistive technology, not only visually.

---

## 7. Illustrative wireframe (non-binding)

The following is an **ASCII sketch** to communicate structure only — it is not a
design asset and prescribes no exact styling.

```
┌───────────────────────────────────────────┐
│  AI ASSIST                            [x]  │   ← heading; close returns to chat
├───────────────────────────────────────────┤
│  Good Topics                               │
│   • Your recent hike                       │   ← one item per row
│   • Weekend plans                          │
│                                            │
│  Approach Gently                           │
│   • Work stress                            │   ← shown only if supported
│                                            │
│  Avoid Topics                              │
│   No clear topic to avoid from this        │   ← required empty-state copy
│   conversation.                            │
├───────────────────────────────────────────┤
│  Recommendation                            │
│   "That sounds beautiful. What was your    │   ← exactly one, never duplicated
│    favorite part of the trail?"            │
│                                            │
│   [ Insert into message ]  [ Rephrase ]    │   ← user-controlled; never auto-send
└───────────────────────────────────────────┘
        (partner chat remains behind the overlay)
```

---

## 8. Behavioral checklist (maps to acceptance criteria)

The overlay implementation (future Phase 4D) must satisfy, at minimum:

- opens only on explicit tap; never auto-opens — `AIA-UX-1`;
- one recommendation only; no duplication — `AIA-UX-2`, `AIA-UX-3`;
- Good Topics one item per line; no two-column topic table — `AIA-UX-4`;
- AI never sends; manual send required — `AIA-FUNC-1`, `AIA-SAFE-*`;
- AI suggestions visibly + programmatically distinct from partner messages —
  `AIA-UX-5`;
- no compatibility score shown — `AIA-GUNA-3`;
- empty avoid-state copy present — `AIA-UX-6`;
- accessible touch targets + screen-reader labels — `AIA-UX-7`.

See [`DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md`](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md)
for the full requirement text.
