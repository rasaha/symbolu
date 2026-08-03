# Oracle-verified minimization (Mode B)

`minimize_context(...)`. **Requires an `InvarianceOracle`.**

## Algorithm

1. **Protection.** Resolve the protected set (explicit ids ∪ `protected=True` units ∪
   a `ProtectionResult`/`ProtectionProvider`'s effective-protected set). A provider
   that raises or returns garbage → **protect everything** (fail closed).
2. **Base evaluation.** Evaluate the oracle on the *full* context. If it raises, is
   malformed, expired (inclusive; or missing `evaluation_time` when a horizon is
   supplied), or correlation-missing/mismatched → **full fallback**. See
   `INVARIANCE_CONTRACT.md`.
3. **Structural pass.** Deduplicate (protected excluded).
4. **Extractive selection.** Remove the lowest-priority unprotected candidates until
   the target reduction / token budget is reached (see `DETERMINISM.md`).
5. **Verify.** Evaluate the oracle on the reduced context. If its `oracle_id` /
   `contract_version` drift from the base → fallback. If the `equivalence_key` matches
   the base → **VERIFIED**.
6. **Restore.** Otherwise, find the removed units whose *individual* removal from the
   full context changes the key (or whose evaluation is uncertain — fail closed) and
   restore them; re-verify. If equal → **RESTORED**.
7. **Fallback.** If individual restoration cannot recover equivalence (joint effects)
   → **full fallback** (`JOINT_EFFECT_FALLBACK`).

Every stage that removes fails closed: uncertainty always increases *retained*
context, never removal.

## Extractive only

Output spans are byte-for-byte input spans. The minimizer only retains / removes /
restores / falls back. It never rewrites, paraphrases, summarizes, or synthesizes.
`tests/oracle/test_oracle_verified.py::test_no_rewrite_output_units_are_input_units`
proves it.

## Result

`MinimizationResult` records whether reduction occurred, whether equivalence was
verified, whether restoration occurred, whether fallback occurred, the reason codes,
and which `oracle_id` / `contract_version` were used — plus a deterministic
fingerprint. See `minimization_result_schema.json`.
