# Capability Discovery — Does the Ecosystem Lack a Machine-Readable LLM Capability Protocol?

**Ugence Labs | The Governed AI Platform**
*A falsification-first investigation into whether a vendor-independent, machine-readable capability-description protocol for LLMs is a real architectural gap — or a duplicate of metadata the ecosystem already exposes.*
*Version 1.0 — July 2026*

> **What this document is.** A research investigation of one question: *does the AI ecosystem genuinely
> lack a standardized machine-readable capability-description protocol for LLMs?* It is **not** a
> protocol proposal, **not** production code, and **not** an expansion of either prior workstream (the
> Model Selection Policy specification or the Capability Negotiation self-assessment investigation). It
> treats capability *discovery* — advertising what a model can do, before interaction — as a distinct
> architectural question and applies a skeptical default: **more metadata is not assumed to be
> valuable, and a "missing standard" must be shown to be missing, not merely imagined.**
>
> **Related experiment.** This document's conclusion — that capability data belongs in an
> enterprise-internal registry with declared/measured/observed provenance rather than a new cross-vendor
> standard — is exercised concretely by the provenance-tagged registry in `model_selection_experiment/`.
>
> **The distributed-systems framing, taken seriously.** The task invites an analogy to how distributed
> systems advertise supported features before interaction (TLS cipher negotiation, HTTP content
> negotiation, gRPC reflection, WSDL/OpenAPI, WebRTC SDP, mDNS/Bonjour service discovery). This document
> takes that analogy seriously enough to find *where it breaks* — and argues the break point is the
> whole answer.
>
> **Reading discipline.** Claims are labeled **[EVIDENCE]** (grounded in a surveyed standard's current
> behavior), **[ARGUMENT]** (architectural reasoning), or **[FALSIFIER]** (a stated condition that would
> overturn the conclusion). Sources for Part 1 are listed at the end.

---

## Table of contents

0. Thesis and falsification-first summary
1. Part 1 — Survey of existing standards
2. Part 2 — Capability categories
3. Part 3 — Classes of machine-readable descriptors
4. Part 4 — Trust and provenance
5. Part 5 — Lifecycle
6. Part 6 — Enterprise value
7. Part 7 — Relationship to existing architecture
8. Part 8 — Commercial analysis
9. Part 9 — Recommendation and falsifiers
10. References

---

## 0. Thesis and falsification-first summary

**The hypothesis, stated so it can be attacked:** *No vendor-independent, machine-readable standard lets
an enterprise platform reason about heterogeneous LLMs' capabilities — recommended execution strategy,
preferred workloads, known weaknesses, task suitability — without hard-coding provider-specific
knowledge, and this absence is a real architectural gap worth closing with a new standard.*

**The single insight that resolves the question.** Distributed systems advertise features that are
**self-certifying at handshake**: if a server claims TLS 1.3 and cannot speak it, the handshake fails
immediately and cheaply. The LLM "capabilities" the hypothesis wants to advertise divide sharply on
exactly this property:

- **Interface/protocol capabilities** (does it support tools? which modalities? what context window?)
  are *self-certifying or cheaply checkable* — and the ecosystem **already advertises these**, via
  provider APIs and, at the agent layer, via **MCP's capability-negotiation handshake** and **A2A Agent
  Cards**. This slice is *solved*. **[EVIDENCE]**
- **Guidance/suitability capabilities** (is it good at legal reasoning? what decomposition should you
  use? what are its operational weaknesses?) are **not self-certifying**: a false claim of "excellent at
  contract analysis" does not fail a handshake — it fails silently, downstream, after the work is done.
  The distributed-systems analogy **breaks precisely here**, and this slice is genuinely unstandardized.

So the gap is *real but narrow*, and — critically — it is unstandardized **for a reason**, not by
oversight: the missing content is exactly the content no party can publish reliably (Parts 4, 8).

**Three attacks that bound the conclusion:**

1. **Standardizing transport does not create trust.** A protocol that defines a field for "recommended
   decomposition strategy" standardizes the *carriage* of a claim, not its *truth*. The unreliable,
   self-asserted, decaying nature of guidance content (established independently) is untouched by giving
   it a JSON schema. **[ARGUMENT]**
2. **The reliable half is inherently private; the publishable half is already published.** The
   trustworthy version of guidance is *measured/observed telemetry* — which is enterprise-specific and
   cannot be a vendor-published standard. The vendor-publishable version is *provider facts* — already
   exposed by APIs and model cards. The genuinely missing middle is the part no authoritative publisher
   exists for. **[ARGUMENT]**
3. **Adoption incentives are inverted.** MCP and A2A were adopted because they *increase usage* (more
   tool calls, more delegated work → more tokens sold). A neutral capability-*comparison* standard
   *increases substitutability* (easier to switch vendors). Vendors adopt what grows their moat and
   resist what commoditizes them; this predicts non-adoption of a neutral model-capability standard.
   **[ARGUMENT]**

**The verdict this document defends (Part 9):** **Between Outcome 2 and Outcome 3 — "existing standards
already solve the verifiable slice; the residual is useful *internal enterprise* metadata, not a missing
*interoperability* layer worth standardizing." Explicitly not Outcome 4, and not Outcome 1.** The
enterprise-internal normalization the hypothesis is groping toward already has a home: the **capability
registry** the Model Selection Policy defines. What is *not* warranted is a new cross-vendor protocol —
it would duplicate MCP/A2A/provider APIs on the verifiable slice and be structurally unpublishable on
the unverifiable slice.

---

## 1. Part 1 — Survey of existing standards

The question cannot be answered without checking whether the problem is already solved. Surveying the
named standards, grouped by what they actually advertise:

### 1.1 Provider APIs (OpenAI, Anthropic, Gemini, Azure AI, Bedrock, Vertex AI)

Each exposes **technical/interface metadata**: context window, supported modalities, tool/function
calling, structured-output modes, pricing, deployment/region options, rate limits. This is the
**Provider Facts** category (Part 2) and it is well covered — *per vendor, in vendor-specific shapes*.
What none exposes is **execution guidance**: recommended decomposition, preferred workloads, named
operational weaknesses, or task-suitability descriptors. **[EVIDENCE]** The absence is uniform across
providers, and it is not accidental (Part 8: no vendor markets its own weaknesses).

### 1.2 MCP (Model Context Protocol) — the closest *mechanism*

MCP opens every connection with a three-step **capability-negotiation handshake**: the client sends
`initialize` declaring its protocol version and capabilities; the server responds with *its* capabilities
(which primitives it supports — tools, resources, prompts — and features like notifications); effective
capabilities are the **intersection**. This is a genuine "advertise features before interaction"
mechanism — the distributed-systems analogy realized. **[EVIDENCE]**

**But it advertises the wrong layer for this question.** MCP negotiates *interface primitives* (what can
be called), not *model competence or suitability* (how good the model is, or how to use it well). It
answers "does this server expose a `search` tool?" — never "is this model good at legal reasoning, and
how should I decompose the task?" MCP solves interface discovery; it does not touch capability *guidance*.

### 1.3 A2A (Agent2Agent) Agent Cards — the closest *content*

A2A's **Agent Card** is a published JSON capability manifest: `name`, `description`,
`supportedInterfaces`, `version`, `capabilities`, `defaultInputModes`/`defaultOutputModes`, and
`skills`. A2A reached **1.0 under a committee including Google, Microsoft, AWS, Salesforce, and IBM**,
was contributed to the **Linux Foundation (June 2025)**, and by 2026 supports **signed Agent Cards** and
a multi-language SDK ecosystem with production adoption. **[EVIDENCE]**

This is the strongest existing analog: a vendor-neutral, machine-readable capability advertisement that
*did* achieve multi-vendor adoption. **But it advertises *agent skills*, not *model* execution
guidance.** An Agent Card's `skills` are builder-declared descriptions of what an *agent* offers; they
are not measured suitability, decomposition advice, or operational-weakness descriptors for an
underlying model. And the fields are, like model cards, **human-authored prose in a schema** — a slot
for a claim, not a verified capability. A2A shows the *packaging* problem is solvable; it does not show
the *content* (reliable model guidance) exists.

### 1.4 Documentation standards: Model Cards, System Cards, FactSheets, MRM3, Policy Cards

- **Model Cards** (the Mitchell et al. lineage; HuggingFace metadata) are the canonical model-description
  artifact — intended use, limitations, performance. They are **predominantly human-readable prose**
  with a thin machine-readable YAML header (tags, license, some metrics). Not designed for a platform to
  *reason over* suitability. **[EVIDENCE]**
- **MRM3 (Machine Readable ML Model Metadata, 2025)** is an explicit attempt at a structured,
  machine-readable model-metadata schema — but its emphasis is provenance, environmental impact, and
  knowledge-graph integration, **not task-suitability guidance**. **[EVIDENCE]**
- **System Cards / FactSheets** extend documentation to system-level behavior and ethical risk — again
  human-facing disclosure, not a routing-consumable capability descriptor.
- **Policy Cards (2025)** target *machine-readable runtime governance* for agents — governance, not
  capability advertisement.

### 1.5 Interface/serialization standards: OpenAPI, ONNX, OCI, MLflow

- **OpenAPI** describes *HTTP interface shape* — endpoints, params, schemas. It can describe an LLM API's
  surface but says nothing about model *capability quality*.
- **ONNX** is a model *interchange/graph* format — portability of weights/compute, not capability
  advertisement.
- **OCI** is container packaging/distribution — deployment plumbing.
- **MLflow** is experiment tracking + a model registry — the closest *registry* analog, and notably an
  *internal enterprise* tool, not a cross-vendor advertisement protocol. Its registry stores versions,
  stages, and metrics you record — it does not standardize vendor-published capability guidance.

### 1.6 Survey conclusion

| Layer | Advertised? | By what | Verifiable? |
|---|---|---|---|
| Interface primitives (tools, modalities, streaming) | **Yes** | MCP handshake; provider APIs | Yes (checkable at call) |
| Technical facts (context, price, deployment, rate limits) | **Yes** | Provider APIs; model-card headers | Mostly (poll/observe) |
| Agent skills | **Yes** | A2A Agent Cards | Partially (builder-declared) |
| Model provenance/environmental metadata | **Emerging** | MRM3, model cards | Partially |
| **Execution guidance / task-suitability / operational weaknesses** | **No standard** | (prose model cards only) | **No — not self-certifying** |

**No existing standard solves the specific slice the hypothesis names.** But the survey also shows the
verifiable slices are *already* solved, and the unsolved slice is unsolved because it is *unverifiable*,
not because it is *unnoticed*. Both halves of that sentence matter for the recommendation.

---

## 2. Part 2 — Capability categories

The hypothesis's five categories map cleanly onto the provenance model established across this research
line; the useful work is deciding *which categories a vendor-published protocol could even carry*.

| Category | Examples | Can a *vendor-published standard* carry it reliably? |
|---|---|---|
| **Provider Facts** | context window, pricing, tool support, deployment, rate limits, modalities | **Yes** — authoritative source is the provider; already exposed. Standardizable, mostly redundant with existing APIs. |
| **Measured Facts** | benchmark scores, effective context, schema-validity rate | **Partly** — but validity **decays on every model update** and depends on *who* measured and *how*; a published number without method+date is inadmissible. |
| **Observed Facts** | production latency, hallucination rate, retry frequency, success rate | **No** — inherently *enterprise-specific telemetry*. Cannot be vendor-published; different for every deployment. |
| **Model Guidance** | decomposition advice, preferred workloads, known weaknesses, interaction patterns | **No, reliably** — authored by provider (marketing-biased) or model (self-assessment, unreliable). This is the "missing" slice — and the reason it is missing. |
| **Enterprise Policy** | approved providers, privacy, regulation, customer rules | **No** — authoritative source is the enterprise; must never be vendor-asserted. |

**Additional categories worth naming:**
- **Request-time computed facts** — actual input token count, actual schema complexity, presence of
  images. Computed from the payload; more authoritative than any advertised "capability" for fit
  decisions. Not something a *standard advertises*; something the *runtime measures*.
- **Change/lifecycle facts** — version identity, deprecation status, changelog. Authoritative source is
  the provider; today under-standardized (silent model updates are the norm), and arguably the *most*
  valuable thing a vendor protocol could reliably standardize (Part 5).

**The category-level finding:** of five categories, **only Provider Facts is both vendor-authoritative
and standardizable — and it is already exposed.** The two categories with the highest routing value
(Observed Facts, Model Guidance) are precisely the ones a *vendor-published* protocol *cannot* carry
reliably. This is the structural reason a new cross-vendor standard adds little.

---

## 3. Part 3 — Classes of machine-readable descriptors

The task asks which *classes* of information belong — not which fields. Grouping the candidate
descriptors by their epistemic character (not their topic) is more revealing than listing them:

| Descriptor class | Members | Epistemic character | Belongs in a *standard*? |
|---|---|---|---|
| **Self-certifying interface** | supported capabilities, tool preferences, modality support | Checkable at connect/call; a false claim fails fast | **Yes — and already standardized** (MCP/APIs) |
| **Verifiable-but-decaying measurement** | benchmark-derived suitability, effective limits | True at a measured moment; decays on model change | Only with mandatory method + date + version binding |
| **Non-self-certifying guidance** | preferred workloads, decomposition advice, recommended execution/interaction patterns, retrieval recommendations, fallback recommendations | A false claim fails *silently, downstream* | **This is the crux — carriable, but not trustworthy from any single publisher** |
| **Disclosed limitation** | known operational weaknesses | Valuable *if honest*; publisher has incentive to omit | Only credible if third-party/observed, not self-published |

**The organizing insight (repeating, because it is the whole answer):** descriptor classes should be
sorted by **self-certifiability**, not by topic. The classes that are self-certifying are already
advertised. The classes that are not self-certifying are the ones the hypothesis wants — and their lack
of self-certification is *why* no standard carries them and *why* standardizing their transport would
not make them useful. "Recommended decomposition strategy" is a perfectly reasonable JSON field and a
nearly useless one, because nothing about writing it into a schema makes the recommendation correct or
keeps it correct across a silent model update. **[ARGUMENT]**

---

## 4. Part 4 — Trust and provenance

For each descriptor, *who is authoritative* — and the answer, category by category, is what dooms a
neutral vendor protocol for the high-value slices.

| Descriptor | Authoritative source | Why not the others |
|---|---|---|
| Context window, pricing, deployment, rate limits | **Provider** | Model confabulates them; enterprise/benchmark can't set them |
| Tool/modality/structured-output support | **Provider** (checkable by **runtime**) | Self-report acceptable *only* because it is cheaply verifiable |
| Benchmark suitability scores | **Benchmark** (with method + date) | Provider marketing-biased; decays on update; enterprise may not have run it |
| Latency, hallucination rate, schema validity, retry, success | **Runtime telemetry** | Provider can't know the enterprise's deployment; the number is deployment-specific |
| Decomposition advice, preferred workloads, interaction patterns | **Contested — no clean authority** | Provider = marketing incentive; model = unreliable self-assessment; only *observed* usage patterns are trustworthy, and those are enterprise-private |
| Known operational weaknesses | **Benchmark or runtime** (adversarial), **not** provider | Providers have a structural incentive to under-disclose weaknesses |
| Approved providers, privacy, regulation | **Enterprise** | Must never be vendor-asserted; a vendor claiming your compliance posture is a hazard |

**The provenance verdict.** For every descriptor with real routing value, the authoritative source is
**either the enterprise's own telemetry or an adversarial third party — not the vendor**. A
vendor-*published* capability protocol is therefore authoritative only for the low-value,
already-exposed Provider Facts, and is *structurally the wrong publisher* for everything else. The one
category where the provider is authoritative *and* under-serves today is **lifecycle/change identity**
(Part 5). This is the sharpest possible statement of why "more vendor metadata" is not the answer: the
metadata that matters is not the vendor's to publish. **[ARGUMENT]**

---

## 5. Part 5 — Lifecycle

Descriptors sorted by volatility — because a protocol that ignores volatility advertises stale facts as
current, which is worse than advertising nothing.

| Descriptor | Volatility | Should expire? | Requires verification? | Never auto-learned? |
|---|---|---|---|---|
| Pricing | **High** (changes without notice) | Yes — short TTL | Poll to confirm | — |
| Rate limits / availability | **High** | Yes — short TTL | Runtime observation | — |
| Model version identity | **Event-driven** (silent updates) | On change | **Fingerprint every call** | — |
| Context window / modalities / tool support | Medium (per version) | On version change | Checkable at call | — |
| Benchmark suitability | **Decays on every model update** | Yes — bind to version + date | Re-run on version change | — |
| Latency / hallucination / success telemetry | Continuous | Rolling window | Continuously measured | — |
| Model guidance (decomposition, weaknesses) | Slow but real (shifts with versions) | Yes — bind to version | Verify against outcomes | — |
| Enterprise policy (approved providers, compliance) | Deliberate, human-controlled | No — human-owned | Change-controlled | **Never auto-learned** |

**Two lifecycle findings drive the architecture:**

1. **Version binding is the single most valuable, under-served thing.** Silent model updates invalidate
   *every* measured and guidance descriptor at once. A capability descriptor with no version fingerprint
   is not just stale-prone — it is dangerous, because it presents version-N facts for a
   silently-shipped version N+1. If any slice of a capability protocol is worth standardizing, it is
   **verifiable version identity and change notification** — which is a *provider*-authoritative,
   *self-certifiable* fact, and thus one of the few that both belongs in a standard and isn't fully
   solved today. **[ARGUMENT]**
2. **Enterprise policy must never be learned or advertised by anyone but the enterprise.** It is the one
   category that is human-owned by design (consistent with the governance/optimization plane split in
   the Policy spec). A "capability protocol" that carried policy would invert control.

---

## 6. Part 6 — Enterprise value

Would such a protocol benefit each consumer? Assessed honestly, separating the *interface slice* (already
standardized) from the *guidance slice* (the actual question).

| Consumer | Value of the *interface* slice (MCP/A2A/APIs) | Marginal value of a *new guidance* protocol |
|---|---|---|
| **Model routing** | Already consumes it | Low–Medium — but only if guidance is *verified*; raw vendor guidance adds bias, not signal |
| **Agent frameworks** | **High — already served by MCP/A2A** | Low — agent discovery is the solved part |
| **AI gateways** | Already consume provider metadata | Low — gateways route on price/latency/config, not guidance |
| **Workflow orchestration** | Medium | Low–Medium — decomposition advice *could* help, if trustworthy |
| **Policy engines** | Consume it as one input | **Medium** — but as an *internal, verified* registry input, not a vendor feed |
| **Benchmark systems** | — | **Medium** — a standard *result* format (method+date+version) is genuinely useful and partly what MRM3 targets |
| **Explainability** | — | **Medium** — machine-readable capability provenance improves decision explanations |
| **Multi-provider deployments** | **This is the real beneficiary** | Medium — normalization across heterogeneous providers is the one place a schema earns its keep |

**The value finding.** The consumers that would benefit most from *guidance* capability data
(routing, policy, explainability, multi-provider normalization) benefit **only from a version-bound,
telemetry-verified, provenance-tagged form of it** — which is an *enterprise-internal registry*
property, not a *vendor-published protocol* property. The consumers a vendor protocol would most
naturally serve (agent frameworks, gateways) are **already served** by MCP, A2A, and provider APIs.
Value concentrates exactly where a cross-vendor standard is the *wrong* vehicle. **[ARGUMENT]**

---

## 7. Part 7 — Relationship to existing architecture

Where should capability discovery live? Five options, assessed:

- **Inside provider SDKs.** Wrong publisher for the valuable slices (Part 4); provider-authored guidance
  is marketing-biased and version-fragile. SDKs should expose *facts* (they do), not *suitability*.
- **A new standard outside the orchestration layer (a neutral protocol).** This is the Outcome-4
  proposal. It duplicates MCP/A2A/APIs on the verifiable slice and cannot carry the unverifiable slice
  credibly (Parts 3–4), and faces inverted adoption incentives (Part 8). **Rejected.**
- **Inside the orchestration layer.** Puts capability data on the hot path and couples it to one
  runtime; the same route-time/trust objections raised against runtime capability *negotiation* apply.
- **Inside enterprise registries.** **Correct.** Capability discovery belongs as an *enterprise-owned
  normalization layer* that **ingests** the existing standards (MCP handshake for interface facts,
  provider APIs for technical facts, benchmark results for measured facts) and **adds** the guidance
  layer as internal, telemetry-verified, provenance-tagged, version-bound data. This is precisely the
  **capability registry** the Model Selection Policy already defines — not a new artifact.
- **Not exist at all.** Too strong: the *normalization* need across heterogeneous providers is real.

**The architectural verdict.** Capability discovery is **an ingestion-and-normalization function of the
enterprise capability registry**, not a new cross-vendor protocol and not an orchestration-layer
feature. It *consumes* the standards that already exist and *owns* the residual that no standard can
publish. The right relationship to the existing platform is therefore: **capability discovery = the
population pathway of the Policy Engine's registry**, drawing verifiable facts from MCP/A2A/provider
APIs and enterprise-private facts from telemetry. There is nothing left over to standardize externally.
**[ARGUMENT]**

---

## 8. Part 8 — Commercial analysis

Would such a protocol become an implementation detail, a product capability, an industry standard, or
merely another metadata schema? And would anyone adopt it?

**Adoption incentives are the decisive analysis.** Compare against the two standards that *did* achieve
multi-vendor adoption:

- **MCP and A2A succeeded because they are *usage-expanding*.** More tool connections and more delegated
  agent work mean more inference sold. Vendors and a Linux-Foundation committee backed them because
  interoperability here *grows the pie* for everyone. **[EVIDENCE]**
- **A neutral model-capability-*comparison* protocol is *substitution-expanding*.** Its explicit purpose
  is to let enterprises reason about heterogeneous models "without hard-coding provider-specific
  knowledge" — i.e., to make models interchangeable and comparable. That erodes vendor lock-in and
  invites a capability bake-off. A rational vendor **under-adopts or waters down** such a standard,
  especially for the fields that expose weaknesses (Part 4). This is the classic dynamic where the party
  asked to publish comparable specs is the party harmed by comparability. **[ARGUMENT]**

**Consequences:**
- As an **industry standard**: unlikely to reach honest, adopted maturity for the *guidance* slice,
  precisely because the authoritative-and-motivated publisher does not exist. The interface slice is
  already standardized, so there is little left to standardize that vendors would populate truthfully.
- As a **product capability**: plausible and defensible — an enterprise platform that *normalizes*
  heterogeneous providers into a verified, version-bound capability registry is valuable **because** the
  vendors won't do it neutrally. The value accrues to the *aggregator*, not to a *standard*.
- As **merely another metadata schema**: this is the failure mode to avoid — a JSON schema for fields
  no one populates reliably (the fate risk shared by MRM3-style efforts if adoption lags).
- As an **implementation detail**: for the interface slice, yes — it already is one, inside MCP/A2A.

**Commercial verdict.** The durable commercial object is **not a standard** but an **enterprise-owned
capability-normalization capability** — which is a *product* property of a platform, not an industry
protocol. Whoever aggregates and verifies heterogeneous-provider capability data captures the value
*because* the ecosystem's incentives prevent a neutral standard from doing it. **[ARGUMENT]**

---

## 9. Part 9 — Recommendation and falsifiers

### 9.1 Recommendation

Against the four possible outcomes:

> **A blend of Outcome 2 and Outcome 3 — "existing standards already solve the verifiable interface
> slice (MCP capability negotiation, A2A Agent Cards, provider APIs); the residual guidance/suitability
> slice is genuinely unstandardized but is best served as *internal enterprise metadata* inside a
> capability registry, not as a new cross-vendor interoperability standard." Explicitly not Outcome 4,
> and not Outcome 1.**

The reasoning, compressed:

- **Not Outcome 1 (no problem):** there *is* a real, uncovered slice — machine-readable execution
  guidance, task-suitability, operational weaknesses, and (under-served) verifiable version identity.
  Heterogeneous-provider normalization is a genuine enterprise pain.
- **Not Outcome 4 (missing interoperability layer worth standardizing):** the uncovered slice is
  uncovered *for structural reasons* — it is non-self-certifying (Part 3), its authoritative source is
  enterprise telemetry or adversarial third parties rather than vendors (Part 4), and vendor adoption
  incentives are inverted (Part 8). A new neutral protocol would duplicate MCP/A2A on the verifiable
  part and go unpopulated (or populated dishonestly) on the valuable part.
- **The honest middle (Outcome 2→3):** treat capability discovery as the **ingestion-and-normalization
  pathway of the enterprise capability registry** — consuming the interface facts the existing standards
  already advertise, and *owning* the guidance/observed slice as internal, verified, version-bound,
  provenance-tagged data. This is a *product capability*, not a *standard*.

**On the framing question ("real architectural gap, or duplicate of existing metadata?"):** it is a
**duplicate on the interface slice and a real gap on the guidance slice — but the real gap is not
closable by a standard**, because the content is not self-certifying and no motivated authoritative
publisher exists. The gap is closable only *internally*, by an aggregator that verifies against its own
telemetry. So "Capability Discovery" is a real *enterprise-internal* need and a largely illusory
*industry-standard* opportunity.

### 9.2 What would falsify this recommendation — both directions

**Evidence that would push the conclusion *up* toward Outcome 4 (a standard worth building):**
- A neutral body (as the Linux Foundation did for A2A) ships a machine-readable model-capability manifest
  carrying *suitability/guidance* fields, **and** multiple vendors populate it with **verifiable,
  version-bound, weakness-inclusive** claims, **and** enterprises demonstrably route on it. That would
  refute both the "not self-certifying" and the "adoption-incentives-inverted" arguments at once.
  **[FALSIFIER]**
- MCP or A2A extend their capability objects to include model-*quality* suitability descriptors and reach
  adoption — showing the usage-expanding vehicles can absorb the guidance slice. **[FALSIFIER]**

**Evidence that would push the conclusion *down* toward Outcome 1/2 (even less of a gap):**
- MRM3 or a successor already covers the guidance/suitability fields *and* achieves real adoption — the
  slice is then solved, not missing. **[FALSIFIER]**
- Enterprises show they never need cross-provider capability normalization because they standardize on
  one or two providers in practice — then even the internal-registry value evaporates and there is no
  meaningful problem. **[FALSIFIER]**

Until such evidence appears, the disciplined position is: **do not build or back a new cross-vendor
capability-advertisement protocol. Build the capability registry's ingestion layer — consume MCP/A2A/
provider metadata for the verifiable facts, verify guidance against telemetry, bind everything to model
version — and treat the residual as owned enterprise metadata, not an industry standard.** The gap is
real; the standard is not the way to close it.

---

## 10. References

Part 1 survey grounding (accessed July 2026):

- Model Context Protocol — Architecture overview and capability negotiation:
  https://modelcontextprotocol.io/docs/learn/architecture
- Handshaking and Capabilities Negotiation in MCP (APXML):
  https://apxml.com/courses/getting-started-model-context-protocol/chapter-1-architecture-and-fundamentals/capabilities-negotiation
- A survey of agent interoperability protocols (MCP, ACP, A2A, ANP), arXiv:2505.02279:
  https://arxiv.org/pdf/2505.02279
- A2A Agent Card — capability manifest specification (VIPS Learn):
  https://learn.engineering.vips.edu/agent-protocols/a2a-agent-card-spec
- Agent Skills & Agent Card — A2A Protocol tutorial:
  https://a2a-protocol.org/latest/tutorials/python/3-agent-skills-and-card/
- Agent2Agent (overview), IBM: https://www.ibm.com/think/topics/agent2agent-protocol
- MRM3: Machine Readable ML Model Metadata, arXiv:2505.13343: https://arxiv.org/pdf/2505.13343
- Policy Cards: Machine-Readable Runtime Governance for Autonomous AI Agents, arXiv:2510.24383:
  https://arxiv.org/pdf/2510.24383
- Human-aligned AI Model Cards with Weighted Hierarchy Architecture, arXiv:2510.06989:
  https://arxiv.org/pdf/2510.06989

---

*End of investigation — Version 1.0.*
