# Plan Replay (P3D)

Uses `POST /plans/replay`. Shows the expected vs replayed plan fingerprints, the
match state (a mismatch is a prominent integrity error, never suppressed), plan
state, AWC version and API contract, and any diagnostics. Persistent
clarification: *Replay verifies deterministic plan reconstruction. It does not
rerun or replay agent execution.* The screen also exposes the deterministic
export bundle (`GET /scenarios/{id}/export`) with a manifest summary and a
client-side JSON download — synthetic data only, no source/secrets/paths.
