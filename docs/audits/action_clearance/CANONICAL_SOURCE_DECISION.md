# ACP Canonical-Source Selection

## Conclusion

> **NO_STABLE_PRODUCT_CORE_EXISTS** for a governance "Action Clearance" product.
> Secondary reading: **MULTIPLE_PARTIAL_SOURCES_REQUIRE_CONSOLIDATION**.
> The capability is best described as **ACP_IS_ONLY_A_SHADOW_CAPABILITY** in production terms.

A genuine, frozen, deterministic robotics **Autonomous Control Plane** core exists — but it is not a
*governance clearance product*: it is a robotics/cloud-domain, shadow-only capability whose neutral clearance
kernel is not factored out, and it does not span the two other framings of the discipline (console digital
clearance and the governance-chain freshness seam), which share no code with it.

## Scoring against the ten criteria (robotics core = candidate #1)

| # | Criterion | Finding | Verdict |
|---|---|---|---|
| 1 | Real consumer count | 3 subsystems / 13 files (`cer_v0_*`); console reimplements separately | Partial |
| 2 | Production-shaped API | Yes for the core; but consumers use `.cloud.*` deep imports, not the frozen top-level `__all__` | Partial |
| 3 | Deterministic behavior | Yes — zero clock/random/network in the core; 100% rerun identity in benches | **Strong** |
| 4 | Stable request/result contract | No single `ClearanceRequest/Result/Status/ReasonCode`; implicit tuple + `SelectionOutcome`; console uses a different `ClearanceVerdict`; consumers rely on enum `.value` strings | **Weak** |
| 5 | Test coverage | 112 tests; but synthetic/authored fixtures, no live cluster/sensor | Partial |
| 6 | Dependency direction | Clean — core imports nothing from production; production does not import the core (grep-asserted) | **Strong** |
| 7 | Freeze / replay evidence | ACP V1 local freeze verified byte-accurate; frozen replay in `acp/` results | **Strong** |
| 8 | Identity & lifecycle semantics | Content-hash identities present; but no clearance ID store, no consumption/lifecycle | Partial |
| 9 | Separation from ActionGate & execution | Clean in cloud/console framing (orthogonal, never executes); **contradicted** in robotics V1 (mints a grant) | **Weak/ambiguous** |
| 10 | Compatibility with Code Governance & other products | The neutral seam (`ActionGovernanceOutcome.EXPIRED`) exists, but the robotics core does not consume it; console/DA use different types | **Weak** |

Two "Strong" structural properties (determinism, dependency cleanliness, freeze) sit next to three
disqualifying "Weak" properties (no stable contract, ambiguous authority/execution separation, no
cross-product compatibility). That combination is exactly a **frozen shadow research core**, not a shippable
product core.

## Why each other candidate is rejected as canonical

- **Cloud domain adapter (#2):** K8s-domain-shaped (`CloudWorldState`, blast radius, freeze window). It is
  the *consumed* surface but is a domain adapter, not the neutral core.
- **Console digital clearance (#4):** the closest match to the audit definition and live product code, but
  63 lines with **hard-coded k8s thresholds** (target-specific), a disposition-only string verdict, no
  contract family, and **no shared code** with the robotics core. It is a separate reimplementation of the
  discipline, not a core to lift.
- **ACP DB adapter (#5):** a domain adapter that *reuses* the frozen `compose()`; it adds its own duplicated
  freshness/freeze/expiry HARD checks. A consumer of the core, not the core.
- **Reliability benches (#6):** read-only shadow harnesses.
- **Decision Authority control plane (#7):** owns the governance-chain `EXPIRED`/freshness check, but lives
  in the Decision Authority package (v1.0.0, pydantic), is labeled the *AI Control Plane's* responsibility,
  and is not the robotics ACP core. Folding it into an ACP package would move durable governance-chain
  responsibility across a boundary the audit forbids.
- **GPF reference provider (#8) / contracts seam (#9):** the neutral vocabulary and a reference impl — the
  *seam* a future ACP would consume, not the core.

## What "consolidation" would require (not done here)

If the project decides to build the product, the consolidation target is a **neutral clearance kernel**
(status enum + reason codes + fail-closed hard-filter + fingerprints + expiry/freshness primitives) factored
out of the robotics envelopes, consumed by domain adapters (robotics, cloud, DB, console). That factoring
does not exist today; the robotics `world_state.py`/`envelopes.py` are robotics-shaped. See
`MIGRATION_SEQUENCE.md` for the prerequisite sequence.
