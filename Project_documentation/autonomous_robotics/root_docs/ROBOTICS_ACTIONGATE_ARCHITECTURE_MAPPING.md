# ActionGate → Robotics V2 — Architectural-Pattern Mapping

**Milestone:** Robotics reliability redesign — ActionGate comparison.
**Source read:** `ACTIONGATE_VC_BRIEF.md`, `cyber_security/action_gate_reference/`
(the pure decision machine `action_gate_ref/`), the isolated broker
(`action_gateway_isolated/`), and ActionGate's own generalization study
`Project_documentation/action_gate_cyber/cyber_security/action_gate_reference/architecture_study/ACTIONGATE_DOMAIN_GENERALIZATION.md`.
**Rule honored:** do **not** port ActionGate's enterprise policies into robotics.

---

## 1. What ActionGate is (and is not)

A deterministic **pre-commit authorization gate** for AI agents acting on
enterprise systems (K8s/IAM/DB/payments): "grant authority to one exact action,
once, only after policy, evidence, state, approval, and consequence requirements
are satisfied" (`ACTIONGATE_VC_BRIEF.md:80`). It is **discrete-action,
synchronous-decision**. ActionGate's *own* study already flags the boundary:
"hard real-time latency bounds and continuous control … is out of model"
(`ACTIONGATE_DOMAIN_GENERALIZATION.md:53`). So robotics can reuse the *decision
architecture*, not the actuation model and not the enterprise policy.

The clean split ActionGate itself draws: "The security model — canonical action
identity, evidence/approval binding, non-compensatory decision, replay-proof
commit token, TOCTOU revalidation, hash-chained audit — is domain-free"
(`…GENERALIZATION.md:31`). The domain-specific, non-reusable pieces are the
operation enum, the `extract_facts` adapter, and the signed policy rules.

## 2. Three kinds of reuse (defined)

* **Architectural reuse** — adopt the *pattern/contract* (e.g. "hard invariants
  are non-compensatory"), re-implemented for robotics.
* **Code reuse** — import ActionGate modules directly. Largely inappropriate:
  the reference is enterprise-typed (24-field IT envelope, IAM/DB operations,
  HMAC/Ed25519 approval workflow).
* **Mathematical reuse** — reuse a specific formula/algorithm. Must earn its
  place empirically; almost none transfers (ActionGate's "math" is hashing +
  precedence lattices, not control math).

## 3. Property mapping table

| ActionGate property | robotics equivalent | reusable principle | robotics-specific implementation needed | evidence needed |
|---|---|---|---|---|
| **Canonical action/state envelope** (`schema.py:40`, 24 frozen fields incl. `current_state_hash`, `state_freshness`) | one `ActionCandidate`/decision envelope carrying action + world-state snapshot hash + sensor freshness | **Architectural** — one validated shape every decision flows through | robotics field set (kinematics, margins, sensor snapshot id); drop IAM/DB fields | envelope covers every real deliberative/coordination decision without loss |
| **Non-compensatory hard invariants** (`gate.py:176` strict-min severity; DENY can't be bought back) | hard safety/feasibility gate before any soft score (already prototyped in `action_baselines._hard_admissible`) | **Architectural** — a good score cannot override a violated hard constraint | robotics invariants: collision margin, stability/ZMP, joint limits, feasibility | selectors never rank an inadmissible candidate (shown: `deterministic_never_selects_unsafe=True`) |
| **Explicit non-binary outcomes** (`gate.py:27` six outcomes) | outcome set `{SELECT, DEGRADE, NO_SAFE_ACTION, ESCALATE}` for actions; `{TRUSTED, DEGRADED, SUSPECT, ABSTAIN}` for predictors (already built) | **Architectural** — closed multi-outcome set incl. abstain/degrade | robotics-named states; no `SIMULATE_AND_RETRY`/`REQUEST_EVIDENCE` agent semantics | every decision path maps to exactly one outcome; abstain reachable |
| **No forced winner** (`gate.py:237` unknown op → ESCALATE, not ALLOW) | `NO_SAFE_ACTION` / predictor `ABSTAIN`; fail-closed on unknown | **Architectural** — refuse rather than default-allow | robotics safe-state on refusal (stop / minimum-risk maneuver) | refusal produces a defined safe posture, not a silent pick |
| **Evidence & state binding** (`projection.py:53` hashes state into `action_hash`) | bind each decision to the sensor-snapshot id + predictor-trust state it was computed on | **Architectural** — decision tied to the evidence/state it assumed | content hash over the sensor/consensus snapshot; no PKI needed | a decision made on stale state is detectably bound to the old snapshot |
| **Commit-time state revalidation / TOCTOU** (`token.py:94` re-check state at commit; broker CAS `broker_core.py:250`) | re-read safety-critical state at actuation commit; reject if the world moved since the plan | **Architectural** — recheck at commit, not just at decision | robotics commit gate (re-check margins/obstacles at the actuation tick) | a plan computed at t is rejected if obstacle state changed by commit tick |
| **Replay / stale-decision rejection** (`token.py:64` single-use nonce; durable at-most-once `replaystore.py`) | reject a stale/duplicated actuation command (e.g. a delayed replan) | **Architectural** — at-most-once + freshness on the decision→actuation handoff | monotonic decision id + freshness window on the command bus | a re-sent or out-of-order command is dropped |
| **Bounded deterministic remediation** (`remediation.py:50` fixed retry classes; broker `reconcile()`) | fixed, finite safe-recovery set (stop, slow, minimum-risk maneuver, hand-back) | **Architectural (partial)** — finite deterministic recovery *classes*; **NOT** ActionGate's human-resubmission model | genuinely new: continuous/real-time recovery actuation (ActionGate marks this out of model) | recovery set is finite, deterministic, and safety-validated |
| **Tamper-evident decision trace** (`audit.py:51` hash-chained log) | append-only, hash-chained decision/trust trace for incident recall | **Architectural** — hash-chained audit is domain-free | robotics record fields (trust states, chosen action, snapshot id); reuse the chaining idea, not the HMAC key custody | chain verifies; first tampered record locatable |

### Bonus patterns worth adopting

* **Independent recomputation (N5)** (`broker_core.py:110` — the executor trusts
  nothing the gateway asserted, recomputes identity). → **Architectural.** A
  robotics *plan/actuation split* where the actuation layer re-derives
  admissibility from first principles is a strong reliability pattern.
* **Deterministic/replayable decision** (`gate.py:144`). → **Architectural.**
  Matches this milestone's own reproducibility discipline.

## 4. Explicitly NOT reused (enterprise policy / wrong domain)

Operation vocabulary enum (`schema.py:34` IAM/DB/NET), `extract_facts` adapter
(`gate.py:46`), signed default policy rules (`policy.py`), human approval
SoD/four-eyes (`approval.py`), constraint-fishing disclosure modes
(`remediation.py:36`), and the Kubernetes/mTLS broker
(`action_gateway_k8s/`). None of these map to robot control.

## 5. Default-expectation check (from the milestone)

* **Architectural reuse is strong** — confirmed: 8 of 9 properties reuse at the
  pattern level, and ActionGate's own layering already separates them from
  enterprise data.
* **Direct code reuse is limited** — confirmed: the reference is enterprise-typed
  end-to-end; robotics needs its own envelope, invariants, and actuation broker.
* **Mathematical reuse must earn its place** — confirmed: essentially none
  transfers; ActionGate's "math" is hashing + precedence lattices, orthogonal to
  the predictor-trust and control problems.

## 6. Consequence for Robotics V2

The V2 predictor-trust and action-selection layers already prototyped in
`robotics_reliability_bench/` independently arrived at ActionGate's core
architectural properties (non-compensatory hard gate, explicit
`ABSTAIN`/`NO_SAFE_ACTION`, no forced winner, per-decision state). Adopting the
remaining three — evidence/state binding, commit-time revalidation, and a
hash-chained decision trace — is the recommended architectural (not code, not
mathematical) borrow. Details in `ROBOTICS_V2_MIGRATION_PLAN.md`.
