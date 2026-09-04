# Phase 4C — First Genuine Research-Only Workflow-Fit Pilot: Commissioning Note and Ballot

**Revision 15.** Status: documentation only. **Nothing in this note authorises a
provider call.** Until every ballot item in §3 is ratified by the owner, no
code path in this repository may contact a provider, hold a credential, or
run a real workflow behind the pilot boundary.

**Decision status after the post-revision-9 owner round.** D1–D5 are
**partially decided and none is fully ratified**. The owner ratified a body of
**policy** in that round (§3.1, revision-10 record); the **facts** each ballot
needs — provider, benchmark, people, task class, pricing, infrastructure,
custody locations and retention periods — remain open, and several selections
remain **conditional** on facts not yet supplied. Ratifying policy is not
ratifying a ballot item. **Phase 4C implementation is not commissioned**, no
genuine provider-backed pilot is authorised, and PR #1578 remains a
documentation-only commissioning pull request. Every output of a ratified 4C
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

**Re-running a halted repetition — OWNER-RATIFIED POLICY, REVISION 10** (assistant selection at revision 5; selected by the owner in the post-revision-9 round).** A repetition
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

**The enforcing authority — the registry's adoption and semantics are
OWNER-RATIFIED POLICY, REVISION 10**; its endpoint, writer identity and
addressing remain open or proposed (§3.1).** Revision 6 recorded that nothing durable marks a commitment consumed:
`run` verifies bundle contents and consults no history `[V]` (`pipeline.py`,
`run`), the prepared bundle cannot hold the mark because it is immutable and
its digest **is** the commitment, and a local run directory binds no other
machine. The owner adopted the registry in the post-revision-9 round. The mechanics
below are ratified policy **except** the writer-identity name and addressing,
which remain assistant proposals (§3.1):

| Question | Status after revision 10 |
|---|---|
| registry and location | a dedicated **append-only commitment registry**, co-located with the D5 preregistration medium and addressed by the pair (commitment identifier, `index_digest`). It is **not** either custody store: expected answers keep their own access-control list, and a store the runner host must write to may not be the store holding answers |
| marking authority | one named **registry writer identity**, distinct from both custody writers, from the boundary and from the evaluator. `run` acts as that identity and no other principal may append a consumption entry |
| atomic check-and-mark | a **single conditional append** — commit an entry only if no consumption entry exists for that pair — over the medium's native atomic primitive. Never read-then-write: two concurrent `run` invocations must resolve deterministically, one proceeding and one refused |
| consumption point | **immediately before boundary startup**: after `run` has matched the preregistered identifier and digest (§2.1) and before the boundary process is constructed or launched, so a halt with no provider call still consumes |
| registry unavailable | **fail closed**, exactly as a pre-run custody failure does: refuse with `COMMITMENT_REGISTRY_UNAVAILABLE`, start no boundary, write no lifecycle record. An unreachable registry never permits an optimistic run |
| crash after marking, no provider call | the commitment **stays spent**. Consumption is terminal: no rollback, no unmark, no reuse, and the replacement is a new preregistration with a distinct `manifest_id` (above). A run appends a closing outcome entry when it terminates, but a **missing** outcome entry never reopens a commitment — that asymmetry is what stops a crash from becoming a re-roll |

A second `run` of a consumed commitment would be refused with
`COMMITMENT_ALREADY_SPENT`. Both codes are **proposed** additions to the
governed vocabulary (§4). The revision-6 `[G]` is **not** lifted by this
proposal: the decision remains open until the owner ratifies a durable
authority. T17 and T25–T27 are acceptance obligations for this **proposed**
mechanism, testable against a conforming registry double, and they test nothing
ratified.

**Deployment facts — PROPOSED, NOT RATIFIED (assistant selection, revision 8;
relabelled revision 9).** The registry writer identity is
`workflow_fit_commitment_registry.writer`, a name reserved to this purpose and
held by no custody writer, boundary or evaluator. Entries are addressed
`commitments/<commitment identifier>/<index_digest>`, one consumption entry
and at most one outcome entry per pair. The registry's **concrete endpoint is
bound at D5 ratification and is deliberately not written here**: it names
infrastructure that does not exist in this repository, and a plausible-looking
URI in a governance document would be a fabricated `[V]`. Everything a test
needs — the identity, the addressing, the atomicity and the refusal codes — is
fixed above, so T17 and T25–T26 could be exercised against a conforming
registry double before the endpoint exists — as obligations for a proposed
mechanism, not a ratified one.

### 2.3 Custody writers (resolves B3)

The boundary sees provider prompts and responses; the experiment-side scorer
alone sees expected answers. **Expected answers must never enter the
provider boundary.**

**Rule — the two-writer design is OWNER-RATIFIED POLICY, REVISION 10**
(assistant design, revisions 2–3; not ratified by the revision-4 instruction,
which assumed it; selected by the owner in the post-revision-9 round). The
**pre-run custody block** and the **post-attestation discard** below are
owner-ratified on the same authority. The **in-boundary exchange-custody
path** and its direct `PROPOSED` → `INCONCLUSIVE` transition remain
owner-ratified from revision 4.
Two append-only custody writers, each referencing the manifest digest and the
preregistered `index_digest`:

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

**Where the diagnostic is retained — PROPOSED, NOT RATIFIED (assistant
selection, revision 5; relabelled revision 9).** In the
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
(4A spec §4 transport prose; `transport` on `run_pilot`; the equivalence test
`test_a16d_transport_equivalence`). If B is later selected, its exact
supervisor handoff and attachment mechanism must be ratified **before**
implementation; no mechanism is specified here. Option C remains explicitly
**non-isolating**.

Under option A the bounded claim is: **the secret does not enter the runner
process or the runner environment; the boundary process retrieves and holds
it.** It does not follow that the secret is absent from the whole process
tree — the boundary is a child process on the same host.

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
it happened. This partial-run policy is owner-ratified from revision 4; D4
remains open and must supply its implementation controls.

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

**The discriminator — OWNER-RATIFIED POLICY, REVISION 10** (assistant
selection at revision 5; mechanics corrected on owner-transmitted review at
revision 6; adopted by the owner in the post-revision-9 round).** A retention write or verification failure does not classify
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

The health check is itself a custody operation, bounded by the **custody health-check timeout of 5 000 ms**, owner-ratified in revision 10 (D4) — **not** the provider-call
timeout, which is a different port with a different owner. It is attempted
**once** and never retried, so a failing service cannot be probed into looking
healthy.

**Where the canary is written — OWNER-RATIFIED POLICY, REVISION 10.** Into the **same
custody store** whose health is in question, under a **reserved key prefix**.
A canary written anywhere else would prove nothing about the store that just
failed, which is the whole purpose of the probe. It is excluded from every
evidence read, never keyed by case digest, and carries its **own** retention
and deletion rule rather than the evidence retention period: probes are
operational exhaust and must not accumulate under evidence retention, nor
dilute what an independent re-evaluator reads. Canaries carry a **separate** retention and deletion policy, owner-ratified in
revision 10; the **period itself is an OPEN OWNER FACT** and the assistant's
30-day figure is **withdrawn**, after which a canary is deleted; deleting one is never an
evidence deletion and never touches a record keyed by case digest. Its own
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

### 2.9 Call ceiling and workflow budget exhaustion (revision 9)

**One shared cap, not per-method `[V]`.** `HarnessWorkflowExecutor.__init__`
stores a single `max_llm_calls` and passes that same value to every workflow:
`wf.execute(query, client, context=context, max_llm_calls=self._max)`
(`experiments/workflow_fit_study/pilot_executor.py`). A method-specific cap is
**not expressible** against the merged executor. Any per-method ceiling is
therefore an accounting figure, not an enforcement point.

**Exhaustion is silent `[V]`.** `ReasoningWorkflow._call_llm` checks
`if call_counter[0] >= max_calls` and, when the budget is spent, appends a
step whose `response` is the runtime sentinel `"(budget exhausted)"` and
returns normally (`agentic/agentic_framework/reasoning_workflows.py`). No
exception, no refusal, no telemetry signal. An undersized cap therefore yields
a **completed** run with a truncated reasoning path, scored as though the
method had run as designed — a comparison biased toward methods with shorter
intrinsic paths, with nothing in the evidence to show it.

The seven workflows' intrinsic bounded paths per case `[V]`:

| Workflow | Declared default | Intrinsic bounded path |
|---|---|---|
| `linear_chain` | 4 | 4 fixed stages |
| `tree_of_thought` | 8 | 5 = `num_branches` 3 + score + synthesise |
| `iterative_refinement` | 8 | 7 = generate + `max_revisions` 3 x (critic + revise) |
| `debate` | 5 | 4 fixed stages |
| `map_reduce` | 8 | 6 = decompose + up to `max_sub_problems` 4 + reduce |
| `socratic_progressive` | 4 | 4 fixed stages |
| `metacognitive` | 10 | delegates to a selected workflow; at most the delegate's path |

**OWNER-RATIFIED POLICY, REVISION 10.** The largest bounded path among the
seven workflows as they stand is **7** calls, so a shared cap of **7** already
clears every present path. The proposed value is **8**, which is 7 plus one
call of headroom against a workflow whose parameters change (`num_branches`,
`max_revisions`, `max_sub_problems` are constructor arguments). Per-method
ceiling `case_count x 8` — an accounting figure, since the executor cannot
enforce per method; repetition ceiling the sum of the assigned methods'
ceilings; retry allowance **zero**. A cap of 7 is sufficient today and a cap
below 7 would truncate at least one workflow; it is **not** the case that
every value below 8 truncates.

**Detection, experiment-side.** A `CaptureRecord` carries digests, never a
stage response, and `HarnessWorkflowExecutor` currently **discards**
`WorkflowResult.steps`, returning only `final_response` and
`total_llm_calls_reported` `[V]` (`pilot_executor.py`; `runner.py`,
`ExecutionOutcome`). Exhaustion is therefore invisible to the boundary and to
every governed contract. **PROPOSED — NOT RATIFIED:** an experiment-side check
inside `HarnessWorkflowExecutor` inspects **all** `WorkflowResult.steps`
before returning an `ExecutionOutcome`; if any step's `response` equals the
runtime sentinel `"(budget exhausted)"`, that method must **not** enter a
comparison and must become `INCONCLUSIVE`. The sentinel is a runtime string in
`agentic/`, not a governed constant; a check depending on it must fail closed
if the string changes.

**A seventh refusal code — selected in revision 10.**
`WORKFLOW_BUDGET_EXHAUSTED` names this condition. With the six others (§4) the
owner selected **seven** additions. The enum itself is unchanged: it has 33
members today `[V]`, and a future commissioned vocabulary would have 40.

**The sentinel becomes a shared constant — owner-ratified policy, revision
10.** `"(budget exhausted)"` must be one shared runtime constant used by the
reasoning workflows, `HarnessWorkflowExecutor` and the provider-free tests.
Implementation is **deferred** until Phase 4C is commissioned. The constant
belongs on the `agentic/agentic_framework` side, where the sentinel
originates, so the experiment-side executor can import it;
`ugence_workflow_fit_pilot` must **not** import the research harness, since
that would invert the dependency boundary the adapter exists to preserve
`[V]` (`experiments/workflow_fit_study/pilot_executor.py`).

### 2.10 Unit of evaluation (owner ruling, revision 12)

**Workflow-Fit evaluates the declared primary reasoning strategy of a complete
agentic workflow.** A workflow may orchestrate multiple agents or
prompt-defined roles, but Workflow-Fit does **not** search for, optimise or
separately attribute combinations of agent-level reasoning strategies. Agent
roles, prompts, local reasoning behaviour and orchestration are part of the
**fixed workflow configuration under evaluation**; changing any of them creates
a **different workflow configuration requiring separate evaluation**.

**Verified implementation limitation `[V]`.** The current harness represents
**workflow stages and prompt-defined roles, not independently governed
agents**, and offers **no per-role reasoning binding or attribution**. No agent
concept exists anywhere in the pilot or governance packages; every workflow
receives a single `LLMClient` whose sole operation is `call(prompt) -> str`, so
stage labels such as `ADVOCATE_A`, `CRITIC_v1` or `SCORE_BRANCHES` are strings
accompanying prompts rather than addressable identities; `ReasoningMethodRef`
is `(catalog, method_id, method_version)`, one binding per workflow; and the
boundary attributes every capture record to a single `run_id` and method, so
per-role attribution is absent from the evidence as well as from the
configuration. The ruling above is therefore the only reading the merged code
can represent — and nothing in the contracts *enforces* configuration fixity,
which rests on the preregistered commitment covering the harness version.

### 2.11 Calibration and confirmatory run architecture (owner ruling, revision 13)

**The defect this resolves `[V]`.** A run role alone cannot separate the two
kinds of run. `PilotStudyManifest.plan` is a `ResearchComparisonPlan`, whose
`task_class` is a `TaskClassIdentity`, whose `comparison_policy.sufficiency.
threshold` is a `GovernedThreshold` requiring a literal or a benchmark
reference; the pilot loader additionally requires `Decimal(literal)` to parse.
A calibration manifest built on that chain **cannot exist without a
threshold**. `run_pilot` then calls `compare` whenever any run is complete, and
`summary_permitted` is derived from record completeness — so a calibration run
on the confirmatory path emits a comparison request, a comparison result,
`EVALUATED` records, a coverage report and a success summary. The resolution is
therefore structural: **calibration carries no comparison policy at all**, so
there is no threshold to fake and no request the runner could construct.

**Compatibility — both mechanisms, ratified.** A schema-version split answers
*is this artifact eligible for a genuine 4C run*; a discriminated union answers
*which role is this*. Neither alone suffices.

| Schema | Role | Status |
|---|---|---|
| `workflow_fit_pilot.manifest.v1` | none | historical **mechanism validation only**; verifiable, **never** 4C-eligible, and **never** defaulted to `CONFIRMATORY` |
| `workflow_fit_pilot.manifest.v2` | `CONFIRMATORY` | requires explicit `run_role` and complete `CalibrationProvenance` |
| `workflow_fit_pilot.manifest.v2` | `CALIBRATION` | **superseded by revision 14:** the same v2 contract with the calibration role, carrying the full governed structure below. The separate `calibration_manifest.v1` contract and `CalibrationTaskBinding` are **withdrawn** |

An absent, unknown or mismatched run role **fails closed**. A calibration
manifest must not contain a comparison plan, task-class identity, comparison
policy, governed threshold, advisory binding or multi-method role assignment.

```
PilotRunRole:
  CALIBRATION
  CONFIRMATORY
```

**Calibration manifest shape — corrected by revision 14.** Revision 13 said
calibration carries no plan and no task class. That is **incompatible with the
mandatory contracts** and is superseded. `ReasoningMethodExecutionRecord`
requires `binding: BindingRef`, `task_class_ref` and `task_class_digest`, all
mandatory `[V]` (`contracts/record.py`); `PilotObservation` requires
`task_class_digest`, `binding` and `roles` `[V]`; and `validate_observation`
cross-checks `manifest.plan == plan`, `record.task_class_digest ==
observation.task_class_digest == plan.task_class.task_class_digest`,
`record.binding == observation.binding == plan.binding`, the benchmark digests
against `plan.task_class.benchmark_set_digest`, and both aggregations against
the manifest `[V]` (`contracts/observation.py`). Without those, calibration
could produce no execution record, no attestation, no quality evaluation and
therefore no `CalibrationResult`.

**Minimum governed shape a calibration run must carry `[V]`** — verified field
by field against the constructors and validators, not assumed:

- `PilotStudyManifest` at `…manifest.v2` with `run_role = CALIBRATION`:
  `manifest_id`, `plan`, `advisory_digest = None`, `rule_set`, `methods`,
  `benchmark`, `capture_boundary`, `evaluator`, `resource_aggregation`,
  `quality_aggregation`, `preregistration_status`, `usage_scope`,
  `preregistered_by`, `preregistered_at`, `manifest_digest`.
- `ResearchComparisonPlan`: `plan_id`, `task_class`, `binding` (`BindingRef`),
  `catalog`, `baseline = linear_chain`, `recommended = ()` — which must equal
  the advisory's qualifying set, empty when no advisory is named `[V]` —
  `challengers` (`ChallengerSamplingPolicy` with `kind`, non-blank `policy_ref`
  and `declared_coverage_ref`), `usage_scope`, `preregistered_by`,
  `preregistered_at`.
- `methods`: **exactly one** `PilotMethodAssignment` — `linear_chain` with
  `roles = (GOVERNED_BASELINE,)`, matching `plan.baseline` `[V]`. No
  `ADVISOR_QUALIFIED` role, which would require an advisory digest `[V]`; no
  `CHALLENGER`.

**The calibration task class.** A full `TaskClassIdentity` binding the same
benchmark, profile, task description and baseline method as the calibration
run, with `consequence_class = NEGLIGIBLE`, `reversibility =
OUTCOME_REVERSIBLE`, `structural_characteristics = ()`, `required_dimensions =
(LLM_CALLS,)`, and — the load-bearing part — a `GovernedThreshold` that
carries **`benchmark_ref` and never `literal_value`**. `GovernedThreshold`
accepts exactly one of the two `[V]`, and the engine computes
`tau = Decimal(literal_value)` **only when `benchmark_ref is None`** `[V]`
(`engine.py`), so **no numeric calibration threshold exists and `tau` is
`None` by construction**. Its distinct `task_class_id` and threshold form give
it a `task_class_digest` different from the confirmatory class, so the two are
never interchangeable.

**Two independent protections, as ratified in revision 14:** first, no
threshold literal exists from which any fit assessment could be computed;
second, the committed `CALIBRATION` role forbids the runner from constructing
or executing a comparison request at all. Calibration therefore produces **no
fit, sufficiency, Pareto or resource-domination claim**.

**Rejected alternatives (revision 14).** Making task-class, binding or role
fields optional in the shared execution and observation contracts; removing
calibration attestation; inserting a placeholder numeric threshold; and
relying on report suppression alone.

**One consequential loader change `[V]`.** The experiment-side
`load_task_class` requires `threshold.literal` to parse as `Decimal`, so it
needs a variant accepting a benchmark-referenced threshold. That is a Phase 4C
experiment-side change, not a governance-contract change.

**`CalibrationResult`** (`workflow_fit_pilot.calibration_result.v1`):
`calibration_id`, `manifest_digest`, `evaluation_digest`, `attestation_digest`,
`statistic_value`, `governed_unit`, `score_count`, `sample_index_digest`,
`commitment_identifier`, `index_digest`, `verdict_custody_ref`, `formula_id`,
`formula_version`, `issued_by`, `issued_at`, `calibration_result_digest`.
Benchmark, method, evaluator, scoring and run fields are **not duplicated**:
`QualityEvaluationRecord` already binds manifest digest, method, record digest,
case-set digest, evaluator declaration digest, scoring-instruction digest,
aggregation, claim digest, quality-result digest, independence and evaluator
attribution `[V]`, and `QualityResult` carries the aggregate value `[V]`.

Verification must establish that `statistic_value` **exactly equals** the
`QualityResult.value` reachable through `evaluation_digest`; that
`governed_unit` is `score.unit`; that `score_count` equals the benchmark case
count; that evaluation and attestation lineage recompute; and that the
commitment pair and sample-index digest match the prepared calibration
artifacts. The aggregate can therefore never be detached from the scores and
attestation beneath it.

**`CalibrationProvenance`**, inside the confirmatory manifest digest:
`calibration_result_digest`, `calibration_manifest_digest`,
`calibration_commitment_identifier`, `calibration_index_digest`, `formula_id`,
`formula_version`, `instantiated_literal`. The verifier must establish that the
instantiated literal equals **both** the calibration statistic **and** the
confirmatory task-class threshold, and that the formula identity and every
named digest reconcile. **Any mismatch fails closed.**

**Role behaviour.**

| | `CALIBRATION` | `CONFIRMATORY` |
|---|---|---|
| Capture, attestation, custody, programmatic scoring | executed and governed | executed and governed |
| Methods | `linear_chain` only | as assigned |
| Comparison request / result | **none — unconstructible** | required |
| `RESULT_ASSESSED` / `EVALUATED` | **forbidden** | permitted |
| Coverage report | **not emitted** | emitted |
| Success summary | **impossible** — no coverage artifact exists | derived as today |
| Distinct artifact | `calibration_result.json` | comparison and coverage files |
| Successful endpoint | `UNDER_TEST`, **only** when a valid `CalibrationResult` exists | `EVALUATED` |

**A required 4A amendment, not a claim that this already works `[G]`.** The
merged lifecycle model permits a chain to rest at `UNDER_TEST` — nothing forces
progression `[V]` (`_PERMITTED`) — but it **cannot distinguish** a successfully
completed calibration from a confirmatory run that merely stopped after
`UNDER_TEST`. `UNDER_TEST` is **not** redefined as globally terminal. Making the
role-specific endpoint safe requires a Phase 4A amendment that ties the
endpoint to the presence of a valid `CalibrationResult`; until that amendment
is commissioned, the distinction is not machine-enforced.

**Accounting ceilings (baseline-only calibration).** Calibration 1 × 50 × 8 =
**400**; three confirmatory repetitions 3 × 2 800 = **8 400**; combined
**8 800**. Only the shared per-case cap of 8 is enforced; the rest is
accounting.

**Prepared-bundle identity.** Calibration prepared bundles use
`workflow_fit_prepared_index.calibration.v1`. The revision-4 confirmatory
identifier `workflow_fit_prepared_index.v1` and its **nine-path layout are
unchanged**; calibration uses the **same path set** with a **different content
model** for `pilot_manifest.json`, which is why it takes its own identifier.
This neither renames nor reinterprets the revision-4 artifact, and creates no
contradiction with the exact-layout ruling: that ruling fixes paths, and the
paths are identical.

**Threshold formula `calfloor.linear_chain.v1`.** Source statistic: the exact
arithmetic-mean quality of `linear_chain` from the baseline-only calibration.
Exact `Decimal` arithmetic; **no rounding** — with 50 binary cases every mean is
an exact two-decimal value `[V]`. Confirmatory comparator `GTE`; **one
universal threshold**, which is all the engine supports `[V]`. Malformed or
non-binary scorer output is a **conformance failure**, not a score. Absent or
inconclusive calibration **blocks threshold instantiation and confirmatory
execution**; a replacement calibration requires a **fresh commitment** (§2.2).
The instantiated literal and complete provenance must enter confirmatory
preregistration **before** execution.

**Self-reference, recorded.** In confirmatory runs the baseline is compared
against a floor derived from its own calibration performance, so its own
sufficiency verdict is definitionally self-referential and **must never be
reported as evidence about baseline quality**.

**Scorer `bbh-ld7.v3`**, superseding v2 (revision 15). **Why v2 was superseded:**
its text described `'ANSWER:'` as "the four characters", which is false — the
quoted prefix has **seven**. The literal was unambiguous and no implementation
was ever misled, but a known contradiction may not stand inside a governed,
digest-pinned procedure. **Exactly two semantic edits** produce v3 from v2: the
procedure identifier `bbh-ld7.v2` → `bbh-ld7.v3`, and "the four characters
`'ANSWER:'`" → "the seven characters `'ANSWER:'`". Nothing else in the wording,
whitespace, punctuation or behaviour changed. **The scoring algorithm and every
acceptance outcome are unchanged.**

Complete v3 normative preimage, verbatim:

```
bbh-ld7.v3: LINES. Split the final response on U+000A only; from each line remove a single trailing U+000D if present. WHITESPACE means exactly the six characters U+0009, U+000A, U+000B, U+000C, U+000D and U+0020; no other character is whitespace for this procedure. SELECTION. A line is prefix-bearing when, after removing leading and trailing WHITESPACE, it begins with the seven characters 'ANSWER:' compared using ASCII case folding only (A-Z to a-z; no other case mapping). If the response contains no prefix-bearing line the score is Decimal('0'). Otherwise select the LAST prefix-bearing line in the response; never fall back to any earlier line, even when the selected line's payload is malformed. NORMALIZATION. Take the selected line's text after the prefix; replace every maximal run of WHITESPACE with a single U+0020; remove leading and trailing U+0020; if and only if the result both begins with '(' and ends with ')', remove exactly one leading '(' and exactly one trailing ')'; remove leading and trailing U+0020 again; map ASCII lowercase a-z to uppercase A-Z and change nothing else. The normalized payload must be exactly one character and that character must be one of A B C D E F G, compared by Unicode code point; any non-ASCII character, including visually similar ones, fails this test. EXPECTED. Normalize the upstream target with the identical steps, so an upstream '(B)' normalizes to 'B'. SCORE. Return Decimal('1') when the normalized payload and the normalized expected value are equal as code-point sequences, and Decimal('0') in every other case, including a failed payload test. No partial credit. No semantic judgment. No prose fallback. No inspection of the case query.
```

UTF-8 byte length **1 704**; `ugence_jcs.canonical_sha256_hex` =
**`9cc587889c5b43dbc1f6ae796840d6af90cfe95c0e6e49cbe245f2ca5dfc1813`**, both
recomputed from the text above, which is the v3 authority. The v2 digest
`84051a08da3451a91ef084777e8aecf1211d04d63eef26ff8a04530443b870e9` over 1 703
bytes is retained as **historical evidence only** and must not be used to pin a
runtime constant. Essential behaviour, unchanged from v2: an `ANSWER:` prefix is
**mandatory**; the **last** prefix-bearing line wins even when malformed;
**there is no fallback** to an earlier line; payload must be exactly one ASCII
character `A`–`G`; parenthesis and whitespace normalisation exactly as stated;
missing, malformed, multi-character, punctuated, out-of-range and non-ASCII
answers score zero. The final `scoring_instruction_digest` still composes this
text with the benchmark manifest digest and the sufficiency rule id/version at
`prepare` `[V]`.

**Four additional refusal codes**, ratified in revision 13:
`RUN_ROLE_INVALID`, `ROLE_ARTIFACT_INCONSISTENT`,
`CALIBRATION_PROVENANCE_INVALID`, `CALIBRATION_STATISTIC_UNAVAILABLE`. Existing
codes are reused where their semantics already apply — `SCHEMA_VERSION_UNSUPPORTED`,
`MANIFEST_MISMATCH`, `MANIFEST_NOT_VALIDATED`, `STATE_TRANSITION_INVALID`,
`RECORD_MISMATCH`, `QUALITY_EVALUATION_MISMATCH`, `ATTESTATION_MISMATCH`,
`COUNT_INVALID`, `CAPTURE_INCOMPLETE` — and are not duplicated. A missing
confirmatory threshold needs no code: `GovernedThreshold` already refuses
construction `[V]`.

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
aggregation (§2.6); and the resource dimensions compared. **Owner-ratified:** `LLM_CALLS` is the
universally required dimension, and **`TOTAL_TOKENS` is not admitted**
(revision 11), because complete provider-usage reporting for every potentially
charged attempt — failures and timeouts included — has not been established;
that is not a claim that the provider never returns usage in those cases. The
pilot therefore compares resource use **by call count**, and its results must
not be represented as a comparison of token consumption or token cost. The
engine refuses
`DIMENSION_UNAVAILABLE` on a missing value with **no fallback to fewer
dimensions** `[V]` (`readiness-comparison/engine.py`), so an optimistic
declaration converts one absent usage field into a lost repetition.
`ResourceDimension` has exactly these two members `[V]`
(`contracts/task_class.py`). Threshold, unit,
aggregation and dimensions are **pilot configuration**, not architectural
defaults. Structural-token traceability per case is required but is not
itself evidence of representative sampling.

**D4. Experimental design.**
Values: repetition count and role; the `manifest_id` naming rule (§2.2); the
custody health-check timeout (§2.8, **PROPOSED at 5 000 ms — NOT RATIFIED**),
stated separately from the provider-call timeout below and never conflated
with it; stochastic-control declaration (seed per repetition, or "provider
offers no seed" with the pinned temperature — note that **temperature 0
removes a major sampling control but does not establish determinism**, since
providers may still vary across attempts); concurrency (sequential unless
stated); the call ceiling of §2.9; spending ceiling with its pricing source,
currency and the count it is derived from; timeout per provider call and who
owns it (provider factory); retry policy, with every retry a captured attempt
that counts in `llm_calls`; stop conditions; and case ordering (preregistered
order, or a declared randomisation with its seed).

**Repetition count and role — PROPOSED, NOT RATIFIED.** With an external
threshold basis fixed before the pilot: **3 confirmatory repetitions**.
Without one: **1 calibration run + 3 confirmatory repetitions**. The
calibration run carries its **own preregistered commitment**, is labelled
`CALIBRATION`, is **not** one of the three, and **never enters the
confirmatory comparison, coverage report or success summary**. It **only
instantiates** a threshold from a rule preregistered **before** it runs
(revision 12): the statistic, the mechanical mapping formula, rounding,
boundary-equality behaviour, treatment of missing and inconclusive methods,
threshold scope, and any evidence-admission reference the consequence class
requires must all be fixed in the commitment first. **The formula itself is
still open and therefore blocks calibration execution** — no calibration run
may be authorised until it is preregistered. Because a 50-case binary mean is
quantised to 0.02 (§3.1), the rounding rule must state behaviour at exact
multiples of 0.02, and a threshold finer than 0.02 is unrepresentable in the
result.

**`manifest_id` — PROPOSED, NOT RATIFIED.**
`<benchmark id>@<benchmark version>.<task class id>.<CALIBRATION|CONFIRMATORY>.rep<ordinal>.<pre-execution nonce>`,
the nonce derived before execution and recorded in the D5 receipt. A
replacement after a halt takes a **fresh nonce or a new ordinal**; the halted
identity is never reused or overwritten.

**Call ceiling — PROPOSED, NOT RATIFIED.** Shared per-case cap 8; per-method
ceiling `case_count x 8`; repetition ceiling the sum over assigned methods;
retry allowance zero. The merged executor supports one shared value only
(§2.9).
**Owner-ratified by this item, and only this:** the revision-4 partial-run
policy — a trust-infrastructure failure stops the repetition; a method-local
failure ends only that method `INCONCLUSIVE`.

The following are **PROPOSED — NOT RATIFIED** and are **not** folded into that
ruling: the bounded custody health-check discriminator and its 5 000 ms
timeout (§2.8); the prohibition on reusing a halted commitment (§2.2); the
replacement manifest identity above; and the commitment-registry mechanics
(§2.2, D5). Ratifying the partial-run policy does not ratify any of them. The
boundary-side hard stop at the call ceiling is a 4A amendment this item would
ratify.

**D5. Preregistration and evidence retention.**
Values: the preregistration medium and the receipt form in which the owner
records the commitment identifier `workflow_fit_prepared_index.v1` and the
prepared bundle's `index_digest` before execution (§2.1), per repetition; the two custody writers of §2.3 with their locations, writer
identities, access-control lists, encryption and key custody, retention
period and deletion rule. **PROPOSED — NOT RATIFIED (assistant selections, revisions 7–8):**
health-check canaries share the store they probe under a reserved prefix,
excluded from evidence reads, under a **30-day** canary retention (§2.8); and
the **spent-commitment authority** of §2.2 in full — registry co-located with the
preregistration medium, addressing
`commitments/<identifier>/<index_digest>`, the writer identity
`workflow_fit_commitment_registry.writer`, a single conditional append,
consumption immediately before boundary startup, fail-closed when
unavailable, consumption terminal after a crash. The **registry's concrete
endpoint is the one value this item still needs**; it names infrastructure
outside this repository. Encryption note: customer-managed key custody protects the retained evidence
**only when the runner, the workflows and unrelated operators lack decrypt
permission**; a customer-managed key whose decrypt authority the runner
principal retains protects nothing against that principal's compromise.
Also the ratification of the boundary-side exchange writer, the runner
retention amendment and the **six** new refusal codes (§4) as 4A amendments. The fail-closed behaviour is **ruled in §2.3**, not decided here:
pre-run custody failure blocks preparation and preregistration; an in-run
failure is classified by the operation that failed and carries
`RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED` or `EVALUATION_FAILED`,
with the repetition scope of §2.8.
Git keeps digests and the governed evidence objects only. Digest-only
evidence is insufficient for later independent re-evaluation.

### 3.1 Decision status of every selection (revision 10)

Four statuses, and nothing sits between them. **Policy ratification is not
ballot ratification:** no D-item below is complete, because each still needs
facts listed as open.

#### OWNER-RATIFIED POLICY — REVISIONS 10–11

Selected by the owner in the post-revision-9 D1–D5 decision round, except the two
rows marked **(revision 11)**, which come from the later D1 provider-route
decision.

| Ballot | Ratified policy |
|---|---|
| D1 | temperature 0; top-p 1.0; maximum output 1024 tokens; no stop sequences |
| D1 | preregistered seed per repetition where supported, else an explicit "provider offers no seed" declaration |
| D1 | credential option A, boundary-side workload identity; immutable deployment identity required on **every** attempt |
| D1 | bounded credential claim: the credential does not enter the runner process or runner environment; the boundary retrieves and holds it |
| D1 | allowlist **policy**: derive the smallest functional child-process environment by provider-free testing; admit no key for convenience; admit `PYTHONPATH` only if proven necessary and its value controlled; `PATH` and the interpreter are process prerequisites only, never credential isolation; every exact key and constraint returns for separate owner ratification before a genuine run |
| D2 | append-only benchmark versioning; a correction creates a new version, never an in-place mutation |
| D2 | expected answers accessible only to the scorer, never in workflow-visible inputs and never in the provider boundary |
| D2 | distinct benchmark author and approver |
| D2 | the two-writer custody architecture (§2.3) |
| D2 | pre-run custody failure blocks preparation and preregistration |
| D2 | post-attestation retention or evaluation failure discards that method's emitted evidence and makes it `INCONCLUSIVE` |
| D3 | `LLM_CALLS` universally required |
| D3 | missing required usage produces `DIMENSION_UNAVAILABLE`; no fallback, no zero-filling, no reduced-dimension comparison |
| D3 | **(revision 11)** `TOTAL_TOKENS` **not admitted**; `LLM_CALLS` alone is the operative resource configuration. Grounds: complete provider-usage reporting for every potentially charged attempt — failures and timeouts included — has not been established. This is not a claim that the provider never returns usage in those circumstances |
| D3 | **(revision 11)** the pilot therefore compares resource use **by call count**. Its results must not be represented as a comparison of token consumption or token cost |
| D2–D3 | **(revision 12)** results apply only to the 50 sampled items under the pinned wrapped configuration; they do **not** generalise to BBH overall, to logical reasoning generally, or to production workloads |
| D2–D3 | **(revision 12)** published BBH scores are **not directly comparable**, because this pilot adds an output wrapper to each case |
| D2–D3 | **(revision 12)** scorer-only custody prevents runtime answer leakage but does **not** establish absence of training-data contamination; the upstream canary string expresses maintainer intent, not provider compliance `[V]` |
| D2–D3 | **(revision 12)** case and expected-answer digests provide **integrity, not confidentiality**; for this seven-option benchmark a party holding the public inputs can brute-force the committed answer in seven trials |
| D4 | **(revision 12)** accounting ceilings: **2 800** maximum workflow calls per repetition (7 workflows × 50 cases × shared per-case cap 8) and **11 200** across one calibration plus three confirmatory repetitions. Under the selected design there are **no known provider calls outside the workflows' `_call_llm` paths** `[V]`. Only the **shared per-case cap of 8** is enforced; the per-method and repetition totals are accounting figures |
| D3 | `score.unit`; arithmetic-mean aggregation |
| D3 | threshold sourced externally where a defensible external basis exists; otherwise one separate calibration run **instantiates a threshold from a rule preregistered before it runs** (revision 12). The commitment must fix the statistic, the mechanical mapping formula, rounding, boundary-equality behaviour, treatment of missing and inconclusive methods, threshold scope, and any required evidence-admission reference. **Calibration confers no post-hoc discretion**: a threshold may never be chosen after inspecting calibration results |
| D3 | representativeness requires an explicit population, a sampling procedure and a written limitation statement; structural-token traceability alone does not prove representative sampling |
| D4 | shared per-case cap **8**; 7 clears every current bounded path; 8 gives one call of headroom and does **not** guarantee safety after workflow change |
| D4 | every workflow or constructor-parameter change reruns the provider-free bounded-path test |
| D4 | per-method and repetition ceilings are accounting figures, not independent enforcement controls |
| D4 | zero retries; sequential execution; 60-second provider-call timeout |
| D4 | calibration carries its own preregistered commitment and never enters confirmatory comparison, coverage or success reporting |
| D4 | manifest identity `<benchmark id>@<benchmark version>.<task class id>.<CALIBRATION\|CONFIRMATORY>.rep<ordinal>.<pre-execution nonce>`; replacement after a halt uses a fresh nonce or ordinal; the halted identity is retained and never overwritten |
| D4 | bounded custody-health-check discriminator adopted; 5 000 ms timeout; performed by the process owning the writer; one check, no retry |
| D4 | stop conditions: call-ceiling breach, spending-ceiling breach, trust-infrastructure failure |
| D5 | external append-only preregistration |
| D5 | receipt binds commitment identifier, `index_digest`, `manifest_id`, nonce, recording instant and recorder identity |
| D5 | a halted commitment may not be reused |
| D5 | durable spent-commitment registry adopted; separate from both custody stores; logically co-located with the preregistration authority where feasible |
| D5 | single conditional append, never read-then-write; consumption immediately before boundary startup; unavailability fails closed; consumption terminal after a crash; a missing outcome entry never reopens a commitment |
| D5 | canary written to the custody store it tests under a reserved prefix; excluded from evidence reads and case-digest addressing; separate retention and deletion policy |
| D5 | customer-managed encryption, bounded: it protects retained evidence only when the runner, workflows and unrelated operators lack decrypt permission |
| codes | seven additions **owner-ratified in revision 10**; four calibration codes added in revision 13, eleven in total (§2.11, §4) |
| codes | `"(budget exhausted)"` must become one shared runtime constant (§2.9, §4) |

#### CONDITIONAL OWNER SELECTION — PROVIDER ROUTE (D1)

Selected by the owner in the post-revision-10 D1 decision round as the
**conditional default route**. This is **not** completed D1 ratification and
**not** a verified provider fact.

**Evidence status.** Every provider-side claim in this table is
**owner-supplied or externally transmitted**, never `[V]`. Official OpenAI
documentation was **not reachable** from the environment that produced this
note — `developers.openai.com` and `platform.openai.com` are blocked by egress
policy — so nothing here was fetched or independently verified. The official
pages are listed below as **evidence references to be checked**, not as
citations supporting a verified claim.

| Field | Owner-selected value (not verified) |
|---|---|
| Provider route | OpenAI API direct |
| Model candidate | `gpt-4.1-2025-04-14` |
| API surface | Chat Completions |
| Credential architecture | boundary-side OpenAI workload-identity federation mapped to a Platform service account (the D1 option-A shape of §2.4; §2.4's allowlist-derivation policy is unchanged and still requires separate ratification of the key set) |
| Operative resource configuration | `LLM_CALLS` only |
| `TOTAL_TOKENS` | not admitted |
| Evidence status | owner-supplied / externally transmitted; **not** `[V]`; not fetched or independently verified |

**This selection does not establish compliance with §2.5.** The owner-ratified
refusal of any provider that cannot return an immutable executed deployment
identity is unchanged and is **not** satisfied by naming a route. **If the
confirmation below fails, the route is disqualified.**

**Unresolved conditions — all must be satisfied before D1 can complete:**

1. the response `model` must be confirmed to identify the **immutable snapshot that actually executed** every successful attempt, not the requested model;
2. the selected snapshot must be confirmed to remain **available throughout the entire pilot**;
3. the **processing region** must be selected and accepted;
4. **retention arrangements** and any ZDR / modified-abuse-monitoring eligibility must be confirmed;
5. the **workload-identity host, principal, issuer, audience and token source** must be supplied;
6. the **exact boundary environment keys** must be derived by provider-free testing and **separately owner-ratified** (§2.4).

**Reopen trigger.** India-only processing is **not** currently an owner
requirement. **If India-only processing becomes mandatory, the provider-route
decision reopens**, because the OpenAI India option is not established as
providing India-local processing.

**Evidence references to be checked** (unfetched, unverified):
`developers.openai.com/api/docs/models/gpt-4.1`;
`developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create/`;
`developers.openai.com/api/docs/guides/workload-identity-federation`;
`developers.openai.com/api/docs/guides/your-data`.

#### CONDITIONAL OWNER SELECTION — BENCHMARK AND TASK CLASS (D2–D3)

Selected by the owner in the post-revision-11 D2–D3 round. **D2 and D3 remain
incomplete**: the identities, custody, governance text and the calibration
formula below are still open.

| Item | Value | Status |
|---|---|---|
| Task | BIG-Bench Hard `logical_deduction_seven_objects` | owner-selected |
| Upstream commit | `9ee07bd481feebf959a6b59d61ea57bdcf30964d` | `[V]` reproduced by `git fetch --depth 1` + `git cat-file` |
| Licence | MIT | `[V]` upstream repository |
| Benchmark identity | `bbh.logical_deduction_seven_objects.wrapped.v1@9ee07bd481feebf959a6b59d61ea57bdcf30964d` | owner-selected |
| File SHA-256 | `2896c7e3482eea318dd37bcc370d24ec3cc91e8374c1784287b5dbd38a529e33` | `[V]` |
| Git blob SHA-1 | `2bc3766619b76d9f4b379782b8c25d3e022025e8` | `[V]` |
| Population | 250 examples; 250 targets; 250 unique inputs; 250 unique (input, target) pairs; targets span exactly `(A)`–`(G)` | `[V]` independently counted |
| Sample size | 50 | owner-selected, **operational first-pilot size, not power-justified** |
| Score resolution | one case moves a 50-case mean by **0.02**; means are quantised to multiples of 0.02 | `[V]` arithmetic |
| Sampling algorithm | `bbh_hash_rank_select.v1` — see below | owner-ratified |
| Seed | hex `2896c7e3482eea31` = decimal `2924744787006253617` (first 16 hex characters of the file SHA-256 as an unsigned 64-bit big-endian integer) | owner-ratified, conversion `[V]` |
| Selected indexes | 50 unique indexes in `[0, 249]`, derived, published ascending | mechanically derived |
| Selected-index-list digest | `c521cdd75dc3b8c9e589835ade4b780ef26ba955d4077f5c7ad74e803be60682` | mechanically derived |
| Execution order | ascending derived case-digest order | owner-selected; matches the merged runner `[V]` |
| Scoring | **`bbh-ld7.v3`**, binary — §2.11; supersedes v2 (revision 15), which superseded v1 | owner-ratified |
| Evaluator kind | `PROGRAMMATIC` | **conditional**: final only after the implementation, complete procedure text, evaluator identity and version, and `scoring_instruction_digest` are inspected and fixed |
| Expected answers | derived from the pinned upstream `target` fields; available only to the scorer | owner-selected |
| External threshold | none presently established for this wrapped task and sample | owner-selected |
| Repetition branch | 1 preregistered `CALIBRATION` run, then 3 confirmatory | owner-selected |

**`bbh_hash_rank_select.v1`.** For each upstream index `i` in `0…249` compute
`k(i) = SHA-256(seed_ascii ‖ ":" ‖ index_ascii)` as lowercase hex, where both
components are decimal ASCII with no sign, padding or leading zeros and `‖` is
byte concatenation around a single ASCII colon. Sort all 250 pairs ascending by
`(k(i), i)`; select the first 50; publish them in ascending numerical order.
The list is digested with `ugence_jcs.canonical_sha256_hex`. **Instantiation
detail `[V]`:** the Action-Profile canonicaliser rejects bare JSON numbers
(`BareNumberError`), so the digest is taken over the **decimal-string form** of
the index list — the same shape the repository's own `payload()`/`digest_of`
produces. Index order is the position in the `examples` array of the pinned
file, zero-based, unfiltered. Ties break on ascending `i`. The derivation needs
no benchmark content: it consumes only the seed and the index range.

**Scoring is `bbh-ld7.v3`** (revision 15), whose complete normative preimage,
byte length and digest are recorded in §2.11. It supersedes the v1 summary
that stood here.

**Open under D2–D3:** benchmark author and distinct approver; benchmark-custody
URI with readers and writers; evaluator identity, version and actual
implementation; separation declaration; `profile.json` and `task_class.json`;
consequence class and any required evidence-admission reference; final
population and representativeness governance text; and the calibration
statistic and threshold formula, which **blocks calibration execution**.

#### CONDITIONAL OWNER SELECTION — NOT YET FINAL

| Ballot | Selection | Condition |
|---|---|---|
| D2 | evaluator kind `PROGRAMMATIC` | the benchmark-side condition is met (revision 12): a single option letter admits deterministic comparison. The label still proves nothing `[V]` (`EvaluatorKind` is declared; no contract verifies determinism), so final selection awaits inspection of the scorer implementation, the complete procedure text, the evaluator identity and version, and the fixing of `scoring_instruction_digest` |
| D4 | **branch resolved (revision 12):** 1 `CALIBRATION` run + 3 confirmatory, no external threshold being established | remains blocked until the calibration statistic and threshold formula are preregistered (§D4) |
| D1 | the exact environment allowlist keys | the policy is ratified; the key set is derived by provider-free testing and returns for separate ratification |

#### WITHDRAWN ASSISTANT PROPOSALS

| Proposal | Status |
|---|---|
| literal allowlist `PATH`, `PYTHONPATH`, `LANG`, `LC_ALL` | **withdrawn** in revision 10; not replaced by another list. The allowlist policy above governs instead |
| evidence retention of at least 24 months | **withdrawn** in revision 10; the period is an open owner choice pending review |
| canary retention of 30 days | **withdrawn** as a fixed value; canaries keep a *separate* retention policy whose period is open |
| registry writer identity `workflow_fit_commitment_registry.writer` and addressing `commitments/<identifier>/<index_digest>` | remain **assistant proposals**; the owner ratified the registry's adoption, separation, append semantics, consumption point and failure behaviour, not these names |

#### OPEN OWNER FACTS

| Ballot | Facts still required |
|---|---|
| D1 — conditionally selected (not verified, not final) | provider route, model candidate, API surface and credential architecture — see **Conditional owner selection — provider route** above |
| D1 — unresolved facts and confirmations | executed-identity confirmation (§2.5); snapshot availability for the whole pilot; deployment region; retention-policy reference and version with ZDR/MAM eligibility; workload-identity host, principal, issuer, audience and token source; and the exact environment keys after provider-free derivation and separate ratification |
| D2 | benchmark author; approver, distinct; benchmark-custody URI with readers and writers; evaluator identity, version and actual implementation; complete scoring procedure text; separation declaration reference. *(Benchmark id, pinned bytes, case selection and expected answers are settled or mechanically derived — see the D2–D3 selection above.)* |
| D3 | `profile.json`; `task_class.json`; consequence class; evidence-admission reference where the class is `MATERIAL` or `SEVERE` with threshold-based sufficiency `[V]`; final population and representativeness governance text; and the **calibration statistic and threshold-mapping formula**, whose absence **blocks calibration execution** (revision 12) |
| D4 | pricing source and version; currency; spending ceiling |
| D5 | preregistration medium; registry endpoint; both custody locations; registry and custody writer identities; ACL principals; key custodian; evidence retention period; canary retention period; deletion rules |

Temperature 0 **removes a major sampling control but does not establish
determinism**; a provider may still vary across attempts.

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
stage code; (iv) **eleven** owner-ratified refusal codes — the **seven ratified
in revision 10** (`PROVIDER_IDENTITY_UNVERIFIED`, `RETENTION_WRITE_FAILED`,
`RETENTION_VERIFY_FAILED`, `EVALUATION_FAILED`, `COMMITMENT_ALREADY_SPENT`,
`COMMITMENT_REGISTRY_UNAVAILABLE`, `WORKFLOW_BUDGET_EXHAUSTED`; the three stage
codes came from revision 4) plus the **four ratified in revision 13** for the
calibration architecture (`RUN_ROLE_INVALID`, `ROLE_ARTIFACT_INCONSISTENT`,
`CALIBRATION_PROVENANCE_INVALID`, `CALIBRATION_STATISTIC_UNAVAILABLE`, §2.11).
**The enum has not changed**: `errors.py` has **33** members today and contains
none of the eleven `[V]`; a future commissioned vocabulary would have **44**.
None of the eleven exists until implementation is separately commissioned.
`RETENTION_FAILED` stays withdrawn. (v) only
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
startup, refusing a commitment already consumed (§2.2), with the registry's
append-only consumption and outcome entries. One preregistered run per repetition. The CI
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
| T17 | a halted repetition cannot be re-run under its own manifest and `index_digest`: `run` refuses with `COMMITMENT_ALREADY_SPENT` against the registry's consumption entry, and the halted evidence survives the replacement repetition intact |
| T18 | the exchange-writer health check runs inside the boundary and its scope reaches the runner in the refusal; the runner holds no reference to that writer or its credential, and no import path exposes it |
| T19 | the canary carries its own identifier, produces no capture record, does not change `llm_calls`, and never renders as a provider attempt |
| T20 | a pre-run custody failure is never health-checked and never classified into a method: no runner, no lifecycle record, no `INCONCLUSIVE` |
| T21 | after a repetition-wide halt, unstarted methods have no `MethodRun`, no execution record and no lifecycle state; `run_status.json` carries the halt and its fatal refusal; verification accepts the bundle |
| T22 | after a repetition-wide halt no comparison request or result is created or rendered, no winner and no success summary appear, and each earlier method's evidence still verifies individually |
| T23 | the report distinguishes an incomplete repetition from a method-local incompleteness |
| T24 | a `RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED` or `EVALUATION_FAILED` reaches the lifecycle record unchanged — never collapsed to `WORKFLOW_FAILED` or `CAPTURE_INCOMPLETE` — and a reason string that is not a string, lacks its code prefix, or carries anything beyond operation, method identity and exception class is refused |
| T25 | consumption is a single conditional append immediately before boundary startup: two concurrent `run` invocations resolve with exactly one proceeding; an unavailable registry refuses with `COMMITMENT_REGISTRY_UNAVAILABLE`, starting no boundary and writing no lifecycle record; a commitment marked spent before any provider call stays spent across a crash; and a missing outcome entry never reopens one |
| T26 | only the named registry writer identity can append a consumption entry, and no principal can unmark one |
| T27 | the canary lands in the probed store under the reserved prefix, is absent from every evidence read and from case-digest keying, and falls under the canary retention rule rather than the evidence retention period |
| T28 | **PROPOSED — NOT RATIFIED. No provider:** a deterministic fake LLM client drives all seven workflows across the case set, records each one's actual call count, inspects **all** `WorkflowResult.steps`, and verifies that the selected shared cap produces **no** `"(budget exhausted)"` sentinel for any workflow |
| T29 | a run whose `WorkflowResult.steps` contain the exhaustion sentinel does not enter a comparison and becomes `INCONCLUSIVE`; the check inspects all steps before `ExecutionOutcome` is returned, and fails closed if the sentinel string is absent from the runtime |
| T30 | a `CALIBRATION` repetition carries its own commitment and appears in no confirmatory comparison, coverage report or success summary |
| T31 | a replacement after a halt carries a fresh nonce or new ordinal, and the halted `manifest_id` is neither reused nor overwritten |
| T32 | a task class declaring `TOTAL_TOKENS` against records missing usage yields `DIMENSION_UNAVAILABLE` rather than a zero-filled or reduced-dimension comparison |

## 5. Explicitly excluded

Provider calls before ratification; any credential in the repository or in
any artifact; cross-run aggregation; advisor changes from pilot results;
readiness composites; **any search over, optimisation of, or separate
attribution to agent-level reasoning strategies within a workflow (§2.10)**;
production eligibility, approval or configuration mutation; TEV integration; any quality unit or aggregation other than §2.6;
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

### Revision 5 (assistant selections on the three choices revision 4 surfaced, 2026-09-03)

Revision 4 named three policy choices and deliberately left them unruled. The
owner asked for them to be closed but supplied no values; the assistant
selected each to follow the fail-closed posture the revision-4 rulings
established. **They were mislabelled "owner ruling" until revision 9. All
three are PROPOSED — NOT RATIFIED.**

| # | Choice | Assistant selection — PROPOSED, NOT RATIFIED |
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
review introduces. It remains **open**: revision 7 proposed values for it but
did not close or ratify it.

### Revision 7 (assistant proposals for the three values revision 6 left open, 2026-09-03)

The owner asked for the values but supplied none; the assistant proposed each.
**They were recorded as ratified until revision 9 and are PROPOSED — NOT
RATIFIED.**

| # | Value | Assistant proposal — NOT RATIFIED |
|---|---|---|
| 1 | spent-commitment registry | append-only, co-located with the preregistration medium, keyed by (identifier, `index_digest`), and **not** either custody store (§2.2) |
| 2 | marking authority | one named registry writer identity, distinct from both custody writers, the boundary and the evaluator; `run` acts as it and nothing else may append a consumption entry |
| 3 | check-and-mark | a single conditional append over the medium's atomic primitive — never read-then-write — so concurrent invocations resolve with exactly one proceeding |
| 4 | consumption point | immediately before boundary startup, after the §2.1 identifier and digest match, so a zero-call halt still consumes |
| 5 | registry unavailable | fail closed: `COMMITMENT_REGISTRY_UNAVAILABLE`, no boundary, no lifecycle record — the pre-run custody posture |
| 6 | crash after marking | consumption is terminal; a run appends a closing outcome entry, but a missing outcome entry never reopens a commitment, which is what stops a crash from becoming a re-roll |
| 7 | custody health-check timeout (D4) | **5 000 ms**, declared separately from the provider-call timeout and never conflated with it |
| 8 | canary retention (D5) | canaries go to the **store they probe**, under a reserved prefix — a canary written elsewhere proves nothing about the failing store — excluded from evidence reads and from case-digest keying, under their own short retention and deletion rule rather than the evidence period |

`COMMITMENT_ALREADY_SPENT` and `COMMITMENT_REGISTRY_UNAVAILABLE` are
**proposed** vocabulary additions (§4). Revision 7 neither lifted the §2.2
`[G]` nor closed the spent-commitment decision; T17 and T25–T27 are
obligations for a proposed mechanism.

### Revision 8 (deployment facts and end-to-end audit, 2026-09-03)

Two of the three facts revision 7 deferred are **proposed by the assistant, not
ratified** (relabelled revision 9): the registry writer
identity `workflow_fit_commitment_registry.writer` with the addressing
`commitments/<identifier>/<index_digest>` (§2.2), and a **30-day** canary
retention (§2.8). The third — the registry's concrete endpoint — is
deliberately still open: it names infrastructure outside this repository, and
inventing a URI here would be a fabricated `[V]`. Nothing depends on it that a
conforming registry double cannot stand in for.

The whole note was then audited against the merged 4A/4B code. One citation
was **wrong and is corrected**: §2.4 cited "row A16d" as `[V]` for transport
equivalence. **No such row exists in the 4A spec** — its acceptance table runs
A16, A16a, A16b, A17 — and the identifier lives only in a test,
`test_a16d_transport_equivalence`, and in the message of commit `93c6b9f1f`.
The claim now cites the 4A spec's §4 transport prose, the merged `transport`
parameter and that test. The underlying capability is real; only the reference
was false. That the 4A acceptance table lacks a row its own test claims is a
gap **in 4A**, outside this note's scope to fix.

Every other `[V]` in the note re-verified against the merged tree: the §1
inventory (`pilot_executor.py` `max_llm_calls`, `recompute_telemetry`,
`entry.py --provider-factory`, `loaders.py` `CREDENTIAL_KEYS`, the 4B
digest-only bundle test, rows A14/A14a/A16a/A30, `QUALITY_UNIT` and `_mean`);
the §2.1 prepared layout and index self-exclusion; §2.2's history-free `run`;
§2.3's `FORBIDDEN_RENDERINGS`, prefix-derived refusal, code-only
`refusal_codes` and the direct `PROPOSED` → `INCONCLUSIVE` transition;
§2.4's unconditional `BoundaryProcess`; and §2.8's frame set, exact-method
equality in `_load_status` and `verify`, comparison over complete runs, and
`success_summary` gating.

### Revision 9 (authority audit and verified technical corrections, 2026-09-03)

**Authority audit.** Revisions 5, 7 and 8 recorded assistant selections under
owner labels. The owner's instructions for those revisions named the
*questions* and asked for values; they supplied none. Revision 9 strips the
false attribution. "Subject to owner correction" is not ratification.

**Owner-ratified — the revision-4 instructions, and only these:** the exact
`workflow_fit_prepared_index.v1` layout (§2.1); operation-based failure
classification (§2.3); `RETENTION_WRITE_FAILED`, `RETENTION_VERIFY_FAILED`,
`EVALUATION_FAILED`; `Exception` caught at each port call site and never
`BaseException` (§2.3); the boundary-custody behaviour with its direct
`PROPOSED` → `INCONCLUSIVE` transition (§2.3); the partial-run policy (§2.8);
credential option A recommended with no invented secret-transfer protocol and
option C labelled non-isolating (§2.4); and refusal of any provider that
cannot return an immutable deployment identity (§2.5).

**Relabelled PROPOSED — NOT RATIFIED:** diagnostic retention in
`run_status.json` `reasons` (§2.3); the health-check discriminator (§2.8); the
canary's placement in the probed store (§2.8); the no-re-run rule for a halted
commitment (§2.2); the whole spent-commitment registry proposal, its
addressing and writer identity (§2.2, D5); the 5 000 ms health-check timeout
(§2.8, D4); and the 30-day canary retention (§2.8, D5). The revision-6
corrections were owner-transmitted and are additionally forced by the merged
code, so they stand as corrections rather than selections.

**Verified technical corrections.** The call ceiling `cases x methods x 1` is
withdrawn: the merged executor supplies **one shared** `max_llm_calls` to every
workflow and budget exhaustion is **silent**, appending a `"(budget
exhausted)"` step and returning normally `[V]` (§2.9). A `CaptureRecord`
carries digests, not stage responses, and `HarnessWorkflowExecutor` discards
`WorkflowResult.steps`, so the condition is invisible to the boundary — a
proposed experiment-side check inspects all steps before returning
`ExecutionOutcome` (§2.9). `WORKFLOW_BUDGET_EXHAUSTED` is proposed, taking the
proposed count from six to seven; neither count is ratified (§4).
`TOTAL_TOKENS` is conditional because the engine refuses
`DIMENSION_UNAVAILABLE` with no dimension fallback `[V]` (D3). Temperature 0
removes a major sampling control but does **not** establish determinism (D4).
Calibration and confirmatory repetitions are separated, each with its own
commitment (D4). The `manifest_id` gains a role segment and a pre-execution
nonce (D4). The workload-identity and encryption claims are reduced to their
bounded forms (§2.4, D5). Obligations T28–T32 added.

**Residual corrections applied within revision 9 (second pass).** The first
pass of this revision left contradictions the audit itself had identified.
Corrected here: the claim that revision 7 *closed* the spent-commitment
decision — it proposed values and closed nothing, and the §2.2 `[G]` stands;
the claim that T17 and T25–T27 test a *ratified* mechanism — they are
obligations for a proposed one; D4's folding of the health-check
discriminator, the 5 000 ms timeout, the halted-commitment prohibition, the
replacement identity and the registry mechanics into the owner-ratified
partial-run policy — only the revision-4 policy itself is ratified by that
item; the enum size, stated as 34 from a `grep` that over-counted and now
**33** by enumerating the class body, making six additions **39** and seven
**40**; the cap rationale, which claimed every value below 8 truncates when
the largest present bounded path is **7**, so 7 suffices today and 8 is one
call of headroom; the unlabelled T28; and the two-custody-writer design, an
assistant design the revision-4 instruction assumed rather than ratified,
and the pre-run block and post-attestation discard inside it are
**PROPOSED — NOT RATIFIED** on the same authority, only the in-boundary
exchange-custody path and its direct `PROPOSED` → `INCONCLUSIVE` transition
being owner-ratified. A consolidated §3.1 now lists every candidate value
as PROPOSED — NOT RATIFIED.

Ballot items remain five and remain `[R]`; D1–D5 still need their provider,
benchmark, threshold, budget, identity and custody values, and D5 still needs
the registry endpoint. As of revision 9, every candidate value in this note
was an assistant proposal except the revision-4 rulings listed above; the
owner's post-revision-9 round changed that, and revision 10 records it. No
revision changed code, contract or CI gate, and none authorises a provider
call.

### Revision 10 (owner policy selections from the post-revision-9 D1–D5 round, 2026-09-03)

**Source of authority.** An explicit owner policy-selection instruction issued
**after** revision 9, in the D1–D5 decision round. These are new decisions of
that round. They are **not** retroactive: revisions 4–9 stand exactly as
recorded, and revision 9's authority audit remains historical fact. What
revision 9 correctly called assistant proposals were assistant proposals when
it said so; the owner has since selected many of them.

**Newly ratified policy categories** — enumerated in §3.1 and reflected in
§2.2, §2.3, §2.8, §2.9 and §4: D1 decoding parameters, seed handling,
credential option A with the bounded credential claim, immutable-identity
verification on every attempt and the allowlist **derivation policy**; D2
append-only versioning, scorer-only answer access, distinct author and
approver, the two-writer custody architecture, the pre-run custody block and
the post-attestation discard; D3 `LLM_CALLS` as universally required, the
no-fallback `DIMENSION_UNAVAILABLE` posture, `score.unit` with arithmetic
mean, external threshold sourcing with a calibration fallback, and the
representativeness minimum; D4 the shared per-case cap 8 with its stated
limits, the bounded-path retest obligation, ceilings as accounting figures,
zero retries, sequential execution, the 60-second provider timeout, the
calibration separation, the manifest identity and halt-replacement rule, the
health-check discriminator with its 5 000 ms timeout and writer-owning
performer, and the stop conditions; D5 external append-only preregistration,
the receipt binding, the no-reuse rule, adoption of the spent-commitment
registry with its separation, append semantics, consumption point and failure
behaviour, canary placement and separate retention policy, and bounded
customer-managed encryption; plus the seven refusal codes and the shared
sentinel constant.

**Conditional selections, not final:** evaluator kind `PROGRAMMATIC` pending a
benchmark that supports objective deterministic scoring — the label alone
proves nothing; `TOTAL_TOKENS` admission pending the provider-usage fact; the
repetition branch pending whether a defensible external threshold basis
exists; and the exact allowlist keys pending provider-free derivation and a
separate ratification.

**Withdrawn assistant proposals:** the literal `PATH`, `PYTHONPATH`, `LANG`,
`LC_ALL` allowlist, replaced by no other list; the 24-month evidence-retention
period; and the 30-day canary retention figure. The registry writer-identity
name and addressing remain assistant proposals rather than ratified values.

**Remaining owner-supplied facts:** every entry in §3.1's open-facts table —
provider, benchmark, people, task class and consequence class, threshold,
pricing, custody and registry locations, identities, ACL principals, key
custodian, and the evidence and canary retention periods, the last pending
legal, privacy, customer-contract and research-reproducibility review.

**Policy ratification is not ballot ratification.** D1, D2, D3, D4 and D5 are
each **partially decided and none is fully ratified**. **No implementation was
commissioned by this revision**: the enum is unchanged at 33 members `[V]`, no
code, test, contract or CI file was touched, no credential was accessed and no
provider was called.

### Revision 11 (conditional provider-route selection, 2026-09-03)

**Source of authority.** An owner decision taken **after** revision 10, in the
D1 provider-selection round. It is recorded here rather than inside the
revision-10 record, which describes a different and earlier round and is left
untouched.

**What the owner selected.** OpenAI API direct as the **conditional default**
provider route, with `gpt-4.1-2025-04-14` on Chat Completions, boundary-side
OpenAI workload-identity federation mapped to a Platform service account, and
`LLM_CALLS` as the operative resource configuration. Recorded in §3.1 under
**Conditional owner selection — provider route (D1)**.

**What it is not.** It is **not** completed D1 ratification, **not** a verified
provider fact, and **not** compliance with §2.5. The immutable-executed-identity
refusal stands unchanged; **the route is disqualified if that confirmation
fails**. Six conditions remain open, and India-only processing is a named
reopen trigger.

**Evidence status.** Official OpenAI documentation was unreachable from this
environment (`developers.openai.com`, `platform.openai.com` blocked by egress
policy), so every provider-side claim is **owner-supplied or externally
transmitted**, never `[V]`. The official URLs appear as references to be
checked, not as verification.

**`TOTAL_TOKENS` is now settled rather than pending.** It is **not admitted**,
on the ground that complete provider-usage reporting for every potentially
charged attempt — failures and timeouts included — has not been established;
this is deliberately weaker than a claim that the provider never returns usage
in those circumstances. The consequence is recorded in D3 and §3.1: the pilot
compares resource use **by call count**, and its results must not be
represented as a comparison of token consumption or token cost.

**Unchanged by this revision.** §2.4 and §2.5 are not modified; the new
subsection cross-references them. No implementation is commissioned, the enum
stays at 33 members `[V]`, and D1–D5 remain incomplete.

### Revision 12 (benchmark, task class and unit of evaluation, 2026-09-03)

**Source of authority.** An owner decision taken **after** revision 11, in the
D2–D3 benchmark and evaluator round. Earlier revision records are unchanged;
none of these decisions existed before this round.

**Unit of evaluation.** §2.10 records the ruling that Workflow-Fit evaluates the
declared primary reasoning strategy of a **complete** agentic workflow, never a
search over agent-level strategy combinations, with roles, prompts, local
reasoning behaviour and orchestration fixed as configuration. The separate
`[V]` finding — that the harness represents stages and prompt-defined roles
rather than independently governed agents, with no per-role binding or
attribution — is recorded alongside it, and §5 gains the matching exclusion.

**Benchmark and sampling.** BBH `logical_deduction_seven_objects` at commit
`9ee07bd4…`, MIT, with the file SHA-256, blob SHA-1 and a **250 / 250 / 250 /
250** count independently reproduced through Git rather than accepted as
transmitted. Sampling is `bbh_hash_rank_select.v1` under a seed **derived from
the verified file digest** rather than chosen — hex `2896c7e3482eea31`, decimal
`2924744787006253617`, conversion checked — yielding 50 unique indexes in
`[0, 249]` whose ascending list digests to
`c521cdd75dc3b8c9e589835ade4b780ef26ba955d4077f5c7ad74e803be60682`. The
derivation consumed only the seed and the index range: no benchmark input or
target was inspected, printed or copied into this repository. One
instantiation detail is recorded because it is not optional `[V]`: bare JSON
numbers are rejected by the canonicaliser, so the digest is over the
decimal-string form of the list.

**Scoring and evaluator.** `bbh-ld7.v1` binary scoring is ratified in full.
`PROGRAMMATIC` stays **conditional**: the benchmark-side condition is met, but
the label proves nothing and final selection awaits the implementation, the
complete procedure text, the evaluator identity and version, and a fixed
`scoring_instruction_digest`.

**Calibration.** Every calibration statement is corrected so it cannot permit
post-hoc threshold selection: the statistic, mapping formula, rounding,
boundary-equality behaviour, missing and inconclusive-method treatment,
threshold scope and any required admission reference must be preregistered
**before** the run, which may then only **instantiate** the rule. **The formula
is open and blocks calibration execution.**

**Limitations recorded as selected**, in §3.1: the 0.02 resolution; claims
confined to the sampled wrapped configuration; no generalisation to BBH,
logical reasoning or production; non-comparability with published BBH scores;
contamination unestablished, with the canary expressing intent rather than
compliance; digests giving integrity but not confidentiality, brute-forceable
in seven trials here; call-count rather than token comparison; and the 2 800 /
11 200 accounting ceilings with only the shared per-case cap enforced.

### Revision 13 (calibration and confirmatory run architecture, 2026-09-03)

**Source of authority.** An owner decision taken **after** revision 12, in the
calibration-schema round. Earlier revision records stand unchanged.

**Ratified.** The compatibility model and manifest architecture of §2.11 —
schema-version split plus discriminated union, with v1 manifests confined to
historical mechanism validation and never defaulting to `CONFIRMATORY`;
`PilotRunRole`; `CalibrationManifest` and its descriptive
`CalibrationTaskBinding`; the reduced `CalibrationResult` with its verification
obligations; `CalibrationProvenance` inside the confirmatory manifest digest;
the role behaviour matrix, including forbidden comparison, forbidden
`RESULT_ASSESSED`/`EVALUATED`, absent coverage and impossible success summary
under `CALIBRATION`; baseline-only accounting of 400 / 8 400 / **8 800**;
`workflow_fit_prepared_index.calibration.v1`; `calfloor.linear_chain.v1` with
its self-reference non-reporting constraint; `bbh-ld7.v2` superseding v1, its
preimage inserted verbatim at 1 703 bytes with digest `84051a08…43b870e9`
recomputed from the inserted text; and four additional refusal codes.

**Recorded as a gap, not as working `[G]`.** The merged lifecycle model can rest
at `UNDER_TEST` but cannot distinguish a completed calibration from a run that
merely stopped there. `UNDER_TEST` is **not** redefined as globally terminal;
tying the endpoint to a valid `CalibrationResult` is a **required Phase 4A
amendment** that is not yet commissioned.

**Attribution corrected.** The original seven refusal codes were **ratified in
revision 10** and are no longer described as unratified. With revision 13's
four, eleven codes are ratified in policy; the live enum remains **33** `[V]`
and a future commissioned vocabulary would hold **44**.

**Layout ruling preserved.** The revision-4 confirmatory identifier and its
nine-path layout are unchanged. Calibration shares the path set under a
distinct identifier because `pilot_manifest.json` holds a different contract
type — no rename, no reinterpretation, no contradiction.

**Vocabulary gap.** The governed token set lacks an accurate token for
relational logical deduction or constraint satisfaction;
`structural_characteristics` stays `[]` rather than carrying an inaccurate
token. Whether `domain_ref` and `intended_outcome_ref` must come from a
registered vocabulary remains open.

**Status.** Revision 13 records architecture and policy only. It does **not**
complete D1–D5 and does **not** commission implementation.

### Revision 14 (calibration binding resolution, 2026-09-03)

**Source of authority.** An owner ruling taken after the implementation-
readiness review, which found one contract contradiction in revision 13.
Revision 13's record stands unchanged; **only its statement that calibration
carries no plan and no task class is superseded**, because the mandatory
execution-record and observation contracts make that shape impossible `[V]`.

**Ratified.** Calibration retains every governed plan, binding, role and
task-class identity that `ReasoningMethodExecutionRecord`, `PilotObservation`,
attestation, quality evaluation and lineage verification require — the exact
minimum shape is enumerated in §2.11 from the constructors themselves. Its
`GovernedThreshold` uses **`benchmark_ref`, never `literal_value`**, so no
numeric calibration threshold exists and engine `tau` is `None` `[V]`.
Calibration keeps its explicit committed `CALIBRATION` run role, and the runner
must not construct or execute a comparison request for it — two independent
protections. Calibration remains **baseline-only** with `linear_chain` as the
sole assigned method. Confirmatory execution still requires a literal
instantiated from a valid `CalibrationResult` and bound through
`CalibrationProvenance`.

**Withdrawn.** The separate `calibration_manifest.v1` contract and
`CalibrationTaskBinding`: calibration uses `…manifest.v2` under the calibration
role instead. The manifest-version split and the explicit run roles are
preserved; the discriminated union is now by committed role within v2, and
`…manifest.v1` remains historical mechanism validation, never 4C-eligible.

**Rejected.** Optional task-class, binding or role fields in shared contracts;
removing calibration attestation; a placeholder numeric threshold; report
suppression alone.

**Preserved unchanged.** Reduced `CalibrationResult`; `CalibrationProvenance`;
baseline-only accounting of 400 and combined 8 800; calibration artifact
restrictions; the lifecycle endpoint qualification and its `[G]`;
`workflow_fit_prepared_index.calibration.v1`; `calfloor.linear_chain.v1` with
its self-reference constraint; the benchmark, sampling and `bbh-ld7.v2`
decisions; and the eleven-code prospective accounting of **33 → 44**.

**Status.** This resolves the **sole** contract contradiction the
implementation-readiness review found, and **provider-free implementation is
architecturally unblocked after revision 14**. The unresolved provider,
credential, pricing, custody, registry and retention facts block **genuine
execution**, not deterministic implementation with fixtures and test doubles.
**D1–D5 remain incomplete for a genuine pilot, and Phase 4C implementation is
not commissioned by this documentation revision.**

### Revision 15 (scorer erratum: `bbh-ld7.v3` supersedes v2, 2026-09-03)

**Source of authority.** An owner ruling after slice-1 implementation surfaced
a contradiction inside the governed procedure text. The revision-13 and
revision-14 records stand unchanged.

**The erratum.** `bbh-ld7.v2` described `'ANSWER:'` as "the four characters"
when the quoted prefix has **seven**. The literal governed, so no
implementation was misled and no acceptance outcome depended on the miscount —
but a false statement inside a digest-pinned normative procedure is not
allowed to stand.

**The correction.** `bbh-ld7.v3` is v2 with **exactly two semantic edits**: the
procedure identifier, and "four" → "seven". No other wording, whitespace,
punctuation or behaviour changed. **The scoring algorithm and all acceptance
outcomes are unchanged**, so no test expectation moves.

**Authority values, recomputed from the inserted text (§2.11):** UTF-8 length
**1 704**, digest
**`9cc587889c5b43dbc1f6ae796840d6af90cfe95c0e6e49cbe245f2ca5dfc1813`**. The v2
pair — 1 703 bytes, `84051a08…43b870e9` — is retained as **historical evidence
only** and must never pin a runtime constant again.

**Consequence for implementation.** The slice-1 scorer's shared procedure
constant, its import-time length and digest guards, and the tests that name the
procedure normatively move to v3 in the stacked implementation branch. Behaviour
does not change.

**Still incomplete.** **D2 and D3 are not complete**, and neither is any other
ballot item. Open: benchmark author and distinct approver; custody URI, readers
and writers; evaluator identity, version and implementation; separation
declaration; `profile.json` and `task_class.json`; consequence class and any
admission reference; final population and representativeness text; the
calibration statistic and formula; and all unresolved D1, D4 and D5 facts. **No
implementation was commissioned**, no benchmark content entered this
repository, no credential was accessed and no provider was called.

### Revision 16 (slice-2 corrections: calibration composition and canonical decimals, 2026-09-03)

**Source of authority.** An independent adversarial review of implementation
slice 2 (PR #1580) found two findings, F1 and F2, that made a manifest shape
the contract accepted fail the package's own validator, or left a digest-bound
numeric value with more than one accepted spelling. Both are resolved here by
owner ruling; the corresponding code and tests land on the slice-2 branch, not
on this documentation branch.

**F1 — calibration composition, ratified.** A `CALIBRATION` manifest's plan
declares `SamplingKind.PREREGISTERED`. Under a v2 `CALIBRATION` manifest the
preregistered assigned-method set is **exactly `{plan.baseline}`**; the single
assignment carries only `GOVERNED_BASELINE`; challengers and recommendations
remain empty. `validate_manifest` is **run-role-aware**: it no longer applies
the confirmatory "every admissible method is assigned" composition rule to a
calibration manifest. Under `CONFIRMATORY` the existing preregistered
completeness rule is **unchanged**.

**Why `PREREGISTERED` and not risk-based or randomized sampling.** The
baseline-only calibration composition was fixed before execution — it is not
a draw from a larger admissible set, and no sampling rule chose it. Declaring
`RISK_BASED` or `RANDOMIZED` would assert a selection process that never
occurred. `PREREGISTERED` is the truthful value for a composition committed in
advance, and it is truthful for calibration in exactly the sense it is
truthful for the exhaustive confirmatory composition — the two preregister
different sets, not different kinds of commitment.

**Why confirmatory completeness is untouched.** `CONFIRMATORY` still runs the
full admissible catalog under the advisor-qualified/challenger split; nothing
about calibration's narrower, fixed composition bears on that rule, and
narrowing it for calibration must not narrow it for confirmation too.

**F2 — canonical decimals, ratified.** Every new digest-bound Phase 4C
calibration value is a **code-point canonical decimal string**. The canonical
form: a string; no surrounding whitespace; no leading `+`; no exponent
notation; `-` only for a nonzero negative value; no leading integer zeros
except the integer zero itself; no decimal point for an integer; no trailing
fractional zeros; every zero, including a negative-zero input, represented
only as `"0"`; and it parses to a finite `Decimal`. An equivalent but
non-canonical spelling — `"0.620"`, `"+0.62"`, `"6.2E-1"`, `"00.62"`,
`"0.0"`, `"-0"` — is **refused, never silently normalised**: normalising a
digest-bound field would change what a caller committed to without their
digest changing to match.

Worked examples: `"0"`, `"1"`, `"0.62"` and `"-0.25"` (where the field
otherwise permits a negative value) are valid; `"0.620"`, `"+0.62"`,
`"6.2E-1"` and `"-0"` are refused.

**Scope of F2.** `CalibrationResult.statistic_value`, `CalibrationProvenance
.instantiated_literal`, and a v2 `CONFIRMATORY` manifest's threshold
`literal_value` are canonical under this rule. **Slice-3 verification compares
these canonical strings by exact code-point equality** — including checking
that the canonical string derived from the reachable `QualityResult.value`
equals the calibration statistic. This rule is **Phase 4C's own**: it is not
imposed retroactively on `MetricClaim.value`, `GovernedThreshold.literal_value`
in any other governance contract, or on any historical v1 threshold literal.
Existing v1 threshold behaviour and every v1 digest, including the anchor
`de6f18598c1fe23d5b7940fb5fb012b07f8ffca462956a9ddf673fddde5b39c9`, are
unchanged.

**F3 and F4 remain slice-3 obligations, not resolved here.** F3: nothing in
the package's execution path calls `require_phase_4c_eligible()` — a v1
manifest is refused *by that method*, not yet by any run entry point. F4: the
v1 digest payload excludes `run_role`/`calibration_provenance`, so a v1 object
whose role field was set by circumventing the frozen dataclass would keep a
digest that still verifies; no public construction path produces such an
object today, but a slice-3 verifier must re-run the manifest's role
validation rather than trust a recomputed v1 digest alone. Both are recorded
as acceptance obligations on the slice-2 branch; neither is implemented by
this revision or by the slice-2 correction it authorises.

**Status.** This revision completes slice-2's contract semantics — the
constructible calibration and confirmatory shapes now also pass the package's
own validator, and every new digest-bound numeric field has exactly one
accepted spelling. **It does not commission slice 3, enforce F3 or F4 at
runtime, or authorise a genuine pilot.** D1–D5 remain incomplete, no
credential was accessed, no provider was called, and no benchmark content
entered this repository.

### Revision 17 (owner rulings: distinct digest meanings, custody-reference semantics, slice-3A/3B split, 2026-09-03)

**Source of authority.** The slice-3 preflight (independent of any implementation)
proposed completing a governed `CalibrationResult` by defining `index_digest`
identically to `sample_index_digest`, and by carrying `verdict_custody_ref` as a
fixed placeholder string. Both proposals are **rejected by owner ruling** below,
and the previously proposed slice 3 is split so that only what these rulings make
constructible is commissioned now.

**Three digests, kept strictly distinct.**

1. **`sample_index_digest`** commits to the ascending list of the 50 selected
   upstream BBH indexes, each encoded as a decimal string, under the governed
   algorithm `bbh_hash_rank_select.v1` (revision 12). Its governed value for the
   pilot fixture is
   `c521cdd75dc3b8c9e589835ade4b780ef26ba955d4077f5c7ad74e803be60682`. It commits
   to *which upstream items were sampled*, nothing else.
2. **`case_set_digest`** commits to the governed case set through the existing
   benchmark contracts (`BenchmarkManifest.benchmark_manifest_digest` and the
   `case_list_digest` helper). It is a digest over *case digests*, not over
   upstream indexes, and is not the sample-index digest.
3. **`index_digest`** commits to the Phase 4C prepared bundle's own `index.json`
   — `ugence_jcs.canonical_sha256_hex` over the sorted path-to-SHA-256 map of the
   nine ratified prepared artifacts (revision 4, §2.1). It cannot be derived until
   that exact artifact set exists on disk; it is a digest over *the prepared
   bundle itself*, not over the sample or the case set.

**Rejected: merging `index_digest` and `sample_index_digest`.** The slice-3
preflight proposed this as a temporary interim definition to unblock
`CalibrationResult` construction without building the prepared-bundle
subsystem. The owner rejects it: the two values answer different questions —
"which indexes were sampled" versus "which exact prepared artifact set was
committed" — and collapsing them would let a bundle substitution attack (same
sample, different provider configuration, different experimental design) pass
undetected under a digest that claims to cover the whole prepared set. No
`CalibrationResult` may carry a fabricated or merged `index_digest`.

**`verdict_custody_ref` — preregistered and index-bound, never a placeholder.**
The slice-3 preflight's proposal of a fixed placeholder string (analogous to
`PREREGISTRATION_DECLARED_UNVERIFIED`) is **rejected**: unlike preregistration
status, a custody reference points at a specific write target, and a fabricated
one would let a `CalibrationResult` claim custody that was never established.
Instead: `verdict_custody_ref` **must be supplied before preparation**, recorded
in the governed `experimental_design.json`, and therefore **committed by the
prepared bundle's `index_digest`** like every other prepared fact. It may be
copied into a `CalibrationResult` **only after** a later custody port
successfully writes and verifies verdict evidence at that exact reference —
slice 3A commits the reference; a later slice proves the write. For
provider-free tests, a clearly test-only URI such as `memory://workflow-fit-test/…`
may be used through a deterministic fake; it is never valid evidence for a
genuine run, and the production custody endpoint and its ACL facts remain D5
gates, unresolved by this revision.

**Slice split.** The previously commissioned "slice 3 core" is split:

- **Slice 3A** (commissioned by this revision): the Phase 4C prepared-bundle
  schemas, a deterministic writer, reader and verifier, under the ratified
  nine-path layout and the two role-specific commitment identifiers
  (`workflow_fit_prepared_index.v1` confirmatory,
  `workflow_fit_prepared_index.calibration.v1` calibration). Its output supplies
  a governed `index_digest`, `sample_index_digest` and `verdict_custody_ref` —
  nothing else.
- **Slice 3B** (not commissioned by this revision): F3/F4 runtime enforcement,
  the custody port, runner role branching, calibration output bundles,
  `CalibrationResult` construction and confirmatory provenance reconciliation.

**No `CalibrationResult` before both verifications.** A `CalibrationResult` may
be constructed only after (1) a slice-3A prepared bundle for that calibration
run verifies completely — every path present, every digest recomputed,
`sample_index_digest` independently reproduced from seed/population/algorithm —
and (2) the custody port slice 3B commissions successfully writes and verifies
verdict evidence at the bundle's committed `verdict_custody_ref`. Neither
condition alone is sufficient.

**Status.** This revision resolves the slice-3 preflight blocker by ruling, not
by building. It authorises slice 3A's prepared-bundle subsystem only. It does
**not** authorise runner changes, custody writes, `CalibrationResult`
construction, confirmatory provenance traversal, a genuine pilot, or any
provider call. D1–D5 remain incomplete.

### Revision 18 (slice-3A residual obligations after merge, 2026-09-04)

Slice 3A merged as PR #1583 (merge commit `acd2e92d5`). Three blocking findings
were raised by successive independent adversarial reviews and closed on the
branch before merge: **F1** (the credential-key scan had been narrowed to exact
name matching while fixing a false positive, letting `openai_api_key` through —
replaced with token-boundary matching, `8c66669c3`); **F1a** (`ProviderConfiguration`
documented a dotted `package.module:function` shape that nothing enforced, so a
credential passed as `provider_factory` would be committed by `index_digest` —
`fd42fd756`); **F1b** (that guard did not survive the round trip: `verify()`
never parsed `provider_configuration.json`, so a hand-written bundle could carry
a credential-shaped `provider_factory` and verify — `ff3b685b2`).

The following are **carried forward as open obligations**, not resolved by that
merge. Recording them here is not closure.

1. **`[G]` Free-form prepared fields still accept credential-shaped values —
   a gate on any genuine run.** `verdict_custody_ref`, `execution_order_rule`,
   `formula_id` and `formula_version` are unconstrained strings. Each accepts a
   credential-shaped value, each reaches a prepared artifact
   (`experimental_design.json`, and via that `preparation.json` and
   `case_set.json`), and `verify()` accepts all of them. The credential-key scan
   cannot catch this: it inspects key *names*, and here the secret would be a
   *value* under a legitimate key. Unlike `provider_factory`, none of these
   fields has a documented shape to enforce, so the F1a/F1b remedy does not
   transfer; closing this requires either per-field grammars or value-side
   scanning, both deliberately out of slice-3A scope. **No run with a real
   credential may be performed until this is closed.** It is not a slice-3A
   defect and did not block the merge.

2. **`[V]` `_FACTORY_PATH` inherits two laxities from the 4B precedent.**
   `experiments/workflow_fit_study/prepared_bundle.py` reuses the regex from
   `experiments/workflow_fit_reference_pilot/loaders.py` (`_FACTORY`) verbatim.
   Python's `$` matches before a trailing newline, so
   `"pkg.mod:func\n"` is accepted; and `\w` is Unicode-aware, so `pkg.möd:fünc`
   is accepted. Both are **symmetric across writer and reader** — the reader
   accepts exactly what the writer accepts — and neither admits a credential
   shape, since real key formats contain hyphens, which the regex refuses.
   Tightening to `\Z` and `(?a)` would diverge from the shared 4B convention, so
   this is to be revisited **only alongside the 4B loader**, not unilaterally in
   the 4C bundle.

3. **`[G]` The F1b tests assert refusal without matching the refusing guard.**
   `test_a_hand_written_credential_shaped_factory_is_refused_on_read` and
   `test_a_provider_configuration_of_any_other_shape_is_refused_on_read` use
   bare `pytest.raises(PreparedBundleError)` with no `match=`. Execution shows
   the six cases are refused by three different guards, and one — the payload
   carrying an extra `api_key` — is caught by the pre-existing credential-key
   scan rather than by the factory-path guard, so that case would still pass
   with F1b reverted. Five of the six do fail without the fix, so the suite is
   non-vacuous as regression evidence; the imprecision is in what one case
   *claims* to prove. To be corrected when the file is next touched.

**Process note `[V]`.** The F1b review was a same-session self-review by the
model that authored the fix. Its factual claims are settled by the repository
(executed probes, AST structure, definition-level byte hashes) rather than by
recollection, which the working agreement accepts for facts. The judgment call —
whether the guard sits at the right layer — was not independently checked, and
the merge proceeded on the owner's decision with that limitation stated.

**Status.** This revision records outcomes and open obligations. It authorises
nothing new: slice 3B remains uncommissioned, D1–D5 remain incomplete, and
obligation 1 above stands as a hard gate on any genuine run.

### Revision 19 (owner rulings: obligation-1 field shapes, 2026-09-04)

Revision 18 recorded, as an open obligation, that four free-form prepared fields
accept credential-shaped values and reach a prepared artifact, where
`index_digest` would commit them permanently. The credential-key scan cannot
catch any of them: it inspects key *names*, and here the secret would be a
*value* under a legitimate key. A preflight established that three of the four
had **no shape the repository settles**, and that inventing one would have been a
fabricated `[V]`. The owner therefore ratified the four shapes below. Each is an
**owner ruling `[R]`**, not an assistant proposal and not an inference from
existing usage.

1. **`verdict_custody_ref` — structural URI constraint only.** The value must be
   a well-formed absolute URI: a scheme starting with a letter, `://`, and a
   non-empty remainder containing no whitespace or control characters. The scheme
   is **deliberately not allowlisted.** §2.2 binds the concrete custody and
   registry endpoint at D5 ratification and declines to name it, on the stated
   ground that "a plausible-looking URI in a governance document would be a
   fabricated `[V]`"; an allowlist ratified today would encode exactly that. The
   structural constraint refuses a **bare** credential, since no key format carries
   `://` — but see obligation 4 below: it does **not** refuse a credential embedded
   inside an otherwise well-formed URI. **This ruling does not ratify any scheme,
   endpoint or custody medium**, and the test-only `memory://workflow-fit-test/…`
   form remains what revision 17 made it: never valid evidence for a genuine run.
2. **`execution_order_rule` — exact match on `ascending_case_digest`.** The owner
   ratifies this as the sole intended value. The field had **zero occurrences**
   in this note before now; its only prior appearance anywhere was a test
   fixture literal, which is why the shape could not be derived and had to be
   ruled.
3. **`formula_id` — the split is ratified; pinned by exact match to
   `calfloor.linear_chain`.** The owner ratifies the decomposition of this note's
   `calfloor.linear_chain.v1` (§2.1) into an id and a version composing as
   `<id>.v<version>`. That decomposition previously existed **only** in
   implementation fixtures and was never ratified here; this revision makes it
   governed rather than incidental.
4. **`formula_version` — a bare positive integer.** One or more digits, no
   leading zeros, no `v` prefix, no dotted form. This matches every value in
   evidence and composes with ruling 3 to reproduce `calfloor.linear_chain.v1`.

**Enforcement `[V]`.** All four are enforced in
`experiments/workflow_fit_study/prepared_bundle.py` at construction, and
re-validated on read: `verify()` reconstructs the design through
`_load_experimental_design`, which calls the real `ExperimentalDesign`
constructor, so the reader cannot accept a shape the writer refuses. This is the
same asymmetry F1b closed for `provider_factory`, and it is closed here by
construction rather than by a second copy of each rule.

**Obligation 2 is untouched and not reproduced.** `_FACTORY_PATH` keeps the 4B
precedent's `$` and Unicode-`\w` laxity by the revision-18 ruling. The two
regexes written fresh here anchor with `\Z` and exclude control characters, so
the laxity is **not** propagated into new code.

**Obligation 3 is narrowed, not closed.** Every test added by this revision
asserts the refusing guard **by message**, so no case can pass for an unintended
reason. The one candidate that would have been refused earlier by the
pre-existing non-blank guard was removed from its parametrize list rather than
left to assert a refusal this ruling did not cause. The three earlier F1b tests
named in revision 18 are unchanged and still carry that imprecision.

**Obligation 4, as it was raised — superseded by the ruling below; retained for the
record and no longer a description of current behaviour.** The structural ruling
refused a bare credential but not one carried inside a URI's userinfo, path, query or
fragment: `https://user:<key>@host/p`, `https://host/<key>` and `memory://x#<key>` were
all accepted by the writer, accepted by `verify()`, and committed by `index_digest`
`[V]`. A scheme allowlist would not have closed this — every one of those values carries
a legitimate scheme — so it was never an argument for revisiting ruling 1. Closing it
needed a separate owner ruling on whether a custody reference may carry userinfo or
opaque path, query and fragment segments at all. **That ruling was given and is recorded
immediately below**; two of the three shapes are now refused and the third is addressed
by ruling 6.

**Obligation 4 — ruled. `verdict_custody_ref` is a non-secret locator and must never be
used to transport credentials `[R]`.** For **every** URI scheme, until D5 ratifies a
narrower scheme and endpoint allowlist:

1. **Userinfo is forbidden.** Any URI whose parsed authority contains a username,
   password or other content before `@` is refused.
2. **Query and fragment components are forbidden.**
3. **Percent-encoding is forbidden.**
4. **The path**, when present, may use only ASCII letters, digits, `/`, `-`, `_`, `.` and
   `~`; must stay within a documented maximum length; and must contain no empty interior,
   `.` or `..` segments. The documented maximum is **255 characters**
   (`_MAX_CUSTODY_REF_LENGTH`) — a documented bound, not a derived one.
5. **Applied at construction and repeated on read**, so a bundle read from disk is held to
   the same rules as one being written.
6. **These are syntax restrictions and prove nothing about content.** They do **not**
   establish that an allowed-looking path contains no secret, and no code or document may
   claim they do. A genuine run must obtain `verdict_custody_ref` from a trusted,
   D5-approved configuration or registry; a reference supplied by an untrusted source
   remains prohibited.

**Provisional, and versioned when replaced.** These all-scheme restrictions stand in for an
allowlist that does not yet exist. A future D5 ratification may replace them with approved
schemes, authorities and reference forms. That replacement **must be versioned**: it takes a
new commitment identifier and must never silently reinterpret an existing prepared bundle.

**What ruling 6 costs, made concrete `[V]`.** A credential whose format is ASCII letters,
digits and hyphens — the common `sk-…` shape — is a **valid path segment** under ruling 4
and is therefore still accepted as `https://custody.invalid/<key>`. Refusing it would mean
banning hyphens from locator paths, which ruling 4 permits. This is not a gap in the
implementation; it is exactly the residue ruling 6 names, and the test suite asserts the
acceptance explicitly so it can never be mistaken for an oversight. Of the three shapes
revision 19 previously pinned as open, two (userinfo, fragment) are now refused and this
third remains accepted **by ruling**.

**On the record of this correction.** Revision 19 as first written asserted that
the structural constraint "refuses every credential shape". That was false in the
case above, and the overstatement originated in the assistant-drafted option text
the owner ratified from, not in the owner's ruling. The ruling itself stands
unchanged; only the claim made for it is corrected. The four guards are unmodified.

**Status.** Obligation 1 is **closed for these four fields**, and obligation 4 is
**ruled and enforced** for userinfo, query, fragment, percent-encoding, path charset,
traversal segments and length. What remains open is not a defect but ruling 6's stated
limit: syntax cannot prove a permitted path carries no secret, so **no genuine run may take
`verdict_custody_ref` from an untrusted source**, and the field's contents are never
evidence that no credential was committed.

This authorises no run: D1–D5 remain incomplete, the custody endpoint remains
unbound, slice 3B remains uncommissioned, and no provider call, credential access
or genuine calibration is permitted by this revision.

### Revision 20 (owner rulings: slice-3B preflight decisions and implementation order, 2026-09-04)

The slice-3B preflight established that the custody endpoint is unbound at D5 and that four
further items blocked commissioning. The owner ruled that all five can be settled **without**
D5 endpoint details. Each below is an **owner ruling `[R]`**.

1. **Custody port — build now.** Define `VerdictCustodyPort` and a deterministic in-memory
   test double. D5 later binds the real endpoint, ACLs, writer identities, encryption,
   retention and deletion policy. This revision binds none of them.
2. **Lifecycle — the Phase 4A amendment comes first**, as a separate prerequisite change
   before runner branching. A calibration ends successfully at `UNDER_TEST` **only when a
   valid, verified `CalibrationResult` exists**; it must never emit `RESULT_ASSESSED` and
   never become `EVALUATED`. This closes the `[G]` recorded in revision 13.
3. **`CalibrationResult` with the fake custody double — tests only.** Construction using the
   in-memory double is permitted **solely in tests**. It is never genuine custody evidence and
   never authorises a real calibration or confirmatory run.
4. **Refusal codes — already ratified.** The original seven were owner-ratified in revision 10
   and the four calibration names in revision 13; their presence in `PilotErrorCode` is
   legitimate. D1–D5 remain incomplete because several codes' **runtime enforcement** is still
   missing, **not** because their names are unratified. No code may be added without a ballot.
5. **Path residue — retain the trust-boundary control.** Maximum segment length is **not** to
   be used as secret detection: it would reject legitimate hashes and identifiers while
   missing shorter secrets. D5 must eventually bind custody references to approved schemes,
   authorities and namespaces, or to a registry. Revision 19 ruling 6 stands unchanged.

**Commissioned implementation order.**

- **Slice 3B-0** — the narrow Phase 4A lifecycle amendment (ruling 2).
- **Slice 3B-1** — F3 entry-point eligibility gate, F4 constructor-based role revalidation,
  the custody port and its test double.
- **Slice 3B-2** — the calibration runner branch and test-only `CalibrationResult` production.
- Real custody adapters and genuine execution **remain blocked until D5**.

**Entry point.** The existing `run_pilot` stays available for historical
mechanism-validation tests. A **separately named Phase 4C entry point** invokes
`require_phase_4c_eligible()` before delegating. A v1 manifest is **never** silently
reinterpreted.

**Slice 3B-0 as implemented `[V]`.** `contracts/lifecycle.py` gains `is_calibration_run`
(false for a v1 manifest, which carries no committed role) and `require_calibration_endpoint`,
which refuses a non-`UNDER_TEST` record, a missing or wrongly-typed `CalibrationResult`, and a
result bound to another manifest. `transition` refuses `RESULT_ASSESSED` under `CALIBRATION`
**before** its state and result checks, so the refusal names the run role rather than a
missing `ReadinessComparisonResult` — under `CALIBRATION` no such result can exist, revision 13
having made comparison unconstructible for that role. `validate_lineage` refuses a hand-built
`EVALUATED` record on a calibration manifest on replay.

**Two limits recorded, not papered over `[G]`.** First, `require_calibration_endpoint`
establishes that a `CalibrationResult` is *constructed and manifest-bound*, **not**
*custody-verified*; revision 17 requires a verifying prepared bundle **and** a successful
custody write before a result is genuine evidence, and the custody port is slice 3B-1 with
real adapters blocked on D5. Passing this check is necessary, never sufficient. Second, the
absent-result refusal uses **`ROLE_ARTIFACT_INCONSISTENT`** rather than a new code: ruling 4
forbids additions without a ballot, and that code names what has gone wrong — the CALIBRATION
role requires an artifact that is absent or of the wrong type.

**Status.** This revision authorises slices 3B-0, 3B-1 and 3B-2 as scoped above and nothing
more. D1–D5 remain incomplete, the custody endpoint remains unbound, real custody adapters and
genuine execution remain blocked, and no provider call, credential access or genuine
calibration is permitted by this revision.

### Revision 21 (slice 3B-1 as implemented: F3, F4 and the custody port, 2026-09-04)

Implements slice 3B-1 as commissioned by revision 20. This revision **rules nothing new**; it
records what the code now enforces and what it still does not.

**F3 — enforced `[V]`.** `runner.run_phase_4c_pilot` is the separately named Phase 4C entry
point. It calls `manifest.require_phase_4c_eligible()` before any boundary process exists, so
a v1 manifest is refused by the entry point rather than only by callers that ask. `run_pilot`
is **unchanged** and remains available for historical mechanism-validation tests; the two are
not aliases, which a test asserts by source inspection. A v1 manifest is refused, **never**
upgraded or silently reinterpreted. The slice-2 test that pinned F3 as unenforced is inverted
rather than deleted: it now requires `runner.py` to appear in the caller list.

**F4 — enforced `[V]`.** `PilotStudyManifest.revalidate_role()` rebuilds the manifest through
its own constructor, which re-runs the role invariants, and requires the freshly settled
digest to equal the one carried. This is the substance of the F4 obligation: the v1 digest
payload excludes `run_role` and `calibration_provenance`, so a v1 object whose role was set by
circumventing the frozen dataclass keeps a digest that still verifies — a test demonstrates
exactly that, then shows `revalidate_role` refusing it. Recomputing the digest alone would
not have caught it. `run_phase_4c_pilot` calls it alongside the F3 gate.

**Custody port `[V]`.** `custody.py` defines `VerdictCustodyRecord` (a settled
`record_digest` over reference, manifest digest, index digest and an ascending, duplicate-free
verdict set), the `VerdictCustodyPort` protocol, `write_and_verify`, and the test-only
`InMemoryVerdictCustody` double. `write_and_verify` performs the two-step revision 17 requires
— write, then read back and compare — as **two distinct call sites**, so a failure is
classified by the operation that failed per §2.3: `RETENTION_WRITE_FAILED` for the write,
`RETENTION_VERIFY_FAILED` for the read-back, never one reported as the other. No refusal code
was added (ruling 4).

> **Superseded by revision 23 — retained for the record and no longer a description of
> current behaviour.** The clause "never one reported as the other" was **false** when
> written: `write_and_verify` wrapped neither call site, so an adapter's own choice of
> exception decided the category. The behaviour it describes became true only with the
> revision-23 correction, refined in revision 24. The `[V]` label on this paragraph did not
> hold at the time it was applied.

**Deliberately not done, and why.**

- **No endpoint, ACL, writer identity, encryption, key custody, retention or deletion policy
  is bound** — all remain D5 (ruling 1). The module names none of them.
- **The double is test-only** (ruling 3): process-local, persisting nothing, enforcing no
  access-control list, holding no retention policy. It is never genuine custody evidence and
  authorises no run.
- **The port does not re-validate `custody_ref` syntax `[G]`.** The obligation-4 grammar
  (revision 19) lives with the prepared bundle, which commits the reference under
  `index_digest` before any custody call. The package must not import from `experiments`, and
  a second copy of the grammar here would be a second authority free to drift from it. The
  consequence is that a caller bypassing the prepared bundle could hand the port an
  unvalidated reference — which is ruling 5's trust boundary restated, not a new gap.
- **No runner role branching and no `CalibrationResult` production** — slice 3B-2.

**Status.** Slices 3B-0 and 3B-1 are complete. D1–D5 remain incomplete, the custody endpoint
remains unbound, real custody adapters and genuine execution remain blocked, and no provider
call, credential access or genuine calibration is permitted by this revision.

### Revision 22 (slice 3B-2 as implemented: the calibration branch, 2026-09-04)

Implements slice 3B-2 as commissioned by revision 20. This revision **rules nothing new**.

**The calibration branch `[V]`.** `run_pilot` now returns immediately after execution when
`is_calibration_run(manifest)` holds, with no `ReadinessComparisonRequest`, no engine call, no
`RESULT_ASSESSED` transition and no coverage report — revision 13's role matrix, enforced
rather than merely stated. `PilotRunResult.coverage` becomes `Optional`, and is `None` for
that role: coverage reports *challenger* coverage and a calibration run assigns no challenger,
which makes a success summary **impossible** rather than empty. The run rests at
`UNDER_TEST`; whether that is a *completed* calibration is decided by
`require_calibration_endpoint` (slice 3B-0) against a `CalibrationResult`, never by the runner.

> **"Impossible rather than empty" superseded by revision 24 — retained for the record.** The
> mechanism at the time was an untyped `AttributeError` from `report.render`, not a designed
> refusal, and the accompanying test codified `(AttributeError, TypeError)` as the guarantee.
> `render` now refuses a calibration result with `ROLE_ARTIFACT_INCONSISTENT`, and the test
> asserts that typed refusal instead.

**Historical behaviour is unchanged `[V]`.** `is_calibration_run` is false for a v1 manifest
and for a v2 CONFIRMATORY manifest, so no historical mechanism-validation run and no
confirmatory run can take the branch. The branch is asserted over the **AST** of the runner,
not its source text, so a comment naming `RESULT_ASSESSED` can neither pass nor fail the test.

**Test-only `CalibrationResult` production `[V]`.** `custody.build_calibration_result`
constructs a result only after **both** revision-17 conditions:

- **Condition 1 — the prepared bundle verified** — is the caller's, evidenced by the new
  `VerifiedPreparedFacts`. The verifier lives in `experiments/`, the package must not import
  from there, and this function therefore **cannot** re-check it and does not pretend to. The
  type exists to make the hand-off explicit and to carry the obligation `[G]`.
- **Condition 2 — a successful custody write and read-back** — is performed here through
  `write_and_verify`, so no result can rest on a write that failed or could not be verified.

`VerifiedPreparedFacts` re-asserts revision 17's rule that `index_digest` and
`sample_index_digest` are strictly distinct. A custody record addressed elsewhere, or binding
another manifest or index digest, is refused **before** any write — tests assert that nothing
was written. `governed_unit` is not a parameter: it is fixed at `score.unit` by the contract.

**Revision 20 ruling 3 holds.** Every result built in the suite uses
`InMemoryVerdictCustody`. It is never genuine custody evidence and authorises no real
calibration or confirmatory run.

> **Superseded by revision 23 — retained for the record.** "Every result built in the suite"
> was **false**: two helpers in `tests/contracts/test_run_role_and_calibration.py` build
> `CalibrationResult` objects with no custody at all. Ruling 3 is unaffected — neither is
> genuine evidence — but the sentence overstated what the suite does.

**Status.** Slices 3B-0, 3B-1 and 3B-2 are complete. What remains blocked is unchanged and
unchanged in kind: D1–D5 incomplete, the custody endpoint unbound, real custody adapters and
genuine execution blocked, no provider call, no credential access, no genuine calibration.

### Revision 23 (independent-review corrections to slices 3B-1 and 3B-2, 2026-09-04)

An independent adversarial review of the 3B stack returned NOT APPROVED. It was commissioned
to run on a different model than the one that wrote the code, after five same-session
self-reviews of earlier slices had missed defects of exactly this kind. **That provenance is
a process claim this repository cannot itself settle**; what it can settle is the findings,
which are reproduced below and were each verified against the code. This revision records the corrections. It **rules
nothing new**.

**Withdrawn: revision 21's `[V]` claim about failure classification.** Revision 21 asserted
that `write_and_verify` classifies by call site so a write failure is "never one reported as
the other". **That was false.** The function wrapped neither call, so classification was
delegated entirely to whatever an adapter chose to raise: an adapter raising
`RETENTION_VERIFY_FAILED` from `write()` surfaced as a verify failure from the write site,
and a bare `OSError` from either side surfaced unclassified. §2.3 rules that *"the call site
determines the category"*, which the code did not do.

**Corrected `[V]`.** `write_and_verify` now wraps each call site and re-raises `Exception`
with that site's code, chained from the original so the cause survives. (As first written
this said "any `Exception`", which revision 24 found overstated: an adapter exception whose
`__str__` raised escaped both wrappers as the *formatting* error. Corrected there.) `BaseException` is
never caught — an interrupt is not a retention outcome. Read-back verification now requires
`isinstance(stored, VerdictCustodyRecord)` **and** `stored == record`, not digest equality
alone, since any object can carry a matching attribute. Eight tests cover this, asserting by
error code and by `__cause__`.

**Withdrawn: revision 22's claim about custody in the suite.** Revision 22 said "every result
built in the suite uses `InMemoryVerdictCustody`". **False**: two helpers in
`tests/contracts/test_run_role_and_calibration.py` build `CalibrationResult` objects with no
custody at all. Ruling 3 is unaffected — neither is genuine evidence — but the claim was
wrong and is withdrawn.

**Corrected: a reader broken by slice 3B-2 `[V]`.** Making `PilotRunResult.coverage` optional
changed the writer and left `report.render` unchanged, so rendering a calibration result
raised `AttributeError` — the same writer/reader asymmetry F1b closed for `provider_factory`,
repeated. `render` now refuses a calibration result closed, with
`ROLE_ARTIFACT_INCONSISTENT` (no new code, ruling 4). Refusing is correct rather than
conservative: the renderer's whole shape is confirmatory, and calibration output bundles are
not commissioned.

**Corrected: the calibration branch is now proven by behaviour `[V]`.** Revision 22's `[V]`
rested on an AST assertion. A real CALIBRATION manifest now executes through the boundary with
the stub provider in `tests/pilot/test_end_to_end.py`, asserting that the methods complete,
the states are exactly `PROPOSED → UNDER_TEST`, `request`/`result`/`coverage` are `None`,
`outcomes` is empty, lineage replays, the Phase 4C entry point admits it, and `render` refuses
it.

**Corrected: a vacuous test.** Dropping the `is_v2` clause from `is_calibration_run` failed
none of the 204 tests, because a constructor-built v1 always has `run_role=None` and the
clause never decides. The test now tampers a v1 manifest with a smuggled role, which is the
only case distinguishing the two implementations. Four bare `pytest.raises` calls across three tests now assert
an error code or message.

**Carried forward, not closed `[G]`.**

1. **`revalidate_role` is applied at one site only.** `run_phase_4c_pilot` calls it;
   `validate_lineage` — the replay verifier — does not, and `is_calibration_run` reads
   `run_role` directly. A v2 manifest tampered from CONFIRMATORY to CALIBRATION is therefore
   trusted by `transition`, `validate_lineage`, `require_calibration_endpoint` and a direct
   `run_pilot` call. The F4 obligation text names a *verifier*; the replay verifier does not
   yet re-run role validation.
2. **`build_calibration_result` reconciles neither `score_count` against the number of
   verdicts in the custody record, nor the verdicts' case digests against the benchmark case
   set** (it never sees the manifest).
3. **`run_phase_4c_pilot` has no non-test caller**, so the F3 gate is opt-in; nothing pins
   that a future Phase 4C pipeline chooses it over `run_pilot`.

**Status.** Slices 3B-0, 3B-1 and 3B-2 stand as commissioned, with the corrections above. D1–D5
remain incomplete, the custody endpoint remains unbound, real custody adapters and genuine
execution remain blocked, and no provider call, credential access or genuine calibration is
permitted by this revision.

### Revision 24 (second independent-review corrections, 2026-09-04)

A second independent adversarial pass over the corrected stack confirmed the revision-23
blocking defect closed and returned CONDITIONALLY APPROVED. This revision closes what it
found. It **rules nothing new**.

**Corrected: the `__str__` escape `[V]`.** Revision 23 said `write_and_verify` re-raises
"any `Exception`" with its site's code. Both handlers interpolated `str(e)`, so an adapter
exception whose `__str__` itself raises escaped **both** wrappers as the *formatting* error,
unclassified — fail-closed, since no result is built, but not what was claimed. The handlers
now interpolate `type(e).__name__` only; the original is chained, so nothing is lost by not
rendering it. Two tests cover it, one per site, with an exception class whose `__str__`
raises. Revision 23's sentence is corrected in place.

**Corrected: superseded claims now annotated where they stand.** Revision 23 withdrew two
false claims but left both original sentences unmarked at their sites, so a reader of
revision 21 or 22 alone still met a false `[V]`. Following the revision-19 form, revision 21's
"never one reported as the other", revision 22's "every result built in the suite uses
`InMemoryVerdictCustody`", and revision 22's "impossible rather than empty" now carry
in-place supersession notes. The original text is retained, not deleted.

**Corrected: an untyped crash no longer stands as a guarantee.**
`test_a_success_summary_is_impossible_without_a_coverage_report` asserted
`(AttributeError, TypeError)`, codifying a crash as the design property revision 22 described.
It now asserts the typed refusal that is the real guarantee — `render` raising
`ROLE_ARTIFACT_INCONSISTENT` — and pins separately that `success_summary` has not silently
acquired a guard of its own.

**Hardened, though already correct `[V]`.** The review verified that a read-back returning a
subclass instance or a mutated record with a forced `record_digest` is refused; only the
`SimpleNamespace` case was tested. Both now have tests.

**Corrected: two small overstatements in revision 23** — "any `Exception`" (above) and "three
bare `pytest.raises` calls", which was four calls across three tests. The claim that the
review "was run on a different model" is a process fact this repository cannot settle; it is
now stated as what was commissioned rather than as a verified property.

**Carried forward, added to revision 23's three `[G]` items.**

4. **`transition` does not refuse `RESULT_INCONCLUSIVE` carrying a
   `ReadinessComparisonResult` on a CALIBRATION manifest** (`contracts/lifecycle.py`,
   the guarded events are `RESULT_ASSESSED`/`EVALUATED` only). An `INCONCLUSIVE` record
   carrying a `result_digest` can therefore be hand-built for a calibration run and would
   replay if the result is supplied. Revision 13 forbids *comparison* for that role, not
   merely assessment, so this is narrower than the ruling. Unprobed — closing it needs a
   synthetic engine result.
5. **The behavioural calibration test is behind a module-level `importorskip`** in
   `tests/pilot/test_end_to_end.py`. Where the `agentic` tree is absent it is skipped, and
   the calibration branch is then covered by the AST assertion alone. Revision 23's
   behavioural `[V]` holds in this environment, not universally.

**Status.** Unchanged in kind: D1–D5 incomplete, the custody endpoint unbound, real custody
adapters and genuine execution blocked, no provider call, no credential access, no genuine
calibration.

### Revision 25 (slice 3B-3: carried-forward items G4 and G5 closed, G3 narrowed, 2026-09-04)

A read-only preflight over revision 24's five carried-forward `[G]` items found three settled
by the repository and two requiring owner rulings. This slice closes the settled ones. It
**rules nothing new**, and does **not** touch G1 or G2.

**G4 — closed `[V]`.** Revision 13 forbids **comparison** under `CALIBRATION`, not merely
assessment, and a `ReadinessComparisonResult` is comparison evidence. Guarding only
`RESULT_ASSESSED` left `INCONCLUSIVE`-carrying-a-result constructible, which was narrower
than the ruling. `transition` now refuses **any** event supplying a result under that role,
placed before the state and result checks so the refusal names the run role rather than a
downstream symptom; `validate_lineage` refuses a record naming an engine result on replay.

> **Corrected by revision 26 — retained for the record.** "Any event" was **not** literally
> true as first written: the guard sat *below* the `SUPERSEDED` block, so a result supplied
> with `SUPERSEDED` was accepted (harmlessly — a `REVISED` record carries no result). The
> guard now sits above it, after the `RESULT_ASSESSED` guard, and the test iterates every
> `LifecycleEvent` member.

The `capture_refusal` path stays open, and a test pins it: a calibration run whose capture
fails must still reach `INCONCLUSIVE`, and that path supplies no result. A second test pins
that the confirmatory path is untouched.

> **Corrected by revision 26 — retained for the record.** That test passed `result=None`, so
> the G4 guard (`result is not None and …`) could not fire for *any* role: it asserted a
> refusal while claiming to show acceptance, and "proving the G4 guard is not what fires
> there" was true only trivially. It is replaced by one that obtains a real
> `ReadinessComparisonResult` through the boundary and asserts the transition **succeeds**.
> The confirmatory path was in fact pinned all along — by fourteen other tests, as a
> role-blind stub of the guard shows.

**G5 — closed `[V]`.** `tests/pilot/test_end_to_end.py` proves the calibration branch
behaviourally but sits behind a module-level `importorskip` on the `agentic` tree, which is
present in this repository but is **not a declared dependency** of the pilot package — so on
a minimal install the branch fell back to the AST assertion alone. A second behavioural test
in `tests/test_calibration_branch.py` now runs the same calibration through the boundary
using `pilot_fixtures.FakeExecutor`, importing nothing outside this package's own fixtures.
That module carries no skip guard and no `agentic` or `experiments` import.

**G3 — narrowed, not closed `[G]`.** A tripwire test asserts that
`experiments/workflow_fit_study` contains no call to the ungated `run_pilot`.

> **Corrected by revision 26 — retained for the record.** The walk matched `ast.Name` only,
> so it asserted no *bare-name* call: `runner.run_pilot(...)`, `api.run_pilot(...)`, an
> aliased import and a rebound variable all passed it. It now also follows `ImportFrom`
> aliases, simple rebindings, and any attribute call named `run_pilot`; all five forms are
> probed. It is
**vacuously true today** — the Phase 4C pipeline does not exist, so there is no runner call
to find — and the test says so in its own docstring. It is a tripwire for when that pipeline
is built, **not** evidence that the F3 gate is mandatory. G3 stays open until a Phase 4C
pipeline exists and calls the gated entry point.

**A vacuous test caught before merge `[V]`.** The first G4 transition test asserted only the
error code. Without the guard, the INCONCLUSIVE case still raises `STATE_TRANSITION_INVALID`
from the downstream "requires the `ReadinessComparisonResult`" check, so the test passed
either way and proved nothing — stubbing the guard failed **zero** of 223 tests. It now
asserts the message per event and fails when the guard is removed. Recorded because it is the
same obligation-3 failure mode revision 19 named and revisions 23–24 corrected twice.

**Still open, awaiting owner rulings — unchanged by this slice.**

1. **G1.** `revalidate_role` is applied only at `run_phase_4c_pilot`. Extending it to
   `validate_lineage` follows from F4's own text; whether `is_calibration_run` — a cheap
   predicate called inside `transition` and `validate_lineage` — is a **trust boundary**
   (revalidating, at the cost of a manifest rebuild and digest recompute per call) or a
   **convenience** is a design ruling the repository does not settle.
2. **G2.** Wiring the reconciliation is mechanical; what to reconcile is not. The note ties
   `score_count` to the **benchmark case count** and says nothing about custody verdict
   count, and for a CALIBRATION run the sample is 50 of 250 — so whether the authoritative
   case set is the benchmark's full set or the sampled subset is unsettled.

**Status.** Five carried-forward items become two closed, one narrowed, two open. D1–D5 remain
incomplete, the custody endpoint remains unbound, real custody adapters and genuine execution
remain blocked, and no provider call, credential access or genuine calibration is permitted by
this revision.

### Revision 26 (independent-review corrections to slice 3B-3, 2026-09-04)

An independent adversarial review of slice 3B-3 returned CONDITIONALLY APPROVED: G4 and G5
closed by code and pinned by non-vacuous tests, with three sentences of revision 25
overstating by one notch and one new test vacuous for its stated purpose. This closes all
four. It **rules nothing new**, and G1 and G2 remain untouched and open.

1. **"Any event" made true `[V]`.** The G4 guard sat below the `SUPERSEDED` block, so a
   result supplied with `SUPERSEDED` was accepted — harmless, since a `REVISED` record
   carries no result, but not what revision 25 claimed. The guard now sits above it and
   below the `RESULT_ASSESSED` guard, which keeps that event's more specific message. The
   test iterates **every** `LifecycleEvent` member rather than two.
2. **A vacuous confirmatory test replaced `[V]`.** It passed `result=None`, so the G4 guard
   could not fire for any role; it asserted a refusal while claiming to show acceptance. The
   replacement runs a confirmatory manifest through the boundary, obtains a real
   `ReadinessComparisonResult`, and asserts the transition **succeeds** with a matching
   `result_digest`. The confirmatory path was pinned regardless — a role-blind stub of the
   guard fails fourteen other tests.
3. **The G3 tripwire widened `[V]`.** It matched `ast.Name` only, so `runner.run_pilot(...)`,
   `api.run_pilot(...)`, `from … import run_pilot as rp` and a rebound `f = rp` all passed.
   It now follows `ImportFrom` aliases and simple rebindings and flags any attribute call
   named `run_pilot`. All five forms are probed in a scratch worktree; each fails the
   tripwire, and a clean tree passes. **G3 is still narrowed, not closed** — the tripwire
   remains vacuous until a Phase 4C pipeline exists.
4. **Three sentences of revision 25 annotated in place**, per the revision-19 form, with the
   original text retained.

**Two vacuous tests in one slice, recorded `[G]`.** One was caught by the author before
push, one by review. Both asserted an outcome that the surrounding code produced anyway, so
neither pinned what its name claimed. This is the same failure mode revision 19 named as
obligation 3 and revisions 23 and 24 each corrected; it has now recurred in four consecutive
slices, always found by adversarial checking rather than by writing the test. The practice
that catches it — stub the guard, confirm the test fails — is cheap and should be treated as
required for any test asserting a refusal, not as a review-time backstop.

**Status.** Unchanged in kind: G4 and G5 closed, G3 narrowed, G1 and G2 open on owner
rulings. D1–D5 remain incomplete, the custody endpoint remains unbound, real custody adapters
and genuine execution remain blocked, and no provider call, credential access or genuine
calibration is permitted.

### Revision 27 (owner rulings on G1 and G2, and their implementation, 2026-09-04)

The two carried-forward items revision 25 left open are ruled and closed. Each ruling below
is an **owner ruling `[R]`**; the implementation notes are `[V]`.

**G1a — `is_calibration_run` is a convenience, not a trust boundary.** It reads `run_role`
directly and stays O(1). The trust boundary is the Phase 4C entry point and `validate_lineage`,
not every predicate call: revalidating inside the predicate would make `transition`
O(manifest) and cost a manifest rebuild plus digest recompute for every record replayed. The
consequence is accepted knowingly: a tampered manifest is trusted wherever the field is read
without revalidation — `transition`, `require_calibration_endpoint`, and a direct `run_pilot`
call — and the replay verifier is what catches it.

> **Extended by revision 28 — retained for the record.** As first written this named only
> `transition`. Revision 23's G1 record named `require_calibration_endpoint` and a direct
> `run_pilot` call as well; the same ruling covers all of them and the list is now complete.

**G1b — `validate_lineage` re-runs role validation, once per distinct manifest.** F4's
obligation names a *verifier*, and this is it. The v1 digest payload excludes the role fields,
so recomputing that digest proves nothing about them. Cost is proportional to manifests, not
records. This closes G1's substance: a v1 manifest whose role was set by circumventing the
frozen dataclass keeps a digest that still verifies and is now refused on replay.

**G2a — the custody verdict count must equal `score_count`, exactly.** `score_count` is the
number of cases scored and the custody record holds one verdict per scored case. A truncated
or partial custody write is refused **before** any write is attempted.

**G2b — the authoritative case set is the sampled subset, not the full benchmark.** For a
CALIBRATION run the sample is 50 of 250, and custody verdicts must cover **exactly** the case
set the prepared bundle committed — neither a different set of the same size nor a partial
cover. *(Revision 28: true of the code from the start, but the test was one
direction short — it omitted verdicts covering **more** than was prepared, so weakening the
check to a superset comparison shipped green. All three directions are now pinned.)* Since `build_calibration_result` never sees the manifest, those digests are carried on
`VerifiedPreparedFacts.case_digests`, which is required, non-empty and duplicate-free.

**Implementation `[V]`.** `validate_lineage` revalidates each supplied manifest before
replaying. `build_calibration_result` performs both reconciliations before
`write_and_verify`, so a mismatch never reaches the custody store — tests assert
`written_references() == ()`. A test pins that `is_calibration_run` does **not** call
`revalidate_role`, so the G1a ruling cannot be quietly reversed by a later change.

> **Corrected by revision 28 — retained for the record.** "Cannot be quietly reversed" was too
> strong: the pin parsed the function for a `revalidate_role` **attribute call**, catching a
> direct call and a call through the class, but a module-level helper, a `getattr` call and an
> inline `dataclasses.replace` rebuild all passed it. The pin is now behavioural — it counts
> actual calls and asserts the predicate trusts the field — and all three forms fail it. Every new
guard was stubbed and fails one test each.

**What this does not do.** It binds no endpoint, ACL, writer identity, encryption, retention
or deletion policy; those remain D5. It does not make `InMemoryVerdictCustody` genuine
evidence, and it does not authorise a run. **G3 remains narrowed and open** — the tripwire is
vacuous until a Phase 4C pipeline exists and calls the gated entry point.

**Status.** Of revision 24's five carried-forward items: G4 and G5 closed in revision 25,
G1 and G2 closed here, **G3 alone remains open**. D1–D5 remain incomplete, the custody
endpoint remains unbound, real custody adapters and genuine execution remain blocked, and no
provider call, credential access or genuine calibration is permitted by this revision.

### Revision 28 (independent-review corrections to revision 27, 2026-09-04)

An independent adversarial review of revision 27 returned CONDITIONALLY APPROVED: all four
rulings implemented as stated and surviving every attack, with two claims outrunning the
tests behind them and one consequence recorded less completely than revision 23 had it. This
closes all three. It **rules nothing new**.

**Confirmed under attack `[V]`, worth recording because it was doubted.** `frozenset` is the
correct comparison for G2b: both sides are validated 64-lowercase-hex and duplicate-free by
construction, so set equality *is* multiset equality, and the record's verdict order is
already forced ascending. An ordered comparison would add nothing and would wrongly refuse a
prepared set given in a different order. Ten attack shapes — uppercase hex, padded digests,
list-not-tuple, empty, duplicated, superset, subset, disjoint — are all refused, and nothing
is written on any of them.

**Corrected: the G1a pin was partly theatre `[V]`.** It parsed `is_calibration_run` for a
`revalidate_role` attribute call. That caught a direct call and a call through the class, but
a module-level helper, a `getattr` call and an inline `dataclasses.replace` rebuild all
passed it — three ordinary forms. The pin is now behavioural: it counts actual calls to
`revalidate_role` across a calibration, a confirmatory and a v1 manifest and asserts zero,
then asserts the predicate reads a tampered v2 CONFIRMATORY→CALIBRATION manifest as a
calibration run, which is the ruling's accepted consequence made explicit. All three bypass
forms now fail it.

**Corrected: the G2b test was one direction short `[V]`.** The code refused verdicts covering
*more* than the prepared set from the start; the test did not, so weakening the check to a
superset comparison failed **zero** of 228 tests. All three directions — different set of the
same size, strict subset, strict superset — are now pinned, each with a message match, and
both weakenings now fail.

**Corrected: the G1a consequence, restored in full.** Revision 23 named
`require_calibration_endpoint` and a direct `run_pilot` call alongside `transition` as sites
that trust `run_role`. Revision 27 named only `transition`. The same ruling covers all of
them; the record now says so.

**Three claims annotated in place** per the revision-19 form, with the original text
retained.

**Status.** Unchanged in kind: G1 and G2 closed, **G3 alone remains open** and vacuous until
a Phase 4C pipeline exists. D1–D5 remain incomplete, the custody endpoint remains unbound,
real custody adapters and genuine execution remain blocked, and no provider call, credential
access or genuine calibration is permitted.

### Revision 29 (owner rulings: no Phase 4C pipeline yet; a Phase 4C integration test instead, 2026-09-04)

A preflight on closing G3 raised a concern about the task rather than a blocker: **G3 is a
tripwire for a future pipeline bypassing the F3 gate, not a defect to clear.** Building a
pipeline *in order to* close G3 inverts cause and effect — the pipeline should be built when
a run needs it, and G3 should close as a side effect. Against that stood a real argument: the
point where slices 3A and 3B meet had never been exercised together. Three owner rulings
`[R]` settle it.

1. **No Phase 4C pipeline module yet — a narrower integration test instead.** It catches
   integration defects without creating a production surface that has no genuine user until
   D1 and D5 land. **G3 therefore stays open**, and this revision closes nothing: a test adds
   no production caller of `run_phase_4c_pilot`, so the tripwire remains vacuous.
2. **Cases reach a run through a caller-supplied external path.** BBH prompts and targets
   never enter the repository. The test writes synthetic cases to a temporary directory and
   loads them back through that path, so the mechanism is exercised rather than bypassed.
3. **The custody step is reached and stops, rather than omitted.** The blocker is expressed
   in executable form, not only in prose.

**What the integration test establishes `[V]`.** For the first time, end to end: a prepared
bundle is written and verified (3A); cases are loaded from an external path and **proved to
reproduce the prepared benchmark manifest** before anything runs; the gated entry point admits
the v2 CALIBRATION manifest (3B-1); the calibration branch produces no comparison, no coverage
and no outcomes, resting at `UNDER_TEST` (3B-2); lineage replays; and a `CalibrationResult`
built over the test-only double carries only digests that came from the verified bundle.

> **Corrected by revision 30 — retained for the record.** Three claims in this paragraph were
> false or overstated as written. **"End to end"**: 3A → gated run was exercised; run →
> `CalibrationResult` → endpoint was not, and `require_calibration_endpoint` was never called.
> **"Proved to reproduce"**: the loader compared digest *labels* from a column in the case
> file; cases whose `query` and `context` were replaced wholesale, with the digest column
> intact, were accepted and drove a complete run. **"Only digests that came from the verified
> bundle"**: `evaluation_digest` and `attestation_digest` were literal constants. All three are
> corrected in the test and the claims restated below.

The bundle commits the **same** provider factory the run uses, and the test asserts that
equality — the check 4B performs at `pipeline.py:263`, which nothing in 4C had.

**Ruling 3, implemented as an inventory assertion `[V]`.** There is no production
`VerdictCustodyPort` implementation to refuse with, so the test asserts the inventory
instead: the only implementation in the tree is `InMemoryVerdictCustody`, test-only by
revision 20 ruling 3. If a real adapter appears, the test fails and says that D5 must have
bound its endpoint, ACLs, identities, encryption and retention first. Asserting a refusal the
package does not raise would have been theatre.

> **Corrected by revision 30 — retained for the record.** "In the tree" overstated the scan,
> which covers `custody.py`'s namespace only: an adapter defined in a sibling module and never
> imported there, or a subclass of the double defined elsewhere, is not detected. It is a
> reminder, not a control, and the test now says so.

**Two limitations, recorded rather than glossed `[G]`.**

1. **The case-reproduction check has no production home.** 4B performs it inside its pipeline
   (`pipeline.py:261`); with no 4C pipeline it lives in test scaffolding, so it constrains
   nothing a future pipeline must do. When the pipeline is built, that check belongs in it —
   and this test should then assert the pipeline performs it, not perform it itself.
2. **The integration test pins less than it exercises.** Stubbing the calibration branch fails
   it; stubbing the G2b case-set reconciliation or slice 3A's provider read-path guard does
   **not**. Those are pinned by their own unit tests, and the integration test's job is the
   wiring — but it should not be mistaken for a second line of defence over the guards it
   happens to traverse.

> **Corrected by revision 30 — retained for the record.** This two-item list understated the
> gap. Re-derived against the tightened test: of the eight guards named here and below it
> detects **one** — the calibration branch. The F3 gate, `revalidate_role`, G2a, G2b,
> `write_and_verify`'s read-back comparison, slice 3A's provider read-path guard and slice
> 3B-0's endpoint check are all undetected. The file in fact traverses more than eight —
> slice 3A's `index_digest` and case-set checks, the endpoint's manifest-digest check, G1b's
> replay revalidation, `run_phase_4c_pilot` aliased to `run_pilot`, and the canonical-decimal
> grammar itself — and detects none of those either. The count understates traversal, not
> detection.

**Status.** G3 remains open by ruling and by construction. D1–D5 remain incomplete, the
custody endpoint remains unbound, real custody adapters and genuine execution remain blocked,
and no provider call, credential access or genuine calibration is permitted by this revision.

### Revision 30 (independent-review corrections to revision 29, and a defect it surfaced, 2026-09-04)

An independent adversarial review of revision 29 returned **NOT APPROVED**. Three claims in
its central `[V]` paragraph were false or overstated, one more was overstated, and its account
of what the test pins was understated. The reviewer's summary is worth recording verbatim in
substance: the blocking problem was the note, not the code — in the revision whose stated
purpose was to be narrower and more honest than a pipeline.

**Corrections `[V]`.** All four claims are annotated in place above — including limitation 2,
which revision 30 first *replaced* rather than annotated, inconsistent with the revision-19
form and with this sentence; the original text is restored with the re-derivation beneath it.
The test is tightened:

1. **The loader now recomputes.** It reads only `case_id`, `query` and `context` — the case
   file no longer carries a digest column at all — and recomputes each digest from content
   before comparing to the prepared benchmark. Four tamper shapes (query, context, case_id, a
   dropped case) are refused. Revision 29 borrowed 4B's language for a check that was not 4B's;
   4B recomputes (`workflow_fit_reference_pilot/pipeline.py:116`) and now so does this.
2. **The result is built from the run.** `evaluation_digest`, `attestation_digest` and
   `statistic_value` come from the executed run's evaluation, attestation envelope and quality
   result. `require_calibration_endpoint` is then called on the `UNDER_TEST` record, so
   slice 3B-0's rule for when a calibration has genuinely ended is exercised.
3. **The circular test is gone**, replaced by the tamper-shape test above.
4. **The inventory assertion says what it covers** — one module's namespace, not the tree.

**A real defect the integration test surfaced `[G]` — the first, and the reason to have
written it.** `contracts/calibration.py`'s module docstring already obliges slice 3 to "check
the canonical rendering of the reachable `QualityResult.value`". **No production function
performs that rendering.** The runner produces `"1.0"`; revision 16's canonical grammar forbids
a trailing fractional zero, so `CalibrationResult(statistic_value="1.0")` raises
`DECIMAL_UNPARSEABLE`. The runner therefore does **not guarantee** a canonical rendering: a run
whose mean is already canonical (`0.75`, `1`) constructs a `CalibrationResult` directly, while
one whose scorer carries a trailing zero — as the pilot fixture's `Decimal("1.0")` does —
cannot. No path works for *all* runs without the caller writing their own canonicaliser, which
is precisely the per-caller reimplementation the canonical-decimal ruling exists to prevent. The test contains a local one, clearly labelled
as exposing the gap rather than filling it. **Closing this needs a governed canonicaliser in
the pilot package, and is not commissioned here.**

**What the test is worth, stated plainly.** One of its tests does real integration work: the
first executed 3A → gated run → result → endpoint chain, and the only thing that would catch a
broken calibration branch outside the unit suites. The others are a tamper-shape test of the
loader, a namespace reminder, and a run-sourced result construction. That is a fair return for
one file; it is not a safety net, and revision 29 implied more.

**Status.** G3 remains open and untouched — a test adds no production caller. The canonical-
rendering gap above is **new and carried forward**. D1–D5 remain incomplete, the custody
endpoint remains unbound, real custody adapters and genuine execution remain blocked, and no
provider call, credential access or genuine calibration is permitted by this revision.

**Second-review corrections, recorded `[V]`.** A re-review of revision 30 returned
CONDITIONALLY APPROVED and found three note-level slips, all closed above: the
canonical-rendering paragraph overstated ("no path from a real run" — a run whose mean is
already canonical constructs directly); the ruling-3 annotation was inserted mid-paragraph,
splitting revision 29's closing sentences so they read as part of the annotation; and
limitation 2 was replaced rather than annotated while this revision claimed otherwise.

It also confirmed two things worth recording because they were reasoned about rather than
measured: `format(Decimal, "f")` never emits an exponent, and the test-local canonicaliser is
accepted by `require_canonical_decimal` for every probed value including `1E+30`, a 31-place
fraction, `-0.0` and `0.50`. And it settled the standing question — **keep the file**: tests 1
and 4 now form the only executed 3A → gated run → result → endpoint chain in the repository,
and building it surfaced the canonical-rendering defect, which is the strongest case a
cross-slice test can make for itself.

One gap it disclosed that this revision had not: the recomputed case-digest scheme agrees with
the prepared benchmark **by construction of the pilot fixtures**, not by a governed rule.
`BenchmarkManifest` constrains `case_digests` only to sorted unique 64-hex, and 4B's scheme
additionally binds the expected-answer digest. A future Phase 4C pipeline needs a **governed
case-digest scheme**; that is pre-existing and is now carried forward alongside G3 and the
canonical-rendering gap.
