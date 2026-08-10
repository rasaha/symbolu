# Mapping Template — IAM Role / Access (BLANK)

> **Blank template.** Fill in with the enterprise workflow owner. Do **not** commit
> real data into this repo copy — keep completed templates in the enterprise's own
> secured location. Every `< >` is a placeholder. Leave a cell blank or write
> `MISSING` when the source does not carry the fact — never invent a value.
>
> Maps onto the **frozen** architecture
> ([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../../ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md));
> field meanings in [`SOURCE_ADAPTER_SPECIFICATION.md`](../SOURCE_ADAPTER_SPECIFICATION.md).

## 0. Header

- Workflow name: `IAM role / access (+ offboarding closure)`
- Enterprise workflow owner: `< >`
- Data owner: `< >`
- Date / template version: `< >`
- Scope confirmed read-only, historical, shadow: `< yes/no >`

## 1. Participating systems

| System | Role in workflow | Read-only access method (export/replica/scoped read) |
|---|---|---|
| `< IAM >` | `< grants / roles >` | `< >` |
| `< VPN >` | `< access state >` | `< >` |
| `< SaaS app(s) >` | `< access state >` | `< >` |
| `< >` | `< >` | `< >` |

## 2. Evidence mapping (source fact → capability group)

For each fact, pick exactly one `CapabilityGroup` and set status/verification/
authority honestly. Payload keys must be those the invariants read
([`SOURCE_ADAPTER_SPECIFICATION.md`](../SOURCE_ADAPTER_SPECIFICATION.md) §4).

| Source fact | Capability group | Payload key(s) | status | verification | authority_role |
|---|---|---|---|---|---|
| `< principal / role >` | `IDENTITY_AUTHORITY` | `< role >` | `< >` | `< >` | `< >` |
| `< grant approval >` | `IDENTITY_AUTHORITY` | `< approver >` | `< >` | `< >` | `< AUTHORITY_BEARING? >` |
| `< granted vs approved perms >` | `CAPABILITY_SPACE` | `available, permitted, prohibited, revoked, approval_required, approvals_present` | `< >` | `< >` | `< >` |
| `< offboarding target state >` | `INTEGRATION_CLOSURE` | `intended[], observed[], required_closure[], satisfied_closure[]` | `< >` | `< >` | `< >` |
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 3. Decisions

| decision_id | actor | effect (allow/allow_with_constraints/widen/defer/deny) | supporting_refs (evidence subjects) | reason_code |
|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` |

## 4. Executions (if observed)

| execution_id | system | subject_key | authorized_form | executed_form | resulting_state |
|---|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 5. Cross-system dependencies

| from_system | to_system | requires_subject | satisfied | stale | description |
|---|---|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 6. Integration / closure (offboarding)

| intended {system,key,value} | observed {system,key,value} | required_closure | satisfied_closure |
|---|---|---|---|
| `< >` | `< >` | `< >` | `< >` |

## 7. Existing controls (for the baseline)

| Existing control | Failure code(s) it already catches | Confirmed deployed & effective? |
|---|---|---|
| `< IAM access review >` | `< PROHIBITED_CAPABILITY_EXPOSURE? >` | `< >` |
| `< >` | `< >` | `< >` |

## 8. Coverage check

- Any workflow fact expressible by **no** frozen capability group? `< list — architecture-coverage gap >`
- Any known problem class mapping to **no** frozen failure code? `< list >`
