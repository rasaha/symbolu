# ActionGate — Hospital Patient-Data Access & Disclosure Governance (Pilot)

**Status:** Pilot implementation. Self-contained domain package
(`agentic/healthcare/`) around the unchanged generic ActionGate.

> **This is a configurable governance framework — not a legal determination
> engine, not a clinical system, and not a substitute for a hospital's privacy,
> compliance, security, or clinical leadership.** It does not diagnose, does not
> recommend treatment, and takes no autonomous clinical action. It decides only
> *what patient data an AI agent or staff-facing automation may read, summarize,
> search, redact, disclose, or export* — and records why.

---

## 1. Product positioning (non-diagnostic)

ActionGate here is the **authorization and policy-enforcement boundary** in front
of hospital AI agents and automations. The objective is not clinical; it is
access governance: enforcing role, purpose-of-use, consent posture,
minimum-necessary scope, and disclosure/export controls at the point where an
agent asks for data. Every decision is deterministic, explainable, and audited.

## 2. Architecture boundary

The generic engine (`agentic/agentic_framework`) is used **unchanged**. Hospital
rules live only in the domain package:

| Component | File | Role |
|---|---|---|
| Taxonomies | `healthcare/taxonomy.py` | operations, roles, data categories, purposes, consent — configurable, non-exhaustive |
| Request | `healthcare/request.py` | `HealthcareAccessRequest` — classifications & references, **no raw PHI** |
| Criticality | `healthcare/criticality.py` | deterministic criticality derivation + minimum-necessary permitted-category map |
| Policy | `healthcare/policy.py` | `HumanPolicyBook` fixtures, `ActionCriticalityRegistry`, forbidden-capability `PolicyResolution` |
| Service | `healthcare/service.py` | `HealthcareGovernanceService`: adapt → generic authorize → minimum-necessary + applicability → PHI-safe audit |

The package reuses the generic engine's existing capabilities and adds **no
hospital logic to `GovernanceService` or `HumanPolicyEngine`**:

- `HumanPolicyMode.BASELINE` / `SOURCE_OF_TRUTH`;
- per-rule `authority_mode`;
- `ActionCriticalityRegistry` (per-decision authority mode);
- conservative unknown handling (`UncertainDisposition.REQUIRE_APPROVAL`);
- independent hard blocks (forbidden capabilities);
- applicability / audit provenance and final-authority attribution.

The **only** generic change the pilot required is a small, symmetric addition to
`ActionCriticalityRegistry`: `non_critical_facts` (mirror of
`critical_promoting_facts`), so a domain adapter that derives criticality
externally can signal *both* directions with a single deterministic fact.
Promotion still wins, so a non-critical fact can never downgrade a critically
classified action.

## 3. The hospital data-access problem

A modern hospital runs many AI automations (clinical summarizers, billing agents,
research pipelines) and staff tools against the same record store. The risk is
not one bad query — it is *ungoverned breadth*: an agent reading more than the
minimum necessary, a summarizer touching a restricted narrative, a billing bot
exporting a full record, a partner integration pulling identifiable data without
approval. The governance question is **who may do what, to which data, for which
purpose, to which destination, under what consent** — answered the same way every
time and written to an audit trail.

## 4. Critical vs non-critical authority model

Authority mode is resolved **per request** from deterministic, human-authored
inputs (never the LLM):

- **`BASELINE`** — bounded, reversible, internal access where policy establishes
  a scope and the model may tighten. *Examples:* a treating clinician's
  summarizer reads the active encounter; a billing agent reads permitted billing
  fields; staff search a patient within an authorized operational context.
- **`SOURCE_OF_TRUTH`** — disclosures, exports, restricted data, consent-dependent
  use, cross-tenant access — the matched human rule controls and the model is
  advisory. *Examples:* external disclosure; identifiable research access;
  restricted-narrative access; record export; third-party release; cross-hospital
  retrieval.
- **Hard blocks** — explicitly prohibited actions force `DENY` regardless of any
  human `ALLOW` (they are independent, human-configured invariants).
- **Unknown / missing material facts** — conservative `REQUIRE_APPROVAL` (or deny)
  per configured disposition.

## 5. Taxonomies (configurable, non-exhaustive)

- **Operations:** `READ`, `SUMMARIZE`, `SEARCH`, `REDACT`, `DISCLOSE`, `EXPORT`,
  `BULK_EXPORT`.
- **Purposes:** treatment, payment/billing, healthcare operations,
  patient-requested access, research, quality review, legal/regulatory,
  marketing, unspecified.
- **Roles:** treating clinician, consulting clinician, nurse, billing staff,
  medical-records staff, researcher, hospital administrator, external partner,
  patient, AI clinical summarizer, AI billing agent, AI research agent, unknown
  actor.
- **Data categories:** demographic, appointment, diagnosis, medication,
  laboratory, imaging, procedure, billing, clinical note, psychiatric/behavioral
  narrative, reproductive health, HIV/infectious-disease-sensitive, genomic,
  identity documents, authentication credentials, full medical record.
  *Restricted* = psychiatric/reproductive/HIV/genomic. *Prohibited* =
  authentication credentials.

These are a starting configuration; a deployment replaces/extends them and their
sensitivity sets. They are **not** a claim of legal completeness.

## 6. Minimum-necessary access

`ALLOW_WITH_CONSTRAINTS` is a first-class outcome. For an allowed request the
service computes the permitted category set for `(role, purpose)` and returns
machine-readable constraints:

```
allowed_data_categories, denied_data_categories, required_redactions,
patient_scope, encounter_scope, max_record_count, approved_destination,
no_onward_disclosure, session_scoped, minimum_necessary_explanation
```

**Representative case — AI billing agent requests the full record:**
permitted billing fields (billing, demographic, procedure, diagnosis,
appointment) are allowed; psychiatric narrative and unrelated clinical notes are
excluded; outcome is `ALLOW_WITH_CONSTRAINTS`; the audit records the
minimum-necessary transformation (`14 → 5` categories, with the excluded list).

## 7. Consent and missing-fact treatment

Consent state is recorded explicitly — present, absent, withdrawn, not required,
unknown — but **the policy book decides whether consent is required** for a given
purpose/action; no legal conclusion is encoded in the generic engine. Missing
consent or purpose is **never silently inferred by the LLM**: an unspecified
purpose on a sensitive request, or unknown consent on a disclosure/export/
restricted request, is recorded as a missing material fact and pushes the
decision to conservative review (or denial). An LLM may provide an *advisory*
applicability assessment, but deterministic facts and human-curated rules control
the authorization result.

## 8. Hard blocks (independent, fail-closed)

Routed through the generic forbidden-capability layer, so they force `DENY` even
over a human `SOURCE_OF_TRUTH` `ALLOW` (`final_authority = HARD_BLOCK`):

- bulk identifiable export to an unapproved destination;
- credential / authentication-secret retrieval;
- cross-tenant access without an approved relationship;
- consent-withdrawn bypass on disclosure/export;
- unauthorized clinician identity (clinician role without verified identity);
- export to an unapproved external system;
- no actor identity established.

## 9. Applicability disputes (separate from verdict authority)

Two concepts are kept distinct under `SOURCE_OF_TRUTH`:

1. **Human verdict authority** — once the correct rule is established as
   applicable, its verdict is dispositive.
2. **Rule-applicability classification** — whether the request actually belongs
   to the matched rule's action class.

A broad `read` rule should not silently remain `ALLOW` when the request is
materially bulk retrieval / exfiltration. The service detects a deterministic
reclassification indicator (a read-like op carrying export/bulk/external
indicators, or an advisory `model_flags_reclassification`) and **escalates to
`REQUIRE_APPROVAL`**, recording `applicability_status = disputed`. This is not the
model overriding the human verdict — it is flagging a possible rule-match error,
so the response is escalation, never a silent policy override.

## 10. Audit minimization

The `HealthcareAccessRequest` carries no raw PHI — only classifications,
references (opaque `patient_ref` / `encounter_ref`), policy facts, hashes, and
scoped evidence IDs. `HealthcareAccessDecision.audit_dict()` records: domain and
operation, actor role, purpose, requested/permitted/excluded categories,
required redactions, patient/encounter scope references, consent status used,
criticality + basis, effective authority mode, matched rule, human verdict, model
advisory verdict, applicability status, hard-block rule + provenance, final
authority used, and policy-book version + hash — and is JSON-serializable with no
protected medical content.

## 11. Example decision tables

| # | Actor / operation | Purpose | Data | Facts | Outcome | Mode / authority |
|---|---|---|---|---|---|---|
| 1 | AI summarizer / SUMMARIZE | treatment | diagnosis, medication | active encounter | ALLOW (encounter scope) | baseline |
| 3 | AI billing / READ | payment | full record | — | ALLOW_WITH_CONSTRAINTS | source_of_truth |
| 4 | AI billing / READ | payment | psych narrative | — | DENY | source_of_truth |
| 6 | AI research / READ | research | identifiable | no authorization | REQUIRE_APPROVAL | source_of_truth |
| 9 | admin / BULK_EXPORT | operations | full record | unapproved dest | DENY | HARD_BLOCK |
| 10 | records / READ | operations | credentials | — | DENY | HARD_BLOCK |
| 13 | admin / EXPORT | operations | diagnosis | caller says "low risk" | REQUIRE_APPROVAL (critical) | source_of_truth |
| 14 | external / DISCLOSE | treatment | demographic | approved dest + consent, model says deny | ALLOW(+constraints) | HUMAN_SOURCE_OF_TRUTH |
| 15 | AI summarizer / SUMMARIZE | treatment | diagnosis | weak model signals | DENY (model tightened) | baseline |
| 16 | external / READ | treatment | demographic | bulk read → reclassification | REQUIRE_APPROVAL (disputed) | source_of_truth |

## 12. Pilot integration flow (HIS / EMR)

```
 AI agent / staff tool
    │  (role, purpose, patient/encounter ref, categories, destination, consent)
    ▼
 HealthcareGovernanceService.authorize(HealthcareAccessRequest)
    │   1. derive_criticality  (deterministic; ignores caller-declared risk)
    │   2. adapt → generic AuthorizationRequest (facts, hard-block caps, advisory
    │      model signals)
    │   3. GovernanceService.authorize  (human policy + per-decision mode +
    │      hard blocks + final authority)
    │   4. minimum-necessary field reduction + applicability escalation
    ▼
 HealthcareAccessDecision  → enforcement point in the HIS/EMR proxy:
    ALLOW / ALLOW_WITH_CONSTRAINTS (apply field filter + redactions) /
    REQUIRE_APPROVAL (route to approver) / DENY
    → PHI-safe audit record to the governance audit store
```

The service is transport-agnostic: an EMR read/query proxy, an MCP tool
front-end, or a disclosure-management workflow calls `authorize()` and enforces
the returned decision and constraints.

## 13. Pilot metrics

Track and report:

- requests automatically allowed;
- requests constrained (minimum-necessary applied);
- requests escalated for approval;
- requests denied;
- unauthorized exports blocked;
- restricted fields excluded;
- false-escalation rate;
- policy-conflict rate;
- average approval time;
- audit completeness (fraction of decisions with a complete PHI-safe record);
- model-versus-policy disagreement rate (advisory model verdict ≠ final).

## 14. Limitations and non-claims

- The taxonomies and rule fixtures are **illustrative defaults**, not legal or
  jurisdictional determinations; a deployment must configure them with its own
  privacy/compliance leadership.
- Consent-required determinations are **policy decisions the hospital encodes**,
  not conclusions the framework makes.
- Identity verification, destination approval, IRB/research authorization, and
  cross-tenant relationships are **inputs** the surrounding systems must supply
  truthfully; this boundary enforces policy over those facts, it does not
  establish them.
- No raw clinical content is evaluated or stored here; the boundary reasons over
  classifications and references only.
- This is **not** a clinical decision system and makes no diagnostic or treatment
  claims.
