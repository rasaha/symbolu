# Mapping Template — Contract Lifecycle (BLANK)

> **Blank template.** Fill in with the enterprise workflow owner. Do **not** commit
> real data into this repo copy. Every `< >` is a placeholder. Leave blank or write
> `MISSING` when the source does not carry the fact — never invent a value.
>
> Maps onto the **frozen** architecture
> ([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md));
> field meanings in [`SOURCE_ADAPTER_SPECIFICATION.md`](../SOURCE_ADAPTER_SPECIFICATION.md).
> This workflow is closure-heavy (multi-system activation), so integration/closure
> is the central capability group.

## 0. Header

- Workflow name: `Contract lifecycle (signature → activation → billing)`
- Enterprise workflow owner: `< >`
- Data owner: `< >`
- Date / template version: `< >`
- Scope confirmed read-only, historical, shadow: `< yes/no >`

## 1. Participating systems

| System | Role in workflow | Read-only access method |
|---|---|---|
| `< CLM / e-signature >` | `< contract state >` | `< >` |
| `< ERP >` | `< effective date / terms >` | `< >` |
| `< Billing >` | `< invoice schedule >` | `< >` |
| `< Finance >` | `< credit hold >` | `< >` |
| `< Provisioning >` | `< entitlement activation >` | `< >` |

## 2. Evidence mapping (source fact → capability group)

| Source fact | Capability group | Payload key(s) | status | verification | authority_role |
|---|---|---|---|---|---|
| `< signer authority >` | `IDENTITY_AUTHORITY` | `< approver >` | `< >` | `< >` | `< AUTHORITY_BEARING? >` |
| `< contract policy basis >` | `PURPOSE_POLICY_BASIS` | `< objective >` | `< >` | `< >` | `< >` |
| `< authorized contract form >` | `AUTHORIZED_FORM` | `< form >` | `< >` | `< >` | `< >` |
| `< policy versions >` | `DECISION_DERIVATION` | `policy_versions` | `< >` | `< >` | `< >` |
| `< protected term (e.g. margin/SLA) >` | `PROTECTED_INVARIANTS` | `< invariant, preserved >` | `< >` | `< >` | `< >` |
| `< intended vs observed activation state >` | `INTEGRATION_CLOSURE` | `intended[], observed[], required_closure[], satisfied_closure[]` | `< >` | `< >` | `< >` |
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 3. Decisions

| decision_id | actor | effect | supporting_refs | reason_code |
|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` |

## 4. Executions (per system)

| execution_id | system | subject_key | authorized_form | executed_form | resulting_state |
|---|---|---|---|---|---|
| `< >` | `< CLM >` | `< contract:... >` | `< >` | `< >` | `< >` |
| `< >` | `< ERP >` | `< contract:... >` | `< >` | `< >` | `< >` |
| `< >` | `< Billing >` | `< contract:... >` | `< >` | `< >` | `< >` |

## 5. Cross-system dependencies

| from_system | to_system | requires_subject | satisfied | stale | description |
|---|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 6. Integration / closure (activation must complete everywhere)

| intended {system,key,value} | observed {system,key,value} | required_closure | satisfied_closure |
|---|---|---|---|
| `< ERP effective_date >` | `< >` | `< invoice_created >` | `< >` |
| `< Billing invoice_schedule >` | `< >` | `< credit_released >` | `< >` |
| `< Finance credit_hold >` | `< >` | `< dates_aligned >` | `< >` |

## 7. Existing controls (for the baseline)

| Existing control | Failure code(s) it already catches | Confirmed deployed & effective? |
|---|---|---|
| `< ERP reconciliation job >` | `< STATE_RECONCILIATION_FAILURE? >` | `< >` |
| `< >` | `< >` | `< >` |

## 8. Coverage check

- Facts expressible by **no** frozen capability group? `< list >`
- Known problem classes mapping to **no** frozen failure code? `< list >`
