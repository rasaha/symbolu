# Known Limitations

This package is intentionally scoped. The following are deliberate limitations,
not defects. The package is **not production certified** (`production_certified`
is always `False`) and is classified `PACKAGE_READY_FOR_CONTROLLED_PILOT`.

## No AI scoring / ranking / fairness model

The package does not ship an AI scoring, ranking, or fairness model. It makes no
claim of validated bias detection, fairness, or non-discrimination.

## No LLM inference

There is no LLM inference in the package. The core carries no AI/model SDK
(openai/anthropic/mistral/torch/transformers) and performs no model calls.

## No production HRIS / ATS / offer / payroll adapters

Only deterministic, offline, in-memory adapters ship. There are no production
HRIS, ATS, offer, payroll, or candidate-contact adapters. The package prepares
governed action requests and records authorization outcomes but never executes
downstream enterprise actions.

## Deterministic-only

The package operates in a deterministic simulation mode. It does not integrate
external, non-deterministic data sources or models.

## Local performance is not a production benchmark

Any timing observed from the in-memory adapters reflects local, in-memory
simulation. It is not a production benchmark and should not be used to project
production throughput or latency.

## No legal / compliance guarantees

The package does not guarantee legal compliance, fairness, non-discrimination,
employment-law satisfaction, or validated bias detection. See
[GOVERNANCE_BOUNDARIES.md](GOVERNANCE_BOUNDARIES.md).

## Not production certified

The distribution is for controlled-pilot evaluation only. See
[DEPLOYMENT.md](DEPLOYMENT.md).
