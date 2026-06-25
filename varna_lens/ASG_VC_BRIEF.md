# ASG — Investor Brief

> **Acoustic Symbol Generation (ASG):** a deterministic symbolic control language for designing, analyzing,
> and generating sound forms — paired with an AI authoring layer and an empirical observation platform.
> Series-A facing. Supersedes the positioning in `CONCEPT_BRIEF.md` (see Changelog, §13).

---

## 1. Executive Summary (one page)

Naming, branding, and voice teams make high-stakes sound-form decisions — a product name, a sonic logo, an
AI agent's identity, a mantra, a character language — with no controllable, repeatable instrument. Today the
options are a creative's intuition, a thesaurus, or a chatbot prompt: none is deterministic, none is
explainable, none improves with evidence.

**ASG is a control system for sound-form design, built on three pillars:**

1. **Deterministic symbolic control.** ASG parses any word or coined form into a structured **profile** — a
   *trajectory* of sound interactions — using a frozen, versioned engine. Same input always yields the same
   profile. You can specify constraints ("opens grounded, resolves open; four syllables; avoids harsh
   onsets; available as a domain") and the engine **generates forms that satisfy them**, deterministically.

2. **AI-assisted authoring.** A rendering layer turns a profile into readable, on-brand prose — name
   rationales, mood palettes, mantras, copy — authored over the deterministic scaffold, never improvised
   from scratch. Determinism + audit trail underneath; fluent natural language on top.

3. **Observation-driven continuous improvement.** Every generated form and human reaction is logged into an
   **observation platform** that reports **measured associations** ("forms with this profile are rated
   *premium* 58% of the time in luxury branding, net of spelling") with confidence estimates and proper
   controls. The product gets sharper with use; the data is proprietary and compounding.

**Why now / why us.** Generative AI gave everyone fluent text but no *control, reproducibility, or
explainability* — the top unmet needs in enterprise creative tooling. ASG occupies exactly that gap: a
deterministic, inspectable control plane that composes with LLMs and embeddings rather than competing with
them. The symbolic vocabulary is an **editable, versioned engineering vocabulary** — the architecture holds
regardless of how the vocabulary evolves.

**The ask / shape.** Seed-to-A round to ship the MVP→V1 product (naming & sonic-branding wedge), build the
observation platform, and establish the trajectory schema as a reusable standard. Moat = deterministic DSL +
authoring workflow + proprietary observation graph + enterprise reproducibility + a versioned trajectory
standard.

---

## 2. Problem

Sound-form decisions are everywhere and expensive: product and company names, sonic logos, voice-assistant
and AI-agent identities, game/film constructed languages, wellness mantras, brand taglines. The current
toolchain is broken in three ways:

- **No control.** You cannot say "give me candidates that feel grounded then opening, four syllables, no
  harsh onsets" and get reproducible results. Prompts drift; thesauruses don't compose.
- **No explanation.** When a tool (or a creative) proposes a name, there is no inspectable rationale — a
  blocker for enterprise sign-off, legal review, and brand governance.
- **No memory.** Nothing measures how forms actually land with people, by context and language, and feeds
  that back. Every project starts from zero.

## 3. Product definition

**ASG is an intermediate representation (IR) / domain-specific language (DSL) for sound-form design.** It
sits between human intent and finished output as a controllable, inspectable layer:

```
intent + constraints ──► ASG profile (trajectory) ──► generated forms ──► authored rationale + measured evidence
```

**Applications (one engine, many surfaces):** naming · sonic branding · product names · AI-agent identities ·
mantras · fictional/constructed languages · poetry & lyric constraints · speech & voice design.

The same deterministic core powers analysis (form → profile), generation (constraints → forms), and
authoring (profile → prose), across all of these.

## 4. Architecture — five layers

```
1. Deterministic Sound Parser  →  2. Trajectory Builder  →  3. Neutral Trajectory Schema
                                                                     │
                                                4. Observation Layer ─┤
                                                                     ▼
                                                        5. AI Rendering Layer
```

1. **Deterministic Sound Parser** — converts a word/coined form into ordered sound units (a versioned
   discretizer). Reproducible and language-aware.
2. **Trajectory Builder** — maps the parsed structure into an interaction **trajectory** (a sequence of
   roles such as source → formation → interaction → transformation → resolution). The only component that
   reads engine internals.
3. **Neutral Trajectory Schema** — a stable, versioned data contract describing a profile (beats, elements,
   texture, motion, tone, resolution). **Everything else depends only on this.**
4. **Observation Layer** — stores generations and human reactions; computes **measured associations** with
   controls and confidence, by context and language.
5. **AI Rendering Layer** — authors human-readable output (names, rationales, mood palettes, mantras) over
   the profile, under a hard honesty filter.

**Why the Trajectory schema is the stable interface — and why vocabularies are replaceable.** The schema is
the keystone: the parser/builder feed it, and the observation and rendering layers consume *only* it. The
**symbolic vocabulary** (which sounds map to which trajectory qualities) is an **editable, versioned
engineering vocabulary** plugged in behind the schema. Improving, localizing, or wholly replacing that
vocabulary changes one component; the rendering layer, the APIs, the SDK, and customer integrations are
untouched. This decoupling is what makes the architecture durable: **the product survives any change to the
vocabulary**, because no downstream layer depends on its specifics.

## 5. Competitive positioning

ASG is not an alternative to LLMs or embeddings — it is the **deterministic, inspectable control plane** they
lack, and it composes with both.

| Capability | **ASG** | Prompting / LLM-only | Embeddings / vector search |
|---|---|---|---|
| Deterministic, reproducible outputs | **yes** | no | no |
| Hard-constraint satisfaction (sounds, length, rhyme, availability) | **yes** | violates constraints | weak |
| Explainability / audit trail | **yes** (profile → output derivation) | post-hoc only | black box |
| Editable symbolic control at meaningful granularity | **yes** | indirect | no |
| Inverse design (intent → conforming forms) | **yes** | unreliable | hard |
| Cost / latency at scale | low (deterministic core) | API-bound | index-bound |

LLMs give fluency; embeddings give similarity; **neither gives control + explanation + reproducibility.** ASG
provides those and uses LLMs for authoring and embeddings for retrieval inside its pipeline.

## 6. Observation platform

A continuously improving **measurement system**, not a claim engine. It collects human reactions to generated
forms (blind, context-tagged, multi-language) and reports:

- **measured associations** — distributions of how forms with a given profile are described,
- **context-specific observations** — segmented by domain (brand vs. product vs. agent vs. mantra) and
  language,
- **confidence estimates** — with controls for surface features (spelling, length, known phonetics) so an
  association reflects the form, not the orthography,
- **empirical evidence** — accumulated, queryable, and improving with every project.

It is explicitly a record of *what observers report*, reported as **measured associations**, not universal
truths.

## 7. Moat

1. **Deterministic symbolic DSL** — a controllable, inspectable IR that is hard to replicate and that LLM/
   embedding stacks structurally lack.
2. **Authoring workflow** — the studio + rendering layer that turns profiles into on-brand output, with
   per-customer brand-voice configuration (switching cost).
3. **Empirical observation graph** — proprietary, controlled, compounding data on how sound forms land by
   context and language. The only dataset measuring response *net of confounds*.
4. **Enterprise reproducibility** — versioned, auditable, deterministic outputs deployable on-prem/VPC; a
   trust and compliance advantage incumbents (and chatbots) cannot match.
5. **Versioned trajectory standard** — owning the schema others build against creates an ecosystem and
   network effects as vocabularies, renderers, and integrations accrue to it.

## 8. Business model

- **SaaS seats** for naming/branding/creative teams (studio + API).
- **Usage-based API** for generation/analysis/rendering at scale (agencies, platforms, agent builders).
- **Enterprise** (SSO/RBAC/audit, on-prem deterministic engine, brand-voice configuration, SLAs).
- **Observation/insights** as a premium data layer (context-specific measured associations).
- **Platform/marketplace** revenue (vocabularies, renderer plugins, partner integrations) at scale.

## 9. Market

Wedge: **brand & product naming + sonic branding** — a budgeted, recurring, sign-off-heavy spend with clear
ROI and fast feedback. Expansion: AI-agent identities (a fast-growing surface), voice/speech design,
game/film constructed languages, education, accessibility/TTS, and agentic workflows that need a controllable
naming/branding tool.

## 10. Roadmap (commercial)

| Stage | Focus |
|---|---|
| **MVP (3 mo)** | deterministic engine + constraint generation + 2 rendering modes; naming wedge; reproducible API; event logging |
| **Beta (6 mo)** | all rendering modes; trajectory editor UI; brand-voice presets; structured observation capture; learned re-ranker; SDK (offline deterministic engine) |
| **V1 (12 mo)** | audio preview; mature inverse design; **observation platform with controls + associations API**; enterprise (SSO/audit/on-prem); hybrid neural-symbolic generation that guarantees constraints |
| **Platform (24 mo)** | published **trajectory standard**; pluggable vocabularies + engines; **marketplace**; multimodal (text + audio/sonic-logo) rendering; cross-customer insights network |

Build priorities, in order: **deterministic engine → renderer → observation platform → SDK → enterprise APIs
→ trajectory standard → marketplace → multimodal rendering.**

## 11. Status

The deterministic engine, the trajectory/rendering architecture (analysis → trajectory → authored output),
the honesty filter, and the observation-capture design are specified and in working form. The commercial
product surfaces (studio UI, observation platform, enterprise APIs) are the build ahead.

## 12. What ASG does not claim

In the interest of defensible positioning, ASG makes only claims it can support with a reproducible
computation or a controlled measurement:

- **ASG does not claim intrinsic sound meaning.** It does not assert that sounds carry objective meaning.
- **ASG does not claim scientific validation of its vocabulary.** The symbolic vocabulary is an **engineered,
  editable, versioned vocabulary**, not a validated natural ontology.
- **ASG provides an engineered symbolic language** for controlling and explaining sound-form generation —
  deterministic, reproducible, constraint-satisfying, and inspectable.
- **Empirical observations are reported as measured associations**, segmented by context and language, with
  confidence and controls — **not as universal truths**, and never as decoded meaning.

This honesty is a feature: it is what makes the product defensible to enterprise buyers, legal review, and
investors, and it is structurally guaranteed by the architecture (the engine is deterministic; the
observations are measured; the prose is authored and clearly downstream).

## 13. Changelog — substantive positioning changes (from `CONCEPT_BRIEF.md`)

| # | Change | Rationale |
|---|---|---|
| 1 | **Repositioned from "esoteric system / astrology for language" → a deterministic symbolic control language (IR/DSL) for sound-form design.** | Commercial, defensible, investor-legible; removes the unprovable framing. |
| 2 | **Symbolic vocabulary reframed from "frozen lexicon of mental propensities" → an editable, versioned engineering vocabulary** behind a stable schema. | Makes the architecture survive any vocabulary change; removes ontology dependence. |
| 3 | **Executive summary rebuilt around three pillars** (deterministic symbolic control · AI-assisted authoring · observation-driven improvement). | Leads with commercial value, not theory. |
| 4 | **Architecture formalized as five layers** (parser → trajectory builder → neutral schema → observation → rendering), with the **Trajectory schema named as the stable interface**. | Communicates durability and decoupling to a technical investor. |
| 5 | **Added competitive positioning vs. prompting / LLMs / embeddings / vector search** (determinism, constraints, explainability, reproducibility, editable control). | Establishes the category and the gap ASG fills; no scientific comparisons. |
| 6 | **Moat reframed away from ontology** → deterministic DSL + authoring workflow + empirical observation graph + enterprise reproducibility + versioned trajectory standard. | Durable, data- and standard-based defensibility. |
| 7 | **Observation platform described as a measurement system** producing *measured associations / context-specific observations / confidence estimates / empirical evidence* — never "proves / validates ontology / decodes meaning." | Honest, sellable, and the compounding data moat. |
| 8 | **Added a dedicated "What ASG does not claim" section.** | Pre-empts the indefensible claims and turns honesty into a buyer-trust asset. |
| 9 | **Roadmap re-centered on the commercial build** (engine · renderer · observation platform · SDK · enterprise APIs · trajectory standard · marketplace · multimodal) and **ontology/scientific discovery removed from the commercial roadmap.** | Keeps the brief about shippable product. |
| 10 | **Language audit applied throughout** — *meaning/decodes/true/ontology/discovered* replaced with *profile / trajectory / symbolic representation / control language / engineered vocabulary / measured association / sound-form design*. | Consistent, defensible, investor-facing voice. |
| 11 | **Preserved (still valid):** the deterministic-scaffold + LLM-authoring architecture, the honesty contract (authored, never decoded), and the determinism-as-moat thesis from the prior brief. | These engineering claims hold and are core to the product. |
