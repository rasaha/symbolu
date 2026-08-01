# Customer Policy-Gap Report (§4) — Account-Takeover Vertical Slice

Compare the customer's actual business process to the frozen reference Account-Takeover
Policy Pack **before** replay. Any customer-specific change creates a **new Policy Pack
version** — never modify the frozen reference pack in place.

| Dimension | Reference behavior | Customer behavior | Mapping decision | Unresolved difference | Replay-safe? |
|---|---|---|---|---|---|
| Controlled action | `TRANSFER` (value transfer proposal) | | | | |
| Completion action | transfer is the completion node | | | | |
| Required event types | credential reset, new device, beneficiary add, transfer | | | | |
| Optional event types | limit increase | | | | |
| Mandatory entity relationships | same account; transfer beneficiary = newly added beneficiary; transfer device = newly enrolled device | | | | |
| Ordering requirements | reset/device/beneficiary before transfer | | | | |
| Time window | takeover window `max_gap = 1000` units | | | | |
| Amount thresholds | (none in reference; add if customer requires) | | | | |
| Legitimate recovery workflow | account recovery covers reset + device | | | | |
| Bank-assisted workflow | covers beneficiary + transfer (scoped) | | | | |
| Trusted evidence sources | case management, payment workflow | | | | |
| Consequence mappings | would-complete → `WOULD_HOLD_FOR_REVIEW`; hard violation → `DENY`; etc. | | | | |
| Policy owners | business/control/technical owners | | | | |
| Replay reviewers | fraud-ops / risk | | | | |

**Decision:** ☐ Reference pack fits as-is · ☐ New pack version required (id/version: ______) · ☐ Replay cannot proceed safely (reason: ______)

> Do not silently assume the reference policy matches the customer's actual business
> process. Unresolved differences that touch a **mandatory** relationship block replay
> (they would change which sequences complete).
