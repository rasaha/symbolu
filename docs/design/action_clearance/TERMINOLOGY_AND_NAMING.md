# Terminology & Naming Policy (permanent)

## Why a policy is mandatory

The audit established that **"ACP" is overloaded across four distinct concepts** plus one vocabulary
word, and that "Action Clearance Protocol" appears nowhere in the repo. Without a naming policy the new
capability would collide with all of them.

| Overloaded term | Meaning | Owner | Kept as-is |
|---|---|---|---|
| ACP / Autonomous Control Plane (robotics) | deterministic robotics decision-and-authorization runtime; frozen stdlib core | Robotics | ✅ retains name & compatibility surface |
| ACP / AI Control Plane (umbrella) | 3-layer enterprise product story | Ugence platform | ✅ docs only |
| Autonomous Control Plane (console sibling) | `CLEAR`/`HOLD` gate over infra signals | `ugence_console_api` | ✅ unchanged |
| ACP DB (`acp_db`) | DB operational-safety adapter | `cer_v0_3` | ✅ unchanged |
| **Action Clearance** (this capability) | neutral pre-execution clearance of an authorized action | **new** | new name, defined here |

## Mandatory naming

| Aspect | Value |
|---|---|
| Technical capability | **Action Clearance** |
| Python namespace | `ugence_action_clearance` |
| Distribution | `ugence-action-clearance` |
| Package directory | `packages/capabilities/action-clearance` |
| Contract/policy version | `action_clearance.v1` |
| Fingerprint domain tag | `action_clearance` (never `acp`) |

This mirrors the repository's established `ugence-<kebab>` / `ugence_<snake>` /
`packages/capabilities/<kebab>` convention (`ugence-model-selection`, `ugence-decision-authority`).

## Acronym-collision policy (explicit)

Bare **"ACP"** is **prohibited** in:

- package names and distribution names,
- import paths / module names,
- public class names,
- public type names,
- reason-code prefixes,
- persistent record names,
- new technical documentation headings.

Consequences:

1. Public types use the `Clearance*` / `TrustedSignal` family (`ClearanceRequest`, `ClearanceResult`,
   `ClearanceReceipt`, `ClearanceStatus`, `ClearanceReasonCode`) — none contains "ACP".
2. Reason codes are UPPER_SNAKE with **no** `ACP_` or `AC_` prefix (e.g. `AUTHORIZATION_EXPIRED`, not
   `ACP_AUTHORIZATION_EXPIRED`).
3. Persistent records are `ClearanceReceipt` (not `ACPRecord`); `result_id` uses the `acr_` content-hash
   prefix (a hash label, not the acronym).
4. New headings say "Action Clearance", never "ACP".

## No identity with robotics

The new capability must **not** alias, re-export, or claim object identity with
`symbolu_robotics.autonomous_control_plane`. Specifically:

- no `import ... as` alias binding either name to the other,
- no `sys.modules` identity preservation between them,
- no shared class objects,
- the robotics `acp/ACP_V1_FREEZE.md` digest and the `acp_k8s_integrated` pin are untouched.

Robotics keeps "Autonomous Control Plane" and its existing compatibility surface; Action Clearance is a
sibling capability, related only as an *engineering-pattern reference* (see
[`EXISTING_IMPLEMENTATION_DISPOSITION.md`](EXISTING_IMPLEMENTATION_DISPOSITION.md)).

## Case-collision hazard

`ACP/` (AI Control Plane docs) and `acp/` (robotics docs) already differ only by case. Action Clearance
introduces **no** new top-level directory near those names; all new material lives under
`packages/capabilities/action-clearance/` (future code) and `docs/design/action_clearance/` (this
design), both unambiguous.
