# ugence-reasoning-method-advisor

Slice 2 of the reasoning-method governance thread
(`docs/architecture/REASONING_METHOD_ADVISOR_SLICE2_COMMISSIONING_SPEC.md`,
owner-ratified as amended 2026-09-02): a **research-only, deterministic,
rule-derived** design-time Reasoning Method Advisor.

`advise(request, *, advised_at) -> advisory` is a pure function of the
developer's `TaskProfile`, an optional governed `TaskClassIdentity`, the
`ReasoningMethodCatalog`, a versioned, canonically ordered `RuleSet` (all from
`ugence-reasoning-method-governance`) and a caller-supplied, timezone-aware
`advised_at`; it reads no clock. `validate_against_request` binds an advisory
to the request it answers, so an unclassified request can never be presented
as governed. The package imports only public names from other distributions;
its canonicalization is package-local and verified against vectors. It returns the qualifying set (zero,
one or many methods), every inclusion and exclusion reason, trade-offs between
multiple qualifiers, and a primary **only when exactly one method qualifies**.
Rule count, rule priority and traversal order never manufacture a winner.

Every label is `RULE_DERIVED`. A request without a governed task class is marked
`UNCLASSIFIED_EXPLORATORY` and `INELIGIBLE_UNCLASSIFIED`: no benchmark comparison, no
configuration binding, no production authority.

## Slice 3 — product entry (0.2.0; signed results 0.3.0)

Under `docs/architecture/ADR_UGENCE_REASONING_METHOD_PRODUCT_ENTRY.md` (rulings
RM-1..RM-3, owner-ruled 2026-09-06) an advisory may enter the product **through a
separate record**, never by changing shape:

- The slice 2 request and advisory are **unchanged, field for field**. Every advisory
  is still `COMPARISON_EVIDENCE_ABSENT` / `RESEARCH_ONLY`, and every historical
  digest — including a preregistered pilot manifest that embeds one — still verifies.
- `admit(advisory, request, result, admitted_at=...)` takes the comparison engine's
  `ReadinessComparisonResult` — never a bare bundle of assessments — and returns a
  `ReasoningMethodAdvisoryAdmission`: `COMPARISON_EVIDENCE_PRESENT` / `ADVISORY_INPUT`,
  digest-bound to the advisory **and to the result** (`comparison_result_digest`),
  restating the qualifying set and primary, and citing the admitting assessments'
  digests as `evidence_refs` — **only when every qualifying method** has a sufficient
  assessment (`SUFFICIENT_PARETO_EFFICIENT` or `SUFFICIENT_RESOURCE_DOMINATED`) for
  exactly its method reference. A result naming any engine but
  `ugence-readiness-comparison` (mirrored as `COMPARISON_ENGINE_IDENTITY`; this package
  still imports nothing from the engine) is unbound. `ComparisonEvidence` is the
  internal shape the coverage rule reads. `validate_admission(admission, advisory,
  result)` replays all of it at any later time.

Evidence never creates a qualifier: the rule set decides who qualifies; the evidence
decides whether that result may leave research. Partial coverage, no qualifier, or
only `COMPARISON_EVIDENCE_ABSENT` assessments — refused as
`RESEARCH_ONLY_REFUSED_IN_PRODUCT`, which is how the `rules.research.v0` fixture is
kept out of the product without naming it. An `INSUFFICIENT_QUALITY` assessment for a
qualifying method — refused as `COMPARISON_EVIDENCE_CONTRADICTED`. Evidence for another
task class, another catalog, or presented twice — `COMPARISON_EVIDENCE_UNBOUND`. An
unclassified advisory is never admitted.

`to_proposer_input(admission)` is the one-way bridge to the Agentic Proposer's typed
`ReasoningMethodAdvisoryInput`: references, method identifiers and evidence digests —
input, never authority — refused for a bare advisory. This package knows the proposer's
input shape; the proposer imports nothing from here.

**Signed results (0.3.0, SCR-1,
`docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md`).** The engine's
signature over a result is verified *outside* this package — by
`ugence-reasoning-method-result-attestation` through the Trusted Evidence Authority's
anchors — and handed to `admit` as a typed fact, `VerifiedResultSignature`
(`result_digest`, `signer_identity`, `signer_key_id`, `verification_receipt_digest`,
`verifier_identity`, `verified_at`). `admit(..., verified=..., require_signature=True)`
refuses an unsigned result (`COMPARISON_RESULT_UNSIGNED`), a record whose digest is not
this result's (`COMPARISON_RESULT_SIGNATURE_MISMATCH`) and a record naming another signer
(`COMPARISON_EVIDENCE_UNBOUND`); the admission (schema `advisory_admission.v3`) cites the
record by `result_signature_receipt_digest`, `None` in the research posture, and the
bridge carries it with the C6 prefix. This package still imports neither the engine, the
attestation package nor the authority: it trusts the composition root's verification, and
an auditor re-verifies from the cited digest outside it. No key for any comparison engine
exists, so today `require_signature=True` refuses every result — the correct behaviour.

**What citing the result does and does not establish.** A hand-assembled tuple of
assessments can no longer be admitted, and the result contract binds every assessment
to one engine identity and one request digest. A *forged result* remains possible
until results are signed and verified by the Trusted Evidence Authority `[G]`.

**What no evidence exists for yet `[G]`.** The fit assessments in this package's tests
are synthetic fixtures proving the mechanism. Real comparison evidence comes from a
comparison study over `ugence-readiness-comparison`, which this package still never
imports and whose results it never ingests: it is handed assessments, and it checks them.

Still excluded by ruling: LLM-based selection, `BENCHMARK_DERIVED` claims, numeric
predictions, scalar cost labels, approval, configuration mutation, Constitution
binding, envelope issuance, and any change to Agent Workforce Composer, Agent Runtime,
readiness classification, ROI or the advisory composite. The former exclusion of "any
change to Agentic Proposer" is lifted by RM-1. The rule set `rules.research.v0` ships
as a **test fixture only**; it is a transcription of the experimental selector's
mapping and is provenance, not evidence of correctness.
