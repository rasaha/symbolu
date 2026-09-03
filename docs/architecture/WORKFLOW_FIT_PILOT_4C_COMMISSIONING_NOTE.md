# Phase 4C — First Genuine Research-Only Workflow-Fit Pilot: Commissioning Note and Ballot

**Revision 11.** Status: documentation only. **Nothing in this note authorises a
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
confirmatory comparison, coverage report or success summary**. Its only
output is a candidate threshold, which is preregistered before any
confirmatory repetition runs.

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
| D3 | `score.unit`; arithmetic-mean aggregation |
| D3 | threshold sourced externally where a defensible external basis exists; otherwise one separate calibration run establishes a candidate threshold before confirmatory execution |
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
| codes | seven additions selected (§4) |
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

#### CONDITIONAL OWNER SELECTION — NOT YET FINAL

| Ballot | Selection | Condition |
|---|---|---|
| D2 | evaluator kind `PROGRAMMATIC` | only if the eventual benchmark supports objective, deterministic programmatic scoring; the label `PROGRAMMATIC` does not itself prove determinism `[V]` (`EvaluatorKind` is a declared kind; no contract verifies determinism). Final selection awaits the benchmark and scoring procedure |
| D4 | 3 confirmatory repetitions, or 1 calibration + 3 confirmatory | which branch applies depends on whether a defensible external threshold basis exists (D3) |
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
| D2 | benchmark author; approver, distinct; benchmark id and version; case list and expected answers; benchmark-custody location; evaluator identity and version; scoring procedure text; separation declaration reference |
| D3 | `profile.json`; `task_class.json`; consequence class; evidence-admission reference where the class is `MATERIAL` or `SEVERE` with threshold-based sufficiency `[V]`; population definition; representativeness statement; threshold literal and its basis |
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
stage code; (iv) the **seven** refusal codes the owner selected in revision 10
— `PROVIDER_IDENTITY_UNVERIFIED`, `RETENTION_WRITE_FAILED`,
`RETENTION_VERIFY_FAILED`, `EVALUATION_FAILED`, `COMMITMENT_ALREADY_SPENT`,
`COMMITMENT_REGISTRY_UNAVAILABLE`, `WORKFLOW_BUDGET_EXHAUSTED`. The three
stage codes were owner-ratified in revision 4; revision 10 ratifies the
remaining four names and the seven-code accounting. **The enum has not
changed**: `errors.py` has **33** members today and contains none of the seven
`[V]`; a future commissioned vocabulary would have **40**. `RETENTION_FAILED`
stays withdrawn. (v) only
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
