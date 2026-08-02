# Model Selection — Duplication Matrix

Section 14. Duplicated / near-duplicated logic. **No consolidation is performed in this audit.**

The dominant structural finding: the same **two-stage pattern (hard eligibility filter + weighted-utility
scoring)** is implemented **four-to-five times** across the repository, by **copy/re-implementation, not
shared code**. The only intra-capability import edge is `reconciliation → experiment`.

## 1. The two-stage selection pattern (primary duplication)

| Paths | Semantic overlap | Differences | Consumers | Correct owner | Consolidation safety | Evidence |
|---|---|---|---|---|---|---|
| `execution_gate/policy.py::select` + `gate.py` | eligibility gate → `argmax(w_q·Q̂ − w_cost·cost − w_lat·lat)` with id tie-break | dataclass I/O; consumes an upstream `EligibilityDecision`; richest evidence/TTL/criticality model | control_plane, control_plane_shadow, execution_gate_shadow, governed_inference_pilot | **Canonical core candidate** (most production-shaped, dependency-free, has real consumers, self-frozen) | Safe as the *target*; others fold into it | `gate.py`, `policy.py` |
| `model_selection_experiment/policy.py::route` (+`hard_filter`,`fuse_quality`,`score`) | same two stages, one function | dict I/O; adds multi-source `fuse_quality` (declared+benchmark+telemetry+advisory); full decision record; arm F/G | control_plane_shadow (1) | fold into canonical | Medium — same schema, different I/O shape (dict vs dataclass); behavior-equivalence harness needed | `policy.py`; ADR |
| `model_selection_pilot/policy.py::route` (+`hard_and_technical_filter`,`predict_quality`) | same two stages | dict I/O; F1(soft)/F2(hard-gate)/G(advisory) modes; reliability gate (`min_reliability`); thin-evidence leniency (`gate_confidence_floor`); different cost/latency numerics (`pricing_per_mtok` vs `price_per_ktok`) | none | fold into canonical (as opt-in modes) | Medium — richest feature set but no consumers; forked copy | pilot `policy.py` |
| `model_selection_reconciliation/variants.py` (`route_A/B/C`) | wraps experiment `route`; A verbatim, B hard-floor+min-cost, C lexicographic | imports experiment read-only (only non-copy edge) | none | fold B/C in as opt-in modes; drop C (≡ B) | Safe — already layered on experiment | `variants.py`; objective-reconciliation doc |
| `governed_inference_pilot/adapters/{execution_gate,model_policy}.py` | eligibility over frozen `execution_gate.gate`; selection `argmin cost s.t. quality≥q_min` | thin adapters; reuse `execution_gate` for eligibility but re-implement selection objective | (governed_inference_pilot) | fold selection into canonical; keep the adapter | Safe — eligibility already reuses `execution_gate` | agent finding; `model_policy.py` |

## 2. Sub-component duplication

| Concept | Duplicated at | Overlap | Correct owner |
|---|---|---|---|
| Hard-filter 4-tuple `(ok, reason, constraint, provenance)` w/ provenance literals `"enterprise-hard-policy"`/`"verified-provider-fact"` | experiment `hard_filter`, pilot `hard_and_technical_filter` | identical shape, precedence, constraint keys | canonical eligibility |
| Weighted-utility formula `w_q·q − w_cost·c − w_lat·l` + normalize over eligible set + id tie-break | all four selection impls | same math | canonical scoring |
| Decision-record schema (`eligible`,`eliminated`,`scored`,`fallback_chain`,`selected`,`abstained`,`preflight_cost`,versions) | experiment `route`, pilot `route` | same keys | canonical selection record |
| `SelfAssessmentViolation` + forbidden-advisory-field guard | experiment `policy.py`, pilot `advisory.py`+`policy.py` | same guard semantics | canonical advisory guard |
| Quality fusion of {declared, benchmark, telemetry, advisory} with per-source confidence | experiment `fuse_quality`, pilot `predict_quality` (subset) | overlapping; pilot omits declared+benchmark | canonical quality-fusion |
| Cost/latency estimate from declared price × tokens | every dir (different constants/units) | same idea, divergent numerics | canonical estimator (must reconcile units) |
| Registry of candidate models | `execution_gate/registry.py` (`ModelRecord`), experiment `data/registry_v1.json`, pilot `registry.py` | one code registry + two JSON registries; different fields | canonical registry port + data separate |
| Reason-code / eligibility-state enums | `execution_gate/{reason_codes,states}.py` vs experiment/pilot string constants | code enums (rich) vs ad-hoc strings | canonical contract (enums) |

## 3. Near-duplicate *pattern*, DIFFERENT object (NOT Model Selection duplication)

These share the eligibility+preference+bounded-fallback vocabulary but govern a **different object** and
must **not** be consolidated into Model Selection:

| Path | Object | Verdict |
|---|---|---|
| `provider_heterogeneity_validation/selection/resolve.py` | governance-**provider** implementations (ActionGate/TAP/ExecutionGate providers), policies `FIXED/ORDERED/CAPABILITY_REQUIRED/BOUNDED_FALLBACK` | Separate capability (governance-provider resolution); pattern-only overlap |
| `symbolu/hybrid/router.py`, `symbolu/providers/*_router.py` | internal specialized sub-models (Hybrid LLM) | Separate capability (Hybrid LLM) |
| `trading2/analysis/model_selector.py` | EMA vs Bayesian forecasting model | Separate capability (product ML) |
| `symbolu/mechanical/mlcr/expert_router.py` | MoE experts inside one model | Unrelated |

## 4. Consolidation safety summary (for a future phase)

- **Safe target:** `execution_gate` (dependency-free, real consumers, self-frozen, richest contract).
- **Fold in as modes/feeds:** experiment `fuse_quality`/`route`, pilot F1/F2/G + reliability gate,
  reconciliation B (opt-in sufficiency mode). Requires a **behavior-equivalence harness** because I/O
  shapes (dataclass vs dict) and cost/latency numerics differ — a byte-identical before/after capture
  (as used in the GPF migration) is the safe mechanism.
- **Leave behind:** every simulator/oracle/baseline/harness/metrics module (research) and the pilot's
  `provider.py`/`execute.py` (execution).
- **Do NOT touch:** the pattern-only neighbors in §3.

**No consolidation is performed here.** This matrix scopes the work a migration phase would do.
