# TAP-E4 — Governance Resolution — Experiment Report

> **Naming note.** This layer's canonical engineering name is used throughout. **Previously referred to as Governance Truth.** For reproducibility, the package directory `tap_e4_governance_truth/`, the schema-version prefix `tap-e4-governance/…`, experiment IDs, and stored artifacts retain the original name — see `01_TRUTH_ASSURANCE_ARCHITECTURE.md` §2a.


## 1. Objective

Implement and evaluate a **standalone, deterministic, provenance-preserving Governance
Resolution layer**. Given the frozen upstream records — `IntentRecord` (TAP-E1),
`RetrievalRecord` (TAP-E2), `RelationshipRecord` (TAP-E3) — and an explicit governance
`Situation`, resolve **which documented authority governs the situation, and why**:
the controlling rule / policy / regulation / contract / version, together with its
jurisdiction, scope, temporal/version basis, supersession, exceptions, precedence chain,
unresolved conflicts, gaps, and per-authority provenance.

Nothing beyond that. This layer does **not** determine factual truth, claim truth, or
response correctness; does **not** answer the user; does **not** retrieve; does **not**
discover relationships; and does **not** authorize or execute anything.

## 2. What "Governance Resolution" means (and does not)

Governance Resolution is the answer to *"among the documented authorities the evidence puts on
the table, which one controls this specific situation, and by what documented rule?"* It is
a **selection-and-justification** result, not a correctness result:

- It may conclude **"the customer contract governs notification timing here."** It must not
  conclude that the contractual number is *correct*, *fair*, or *legal* — that is outside
  the layer.
- It resolves precedence among **documented** authorities (a frozen, versioned hierarchy).
  It is **not** real legal reasoning and makes no claim to be.
- When authorities tie with no documented resolver, it **surfaces a conflict** — it never
  silently picks a winner.
- When nothing governs, or an upstream relationship gap blocks resolution, it **reports a
  gap** — it never fabricates an authority.

## 3. Inputs and output

**Inputs:** `IntentRecord`, `RetrievalRecord`, `RelationshipRecord` (all via frozen public
interfaces), plus a `Situation` (jurisdiction, user role, environment, date/year, contract,
product, business unit) supplied as application metadata. See [ARCHITECTURE](ARCHITECTURE.md).

**Output:** a single versioned, serializable `GovernanceRecord` (see [SCHEMA](SCHEMA.md))
carrying the `GoverningDecision` (selected authority + tier + selection reason + precedence
chain + rejected authorities + jurisdiction/scope/temporal/exception basis + provenance +
status), plus governance conflicts, governance gaps, an 8-axis confidence vector, and an
append-only processing trace.

## 4. Method

### 4.1 Documented authority model (frozen)

Authority tiers, highest first: **LAW > REGULATION > CORPORATE_POLICY > DEPARTMENT_POLICY >
SOP > WORK_INSTRUCTION > RECOMMENDATION > DRAFT > UNKNOWN**. `LAW` and `REGULATION` are
*immutable* — a customer contract or corporate policy may never override them. `DRAFT` is
*never selectable*. Each candidate's tier is derived from the TAP-E2 evidence unit that
states it (document type + authority level), optionally refined by an explicit tier the
governing statement carries. This mapping is the only place upstream authority metadata is
interpreted; it is versioned (`tap-e4-authority/1.0.0`) and hashed.

### 4.2 Documented precedence rules (frozen)

Ordering key, applied only to candidates that already survived jurisdiction, scope,
temporal, supersession, and exception filtering (`tap-e4-precedence/1.0.0`):

1. authority tier rank;
2. customer-contract override (a contract may override CORPORATE/DEPARTMENT policy, **never
   an immutable tier**);
3. emergency override (an emergency procedure wins for emergency situations);
4. scope specificity (role/environment-specific beats broad);
5. version recency.

Ties are broken deterministically by authority name; a residual tie at the top key with
incompatible obligations is a **conflict**, not a silent choice.

### 4.3 Thirteen-stage deterministic pipeline

`input validation → authority identification → authority normalization → jurisdiction →
scope → temporal applicability → version resolution → exception evaluation → precedence
resolution → conflict detection → confidence → governance gaps → GovernanceRecord
generation`. Every stage is a pure function of the records + situation; the pipeline emits
an append-only trace. See [ARCHITECTURE](ARCHITECTURE.md) §4.

### 4.4 Ablation ladder (A–F)

| Config | Adds | Intended weakness |
|---|---|---|
| **A** | first matching policy | selects expired/superseded/draft/out-of-jurisdiction |
| **B** | highest authority only | ignores jurisdiction/scope/temporal |
| **C** | + jurisdiction + scope | still selects expired/superseded/future/old-version |
| **D** | + temporal + version/supersession | ignores exceptions & customer/emergency override |
| **E** | + exceptions + precedence | resolves ties silently; drops conflicts & gaps |
| **F** | + conflict + confidence + gaps + provenance + trace | — (full) |

Configuration is selected on the **DEV split only**: the simplest baseline (A..F order)
satisfying every preregistered gate. The locked eval split is scored once, for the verdict.

## 5. Corpus

New, independently authored: **30 cases across 15 governance families** (dev 15 / eval 15),
26 synthetic evidence units. Families: basic, jurisdiction, scope, expired, superseded,
future, version, draft, customer_override, emergency_override, law_supremacy, exception,
conflict, no_governing, upstream_gap — including the adversarial cases the spec requires
(superseded, overlapping jurisdiction, conflicting contracts, temporary exceptions,
historical/future-effective, draft-vs-approved, regional/customer/emergency override). The
relationship inputs are authored to be already-perfect (upstream confidence 1.0) so the
experiment isolates the governance layer. See [CORPUS](CORPUS.md).

## 6. Results

Selection chose **baseline F** — the simplest configuration passing every preregistered
gate on DEV. Every earlier baseline fails ≥1 gate on DEV:

| Baseline | DEV gates passed | First blocking failures |
|---|---|---|
| A | no | governing/jurisdiction/scope/temporal/version/exception/precedence/conflict + severe criticals |
| B | no | jurisdiction/scope/temporal/version/exception/conflict + severe criticals |
| C | no | temporal/version/exception/precedence/conflict + expired critical |
| D | no | exception/precedence/conflict + exception & override criticals |
| E | no | conflict F1, gap, severe critical (UPSTREAM_GAP_IGNORED) |
| **F** | **yes** | — |

**Locked eval, selected baseline F — all 14 gates pass:**

| Gate | Op | Threshold | Value |
|---|---|---|---|
| governing_authority_accuracy | ≥ | 0.90 | 1.00 |
| jurisdiction_accuracy | ≥ | 0.90 | 1.00 |
| scope_accuracy | ≥ | 0.90 | 1.00 |
| temporal_accuracy | ≥ | 0.95 | 1.00 |
| version_accuracy | ≥ | 0.90 | 1.00 |
| exception_accuracy | ≥ | 0.90 | 1.00 |
| precedence_accuracy | ≥ | 0.90 | 1.00 |
| governance_conflict_f1 | ≥ | 0.75 | 1.00 |
| governance_gap_accuracy | ≥ | 0.75 | 1.00 |
| provenance_completeness | == | 1.00 | 1.00 |
| unsupported_governance_rate | ≤ | 0.05 | 0.00 |
| incorrect_override_rate | == | 0.00 | 0.00 |
| expired_policy_selection_rate | == | 0.00 | 0.00 |
| severe_critical_failure_count | == | 0.00 | 0.00 |

All ten independent critical-failure classes are **0** for F on both splits. See
[METRICS](METRICS.md) and [FAILURE_ANALYSIS](FAILURE_ANALYSIS.md).

## 7. Verdict

**`PASS_WITH_LIMITED_CLAIM`.**

**Supported claim (narrow):** a deterministic, provenance-preserving architecture for
resolving *which documented authority governs a situation* — across authority precedence,
jurisdiction, scope, temporal/version, supersession, exception, customer/emergency
override, immutable-tier protection, conflict surfacing, gap preservation, and per-authority
provenance — on this study's synthetic corpus, with the full pipeline (F) demonstrably the
simplest configuration that avoids every preregistered safety-critical governance failure.

**Explicitly NOT claimed:** production legal/regulatory reasoning; correctness of any
obligation; real-world authority hierarchies; external generalization; claim truth; user
answers; enforcement.

## 8. Integrity

- TAP-E1, TAP-E1.1, TAP-E2, TAP-E3 are **unchanged** (byte-identical; consumed through
  frozen public interfaces only). Full repository regression: **124 tests pass**.
- Deterministic across `PYTHONHASHSEED ∈ {0,1,7,42,123}` — identical result hash and
  `frozen_components_hash`.
- `frozen_components_hash = 9e44afd7…`; `eval_inputs_hash = c28e23f3…` (n_eval = 15).

## 9. Next layer

**TAP-E5 — Evidence Assembly.** With intent (E1), trusted retrieval (E2), relationships (E3),
and now governing authority (E4) resolved, the next layer should **assemble the minimal,
fully-provenanced evidence packet** — the governing authority, the relationships it rests
on, the retrieved units behind them, and the intent it answers — that a downstream Claim
Validation layer will need. It should carry every unresolved conflict and gap forward intact and
add no new inference. See [CHANGELOG](CHANGELOG.md) and [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md).
