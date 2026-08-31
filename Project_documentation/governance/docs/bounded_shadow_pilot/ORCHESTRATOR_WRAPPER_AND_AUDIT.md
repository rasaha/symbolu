# Orchestrator Wrapper & Audit Extension (Phases 6–7)

*`bounded_shadow_pilot/case_builder.py` + `bounded_shadow_pilot/orchestrator_wrapper.py`. Runs each
natural artifact through the **frozen** governed-inference orchestrator read-only and produces an
extended audit record that adds the native ActionGate outcome, derivation provenance, and the blinded
ground-truth label — without modifying the frozen trace.*

## Governance-input derivation (the central honest limitation)

Natural artifacts carry no gold evidence bundles, registries, telemetry, or assertion signals.
`case_builder.build_case` derives them from the text with a **fixed, documented, conservative** rule —
never tuned to a target outcome:

| Input | Derivation |
|---|---|
| `model_output` | the natural artifact text **verbatim** — this is what the runtime governs |
| `domain` | use-case → nearest frozen GIP domain |
| `risk_tier` | `high` if security-sensitive / cybersecurity / GT-REVIEW, else `medium` |
| `evidence_steer` | base `VERIFIED_WITH_LIMITATIONS` (documentation is self-descriptive but unverified); unbacked absolute claims → `INSUFFICIENT`; security-sensitive + claims → `CONFLICTED` |
| `assertion_signals` | base supportive; unbacked claims lower support/adequacy; hedging raises uncertainty |
| `registry` / `telemetry` | frozen GIP shapes, eligible models |
| `action_proposal` | derived **only** when the text explicitly names a canonical operation (deploy/restart/key-rotate/secret-read/disable-monitoring/send); else `None` |
| `human_review_required` | GT expected class == `REVIEW` |

Every transfer result in the pilot is explicitly conditioned on `natural_derivation_v1`. The base
`VERIFIED_WITH_LIMITATIONS` choice is deliberate and honest: a natural document has no external
evidence backing, so the runtime should treat it as verified-with-limitations, not verified.

## What the wrapper composes (read-only)

1. **Frozen orchestrator** (`governed_inference_pilot.orchestrator.run_case`) decides the full pipeline
   and emits its own audit trace, reason codes, and replay signature — unmodified.
2. **Native ActionGate contract** (`actiongate_contract.evaluate`) decides any derived action, its six
   native outcomes preserved with zero loss. `None` for advisory-only artifacts.
3. **Extended audit record** (`ExtendedAudit`) carries both, plus derivation provenance
   (`derivation_version`, `derived_risk_tier`, `derived_evidence_state`, `action_derived`) and the
   blinded `gt_expected_class`. `enforced=False` by construction.

## Early transfer signal (surfaced on the first batch)

On natural artifacts the frozen runtime returns **`WOULD_QUALIFY`** (allow-with-qualification), not
`WOULD_ALLOW`, for benign documentation — a direct consequence of the honest
`VERIFIED_WITH_LIMITATIONS` derivation. This is not a false block (`WOULD_QUALIFY` is a safe,
non-blocking, delivering-with-caveats disposition); it is a **conservatism / utility** effect that the
metrics (Phase 12) and transfer analysis (Phase 14) quantify against the structured baseline, where
`CLEAN_LOW_RISK` cases reached `WOULD_ALLOW`.

## Non-enforcement & determinism

- `enforced=False` on every record; the frozen orchestrator "never performs an external governed
  action"; the native gate only decides.
- Deterministic: fixed derivation, fixed reference clock in the gate, no wall-clock/random. `run_batch`
  processes artifacts in `artifact_id` order; `replay_signature` over the extended record is stable
  across runs (tested).

## Tests

`bounded_shadow_pilot/tests/test_wrapper.py` — never-enforces, replayable record, determinism,
derivation carried, derived-action native-outcome preserved.
