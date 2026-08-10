# ACP Product-Core Separation & Canonical-Package Readiness — Executive Summary

**Phase:** audit-only (documentation). No source moved, no package created, no ACP/ActionGate/contract
behavior changed, no freeze re-baselined.
**Default branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `3ec11e4e`
(*Merge PR #1273 — Ugence Code Governance design spec*).
**Audit branch:** `claude/acp-product-core-separation-audit-qrwlxv` (harness-mandated; the prompt's
proposed `claude/acp-product-core-separation-audit` is honored as the intent, the mandated suffixed name
is authoritative). Based on the verified default tip `3ec11e4e`.

## Verdict

> ## ACP NOT READY — capability remains shadow, experimental, or architecturally unresolved; do not package

This is **not** a criticism of code quality. The robotics **Autonomous Control Plane** core is genuinely
frozen, deterministic, dependency-clean, and well-tested. The verdict is about **product-core existence and
identity**, which four findings undermine:

1. **The named capability does not exist.** "Action Clearance Protocol" appears *nowhere* in the repo or git
   history. In this codebase **ACP = "Autonomous Control Plane"** everywhere. The acronym denotes **four
   distinct concepts** (robotics Autonomous Control Plane; the "AI Control Plane" product umbrella; a
   *separate* console digital-clearance reimplementation; and a DB-domain adapter). See
   `TERMINOLOGY_AND_SCOPE.md`.

2. **The authority definition is architecturally unresolved.** The audit's own definition — *ACP evaluates
   whether an already-authorized action remains valid; it never authorizes* — is contradicted by the live
   **robotics V1** core, which is documented as a *"decision-**and-authorization** runtime"* that mints a
   one-shot `ControlAuthorization` grant (`acp/ACP_ARCHITECTURE.md:20,110`). The *cloud/console* framing
   agrees with the audit definition (*"never authorizes… ActionGate decides whether; ACP decides whether
   now"*, `ugence_console_api/capabilities/operational_safety.py:11-12`). The product cannot be packaged
   until it picks one meaning. See `AUTHORITY_BOUNDARY.md`.

3. **There is no single product core; the discipline is split across three non-sharing places.** The
   robotics core (`symbolu_robotics/autonomous_control_plane/`), the console digital clearance
   (`ugence_console_api/…/operational_safety.py`, which imports none of the robotics core), and the
   governance-chain freshness seam (Decision Authority's `OfflineDeterministicControlPlane` → `EXPIRED`).
   See `CANONICAL_SOURCE_DECISION.md`.

4. **It is uniformly shadow-only.** Every results doc leads with a shadow disclaimer; the one live robotics
   path runs on a *stub* planner; no live cluster is ever contacted; *"no production enforcement is
   recommended"* (`acp/ACP_V2_1_RESULTS.md:117-118`). Overall maturity: **SHADOW_ONLY / PARTIAL_PROTOTYPE**.
   See `MATURITY_ASSESSMENT.md`.

## What *is* real and reusable

- A **frozen, stdlib-only, deterministic robotics ACP core** (10 modules; combined digest
  `8f8660e293308cf94c983a26a2ae69c9`, **verified byte-accurate against live code in this audit**).
- Correct **fail-closed** and **narrow-only** security properties in the cloud composition (an ActionGate
  `DENY` is never overridden; an ACP hold never mints authorization — `cloud/composition.py`).
- Real product consumers: **3 subsystems / 13 files** (`cer_v0_1/2/3`), plus a clean product-over-core reuse
  in `cer_v0_3/acp_db` and the console governed loop.
- The **neutral seam already exists** in `ugence_governance_contracts`
  (`ActionGovernanceOutcome.EXPIRED`, `ActionGovernanceRequest.authorization_expired`,
  `ActionGovernanceResult.expiry`).

## Baseline (reproduced green; pre-existing failures unchanged)

| Check | Result |
|---|---|
| `python -m platform_freeze.verify` | **PASS** — substantive digest `d4ad77e1…a174a1a6` |
| `scripts/validate_terminology.py` | **PASS** |
| `scripts/check_doc_links.py` | **PASS** (21 links) |
| `platform_freeze.dependencies.dependency_report()` | **passed=True, 0 violations** |
| governance-contracts / GPF / decision-authority | **45 / 84 / 79 passed** |
| actiongate_provider | **30 passed** |
| ACP (`autonomous_control_plane/tests`) | **112 passed** |
| control_plane / execution_gate / execution_gate_shadow | **65 / 25 / 23 passed** |
| robotics_reliability_bench (acp_* benches) | **47 passed** |
| ugence_console_api | **4 passed** |
| `platform_freeze/tests` | 19 passed, **2 pre-existing failures** (freeze-tooling; documented) |
| `bounded_shadow_pilot` | 44 passed, **1 pre-existing failure** (ground-truth; unrelated) |

Pre-existing failures are the same ones recorded in the Model-Selection audit baseline plus one unrelated
shadow-pilot ground-truth test; none is caused by or attributable to ACP. See `BASELINE.md`.

## Recommendation

Do **not** begin an ACP migration. Before any packaging phase, resolve the authority definition, choose the
world the package serves, factor a neutral clearance kernel out of the robotics envelopes, stabilize a real
request/result contract, decide one-time-use ownership, and plan an ACP-local freeze amendment. These
prerequisites are enumerated in `MIGRATION_SEQUENCE.md`, `PACKAGE_READINESS.md`, and `RISK_REGISTER.md`.
