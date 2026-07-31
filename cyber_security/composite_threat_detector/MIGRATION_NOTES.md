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
