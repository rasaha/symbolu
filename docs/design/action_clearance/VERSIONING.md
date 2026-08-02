# Versioning

Design proposals, not implementation facts.

| Axis | Proposed value |
|---|---|
| Distribution version | `0.1.0` |
| Contract/policy version | `action_clearance.v1` |
| Fingerprint algorithm id | `action_clearance.fp.v1` (SHA-256 over canonical JSON, domain-separated) |
| Design-artifact version | `action_clearance.design.v0.1` |

## Compatibility policy

| Surface | Policy |
|---|---|
| Request schema | additive fields are minor; removing/retyping a required field is major (`action_clearance.v2`) |
| Result schema | additive optional fields minor; changing `status` set or a fingerprinted field is major |
| Reason codes | adding a code is minor; removing or re-mapping a code's default status is major |
| Signal types | adding a type is minor; changing a required-field set for an existing type is major |
| Profile versions | each profile carries its own version (`github_exact_merge.v1`); a binding-set change is a profile-major bump |
| Fingerprint algorithm | any change to canonical serialization or domain tags is a **major** algorithm bump (`.fp.v2`); results across algorithm versions are not comparable |

## No robotics-compatibility promise

**No compatibility promise is made to existing robotics imports.** `symbolu_robotics.autonomous_control_plane`
is a separate capability with its own local freeze; Action Clearance versioning is independent and does
not track, alias, or preserve identity with any robotics type or version. Consumers of the robotics core
are unaffected and unsupported by this package.

## Version discipline

- The evaluator's determinism means a fingerprint-algorithm bump is observable and testable (the
  equivalence harness re-captures under the new algorithm).
- `POLICY_VERSION = "action_clearance.v1"` is embedded in `version.py` and echoed in results'
  `policy_refs`, so a result records the contract version under which it was evaluated.
