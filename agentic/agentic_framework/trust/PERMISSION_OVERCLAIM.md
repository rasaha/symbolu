# Permission Overclaim Observable (Phase 2 — deterministic)

**Status:** PROVISIONAL · advisory-only · shadow-recorded. No ML. No production behaviour
change. First Phase 2 observable.

## Definition

Detect when a requested action **claims permission/scope/authority/capability beyond what is
explicitly granted**. Six concrete failure modes:

| Example | Violation kind |
|---|---|
| admin action without admin grant | `authority_escalation` |
| cross-tenant access claim | `cross_tenant` |
| capability escalation | `capability_escalation` |
| scope escalation | `scope_escalation` |
| authority escalation | `authority_escalation` |
| policy bypass request | `policy_bypass` |

## Taxonomy placement (and why)

- **ObservableType = VALIDATOR.** It is an independent check on the action, not a model claim
  (TRUST_SIGNAL) nor a deterministic correctness kill-switch (HARD_VETO — that is the already
  mapped `forbidden_capability`).
- **EvidenceStatus = PROVISIONAL.** Per the kernel rules a PROVISIONAL validator is
  **confirm-only — it can escalate to CONFIRM but never BLOCK**, regardless of its verdict.
  This is the "advisory only initially" guarantee, enforced by `decision._proposed`, not by
  this module.
- Verdict is computed deterministically: `UNSAFE` for *severe* overclaims (policy bypass,
  cross-tenant, admin/root authority escalation), `UNSURE` for milder ones, `SAFE` when the
  request is within grant. While PROVISIONAL both `UNSAFE` and `UNSURE` collapse to CONFIRM;
  the `UNSAFE`/`UNSURE` split only matters **after** promotion to PROVEN (then severe → BLOCK).

## Determinism (no ML)

Pure set/rank/glob comparison of a **requested** permission profile against a **granted** one:

- `capability_escalation` — `requested_capabilities ⊄ granted_capabilities`.
- `authority_escalation` — `rank(requested_authority) > rank(granted_authority)` over a fixed
  ordering `none < read < write < execute < admin < root`.
- `scope_escalation` — a requested resource pattern not covered by any granted scope glob
  (`fnmatch`).
- `cross_tenant` — `requested_tenant` present and not in `granted_tenants`.
- `policy_bypass` — an explicit bypass request flag.

No thresholds learned, no scores fitted; identical inputs → identical output.

## Inert by default (no production behaviour change)

The observable is appended to the trust observation set **only when an explicit
`PermissionContext` is supplied** (via `MCPToolCall.permission_context`). Production tool calls
do not carry one today, so:

- it is **not** added to the observation list → does not change the recorded trust decision;
- legacy still decides and executes; the trust core remains authoritative only for the
  JEPA-relax path, which this observable never touches;
- existing parity/shadow-volume corpora (no permission context) are unchanged.

When a context *is* supplied (the validation corpus, or a future caller), the observable
participates in **shadow mode** (recorded trust decision), **parity reporting** (a
`permission_overclaim` driver), **audit persistence** (`trust_shadow.drivers` +
`trust_observations`), and **shadow_report aggregation** (mismatch-by-driver), where its
stricter-only escalation is classified **`intended`** (advisory escalation), never
`unsafe_relaxation` (it only ever escalates, never relaxes).

## Participation summary

| Surface | How |
|---|---|
| shadow mode | included in `build_parity_observations` → `shadow_compare` recorded decision |
| parity reporting | `permission_overclaim` appears as a driver; stricter escalation = `intended` |
| audit persistence | flows into `trust_shadow.drivers` and `trust_observations` (durable, hash-chained) |
| shadow_report | aggregated under "mismatch by driver" with the entropy/gap slices |

## Promotion criteria (PROVISIONAL → PROVEN)

Promote (which lets severe overclaims BLOCK instead of only CONFIRM) only when **all** hold
over a real shadow window:

1. **Zero unsafe_relaxation, zero unintended** in `shadow_report` with the observable active.
2. **Precision on real traffic:** of the calls where `permission_overclaim` fired and a human
   adjudicated (under TRUST_CORE the CONFIRM goes to a human), the **human-approval rate is low**
   (i.e. the observable's escalations are usually upheld, not overridden) — the same
   human-adjudication signal the canary runbook collects for JEPA.
3. **Rule audit:** every violation kind has been observed firing correctly on the validation
   corpus AND on real traffic, with no false-positive class traced to a deterministic bug.
4. **Grant provenance trusted:** the `granted_*` inputs come from an authoritative source
   (not model-supplied), so the comparison cannot be gamed.
5. **Reviewed + signed off** exactly as the JEPA demotion was (AUTHORITY_REVIEW process).

Promotion is a one-line evidence change (`EvidenceStatus.PROVISIONAL → PROVEN`) plus the
severe-verdict→BLOCK behaviour it unlocks — itself parity-gated and differential-checked. Not
done here.
