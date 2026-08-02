# Policy-Ownership Matrix — Code Governance

> Documentation only. Authoritative source: `UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md` v0.2 (§10, §16.1).

Repository governance policy must have a **single source of truth per rule** and must be loaded from
the **approved base branch, never the candidate branch** (`case_validation_service`/design §16.1).
Policy version is referenced across the chain via `VersionedRef` (`policy_refs`) — no contract change.

## 1. Ownership by policy rule

| Policy | Source of truth | Enforced by | Live anchor |
|---|---|---|---|
| protected repository allowlist | Code Governance product policy | Workflow Service + connector | product |
| target-branch rules | product policy (+ GitHub repo settings) | Workflow Service | product |
| required checks | product policy | TAP admission + ACP re-check | `AssertionGovernanceRequest`; ACP signal |
| required validator identities | product policy | TAP / evidence provenance | evidence provenance (must add validator binding) |
| minimum approvals | Decision Authority (`AuthorityContext.required_approvals`) | Decision Authority | `decisions/authority.py` |
| required approver roles | product policy → `AuthorityType` mapping | Decision Authority | `validate_authority` |
| Code Owner requirements | product policy | Decision Authority (mapped) | product → authority |
| security approval requirements | product policy | Decision Authority | product → authority |
| author/approver separation (SoD) | Decision Authority (`segregation_of_duties=True`) | Decision Authority | `case_validation_service.py:138` (off by default — product must enable) |
| override permissions | Decision Authority | `OverrideRecord` | `decisions/override.py` |
| merge methods | product policy | ActionGate (bound param) + execution provider | CER `permitted_parameters` |
| merge-queue policy | product policy | Workflow Service + ACP | product |
| max authorization lifetime | product policy | CER `expires_at` + ActionGate `expiry` | reuse |
| freeze / incident rules | ACP (operational) + product policy | ACP clearance | `change_freeze_active` signal |
| high-risk path classification | product policy | Workflow Service (mode selection) + StoryGraph | product; StoryGraph pattern pack |
| external-model restrictions | product policy + Model Selection | Model Selection + product | `model-selection` |
| source-code residency restrictions | product policy | Workflow Service (pre-external-model gate) | product (design §16.1) |
| competitive-adjudication triggers | product policy | Workflow Service | product (MVP2) |

## 2. Which authority owns which class

- **TAP**: which evidence is mandatory / admissible for a claim (evidence-tier).
- **Decision Authority**: who may approve, required approvals/roles, SoD, overrides.
- **ActionGate**: exact-action authorization bounds (permitted/prohibited parameters, expiry).
- **ACP**: live operational gates (freeze, incident, health, staleness).
- **StoryGraph**: advisory sequence-risk (control-erosion pattern pack).
- **GitHub repository settings**: native branch protection (defense-in-depth, not source of truth).
- **Code Governance product policy**: the repository policy pack that composes and *scopes* all of
  the above (paths, modes, thresholds) — the single authoring surface, compiled via the policy-pack
  compiler.

**Anti-duplication rule:** each rule appears once as source of truth (column 2). GitHub repo settings
are defense-in-depth mirrors, not authoritative.

## 3. Conflict handling (§10.1)

- **Compatible constraints → deterministic intersection** (strictest compatible set).
- **Direct conflict (no strict ordering) → `POLICY_CONFLICT`** — never silently pick one.
- **Missing resolution rule → fail closed and escalate** — never fail open.

## 4. Policy version + digest across the chain

- `policy_refs: tuple[VersionedRef,...]` (`ref_id:version`) is recorded on `DecisionRecord`,
  `DecisionCase`, `ActionRequest`, and CER `policy_context`; folded into the CER `content_hash` and
  `ActionAuthorizationResponse.policy_versions`.
- A **policy digest** (content hash of the compiled policy pack) should be recorded as a
  `VersionedRef` id so any decision/authorization reconstructs the exact policy applied. This is a
  **product convention over existing fields** — no contract change.
