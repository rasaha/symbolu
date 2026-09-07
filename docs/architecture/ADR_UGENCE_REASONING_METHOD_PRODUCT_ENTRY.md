# ADR — Reasoning-method advisor: product entry

**Status:** ratified and implemented, 2026-09-06. Owner rulings RM-1 to RM-3 below were
given in one instruction on 2026-09-06 and are enacted in this change set. Labels:
`[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Can `reasoning-method-governance` and `reasoning-method-advisor` move from the
research-only module into the proposal-and-advisory module (M3 of
`docs/UGENCE_PREVENTIVE_DETECTIVE_MODULE_MAP.md`) without violating the two rules that
kept them out — the advisor's own "excluded by ruling" list and roadmap §11.2's "no
research-only package in the product"? **Yes, by adding a record rather than changing
one.** An advisory stays research-only by construction; a separate, digest-bound
*admission* lets it enter the product only when comparison evidence covers every method
the rule set made qualify; and the Agentic Proposer records that admission as typed
input, never as authority.

## 2 — The three rulings, as given

| # | Ruling | Enacted by |
|---|---|---|
| RM-1 | Lift the advisor's exclusion "any change to Agentic Proposer". | `packages/capabilities/reasoning-method-advisor/README.md` (exclusion paragraph rewritten; the other exclusions stand) |
| RM-2 | Replace the fixture rule set with one carrying comparison evidence; today every advisory is `COMPARISON_EVIDENCE_ABSENT`. | `packages/capabilities/reasoning-method-advisor/src/ugence_reasoning_method_advisor/admission.py` — `ComparisonEvidence`, `admit`, `validate_admission`; governance 0.2.0 vocabulary `COMPARISON_EVIDENCE_PRESENT` / `ADVISORY_INPUT` |
| RM-3 | Wire the proposer to consume the advisory as a typed input, not as authority. | `ugence_agentic_proposer.ReasoningMethodAdvisoryInput` and `ProposerProcessRecord.reasoning_method_advisory_input` (0.5.0); the advisor's `to_proposer_input` bridge |

## 3 — What was built `[V]`

**Governance 0.2.0.** Two constants added to the shared vocabulary:
`EVIDENCE_STATUS_COMPARISON_EVIDENCE_PRESENT` and `USAGE_SCOPE_ADVISORY_INPUT`
(`contracts/assessment.py`). Fit assessments, comparison plans and comparison results
stay fixed at `RESEARCH_ONLY`: they are the evidence, not the thing the evidence admits.

**Advisor 0.2.0.** The slice 2 request and advisory are **unchanged, field for field**
(`tests/test_profiles.py::test_p8_no_comparison_field_exists` still holds). Three
additions beside them:

- `ComparisonEvidence(task_class_digest, catalog, assessments)` — a bundle of
  `ReasoningMethodFitAssessment`s for one task class over one catalog; another class,
  another catalog or a duplicated assessment is `COMPARISON_EVIDENCE_UNBOUND`.
- `admit(advisory, request, result, admitted_at=...)` →
  `ReasoningMethodAdvisoryAdmission`: takes the engine's `ReadinessComparisonResult`
  (never a bare bundle; a result naming another engine is unbound), binds the advisory
  to its request first, refuses an unclassified advisory, then asks one question per
  qualifying method — is there a
  `SUFFICIENT_PARETO_EFFICIENT` or `SUFFICIENT_RESOURCE_DOMINATED` assessment for
  exactly its method reference? All covered: admitted, citing the admitting digests as
  `evidence_refs` inside the admission digest. An `INSUFFICIENT_QUALITY` assessment for
  a qualifying method: `COMPARISON_EVIDENCE_CONTRADICTED`. Partial coverage, no
  qualifier, or only `COMPARISON_EVIDENCE_ABSENT` assessments:
  `RESEARCH_ONLY_REFUSED_IN_PRODUCT`. The admission exists only in the admitted state
  and cites the result by `comparison_result_digest`; `validate_admission` replays
  coverage against that result at any later time. (Amended 2026-09-06: the first
  version took a bare `ComparisonEvidence` bundle, so a hand-built assessment could
  admit; study-plan requirement A1 closed that structurally. Amended again the same
  day under SCR-1: `admit` takes `verified=` and `require_signature=`, and the
  admission — schema `advisory_admission.v3` — cites `result_signature_receipt_digest`;
  see `ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md` §6.)
- `to_proposer_input(admission)` — the one-way bridge. Refuses a bare advisory. Adds
  the proposer's C6 `sha256:` prefix to every digest; the advisor's own digests stay
  bare hex.

**Proposer 0.5.0.** One public name, `ReasoningMethodAdvisoryInput` (thirteen fields,
no C2 common field, including `comparison_result_digest`), and one optional field on `ProposerProcessRecord` (18 → 19). Both
vocabulary fields are `Literal`s, so a research-only advisory cannot be constructed as
input at all. The record sits outside `P_unsigned` (D9), so no advisory digest moves
`[V]` (`tests/test_rm3_reasoning_method_input.py::test_the_input_is_outside_p_unsigned`).
The proposer imports nothing from the research packages; its boundary guard is
unchanged. `docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` D8 and H3 are amended,
`public_api.json` regenerated (51 → 52 names).

**Evidence.** Suites at the change: governance 62, advisor 63 (+2 skips), readiness
comparison 45, workflow-fit pilot 260 (+1 skip), agentic proposer 2245 (+863 skips),
all passing in a clean editable install.

## 4 — Two constraints the implementation discovered `[V]`

**A digest that must not move.** The workflow-fit pilot's v1 manifest pins a
"historical" digest that embeds an advisory. A first attempt added `evidence_refs` to
the advisory and moved that digest; the admission record exists because of it. The
pilot's fixture was also found to embed the *installed* advisor version string, so any
advisor release would have moved the pin; `tests/pilot_fixtures.py` now restates the
captured version literal (`ADVISOR_VERSION_AT_V1_CAPTURE`), and the pin means what it
says.

**Two digest grammars.** The proposer's C6 digest carries an algorithm prefix; the
reasoning-method packages use bare hex. The bridge translates one way and nothing
translates back.

## 5 — What this does not establish `[G]`

- **No real comparison evidence exists.** Every fit assessment in the test suites is a
  synthetic fixture proving the mechanism. Evidence for a real task class comes from a
  comparison study over `ugence-readiness-comparison`, which the advisor still never
  imports and whose results it never ingests: it is handed assessments and checks them.
- **No admission has been produced for a real workload,** and nothing here is
  pilot-validated or production-certified (Appendix B.5 still records zero of either).
- **`readiness-comparison` and `workflow-fit-pilot` stay research-only.** Only the two
  packages the rulings named move; the study harness and the comparison engine remain
  in M4.

## 6 — Roadmap §11.2

"No research-only package in the product" is amended to: no research-only package in
the product, *except* a reasoning-method advisory that carries a
`ReasoningMethodAdvisoryAdmission` under this ADR — the advisory enters as typed input
to the Agentic Proposer and as nothing else. All other §11.2 non-goals stand.

## 7 — Module map

`docs/UGENCE_PREVENTIVE_DETECTIVE_MODULE_MAP.md` unit 7 and the published module map
move `reasoning-method-governance` and `reasoning-method-advisor` from M4 (research-only,
four packages) to M3 (proposal and advisory, eleven packages), marked *product entry
gated on admission*. M4 keeps `readiness-comparison` and `workflow-fit-pilot`.
