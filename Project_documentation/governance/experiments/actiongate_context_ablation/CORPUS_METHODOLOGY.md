# CORPUS_METHODOLOGY

How the naturalistic corpus was built and evaluated. **This study uses public
(repository-derived) and authored naturalistic data, NOT confidential customer
operational data.** No result can or does emit `REAL_CUSTOMER_VALIDATED`.

## Two partitions

### A. PUBLIC_NATURALISTIC_CORPUS (repository-derived)
Every item is adapted from material that already exists in the `rasaha/symbolu`
repository — it was **not** authored for this experiment. Sources include:

- GKE manifests: `deploy/gke/deployment.yaml`, `deploy/gke/rbac.yaml`
- CI workflows: `.github/workflows/pipeline-ci.yml`, `.github/workflows/backbone-ci.yml`
- The frozen policy ruleset: `cyber_security/action_gate_reference/action_gate_ref/policy.py` (R1, R3, R5, R6)
- Gateway/k8s/MCP demo scenarios: `cyber_security/action_gateway/demos/scenarios.py`, `cyber_security/action_gateway_k8s/demos/scenarios.py`, `cyber_security/action_gateway_mcp/action_gateway_mcp/registry.py`
- Operational runbooks: `CTM_plus/Bench/scripts/*RUNBOOK.md`

Adaptation transforms a manifest / policy rule / demo scenario into an ActionGate
request context. Only field names and short structural excerpts are used — no
copying of large copyrighted text. Each item's exact source path, license
(`repo-internal`), and adaptation are recorded in `corpus/manifest.json` and
`PROVENANCE_RECORD.md`.

### B. AUTHORED_REALISTIC_CORPUS (independently authored)
Realistic enterprise scenarios written to resemble genuine change contexts, **not
constructed to force a verdict**. Each contains a realistic mixture of request /
justification / current state / approval / policy excerpt / rollback / simulation /
logs / irrelevant history / duplicated and stale facts. Clearly labelled authored;
not customer data.

## Coverage (this build)

- **77** contexts (42 public, 35 authored) — exceeds the 75 / 40 / 35 minimums.
- **11** domains (kubernetes, terraform, cicd, iam, secrets, network, database,
  monitoring, storage, payments, repo) — exceeds the 5 minimum.
- **16** action types — exceeds the 10 minimum.
- **3** structure families: `prose`, `prose_tables`, `structured` (JSON/YAML/logs).
- Realistic filler (justification, history, logs, stale notes) is included on
  purpose, so critical fractions come out realistically low rather than dense.

## Construction

Contexts are materialized from compact specs (`corpus/public/scenarios.py`,
`corpus/authored/scenarios.py`) through an action-type **core** library
(`corpus/core.py`) that emits the critical spans + base request, plus a filler
library. Two phrasing modes per core: *recognized* (DEV/VALIDATION, keywords the
realistic extractor knows) and *paraphrased* (HELDOUT, wording it does not) — the
oracle mapping is identical in both, so held-out true criticality is unchanged and
only realistic-extractor behaviour differs.

## Anti-leakage splits

- `DEV` / `VALIDATION` / `HELDOUT_TEST`, split by scenario/template family.
- Each `template_family` uses a distinct target/service per split, so no
  near-duplicate template crosses splits (checked by content hash in tests).
- Both partitions appear in the held-out split.
- The extractor and P0 detector are **not** tuned on held-out contexts; held-out
  is run with interaction ablation disabled (`dev=False`).

## Extraction & ablation

Both extraction modes run against the **real** gate (`STRUCTURED_ORACLE_EXTRACTOR`
for true opportunity, `REALISTIC_EXTRACTOR` for deployable feasibility), and the
gap is reported. All five ablation modes run (single / group / redundancy-set /
linked-pair / limited-interaction); interaction modes are not skipped on
DEV/VALIDATION.

## Metrics & verdicts

Metrics are reported per partition, per domain, per action type, and combined,
with bootstrap 95% CIs (fixed seed, deterministic). Domain heterogeneity is
**not** averaged away. The preregistered thresholds (PREREGISTRATION.md) are
applied unchanged. Naturalistic partitions may emit
`PUBLIC_/AUTHORED_CORPUS_OPPORTUNITY_SUPPORTED`, a specific failure label, or
`MIXED_BY_DOMAIN` — never `REAL_CUSTOMER_VALIDATED`.
