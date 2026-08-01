# StoryGraph Adversarial Validation & Implementation Audit

Focused adversarial validation and implementation audit of the existing
account-takeover StoryGraph vertical slice. **No new domains, no learned scoring,
no PageRank, no unknown-threat discovery, no large story library, no rewrite of the
analyzer core.** Every claim below is checked against the *actual code* and a
*passing test*, not against a design summary.

Baseline: the pre-phase slice (147 tests). This phase adds structural proofs and
adversarial coverage: **179 tests total**, all passing.

---

## 1. Code-audit matrix (claimed → actual code → test → gap)

| # | Claimed property | Actual implementation | Test | Gap / status |
|---|---|---|---|---|
| 1 | Typed graph, not a flat checklist | `storygraph.py` `Edge`/`StoryNode`/`StoryGraph`; edge kinds ORDER/SAME_ENTITY/WITHIN/RELATED_ACTORS/REQUIRES_CORROBORATION/CONTRADICTS/COVERED_BY_AUTHORIZATION | `test_storygraph*.py` | none |
| 2 | Deterministic bounded matching → decomposed vector | `match()`, `_exhaustive()` (sorted candidates, `_MAX_COMBINATIONS=4096`, `_MAX_CANDIDATES_PER_NODE=6`, greedy → `unavailable`); `RiskVector` | `test_storygraph.py`, `_v2` | none |
| 3 | Non-compensatory structural gates | `_build_match`: gate on `entity_consistency`/`ordering_consistency`/`timing_consistency`; `harmful = min(raw, threat_threshold-ε)` when gated | `test_storygraph_adversarial.py::test_full_coverage_cannot_compensate_failed_entity_gate` | none |
| 4 | Non-mutation during hypothetical evaluation | `evaluate_proposed_action`/`completion_witness` build `events + [proposed]` locally; never call `analyzer.observe()`; `ObservedEvent` is a frozen view | `..._adversarial.py::test_evaluate_does_not_record_into_ledger`, `..._input_list_unmodified` | none |
| 5 | Minimal completion witness (every element necessary) | `completion_witness`: per-event removal proofs over `witness_ids`; `minimality_verified`; `TIE_BREAK_RULE_VERSION` | `..._adversarial.py::test_witness_minimality_every_element_necessary`, `test_removing_proposed_breaks_completion` | none |
| 6 | Exact entity binding (account/device/beneficiary) | `_edge_ok` SAME_ENTITY requires non-empty equal values; matcher maximizes satisfied edges | `..._adversarial.py::test_wrong_single_entity_trips_gate_and_blocks_completion` (3 dims), `test_competing_beneficiary_binds_the_matching_event` | none |
| 7 | Ordering + timing discrimination | `_edge_ok` ORDER `coord<coord`, WITHIN `|Δ|<=max_gap`; `ordering_ambiguous` on equal coords | `..._adversarial.py::test_out_of_order_trips_ordering_gate`, `test_outside_time_window_trips_timing_gate`, `test_equal_coordinate_flagged_ordering_ambiguous` | none |
| 8 | CONTRADICTS requires *explicit* incompatibility | `Edge.incompatible_when`; `contradicts()` raises without it; `_edge_ok` fires only on `BOTH_PRESENT`/`SAME_ENTITY:<dim>`/`DIFFERENT_ENTITY:<dim>`; `StoryGraph.__post_init__` validates | `..._adversarial.py::test_contradicts_*` (4), `test_storygraph_gaps.py` | **closed this phase** — was "both present ⇒ weakened" |
| 9 | Verified legitimate coverage; self-declared covers nothing | `legitimate.py::coverage`, `_covers` (`auth.valid` required); `_merge_coverage` | `..._adversarial.py::test_self_declared_authorization_covers_nothing`, `test_wrong_account_authorization_does_not_cover`, `test_partial_recovery_leaves_transfer_uncovered` | none |
| 10 | Multiplicity / competing optimal bindings | `_exhaustive` counts equal-best bindings → `multiple_optimal_bindings` | `..._adversarial.py::test_duplicate_equivalent_candidates_report_multiple_optimal` | none |
| 11 | Evaluation binding + stale detection | `build_evaluation_binding`, `is_stale`, `_assembly_state_digest`, `_tcs_digest`; `ProposedActionResult.evaluation_binding` | `..._adversarial.py::test_result_carries_evaluation_binding`, `test_stale_detected_on_*` | **added this phase** |
| 12 | Freeze binds graphs incl. CONTRADICTS condition | `evaluation/freeze.py::current_config` story_graphs edge digest now includes `incompatible_when` | `test_storygraph_gaps.py::test_freeze_binds_story_graphs` | **closed this phase** (digest omitted the field) |
| 13 | Advisory-only alphabet; never ALLOW/DENY/execute | `_SIGNAL` maps only to `OBSERVE`/`ESCALATE`/`UNAVAILABLE`; no side-effects in the path | grep audit (below) | none |
| 14 | Unknown/unencoded patterns remain undetected | matcher has no anomaly/learning path; a graph with no matching fragments → no completion | corpus B-cases | by-design; documented |

### Advisory-alphabet grep audit

`_SIGNAL` in `storyverdict.py` maps every category to `signals.OBSERVE`,
`signals.ESCALATE`, or `signals.UNAVAILABLE`. No `ALLOW`/`DENY`/`BLOCK`/`EXECUTE`
token, no credential/trade/transfer emission, and no network/LLM/wall-clock call
exists in the authoritative StoryGraph path (`storygraph.py`, `storyverdict.py`,
`legitimate.py`, `contradictions.py`). The proposed action is inserted into a
*local list* only and never recorded (proof §4).

---

## 4. Non-mutation proof

`evaluate_proposed_action(assembly_events, proposed, graph, …)` and
`completion_witness(graph, events, proposed)`:

1. construct the hypothetical world as a **new local list** `events + [proposed]`;
2. call the pure `match()` engine on it;
3. never call `analyzer.observe()`, never touch `analyzer.ledger`, never append to
   the caller's `assembly_events` list.

`ObservedEvent` is a `@dataclass(frozen=True)`, so views cannot be mutated in place.
Verified by:

- `test_evaluate_does_not_record_into_ledger` — after evaluation, the live
  assembly's `seen_event_ids` and `instances` are byte-for-byte unchanged, and the
  proposed id is absent from the ledger.
- `test_evaluation_is_deterministic_and_input_list_unmodified` — the caller's list
  keeps length 3 and equal contents; two evaluations produce identical
  `verdict_digest` and `certificate_digest`.
- `test_observed_events_stable_across_repeated_reads` — repeated reads of a live
  assembly return identical event views.

---

## 5. Witness minimality proof

The completion witness proves **necessity of every witness element**, not only the
proposed action. `completion_witness` iterates `witness_ids = sorted(witness
bindings ∪ {proposed})`; for each it removes that single event, re-runs `match()`,
and records whether completion broke and *why* (`missing_required`, `gate:…`, or
`lost_binding:…`). `minimality_verified` is `True` only if **removing any element
breaks completion**. A frozen, versioned tie-break
(`TIE_BREAK_RULE_VERSION = "ctd.witness.tiebreak/1.0.0"`) documents the
deterministic selection among equally-minimal witnesses (fewest events → earliest
complete span → highest mandatory-edge satisfaction → lexicographic id), which the
matcher realizes via its sorted candidate order.

Verified by `test_witness_minimality_every_element_necessary` (each removal proof
has `broke_completion=True`, `still_complete=False`, `unsatisfied != "none"`) and
`test_removing_proposed_breaks_completion`.

---

## 8. Corrected CONTRADICTS semantics

Prior behavior treated *both nodes present* as sufficient to weaken the harmful
story. Corrected: a CONTRADICTS edge now carries an explicit
`incompatible_when ∈ {BOTH_PRESENT, SAME_ENTITY:<dim>, DIFFERENT_ENTITY:<dim>}`.
`contradicts()` raises `ValueError` without one; `StoryGraph.__post_init__` rejects
a graph containing an unconditioned CONTRADICTS edge; `_edge_ok` fires the edge
*only* when the declared condition holds (an empty condition returns `False`). This
makes "both present" insufficient unless the two node states are *declared* mutually
incompatible. When fired, the record states `weakens=HARMFUL`, `severity=decisive`,
`resolution_status=unresolved`, and the proposed-action classifier returns
`AMBIGUOUS_COMPETING_STORIES`.

---

## 16. Metrics (strict evidence labels)

Source: `evaluation/story_corpus.py` (`evaluate_corpus`), 9 hand-authored labeled
cases for the account-takeover slice. **These are encoded-pattern *structural
separation* rates on a hand-built corpus — NOT fraud-detection accuracy on real
traffic.**

| Metric | Value | Meaning |
|---|---|---|
| `true_completion_detection_rate` | 1.00 | true assemblies (incl. low-and-slow within window) reach WOULD_COMPLETE |
| `benign_false_completion_rate` | 0.00 | no benign look-alike reaches WOULD_COMPLETE |
| `evasion_false_completion_rate` | 0.00 | wrong beneficiary/device/account evasions do not complete |
| `benign_escalate_advisory_rate` | 0.75 | **honest limitation** — benign look-alikes that still reach an ESCALATE advisory (not completion) |

**Known limitation, surfaced not hidden.** Three of four benign look-alikes reach
an ESCALATE-level *advisory* category (never WOULD_COMPLETE):
`B1` is verified-partial-coverage (the beneficiary-add node is genuinely uncovered,
so escalating for review is appropriate); `B3`/`B4` reach
`THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT` because, when the completion node is
absent, the discriminating SAME_ENTITY/ORDER/WITHIN edges are *not evaluable* and
default to a satisfied fraction of 1.0, inflating the consistency dimensions. This
is a property of the frozen scoring; changing it would rewrite the analyzer core,
which this phase explicitly does not do. It is reported as
`benign_escalate_advisory_rate` and asserted by
`test_benign_escalation_limitation_is_reported_not_hidden`. The strong
completion-gating claim (WOULD_COMPLETE) is unaffected: benign and evasive cases
never reach it.

Per-case detail is in `evaluate_corpus()["per_case"]` and reproduced by the
`tests/test_story_corpus.py` suite.

---

## 17. Verdict

**CONTINUE — StoryGraph adversarial validation passed.**

The account-takeover slice remains structurally correct, deterministic, and
non-mutating under hypothetical evaluation; resists false entity binding, wrong
ordering, and out-of-window timing via non-compensatory gates; produces a truly
minimal completion witness with per-element removal proofs and a versioned
tie-break; treats CONTRADICTS as an explicit-incompatibility relation; distinguishes
verified from self-declared legitimate context; reports competing optimal bindings;
and binds each finding to its exact inputs with stale-detection. One honest
limitation (benign partial look-alikes can reach an ESCALATE *advisory*, never a
completion) is measured and surfaced.

### Explicit non-claims

This document does **not** assert, and this phase does not establish: *Production
ready*, *Enterprise validated*, *Fraud detection validated*, *Enforcement ready*, or
*Novel algorithm proven*. The slice is advisory, known-pattern-only, single-domain,
and evaluated on a small hand-built corpus. Unknown or unencoded patterns remain
explicitly undetected.

---

## 18. Completion report

- Original suite: **147 tests** — still passing.
- New/changed this phase:
  - `tests/test_storygraph_adversarial.py` — **25** tests (§4–§10, §13, §14).
  - `tests/test_story_corpus.py` — **7** tests (§11, §12, §16).
  - `tests/test_storygraph_gaps.py` — 2 CONTRADICTS calls updated to the required
    3-arg signature.
- Total: **179 tests passing.**
- Code changes: `storygraph.py` (CONTRADICTS `incompatible_when`, validation, fired
  semantics, enriched records), `storyverdict.py` (per-event witness removal proofs,
  `TIE_BREAK_RULE_VERSION`, evaluation binding + `is_stale`, `evaluation_binding`
  wired into `ProposedActionResult`), `evaluation/freeze.py` (edge digest now binds
  `incompatible_when`), new `evaluation/story_corpus.py` (labeled corpus + metrics).
- Interfaces preserved: flat-recipe compatibility (`from_recipe`), StoryGraph public
  API, deterministic matching, trusted-provider model, audit/replay/freeze, advisory
  signal alphabet. No ALLOW/DENY/BLOCK/credential/transfer emission was added.
