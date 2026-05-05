# Sensor attestation interface — design

The §9-row-#8 industry-features-roadmap pick. The roadmap §7
frames it directly: *"closes the UN ECE R155 cybersecurity loop
the adversarial family opened."* This is the in-scope mitigation
the safety case has been pointing at since v0.7 — SOTIF
clause 8 Insufficiency #3 documents the Lemma-1 trapdoor + names
attestation as the deployment-side mitigation; this doc + its
implementation make that mitigation real.

## §1 Why this exists

The kernel + the adversarial family already establish the
cybersecurity scope-boundary explicitly:

* **Lemma-1 trapdoor.** Stealth-bias spoofs (a constant or
  linearly-drifting offset injected by an attacker who controls
  one sensor's data path) are invisible to the kernel by
  construction — the same Lemma-1 invariance that makes the
  SECOND-order kernel ignore benign sensor bias makes it ignore
  malicious bias when crafted in the same shape.
* **`adversarial_consistent_bias` characterization family.**
  The 8th family + third polarity bucket
  (`ADVERSARIAL_FAMILIES`) makes the boundary machine-checkable
  — the cybersecurity-reviewer-facing evidence pinned in the
  certification grid.
* **SOTIF clause 8 Insufficiency #3.** The traceability matrix
  names the trapdoor + scopes the mitigation as
  *"out-of-scope of the kernel; in-scope at the deployment-
  partner layer: cross-modal sensor attestation, cross-class
  redundancy, calibration drift monitoring (UN ECE R155
  §7.3.4)."*

What's missing is the *attestation surface itself* — a typed
contract a deployment partner wires their sensor-stack
attestation pipeline against, and a verifier that gates
predictor admission on attestation rather than only on
observed disagreement. Without the surface, every OEM
re-builds attestation glue per program; with it, the
attestation-failure → predictor-exclusion path is a documented
contract their UN ECE R155 cybersecurity reviewer can argue
against.

The discipline: **a sensor whose attestation fails is excluded
from the consensus before BCVF sees it.** The kernel's "I
can't detect stealth bias" property becomes "I never had to —
the attestation gate caught it upstream." The defence-in-depth
narrative the safety case has been writing checks for now has
the cashing layer.

## §2 The attestation contract

A `SensorAttestation` is a typed record one predictor (or its
upstream sensor stack) attaches to its trajectory output.
Three load-bearing fields:

| Field | Type | Why |
|---|---|---|
| `predictor_name` | str | The predictor the attestation is for. Must match the predictor the integrator is verifying. |
| `firmware_version` | str | The sensor firmware version that produced the data. Verified against a per-policy allowlist. |
| `signature` | str | HMAC-SHA256 hex digest over the canonical payload (predictor_name + firmware_version + nonce + timestamp + data_digest). The integrator's trusted key (provisioned at manufacture) verifies this. |
| `nonce` | str | Per-message nonce. Replay-protection — the verifier rejects nonces it has already seen within the configurable replay window. |
| `issued_at` | str (ISO 8601) | When the attestation was minted. Verified against a configurable freshness window. |
| `data_digest` | str | SHA-256 hex digest over the predictor's actual trajectory payload (the `(K, H, 3)` tensor flattened canonically). Binds the attestation to the data — an attacker can't swap the trajectory for a different one with the same attestation. |
| `metadata` | dict | Free-form caller annotations (sensor serial, lot number, region). Not interpreted by the verifier. |

The contract is intentionally **stdlib-only** — `hashlib` +
`hmac` + `secrets`. No `cryptography` library; no PKI; no
asymmetric keys. The realistic within-vehicle model is a
symmetric key burned into the sensor at manufacture and
distributed to the orchestrator via the OEM's existing
provisioning channel. If a deployment partner needs
asymmetric (X.509 + ECDSA) signatures, they ship a custom
verifier subclass; the framework's HMAC-SHA256 verifier is
the reference implementation.

## §3 The verification policy

A `SensorAttestationPolicy` is a per-predictor configuration
the integrator distributes alongside their `CalibrationSet`.
Documented as a sibling of `per_predictor_failure_thresholds`
(per the calibration-bundle composition).

| Field | Type | Why |
|---|---|---|
| `predictor_name` | str | Must match the attestation's `predictor_name`. |
| `accepted_firmware_versions` | tuple[str, ...] | Allowlist. Empty tuple = accept any version (test mode). Production policies pin specific versions. |
| `freshness_window_seconds` | float | An attestation older than this is rejected. Default 300s (5 minutes); AUTOSAR partners may tighten to 1s. |
| `replay_window_seconds` | float | Nonces seen within this window cannot be reused. Default 600s. |
| `key_id` | str | Identifier for the verifying key. The verifier looks up the actual key bytes via a caller-supplied `key_resolver` callable (the framework never holds key material). |
| `enabled` | bool | Default True. Setting False short-circuits to "always pass" — for test environments / staged rollouts. The verification result is still recorded so an audit can prove the policy was off. |

The verifier is constructed with a dict mapping
predictor_name → policy + a key resolver. The key resolver
is the integrator's hookpoint — they wire it to their HSM /
secure-enclave / TPM / whatever the deployment uses. The
framework explicitly does not store keys; the key material
never enters this module.

## §4 The verification gate

`SensorAttestationVerifier.verify(attestation, *, expected_data_digest) → AttestationResult`
runs five checks in this order:

1. **Policy lookup.** `attestation.predictor_name` resolves
   to a known policy. Unknown predictor → `UnknownPredictorError`.
2. **Policy-disabled short-circuit.** If `policy.enabled is
   False`, return success immediately (with `policy_enabled=False`
   on the result so an audit captures that the verifier
   ran but the policy was off).
3. **Firmware allowlist.** `attestation.firmware_version` ∈
   `policy.accepted_firmware_versions` (if non-empty).
4. **Freshness.** `now() - attestation.issued_at ≤
   policy.freshness_window_seconds`.
5. **Replay.** `attestation.nonce` not in the replay-cache
   for this predictor (the cache is bounded; entries older
   than `policy.replay_window_seconds` evict).
6. **Data binding.** `attestation.data_digest ==
   expected_data_digest`. The integrator computes
   `expected_data_digest` over the trajectory tensor before
   calling verify — a mismatch means the attestation is
   stale-but-fresh-looking (signed for a different payload).
7. **HMAC signature.** `hmac.new(key, canonical_payload,
   sha256).hexdigest() == attestation.signature`. Constant-
   time comparison via `hmac.compare_digest` (timing-attack
   safe).

The result is a typed `AttestationResult` with a `passed`
bool + a `failure_reason` string naming the first check that
failed. A predictor whose attestation does NOT pass is
*excluded from the consensus* — the verifier emits a
`per_predictor_excluded` mask the integrator feeds to
`TrustWeightComputer.set_exclusion()` (the existing
exclusion path).

## §5 Composition with the existing exclusion path

Attestation-driven exclusion uses the same `is_excluded`
mask the deadline-driven + state-machine-driven exclusion
paths already populate:

```python
attestation_results = verifier.verify_batch(
    attestations,
    expected_data_digests=digests,
)
attestation_excluded = np.array([
    not r.passed for r in attestation_results
], dtype=bool)
deadline_excluded = ...  # from BCVFNode
combined_excluded = np.logical_or(
    deadline_excluded, attestation_excluded
)
trust_computer.set_exclusion(combined_excluded)
```

Three exclusion sources stack via `np.logical_or` — a
predictor is excluded if ANY one trips:

* **Deadline.** Predictor hasn't published within
  `predictor_deadline_ms`. Documented per the §9-row-#2 ROS 2
  integration contract.
* **Attestation.** Sensor's signature didn't verify, or
  firmware is on the deny-list, or the attestation expired,
  or the nonce was replayed. **NEW with this surface.**
* **State machine.** `SafetyStateMachine` escalated this
  predictor to FAULT/FAILSAFE based on accumulated BCVF
  signal. Documented per the §9-row-#1 state-machine landing.

A `SafetyStateMachine` deployment that ingests the combined
mask sees the attestation failure as another predictor
exclusion and walks the same FAULT → FAILSAFE escalation
path if ≥ 2 predictors are attestation-excluded. The state
machine doesn't need to know *why* — exclusion is exclusion;
the audit log captures the cause. This is the discipline:
a kernel-invisible attack surfaces as a same-shape signal at
the system level.

## §6 What this is NOT

* **Not a PKI implementation.** No X.509, no ECDSA, no
  certificate chains. Symmetric HMAC-SHA256 only. A deployment
  partner needing asymmetric attestation ships a custom
  verifier subclass; the framework's surface is the typed
  contract + the HMAC reference implementation.
* **Not a key-management system.** Key material never enters
  this module. The integrator supplies a `key_resolver`
  callable that fetches the verifying key from their HSM /
  TPM / secure enclave per predictor. The framework explicitly
  refuses to hold keys to keep the trusted-base small.
* **Not a DDS-Security replacement.** DDS-Security operates
  at the transport / middleware layer (sender authentication
  via the DDS plugin). The attestation surface is in-band: it
  travels with the predictor's payload + binds to the actual
  data via `data_digest`. The two compose — DDS-Security
  authenticates *who* sent the message; attestation
  authenticates *what* the message says.
* **Not a kernel-rule rewrite.** The kernel's Lemma-1
  invariance is unchanged. Attestation gates predictor
  admission upstream of the kernel; once a predictor's data
  reaches the kernel, the same arbitration math applies.
  This is the in-scope half of the SOTIF clause-8
  Insufficiency-#3 mitigation; the kernel's out-of-scope
  half is the documented + already-shipped behaviour.
* **Not a substitute for the deployment partner's own
  cybersecurity case.** UN ECE R155 demands a full risk-
  assessment + threat-modelling artifact at the OEM level.
  This framework is one component the artifact references.
* **Not a fleet-management interface.** Per-vehicle key
  distribution, key rotation, certificate revocation — all
  live at the deployment-partner layer. The framework's
  interface is per-message verify, not lifecycle management.

## §7 Composition with existing surfaces

* **`adversarial_consistent_bias` family + Lemma-1
  trapdoor docs (post-v0.7).** The cybersecurity scope-
  boundary documentation. This surface is the in-scope
  mitigation — the safety case can now point at attestation
  instead of saying "deployment partner handles this".
* **SOTIF clause 8 Insufficiency #3 (post-v0.7).** Names
  attestation as the documented mitigation. New evidence
  artifacts (`_SENSOR_ATTESTATION` +
  `_SENSOR_ATTESTATION_VERIFIER`) wire into clause 8 +
  clause 6 (HARA — the attestation-failure case is a named
  hazard input).
* **`TrustWeightComputer.set_exclusion()` (existing).** The
  hookpoint attestation-driven exclusion feeds. No changes
  to the trust computer; the integrator unions the masks.
* **`SafetyStateMachine` (post-v0.7).** Sees attestation-
  excluded predictors via the same `is_excluded` field a
  deadline-excluded predictor uses. Same FAULT/FAILSAFE
  escalation path applies; the audit log differentiates
  causes.
* **`CalibrationSet` (post-v0.7.x).** A bundle's
  `per_predictor_failure_thresholds` field can carry an
  optional `attestation_policy` sub-dict per predictor —
  ships the policy alongside the calibration knobs. The
  attestation surface is JSON-roundtrip compatible with the
  bundle's strict-validation discipline.
* **`bcvf_ros2/node.py BCVFNodeBehaviour` (post-v0.7.x).**
  The natural integration point — extract the attestation
  field from the inbound `PredictorTrajectoryMessage`,
  verify before feeding to the trust bridge. The existing
  `combined_excluded` mask gains a third union term.

## §8 Ship-when-ready criteria for STABLE_API graduation

Promotion to `STABLE_API` requires:

1. **One deployment partner runs the attestation surface
   against their HSM / TPM key-resolver in production for
   one quarter** without filing a contract-shape change
   request. Three months of live verification is the
   empirical filter for the policy + result + exclusion
   contract.
2. **One real attestation-failure detection across a known
   sensor-firmware regression.** A field incident where a
   sensor's firmware was downgraded outside policy + the
   verifier correctly excluded the predictor + the safety
   state machine escalated. Negative control proving the
   chain works.
3. **One asymmetric-attestation extension subclass** — a
   deployment partner using ECDSA or X.509 ships a custom
   verifier that satisfies the same typed contract. Proves
   the framework's interface is extension-friendly, not
   HMAC-only.
4. **External auditor (TÜV / DEKRA / equivalent) signs off
   the attestation interface as admissible UN ECE R155
   §7.3.4 evidence.** Out-of-sandbox manual gate.
5. **Replay-cache persistence layer.** Currently in-memory
   bounded ring; STABLE_API graduation requires a file-
   backed / IPC-shareable cache so a process restart
   doesn't reset the replay window. A deployment partner
   running multiple verifier processes per vehicle needs
   shared replay state.

Until all five land, the symbols stay in `PROVISIONAL_API`.

## §9 API sketch (no implementation in this doc)

```python
# attestation/interface.py

@dataclass(frozen=True)
class SensorAttestation:
    predictor_name: str
    firmware_version: str
    signature: str        # HMAC-SHA256 hex digest
    nonce: str
    issued_at: str        # ISO 8601
    data_digest: str      # SHA-256 hex over trajectory payload
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]: ...

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "SensorAttestation": ...


@dataclass(frozen=True)
class SensorAttestationPolicy:
    predictor_name: str
    accepted_firmware_versions: Tuple[str, ...] = ()
    freshness_window_seconds: float = 300.0
    replay_window_seconds: float = 600.0
    key_id: str = ""
    enabled: bool = True


@dataclass(frozen=True)
class AttestationResult:
    predictor_name: str
    passed: bool
    failure_reason: Optional[str]   # None on pass; else first-failed-check name
    policy_enabled: bool
    verified_at: str                # ISO 8601


# attestation/verifier.py

class SensorAttestationVerifier:
    def __init__(
        self,
        policies: Mapping[str, SensorAttestationPolicy],
        key_resolver: Callable[[str], bytes],   # key_id → key bytes
        clock: Callable[[], float] = time.time,
    ) -> None: ...

    def verify(
        self,
        attestation: SensorAttestation,
        *,
        expected_data_digest: str,
    ) -> AttestationResult: ...

    def verify_batch(
        self,
        attestations: Sequence[SensorAttestation],
        *,
        expected_data_digests: Sequence[str],
    ) -> Tuple[AttestationResult, ...]: ...

    @property
    def n_replay_cache_entries(self) -> int: ...


def compute_data_digest(trajectory: np.ndarray) -> str: ...
def sign_attestation(
    *,
    predictor_name: str,
    firmware_version: str,
    nonce: str,
    issued_at: str,
    data_digest: str,
    key: bytes,
) -> str: ...


# attestation/errors.py

class AttestationError(Exception): ...
class UnknownPredictorError(AttestationError): ...
class AttestationVerificationError(AttestationError): ...
```

The implementation lands paired with this doc. This section
captures the surface a future refactor must preserve.
