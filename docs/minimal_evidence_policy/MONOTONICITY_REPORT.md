# Monotonicity & Error-Propagation Report (Phases 14–15)

## Monotonicity (`monotonicity.py`)

Exhaustive check over 12 claim families × 4 risk tiers × 11 increasing transforms = **528 transitions**.

| | |
|---|---|
| Tested transitions | 528 |
| Violations | **0** |
| Monotonic | **True** |
| Pilot blocker | **False** |

Increasing any of {risk, actionability, temporal sensitivity, source→unknown, contradiction, regulated-
domain status, self-verification, ambiguity→unknown, remove-approval, high-impact, stale-authority}
**never lowers** the obligation. This holds by construction (every step is a monotone `max` over the
obligation rank, plus the final floor re-assertion) and is verified exhaustively. **Any monotonicity
violation is a pilot blocker; there are none.**

## Error propagation (`error_propagation.py`)

Injects each canonical obligation error into the correct (gold) obligation and measures induced unsafe
clean allows over 325 items (held-out + adversarial).

| Injected error | affected | induced unsafe |
|---|---|---|
| **risk_downgrade** | 178 | **178** |
| **factual_as_opinion** | 164 | **164** |
| **generated_as_evidence** | 164 | **164** |
| **actionability_omitted** | 143 | **143** |
| **current_as_timeless** | 143 | **143** |
| source_authoritative_no_basis | 143 | 52 |
| fixture_as_telemetry | 143 | 52 |
| stale_as_current | 143 | 52 |
| ER_forced_to_E1 | 14 | 14 |
| E4_downgraded_to_E2 | 21 | 10 |
| attribution_as_truth | 56 | 0 |
| unknown_forced_internal | 14 | 0 |

*(Baseline unsafe at correct obligations = 6, the INV-12 E1-gold adversarial cases the metric over-counts
as synthetic; the policy over-escalates them, so its own score is 0.)*

### Reading

- **Dangerous = burden-stripping errors** — risk-downgrade, factual→opinion, generated-as-evidence,
  actionability-omitted, current-as-timeless each turn 140–178 correctly-withheld claims into clean
  allows. These are exactly the directions the minimal policy forbids: the **risk floor** blocks
  risk-downgrade, the **upward-only** rule blocks the rest, and **INV-1/INV-2** block generated-as-
  evidence.
- **Partially / fully absorbed** — errors that name evidence the artifact lacks (source-authoritative-no-
  basis, fixture-as-telemetry, stale-as-current) propagate only where the artifact happens to carry
  implementation evidence (52 of 143); attribution→truth and unknown→internal are fully absorbed by the
  contract's fail-closed asymmetry (0).

The study confirms that **the minimal policy's safety rests on not stripping evidence burden** — and that
its monotonicity + risk floor + anti-self-verification invariants are precisely the defenses against the
highest-propagation errors.
