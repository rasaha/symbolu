# Truth Assurance Platform (TAP) — VC Brief

**Ugence Labs | Assertion Governance for Enterprise AI**
*An external, model-independent control layer that decides whether a completed AI response is sufficiently supported to deliver — or must be qualified or withheld — before it reaches a user.*
*Version 1.0.0 — July 2026 (external / evidence-based) · Status: emerging capability*

> **Product family.** TAP is the **assertion-side** control in the **AI Control Plane** of the Ugence
> Labs platform (canonical taxonomy in `UGENCE_PLATFORM_OVERVIEW.md`). It is the analogue of
> **ActionGate** (see `ACTIONGATE_VC_BRIEF.md`): **ActionGate governs what an AI *does*; TAP governs what
> an AI *says*; ACP decides whether an authorized action is operationally safe now.** TAP consumes the
> same evidence-obligation machinery as the Model Selection / governed-inference layer (see
> `MODEL_SELECTION_POLICY_VC_BRIEF.md`). This brief describes TAP as it exists in the repository today —
> its specified architecture, the falsification-first component studies completed, and, plainly, what is
> **not** yet proven.

---

## Page 1 — The Problem

### Enterprises can generate fluent AI answers; they cannot independently prove those answers are supported.

Current approaches largely rely on **the same model that produced the answer to grade its own answer** —
a structural governance weakness. Retrieval, agent frameworks, and larger models improve *generation* and
*evidence access*, but none provides a **model-independent enterprise authority over assertions**. For
regulated and high-consequence workflows the question is not "can the AI answer?" but "can the enterprise
prove the delivered assertion was **supported**, **qualified when uncertain**, or **withheld when evidence
was insufficient** — and replay that decision under audit?"

### The Ugence answer

TAP is an **external assertion-governance layer** that evaluates a *completed* response before delivery
and returns one of three outcomes:

- **DELIVER** — the assertion is sufficiently supported.
- **QUALIFY** — deliver with explicit scope, limits, or uncertainty.
- **ABSTAIN** — evidence is insufficient or contradictory; withhold / escalate.

TAP does not generate the response; it governs whether the response may leave the system, regardless of
which model, provider, agent framework, or application produced it. Its founding design principle comes
directly from our own completed study (below):

> **Evidence assurance is trustworthy only when semantic scope is preserved before verification begins.**

---

## Page 2 — Architecture

```
   Completed AI response (any model / provider / agent framework)
        │
        ▼
   ClaimIntegrity        ── decompose safely, PRESERVATION-FIRST
     • conservative splitting (never strip negation, modality,
       qualifiers, attribution, numeric limits, temporal scope, exceptions)
     • reference resolution · non-assertive filtering · scope validation
        │
        ▼
   ScopeIntegrity        ── gated hybrid for exception/scope-spanning conjunctions
     • split only when attachment is provable, else preserve-and-flag (INDETERMINATE_SCOPE)
        │
        ▼
   EvidenceAssurance     ── is each claim supported / contradicted / stale / insufficient?
     • provenance + independence + freshness; correlated-failure aware
        │
        ▼
   AssertionGate         ── risk-aware delivery decision (thin composition)
     • evidence support + claim strength + risk tier → DELIVER · QUALIFY · ABSTAIN
        │
        ▼
   Audit record          ── original response, claims, evidence relations, reason codes, outcome (replayable)
```

TAP separates four decisions kept under distinct authorities across the platform: **context** (what may
enter reasoning), **assertion** (TAP — is the output supported), **action** (ActionGate — is the act
authorized), and **operational safety** (ACP — is it safe now). The Truth Assurance Pipeline
specification (`docs/truth_assurance_pipeline/`) further separates *relationship truth*, *governance
truth*, *claim truth*, and *response truth* as distinct problems with distinct corpora and failure modes —
the architecture explicitly forbids conflating them.

---

## Page 3 — Evidence (what has been studied) & honest limitations

**Read this section as a whole.** Every result below is from **our own repository**, on **synthetic,
self-authored, deterministic** corpora with preregistered, hash-pinned success/kill criteria (a
falsification-first program). **There is no human/inter-annotator validation, no real-customer data, and
no production-efficacy result anywhere in TAP today.** The value proven so far is **architectural and
mechanism-level**; exact rates are construction-bounded and are stated as such in each study.

### The load-bearing research finding (ClaimIntegrity, `ci_corpus_v1`: 832 examples / 1,144 gold claims)

- **How you decompose dominates safety by an order of magnitude.** Triple/parser extraction (OpenIE/SPO)
  causes **0.864** unsafe delivery; preservation-first sentence splitting causes **0.068** — identical
  across every risk tier. Dropping negation, numeric limits, exceptions, or population scope reaches
  unsafe delivery (0.09–0.21 per error type) and **downstream never catches it** — the gate faithfully
  evaluates an altered claim because it cannot see the original. **This is the study's positive result: a
  decomposition error is a "no-tell" failure.**
- **Complexity was rejected on its own evidence.** A heavyweight 15-probe decomposition component **ties a
  2-probe splitter at 0.068** on the primary endpoint; its only distinct benefit is dangling-reference
  resolution (**0.091 → 0.000**, a secondary endpoint). Decision: keep preservation-first splitting +
  reference resolution; **prohibit clause/triple/aggressive extraction**; retain per-dimension checkers
  only as an **audit of untrusted extractors**.

### Supporting component studies (each synthetic, deterministic, preregistered)

- **ScopeIntegrity** — a small **gated hybrid** (≈4 regex rules) removes ClaimIntegrity's residual on the
  general corpus **0.068 → 0.000** with no rise in false-rejection. Honesty flag recorded in the study:
  ungated variants are *catastrophic* on the general corpus (**0.218–0.472**) even though they look best on
  a purpose-built scope corpus — the claim rests on the un-rigged corpus. **102 tests pass.**
- **EvidenceAssurance** (`ea_corpus_v1_1`: 624 cases) — catches **correlated** grounding+entailment
  failures that signal-composition cannot: single-signal and even a learned comparator escape
  **0.667–1.000**; the component's correlated-failure escape is **0.000** (its 0.114 false-block is
  entirely NLI-proxy noise). **Disclosed hard limit:** a no-tell failure with fabricated provenance escapes
  **100%** — a property of *any* metadata-based method, not a tuning gap.
- **AssertionGate** (`age_corpus_v1` / `agr_corpus_v1`) — single signals fail the delivery decision
  (confidence 0.31, grounding 0.38); a risk-aware composition reaches **0.97–1.00 agreement with 0.00
  unsupported-escape**. **Anti-circularity honesty:** a *trivial* grounding+entailment+risk rule reproduces
  ground truth and **dominates the bespoke engine 6–0**, so the verdict is **"high-risk domains only, as a
  thin composition — not a novel engine."** The noisy-signal follow-up confirms **no method is
  safe when grounding and entailment fail together** — correlated/silent failure is unsolved by any
  composition tested.
- **Claim-validation prototype** (`relationship_claim_validation`, synthetic) — precision **0.417 → 1.000**,
  false acceptances **28 → 0** — but its own verdict states plainly: *"perfect scores are by construction …
  production deployment: NO."*

### What is NOT proven (stated, not hidden)

- **No production efficacy. No external/enterprise validation. No third-party validation. No measured
  avoided-incident ROI. No calibrated cross-domain operation.** Corpora are self-authored; "LLMs"/parsers
  in the studies are **deterministic local stand-ins, labelled as simulated**.
- The full **Truth Assurance Pipeline** (`docs/truth_assurance_pipeline/`) is an **architectural framework
  proposal** that *"makes no empirical performance claims"* and *"does not claim hallucination
  elimination."* Its per-layer experiments (E1–E5) each pass their preregistered gates but carry the
  verdict **`PASS_WITH_LIMITED_CLAIM`** (mechanism validation on synthetic data; two disclose they are
  *development*, not blind-holdout, evaluations).

---

## Page 4 — Positioning, moat, go-to-market, ask

### Positioning — the assertion-governance boundary

TAP is **not** another retrieval system, a model self-confidence score, prompt-based fact-checking, a
generic guardrail, a moderation layer, or an action-authorization system. Its differentiation is the
*combination*: external assertion governance · claim-level evidence evaluation · **semantic-scope
preservation** · explicit qualify/abstain outcomes · replayable provenance · model- and
framework-independent control.

| Category | Typical focus | TAP differentiation |
| --- | --- | --- |
| Retrieval / RAG | Fetch evidence for generation | Governs the *completed* assertion against evidence, after generation |
| Model self-confidence | The generator grades itself | Independent authority — the generator does not grade its own output |
| Guardrails / moderation | Prompt / output filtering, policy strings | Claim-level evidence support with qualify/abstain and audit |
| Fact-checking tools | Binary true/false on a claim | Scope-preserving decomposition + qualification when evidence is narrow |
| Action-authorization (ActionGate) | What the AI *does* | What the AI *says* — the assertion-side analogue |

### Moat / defensibility

Not the phrase "fact-checking." The defensible asset is the **system-level combination**:
semantic-preservation machinery; claim & semantic-failure taxonomies; evidence-state modeling;
qualification/abstention policy; risk-tiered thresholds; replayable audit/provenance; and integration with
ActionGate and the broader control plane. Over time, customer-specific evidence graphs, reviewer outcomes,
calibration histories, and failure signatures compound the moat. The falsification-first record — a program
that **rejected its own unnecessary complexity** and **named the genuine hard limit** (correlated/no-tell
failures unsolved by any method) — is itself a credibility asset for regulated buyers.

### Go-to-market — a bounded assurance layer, not a universal truth engine

**Phase 1 (wedge):** assertion assurance for enterprise AI producing **regulated or customer-facing
reports** — one domain, one claim class, customer-approved evidence, **shadow mode**, decisions compared
against expert reviewers. **Phase 2:** governed production recommendations with humans retained for
indeterminate/high-risk claims. **Phase 3:** repeatable deployment package across multiple model providers.
Initial targets: financial services, healthcare/life sciences, legal & compliance, insurance, enterprise
knowledge systems, government/regulated industries, and agent-generated reports.

**Business value paths:** deployment enablement (use AI where unverified output is otherwise inadmissible)
· risk reduction (fewer unsupported assertions reaching users) · review efficiency (concentrate human
review on indeterminate/high-risk claims) · platform leverage (one assurance layer across many models).
*Economic ROI is not yet quantified; avoided-incident value is customer-specific.*

### Key risks

Evidence may be incomplete/conflicting/stale; aggressive abstention can make the system safe but unusable;
claim + evidence analysis add latency and cost; thresholds calibrated in one domain may fail in another;
incorrect decomposition can create assurance over the wrong claim; and — proven in our own studies —
**correlated/silent failures are not fully controllable by any current method**, so TAP is positioned as
defense-in-depth, never a sole safety layer.

### The ask

Fund the move from **validated mechanism to bounded real-data evidence**: a shadow-mode pilot on real
customer data in one regulated workflow, with expert comparison and explicit acceptance thresholds
(unsupported-delivery rate, qualification precision, abstention burden, latency/cost, reviewer agreement);
enterprise evidence connectors; replayable decision records; and domain-specific assertion policies. The
next value-creating step is **not** broader feature development — it is one honest, bounded pilot that
converts architectural evidence into external efficacy evidence.

### Investment thesis

As enterprises move from AI experimentation to consequential deployment, the limiting question shifts from
*"can the model generate an answer?"* to *"can the enterprise independently determine whether that answer is
sufficiently supported to deliver?"* TAP is the missing assertion-governance boundary — complementing action
governance (ActionGate) and operational safety (ACP). Its current value is **architectural and strategic,
not commercially proven**, and this brief says so plainly. **Ugence Labs is building that boundary.**

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Components: `claim_integrity/` (ClaimIntegrity) · `scope_integrity/` (ScopeIntegrity) · `evidence_assurance/` (EvidenceAssurance) · `assertion_governance/` + `assertion_gate_robustness/` (AssertionGate) · `relationship_claim_validation/` (claim-validation prototype) · `truth_assurance_pipeline/` (TAP architecture + E1–E5 layer studies)*
*Status: emerging capability · architecture specified · falsification-first synthetic studies complete · human validation NONE · real-data / external / production efficacy NOT established*
