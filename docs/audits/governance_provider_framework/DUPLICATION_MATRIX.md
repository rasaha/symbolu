# Duplication Matrix — Governance Provider Framework

Audit-only. **Nothing is consolidated in this phase.** Each suspected duplicate
is classified as a *true duplicate*, an *adapter specialization*, or a
*compatibility surface*.

## 1. Already-resolved duplication (historical)

The neutral contracts (`errors`, `lifecycle`, `metadata`, `contracts/*`) were
**previously** duplicated as the framework's own definitions. The Governance
Contracts migration extracted them to `ugence_governance_contracts` and left the
framework paths as identity-preserving re-export shims. **These are not
duplicates — they are compatibility surfaces** (removal target
`governance_providers` 0.2.0). No action.

## 2. Live duplication findings

| # | Concept | Path A | Path B (and C) | Semantic similarity | API differences | Consumers | Consolidation safe now? | Correct ownership | Classification |
|---|---|---|---|---|---|---|---|---|---|
| D1 | Provider invocation record + log | `governance_providers/observability.py` (`ProviderInvocationRecord`, `ProviderInvocationLog`, `record_invocation`) | `tap_provider/observability/__init__.py` (`TapInvocationRecord`, `TapInvocationLog`); `actiongate_provider/observability.py` (`ActionGateInvocationRecord`, `ActionGateInvocationLog`) | High on the neutral core (provider_id, kind, operation, completed, outcome, trace_id, error/failure class) | Provider records add fields: TAP `mapping_version, mode, evidence_count, evidence_coverage, fingerprint, policy_version, duration_ms`; ActionGate `provider_version, mapping_version, mode, compatible, policy_version, fallback_provider_id`. Providers do **not** call `record_invocation`. | framework record: framework internals + tests; provider records: each provider's own tests | **No** — not in this phase | Neutral subset could be GC/GPF; extension fields are capability-owned | **Adapter specialization** (capability-owned superset), not a true duplicate |
| D2 | Conformance `CheckResult` dataclass | `governance_providers/conformance/common.py` (`CheckResult`) | `tap_provider/conformance/__init__.py` (`CheckResult`); `actiongate_provider/conformance/__init__.py` (`CheckResult`) | Very high — the provider `CheckResult`s are structurally identical to each other; GPF's is the same pattern | Field-for-field the two provider copies match; GPF's is used by the shared kit | provider conformance runners + tests | **No** — later, low priority | A shared conformance-report base (GPF-public or GC) | **True duplicate** (small, test-harness scaffolding) between TAP and ActionGate |
| D3 | Conformance report envelope | `governance_providers/conformance/common.py` (`ProviderConformanceReport`) | `tap_provider` (`TapConformanceReport`); `actiongate_provider` (`ActionGateConformanceReport`) | High — same `results/passed/failures/summary` shape | Only the `summary()` prefix string differs | provider tests | **No** | Shared base as above | **Adapter specialization** of the same shape |
| D4 | Health report wrapper | — (framework has no health *report*, only `ProviderHealth`) | `tap_provider/health` (`TapHealthReport`); `actiongate_provider/health` (`ActionGateHealthReport`) | Medium — both *wrap* the framework `ProviderHealth` and add provider dimensions | Each adds capability-specific dimensions (evaluator/evidence/policy vs engine/policy) | provider health checks | N/A — not a duplicate of framework | Capability-owned | **Adapter specialization** — correctly reuses `ProviderHealth` rather than redefining it |
| D5 | Provider module-seam layout | `tap_provider/**` | `actiongate_provider/**` | High structural twinning: `provider.py`, `core`, `mapping/{request,result,constraints\|controls}`, `client` (Protocol + in-process/remote), `errors` (translate_error), `health`, `observability`, `configuration` (Settings + `build_*`), `conformance`, `api`, `version` | Vocabulary differs (assertion vs action); TAP adds `fail_safe` + evidence resolution + `indeterminate_result`; TAP's `core`/`observability` are packages, ActionGate's are single modules | — | N/A — intentional parallel structure across two independent capabilities | Each capability owns its own | **Not a duplicate** — two bounded capabilities sharing a healthy convention |
| D6 | Client transport pair | `tap_provider/client` (`TapClient`, `InProcess…`, `Remote…`) | `actiongate_provider/client` (`ActionGateClient`, `InProcess…`, `Remote…`) | High pattern similarity | Vendor-specific payloads | provider internals | N/A | Capability-owned | **Not a duplicate** — vendor transport, correctly private |

## 3. What is explicitly NOT duplicated

- **Request/Result/error envelopes.** Neither provider redefines
  `AssertionGovernanceRequest/Result`, `ActionGovernanceRequest/Result`, the
  provider error taxonomy, or `ProviderDescriptor/Health/Capabilities/
  Compatibility` — all are reused from `governance_providers.api` (which re-exports
  GC). This is the load-bearing anti-duplication result: the *contracts* are
  single-sourced.
- **Registry / resolution / configuration / fingerprint.** Exist only in the
  framework; no provider or application reimplements them.
- **Native vendor vocabulary** (`tap_provider/core`, `actiongate_provider/core.py`)
  is intentionally separate per capability — not duplication of framework models.

## 4. Consolidation guidance (for a LATER phase — not now)

| Finding | Recommended future action | Change class |
|---|---|---|
| D1 | Optionally introduce a neutral `ProviderInvocationRecord` base and have providers extend it; adopt `record_invocation` in providers | MINOR (additive) |
| D2/D3 | Introduce one shared conformance-report base (GPF-public), have providers subclass | MINOR |
| D4/D5/D6 | Leave as-is; healthy parallel structure across bounded capabilities | none |

Consolidating D1–D3 is **not** required for and is **independent of** the
framework canonical-package migration. Do not consolidate during the audit or
during the migration; treat as separate, additive, contract-versioned work.
