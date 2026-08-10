# Agent Runtime VC Brief — Change Log (v2.0.0 → v2.1.0)

Refinement of `AGENTIC_FRAMEWORK_VC_BRIEF.md` following the completed architecture work
(CER V0.3, AI Control Plane separation, Runtime migration). **Refinement, not a rewrite** — the
four-page structure, the FACT/positioning/vision distinction, and the two-product separation are
all preserved. Every change below is classified as one or more of:

- **[POS]** Better positioning
- **[CLR]** Better investor clarity
- **[ACC]** Better technical accuracy
- **[CON]** Better architectural consistency

No technical claim was changed except to improve factual accuracy. Every quantitative claim is still
sourced from the repository/CI. The AI Control Plane brief was **not** modified, and the two products
are **not** merged.

---

## 1. Headline / subtitle strengthened — **[POS] [CLR]**
- **Before:** "*A stateful autonomous runtime that plans work, coordinates tools, and emits Canonical Execution Requests for deterministic governance.*"
- **After:** "*The Agent Runtime that turns AI reasoning — planning, memory, reflection, tool orchestration — into a **deterministic, governable Canonical Execution Request**.*"
- **Why:** Repositions the headline around **trusted/governable execution** (the enterprise value)
  rather than "planning work" (a mechanism). Deliberately **did not** adopt the suggested word
  "first" — that is an unprovable market-first superlative, and the constraint is to stay
  evidence-based and not oversell.
- **Also:** version bumped to **2.1.0 — Refined July 2026**; the product-family note now names all
  three portfolio layers (Specialized AI Systems / AI Control Plane / AI Infrastructure) and
  explicitly states the two products are not merged.

## 2. Opening problem rewritten around trust across runtimes — **[POS] [CON]**
- **Before:** Heading "Generation and governance are improperly coupled"; framed the problem as
  coupling inside one framework.
- **After:** Heading "**Enterprises cannot consistently trust execution across AI runtimes.**" The
  narrative now walks the deeper enterprise problem in order: (a) every runtime reasons differently
  and represents actions differently; (b) enterprises increasingly run **multiple** runtimes;
  (c) governance **fragments**; (d) enterprises need **one trustworthy execution contract**. It then
  leads explicitly into **Runtime → CER → AI Control Plane**.
- **Why:** The old framing named a mechanism (coupling); the new framing names the **business risk**
  (inconsistent trust across a multi-runtime estate), which is what a Tier-1 enterprise buyer feels.
  The four-question buyer table is retained (it was already strong and evidence-anchored).
- Added coding/desktop agents (Claude Code, OpenAI Agents SDK) to the runtime landscape for accuracy.

## 3. New section: **Native Execution Proposal Engine** — **[POS] [CLR]**
- **Added** at the top of Page 2. States that, unlike existing runtimes that pass their internal
  action object straight to execution, the Ugence Runtime **converts reasoning into a CER** as its
  native output. A table enumerates what the CER carries: **intended action, normalized parameters,
  execution target, supporting evidence, provenance, deterministic identity.**
- **Why:** Elevates the single most differentiated capability into a named, first-class section.
- **Accuracy guard [ACC]:** an explicit callout describes CER as "the runtime's **native execution
  contract** — **not** an industry standard," with a forward pointer to the Page 4 vision.

## 4. New section: **Runtime independence** — **[ACC] [CON]**
- **Added** to Page 2. States plainly that the **AI Control Plane does not require the Ugence
  Runtime**, with a table of producers: **Ugence (native reference producer), LangGraph (adapter),
  OpenAI Agents (adapter), future runtimes (adapter).**
- **Why / evidence:** This is repository-supported FACT — `cer_v0_1/producers/langgraph_adapter.py`,
  `cer_v0_2/producers/{langgraph_adapter,openai_agents_adapter}.py`, and the native Ugence producers
  all exist and are conformance-tested to produce identical action identity.
- **Accuracy guard [ACC]:** explicit parenthetical — "this is architectural interoperability
  demonstrated in the repository — **not** a claim of broad market adoption."

## 5. Runtime advantages separated from Platform advantages — **[CON] [CLR]**
- **Before:** Runtime and platform advantages were mixed in one bullet list ("Where the Ugence Agent
  Runtime differentiates") and again in the "strongest platform-level comparison" prose.
- **After:** Two distinct tables under "**Runtime advantages vs. Platform advantages — kept separate
  on purpose.**"
  - **Runtime:** planning, decomposition, memory, reflection, tool orchestration, native CER
    generation, richer execution evidence.
  - **Platform:** ActionGate, ACP, runtime-independent governance, operational safety, deterministic
    authorization, runtime independence.
- **Why:** Keeps the product boundary crystal clear and prevents the runtime brief from silently
  claiming platform value. Reinforces the "two products, not merged" constraint.

## 6. Competitive Landscape rewritten as an execution-architecture comparison — **[POS] [ACC]**
- **Before:** Prose plus a differentiation bullet list (feature-flavored).
- **After:** A five-column table — **Runtime | Proposal mechanism | Governance location | Execution
  authority | Representative examples** — with rows for **LangGraph, CrewAI, Claude Code, OpenAI
  Agents, Ugence Runtime.**
- **Why:** Compares **architectures**, not features, which is both more defensible and more
  investor-legible. The distinguishing axis is made explicit: *where governance lives and who holds
  execution authority.*
- **Accuracy guard [ACC]:** a note states these are architectural characterizations (not feature
  judgments) and that competing runtimes can also emit CER via adapters — so the distinction is
  **native vs. adapter**, not exclusivity. The "Where competitors may be stronger" honesty paragraph
  is retained.

## 7. Low-value implementation plumbing removed — **[CLR]**
- **Before:** Code sample and prose referenced `AnthropicAdapter`, `MockLLMAdapter`, and the
  `BaseLLMAdapter` interface by name; a paragraph discussed mock-vs-live wiring.
- **After:** The developer snippet is reduced to the seam that matters (`propose → govern → observe`),
  and the prose is replaced with one line: "**compatible with commercial and local models through a
  common adapter interface.**"
- **Why:** VCs evaluate architecture, not developer plumbing. Removing class names also future-proofs
  the brief against internal refactors.

## 8. CER elevated out of the appendix into the main body — **[POS] [CLR]**
- **Added** a `FACT`-labeled paragraph on **Page 1** summarizing that CER V0.3 is validated through
  **multiple runtimes, multiple execution profiles, deterministic identity, and a clean-room
  implementation** — with details left in the appendix.
- **Why:** CER is the core thesis; it should be visible on page one, not buried. The appendix retains
  the full evidence, so the body summarizes without duplicating.
- **Accuracy note [ACC]:** the appendix CER paragraph was corrected to say "**three execution
  profiles** (Kubernetes scale, Kubernetes rollout, and database mutation)" — previously it listed
  the profiles without the count; now it matches the three frozen profiles in `cer_v0_3/`.

## 9. Roadmap made product-centric — **[CLR] [POS]**
- **Before:** Feature-centric near/medium/later lists.
- **After:** A five-phase **product** roadmap: **Phase 1 Agent Runtime · Phase 2 CER SDK · Phase 3
  Runtime adapters · Phase 4 Enterprise orchestration · Phase 5 Hierarchical proposal generation.**
- **Why:** Product-phased roadmaps map to fundable milestones and are what investors expect.
- **Accuracy guard [ACC]:** Phase 3 carries a parenthetical that LangGraph/OpenAI Agents adapters
  **already exist** in conformance testing and this phase *productizes* them — so the roadmap does
  not imply they are unbuilt.

## 10. New section: **"Why use the Ugence Runtime if I already use LangGraph?"** — **[POS] [CLR]**
- **Added** to Page 3 — the biggest missing commercial question. A table answers honestly: **native
  CER generation, richer execution evidence, no translation layer, better planning, better
  reflection, tighter AI Control Plane integration.**
- **Why:** Directly addresses the incumbency objection every technical VC will raise.
- **Tone guard [POS]:** does **not** attack LangGraph — it states LangGraph can be kept and governed
  through its adapter, and frames Ugence as the option for the cleanest native producer, not a
  rip-and-replace mandate.

## 11. The Ask improved — **[CLR] [CON]**
- **Before:** "two linked but separately positioned assets," with the funding framed as one brief
  funding asset (1) and referencing (2).
- **After:** Explicitly **two complementary products** that "**may be purchased independently or
  deployed together**," with three concrete adoption paths (runtime-only, control-plane-only over an
  existing runtime, or both). Reiterates the products are not merged.
- **Why:** Clarifies the commercial model and reinforces the separation constraint; removes any
  implication of an equal 50/50 funding split.

## 12. Long-term vision introduced carefully — **[POS] [ACC]**
- **Added** a `VISION`-labeled section: CER as a **common execution contract**, analogous to **OCI
  (containers)** and **CloudEvents (event envelopes)**.
- **Accuracy guard [ACC]:** the section states in bold that this is "**the architectural vision, not
  a claim of present-day industry adoption**," and that any future standardization is "an outcome to
  earn, not a status we assert." No claim that CER is already a standard appears anywhere in the
  brief.

---

## Cross-cutting integrity checks
- **[ACC]** No quantitative claim changed; all still trace to repo/CI (1,550+ tests; AUROC figures in
  the appendix; three producers, three profiles, clean-room — all verified in `cer_v0_1/`,
  `cer_v0_2/`, `cer_v0_3/`).
- **[CON]** The runtime is described **only** as proposer throughout; authorization, operational
  safety, execution authority, policy enforcement, and replay protection are attributed **exclusively**
  to the AI Control Plane in every section that touches them.
- **[CON]** `AI_CONTROL_PLANE_VC_BRIEF.md` was **not** edited.
- **FACT / positioning / vision** are kept distinct: repository-backed claims carry `FACT`, the
  long-term standardization thesis carries `VISION`, and positioning language is framed as
  positioning (e.g. "the honest and stronger position").
