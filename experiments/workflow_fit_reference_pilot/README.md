# Workflow-Fit Reference Pilot (Phase 4B tooling; mechanism validation only)

**Load-bearing statement.** Everything this workspace produces is
**MECHANISM_VALIDATION_ONLY** and **RESEARCH_ONLY**. The bundled fixture is
synthetic: a canned-answer provider, a synthetic executor that makes a declared
number of gateway calls, and three structured-answer cases. Its runs are **not a
real pilot**, **not reasoning-performance evidence**, **not benchmark-derived
evidence**, and say nothing about the quality of any reasoning method. They
prove only that the ratified Phase 4A machinery (capture boundary, attestation,
evaluation binding, comparison engine, lifecycle, coverage, report) runs end to
end from typed inputs to a verifiable artifact bundle.

## What is here

| Module | Role |
| --- | --- |
| `loaders.py` | Strict typed loaders for every input document: exact key sets, exact JSON types, no defaults, no coercion, no inference; credential-like keys are refused. |
| `evaluator.py` | Deterministic programmatic scorer (`ANSWER:` line exact match, 1 or 0). Expected answers come from a separate document and never enter workflow-visible inputs. |
| `synthetic_provider.py` | Provider factory for the boundary process: canned answers by substring table; modes `ok`, `no_usage`, `raise:<method_id>`. No network, no credentials, no model. |
| `synthetic_executor.py` | `WorkflowExecutorPort` that makes `calls[method][case]` gateway calls (zero permitted); optional uncaptured bypass call; optional workflow failure. Not a reasoning workflow. |
| `bundle.py` | Deterministic bundle layout, canonical JSON artifacts, type-hint-driven rebuild of every contract object, and an index whose JCS digest covers the complete artifact set. |
| `pipeline.py` | `prepare`, `run`, `verify`, `render`, `replay`. |
| `cli.py` | Command line over the five commands. |
| `fixture/` | The synthetic qualification fixture (typed JSON documents, scenarios). Contains no prompt text beyond the three case queries, no response text, no hidden reasoning, no credentials. |

Real workflows are reached only through
`experiments/workflow_fit_study/pilot_executor.py` (Phase 4A); this workspace
never imports them and modifies nothing under `agentic/`.

## Commands

```
python -m experiments.workflow_fit_reference_pilot.cli prepare --fixture experiments/workflow_fit_reference_pilot/fixture --out <prepared>
python -m experiments.workflow_fit_reference_pilot.cli run --fixture <fixture> --prepared <prepared> --out <bundle> --scenario nominal [--transport unix|pipe]
python -m experiments.workflow_fit_reference_pilot.cli verify --bundle <bundle>
python -m experiments.workflow_fit_reference_pilot.cli render --bundle <bundle>
python -m experiments.workflow_fit_reference_pilot.cli replay --bundle <bundle>
```

- `prepare` builds the existing `BenchmarkManifest` and `PilotStudyManifest`
  from the fixture documents with caller-supplied instants, the model
  reference, the provider-factory reference, the evaluator identity, the
  scoring-instruction digest and the calibration-evidence declaration
  (`null` → declared absent, recorded as `calibration_evidence_declared_absent`).
  It calls the real Slice 2 advisor over the demo's research catalog and
  `rules.research.v0`, then `validate_manifest`. No new contract, enum, schema
  version or evidence label is introduced.
- `run` executes one named scenario through `run_pilot` (the ratified 4A
  runner) with the boundary in a separate OS process, then writes the bundle.
- `verify` fails closed: index coverage; every artifact rebuilt from JSON
  through the contract constructors (which re-verify every self-digest);
  fresh `validate_manifest`; per method: capture-record attribution, telemetry
  recomputation from the bundled capture records, attestation binding,
  `validate_observation`; the comparison engine re-run at the stored
  `produced_at` with digest equality; `validate_lineage` bound to the result;
  coverage rebuild; and byte equality of `report.txt` with a fresh rendering.
- `render` = verify, then print the 4A report. `replay` = verify + render and
  never starts a boundary or imports a provider factory.

## Bundle layout

```
index.json                       {artifacts: {path: sha256}, index_digest}   (workspace tooling, not a contract)
benchmark_manifest.json  pilot_manifest.json  validated_manifest.json  advisory.json  catalog.json  rule_set.json
case_set.json                    case ids and digests only
preparation.json                 provider-factory reference, identity, instants, calibration declaration, usage label
run_status.json                  scenario, transport, provider mode, per-method completeness, reasons, diagnostics, usage label
methods/<id>@<ver>/capture_records.json          digests only: prompt_digest, response_digest, usage, status
methods/<id>@<ver>/{execution_record, attestation_envelope, quality_claim, quality_result, quality_evaluation, observation}.json   (complete runs only)
comparison_request.json  comparison_result.json  (present when at least one run completed)
lifecycle_states.json  coverage_report.json  report.txt
```

Verification rejects an omitted, substituted, duplicated or unexpected
artifact, an index digest that does not cover the set, and any artifact whose
attribution (manifest, method, run id, identity) differs from the manifest's.
Raw provider requests and responses never enter a bundle.

## Scenarios in the fixture

| Scenario | Exercises | Outcome |
| --- | --- | --- |
| `nominal` | zero-, one- and multi-call cases across seven methods | all complete; engine assesses |
| `no_usage` | provider reports no token usage | complete; only `telemetry.llm_calls` attested |
| `provider_failure` | provider raises for one method | that run `INCONCLUSIVE` (`WORKFLOW_FAILED`); others assessed |
| `incomplete_capture` | one uncaptured in-process call | that run `INCONCLUSIVE` (`CAPTURE_INCOMPLETE`) |
| `engine_refusal` | governed baseline's workflow fails | engine refuses `BASELINE_ABSENT`; every method `COMPARISON_EVIDENCE_ABSENT` |
| `zero_call_run` | every method makes no call in any case | complete; `llm_calls = 0` attested over the manifest stamp; every method `INSUFFICIENT_QUALITY` (no answer line) |

A zero-call **case** inside a run with other calls is complete and scores 0
under the reference evaluator (no `ANSWER:` line); this is the mechanism working,
not a quality finding.

## Interpretations made (workspace conventions, not contracts)

1. **Case identity.** `case_digest` = digest of `{case_id, query, context,
   expected_digest}` where `expected_digest` digests the normalized expected
   answer. The benchmark manifest thereby commits to the expected answers
   without carrying them.
2. **Instants.** `run` derives every runner instant from the fixture's
   `run_started_at` advanced by one microsecond per request; `preregistered_at`
   is used for the advisory, the plan and the manifest; `issued_at` for the
   benchmark manifest. No command reads a clock.
3. **Scoring-instruction digest.** Digest of the scoring rule text, the
   benchmark manifest digest and the sufficiency rule id/version.
4. **Zero-call telemetry.** None needed: zero-call cases and zero-call runs
   both follow the ratified 4A recomputation (spec §4.3, §11).
5. **Bundle index.** A plain JSON map plus its JCS digest, no schema version.

## Zero-call runs (gap resolved by owner ruling, 2026-09-02)

The first 4B revision recorded a gap: the 4A boundary could not attest a
method run with no provider call in any case. The owner ruled (spec §11,
"Zero-call attestation ruling") that such a completed run attests
`telemetry.llm_calls = 0` over the boundary's manifest stamp, while missing
cases, skipped control frames, workflow failure or unequal counts remain
`INCONCLUSIVE`. 4A now implements the ruling (row A14a) and the
`zero_call_run` scenario exercises it.

## Exclusions (unchanged from the commissioning message)

No real provider call, no customer data, no benchmark-derived advisor
behaviour, no `BENCHMARK_DERIVED` label or contract change, no TEV
integration, no production approval, eligibility, configuration mutation or
Constitution binding, no readiness composite, no claim that the fixture
measures quality, and no modification to the reasoning workflows.
