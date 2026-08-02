# Determinism and Fingerprinting

The evaluator is deterministic: no random values, no clock reads, no network, no
environment reads, no mutable global policy, no unordered reason output, no
unstable map serialization.

## Canonical normalization
JSON with sorted keys, compact separators `(",", ":")`, `ensure_ascii=True`,
`allow_nan=False`; strings NFC-normalized; datetimes → canonical RFC3339 UTC with a
`Z` suffix; enums by value; `-0.0 → 0.0`; `NaN`/`Inf` rejected; unsupported /
nondeterministic types raise `ValidationError` (never silently stringified).

## Domain-separated SHA-256
Preimage: `action_clearance \x1f <domain> \x1f v1 \x1f <canonical_json>` (0x1F unit
separator). Domains: `signal_content`, `signal_provenance`, `signal_bundle`,
`action`, `request`, `result`.

| Fingerprint | Domain | Excludes |
|---|---|---|
| `signal.content_fingerprint` | `signal_content` | provenance/adapter extension |
| `provenance.fingerprint` | `signal_provenance` | — |
| `bundle.fingerprint` | `signal_bundle` | signal wire order (sorted by `signal_id`) |
| `action.computed_fingerprint` | `action` | storage metadata |
| `request.fingerprint` | `request` | — |
| `result.result_fingerprint` | `result` | itself + all receipt storage/lifecycle metadata |

`result_id = "acr_" + result_fingerprint`. Reason codes are canonically ordered
(sorted) before fingerprinting, so input order never changes the result
fingerprint. Caller-supplied ids (`request_id`) are carried but never make
semantically identical evaluations produce different result fingerprints beyond
the request-fingerprint field the design includes.
