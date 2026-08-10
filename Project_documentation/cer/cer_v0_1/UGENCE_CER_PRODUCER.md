# Ugence Native CER Producer (Deliverable 4)

`cer_v0_1/producers/ugence.py`. Grounded in the implemented, tested producer.

Labels: `FACT` · `RECOMMENDATION`.

## What it owns / does not own
`FACT`. `UgenceCERProducer.propose(req)` runs a real runtime code path — `_understand_goal → _plan → _select_tool → emit CER` — and returns a CER V0.1 **before any execution**. It:
- OWNS: goal understanding, planning, tool selection, proposal generation (and, post-execution, observation/reflection — `observation.py`).
- Does NOT own: authorization, operational safety, execution eligibility, execution tokens. It never calls the gate, never mints a token, never executes the tool.

## Governed mode
`FACT`. `governed_mode=True` (default): the producer only proposes; no governed action executes directly from the producer. A compatibility (ungoverned) path is kept separate and is not exercised on the governed path. In this milestone the governed path is the only one used.

## Identity vs provenance
`FACT`. The identity block comes from the shared `ActuationRequest.identity_block()` (target, replicas, authority, external-state binding, policy, reversibility). The producer stamps **Ugence provenance** (`runtime=ugence-agent-runtime`, `model=mistral-cg`, `planner=ugence.deterministic.htn`) and its **own objective prose** ("raise availability of deployment protected/web from 1 to 3 replicas") — all non-identity.

## Proven result
`FACT` (Stage-3 run): Ugence's CER digest = `3cef1b0f767e2e3e…` — **identical** to the LangGraph adapter's digest for the same actuation, despite different provenance/objective. Deterministic across reruns.
