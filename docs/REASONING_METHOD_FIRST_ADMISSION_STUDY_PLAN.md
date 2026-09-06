# Reasoning-method advisor — plan for the first real admission

**Status:** preregistration draft, 2026-09-06. Documentation only; nothing here has
run. Companion to `docs/architecture/ADR_UGENCE_REASONING_METHOD_PRODUCT_ENTRY.md`.
Labels: `[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

What is the smallest study that would turn a synthetic `ReasoningMethodAdvisoryAdmission`
into a real one? **One governed task class, one baseline, the three methods the fixture
rule set makes qualify for it, one comparison run, and four attestations the repository
can already express but has never produced.** Everything below is mechanism that exists;
the dataset, the model client and the independent parties do not `[G]`.

## 2 — The task class

`study.hard`, from the pilot fixtures `[V]`
(`packages/capabilities/workflow-fit-pilot/tests/pilot_fixtures.py:93-98`):
structural tokens `comparison_request`, `ambiguity_detected`, `creative_synthesis`;
consequence `RECOVERABLE`; reversibility `OUTCOME_COMPENSATABLE`; sufficiency rule
`study.hard.sufficiency`, threshold `score.unit >= 0.9`; required resource dimension
`LLM_CALLS`; quality aggregation `research.mean` `[V]` (lines 62-64).

Under `rules.research.v0`, those three tokens make **three methods qualify** —
`map_reduce`, `tree_of_thought`, `iterative_refinement` — with no primary `[V]`
(`reasoning-method-advisor/tests/rule_fixtures.py:35-46`). The plan's baseline is
`linear_chain` `[V]` (`pilot_fixtures.py:135`). So the admission needs a sufficient
assessment for each of the three qualifiers; the baseline is compared, not admitted.

**One thing changes, and it changes the digest.** The fixture class is bound to
`benchmark.pilot.hard`, two hand-written cases `[V]` (`pilot_fixtures.py:79-84`). A
real study re-issues the same structural declaration bound to a real benchmark manifest
through `build_task_class` `[V]` (`experiments/workflow_fit_study/governed_adapter.py:87`),
which yields a **new `task_class_digest`**. The advisory must then be re-derived for that
class, because `admit` refuses evidence for another class `[V]` (`admission.py:207-210`).
The fixture's population label `population:support-tickets` is also wrong for the
benchmark below and must be redeclared `[R]`.

## 3 — The benchmark and the harness

The repository already carries a BBH logical-deduction (seven objects) path:

- `bbh_sample.py` — a hash-rank index selector that reads indexes and metadata only
  and never opens the benchmark file `[V]` (`experiments/workflow_fit_study/bbh_sample.py:39`);
- `bbh_ld7_scorer.py` — a deterministic scorer whose procedure text is a guarded
  normative preimage, receiving a case digest and a response, never the query, with
  expected answers held only in scorer-side custody `[V]` (`bbh_ld7_scorer.py:1-14`);
- `pilot_executor.py` — runs the research harness's workflows behind the pilot's
  gateway with a caller-supplied client and `max_llm_calls` `[V]` (`pilot_executor.py:12-24`);
- `governed_adapter.py` — one execution record per method with `llm_calls` summed over
  the *same* case set, one `MetricClaim` per method calculated as the research mean, and
  the per-case self-reported quality carried but **never referenced by any claim** `[V]`
  (`governed_adapter.py:1-27`).

**The benchmark file is not in the repository** `[G]`; **no LLM client is in the
repository** `[G]`. Both are supplied at run time and named in the preregistration.

## 4 — The run, step by step

1. **Preregister.** A `PilotStudyManifest` binding the plan (baseline, the three
   qualifiers, the sampling policy), the advisory digest for the re-issued class, the
   rule-set digest, the benchmark manifest with its exact case digests, the boundary and
   evaluator declarations, and the aggregations `[V]` (pilot README). Sample size, seed
   and `max_llm_calls` are owner-supplied: the package deliberately holds no numeric
   default `[V]` (README, last paragraph). Today preregistration is
   `DECLARED_UNVERIFIED` `[G]`.
2. **Sample.** `select_indexes(seed, population_size, sample_size)` over the benchmark's
   index range; commit the index-list digest before any case text is read.
3. **Execute** each of the four methods over the identical case set through the
   separate-process capture boundary, which is the only client `[V]` (README).
4. **Attest telemetry.** The boundary recomputes the record digest and the telemetry
   from its own capture records and refuses mismatch or self-attestation before issuing
   the envelope `[V]` (`boundary/attestation.py:98-125`).
5. **Score** with `bbh-ld7.v3`; aggregate to one claim per method.
6. **Compare.** `compare(request, produced_at=...)` `[V]` (`engine.py:67`). Per
   candidate the engine yields exactly one of: `COMPARISON_EVIDENCE_ABSENT` when a record,
   claim or dimension is missing `[V]` (`engine.py:206, 367`); `INSUFFICIENT_QUALITY`
   when the mean fails `>= 0.9` `[V]` (`engine.py:382`); otherwise
   `SUFFICIENT_RESOURCE_DOMINATED` if another sufficient method dominates it on
   `LLM_CALLS`, else `SUFFICIENT_PARETO_EFFICIENT` `[V]` (`engine.py:416`).
7. **Admit.** Hand the engine's result to
   `admit(advisory, request, result, admitted_at=...)`. It refuses if any qualifier is
   `INSUFFICIENT_QUALITY` (`admission.py:166-171`) or lacks a sufficient assessment
   (`admission.py:176-180`); both sufficient outcomes count (`admission.py:53`) `[V]`.

The study therefore has three legitimate endings: admitted; refused as contradicted
because a qualifier fails the threshold; refused as research-only because evidence is
absent. **All three are results.** A refusal is the rule set being wrong for this class,
which is what the study exists to find out.

## 5 — What must be attested before `admit` is trusted

`admit` checks shape, binding, coverage and — since the amendment of 2026-09-06 —
that the evidence arrived as an engine `ReadinessComparisonResult`, which it cites by
`comparison_result_digest` `[V]` (`admission.py`, `evidence_from_result`). A hand-built
tuple of assessments no longer admits. What remains open is a *forged result*, and the
three attestations below it. Trust therefore rests on four things upstream:

| # | Requirement | Mechanism | Status |
|---|---|---|---|
| A1 | Assessments come from an engine-produced `ReadinessComparisonResult`, not a hand | result contract refuses a foreign assessor `[V]` (`governance/contracts/ports.py:170`); the admission cites the **result digest** and refuses any engine but the comparison engine `[V]` | closed structurally; a forged result still needs A3 |
| A2 | Execution records attested by a party that is neither producer nor requester, and resolved as an authority | engine refuses self-attestation `[V]` (`engine.py:244`); resolution is requester-asserted `[V]` (`engine.py:218`) | `[G]` no authority resolution exists |
| A3 | Attestations verified by the Trusted Evidence Authority; the result itself signed by the engine under a lent TEA capability | `VerificationEnvelope` must reference an attestation of the same record `[V]` (`engine.py:251-258`); TEV-2 verifier exists; result signing **built as contracts** under `ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md` SCR-1 `[V]` (`reasoning-method-result-attestation`; `admit(..., require_signature=True)`) | closed for the research posture: `experiments/workflow_fit_study/signed_admission.py` signs with a research reference key and verifies through a committed research snapshot (SR-0 to SR-5, ADR §7); `[G]` no production key, so a signed admission is cryptographically verifiable self-attestation, not independent verification |
| A4 | Quality claims independent of self-reported quality; scorer custody independent of the executor | engine refuses claims naming `self_reported_quality` `[V]` (`engine.py:306`); scorer custody keyed by case digest `[V]` | `[G]` evaluator independence is `DECLARED_UNVERIFIED` |

Under SR-5 a signed admission is exactly as trustworthy as whoever ran the engine,
because the operator, requester and signer are the same party: the signature makes
that attribution cryptographically verifiable and nothing more. That is acceptable for
the first study, whose purpose is to exercise the path, and not acceptable for any
product claim `[R]`.

## 6 — What today lacks a real dataset `[G]`

Steps 1 (the benchmark manifest), 2 (the index range), 3 (the client), 5 (custody of
expected answers held by someone other than the executor) and the whole of §5. Every
assessment in every suite in this repository is synthetic. Nothing in this plan changes
Appendix B.5's zero pilot-validated capabilities.

## 7 — RM-4 given, and what stopped the run `[V]`

RM-4 was given on 2026-09-07 with the owner's five values. The sample was preregistered
before any case text was used: `experiments/workflow_fit_study/first_admission_study/
preregistration_rm4.json` commits the seed, the 100 selected indexes and their digest,
the benchmark content digest and the case-list digest; no case text or target is
committed. Execution did not start, for three reasons recorded there: the environment
holds no model credential or SDK; the ratified Phase 4C process requires a CALIBRATION
run whose verdict custody needs a D5-approved adapter, and none exists; and the ruling
names no calibration step, so the confirmatory manifest's provenance cannot be
preregistered yet. None of the three endings in §4 has occurred `[G]`.

## 7a — The ruling as originally needed `[R]`

**RM-4 — run the first admission study**: authorize one execution of §4 over BBH
logical-deduction-7 for the re-issued `study.hard` class, with the owner supplying, in
the preregistration and nowhere else, the model client identity, the sample size, the
seed and `max_llm_calls`; accept that the three endings in §4 are all results; and
record that the resulting admission, if any, is research evidence about the rule set
and not a product claim until §5 A1–A4 are closed.
