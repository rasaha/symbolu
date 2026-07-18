# B1.1 Freeze-Validator Implementation Plan (planning only, not implemented)

## Scope and non-claims

Specifies the **future** behavior of the freeze validators. **Does not implement them.** No freeze · no
model / embedding / generation / scoring / judging · no final config · no manifest. Does **not** modify B1,
change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology / Sanskrit
privilege / semantic-truth claim. **Structure, not validated meaning.**

## Future validator scripts (to implement in `B1_1_FREEZE_CONFIG_IMPLEMENTATION`)

- `run_b1_1_freeze_artifact_validation.py` — config/schema validation over the final configs.
- `run_b1_1_freeze_manifest_verifier.py` — re-hash every bound artifact; fail on mismatch.

Both **pure stdlib** (json/hashlib/pathlib/re) — no network, no model, no third-party deps.

## Required validator checks

1. **All required config files exist** — arm-construction, generation, seeds, judge-panel, scorer,
   leak/packet (and, at freeze, the manifest).
2. **No `PLACEHOLDER_REQUIRED` values remain in *final* configs** (templates are exempt; a final config with
   any placeholder → FAIL).
3. **Arms exactly `A, D, S, R_same, R_deranged, R_domain, C, X`** — no more, no fewer.
4. **Primary comparisons include all three R controls** — `A_vs_R_deranged`, `A_vs_R_domain`, `A_vs_R_same`.
5. **Generation authorization flag is `false` by default** — a final config must not set it true without the
   separate `B1_1_GENERATION_AUTHORIZATION` gate.
6. **Embedding status represented correctly** — `BLOCKED_DEPENDENCY_UNAVAILABLE` (or updated if the real gate
   later runs).
7. **Fallback qualification represented correctly** — `FALLBACK_QUALIFIED` while the embedding gate is
   blocked.
8. **B1 verdict anchor present** — `RANDOM_OR_SCRAMBLED_MATCHES`.
9. **Track B blocked anchor present** — `BLOCKED`.
10. **All artifact sha256 hashes computed** — for every bound artifact.
11. **No source lexicons modified** — `varna_lens/` files untouched (compared against their committed
    hashes / git status).
12. **No forbidden good/bad/positive/negative/vice/virtue framing in the bridge** — re-assert the
    bridge-generation guardrail (word-boundary match; "goodwill"/"good fortune"-style collocations handled as
    already resolved).
13. **Manifest verifies hashes** — `run_b1_1_freeze_manifest_verifier.py` recomputes and matches every bound
    artifact's sha256 (`INVALID_POSTHOC` on any mismatch).

## Pass/gate behavior

- Any FAIL → freeze state stays `NOT_READY_FOR_FREEZE`.
- All PASS on final configs → advance to `READY_FOR_FREEZE_REVIEW` (still not frozen; freeze is a separate
  approved gate that builds + signs the manifest).
- The manifest verifier is the last line: it must pass at freeze and again before any (separately
  authorized) generation.

## Freeze readiness & authorization

- Freeze readiness remains **`NOT_READY_FOR_FREEZE`** (final configs do not yet exist; only templates do).
- **Generation not authorized** — validators passing does **not** authorize a model call; that needs
  `B1_1_GENERATION_AUTHORIZATION`.

## Final status
```
B1 verdict: RANDOM_OR_SCRAMBLED_MATCHES (unchanged) · Track B: BLOCKED
Freeze status: NOT_READY_FOR_FREEZE · Bridge: PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate: BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · Generation: NOT authorized
Validators: PLANNED, not implemented
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) · Track F `CORRECTNESS_DEGRADED`.
`R_deranged` remains the crux. **Structure, not validated meaning.**
