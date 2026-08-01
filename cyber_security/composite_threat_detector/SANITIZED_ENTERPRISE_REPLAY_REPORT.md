# Sanitized Enterprise Historical Replay — Account-Takeover Vertical Slice

This phase tests whether **real or realistically sanitized enterprise records** can be
normalized, linked, replayed, explained, and reviewed using the frozen account-takeover
Story Policy Pack. No StoryGraph algorithm was added or changed.

## 1. Pre-flight verification (§1)

- **Exact baseline:** `pytest --co -q` → **289 tests collected; 289 passed.**
- **Test-count discrepancy resolved:** the prior report's "279 vs 280" was a transient
  count taken **before** `test_json_schema_contract_matches_python_validator` was added
  to `test_policypack.py` (now 32 tests in that file). The true count at commit
  `6b5d7c2d` was **280**; this phase adds `tests/test_replay_intake.py` (9) → **289**.
- **StoryGraph frozen:** confirmed. The reference pack compiles to the frozen graph
  digest byte-for-byte:
  `sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8`
  (`test_compiled_reference_reproduces_frozen_graph`).

### Digest-completeness audit (§1.6, §1.7)

The per-graph `CTD-STORYGRAPH` digest binds **all structural behavior**:

| Field | Bound? |
|---|---|
| nodes + node requirements (`required`) | ✅ |
| completion nodes (`is_completion`) | ✅ |
| edge types (`kind`) | ✅ |
| mandatory/optional edge status | ✅ (derived from bound `node.required` + edge endpoints) |
| entity dimensions (`dim`) | ✅ |
| time windows (`max_gap`) | ✅ |
| contradiction conditions (`incompatible_when`) | ✅ |
| discriminating metadata (`is_discriminating`, `specificity_class`) | ✅ |
| partial-escalation policy **version** | ✅ (`partial_policy.version`) |
| **matcher version** | ⚠️ not in the graph digest |
| **witness version** | ⚠️ not in the graph digest |

**Finding:** the graph digest identifies graph *structure* only; the matcher and
witness (tie-break) versions were bound at the freeze top-level but **not** carried on
a replay finding. Left unaddressed, two different algorithm versions with the same
graph could produce indistinguishable finding digests — a real replay-evidence gap.

**Resolution (additive, in-scope — evidence packaging):** replay findings and the
replay report now carry an explicit `version_binding`
(`graph_structure_digest` + `matcher_version` + `partial_policy_version` +
`witness_tiebreak_version` + `witness_minimality_basis` + `schema_version` +
`compiler_version` + `bundle_digest`), and the finding/report digests include it.
`test_finding_digest_changes_if_matcher_version_changes` proves the digest is now
sensitive to the matcher version. No StoryGraph semantics changed (289 tests green).

## 2. Enterprise-data availability decision (§2)

The repository and workspace were searched for a sanitized enterprise account-takeover
replay package (manifest, source schemas, sanitized event records, tenant/account ids,
timestamps, approvals/recovery cases, data-use authorization).

**Result: no valid sanitized enterprise dataset is present.**
- `enterprise_validation_pilot/datasets/enterprise_pilot_v1.json` is a **synthetic
  assertion/action-governance** scenario set (evidence like "governed excerpt 1"), not
  account-takeover event streams.
- No JSONL/JSON contains credential-reset / device-enrollment / beneficiary-add /
  transfer records with tenants, timestamps, and a data-use authorization.
- The only account-takeover replay data is this repo's **synthetic fixture**
  (`policypack/fixtures/account_takeover_replay.json`, explicitly labeled *NOT
  enterprise data*).

Per the phase rules: no enterprise records were fabricated, no synthetic fixture was
relabeled as enterprise data, and **historical replay is not claimed as completed.**
The customer data-intake package is produced instead (`replay_intake/`).

## 3. What is ready (readiness scaffolding, validated on synthetic fixtures)

- **Two-commit evidence chain** (`evaluation/evidence_chain.py`) — Commit A records the
  evaluated hash (placeholders rejected); Commit B is evidence-only and path-verified.
- **Pre-registered gates** (`policypack/replay_gates.py`) R1–R9 + data-quality minimums,
  sealed **before any findings were viewed** (no enterprise findings exist):
  `preregistration_digest sha-256:1f026c7a95ee64bb9d2d8398941f84d75ff38f6414b7429b42eba76a736422d4`.
  Hard-zero on cross-tenant contamination and redaction failures.
- **Data-quality gate** fails visibly (`replay_ready: false`) on
  rejected/unknown/redaction/ordering issues.
- **POST_HOC_ONLY** labeling — a workflow carrying an execution receipt (or a proposal
  flagged not-pre-action) is labeled `POST_HOC_ONLY`; pre-commit simulation is not
  claimed when records don't establish what was known before execution
  (`test_post_hoc_only_labeled_on_execution_receipt`).
- **Version binding** on every finding (digest audit closed).
- **Customer data-intake package** (`replay_intake/`): manifest template, record schema,
  source-event + provider mapping templates, policy-gap report template, reviewer
  worksheet template, redaction guidance, secure-handoff requirements, and a clearly
  synthetic example record.

## 4. Metrics

| Metric class | Status |
|---|---|
| Data-quality on enterprise data | **REQUIRES ADDITIONAL ENTERPRISE DATA** |
| StoryGraph findings on enterprise data | **REQUIRES ADDITIONAL ENTERPRISE DATA** |
| Human-review agreement / burden | **REQUIRES ADDITIONAL ENTERPRISE DATA** |
| Operational (throughput, p95 runtime, memory) on enterprise data | **NOT RUN** |
| Import/replay infrastructure | **Measured — synthetic fixture** (deterministic; 3 workflows → WOULD_HOLD_FOR_REVIEW / OBSERVE / ADDITIONAL_CONTEXT_REQUIRED) |
| Version binding / gates / intake schemas | **Measured — unit/integration test** (289 passing) |

No metric is presented as enterprise-measured — none exists.

## 5. Acceptance-gate status

R1–R9 are **pre-registered but not evaluated against enterprise data** (there is none).
R4 (deterministic replay) and R6 (context safety) and the digest/version binding are
demonstrated on the synthetic fixture and unit tests; R1/R2/R3/R5/R7/R8 require the
customer dataset + policy-gap report + human review; R9 (evidence chain) is implemented
and will be exercised on the official run.

## 6. Verdict

**STOP — sanitized enterprise replay data required.**

The strongest permissible outcome without an actual sanitized dataset. Do NOT interpret
this as: production readiness, enterprise-wide validation, fraud-detection validation,
enforcement readiness, malicious-intent detection, or a novel-algorithm proof.

## 7. Completion report

- **Files added:** `policypack/replay_gates.py`, `replay_intake/` (README,
  `replay_manifest.template.json`, `replay_record.schema.json`,
  `source_event_mapping.template.json`, `provider_mapping.template.json`,
  `reviewer_worksheet.template.json`, `policy_gap_report.template.md`,
  `example_sanitized_record.json`), `tests/test_replay_intake.py`, this report.
- **Files changed:** `policypack/replay.py` (version binding + POST_HOC_ONLY).
- **Exact test count:** 289 collected / 289 passed.
- **Digest audit result:** structural fields fully bound; matcher/witness-version gap
  found and closed via explicit finding/report `version_binding`.
- **Enterprise dataset status:** absent → data-intake package produced.
- **Dataset/policy digests:** frozen graph
  `sha-256:6a77b899…`; compiled bundle `sha-256:f6323c92…`; pre-registration
  `sha-256:1f026c7a…`.
- **Data-quality / entity-resolution / ordering / findings / review / performance:**
  REQUIRES ADDITIONAL ENTERPRISE DATA / NOT RUN (no dataset).
- **Metrics still NOT RUN:** all enterprise-accuracy and operational-on-enterprise
  metrics.
- **Known limitations:** single synthetic domain; no enterprise dataset available;
  gates pre-registered but unevaluated against real data; entity equivalence relies on
  exact redaction-token equality (customer must tokenize deterministically).
- **Commit A / Commit B:** **not applicable** — no official enterprise replay occurred,
  so no two-commit evidence record was created (fabricating one would misrepresent a
  run that did not happen). The chain is implemented and will be exercised when a
  sanitized dataset with authorization is supplied.
- **Final verdict:** `STOP — sanitized enterprise replay data required`.

---

This phase does not add another StoryGraph mechanism. It tests whether a
customer-defined, governed account-takeover policy can be applied to sanitized
historical enterprise records with reliable event normalization, exact entity linkage,
explicit ordering, trusted-context reconstruction, deterministic replay, and
review-ready explanations. Successful completion establishes evidence for one bounded
historical workflow — not production fraud accuracy, enterprise-wide validation, or
enforcement readiness. **No sanitized enterprise dataset was available, so this phase
stops at the data gate with a customer-ready intake package and a strengthened,
version-bound replay evidence path.**
