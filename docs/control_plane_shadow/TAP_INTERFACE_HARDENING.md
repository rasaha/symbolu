# TAP / Assertion-Governance Interface Hardening

*Phase 6. TAP is the least mature integration boundary. This defines the minimum stable
assertion-governance interface, records whether the current TAP artifacts produce it directly
(they do not — there is a semantic gap), and preregisters what ActionGate receives.*

## Minimum stable interface

**Input (assertion-governance request):**
- governed request context (task, risk class, domain)
- model output reference (never raw content by default)
- claim units / assertion candidates
- evidence references
- domain policy + policy version
- risk class
- provenance
- uncertainty metadata
- version context

**Output (assertion-governance decision):**
- `assertion_disposition` ∈ {ALLOW, QUALIFY, REJECT, ESCALATE, INDETERMINATE}
- approved/transformed assertion reference
- qualifications
- unsupported claims
- escalation reason
- evidence adequacy
- reason codes (`ASSERT.*`)
- audit metadata

## Can the current TAP artifacts produce this directly?

**No — not as a production assertion governor.** The closest real, deterministic decision engine
is **TAP-E4 `GovernanceTruthLayer.resolve()`** (config F). It is genuinely executable and emits a
disposition (`GovStatus`), 8-axis confidence, conflict/gap detection, and full provenance. But:

- **Semantic gap.** E4 answers *"which documented authority governs this situation?"* — not
  *"may the model state this claim?"*. Its own README separates it from assertion/action
  governance. The `GovStatus → assertion_disposition` map (`vocabulary.TAP_MAP`) is an
  **adapter-authored approximation**.
- **Input mismatch.** E4 consumes three upstream records (intent, retrieval, relationship) + a
  `Situation`, not "claim units + evidence references + uncertainty metadata" directly. The
  adapter builds valid records read-only from the real E4 corpus.
- **Confidence loss.** E4's 8-axis confidence and conflict/gap detail are richer than a single
  disposition; the adapter preserves them in the payload but the disposition ignores them.

**Decision (this pilot):** wrap E4 as a **deterministic adapter over the closest existing
evaluator**, label every result with the semantic gap, and report TAP integration as
**TIER 3 with a documented semantic-approximation caveat**. We do **not** claim production TAP
integration. A true assertion governor (grading model claims against evidence — closer to
TAP-E3 `AssertionStatus`: SUPPORTED/PARTIALLY_SUPPORTED/CONTRADICTED/…) is future work
(`LIMITATIONS_AND_FALSIFICATION.md`).

## Semantic gap — explicit

| What we want (assertion governance) | What E4 provides (authority resolution) | Gap |
|---|---|---|
| "may the model state claim X?" | "which authority governs situation S?" | subject differs: claim vs situation |
| grounded in evidence support of X | grounded in documented authority precedence | evidence-of-claim not directly evaluated |
| REJECT = claim unsupported | NO_GOVERNING_AUTHORITY = no policy governs | proxy, not identity |
| QUALIFY = state with caveats | GOVERNING_WITH_EXCEPTION = governed w/ exception | closest, still a proxy |

## Preregistered rule: what does ActionGate receive?

Tested options: (a) raw model output; (b) governed assertion output; (c) both; (d) governed
output + provenance.

**PREREGISTERED CHOICE (before outcome evaluation): (d) governed assertion output + provenance.**

Rationale: action authorization must be based on what the system is *permitted to assert* (the
governed output), never on raw model output that may contain ungoverned/unsupported claims
(invariant: assertion precedes action; no bypass). Provenance travels with it so ActionGate can
verify the authority chain. Raw model output is **not** forwarded to ActionGate. This choice is
fixed here and evaluated (not tuned) in Phase 17.

## Adapter guarantees

- Runs the real E4 engine deterministically, no network, no LLM (avoids `tap_e1_1_realmodel`).
- Never invents evidence; unknown/insufficient basis ⇒ INDETERMINATE, never silently ALLOW.
- Preserves the raw `GovernanceRecord` summary + records information loss + the semantic gap in
  every result.
- Does not modify the engine (its `frozen_components_hash` stays intact).
