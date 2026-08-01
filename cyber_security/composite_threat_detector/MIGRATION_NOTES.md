# Migration Notes — from the correlation-only prototype (v1 → v2)

The first version was a correlation-grouped recipe-matching prototype
("composite-threat / crime-story detector"). This version evolves it into the
**Composite Capability & Sequence-Risk Analyzer** while preserving the
deterministic core and the firearm/exfiltration illustrations.

## What is preserved

- Deterministic, stdlib-only core; SHA-256 finding digests; replayable.
- The firearm and exfiltration illustrations still run
  (`cli demo firearm|exfiltration`).
- `CompositeThreatMonitor(ontology).observe(event)` still works — it is now a
  **deprecated facade** over `SequenceRiskAnalyzer`, grouping by `by_correlation`
  to match the old single-correlation behavior.

## Breaking changes (documented)

| Area | v1 | v2 |
|------|----|----|
| Primary class | `CompositeThreatMonitor` | `SequenceRiskAnalyzer` (facade retained) |
| Grouping | `correlation_id` only | `assembly_key` from configurable entity specs (§4) |
| Windowing | `window_actions` count window (wrongly described as stopping low-and-slow) | multi-timescale ledger + decay; persistent capability retained (§3) |
| Signals | `OBSERVE`/`ESCALATE` | `OBSERVE`/`ESCALATE`/`UNAVAILABLE`; forbidden authorization signals enforced |
| Finding shape | `story` dict (dramatic headline) | rich `Finding` (§9); concise, non-dramatic text |
| Recipe | required/optional only | full constraint schema (`RECIPE_SCHEMA.md`) |
| Evidence producer name | `composite_threat_detector` | `composite_capability_sequence_risk_analyzer` |
| Removed | `monitor.py` | replaced by `analyzer.py` |

The old `window_actions` kwarg on the facade is mapped onto the transient-decay
half-life so the *documented* behavior (persistent capability is retained across
any window) holds; it no longer deletes early fragments by count.

## Framing changes

External framing "crime-story / crime reconstruction / criminal narrative /
general composite-intent detector" is removed. The system does **not** infer
arbitrary criminal intent; it detects assembly of *encoded* capability recipes and
emits advisory evidence. See the product statement in the spec.

## Upgrade guidance

- Replace `CompositeThreatMonitor(ont)` with
  `SequenceRiskAnalyzer(ont, specs=(BY_CASE, BY_ACTOR))` and choose specs suited to
  your grouping needs.
- Consume `finding.signal` (advisory) and bind consequences via `policy.py` — do
  not treat any analyzer output as an authorization.
- If you relied on `finding.story["headline"]`, use `finding.explanation` and the
  structured `present_fragments` / `missing_fragments` fields instead.

## Phase 2 (shadow-mode readiness) schema changes

| Area | Before | After |
|------|--------|-------|
| Benign neutralization | event-embedded `approval` accepted (self-declared) | requires a **verified** authorization from a `ProviderRegistry`; self-declared purpose never neutralizes (§3/§4) |
| `Finding` fields | — | added `purpose`, `recipe_version_binding`, `lifecycle`, `raw_evidence_digest`, `shadow_mode`; `ordering_status` now includes `clock_status` |
| `Recipe` | — | added `permit_ambiguous_ordering` (default `False`, fail-safe) |
| `StateLimits` | 3 caps | added `max_assemblies_per_actor`, `max_candidate_linkages_per_event`, `max_recipe_evaluations`, `max_benign_records_per_assembly`, `max_replay_backlog` (defaults high → no behavior change) |
| `PolicyBinding` | binding consequence | added `shadow` (default `True`): computes consequence but `enforced=False` |
| New modules | — | `providers`, `purpose`, `ordering`, `audit`, `governance`, `replay`; `evaluation/{corpus,review}` |
| Removed | — | none |

**Justified test migrations (2).** `test_03_authorized_security_test_qualified`
and `test_16_valid_approval_neutralizes` now pass a trusted `ProviderRegistry`
fixture, because self-declared approvals no longer neutralize. A new test
(`test_16b`) asserts the same claim *without* a provider does **not** neutralize.
All other original tests remain unchanged and green.

**Backward compatibility.** `SequenceRiskAnalyzer(...)` with no `providers` runs
exactly as before except that event-embedded approvals no longer neutralize
(they are treated as unverified claims). The `CompositeThreatMonitor` facade,
`observe()`, `standing_findings()`, `load_ontology()`, and the demos are
unchanged. Shadow mode is the default; nothing enforces.

## Phase 3 (historical-replay readiness) schema changes

| Area | Change |
|------|--------|
| `AuthorizationQuery` | added `activity_start`, `expected_provider_version` |
| Provider statuses | added REVOKED/SUPERSEDED/STALE/EXPIRED/INVALID_SIGNATURE/UNVERIFIABLE/VERSION_MISMATCH/MODIFIED_AFTER_ACTIVITY/NOT_YET_INGESTED/PROVIDER_UNAVAILABLE; `ProviderRegistry.verify_all` + `RegistryResult`; `FailingProvider`, `ProviderUnavailable` |
| `FixtureProvider` records | new optional keys: `revoked`, `superseded_by`, `stale`, `signature`, `provider_version_required`, `unverifiable`, `modified_at`, `available_from`; `available=` flag |
| `PurposeAssessment` | added `provider_unavailable`, `scope_mismatch_fields`; new statuses (REVOKED/SUPERSEDED/STALE/INVALID/PROVIDER_UNAVAILABLE); conflicting/duplicate → AMBIGUOUS |
| `StateLimits` | added `evict_on_pressure` (default `False`); ledger gains priority-retention eviction + `AddResult.evicted` |
| `SequenceRiskAnalyzer` | added `audit=` param (in-memory or `DurableAuditLog`); appends one `INGEST` record per event; `report.evictions`; module `recover_from_audit()` and `.reconstruct()` |
| New modules | `durable_audit.py`, and `evaluation/{corpus_gen,freeze,benchmark,alerts,review_sim,readiness}.py`; `replay.py` K8s adapter |
| `replay.py` | `K8sAuditReplayAdapter`, `data_quality_report`, richer contract |
| `PolicyBinding` | `WOULD_*` shadow semantics already covered by `shadow=True` (`enforced=False`) |

**No breaking changes to existing tests.** All 62 phase-2 tests remain green; the
new failure-mode semantics are additive (event-embedded approvals were already
non-neutralizing without a provider since phase 2). Recovery model is documented
as *recomputed state from durable event replay*.

## Story-graph layer (additive; no breaking changes)

New modules `storygraph.py`, `storyverdict.py`, `stories.py`, `financial.py`,
`story_bridge.py` and a `cli story` command. This layer is **entirely additive** —
the default `SequenceRiskAnalyzer.observe()` path, all findings, and every prior
test are unchanged (110 → 126 tests). It reads an assembly's active instances and
the purpose/providers verdict through `story_bridge`; it does not alter ingestion,
the ledger, or recipe matching. Story verdicts are advisory (`OBSERVE`/`ESCALATE`
only). See `STORY_GRAPH_SPEC.md`.

### Story-graph v2 (additive; 126 → 138 tests)

New modules `legitimate.py` (verified counter-story + per-node coverage) and
`contradictions.py` (typed contradiction enum). `storygraph.py` gains matcher
`unavailable`/`ordering_ambiguous`/`multiple_optimal_bindings`, edge-name aliases
(`before`/`within_time`/`same_account`/`same_device`/`same_beneficiary`/
`same_destination`/`related_actor`), and `from_recipe()` (flat-recipe → graph).
`storyverdict.py` gains the canonical taxonomy (old names kept as aliases so the
prior 16 story tests pass unchanged), `completion_witness()` (minimal deterministic
certificate), and `evaluate_proposed_action()` (the pre-commit dual-story entry
point). `stories.py` adds `ACCOUNT_RECOVERY_STORY` / `BANK_ASSISTED_TRANSFER_STORY`.
Still additive: the analyzer core is untouched; all signals remain advisory.

## Sanitized-enterprise-replay readiness (account-takeover slice)

Additive, StoryGraph frozen. `policypack/replay.py` findings/report now carry a
`version_binding` (graph structure digest + matcher/partial-policy/witness/schema/
compiler versions) so a replay result is bound to the exact algorithm, closing a
digest-audit gap; a workflow with an execution receipt is labeled `POST_HOC_ONLY`.
`policypack/replay_gates.py` pre-registers the R1–R9 acceptance gates + data-quality
minimums (sealed digest). `replay_intake/` is the customer data-intake package
(manifest/record/mapping templates, redaction + secure-handoff guidance). No sanitized
enterprise dataset was available, so historical replay is NOT claimed complete — see
`SANITIZED_ENTERPRISE_REPLAY_REPORT.md` (verdict: STOP — sanitized enterprise replay
data required). Analyzer core untouched; all signals remain advisory.
