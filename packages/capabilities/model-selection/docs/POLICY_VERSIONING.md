# Policy versioning and backward replay

## What `POLICY_VERSION` means

It identifies the **decision semantics** that produced a record — not the record's shape.
Two builds that can reach different outcomes from identical inputs and configuration must
not both stamp the same policy version, because distinguishing them is exactly what an
auditor uses the field for.

This is not a schema version. Nothing in the repository defines it as one: the README
calls it "decision provenance", `version.py` calls it "the policy-record version stamped
on decisions", and the `0.1.0` migration manifest recorded
`"policy_version_preserved": "exec_gate_v1"` under a phase explicitly scoped as
*"behavior-preserving structural consolidation (no scoring/policy/behavior change)"* — the
condition that made preservation correct then, and that no longer holds.

## The versions

| Version | Semantics | Written by | Read by |
|---|---|---|---|
| `exec_gate_v1` | The eligibility algorithm through `0.1.0`, before the capability floor existed. Fifteen conditions. | `0.1.0` only | every build |
| `exec_gate_v2` | Adds the non-compensatory `quality_within_floor` condition, applied when `GateConfig.quality_floor` is configured. | `0.2.0`+ | `0.2.0`+ |

`SUPPORTED_POLICY_VERSIONS` is the read set, ordered oldest first. `POLICY_VERSION` is the
single writable version.

## Reading is broad; writing is narrow

**`EligibilityDecision.from_dict` reads any supported version.** A stored v1 record is
reconstructed exactly as written — its own stamp, its condition list, its per-condition
detail and its retained raw provider strings — and its fingerprint is unchanged. Nothing
is recomputed, nothing is upgraded, and a v1 record is never re-stamped as v2. A v1 record
has no `quality_within_floor` condition; that is not damage to repair, it is what a v1
decision was.

**`GateConfig` refuses to write an older version.** `GateConfig(policy_version="exec_gate_v1")`
raises. This is the asymmetry that gives the field its meaning: this code cannot reproduce
v1 semantics, so it may not claim to be them. Allowing the override would recreate, by
configuration, the precise ambiguity the bump removes.

## Unknown versions fail closed

An unrecognized `policy_version` raises `UnsupportedPolicyVersionError`. That includes:

- a **newer** version from a future release — this build does not know the semantics the
  record was produced under, and reconstructing it would assert an equivalence nobody
  established;
- a **missing** version — absence is not v1, and defaulting would silently attribute
  unknown semantics to a known one;
- near-misses that are not the same string: `EXEC_GATE_V1`, `exec_gate_v1 `. Case and
  whitespace are not normalized away, because a normalizing reader is a reader that
  accepts records it was never shown.

## What the bump did not do

It did not rewrite, migrate, re-stamp or invalidate a single stored record. It did not
change any decision a caller does not configure: with no floor set, a v2 decision's
conditions are the fifteen v1 emitted, in the same order. It did not touch the eligibility
aggregation, the authority contract, the fallback chain or the reason-code meanings.

The record still says v2, and should. The implementation is the thing being identified —
this is the code that *could* have applied a floor, and a reader is entitled to know which
code answered, not merely which branches it happened to take.

## Regression

`tests/test_policy_version.py` holds the five properties: a stored v1 record stays
readable and verifiable (round-trip and fingerprint), new evaluations identify as v2, the
configured floor is non-compensatory under v2, an unconfigured floor adds no condition, and
unsupported versions fail closed. The stored v1 record is a committed literal rather than a
regenerated fixture, so it cannot silently follow the code it exists to outlive. The
distribution verifier proves the same replay and refusal against the built wheel.
