# Pilot Assumptions and Exclusions (Phase 1)

*Stated up front so the final evaluation cannot be read as claiming more than the method supports.
Falsification-first: assumptions are liabilities to be tested, not conveniences to be trusted.*

## Assumptions (each a stated liability)

1. **Natural artifacts exist in-repository in sufficient number.** The pilot assumes ≥ 200 naturally
   occurring artifacts (documentation, docstrings, comments) can be harvested from real repository
   text not authored for a governance corpus. **If this assumption fails, the pilot reports the actual
   count and returns NOT ENOUGH EVIDENCE rather than fabricating data.**

2. **Governance inputs can be derived deterministically from natural text.** Real artifacts lack the
   gold evidence bundles, registries, and telemetry the structured corpora provide. The pilot derives
   governance inputs from the natural text with a deterministic, documented procedure. This is a
   **known honest limitation**: derived inputs are weaker than authored gold inputs, and any transfer
   result is conditioned on this derivation. The derivation is frozen and auditable.

3. **The frozen runtime is a faithful decision oracle.** The pilot assumes the frozen orchestrator and
   real ActionGate behave on natural inputs as their contracts specify. It does not re-verify their
   internal logic (read-only); it observes their outputs.

4. **De-identification/redaction is sufficient for repository text.** The pilot assumes the inherited
   redaction/minimization controls, applied to already-non-sensitive repository text, are sufficient.
   Any prohibited or unclassifiable artifact fails closed at intake.

5. **Determinism holds.** All governance stages are stdlib-only and free of wall-clock/random in the
   decision path, so results are byte-reproducible. Non-determinism, if observed, is a finding.

## Exclusions (hard — outside this pilot by construction)

- **No enforcement.** No disposition is acted upon; `enforced=False` by construction.
- **No external actions.** Nothing executes in the world.
- **No autonomous action.** The runtime proposes; a human reviews.
- **No real customer.** No customer is onboarded, automatically or otherwise.
- **No unrestricted providers.** No unrestricted provider calls.
- **No unrestricted web retrieval.**
- **No live model calls** in the decision path.
- **No prohibited or unclassified data.**
- **No threshold tuning on the final pilot set.** Thresholds are inherited frozen; the final set is
  scored once, not fit.
- **No production-readiness claim.**
- **No new synthetic corpus presented as primary pilot evidence.** A synthetic control set may be used
  only as an explicitly-labelled reference against the natural corpus, never as the pilot's evidence.
- **No excluded use case** (clinical, financial/trading, permission changes, irreversible deletion,
  employment, legal, regulated automation, autonomous security, PII/sensitive data).

## Native ActionGate semantics — preservation is mandatory

The pilot must **not collapse native ActionGate outcomes.** All six native outcomes are preserved
exactly:

`ALLOW` · `ALLOW_WITH_CONSTRAINTS` · `DENY` · `ESCALATE_TO_HUMAN` · `REQUEST_MORE_EVIDENCE` ·
`SIMULATE_AND_RETRY`

together with their **constraints, approvals, evidence requirements, simulation, retry, reason codes,
policy references, and action/policy hashes**. The customer-shadow-readiness adapter compressed these
six into a four-value shadow vocabulary (a tracked 25% semantic loss). Phase 5 of this pilot builds a
**native-vocabulary contract** that preserves all six and their metadata.

> **Pilot blocker:** any semantic loss in a **safety-relevant** native ActionGate outcome. If a native
> outcome that carries safety meaning (e.g. `DENY`, `ESCALATE_TO_HUMAN`, `REQUEST_MORE_EVIDENCE`) is
> lost, flattened, or misrepresented anywhere in the pilot's path, the pilot stops.

## Fail-closed posture (applies everywhere)

Unknown vocabulary, a missing field, or any exception resolves to `INDETERMINATE` / `BLOCK` — never to
a permissive outcome. This holds at intake, in the derivation of governance inputs, in the native
ActionGate contract, and in the orchestrator wrapper.

## What a defensible negative result looks like

- **NOT ENOUGH EVIDENCE** — fewer than the target natural artifacts exist, or too few reach a scorable
  state. Reported with the actual count.
- **DO NOT PROCEED** — a stop condition fired, or transfer analysis shows structured-corpus results do
  not hold on natural artifacts.
- **PROCEED WITH CONDITIONS** — transfer holds within stated limits; specific conditions gate a
  single-customer external shadow pilot.

Any of these is an acceptable, honest terminus. The method is designed to make a false "ready" hard to
reach.
