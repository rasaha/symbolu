# Status and Reason Codes

> Machine-readable: `reason_codes.json`.

## Statuses (exactly four)
`CLEAR`, `HOLD`, `BLOCK`, `ESCALATE`. Combined least-permissive-wins with
precedence **`BLOCK > ESCALATE > HOLD > CLEAR`**. There is no `DENY` — ActionGate
owns authorization denial. `STALE`/`EXPIRED`/`INCOMPLETE`/`CONFLICT`/`UNTRUSTED`
are **reason codes**, not statuses.

| Status | Execution | Retry | Fresh request | Human | Reauth | Authorization still valid |
|---|---|---|---|---|---|---|
| CLEAR | not yet (downstream must validate receipt + reserve) | — | — | — | — | yes |
| HOLD | no | yes (after condition clears) | yes | no | no | yes |
| BLOCK | no | no | yes | no | maybe | unchanged (never broadened/replaced) |
| ESCALATE | no | no | yes | yes | maybe | unchanged |

## Reason codes
All catalog entries are `CORE_NEUTRAL` (UPPER_SNAKE, no `ACP`/`AC_` prefix). See
`reason_codes.json` for each code's default status. Profile-specific (e.g.
`GITHUB_*`), workflow-only (`DISPATCH_DUPLICATE`, `RECEIPT_SUPERSEDED`), and
`UNNECESSARY` (`DENY`, `ACP_*`) codes are **not** part of the neutral core.

## Failure handling
Expected operational conditions produce fail-closed **results**
(`RESULT`/`RETRYABLE_ERROR`/`NON_RETRYABLE_ERROR`/`ESCALATION`/
`UPSTREAM_REAUTHORIZATION_REQUIRED`). Only programming errors and malformed
contracts raise typed **exceptions**.
