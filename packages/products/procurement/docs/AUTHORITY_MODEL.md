# Authority Model

Ugence Procurement enforces four hard authority boundaries. Each is enforced in
**types and services**, not merely described here. The governing principle:
authority only ever flows forward through explicit, separately-authorized steps,
and constraints may **narrow but never broaden**.

## The four boundaries

| # | Boundary | Meaning |
|---|---|---|
| 1 | recommendation ≠ decision | An advisory recommendation never auto-becomes a binding decision. |
| 2 | decision ≠ authorization | A human decision does not itself authorize a supplier action; authorization is a separate, neutral step bound to the exact approved purchase. |
| 3 | authorization ≠ execution | Nothing is dispatched to a supplier as a side effect; dispatch is an explicit, separate call. |
| 4 | constraints narrow, never broaden | Authorization is bound to the exact approved supplier / budget / amount and may add constraints/obligations, but can never enlarge scope. |

## Who may do what

| Actor | May | May NOT |
|---|---|---|
| Deterministic policy (AI-free) | Produce an **advisory** recommendation | Decide, authorize, or dispatch |
| Authenticated authorized **human** approver | Record the binding **decision** (approve/reject/hold/defer) | Bypass validation or authorization |
| Kernel authorization (control plane) | Grant `AUTHORIZED` / `AUTHORIZED_WITH_CONSTRAINTS`, or `DENIED` / `EXPIRED` | Broaden the approved purchase |
| Explicit dispatch step | Send the authorized action to the supplier | Fabricate a business outcome |

No AI or automation may approve. Automation is confined to producing advisory
signals and deterministic transport; the binding decision is reserved to a human.

## How each boundary is enforced

- **1 — recommendation is advisory.** `recommend()` calls the kernel `CaseRecommendationService` with `generator_type=DETERMINISTIC_POLICY`; the recommendation record is distinct from any decision. Recommendation and approval vocabularies are separate types (`PurchaseRecommendation`, `PurchaseApproval`) mapped through `RECOMMENDATION_TO_PROPOSED` and `APPROVAL_TO_DECISION`.
- **2 — only a human decides; authorization is separate.** `decide()` requires an `AuthorityContext` of `AuthorityType.HUMAN_APPROVER`. Authorization is a later, distinct step (`authorize()`) run by the kernel `ActionAuthorizationService` consulting the `BudgetAuthorityAdapter`.
- **3 — dispatch is explicit.** `authorize()` and `dispatch_and_observe()` are separate calls; creating and authorizing an action request performs no supplier I/O. Execution only happens when dispatch is explicitly invoked.
- **4 — bound and narrowing.** The action request for a purchase-order carries the exact `amount`, `supplier_id`, and `budget_id` from the approved request. The CER binding ties authorization to that exact action request. `BudgetAuthorityAdapter` may return `AUTHORIZED_WITH_CONSTRAINTS` (attaching a senior-approval obligation) — adding conditions, never expanding scope.

## Fail-closed corollary

Any unknown, malformed, stale, mismatched, timed-out, or unavailable condition
never becomes an authorization or a success. A supplier transport acknowledgement
is **not** business completion. See
[SECURITY_AND_FAILURE_MODEL.md](SECURITY_AND_FAILURE_MODEL.md).
