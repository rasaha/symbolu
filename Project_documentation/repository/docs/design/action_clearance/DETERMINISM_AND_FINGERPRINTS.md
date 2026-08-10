# Determinism & Fingerprints

The neutral evaluator is a deterministic pure function. It mirrors the repository's established
canonical-hash pattern (`symbolu_robotics/.../identity.py`, `ugence_decision_authority.common.canonical_hash`,
`ugence_governance_provider_framework.fingerprint`) under a **new** `action_clearance` domain tag.

## Canonical serialization

One canonical form for request, normalized signal bundle, policy input, result, effective constraints,
obligations, and reason codes:

- JSON with **sorted keys**, compact separators `(",", ":")`, UTF-8, `ensure_ascii=true`,
  `allow_nan=false`;
- floats normalized (`NaN`/`Inf` rejected, `-0.0 → 0.0`);
- mapping keys sorted; **sequence order preserved** except reason codes, which are sorted by the
  canonical reason-order rule before serialization;
- enums encoded by their string value; timestamps in one canonical form (integer epoch-nanoseconds or
  RFC3339 — pick one at implementation and freeze it);
- bytes encoded deterministically (hex).

## Fingerprints (SHA-256, domain-separated)

Domain separation prefix: `action_clearance\x1f<domain>\x1fv1\x1f` then the canonical JSON, hashed with
SHA-256.

| Fingerprint | Domain | Included | Excluded |
|---|---|---|---|
| `action_fingerprint` | `action` | `action_type`, `target_ref`, `operation`, authorized-action identity fields | storage metadata |
| `request_fingerprint` | `request` | all `ClearanceRequest` fields incl. grouped sub-structures and `evaluation_time` | none (the whole request) |
| `signal_bundle_fingerprint` | `signal_bundle` | each normalized `TrustedSignal`'s fingerprinted fields, in `signal_id` order | adapter extension maps not marked fingerprinted |
| `result_fingerprint` | `result` | every `ClearanceResult` field marked fingerprinted in [`RESULT_AND_RECEIPT_CONTRACT.md`](RESULT_AND_RECEIPT_CONTRACT.md) | all `ClearanceReceipt` storage metadata (`receipt_id`, wall-clock `issued_at`, `receipt_state`, `superseded_by`, dispatch linkage) |

`result_id = "acr_" + result_fingerprint`.

## Prohibited (would break determinism)

- random values, `uuid` in the core,
- implicit clock reads,
- network calls,
- environment-variable reads,
- mutable global policy (policy is passed in),
- unordered reason output,
- unstable map serialization.

## Semantic-equivalence harness (design only)

For future implementation, a capture harness records per scenario a JSON row:

```json
{
  "scenario_id": "…",
  "request": { "…": "…" },
  "signal_bundle": { "…": "…" },
  "status": "CLEAR | HOLD | BLOCK | ESCALATE",
  "reason_codes": ["…"],
  "effective_constraints": ["…"],
  "obligations": ["…"],
  "valid_until": "…",
  "exception": "MalformedRequestError | UnsupportedProfileError | null",
  "request_fingerprint": "…",
  "signal_bundle_fingerprint": "…",
  "result_fingerprint": "…"
}
```

Two implementations (or two versions) are **semantically equivalent** iff, across the full
[`acceptance_scenarios.json`](acceptance_scenarios.json) corpus, `status`, `reason_codes` (as a set),
`effective_constraints`, `obligations`, `valid_until`, `exception`, and all four fingerprints match. The
harness is **not built** in this phase.
