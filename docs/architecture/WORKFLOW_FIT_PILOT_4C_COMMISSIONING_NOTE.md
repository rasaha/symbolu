# Phase 4C — First Genuine Research-Only Workflow-Fit Pilot: Commissioning Note and Ballot

**Revision 6.** Status: documentation only. **Nothing in this note authorises a
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
path-to-SHA-256 map; and **exactly** this prepared layout (owner ruling,
revision 4) — the seven-file 4B prepared set `[V]`
(`pipeline.py`, `PREPARED_LAYOUT`) plus two:

```
benchmark_manifest.json   catalog.json     preparation.json
pilot_manifest.json       rule_set.json    provider_configuration.json
advisory.json             case_set.json    experimental_design.json
```

`index.json` carries the commitment identifier, the artifact map and the
`index_digest`, and is excluded from its own artifact map `[V]`
(`bundle.py`, `write_index`). `experimental_design.json` is **the single
selected and preregistered scenario**, not a set: the 4B `scenarios.json`
fixture is an input to selection and is **not** part of the v1 layout. Every
canonical provider-configuration value and every experimental-design
parameter must be a prepared artifact under that layout, written by `prepare`
before the commitment is recorded. `run` must refuse to start, and `verify`
must refuse to pass, unless **both** the identifier and the recomputed digest
equal the preregistered pair supplied to them. Any change to the algorithm,
the canonicalisation, the path set or the layout requires a **new commitment
identifier**; `v1` is never redefined. Experiment-side; no contract change.

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

**Re-running a halted repetition (owner ruling, revision 5).** A repetition
halted by a trust-infrastructure failure (§2.8) **may not be re-run under the
same preregistered manifest and `index_digest`**. The replacement attempt is
a new repetition: a fresh preregistration, a distinct `manifest_id` and its
own prepared-bundle index under §2.1. The halted repetition's evidence is
**retained and reported** — its `INCONCLUSIVE` method, its unstarted methods
and its incomplete label — and is never deleted, overwritten or silently
replaced by the successful attempt. Reusing the commitment would let an
unfavourable partial run be discarded and re-rolled behind one preregistered
identity, which is the precise thing preregistration exists to prevent. The
same rule holds however the repetition was halted, including a halt with no
provider call made.

**The ruling is coherent but not yet enforceable `[G]` (revision 6).** No
durable authority records that a commitment has been consumed. `run` verifies
bundle contents and consults no history `[V]` (`pipeline.py`, `run`), so the
same prepared bundle can be run again into another output directory. The
prepared bundle itself cannot hold the mark — it is immutable and its digest
is the commitment — and a local run directory cannot bind another machine or
workspace. The **durable spent-commitment authority is therefore a new owner
choice, balloted under D5**; until it is ratified, `run` cannot refuse a spent
commitment and T17 is not testable. Because a zero-call halt already consumes
the commitment (above), the safest mechanics are an atomic check-and-mark
**before boundary startup**, but the registry and its procedure are the
owner's to decide, not this note's.

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

Each writer has its own access-control list and named writer identity.

**Failure classification (owner ruling, revision 4).** A failure is
classified by **the operation being performed**, never by Python exception
class:

| Operation that failed | Refusal code |
|---|---|
| writing a custody record | `RETENTION_WRITE_FAILED` |
| confirming or reading back a retained record | `RETENTION_VERIFY_FAILED` |
| evaluation or scoring | `EVALUATION_FAILED` |

An evaluation failure must **never** be described as a retention failure. No
generic `RETENTION_FAILED` code is used where the stage is known; the code
revision 3 named is withdrawn. The three codes are additions to the governed
refusal vocabulary (`errors.py`, `PilotErrorCode`) and are balloted as part
of the 4A amendments in §4.

**Exception boundary.** Catching `Exception` at each port call site is
permitted, because the **call site** determines the category: the write call,
the read-back call and the scorer call are distinct sites with distinct
codes. `BaseException` is never caught. The concrete exception class is
preserved as **non-authoritative diagnostic** information; it never carries
secrets, prompts, responses or expected answers, and it never determines the
refusal code.

**Where the diagnostic is retained (owner ruling, revision 5).** In the
**run report, carried by the non-evidential run-status artifact** — the
method's `reasons` entry in `run_status.json`, which `report.txt` renders for
an incomplete method. The mechanism is not free: `verify` re-renders
`report.txt` from the bundle and demands byte equality, and rebuilds an
incomplete method's `reasons` from `run_status.json` `[V]`
(`pipeline.py`, `verify` and `_load_status`; `report.py`, `render`). A
diagnostic held only in a log would therefore make a bundle unverifiable, so
"report only, in no artifact" is not an available option. It stays
non-evidential nonetheless: `run_status.json` is workspace tooling, not a
governed contract, and the diagnostic does **not** enter governed evidence —
a lifecycle record carries the refusal **code alone** in `refusal_codes` `[V]`
(`contracts/lifecycle.py`), and no contract gains a diagnostic field. It is
**not** written to either custody store: those are append-only evidence, and
a writer that has just failed cannot be the recorder of its own failure. The
reason string names the failing operation, the method and the exception
class, and begins with the refusal code so the authoritative part is
unambiguous; anything that cannot be rendered without a secret, a prompt, a
response or an expected answer is **omitted rather than redacted**, an
exception class whose own name contains a forbidden rendering `[V]`
(`report.py`, `FORBIDDEN_RENDERINGS`) included.

**The prefix is load-bearing, not cosmetic (revision 6).** The merged runner
derives the authoritative refusal from the reason strings by prefix match
`[V]` (`runner.py`: `WORKFLOW_FAILED` when a reason starts with it, else
`CAPTURE_INCOMPLETE`). That two-way mapping **cannot carry the three new
codes**, so the §4 runner amendment must preserve the **exact** code rather
than collapse it, and must validate every reason string: a string, beginning
with the refusal code it carries, containing only the failing operation, the
method identity and the exception-class diagnostic, and nothing else.

Both writers fail closed, at three distinct moments:

- **Pre-run benchmark-custody failure.** Expected answers are retained by the
  benchmark-custody writer before preregistration. A write or read-back that
  cannot be confirmed **blocks preparation and preregistration**: no manifest
  is committed, no run exists and no lifecycle record exists, so nothing is
  marked `INCONCLUSIVE`.
- **In-run boundary exchange-custody failure**, during a provider attempt. An
  exchange write or verification failure must: record the provider attempt in
  boundary memory; mark the method run **fatally incomplete**; return the
  typed refusal through the boundary protocol; **prevent the workflow from
  retrying or making another provider call for that method**; issue **no**
  execution record and **no** attestation for that method; and cause a direct
  `PROPOSED` → `INCONCLUSIVE` transition carrying the exact retention refusal.
  That direct transition is already permitted and already validates without an
  engine result `[V]` (`contracts/lifecycle.py`, `_PERMITTED` and
  `validate_lineage`: a refusal-carrying `INCONCLUSIVE` record has no
  `result_digest`).
- **Post-attestation failure.** A benchmark-verdict retention failure or an
  evaluation failure after attestation must cause the runner to **discard that
  method's record, attestation, claim, result, evaluation and observation from
  the emitted evidence** and transition the method to `INCONCLUSIVE` with the
  exact code. The merged runner cannot do this: scoring happens after
  attestation and outside the executor's exception handling (`runner.py`,
  `_run_method`), so such an exception today aborts the whole pilot without a
  lifecycle record. A **narrow 4A runner amendment** (§4) supplies it.

The scope of each failure — this method only, or the whole repetition — is
§2.8.

### 2.4 Credential delivery (resolves M4)

`BoundaryProcess` hands an environment to the whole child process
(`boundary/process.py`), and the 4B helper starts from a full copy of the
runner's environment (`pipeline.py`). **No environment mechanism makes a
credential visible only to the provider factory**; any code in the boundary
process can read it. The alternatives are put to ballot in D1 with their
option-specific values.

**Owner ruling (revision 4).** **Option A is recommended**: boundary-side
retrieval through workload identity. No TCP credential port, HTTP credential
protocol or any other new secret-transfer protocol is designed for this
pilot; inventing one is excluded (§5). Option B is not implementable against
the merged API — `run_pilot` constructs `BoundaryProcess` unconditionally and
that class launches its own subprocess `[V]` (`runner.py`,
`boundary/process.py`) — and remains available **only** through a separately
specified launch/connection-port amendment that reuses the **existing pilot
frame protocol** over the **supported Unix-socket or pipe transports** `[V]`
(row A16d, `transport` on `run_pilot`). If B is later selected, its exact
supervisor handoff and attachment mechanism must be ratified **before**
implementation; no mechanism is specified here. Option C remains explicitly
**non-isolating**.

For whichever option is selected, the ballot must **name every environment
key** admitted by the minimal child-process allowlist, and nothing else
reaches the child. `PATH` and the interpreter executable are process
prerequisites and **must not be described as a credential-isolation
mechanism**.

### 2.5 Provider identity (resolves M5)

`ProviderResult` returns `provider_id` and `provider_request_id` only
(`boundary/frames.py`). A pinned `provider_configuration.json` proves what was
**requested**, not what the provider **executed**. Configured identity is
therefore requester-declared and unverified unless the provider returns an
immutable deployment identity.

**Owner ruling (revision 4) — binding policy for the first genuine 4C
pilot.** **Refuse any provider that cannot return an immutable deployment
identity.** The provider factory must compare the returned immutable identity
with the preregistered value **before** returning `ProviderResult`, map the
verified identity into `provider_id` (`CaptureRecord` is unchanged), and
require **the same identity on every attempt**. Absence, mismatch or
cross-attempt inconsistency produces a **non-retryable**
`PROVIDER_IDENTITY_UNVERIFIED` refusal — never an ordinary captured provider
exception a workflow could retry past — and **stops the entire repetition**
under §2.8, as part of the boundary hard-stop amendment (§4).

Requester-declared provider identity is **not an accepted Phase 4C execution
mode**. It remains documented as an excluded future research option (§5); it
must not share the `provider_id` representation of a verified identity and
must never appear as verified.

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

### 2.8 Partial-run policy (owner ruling, revision 4)

The scope of a failure is decided by **what failed**, not by where in the run
it happened. Ratified under D4.

**A trust-infrastructure failure stops the entire repetition.** These are:
provider-identity failure (§2.5); boundary exchange-custody failure (§2.3);
benchmark-custody service failure (§2.3); and failure of the boundary itself.
The failing method becomes `INCONCLUSIVE` with its exact refusal code.
Methods not yet started produce **no fabricated lifecycle record and no
result**. Evidence for already completed methods remains individually valid,
but the repetition report is **labelled incomplete** and **may not present a
comparative winner or a success figure**.

**A method-local failure makes only that method `INCONCLUSIVE`**: execution
failure, a call-ceiling breach, or an evaluation failure (`EVALUATION_FAILED`).
Later methods may continue **only if** the boundary and **both** custody
services remain healthy. Coverage reporting must expose the missing method,
and no complete-set comparison may be claimed.

**The discriminator (owner ruling, revision 5; mechanics corrected in
revision 6).** A retention write or verification failure does not classify
itself; **a custody health check does**. It applies to **in-run failures
only** — an exchange or verdict-retention failure inside a run. A **pre-run**
custody failure is never health-checked and never classified into a method:
§2.3 blocks preparation and preregistration outright, and before
preregistration there is no runner, no method and no lifecycle to classify.

On an in-run `RETENTION_WRITE_FAILED` or `RETENTION_VERIFY_FAILED`, **the
process that owns the failing writer** performs **one bounded health check** —
an append and read-back of a canary record carrying no benchmark, prompt or
response content — before scope is decided:

- the **boundary** performs the check for the boundary-side exchange writer,
  **inside the boundary process**, and returns the original typed refusal
  together with `failure_scope` = `METHOD_LOCAL` or `REPETITION_WIDE`;
- the **runner** performs the check for the experiment-side benchmark-custody
  writer only.

The runner **never imports, holds or reaches the boundary's writer or its
credential**, and the boundary protocol must carry the scope: the merged
protocol has `RUN_BEGIN`, `CASE_BEGIN`, `CALL`, `CASE_END`, `RUN_END`,
`ATTEST`, `PING` and `SHUTDOWN` and **no custody-health operation** `[V]`
(`boundary/server.py`, `boundary/client.py`), so the scope field is
commissioned in §4. The canary carries **its own identifier** and is **never
represented as a provider exchange**: it is not a capture record, it never
reaches `llm_calls`, and it never appears as an attempt.

The verdict decides scope:

- health check **succeeds** → the failure was record-scoped: **method-local**,
  that method `INCONCLUSIVE` with its exact code, later methods may continue;
- health check **fails, times out, or cannot be performed** → **service
  failure**: the repetition stops under the rule above.

The health check is itself a custody operation, bounded by the custody
health-check timeout balloted in D4 — **not** the provider-call timeout, which
is a different port with a different owner. It is attempted **once** and never
retried, so a failing service cannot be probed into looking healthy. Its own
failure is a service failure, never a fresh method-local one. On the
boundary-side writer a `METHOD_LOCAL` scope still leaves that method
`INCONCLUSIVE`, because the boundary has already returned a non-retryable
refusal for it (§2.3); what the scope decides is whether the **repetition**
continues.

**Representing a repetition-wide halt (revision 6).** The merged result model
cannot express this halt as ruled, and the gap is mechanical, not a new
decision. Verification today requires `run_status.json` to carry **exactly**
the manifest's assigned methods, lifecycle states to cover **exactly** those
methods, and any complete method to feed a comparison result `[V]`
(`pipeline.py`, `_load_status` and `verify`; `runner.py`, `complete_runs`),
while §2.8 requires unstarted methods to have **no** lifecycle record and
forbids a winner or a success figure after a halt. The amendments in §4
therefore must: add a **non-governed repetition-level status** — halted or
incomplete — to `run_status.json`, carrying the fatal refusal; represent
unstarted methods in run status **without fabricating** a `MethodRun`, an
execution record or a lifecycle state; relax verification's exact
lifecycle-method equality **only** for a validated repetition-wide halt;
**suppress creation and rendering of the comparison request and result**
after a repetition-wide trust failure even when earlier methods completed —
their evidence stays individually verifiable; and make coverage and report
rendering distinguish an **incomplete repetition** from ordinary
method-local incompleteness, with `success_summary` unavailable in the
former `[V]` (`contracts/coverage.py`).

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
  (**recommended, revision 4**): the principal or role, the token audience,
  the secret location, and the credential-source mechanism;
- B. an external supervisor injects it directly into the boundary process:
  the supervisor identity, the handoff mechanism, and **prior ratification**
  of the separately specified launch/connection-port amendment over the
  existing frame protocol and supported transports (§2.4, §4);
- C. the runner inherits it under a tested non-reading, non-serialising
  convention, **explicitly labelled non-isolating**: the single
  environment-variable name.
**Identity policy is ruled, not open (revision 4):** refuse any provider that
cannot return an immutable deployment identity, enforced by the factory
comparison and the boundary hard stop of §2.5, with the repetition-wide stop
of §2.8. Requester-declared identity is not an available mode. In every
option the credential never appears in arguments, manifests, logs, bundles,
retention records or this repository, and the child process receives the
§2.4 allowlist only — **every admitted environment key named in this item**.

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
repetition and the `manifest_id` naming rule (§2.2); the **custody
health-check timeout** of §2.8, stated separately from the provider-call
timeout below; stochastic-control
declaration (seed per repetition, or "provider offers no seed" with the
pinned temperature); concurrency (sequential unless stated); run-level call
ceiling and its scope (per run, per method, per case); spending ceiling with
its pricing source, currency and the count it is derived from; timeout per
provider call and who owns it (provider factory); retry policy, with every
retry a captured attempt that counts in `llm_calls`; stop conditions; and case
ordering (preregistered order, or a declared randomisation with its seed).
The **partial-run policy is ruled in §2.8** (trust-infrastructure failure
stops the repetition; a method-local failure, a ceiling breach included, ends
only that method `INCONCLUSIVE`; scope decided by the one bounded custody
health check) and is ratified by this item, not re-decided in it. So is the
§2.2 rule that a halted repetition is replaced by a **new** preregistration
with a distinct `manifest_id`, never re-run under the same commitment — the
repetition count this item fixes is a count of **preregistered** repetitions,
and a halted one is not replaced within it. The D4 timeout bounds the health
check. The boundary-side hard stop at the call ceiling is a 4A amendment
ratified by this item.

**D5. Preregistration and evidence retention.**
Values: the preregistration medium and the receipt form in which the owner
records the commitment identifier `workflow_fit_prepared_index.v1` and the
prepared bundle's `index_digest` before execution (§2.1), per repetition; the two custody writers of §2.3 with their locations, writer
identities, access-control lists, encryption and key custody, retention
period and deletion rule; **whether the §2.8 health-check canary records
share the evidence custody store**, and whether that retention period and
deletion rule apply to them; the **durable spent-commitment authority** of
§2.2 — registry and location, the authority permitted to mark a commitment
spent, the atomic check-and-mark operation, the exact point of consumption
(before boundary startup unless stated otherwise), the behaviour when the
registry is unavailable, and the crash-recovery rule where a commitment is
marked spent but no provider call occurred; and the ratification of the
boundary-side exchange
writer, the runner retention amendment and the three new refusal codes as 4A
amendments. The fail-closed behaviour is **ruled in §2.3**, not decided here:
pre-run custody failure blocks preparation and preregistration; an in-run
failure is classified by the operation that failed and carries
`RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED` or `EVALUATION_FAILED`,
with the repetition scope of §2.8.
Git keeps digests and the governed evidence objects only. Digest-only
evidence is insufficient for later independent re-evaluation.

## 4. What ratification would commission `[I]`

Only after all five items are ratified: `prepare` extended to write
`provider_configuration.json` and `experimental_design.json` under the exact
§2.1 layout and to refuse non-`score.unit` or non-mean configuration; `run`
and `verify` extended to take and enforce the preregistered commitment
identifier and `index_digest` together; a boundary-side provider factory
implementing the D1 option, decoding parameters and the §2.5 identity
comparison; the **4A amendments**, each with acceptance rows and a spec §11
record: (i) boundary hard stop at the call ceiling and on
`PROVIDER_IDENTITY_UNVERIFIED`; (ii) boundary-side exchange writer; (iii)
runner amendment discarding the method's evidence after a post-attestation
retention or evaluation failure and emitting `INCONCLUSIVE` with the exact
stage code; (iv) the three refusal codes added to `PilotErrorCode`; (v) only
if D1 selects option B, a separately ratified launch/connection port over the
existing frame protocol; the benchmark-custody writer with the runner-side
bounded health check of §2.8; a **boundary-internal** exchange-writer health
check whose `failure_scope` (`METHOD_LOCAL` / `REPETITION_WIDE`) is carried
back with the typed refusal, which the merged frame protocol cannot express
today `[V]`; the **repetition-level halt representation** of §2.8 — run-status
halt field, unstarted methods without fabricated evidence, the narrowed
verification equality, comparison suppression, and coverage and report
rendering that separates an incomplete repetition from method-local
incompleteness; the runner amendment preserving the **exact** refusal code and
validating every reason string (§2.3); and `run` performing the atomic
check-and-mark against the D5 spent-commitment registry before boundary
startup, refusing a commitment already consumed (§2.2) — commissioned only
once that registry is ratified. One preregistered run per repetition. The CI
gate stays provider-free.

**Acceptance obligations.** Each branch ruled above needs its own row, and no
row may reach a provider:

| # | Obligation |
|---|---|
| T1 | `run` and `verify` refuse a correct `index_digest` under a different commitment identifier, and a correct identifier with a mismatched digest |
| T2 | `prepare` refuses a prepared set that omits, or adds to, the nine-file §2.1 layout; `index.json` is absent from its own artifact map |
| T3 | a pre-run benchmark-custody write failure leaves no manifest, no run and **no lifecycle record** |
| T4 | a pre-run benchmark-custody read-back failure does the same |
| T5 | a boundary exchange **write** failure during an attempt yields `RETENTION_WRITE_FAILED`, the attempt recorded in boundary memory, no execution record, no attestation, and a direct `PROPOSED` → `INCONCLUSIVE` record |
| T6 | a boundary exchange **verification** failure yields `RETENTION_VERIFY_FAILED` on the same path |
| T7 | after either, the workflow cannot make a further provider call for that method (the refusal is non-retryable) |
| T8 | a post-attestation verdict-retention failure discards record, attestation, claim, result, evaluation and observation from the emitted evidence and transitions to `INCONCLUSIVE` with the retention code |
| T9 | a scorer failure yields `EVALUATION_FAILED` — never a retention code — and discards the same evidence |
| T10 | a trust-infrastructure failure stops the repetition: unstarted methods emit no lifecycle record and no result, and the report is labelled incomplete with no winner and no success figure |
| T11 | a method-local failure leaves later methods runnable, and coverage exposes the missing method with no complete-set comparison |
| T12 | absent, mismatched, or cross-attempt-inconsistent provider identity yields non-retryable `PROVIDER_IDENTITY_UNVERIFIED` and the §2.8 repetition stop |
| T13 | a verified identity reaches `provider_id`; no requester-declared identity path exists |
| T14 | the child process environment equals the ratified allowlist exactly; no refusal payload, log line or retained record carries the credential, a prompt, a response or an expected answer |
| T15 | the exception class reaches only the method's `run_status.json` reason and the `report.txt` line rendered from it — no lifecycle record, contract object or custody record carries it; the reason begins with the refusal code; a diagnostic needing a secret, prompt, response or expected answer is omitted; and `verify` still re-renders the report byte-identically |
| T16 | a retention failure whose custody health check succeeds is method-local and later methods run; one whose health check fails, times out or cannot be performed stops the repetition; the health check is attempted exactly once and carries no benchmark content |
| T17 | a halted repetition cannot be re-run under its own manifest and `index_digest` — `run` refuses the commitment the registry records as spent — and its evidence survives the replacement repetition intact |
| T18 | the exchange-writer health check runs inside the boundary and its scope reaches the runner in the refusal; the runner holds no reference to that writer or its credential, and no import path exposes it |
| T19 | the canary carries its own identifier, produces no capture record, does not change `llm_calls`, and never renders as a provider attempt |
| T20 | a pre-run custody failure is never health-checked and never classified into a method: no runner, no lifecycle record, no `INCONCLUSIVE` |
| T21 | after a repetition-wide halt, unstarted methods have no `MethodRun`, no execution record and no lifecycle state; `run_status.json` carries the halt and its fatal refusal; verification accepts the bundle |
| T22 | after a repetition-wide halt no comparison request or result is created or rendered, no winner and no success summary appear, and each earlier method's evidence still verifies individually |
| T23 | the report distinguishes an incomplete repetition from a method-local incompleteness |
| T24 | a `RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED` or `EVALUATION_FAILED` reaches the lifecycle record unchanged — never collapsed to `WORKFLOW_FAILED` or `CAPTURE_INCOMPLETE` — and a reason string that is not a string, lacks its code prefix, or carries anything beyond operation, method identity and exception class is refused |
| T25 | the registry's check-and-mark is atomic and precedes boundary startup: a second `run` of the same commitment is refused, an unavailable registry refuses rather than proceeds, and a commitment marked spent before any provider call stays spent |

## 5. Explicitly excluded

Provider calls before ratification; any credential in the repository or in
any artifact; cross-run aggregation; advisor changes from pilot results;
readiness composites; production eligibility, approval or configuration
mutation; TEV integration; any quality unit or aggregation other than §2.6;
any claim that a run measures reasoning quality beyond the declared
benchmark; **requester-declared provider identity as an execution mode**
(§2.5 — an excluded future research option only); **any newly invented
credential transport** — TCP credential port, HTTP credential protocol or
other secret-transfer protocol (§2.4); and a generic `RETENTION_FAILED`
refusal where the failing stage is known (§2.3).

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
| B3 | In-run custody failure could abort without an `INCONCLUSIVE` record; pre-run and in-run failures conflated | pre-run failure blocks preregistration; in-run failure is `RETENTION_FAILED` via a narrow runner amendment commissioned in §4 (§2.3, D5) — **the single code is superseded by the three stage codes of revision 4** |
| B1 | Unversioned index promoted to a commitment | commitment identifier `workflow_fit_prepared_index.v1` with algorithm and layout pinned in bundle and receipt; `run`/`verify` check identifier and digest together (§2.1, D5) |
| M4 | Option-specific values missing; option B unimplementable | values enumerated per option; launch/connection port amendment commissioned only if B is selected; allowlist derived from the option (§2.4, D1, §4) |
| M5 | Returned identity had no representation or stop semantics | factory compares before returning, verified identity in `provider_id`, boundary hard stop `PROVIDER_IDENTITY_UNVERIFIED` (§2.5, D1, §4) |

### Revision 4 (owner rulings on the remaining design questions, 2026-09-03)

The owner issued these on their own authority, in their own wording, as
rulings rather than recommendations. They close the design questions the
third review left open; they do **not** ratify D1–D5, which stay `[R]` and
still require their concrete provider, benchmark, threshold, budget, identity
and custody values.

| # | Question left open | Owner ruling |
|---|---|---|
| B1 | which artifacts `workflow_fit_prepared_index.v1` covers | the nine named files of §2.1; `index.json` holds identifier, map and digest and is excluded from its own map; `experimental_design.json` is the single selected scenario and `scenarios.json` is not in v1; any layout or algorithm change takes a new identifier |
| B3 | which exceptions trigger which refusal | classify by **the operation that failed**, never by exception class: `RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED`, `EVALUATION_FAILED`; no generic `RETENTION_FAILED` where the stage is known; an evaluation failure is never a retention failure |
| B3 | the exception boundary | `Exception` may be caught at each port call site because the site fixes the category; `BaseException` never; the concrete class is non-authoritative diagnostic information carrying no secret, prompt, response or expected answer |
| B3 | in-run boundary custody behaviour | attempt recorded in boundary memory, method fatally incomplete, typed refusal returned, no further provider call for that method, no record and no attestation, direct `PROPOSED` → `INCONCLUSIVE` |
| — | partial-run scope (new §2.8, ratified under D4) | trust-infrastructure failure stops the repetition with no fabricated lifecycle for unstarted methods and an incomplete-labelled report; a method-local failure ends only that method |
| M4 | option B's connection mechanism | none is invented: no TCP credential port and no HTTP credential protocol; A recommended; B only via a separately ratified launch/connection-port amendment over the existing frame protocol and supported transports; C non-isolating; every allowlisted environment key named in D1; `PATH` and the interpreter are not isolation |
| M5 | identity acceptance policy | binding: refuse any provider that cannot return an immutable deployment identity; same identity required on every attempt; requester-declared identity is not a 4C mode and never shares the verified `provider_id` representation |

### Revision 5 (owner rulings on the three choices revision 4 surfaced, 2026-09-03)

Revision 4 named three policy choices and deliberately left them unruled.
The owner commissioned this revision to close them; the values below were
selected to follow the fail-closed posture the earlier rulings established,
and stand as rulings subject to the owner's correction.

| # | Choice | Owner ruling |
|---|---|---|
| 1 | where the non-authoritative exception diagnostic is retained | **the run report, carried by the method's `reasons` in the non-evidential `run_status.json`** — the artifact `verify` re-renders `report.txt` from, so a log-only diagnostic would make the bundle unverifiable; never in governed evidence (`refusal_codes` carries the code alone), never in either custody store, omitted rather than redacted when it needs a secret, prompt, response or expected answer (§2.3) |
| 2 | when a custody failure becomes a service failure | **one bounded custody health check decides**: it succeeds → method-local; it fails, times out or cannot be performed → repetition-wide. Attempted once, never retried, carrying no benchmark content; bounded by the D4 timeout (§2.8) |
| 3 | whether a halted repetition may be re-run under the same commitment | **no** — a fresh preregistration with a distinct `manifest_id` and its own index; the halted repetition's evidence is retained and reported, never overwritten, and `run` refuses the spent commitment (§2.2) |

Acceptance obligations T15–T17 carry these branches.

### Revision 6 (third-model review of the revision-5 selections, applied on owner instruction, 2026-09-03)

An independent review confirmed the diagnostic selection, corrected the
health-check mechanics, and found the halted-commitment ruling unenforceable
against the merged repository. Every correction below is **forced by the
revision-4 and revision-5 rulings**; one new owner choice is recorded as open,
not decided.

| # | Defect | Correction |
|---|---|---|
| 1 | the runner cannot health-check the boundary-side writer: that writer and its credential live inside the boundary process, and the merged protocol has no custody-health operation `[V]` | the process owning the writer performs the check — boundary internally, returning the refusal plus `failure_scope`; runner for benchmark custody only; the protocol carries the scope; the canary has its own identifier and is never a provider exchange (§2.8, §4) |
| 2 | "refuse a spent commitment" has no authoritative state store: `run` consults no history, the prepared bundle is immutable, a local run directory binds no other machine `[V]` | the ruling stands and is marked `[G]` until the **durable spent-commitment authority** is ratified — registry, marking authority, atomic check-and-mark, consumption point, unavailability behaviour, crash recovery — balloted under D5 (§2.2, D5) |
| 3 | §2.8 health-checked "any" retention failure, contradicting §2.3's pre-run block | the discriminator applies to **in-run** failures only; a pre-run failure blocks preparation with no health check and no method classification (§2.8) |
| 4 | the merged result model cannot represent a repetition-wide halt: run status and lifecycle states must cover exactly the manifest's methods, and complete methods feed a comparison `[V]` | run-status halt field with the fatal refusal; unstarted methods without fabricated evidence; verification equality narrowed for a validated halt only; comparison suppressed; coverage and report separating an incomplete repetition from method-local incompleteness (§2.8, §4) |
| 5 | the runner's generic mapping would collapse the new codes, and reason strings were unvalidated `[V]` | the amendment preserves the exact code and validates every reason string's type, code prefix and permitted content (§2.3, T24) |

The **durable spent-commitment authority is the only new owner choice** this
review introduces. Ballot items remain five and remain `[R]`; nothing was
ratified by any revision. No revision changed code, contract or CI gate, and
none authorises a provider call.
