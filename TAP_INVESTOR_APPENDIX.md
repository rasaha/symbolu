# TAP — Investor Appendix

*Companion to `TAP_VC_BRIEF.md`. Same evidence discipline: every quantitative statement corresponds to a
committed repository artifact; nothing here claims production readiness, external validation, or ROI. Ugence
Labs, July 2026.*

---

## 1. One-Page Executive Summary (email-ready)

**Subject: Ugence Labs — TAP: the independent assertion-governance layer for enterprise AI**

Enterprises can generate fluent AI answers but cannot independently prove an answer was supported before it
was delivered — today that judgment is made by the same model that produced it. **TAP (Truth Assurance
Platform)** is an external, model-independent layer that evaluates a *completed* AI response and returns
**DELIVER**, **QUALIFY**, or **ABSTAIN**, with a replayable audit record. It governs what an AI *says* — the
assertion-side analogue of our action-governance layer (ActionGate) inside the Ugence AI Control Plane.

**Why now.** As AI moves into regulated and high-consequence work, the binding question shifts from *"can
the model answer?"* to *"can the enterprise prove the answer was admissible?"* No foundation model, RAG
system, or agent framework provides an independent authority over assertions at the delivery boundary.

**What is real today.** A falsification-first research program (preregistered, hash-pinned, deterministic)
established the mechanism and architecture on synthetic corpora. Its most valuable outputs are disciplined
negative results: *how* text is decomposed moves the synthetic safety endpoint by an order of magnitude
(triple-extraction 0.864 vs preservation-first 0.068 unsafe delivery on an 832-example corpus), and
heavyweight components were **rejected** because a minimal design matched them. The program also names its
own hard limit: correlated "no-tell" failures are uncatchable by any evidence composition and are routed to
human review — never hidden.

**What is not yet proven — stated plainly.** No human/expert validation, no real-customer data, no
production deployment, no measured ROI. The next value-creating milestone is a **bounded enterprise shadow
deployment** on real data with expert comparison and preregistered acceptance thresholds — the specific use
of investment.

**The thesis.** Own the independent assertion-governance authority for enterprise AI — the trust
infrastructure that makes consequential AI admissible — as that authority becomes a deployment prerequisite.

*Details, evidence citations, and an explicit maturity ladder: `TAP_VC_BRIEF.md`.*

---

## 2. One-Slide Narrative — "Why TAP Exists"

```
  WHY TAP EXISTS

  Foundation models GENERATE.  Nothing independently GOVERNS what they deliver.

     User  →  LLM / agent  →  [ TAP ]  →  DELIVER · QUALIFY · ABSTAIN  →  Enterprise workflow
                                 │
                                 └─ external · claim-level · scope-preserving · evidence-grounded · audited

  THE GAP:   Today the model that writes the answer also certifies the answer.
             In regulated / high-consequence work, that is not admissible.

  THE SHIFT: "Can the model answer?"  →  "Can the enterprise prove the answer was supported?"

  TAP:       The independent authority that decides whether an AI assertion may be delivered —
             the assertion-side peer of action governance (ActionGate) and operational safety (ACP).

  STATUS:    Architecture specified · mechanisms prototyped · synthetic evaluation complete ·
             human / external / production validation PENDING (stated, not hidden).
```

---

## 3. Five Investor FAQs (evidence-backed)

**Q1. Isn't this just a hallucination detector or fact-checker?**
No. Those are point tools that score a claim true/false, usually on the generator's own signals. TAP is an
**external delivery authority** that (a) decomposes a response *without altering its meaning*, (b) evaluates
each claim against evidence, and (c) returns DELIVER/QUALIFY/ABSTAIN with an audit record — independent of
the model. The repository shows why decomposition-then-check is the right frame: dropping scope during
decomposition produces a *downstream-invisible* failure (`claim_integrity`), which a fact-checker operating
after decomposition cannot recover.

**Q2. What have you actually proven versus specified?**
Proven, on synthetic/deterministic corpora: (i) decomposition *method* dominates the safety endpoint
(OpenIE 0.864 vs preservation-first 0.068, `ci_corpus_v1`, 832 examples); (ii) a minimal decomposer matches
a heavyweight one, so complexity was rejected; (iii) an evidence stack drives modeled correlated-failure
escape to 0.000 where signal-only baselines escape 0.67–1.00 (`evidence_assurance`); (iv) a thin risk-aware
composition beats single signals and a bespoke engine at the delivery decision (`assertion_governance`).
Specified but not built into a running product: the full end-to-end pipeline (`truth_assurance_pipeline` —
an architectural framework that "makes no empirical performance claims").

**Q3. Do the synthetic numbers transfer to real data?**
We do not claim they do. Each study labels its rates as **construction-bounded** and states that only the
*mechanism and ordering* are expected to transfer, not the exact figures. That is precisely why the next
milestone is a real-data shadow deployment with expert comparison — to establish transfer rather than assume
it.

**Q4. Where does TAP sit relative to RAG, guardrails, and agent frameworks?**
Complementary, not competitive. RAG improves evidence *into* generation; guardrails filter by rules;
agent frameworks produce more assertions to govern. TAP consumes such signals and adds the missing function:
an independent, claim-level, evidence-grounded delivery decision at the boundary. Within Ugence it is the
assertion-side peer of ActionGate (actions) and ACP (operational safety).

**Q5. What exactly would our capital fund?**
One bounded enterprise shadow deployment: a single domain and claim class, customer-approved evidence,
shadow mode (decides, never enforces), decisions compared to expert reviewers against **preregistered**
acceptance thresholds (unsupported-delivery rate, qualification precision, abstention burden, latency/cost,
reviewer agreement); plus the enterprise evidence connectors and replayable decision records that pilot
requires. It converts architectural evidence into external efficacy evidence.

---

## 4. Five Likely Objections and Evidence-Based Responses

**Objection 1 — "Frontier models will just get accurate enough to make this unnecessary."**
Response: Accuracy of *generation* does not create an *independent* authority over delivery, and a model
certifying its own output is the structural weakness regardless of its accuracy. TAP's value is
model-independence and auditability at the boundary; it also *benefits* from better models as cleaner inputs.

**Objection 2 — "The evidence is all synthetic — this could be a lab artifact."**
Response: Correct that it is synthetic, and we say so on every page. But the load-bearing findings are
*directional and structural* (decomposition method dominates; correlated failure is uncatchable by
composition; minimal design matches heavyweight), and the studies are preregistered and hash-pinned so they
cannot be retrofitted. We are asking for capital to test transfer on real data — not asserting it.

**Objection 3 — "Abstention will make it too conservative to use."**
Response: The architecture is explicitly risk-concentrated: high-risk assertions carry the governance load,
low-risk supported content passes without unnecessary qualification. Abstention burden is one of the
**preregistered acceptance metrics** for the shadow pilot, not an afterthought.

**Objection 4 — "You admit correlated 'no-tell' failures escape 100% — isn't that fatal?"**
Response: That is a property of *any* metadata-based method, and disclosing it is a strength. TAP is
positioned as defense-in-depth with a **human/external-verification route** for the no-tell residual — never
as a sole safety layer. A vendor claiming to catch everything would be the one to distrust.

**Objection 5 — "There's no moat; a model provider could add a delivery check."**
Response: The defensible asset is the *system-level* combination — scope-preserving decomposition, claim and
failure taxonomies, evidence-state modeling, risk-tiered qualification/abstention policy, replayable audit,
and integration with action governance and operational safety — not a single check. Model-independence is
itself the wedge: enterprises want an authority that is *not* the provider grading itself. Customer
deployments then compound the moat (Section 5).

---

## 5. Evidence & Readiness Table

*Evidence strength: **Strong** = preregistered synthetic result, directional transfer expected · **Bounded**
= real but explicitly construction-limited · **Architectural** = specified/reasoned, not yet measured.
Commercial readiness is deliberately conservative.*

| Claim | Repository evidence | Evidence strength | Commercial readiness |
| --- | --- | --- | --- |
| Decomposition method dominates delivery safety | `claim_integrity` `ci_corpus_v1` (832 ex): OpenIE 0.864 vs preservation-first 0.068 unsafe delivery | Strong (synthetic) | Mechanism validated; not product-proven |
| Minimal decomposer ≈ heavyweight (complexity rejected) | 15-probe component ties 2-probe splitter at 0.068; ref-resolution 0.091→0.000 secondary | Strong (synthetic) | Design decision made |
| Residual scope failures reducible by a small gated rule | `scope_integrity`: general-corpus residual 0.068→0.000; 102 tests; ungated variants 0.218–0.472 | Strong (synthetic) | Mechanism validated |
| Evidence stack catches correlated failure signals miss | `evidence_assurance` `ea_corpus_v1`: cf-escape 0.000 vs baselines 0.67–1.00; false-block 0.114 | Strong (synthetic) | Shadow-mode design only |
| Correlated "no-tell" failure is uncatchable by composition | `evidence_assurance`: disclosed ceiling S23 escape = 1.000 (shipped disclosure) | Strong (negative result) | Defines human-in-loop routing |
| Delivery decision reduces to a thin risk-aware composition | `assertion_governance` `age_corpus_v1`: single signals 0.31–0.38 agreement; composition 1.00 agreement, 0.00 escape; engine not required (dominated 6–0) | Strong (synthetic) | Design decision made |
| End-to-end TAP pipeline | `truth_assurance_pipeline`: architecture + E1–E5 layer studies, `PASS_WITH_LIMITED_CLAIM` | Architectural | Not integrated as a product |
| Real-world efficacy / human agreement / ROI | — none — | Not established | Pending shadow deployment |

---

## 6. Provenance Note

Component evidence is drawn from the committed evaluation and decision documents under `docs/claim_integrity/`,
`docs/scope_integrity/`, `docs/evidence_assurance/`, `docs/assertion_governance/`,
`docs/assertion_gate_robustness/`, `docs/relationship_claim_validation/`, and
`docs/truth_assurance_pipeline/`. All corpora referenced are synthetic, self-authored, and deterministic;
"LLM"/"parser" methods in those studies are deterministic local stand-ins, labelled as simulated. No figure
in this appendix originates outside the repository.
