# Agent Runtime — Migration Test Plan (Deliverable 7)

The tests proving the runtime loop and — decisively — the governance boundary. All in
`agent_runtime_migration/tests/` (39 tests, all green) + the deterministic benchmark.

Labels: `FACT`.

## Runtime behavior (`test_runtime_core.py`, 9)
`FACT`. Goal decomposition + planning (dependency-ordered); memory receives every observation;
reflection runs after each result; retries/cancellation functional (cancel stops the loop; budget
stops the loop); multi-step workflow preserves deterministic order; default planner.

## CER (`test_contracts_and_cer.py`, 13)
`FACT`. CER generation is deterministic; provenance-only change preserves identity; material change
yields a different identity; invalid/incomplete CERs fail closed (`ProposalError`); a modified
action fails binding (`assert_binding`). Plus the full control-plane boundary (PROCEED/DENY/HELD/
PENDING) against the real frozen control plane.

## Governance boundary (`test_tools_and_execution.py`, 10)
`FACT`. Runtime never emits authoritative allow/deny (it consumes a `GovernanceDecision`); governed
consequential tools cannot execute without a control-plane execution reference (DENY/HOLD/PENDING →
tool never runs, `spy.calls == 0`); PROCEED runs the tool once; the model cannot reclassify a
governed tool as local (fail closed); low-risk fast paths are policy-controlled; a governed receipt
is accepted only from the control plane; a modified action invalidates a prior decision;
observations return to memory/reflection; workflow ordering + checkpoint/restore.

## Research isolation (`test_forbidden_imports.py`, 2)
`FACT`. AST scan proves the runtime imports none of `agentic.*`, the research-signal modules, or the
duplicate governance authority; importing the package loads no `agentic.*` module. Advisory signals
(`reasoning/uncertainty.py`, `proposal/proposal_evidence.py`) expose no allow/deny.

## Compatibility (`test_compatibility.py`, 5)
`FACT`. Supported legacy workflows migrate and run; a governed legacy action routes through CER; an
unsupported legacy governed action (missing envelope) fails explicitly; deprecation warnings fire;
legacy governance authority is refused.

## Deterministic migration benchmark (`benchmark/`)
`FACT`. 10 scenarios (read-only, multi-step, Kubernetes scale, database mutation, denied, ACP hold,
execution failure, cancellation, human intervention, observe→reflect→replan). Measures per-scenario
status, governed-execution correctness, CER identity presence, trace completeness, memory updates,
and governance-boundary violations. Machine-readable results in `benchmark/results.json`.

## Old-vs-new
`FACT`/`INTERPRETATION`. The legacy runtime is NOT executed in the benchmark: its execution path
makes its own authoritative allow/deny (architecturally invalid under the frozen boundary) and its
package import pulls research code. Per the milestone, exact behavioral equivalence is not required
where the old behavior was invalid; the intended differences are recorded in `benchmark/results.json`
and `AGENT_RUNTIME_MIGRATION_RESULTS.md`.
