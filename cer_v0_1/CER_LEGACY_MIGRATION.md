# CER Legacy Migration (Deliverable 3)

How the ActionGate identity change is handled as a **frozen-contract change**: version increment, legacy preservation, migration behavior, and non-confusability. Grounded in the Stage-1 commit.

Labels: `FACT` (implemented + tested) · `RECOMMENDATION`.

---

## 1. What changed (and what did not)

`FACT`. A new **identity profile `v2`** was added to ActionGate, additively:
- `projection.project_action_payload / action_canonical_bytes / action_hash` gained `identity_profile` (default `"v1"`).
- `gate.evaluate`, `gate._approver_satisfied`, `approval.verify_approval` thread `identity_profile` through (default `"v1"`).
- `canon_profile` added `ENVELOPE_SCHEMA_VERSION_V2 = "2.0.0"`, `IDENTITY_PROFILES = {v1, v2}`, `DEFAULT_IDENTITY_PROFILE = "v1"`.

**Nothing about v1 changed.** The default path is byte-identical to the historical behavior. The change is opt-in: only an explicit `identity_profile="v2"` alters anything.

## 2. Version increment

`FACT`. v1 uses `envelope_schema_version="1.0.0"`; v2 uses `"2.0.0"`. Because `domain_digest` folds the schema version into the hash frame, a v1 and a v2 `action_hash` of the *same* envelope are **always different values**. Migration is therefore a namespace switch, not an in-place mutation.

## 3. Legacy preservation

`FACT`:
- The full pre-existing ActionGate suite passes unchanged: **183 pre-existing tests + 12 new v2 tests = 195 passed.**
- `fixtures/conformance_vectors.json` (historical) is **untouched** — no historical vector was edited or removed. New CER/v2 vectors live in `cer_v0_1/conformance/vectors.json` (separate file).
- Existing callers that do not pass `identity_profile` get v1 automatically.

## 4. Migration behavior

`RECOMMENDATION` (how an operator adopts v2):
- Producers/adapters emit CERs; the harness authorizes with `identity_profile="v2"`.
- Approvals and evidence must be **bound under v2** (their `bound_to`/`action_hash` = the v2 digest). An approval built under v1 will NOT verify under v2 and vice-versa — proven by `test_approval_binds_within_profile_and_not_across`. This is intentional fail-closed behavior: an approval for a v1 identity cannot be silently reused under v2.
- No dual-profile action may be evaluated ambiguously: a decision is made under exactly one `identity_profile`; the profile is part of the decision context.

## 5. Non-confusability (old vs new)

`FACT` (tested):
- `test_v1_and_v2_are_domain_separated`: same envelope → different digests under v1 vs v2.
- `test_approval_binds_within_profile_and_not_across`: an approval bound under v2 raises `ActionHashMismatchError` when checked under v1.
- Exact-action binding is **not weakened**: within v2, any identity-bearing change still changes the digest and breaks a stale approval/evidence binding (`test_v2_identity_bearing_change_alters_digest`).

## 6. Rollback

`RECOMMENDATION`. The change is fully reversible: removing the `identity_profile` arguments (or leaving them at the default) restores exact v1 behavior. No data migration is required because v2 is a parallel namespace, not a rewrite of v1 identities.

## 7. Repository-impact metric (Stage 1)

`FACT` (git diff --stat, `action_gate_ref/`): projection.py +89/-, gate.py ~+9, approval.py ~+8, canon_profile.py +8 → **4 files changed, ~118 insertions, 13 deletions**, plus a new 100-line test file. **ACP, Context Minimization, and the Agent Runtime were not modified in Stage 1.**
