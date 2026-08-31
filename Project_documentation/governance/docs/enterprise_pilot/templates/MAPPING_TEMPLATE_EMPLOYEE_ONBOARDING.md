# Mapping Template — Employee Onboarding (BLANK)

> **Blank template.** Fill in with the enterprise workflow owner. Do **not** commit
> real data into this repo copy. Every `< >` is a placeholder. Leave blank or write
> `MISSING` when the source does not carry the fact — never invent a value.
>
> Maps onto the **frozen** architecture
> ([`ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md`](../../../actiongate/ACTIONGATE_GOVERNANCE_ARCHITECTURE_POSITION.md));
> field meanings in [`SOURCE_ADAPTER_SPECIFICATION.md`](../SOURCE_ADAPTER_SPECIFICATION.md).
> Onboarding spans HR → IAM → device/SaaS provisioning; capability-space and
> integration-closure are the central groups.

## 0. Header

- Workflow name: `Employee onboarding (hire → access → provisioning)`
- Enterprise workflow owner: `< >`
- Data owner: `< >`
- Date / template version: `< >`
- Scope confirmed read-only, historical, shadow: `< yes/no >`

## 1. Participating systems

| System | Role in workflow | Read-only access method |
|---|---|---|
| `< HRIS >` | `< hire record / role >` | `< >` |
| `< IAM >` | `< granted vs approved access >` | `< >` |
| `< Device / MDM >` | `< device entitlement >` | `< >` |
| `< SaaS apps >` | `< app access >` | `< >` |

## 2. Evidence mapping (source fact → capability group)

| Source fact | Capability group | Payload key(s) | status | verification | authority_role |
|---|---|---|---|---|---|
| `< manager / HR approval >` | `IDENTITY_AUTHORITY` | `< approver >` | `< >` | `< >` | `< AUTHORITY_BEARING? >` |
| `< role / job function basis >` | `PURPOSE_POLICY_BASIS` | `< objective >` | `< >` | `< >` | `< >` |
| `< granted vs role-approved access >` | `CAPABILITY_SPACE` | `available, permitted, prohibited, revoked, approval_required, approvals_present` | `< >` | `< >` | `< >` |
| `< access provisioning policy versions >` | `DECISION_DERIVATION` | `policy_versions` | `< >` | `< >` | `< >` |
| `< onboarding target state per system >` | `INTEGRATION_CLOSURE` | `intended[], observed[], required_closure[], satisfied_closure[]` | `< >` | `< >` | `< >` |
| `< >` | `< >` | `< >` | `< >` | `< >` | `< >` |

## 3. Decisions

| decision_id | actor | effect | supporting_refs | reason_code |
|---|---|---|---|---|
| `< >` | `< >` | `< allow/allow_with_constraints/widen/defer/deny >` | `< >` | `< >` |

## 4. Executions

| execution_id | system | subject_key | authorized_form | executed_form | resulting_state |
|---|---|---|---|---|---|
| `< >` | `< IAM >` | `< principal:... >` | `< >` | `< >` | `< >` |
| `< >` | `< SaaS >` | `< principal:... >` | `< >` | `< >` | `< >` |

## 5. Cross-system dependencies

| from_system | to_system | requires_subject | satisfied | stale | description |
|---|---|---|---|---|---|
| `< IAM >` | `< HRIS >` | `< approval:... >` | `< >` | `< >` | `< access requires approved hire >` |

## 6. Integration / closure (all systems provisioned to intended state)

| intended {system,key,value} | observed {system,key,value} | required_closure | satisfied_closure |
|---|---|---|---|
| `< IAM access active >` | `< >` | `< access_consistent >` | `< >` |
| `< >` | `< >` | `< >` | `< >` |

## 7. Existing controls (for the baseline)

| Existing control | Failure code(s) it already catches | Confirmed deployed & effective? |
|---|---|---|
| `< IAM access review >` | `< PROHIBITED_CAPABILITY_EXPOSURE? >` | `< >` |
| `< joiner/mover/leaver process >` | `< >` | `< >` |
| `< >` | `< >` | `< >` |

## 8. Coverage check

- Facts expressible by **no** frozen capability group? `< list >`
- Known problem classes mapping to **no** frozen failure code? `< list >`
