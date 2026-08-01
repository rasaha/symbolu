# StoryGraph Partial-Match Correction — Run 2 Validation

This phase preserves the prior failed frozen result (Run 1) and corrects the
StoryGraph's **partial-match semantics**. It does **not** add StoryGraph domains,
PageRank, ML scoring, probabilistic intent inference, or unknown-pattern discovery.

- **Prior evidence:** `STORY_GRAPH_EVIDENCE_LEDGER.md` + `evaluation/prior_runs.py`
  (Run 1 @ `78911a9f`, corrected verdict *incomplete*, preserved verbatim).
- **This run:** matcher semantics `ctd.storygraph.matcher/2.0.0`, schema
  `ctd.storygraph/1.1.0`, partial-escalation policy `ctd.partial_escalation/1.0.0`.
- **Freeze digest (Run 2, final profile):**
  `sha-256:ed63bc9ba3f7636548360ecfb7d3cec6426fc02c884734a861a1f8347055c3da`
  (≠ Run 1's `sha-256:318e321…` — a distinct frozen version, never silently reused).

## The defect (Run 1) and the fix (Run 2)

Run 1 escalated three of four benign look-alikes. Root cause: the per-dimension
consistency fraction defaulted to **1.0 when zero edges were evaluable**, so an
absent completion node (making the discriminating edges non-evaluable) yielded a
high `harmful_score` and a `THREAT_CONSISTENT` escalation built entirely from
**untested** relationships.

The correction makes non-evaluability explicit and requires positive evidence:

1. **Explicit edge states (§3, §4).** Every edge is `SATISFIED` / `FAILED` /
   `NOT_EVALUABLE` / `AMBIGUOUS` (`storygraph._edge_state`). A missing endpoint or
   missing entity → `NOT_EVALUABLE`, never silently satisfied. Each match reports
   `edge_results`, `satisfied_edges`, `failed_edges`, `not_evaluable_edges`,
   `ambiguous_edges` with full per-edge detail.
2. **Honest dimensions (§5).** `DimensionResult` reports
   `satisfied/failed/not_evaluable/ambiguous/applicable` counts + a `status`
   (`SATISFIED/FAILED/PARTIAL/NOT_EVALUABLE/AMBIGUOUS/NOT_APPLICABLE`) + an
   `evaluable_ratio` computed **only over evaluable edges** (`None` when none are).
   The scalar consistency is the evaluable ratio or `0.0` — **never 1.0 on a zero
   denominator**. `harmful_score` excludes `NOT_APPLICABLE` dimensions and gives
   `NOT_EVALUABLE` dimensions zero positive weight.
3. **Non-compensatory gates (§6).** A structural gate fires only on a *genuinely
   evaluated* failure. A mandatory edge that is bound but not satisfied
   (`FAILED`/`AMBIGUOUS`/`NOT_EVALUABLE`) sets `mandatory_unsatisfied` and blocks
   completion — a non-evaluable completion edge can never count as satisfied.
4. **Positive-evidence partial escalation (§7).** The frozen
   `PartialEscalationPolicy` requires required-node coverage ≥ floor, ≥1
   **discriminating** mandatory edge actually evaluated *and satisfied*, no
   mandatory failure, and completion-proximity or corroboration evidence.
   `escalation_eligible` gates the `THREAT_CONSISTENT` verdict. Absence of a benign
   explanation is never, by itself, harmful evidence.
5. **Discriminating metadata (§8).** ATO nodes carry `specificity_class`
   (COMMON vs DISCRIMINATING); edges carry `is_discriminating`. A password reset /
   new device is COMMON; the beneficiary/device binding, the bounded window, and the
   reset→transfer order are DISCRIMINATING.

Exact completion, verified-context handling, determinism, and non-mutation are
unchanged.

## Metrics (full corpus, strict evidence labels)

**Encoded-pattern structural separation on a hand-built corpus for ONE
account-takeover StoryGraph — NOT fraud-detection accuracy on real traffic.**
Corpus: 108 cases (60 benign across 20 families, 48 harmful/evasive across 16
families), 3 deterministic variants each.

| Metric | Run 1 | Run 2 |
|---|---|---|
| encoded completion detection | 1.00 | **1.00** |
| benign false completion | 0.00 | **0.00** |
| evasion false completion | 0.00 | **0.00** |
| benign ESCALATE (advisory) | **0.75** | **0.00** |
| benign THREAT_CONSISTENT (the defect) | — | **0.00** |
| witness minimality (canonical) | — | 1.00 |
| duplicate witness non-minimal correctly reported | — | 1.00 |
| deterministic replay | — | 1.00 |
| hypothetical non-mutation | — | 1.00 |

Structural: edge states across the corpus — SATISFIED 453, FAILED 12,
**NOT_EVALUABLE 399**, AMBIGUOUS 0 (non-evaluable rate 0.46 — partial stories
genuinely leave discriminators untested rather than assuming them). Operational
(synthetic): mean candidate bindings 1.25 (p95 2), mean witness size 5.0,
measured escalations 305 per 1000 corpus cases.

**NOT RUN** (require real traffic / a live queue, not synthesized here):
duplicate-review rate, alerts per 1000 real events, review items per tenant-day.

## Splits and frozen final run (§13)

Deterministic split by case-id digest — dev 39 / calibration 38 / final 31.
Thresholds were pre-registered (`PREREGISTERED_GATES`) before the frozen run.
`story_corpus_v2.run_final_split(freeze)` calls `freeze.require_frozen(official=True)`
first and **refuses** if the corpus, graph, matcher semantics, partial policy, or
gates changed. Final-split result: all pre-registered gates pass.

## Acceptance gates (§15) — all satisfied

encoded completion = 1.0 ≥ 1.0 · benign false completion = 0.0 ≤ 0.0 · evasion
false completion = 0.0 ≤ 0.0 · benign escalate = 0.0 ≤ 0.10 · benign
threat-consistent = 0.0 ≤ 0.0 · canonical witness minimality = 1.0 · duplicate
non-minimal reported = 1.0 · deterministic replay = 1.0 · non-mutation = 1.0.

## Verdict

**CONTINUE — StoryGraph adversarial validation passed.**

All required conditions hold: exact completion detection is correct; benign false
completion and advisory escalation are below the frozen thresholds; missing
endpoints are reported `NOT_EVALUABLE`; partial stories require positive
discriminating evidence before escalation; mandatory constraints are
non-compensatory; trusted-context failures do not silently neutralize; hypothetical
evaluation is non-mutating; replay is deterministic; final-evaluation integrity
holds.

### Explicit non-claims

Not asserted and not established: *Production ready*, *Enterprise validated*,
*Fraud detection validated*, *Enforcement ready*, *Novel algorithm proven*. Passing
the frozen evaluation establishes **synthetic robustness for one account-takeover
StoryGraph** — not enterprise fraud accuracy or enforcement readiness. Unknown /
unencoded sequences remain explicitly undetected (the `unknown_unencoded_sequence`
family stays `NO_MATERIAL_PATTERN` / OBSERVE).

## Migration (§11)

Findings created under Run 1 remain reconstructable from commit `78911a9f` and the
`ctd.storygraph/1.0.0` schema. Run-2 findings carry
`matcher_semantics_version = ctd.storygraph.matcher/2.0.0` on every `StoryMatch`;
consumers should branch on that field. The Run-1 frozen hashes/metrics are retained
in `evaluation/prior_runs.py` and asserted by `test_prior_run_preserved`.

## Completion report

- **Files added:** `evaluation/story_corpus_v2.py`, `evaluation/prior_runs.py`,
  `STORY_GRAPH_EVIDENCE_LEDGER.md`, `STORY_GRAPH_PARTIAL_MATCH_VALIDATION.md`,
  `tests/test_storygraph_partial_match.py`, `tests/test_story_corpus_v2.py`.
- **Files changed:** `storygraph.py` (edge-state model, dimension results,
  positive-evidence gate, discriminating metadata, version bumps),
  `storyverdict.py` (require `escalation_eligible` for THREAT_CONSISTENT),
  `stories.py` (ATO discriminating metadata; bank-assisted covers beneficiary),
  `evaluation/freeze.py` (bind matcher/policy/corpus/gates), `__init__.py` (exports).
- **Prior failure preserved:** yes — ledger + `prior_runs.RUN_1` +
  `test_prior_run_preserved`; original `STORY_GRAPH_ADVERSARIAL_VALIDATION.md`
  unmodified.
- **Tests:** 179 baseline preserved + 33 new = **212 passing**.
- **Corpus:** 108 cases; splits dev 39 / calibration 38 / final 31.
- **New versions:** schema `ctd.storygraph/1.1.0`, matcher
  `ctd.storygraph.matcher/2.0.0`, partial policy `ctd.partial_escalation/1.0.0`.
- **Frozen config digest:** `sha-256:ed63bc9ba3f7636548360ecfb7d3cec6426fc02c884734a861a1f8347055c3da`.
- **Exact-completion regression:** none (detection 1.00, unchanged).
- **Known limitations:** single synthetic domain; small hand-built corpus; rates
  are structural-separation, not fraud accuracy; several operational metrics NOT RUN.
- **Final verdict:** `CONTINUE — StoryGraph adversarial validation passed`.

---

This phase preserves the prior failed frozen result and corrects the StoryGraph's
partial-match semantics. Missing graph endpoints are no longer treated as satisfied
relationships; they remain explicitly not evaluable. Partial sequences require
positive discriminating evidence before escalation, while exact proposed-action
completion, mandatory non-compensatory constraints, verified-context safety,
deterministic replay, and non-mutating hypothetical evaluation remain intact.
Passing the new frozen evaluation establishes synthetic robustness for one
account-takeover StoryGraph — not enterprise fraud accuracy or enforcement readiness.
