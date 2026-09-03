# Phase 4C — First Genuine Research-Only Workflow-Fit Pilot: Commissioning Note and Ballot

**Status: documentation only. Nothing in this note authorises a provider call.**
Until every ballot item below is ratified by the owner, no code path in this
repository may contact a provider, hold a credential, or run a real workflow
behind the pilot boundary. Every output of a ratified 4C run remains
`RESEARCH_ONLY` with `preregistration_status = DECLARED_UNVERIFIED`. No
benchmark-derived advisor behaviour, no `BENCHMARK_DERIVED` label and no
governed-contract change is in scope.

**The load-bearing question.** What makes a run a genuine research pilot
rather than a mechanism exercise? Not the provider. A run is a pilot only if
its benchmark is demonstrably representative of the declared task class, its
inputs are owner-decided and preregistered, and its underlying artifacts are
retained where an independent party can re-evaluate them later. Phase 4B
proved the mechanism (`experiments/workflow_fit_reference_pilot/README.md`);
4C supplies the five things the mechanism cannot decide for itself.

## 1. What already exists `[V]`

| Need | Provided by | Reference |
|---|---|---|
| Real workflows behind the gateway stub | `HarnessWorkflowExecutor(max_llm_calls)` | `experiments/workflow_fit_study/pilot_executor.py` |
| Separate-process capture, every provider attempt recorded including `EXCEPTION`/`TIMEOUT`; `llm_calls` = count of capture records, so a retry is never hidden | `BoundaryServer._call`, `recompute_telemetry` | `boundary/server.py`, `boundary/attestation.py` (spec §4.2–4.3, A14, A16a) |
| Provider injected only by dotted path, imported once inside the boundary process | `boundary/entry.py` (`--provider-factory`) | spec §4.1, A30 |
| Typed inputs with no defaults, credential-like keys refused | `loaders.py` | 4B |
| Manifest preparation, run, fail-closed verify, replay without provider | `pipeline.py`, `cli.py` | 4B |
| Digests-only bundle; prompts, responses and expected answers never enter it | `bundle.py`; 4B test `test_expected_answers_prompts_and_responses_never_enter_a_bundle` | 4B |
| Zero-call runs attested; incomplete runs `INCONCLUSIVE` | rows A14, A14a | spec §11 |

## 2. What the tooling cannot enforce today `[V]`

These are not defects in 4A/4B; they are controls a genuine pilot needs that
no ratified contract covers. Each becomes an **experiment-side control**
under `experiments/`, or, where it must live inside the boundary process, an
explicitly balloted 4A amendment. None may be added silently.

| Control | Current state | Where it must live |
|---|---|---|
| Immutable model version, region, decoding parameters | `ProviderPort.complete(prompt)` carries no parameters; nothing pins them | provider factory, with the pinned values digested into `preparation.json` `[R]` |
| Credential | boundary inherits the runner's environment copy | one named variable read only by the factory inside the boundary process; the runner must strip it from its own environment before writing any artifact `[R]` |
| Spending and call ceilings | per-workflow `max_llm_calls` only; no run-level or monetary ceiling | experiment-side counter in the executor plus a boundary-side hard stop (4A amendment, `[R]`) |
| Retry policy | a failed call raises into the workflow; whatever the workflow does next is captured | policy declared in the scenario document; every retry stays a captured attempt `[V]` |
| Concurrency | runner is sequential, one connection | keep sequential unless balloted |
| Repetitions and stochastic control | no seed or repetition concept anywhere | scenario document: repetitions per case, seed or "no seed available" declaration, temperature pinned `[R]` |
| Plaintext retention | prompt and response text exist transiently in the boundary and are digested; no sink | append-only retention sink written by the boundary process (4A amendment, `[R]`) |
| Preregistration record | manifest digest computed by `prepare`; nowhere recorded before execution | owner records the digest out-of-band before `run` `[R]` |

## 3. Ballot — five owner decisions `[R]`

**D1. Provider identity.** Provider, immutable model identifier and version,
region, the provider's data-retention policy as it applies to the run, the
full decoding-parameter set, and the single environment-variable name the
boundary-side factory reads. The credential never appears in arguments,
manifests, logs, bundles or this repository. *Recommendation:* pin every
value in `provider.json` (extended by ballot, not by default) and digest it
into `preparation.json`.

**D2. Benchmark custody.** Who authors the cases, who approves the expected
answers, where plaintext answers are stored, and who may read them. The case
digest is an integrity commitment only: it does not conceal an easily guessed
answer. *Recommendation:* owner authors, a second named person approves, the
plaintext lives in the D5 retention location, and Git holds digests only.

**D3. Task-class validity.** A written statement of why the benchmark
represents the declared task class, and the quality threshold, unit,
aggregation and resource dimensions declared as **pilot configuration** in
`task_class.json` and `aggregation.json`, not as architectural defaults.
*Recommendation:* at least one structural token per case traced to the
profile, and an explicit statement of what the benchmark does not cover.

**D4. Experimental design.** Repetitions per case, seed or stochastic-control
policy, concurrency, run-level call ceiling, spending ceiling, stop
conditions and retry behaviour. Every retry is a captured provider attempt
and counts in `llm_calls`. *Recommendation:* sequential execution, a
boundary-side hard stop at the call ceiling, and `INCONCLUSIVE` on any
ceiling breach.

**D5. Preregistration and evidence retention.** The manifest digest is
recorded by the owner before execution, in a location and form named here.
An append-only location outside Git retains prompts, responses and expected
answers with access restricted to named persons. Git keeps their digests and
the governed evidence objects. Digest-only evidence is insufficient for later
independent re-evaluation. *Recommendation:* the boundary writes the
retention records itself, so the runner never sees plaintext it did not send.

## 4. What ratification would commission `[I]`

Only after all five are ratified: a boundary-side provider factory reading
the D1 variable; a scenario document carrying D3/D4 configuration; the two
4A amendments named in §2 (hard stop, retention sink), each with its own
acceptance rows and a spec §11 record; and one preregistered run. The
readiness gate in `.github/workflows/workflow-fit-pilot-ci.yml` stays
provider-free.

## 5. Explicitly excluded

Provider calls before ratification; any credential in the repository;
advisor changes from pilot results; readiness composites; production
eligibility, approval or configuration mutation; TEV integration; any claim
that a run measures reasoning quality beyond the declared benchmark.
