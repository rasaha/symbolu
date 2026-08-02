# Pilot Evidence Pack

> A deterministic, offline-verifiable evidence pack. It binds every artifact by
> fingerprint, contains references rather than raw source data, excludes
> credentials, and fails verification when modified or incomplete.

## Structure

Sections: manifest, pre_pilot_freeze, amendments, candidate_selection, evaluations,
evidence_classification, reviewer_protocol, annotations, reviewer_queue,
checkpoints, adverse_cases, metrics, calibration, replay, security, integrity,
limitations, readiness_verdict — plus a `verification_manifest` (per-section record
ids + counts) and a top-level `pack_fingerprint`.

## Offline verification

`verify_pilot_evidence_pack` requires no store connection. It checks the pack
version, recomputes the pack fingerprint over the body (any modified field fails),
checks each section's declared count against its length (missing/extra records
fail), requires the execution-disabled marker, and scans for credential-like values
and prohibited keys (authorization headers, raw responses, incident notes) — any of
which fails verification. The pack excludes credentials, raw authorization headers,
full private incident notes, and unnecessary identity data.
