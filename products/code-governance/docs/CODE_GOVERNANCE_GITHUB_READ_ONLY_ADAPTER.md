# GitHub Read-Only Adapter

> A single concrete GET-only GitHub adapter. It reads only the minimum needed for
> shadow governance, verifies the returned artifact identity against the governed
> change, and **fails closed** on any mismatch. It has no write method and no write
> client. Machine-readable companion: `docs/github_signal_mapping.json`.

## Read endpoints

- `GET /repos/{owner}/{repo}/pulls/{number}` — PR state, draft, base/head SHA
- `GET /repos/{owner}/{repo}/commits/{head_sha}/check-runs` — required-check status

All requests go through the read-only transport (GET only). The adapter exposes no
`merge`, `approve`, `close`, or write method.

## Identity verification (fail closed)

The adapter verifies the returned repository, PR number, base SHA, and head SHA
match the governed change. A repository/number/base mismatch is
`SOURCE_IDENTITY_MISMATCH`; a superseded head SHA is `ARTIFACT_IDENTITY_MISMATCH`
(the prepared action is stale). Both yield a fact-free `FAILED` result — never a
positive signal.

## Signal mapping

| GitHub fact | Canonical signal | Consistency |
|---|---|---|
| artifact identity still matches | `ARTIFACT_IDENTITY` | `AUTHORITATIVE` |
| PR open and not draft | `TARGET_AVAILABILITY` | `EVENTUALLY_CONSISTENT` |
| required checks completed + successful | `REQUIRED_CONTROL` | `EVENTUALLY_CONSISTENT` |

Only canonical Action Clearance `SignalType` values are used. A GitHub fact with no
canonical signal type stays product-level advisory and is documented as future
profile work — Action Clearance is never modified and no conflicting neutral signal
is invented.

## Permission minimization

The adapter requires only read permissions (`metadata:read`,
`pull_requests:read`, `checks:read`, `statuses:read`) and never requires
`contents:write`, `pull_requests:write`, `checks:write`, `statuses:write`,
`issues:write`, `actions:write`, or `administration:write`. No real GitHub App is
created or configured in this phase — the permission set is documentation +
tests only.

## Live use is opt-in

The offline demo and all tests use a deterministic fake GET-only transport. An
optional live read-only smoke exists but is skipped by default and only runs with
an explicit environment flag, an allowlisted repository/PR, and externally supplied
read-only credentials. It performs GET-only requests, prints no credential data,
and makes no mutations.
