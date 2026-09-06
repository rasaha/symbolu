# Ugence model, prompt and agent lifecycle promotion — scoping record and ratification

**Status:** ratified 2026-09-05 by the repository owner on LP-1 only:
**`DEFER_TO_WAVE_5`**. This record authorizes no code change, creates no package,
adds no dependency and amends no package port, test or manifest. Its one
consequence is the in-place correction of the sequencing ADR's lifecycle row,
count row and wave logic, made the same day. Sequenced by `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md`
(wave 4, line 61: "Model Selection `ExecutableRegistry` and Agent Constitution
lifecycle already cover parts; new package only for the promotion state machine
`[I]`"). It tests that premise first, maps what lifecycle vocabulary exists, and
poses the five owner decisions to rule before any code.

Evidence labels: `[V]` verified against this repository at commit `2c64d31f`,
`[I]` inferred, `[R]` requires ratification, `[G]` gap.

## 1 — The question

Does the sequencing ADR's premise hold — that two existing packages already own
the lifecycle registries, so only a promotion state machine is new? **Half of it
does not.** Model Selection's registry tracks *whether a model can be executed*,
not whether anyone approved it for a stage; and all three Agent Constitution
packages explicitly disclaim lifecycle authority. They carry a lifecycle *label*;
they own no lifecycle. The row's scope is therefore larger than "only the state
machine", and that is the first thing to rule.

## 2 — What the repository already fixed

| Finding | Where |
|---|---|
| `ExecStatus` is an executability-evidence ladder — `DECLARED`, `ENUMERATED`, `AUTHENTICATED`, `EXECUTION_VERIFIED`, `DISABLED` — each step meaning "a provider fact was observed", none meaning "an owner promoted this" `[V]` | `packages/capabilities/model-selection/src/ugence_model_selection/registry.py:19-24` |
| All three Agent Constitution packages declare `OD-C4=A`: "not a lifecycle authority — no revocation seam", "No role lifecycle authority of any kind", "No role lifecycle authority" `[V]` | `agent-constitution-activation/README.md:40`; `agent-constitution-policy/README.md:89`; `agent-constitution-conformance/README.md:87` |
| What they do carry: a `lifecycle_state` label on the policy's own metadata envelope, admitted set `DRAFT`, `APPROVED_ACTIVE`, `SUPERSEDED`, `WITHDRAWN`, of which exactly one resolves; no transition function exists `[V]` | `agent-constitution-policy/.../identifiers.py:81-97`; `policy.py:222-268`; `README.md:34` |
| The registry explicitly defers this row: "Not a lifecycle authority. The promotion state machine is wave 4" `[V]` | `packages/integration/ai-system-registry/README.md:113-114` |
| No package owns a `promote`, `approve_for_environment` or model `rollback` transition. The only `rollback` code is cloud-scaling's infrastructure rollback, "never assumed automatically safe", and incident-response "never revokes, executes, rolls back" `[V]` `[G]` | `cloud-scaling-operations/.../rollback_coordinator.py:1-6`; `incident-response/README.md:10` |
| "Lifecycle" is already used in a third sense: Risk Authority's *authority* lifecycle of TTL, epoch and targeted revocation `[V]` | `risk-authority-status-runtime/README.md:14` |
| The binding already carries an opaque `deployment_environment_ref`: "no environment enumeration is ratified anywhere in the repository, so none is invented" `[V]` | `governance-contracts/.../contracts/system_identity.py:63-64`, `:288` |
| "Promotion" as a noun is unreserved; the one README use is a ratification act, not a package `[V]` | `durable-execution/README.md:193` |
| The contracts-only shape has three wave 4 precedents `[V]` | `data-use-admission`, `vendor-dependency`, `agent-assurance-evidence` |

The sequencing ADR's prohibition (line 85) is satisfied by any name that avoids
"lifecycle authority" — a noun three packages disclaim and a fourth uses for
authority TTL.

## 3 — A first slice, by analogy `[I]`

Following the three wave 4 packages: a `StageDeclaration` binding one
`AssessedSystemBinding` re-exported from governance-contracts, a declared stage as
an **uninterpreted label** (following DE-3, VR-3 and AE-3), an opaque
`environment_ref` recorded alongside the binding's own `deployment_environment_ref`
and never compared to it, a `Validity` window and an optional `supersedes`.
Refusal reasons for a blank label, a look-alike binding, and a mismatched tenant.
Pure selectors, in-force first. One read-only Protocol, no implementation.

**Structurally unable:** no transition table, no promote, no approve, no rollback,
no environment enumeration, no clock; and no import of Model Selection, Agent
Constitution or Risk Authority. A state *machine* is exactly what this slice would
not be; it records that a stage was declared and by what supersession history.

## 4 — Ratified decision, and the four deferred with it

| # | Decision | Ruling |
|---|---|---|
| **LP-1** | Given the contradicted premise, is the row re-scoped in wave 4 or deferred to wave 5? | **`DEFER_TO_WAVE_5`.** Wave 4 closes at four packages. The sequencing ADR's line 61, its count row and its wave logic are corrected in place so the row is no longer described as "only the promotion state machine"; the row re-enters wave 5 as a scoping item, not a hardening item, and LP-2 to LP-5 are ruled there. |
| **LP-2** (deferred) | The noun and package name. | Not "lifecycle authority" (disclaimed three times, and Risk Authority's TTL sense); not "registry" (the inventory's). "stage-declaration" or "promotion-record" name what is recorded. |
| **LP-3** (deferred) | Is a stage a declared label or an enforced state machine? | A label follows every wave 4 precedent and needs no ratified stage set; a state machine needs a ratified set of stages *and* transitions, and an owner to authorize each, which is an approval-workflow concern under D-2. |
| **LP-4** (deferred) | How does a declared stage relate to `deployment_environment_ref` on the binding? | Recorded separately and never compared keeps the binding's opaque token opaque; equating them would make this package the first to interpret an environment reference, which `system_identity.py:63` says nobody has ratified. |
| **LP-5** (deferred) | Does any neutral type land in governance-contracts first? | A neutral `StageLabel` would follow DE-5, VR-5 and AE-5; reusing nothing lands nothing, and a fourth one-field label may be the point at which a shared uninterpreted-label base is worth ruling on instead. |

## 5 — Next step

None in wave 4. When wave 5 opens this row, rule LP-2 to LP-5 against the findings
above before any package. Nothing is implemented by this record.
