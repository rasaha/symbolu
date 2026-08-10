# Mapping Template — Discount Approval (BLANK)

> **Blank template.** Fill in with the enterprise workflow owner. Do **not** commit
> real data into this repo copy. Every `< >` is a placeholder. Leave blank or write
> `MISSING` when the source does not carry the fact — never invent a value.
>
> Maps onto the **frozen** architecture
> ([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md));
> field meanings in [`SOURCE_ADAPTER_SPECIFICATION.md`](../SOURCE_ADAPTER_SPECIFICATION.md).
> This is the recommended first pilot workflow (discount → contract).

## 0. Header

- Workflow name: `Customer discount approval`
- Enterprise workflow owner: `< >`
- Data owner: `< >`
- Date / template version: `< >`
- Scope confirmed read-only, historical, shadow: `< yes/no >`

## 1. Participating systems

| System | Role in workflow | Read-only access method |
|---|---|---|
| `< CRM >` | `< opportunity / quote / discount >` | `< >` |
| `< ERP / Finance >` | `< margin decision / approval >` | `< >` |
| `< Policy registry >` | `< policy versions >` | `< >` |
| `< >` | `< >` | `< >` |

## 2. Evidence mapping (source fact → capability group)

| Source fact | Capability group | Payload key(s) | status | verification | authority_role |
|---|---|---|---|---|---|
| `< sales agent identity >` | `IDENTITY_AUTHORITY` | `< role >` | `< >` | `< >` | `< SUPPORTING? >` |
| `< stated objective >` | `PURPOSE_POLICY_BASIS` | `< objective >` | `< >` | `< >` | `< ADVISORY? >` |
| `< margin floor / policy basis >` | `PURPOSE_POLICY_BASIS` | `< objective, margin_floor >` | `< >` | `< >` | `< AUTHORITY_BEARING? >` |
| `< quote form >` | `AUTHORIZED_FORM` | `< form >` | `< >` | `< >` | `< >` |
| `< finance approval / sign-off >` | `IDENTITY_AUTHORITY` | `< approver >` | `< PRESENT/MISSING >` | `< >` | `< AUTHORITY_BEARING? >` |
| `< margin invariant preserved? >` | `PROTECTED_INVARIANTS` | `< invariant, preserved >` | `< >` | `< >` | `< >` |
| `< policy versions used >` | `DECISION_DERIVATION` | `policy_versions (name@version)` | `< >` | `< >` | `< >` |
| `< enterprise-wide limit >` | `CUMULATIVE_CONSTRAINTS` | `< constraint, breached >` | `< >` | `< >` | `< >` |
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 3. Decisions

| decision_id | actor | effect | supporting_refs | reason_code |
|---|---|---|---|---|
| `< >` | `< >` | `< allow/allow_with_constraints/widen/defer/deny >` | `< >` | `< >` |

## 4. Executions

| execution_id | system | subject_key | authorized_form | executed_form | resulting_state |
|---|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 5. Cross-system dependencies

| from_system | to_system | requires_subject | satisfied | stale | description |
|---|---|---|---|---|---|
| `< CRM >` | `< ERP/Finance >` | `< approval:... >` | `< >` | `< >` | `< discount needs finance approval >` |

## 6. Integration / closure (discount → contract)

| intended {system,key,value} | observed {system,key,value} | required_closure | satisfied_closure |
|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` |

## 7. Existing controls (for the baseline)

| Existing control | Failure code(s) it already catches | Confirmed deployed & effective? |
|---|---|---|
| `< approval matrix >` | `< MISSING_AUTHORITY_BASIS? >` | `< >` |
| `< margin rule engine >` | `< PROTECTED_INVARIANT_BREACH? >` | `< >` |
| `< >` | `< >` | `< >` |

## 8. Coverage check

- Facts expressible by **no** frozen capability group? `< list >`
- Known problem classes mapping to **no** frozen failure code? `< list >`
