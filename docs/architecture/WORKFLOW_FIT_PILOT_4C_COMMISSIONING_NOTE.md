# Phase 4C — First Genuine Research-Only Workflow-Fit Pilot: Commissioning Note and Ballot

**Revision 3.** Status: documentation only. **Nothing in this note authorises a
provider call.** Until every ballot item in §3 is ratified by the owner, no
code path in this repository may contact a provider, hold a credential, or
run a real workflow behind the pilot boundary. Every output of a ratified 4C
run remains `RESEARCH_ONLY` with `preregistration_status =
DECLARED_UNVERIFIED`. No benchmark-derived advisor behaviour, no
`BENCHMARK_DERIVED` label and no silent governed-contract change is in scope.

**The load-bearing question.** What makes a run a genuine research pilot
rather than a mechanism exercise? Not the provider. A run is a pilot only if
its benchmark is demonstrably representative of the declared task class, its
every input is owner-decided and bound by a preregistered commitment, and its
underlying artifacts are retained where an independent party can re-evaluate
them later. Phase 4B proved the mechanism
(`experiments/workflow_fit_reference_pilot/README.md`); 4C supplies the five
things the mechanism cannot decide for itself.

## 1. What already exists `[V]`

| Need | Provided by | Reference |
|---|---|---|
| Real workflows behind the gateway stub | `HarnessWorkflowExecutor(max_llm_calls)` | `experiments/workflow_fit_study/pilot_executor.py` |
| Separate-process capture; every provider attempt recorded including `EXCEPTION`/`TIMEOUT`; `llm_calls` = count of capture records, so a retry is never hidden | `BoundaryServer._call`, `recompute_telemetry` | `boundary/server.py`, `boundary/attestation.py` (spec §4.2–4.3, A14, A16a) |
| Provider injected by dotted path only, imported once inside the boundary process | `boundary/entry.py` `--provider-factory` | spec §4.1, A30 |
| Typed inputs with no defaults; credential-like keys refused | `loaders.py` | 4B |
| Manifest preparation, run, fail-closed verify, replay without provider; a prepared bundle with `index_digest` over every prepared artifact | `pipeline.py`, `bundle.py`, `cli.py` | 4B |
| Digests-only run bundle; prompts, responses and expected answers never enter it | `bundle.py`; 4B test `test_expected_answers_prompts_and_responses_never_enter_a_bundle` | 4B |
| Zero-call runs attested; incomplete runs `INCONCLUSIVE` | rows A14, A14a | spec §11 |
| Quality unit and aggregation actually executed | `QUALITY_UNIT = "score.unit"`, arithmetic mean over cases | `runner.py` (`_mean`) |

## 2. What the tooling cannot enforce today, and where each control lives `[V]`

None of these is a defect in 4A/4B; each is a control a genuine pilot needs
that no ratified contract covers. Each is assigned below to an
**experiment-side control** (under `experiments/`, bound by the preregistered
commitment of §2.1) or to an **explicitly balloted 4A amendment**. Nothing
may be added silently.

### 2.1 Preregistration binding (resolves B1)

`PilotStudyManifest` carries no provider or experimental-design field
(`contracts/manifest.py`), and 4B writes `preparation.json` after the
manifest digest exists and loads the scenario only at run time
(`pipeline.py`). A commitment to the manifest digest alone therefore binds
nothing D1 or D4 decides.

**Rule.** The preregistered commitment is the prepared bundle's
`index_digest` **together with a commitment identifier**. The 4B index is
deliberately unversioned (`bundle.py`); a bare hexadecimal digest does not
identify the algorithm, canonicalisation or layout a future verifier must
reproduce. The prepared bundle therefore carries, and the preregistration
receipt repeats, the commitment identifier
`workflow_fit_prepared_index.v1`, defined as: SHA-256 per artifact; the
index digest = `ugence_jcs.canonical_sha256_hex` over the sorted
path-to-SHA-256 map; the prepared layout = the 4B prepared set plus
`provider_configuration.json` and `experimental_design.json`. Every canonical
provider-configuration value and every experimental-design parameter must be
a prepared artifact under that layout, written by `prepare` before the
commitment is recorded. `run` must refuse to start, and `verify` must refuse
to pass, unless **both** the identifier and the recomputed digest equal the
preregistered pair supplied to them. The scenario document used by 4B
becomes a prepared artifact under the same rule. Experiment-side; no
contract change.

### 2.2 Repetitions (resolves B2)

The runner executes each case exactly once per method with one run identity
per manifest and method (`runner.py`), and case digests must be unique
(`contracts/benchmark.py`). Repetition inside one run is unimplementable
without a 4A amendment.

**Rule.** One separately preregistered manifest and prepared-bundle index per
repetition, each with a distinct `manifest_id` (and therefore distinct
manifest digest, run identities, record identities and comparison request
id). A repetition is a whole pilot run. Cross-run aggregation is **deferred to
a later ballot**; 4C reports repetitions side by side without combining them.

### 2.3 Custody writers (resolves B3)

The boundary sees provider prompts and responses; the experiment-side scorer
alone sees expected answers. **Expected answers must never enter the
provider boundary.**

**Rule.** Two append-only custody writers, each referencing the manifest
digest and the preregistered `index_digest`:

- the **boundary-side exchange writer**, inside the boundary process, retains
  every provider prompt and response with its `capture_fingerprint`
  (4A amendment to `boundary/server.py`, balloted under D5);
- the **benchmark-custody writer**, experiment-side, retains the expected
  answers and the scorer's per-case verdicts keyed by case digest.

Each writer has its own access-control list and named writer identity. Both
fail closed, at two distinct moments:

- **Pre-run benchmark-custody failure.** Expected answers are retained by the
  benchmark-custody writer before preregistration. A write that cannot be
  confirmed **blocks preregistration and execution**: no manifest is
  committed and no run exists, so nothing is marked `INCONCLUSIVE`.
- **In-run retention failure.** A verdict-retention write or a boundary
  exchange write that fails during a run must end that method's run
  `INCONCLUSIVE` with a named refusal (`RETENTION_FAILED`), never a partial
  record. The merged runner cannot do this: scoring happens after attestation
  and outside the executor's exception handling (`runner.py`, `_run_method`),
  so a scorer or retention exception today aborts the whole pilot without a
  lifecycle record. A **narrow 4A runner amendment** (§4) must catch scorer
  and retention exceptions after attestation, discard the attested record for
  that method, and emit the `INCONCLUSIVE` transition with the named refusal.

### 2.4 Credential delivery (resolves M4)

`BoundaryProcess` hands an environment to the whole child process
(`boundary/process.py`), and the 4B helper starts from a full copy of the
runner's environment (`pipeline.py`). **No environment mechanism makes a
credential visible only to the provider factory**; any code in the boundary
process can read it. The alternatives are put to ballot in D1 with their
option-specific values. Option B is not implementable against the merged
API: `run_pilot` constructs `BoundaryProcess` unconditionally and that class
launches its own subprocess (`runner.py`, `boundary/process.py`), so an
externally supervised boundary requires a **launch/connection port
amendment** to 4A (§4), commissioned only if B is selected. In every option
the boundary child process receives a **minimal environment allowlist
derived from the selected option**: interpreter path, `PYTHONPATH`, locale,
plus for A the workload-identity variables the source mechanism needs, for B
nothing further, for C the single named variable; and nothing else.

### 2.5 Provider identity (resolves M5)

`ProviderResult` returns `provider_id` and `provider_request_id` only
(`boundary/frames.py`). A pinned `provider_configuration.json` proves what was
**requested**, not what the provider **executed**. Configured identity is
therefore requester-declared and unverified unless the provider returns an
immutable deployment identity. **Representation and enforcement.** The
provider factory must compare the identity the provider returns with the
preregistered value **before** returning `ProviderResult`, and map the
verified identity into `provider_id`; `CaptureRecord` is unchanged. On
absence, mismatch, or inconsistency across attempts within a run, the
boundary **hard-stops the run** with a named refusal
(`PROVIDER_IDENTITY_UNVERIFIED`) as part of the boundary hard-stop amendment
(§4); the refusal is never surfaced as an ordinary captured provider
exception that a workflow could retry past. The acceptance policy is
balloted in D1.

### 2.6 Quality unit and aggregation (resolves M6)

Phase 4C is constrained to `score.unit` and the arithmetic mean over cases as
the runner executes them. Any other unit or aggregation named in
`task_class.json` or `aggregation.json` would not control the calculation and
is refused by `prepare`; changing it requires a later 4A amendment.

### 2.7 Remaining controls

| Control | Current state | Where it lives |
|---|---|---|
| Call and spending ceilings | per-workflow `max_llm_calls` only | run-level counter experiment-side; boundary-side hard stop as a 4A amendment (D4) |
| Retry and timeout | a failed call raises into the workflow; whatever follows is captured | declared in `experimental_design.json`; every retry is a captured attempt and counts in `llm_calls` `[V]` |
| Concurrency | runner sequential, one connection | sequential; change only by ballot |
| Stochastic control | no seed or temperature concept anywhere | declared in `experimental_design.json` and applied by the provider factory (D4) |

## 3. Ballot — five owner decisions `[R]`

Each item lists the **concrete values the owner must supply at
ratification**. A ballot item without every value is not ratified.

**D1. Provider identity and credential delivery.**
Values: provider name; immutable model identifier and version; deployment
region; data-retention policy reference and version as it applies to the run;
complete decoding-parameter set (temperature, top-p, max output tokens, stop
sequences, seed or "not supported"); and the credential-delivery
option with its option-specific values:
- A. the boundary retrieves the secret itself using workload identity
  (**recommended**): the principal or role, the token audience, the secret
  location, and the credential-source mechanism;
- B. an external supervisor injects it directly into the boundary process:
  the supervisor identity, the handoff mechanism, and ratification of the
  launch/connection port amendment (§2.4, §4) it requires;
- C. the runner inherits it under a tested non-reading, non-serialising
  convention, **explicitly labelled non-isolating**: the single
  environment-variable name.
Identity policy, one of: accept requester-declared identity as unverified, or
**refuse any provider that does not return an immutable deployment identity
(recommended)**, enforced by the factory comparison and boundary hard stop of
§2.5. In every option the credential never appears in arguments,
manifests, logs, bundles, retention records or this repository, and the child
process receives the §2.4 allowlist only.

**D2. Benchmark and evaluation custody.**
Values: named author and named approver of the cases and expected answers
(distinct persons); exact benchmark id, version and case list; the
benchmark-custody location (URI) and its readers and writers; the answer
versioning rule; the separation rule keeping expected answers out of every
workflow-visible input and out of the boundary; and the **evaluator
declaration**: kind (`PROGRAMMATIC`, `HUMAN` or `LLM`), evaluator identity
distinct from record issuer, requester and boundary, scoring procedure text
whose digest becomes `scoring_instruction_digest`, separation declaration
reference, model reference when the kind is `LLM`, and calibration-evidence
reference or explicit declared absence. The case digest is an integrity
commitment only; it does not conceal an easily guessed answer.

**D3. Task-class validity and comparison configuration.**
Values: the exact `profile.json` and `task_class.json`; the population
definition; a written representativeness statement saying why these cases
represent the declared task class and what they do not cover; the quality
threshold literal and comparator in `score.unit` under arithmetic-mean
aggregation (§2.6); and the resource dimensions compared. Threshold, unit,
aggregation and dimensions are **pilot configuration**, not architectural
defaults. Structural-token traceability per case is required but is not
itself evidence of representative sampling.

**D4. Experimental design.**
Values: repetition count, with one preregistered manifest and index per
repetition and the `manifest_id` naming rule (§2.2); stochastic-control
declaration (seed per repetition, or "provider offers no seed" with the
pinned temperature); concurrency (sequential unless stated); run-level call
ceiling and its scope (per run, per method, per case); spending ceiling with
its pricing source, currency and the count it is derived from; timeout per
provider call and who owns it (provider factory); retry policy, with every
retry a captured attempt that counts in `llm_calls`; stop conditions and the
partial-run policy (a ceiling breach ends the run `INCONCLUSIVE`); and case
ordering (preregistered order, or a declared randomisation with its seed).
The boundary-side hard stop at the call ceiling is a 4A amendment ratified
by this item.

**D5. Preregistration and evidence retention.**
Values: the preregistration medium and the receipt form in which the owner
records the commitment identifier `workflow_fit_prepared_index.v1` and the
prepared bundle's `index_digest` before execution (§2.1), per repetition; the two custody writers of §2.3 with their locations, writer
identities, access-control lists, encryption and key custody, retention
period and deletion rule; the fail-closed behaviour at both moments of §2.3
(pre-run block, in-run `RETENTION_FAILED`); and the ratification of the
boundary-side exchange writer and the runner retention amendment as 4A
amendments.
Git keeps digests and the governed evidence objects only. Digest-only
evidence is insufficient for later independent re-evaluation.

## 4. What ratification would commission `[I]`

Only after all five items are ratified: `prepare` extended to write
`provider_configuration.json` and `experimental_design.json` and to refuse
non-`score.unit` or non-mean configuration; `run` and `verify` extended to
take and enforce the preregistered commitment identifier and `index_digest`
together; a boundary-side provider factory implementing the D1 option,
decoding parameters and the §2.5 identity comparison; the **4A amendments**,
each with acceptance rows and a spec §11 record: (i) boundary hard stop at
the call ceiling and on `PROVIDER_IDENTITY_UNVERIFIED`; (ii) boundary-side
exchange writer; (iii) runner amendment catching scorer and retention
exceptions after attestation and emitting `INCONCLUSIVE` with
`RETENTION_FAILED`; (iv) only if D1 selects option B, a launch/connection
port so an externally supervised boundary can be attached; the
benchmark-custody writer; and one preregistered run per repetition. The CI gate stays provider-free.

## 5. Explicitly excluded

Provider calls before ratification; any credential in the repository or in
any artifact; cross-run aggregation; advisor changes from pilot results;
readiness composites; production eligibility, approval or configuration
mutation; TEV integration; any quality unit or aggregation other than §2.6;
any claim that a run measures reasoning quality beyond the declared
benchmark.

## 6. Correction record

### Revision 2 (adversarial design review, applied on owner instruction, 2026-09-03)

| # | Defect | Resolution |
|---|---|---|
| B1 | Preregistered manifest digest bound no provider or design parameter | commitment is the prepared bundle `index_digest`; parameters become prepared artifacts; `run`/`verify` refuse index mismatch (§2.1, D5) |
| B2 | Repetitions unimplementable through a scenario document | one preregistered manifest and index per repetition with distinct identities; cross-run aggregation deferred (§2.2, D4) |
| B3 | Expected-answer retention assigned to the boundary, which never receives them | two append-only custody writers with shared references and separate access controls; answers never enter the boundary (§2.3, D5) |
| M4 | Environment allowlist misdescribed as isolating the credential | three delivery options balloted, A recommended, C labelled non-isolating; minimal allowlist required in every case (§2.4, D1) |
| M5 | Immutable provider identity unproven | requester-declared and unverified unless the provider returns immutable deployment identity; refusal recommended (§2.5, D1) |
| M6 | D3 permitted units and aggregations the runner cannot execute | 4C constrained to `score.unit` and arithmetic mean; `prepare` refuses otherwise (§2.6, D3) |
| M7 | Evaluator decision absent | folded into D2 with kind, identity, scoring procedure, separation, model and calibration references (D2) |

### Revision 3 (second review limited to the revision-2 resolutions, applied on owner instruction, 2026-09-03)

| # | Defect | Resolution |
|---|---|---|
| B3 | In-run custody failure could abort without an `INCONCLUSIVE` record; pre-run and in-run failures conflated | pre-run failure blocks preregistration; in-run failure is `RETENTION_FAILED` via a narrow runner amendment commissioned in §4 (§2.3, D5) |
| B1 | Unversioned index promoted to a commitment | commitment identifier `workflow_fit_prepared_index.v1` with algorithm and layout pinned in bundle and receipt; `run`/`verify` check identifier and digest together (§2.1, D5) |
| M4 | Option-specific values missing; option B unimplementable | values enumerated per option; launch/connection port amendment commissioned only if B is selected; allowlist derived from the option (§2.4, D1, §4) |
| M5 | Returned identity had no representation or stop semantics | factory compares before returning, verified identity in `provider_id`, boundary hard stop `PROVIDER_IDENTITY_UNVERIFIED` (§2.5, D1, §4) |

Ballot items remain five and remain `[R]`; nothing was ratified by either
revision.
