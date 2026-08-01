# Enterprise Story Policy Pack & Historical-Replay Readiness

This phase **freezes further StoryGraph algorithm development** and turns the verified
account-takeover vertical slice into a governed, customer-configurable enterprise
policy package with a deterministic historical-replay path over sanitized fixtures.

Module: `composite_threat_detector/policypack/`. Baseline preserved and extended:
**248 → 279 tests passing.**

## Core-algorithm freeze result (§2)

No StoryGraph matching semantics changed. The reference pack **compiles to the frozen
graph byte-for-byte**: the compiled graph's freeze-style digest equals the frozen
`ACCOUNT_TAKEOVER_TRANSFER@1.0.0` digest
`sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8`
(`test_compiled_reference_reproduces_frozen_graph`), and the compiled graph produces
identical verdicts to the frozen graph (`test_compiled_graph_behaves_like_frozen_graph`).
Changes were confined to policy authoring, configuration schemas, event normalization,
provider mapping, replay adapters, governance, evidence packaging, and documentation.
No unavoidable core change was required — **zero scope deviation.**

## Witness terminology correction (§3)

The witness proof canonicalizes semantically-equivalent duplicate events and proves
necessity by removing an entire equivalence class. Terminology corrected across code,
certificates, and `to_dict()`:

- `minimality_basis: "SEMANTIC_EQUIVALENCE_CLASS"` (constant `MINIMALITY_BASIS`)
- `canonical_witness_minimal: true|false` (property + serialized field)
- `equivalence_classes`, `excluded_equivalent_events`, `removal_proofs` (unchanged)
- `minimality_verified` retained as a **back-compat alias**.

> The canonical witness is minimal over semantic event-equivalence classes. Duplicate
> or replayed source records remain visible as provenance but are not treated as
> independent required evidence.

## Two-commit official evidence chain (§4)

`evaluation/evidence_chain.py` implements the stronger workflow for the **next**
official evaluation generation (the prior Run-3 holdout result is preserved and **not
rerun**):

- **Commit A** — evaluated implementation; the official evaluator records Commit A's
  exact hash. `build_evidence_record` **rejects placeholder commits**.
- **Commit B** — evidence-only record referencing Commit A (evaluated source commit,
  timestamp, freeze digest, holdout manifest hash, generator version + seeds, graph /
  matcher / policy / witness versions, raw counts, derived metrics, verdict,
  record digest). `verify_evidence_commit_paths` asserts Commit B touches only
  approved evidence paths; `verify_record` re-checks the sealed digest.

## StoryPolicyPack schema + authoring forms (§5, §6)

`policypack/schema.py` (`ctd.storypolicypack/1.0.0`) validates identity, business
objective, scope, canonical action, harmful StoryGraph, legitimate counter-stories,
ActionGate consequence mapping, event/provider mappings, governance, and validation.
A machine-readable contract lives at `policypack/schemas/storypolicypack.schema.json`
(its required set is asserted to match the authoritative Python validator).

Two authoring forms converge on one canonical pack: the policy-as-code
`reference.ACCOUNT_TAKEOVER_PACK` and the business questionnaire
`business_form.ACCOUNT_TAKEOVER_BUSINESS_FORM` share the canonical digest
`sha-256:a151392017634309cbbc8066380e4c9d0985a4a4599b8341a27fb72c361b0ab9`
(`test_business_form_compiles_to_same_canonical_pack`). The business form cannot
bypass schema validation.

## Deterministic compiler (§7)

`policypack/compiler.py` (`ctd.policypack.compiler/1.0.0`):
validated pack → canonical `StoryGraph` → legitimate `CoverageRule`s → consequence
map → frozen bundle (`bundle_digest`
`sha-256:f6323c9275e125be…`) with source→compiled lineage. It **rejects** missing
required fields, unknown node references, invalid edge endpoints, mandatory
`CONTRADICTS` without an explicit condition, unversioned provider mappings,
consequences outside the approved vocabulary, and enforcement status without
governance approvals. **An AI draft never publishes itself** — `publish()` refuses
without human publication confirmation and business/control/technical approvals.

## Lifecycle + approvals (§8)

`policypack/lifecycle.py` — `DRAFT → VALIDATING → SHADOW_APPROVED → SHADOW_ACTIVE →
ENFORCEMENT_CANDIDATE → ENFORCED` (+ `SUSPENDED`, `RETIRED`). Each transition is
role-gated and audited; **the author of a policy may not also publish it to
enforcement** (segregation of duties). Invalid transitions and missing roles are
rejected.

## Event + provider mappings (§9, §10)

`policypack/event_mapping.py` maps generic source events to canonical StoryGraph
events (deterministic, tenant-mandatory, redaction-aware, dedup identity + payload
digest); unmapped/rejected records are reported, never silently absent.
`policypack/providers_mapping.py` validates trusted-provider config and **forbids an
`ALLOW` availability behavior** — provider failure can never become permission, and
missing provider evidence never strengthens the harmful graph (the frozen matcher
leaves the structural vector unchanged; `incorrect_harmful_strengthening = 0`).

## Reference Account-Takeover Policy Pack (§11) + scenario matrix (§12)

`policypack/reference.py` encodes the frozen harmful graph (reset · device · benef ·
optional limit · transfer completion), the mandatory relationships (same account,
transfer beneficiary = newly added beneficiary, transfer device = newly enrolled
device, ordering, bounded window), the legitimate counter-stories (account recovery,
bank-assisted transaction), the consequence mapping, and generic event/provider
mappings. The §12 scenario matrix (correct completion; wrong account/device/
beneficiary; expired/partial coverage; provider unavailable; duplicate events;
ambiguous ordering; tenant mismatch) is verified against the compiled graph, and the
business-form pack shares the reference's canonical digest.

Consequence mapping (advisory → policy): weak partial → `OBSERVE`; missing context →
`ADDITIONAL_CONTEXT_REQUIRED`; ambiguous → `REQUIRE_REVIEW`; exact completion of an
uncovered harmful graph → `WOULD_HOLD_FOR_REVIEW`; hard violation → `DENY`. The
StoryGraph layer stays advisory; policy owns the binding consequence.

## Historical-replay contract, data quality, runner (§13–§16)

`policypack/replay.py` (`ctd.storyreplay/1.0.0`) defines the replay-record schema, a
**data-quality report that fails visibly** on rejected/unknown/redaction/ordering
issues (`replay_ready: false`), and a deterministic runner that normalizes, sorts by
explicit ordering, reconstructs per-workflow assembly state, evaluates advisory
StoryGraph findings + proposed-action simulations, records trusted-context, and emits
review-ready explanations + a `report_digest`. On the synthetic fixture
(`fixtures/account_takeover_replay.json`) the three workflows resolve to
`WOULD_HOLD_FOR_REVIEW`, `OBSERVE` (verified legitimate), and
`ADDITIONAL_CONTEXT_REQUIRED` (provider unavailable), deterministically
(`report_digest sha-256:bf374cd6…`).

### Metrics still NOT RUN / REQUIRES ENTERPRISE DATA

`unauthorized_action_detection_rate`, `benign_review_burden`,
`operator_agreement_rate`, `false_hold_rate` → **REQUIRES ENTERPRISE DATA**;
`runtime_per_event_ms`, `replay_throughput` → **NOT RUN**. The runner never fabricates
enterprise results and runs only on synthetic/sanitized fixtures.

## Historical-replay readiness gates

Replay is *ready* (contract + runner + data-quality + deterministic findings on
synthetic fixtures) but **not completed** — no sanitized enterprise events were
supplied. Promotion to a real replay requires: sanitized enterprise fixtures passing
the data-quality gate (`replay_ready: true`), the two-commit evidence chain for the
official run, and shadow-mode review-agreement baselines.

## Verdict

**CONTINUE — enterprise policy pack and historical replay ready.**

This is the strongest permissible outcome: no real sanitized enterprise data was
supplied, so historical replay is *ready*, not *completed*.

### Explicit non-claims

Not *Production ready*, *Enterprise validated*, *Fraud detection validated*,
*Enforcement ready*, or *Novel algorithm proven*. This establishes enterprise
policy-onboarding and historical-replay readiness for one synthetic account-takeover
StoryGraph — not real-world fraud accuracy.

## Known limitations

Single synthetic domain; generic (non-vendor) source/provider categories; event
equivalence uses a fixed material-field key; replay exercised only on a small
synthetic fixture; all enterprise-accuracy metrics remain NOT RUN.

## Completion report

- **Files added:** `policypack/{__init__,schema,compiler,lifecycle,event_mapping,`
  `providers_mapping,reference,business_form,replay}.py`,
  `policypack/schemas/storypolicypack.schema.json`,
  `policypack/fixtures/account_takeover_replay.json`,
  `evaluation/evidence_chain.py`, `tests/test_policypack.py`, this document.
- **Files changed:** `storyverdict.py` (witness terminology; `MINIMALITY_BASIS`),
  `__init__.py` (exports).
- **Tests:** 248 baseline + 31 new = **279 passing** (+1 JSON-schema contract check = 32
  in the policypack suite).
- **Core algorithm freeze:** confirmed — compiled reference reproduces the frozen
  graph digest; zero scope deviation.
- **New versions:** schema `ctd.storypolicypack/1.0.0`, compiler
  `ctd.policypack.compiler/1.0.0`, event mapping `ctd.event_mapping/1.0.0`, provider
  mapping `ctd.provider_mapping/1.0.0`, replay `ctd.storyreplay/1.0.0`, evidence chain
  `ctd.evidence_chain/1.0.0`, witness tie-break `ctd.witness.tiebreak/2.0.0` (basis
  `SEMANTIC_EQUIVALENCE_CLASS`).
- **Final verdict:** `CONTINUE — enterprise policy pack and historical replay ready`.

---

This phase freezes further StoryGraph algorithm development and turns the verified
account-takeover vertical slice into a governed enterprise policy package. It defines
how business owners describe the controlled action and harmful sequence, how technical
teams map source events and trusted evidence, how ActionGate consequences are approved
and versioned, and how sanitized historical records can be normalized and replayed
deterministically. Passing this phase establishes enterprise policy-onboarding and
historical-replay readiness — not real-world fraud accuracy, production readiness, or
enforcement readiness.
