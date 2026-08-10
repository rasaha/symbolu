# 8. Pilot Execution Checklist

## Pre-flight
- [ ] Package pinned: `tap-e7-base-companion/1.2.0`; record commit + `package_root`.
- [ ] Recompute config fingerprint; MUST equal `d01e466e…`; else STOP.
- [ ] Reference engine (Impl B) present and required **read-only**; no modification.
- [ ] Sampling seed + per-domain quotas frozen and recorded.
- [ ] Reviewer roster confirmed; blinding tooling verified.
- [ ] "No production decision uses TAP-E7" attestation signed.

## Per batch
- [ ] Draw sample; snapshot artifact hashes.
- [ ] Reviewers label blind; capture category + confidence + time.
- [ ] Run TAP-E7 read-only; store AssuranceRecords + `projection_pi_sha256`.
- [ ] Verify package composite hash unchanged before/after (immutability).
- [ ] Adjudicate; file taxonomy classes; open tracked items for H*/V*.
- [ ] Replay 10% subset; confirm identical outputs.
- [ ] Update daily + domain summaries.

## Close-out
- [ ] Generate overall report + executive dashboard from `results/metrics.json`.
- [ ] Confirm 0 protocol/package/impl changes during pilot.
- [ ] Classify all findings into disposition buckets (post-pilot analysis).
- [ ] Publish with commit, fingerprint, package_root, and the read-only attestation.

## Abort conditions
- Fingerprint drift, package mutation, or nondeterministic replay → halt, void batch, investigate.
