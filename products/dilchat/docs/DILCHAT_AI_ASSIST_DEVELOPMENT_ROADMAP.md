# DilChat — AI Assist Development Roadmap (V1 sequencing)

**Product:** DilChat · **Company:** Ugence Labs
**Status:** Requirements / architecture-decision phase. **No implementation.**
**Founder direction:** DEC-048.

> **Documentation only.** This roadmap sequences *future* work. It builds nothing.
> It complements — and does not replace — the existing
> [`DILCHAT_IMPLEMENTATION_ROADMAP.md`](DILCHAT_IMPLEMENTATION_ROADMAP.md); where
> they overlap, the implementation roadmap's phase definitions remain canonical
> and this document maps the AI-Assist work onto them.

## Current state (verified)

- **Mobile Phase 1 is merged** (account, birth profile, partner invitation,
  pairing, consent, paired status, unpairing).
- **Mobile Phase 2 has not started.**
- **Secure partner chat has not been implemented.**
- **AI Assist has not been implemented.**
- **User-facing Guna scores do not exist**, and the classical Guna authority
  remains unresolved (`GUNA_AUTHORITY_VALIDATION_BLOCKED`, `RULE_PACK_BLOCKED`).

---

## Approved sequence

### Phase 2 — Mobile device and native hardening
- native builds;
- physical-device validation;
- deep-link foundation;
- privacy hardening;
- network resilience;
- accessibility review.

### Phase 3 — Secure shared partner chat
- message persistence;
- synchronization;
- delivery states;
- relationship-scoped authorization;
- unpair revocation;
- retention and deletion;
- abuse, blocking, and reporting controls.

### Phase 4A — Conversation evidence and preference learning
- topic extraction;
- explicit preference storage;
- inferred-interest model (`conversation_evidence_model_v1`);
- confidence and decay;
- user corrections;
- recommendation feedback.

### Phase 4B — Guna-derived structural prior
- `structural_relationship_prior_v1`;
- **60 %** cold-start weight;
- gradual decline to a **30 %** floor;
- qualified-evidence transition (not elapsed time / message count);
- **no visible Guna score**;
- **no classical-authority claim**.

### Phase 4C — Relative Moon receptivity context
- `moon_receptivity_context_v1`;
- deterministic current-Moon calculation;
- natal-relative context;
- topic-domain receptivity;
- temporary bounded modifiers;
- safe, non-deterministic language.

### Phase 4D — AI Assist overlay
- `ai_assist_guidance_fusion_v1`;
- Good Topics;
- Approach Gently;
- Give Space;
- conservative Avoid Topics;
- one AI recommendation;
- rephrase and sentence correction;
- user-controlled insertion;
- **no automatic send**.

---

## Hard gating rules

- **AI Assist (4D) must not be implemented before secure shared chat (Phase 3)
  and privacy boundaries exist.**
- Phases **4A–4D depend on Phase 3** (a secure, relationship-scoped shared chat is
  the substrate for conversation evidence and for delivering suggestions into the
  composer).
- The structural prior (4B) and Moon context (4C) are personalization inputs to
  the fusion layer; they do **not** gate on the classical-authority track and do
  **not** enable any runtime classical rule pack.
- Within 4A–4D, the fusion layer (4D) is last: it consumes the other three
  components. Conversation evidence (4A) should precede or accompany the
  structural prior (4B) so that the progressive-dominance behavior can be tested
  against real evidence.

```
Phase 2 ──▶ Phase 3 ──▶ Phase 4A ──▶ Phase 4B ──▶ Phase 4C ──▶ Phase 4D
(device)    (secure     (evidence)   (Guna        (Moon        (AI Assist
            chat)                     prior)       context)     overlay)
                 └──────────── privacy boundaries required before 4D ─────┘
```

---

## Mapping to the existing implementation roadmap

The existing [`DILCHAT_IMPLEMENTATION_ROADMAP.md`](DILCHAT_IMPLEMENTATION_ROADMAP.md)
already sketches post-MVP AI work (its Phases E–G: daily Moon transit / interest
themes / feedback capture, and private/shared AI chat). This AI Assist roadmap
**refines** that direction under DEC-048:

- the **hidden** Guna structural prior replaces any user-visible compatibility
  score in the AI Assist surface;
- Moon transit work is scoped to a **bounded, temporary receptivity modifier**,
  not a standalone prediction;
- conversation evidence is elevated to the **progressively dominant** signal.

Where wording differs, DEC-048 and these AI Assist requirements govern the AI
Assist surface specifically; the broader roadmap remains the canonical schedule.

---

## Exact next engineering phase

> **Complete Mobile Phase 2 device and native hardening before implementing
> secure shared chat. AI Assist implementation begins only after the secure chat
> foundation and privacy boundaries are complete.**

No runtime functionality is implemented by this documentation package.
