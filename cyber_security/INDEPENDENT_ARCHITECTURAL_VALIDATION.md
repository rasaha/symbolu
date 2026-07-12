# Independent Architectural Validation — Action Gateway

*An adversarial replication study by a notional independent security research group.
Prior verdicts (`ISOLATED_GATE_THESIS_SUPPORTED`, "26/26 blocked", "production-grade
isolation") are treated as unproven until re-established from code, tests, and
runtime behavior. Where implementation contradicts documentation, implementation
wins. No code was written or changed for this study; all findings are grounded in
source inspection with file:line citations.*

---

## Methodology

1. **De-biasing.** Discarded every prior conclusion and comment. Re-derived the
   enforced threat model from `action_gateway_isolated/` source, the SQLite/mTLS/
   netns runtime, and the test/harness code — not from `README`/`THREAT_MODEL`.
2. **Fresh attack tree.** Built a new attack taxonomy from scratch (parser/
   serialization/commit/quorum/supply-chain/transport classes), deliberately
   *not* reusing the internal `redteam.py` list, then checked each class against
   the actual code paths.
3. **Falsification bias.** Every claimed property is presumed false until an
   executable or code-provable mechanism establishes it; a mechanism that is only
   *asserted* in the harness counts as unproven.
4. **Scope.** The system's own stated adversary: a fully compromised agent with
   arbitrary code execution, confined to a network namespace + unprivileged user,
   reaching only the gateway Unix socket.

### What the code actually enforces (reconstructed, not from docs)

Genuinely enforced and independently re-verifiable: (a) the agent process runs in
a fresh net namespace and separate uid, so the apiserver/broker TCP endpoints are
unreachable and every private key / kubeconfig / DB is `PermissionError`
(`redteam.py` probe, reproduced); (b) cross-boundary artifacts are Ed25519 with
public-key-only verifiers (`crypto.py`, `authz.py`); (c) a SQLite store gives
single-process durable nonce/commit claims (`replaystore.py`); (d) updates use a
`resourceVersion` CAS (`broker_core.py:174-177`). These four are real.

Everything else in the "SUPPORTED" verdict required scrutiny — and several claims
did not survive it.

---

## Phase 2 — Fresh attack tree and discovered attack classes

New attack classes, each checked against code. **D = demonstrated from code; A =
architecturally argued.**

### N1 — Policy-completeness bypass via non-`containers` fields (D) — **HIGH**
`policy_semantic.check` iterates **only** `spec.containers`
(`policy_semantic.py:66`). It never inspects `initContainers`,
`ephemeralContainers`, `envFrom`, `serviceAccountName`, or
`automountServiceAccountToken`. Consequences the compromised agent can obtain
through the normal gateway channel:
- An `initContainer` with an **untrusted image** (`nginx:latest`, or any non-
  pinned image) produces **zero** violations → the gateway issues admission
  evidence → the broker re-check (same function, same blind spot) passes → the
  Deployment is **admitted**. `image_provenance` is not a PodSecurity control, so
  the apiserver dry-run does not catch it either. The claimed invariant "require
  provenance for deploy artifacts" is **false by construction**.
- `envFrom: [{secretRef: {name: app-secret}}]` bypasses both `secret_env`
  (checks only `env[].valueFrom.secretKeyRef`) and `secret_mount` (checks only
  `volumes[].secret`) → a secret-exfiltration manifest is admitted.
- `serviceAccountName: <privileged-sa>` in a pod template is unchecked → a
  workload can be bound to a stronger identity than the action implies.

This is a genuine unauthorized protected-state mutation **within** the stated
threat model. The internal `A30_canary` only compares `app-config.tier`
(`redteam.py`), so it would not detect the admitted malicious Deployment.

### N2 — Double-commit + residual RBAC + audit gap on teardown failure (D) — **HIGH**
`_mint_scope_and_write` performs the cluster write, then runs
`_teardown_verified` in a `finally` (`broker_core.py:159-163`). If teardown fails
(a transient API error, an etcd hiccup, a 500), `_teardown_verified` raises
`E_TEARDOWN` **after the write already succeeded**. `execute` catches it and calls
`self.replay.release_commit(ah)` (`broker_core.py:124-126`), which deletes the
commit claim because `finalize_commit` was never reached. Net effect of one
induced teardown failure:
- the single-commit invariant is **released** → a re-approved/retried identical
  action can `claim_commit` again and **execute a second time**;
- the per-action ServiceAccount/Role/RoleBinding **persist** and the minted bearer
  token remains valid for its 600 s TTL (**residual privileged capability**);
- **no `COMMIT` audit record** is written (only `TEARDOWN_FAILURE`) though the
  mutation happened → audit desynchronization.

The internal suite's `A19_cleanup_residual` is hard-coded `blocked=True` with
reasoning only — the path was never executed, so this bug was never surfaced.

### N3 — Partial commit / dual-write / crash recovery (D) — **MEDIUM**
The durable commit claim (SQLite), the cluster mutation (apiserver), and the audit
append (SQLite) are three separate systems written sequentially
(`broker_core.py:117-130`) with no distributed transaction or idempotency key
tying them. A crash **after** the cluster write but **before**
`finalize_commit`/`_audit` yields a real mutation that is unaudited and whose
commit row is un-finalized (blocks replay — good) but whose audit is permanently
missing. "Every execution produces an audit record" is not crash-safe.

### N4 — Agent-triggerable gateway DoS via the allowed channel (D) — **MEDIUM**
`serve_unix` is single-threaded and sets **no timeout** on accepted connections
(`rpc.py:45-` onward; the accept loop processes one connection to completion
before the next). The agent — which legitimately reaches this socket — can:
- open a connection, send a 4-byte length prefix of `0xFFFFFFFF`, then stall →
  `_recvn` blocks forever → the gateway serves no one else (**slow-loris**);
- send a huge length prefix and trickle bytes → `_recvn` accumulates up to ~4 GiB
  in `buf` (**memory exhaustion**); there is no `struct` length bound.
`A24_flood` measured only 50 sequential `get`s and is labelled "availability-only";
this class was not tested.

### N5 — The broker never recomputes the action hash (D) — **MEDIUM (architectural)**
`broker_core.execute` consumes `intent["action_hash"]`, `["policy_hash"]`,
`["manifest"]`, `["namespace"/"kind"/"name"]` as **gateway-asserted** fields
(`broker_core.py:87-93`). It never recomputes `action_hash = H(manifest, target,
…)`. Replay-freedom, single-commit, and approval binding are therefore anchored to
a label the gateway *asserts* corresponds to the action — not to a value the
broker verifies. Under the stated (compromised-agent) model the agent cannot forge
the gateway signature, so this is not agent-exploitable; but it means the
advertised "**exact-action** binding" is really "**gateway-asserted-label**
binding," relocating the crux of the novelty into gateway trust. An approval for
action X and a manifest for action Y are only kept consistent by the honest
gateway, not by the broker.

### N6 — Unmeasured red-team verdict inflation (D) — **HIGH (methodology)**
Of the 26 "blocked" results, **9 are hard-coded `blocked=True` with prose only**
and no execution: `A2, A6, A7, A9, A13, A14, A15, A16, A19` (`redteam.py`). The
verdict `decide()` counts these equally. So "26/26 blocked" is **17 measured + 9
asserted**. Some assertions are defensible (A6/A7/A13 follow from the measured
network isolation), but `A14`/`A15` (modify/retarget after approval) and `A19`
(teardown residual) are *not* independently measured, and N1/N2 show at least one
of them (A19) hides a real defect. A study cannot grade its own unfalsifiable
claims as passes.

### N7 — Split-brain / distributed replay (A→D by design) — **MEDIUM**
Durable replay is a **single SQLite file** on one host (`layout.REPLAY_DB`). The
"multi-instance" test ran instances on one host sharing that file. Across hosts,
SQLite file locking is not a distributed transaction; two brokers on two hosts (or
a network partition, or NFS) have **no** shared atomic commit → the single-commit
and nonce-single-use guarantees fail (distributed double-commit). The claim
"survives multi-instance execution" is proven only for co-located processes.

### N8 — Supply-chain: unverified fetch of the trust base (D) — **MEDIUM**
`../action_gateway_k8s/scripts/cluster_up.sh` downloads `kubectl`, `kube-apiserver`
and `etcd` via `curl` with **no checksum or signature verification**. The isolated
deployment's own signing library, `ecdsa`, is `pip install`-ed unpinned from PyPI
(`scripts/deploy.sh` path / README). The integrity of the entire asymmetric-
signing story rests on an unverified, unpinned dependency fetch. (in-toto/Sigstore/
SLSA — which the system's docs invoke conceptually — are not applied to its own
build.)

### N9 — Unframed ad-hoc hashing (D) — **LOW**
`gateway_core` builds the state hash as `H(f"{ns}/{kind}/{name}@{rv}")` — plain
string concatenation, *not* the length-prefix framing the frozen
`ACTION_CANONICALIZATION_AND_HASHING_SPEC` mandates elsewhere. Kubernetes charset
limits make a practical collision unlikely, but it is a canonicalization
inconsistency inside the same system, in the field that anchors TOCTOU.

### N10 — Coarse transport identity; hostname check disabled (D) — **LOW**
`mtls_client_ctx` sets `check_hostname=False` (`rpc.py`), and the broker authorizes
by a CN **string match** (`_peer_cn == "gateway"`) with no certificate pinning. The
local CA issues only the one gateway cert, so exploitation needs the CA — but the
identity check is weaker than the "authenticated workload identity" framing
implies (any CA-signed CN=gateway cert is accepted).

### N11 — Parser differential surface (A) — **LOW (bounded here)**
Two JSON realms exist: Python `json` (used for hashing, semantic checks, and
`manifest_json`) and the apiserver's Go decoder (final apply). Duplicate-key and
type-coercion differentials are neutralized because the manifest is normalized to a
Python dict *before* both the check and the re-serialized apply. The real residual
differential is **field coverage** (N1), not encoding.

### Classes checked and found adequately handled
Forged approval/token (Ed25519, measured reject); direct network/credential access
(netns/uid, measured); TOCTOU on `update` (CAS, measured deterministically);
downgrade to HMAC (no HMAC acceptance path in the broker — verified); replay within
one host across restart (durable store, measured).

---

## Phase 3 — Assumptions (classified)

| # | Assumption | Class | If false, what breaks |
|---|---|---|---|
| 1 | Broker process is uncompromised | Operational | Total loss — broker holds admin creds; no second-broker/Byzantine defense |
| 2 | Signing-root/approver/checkpoint keys stay offline | Operational (here: only file perms) | Forge policy/approvals/checkpoints; here no HSM, so root/host compromise = forgery |
| 3 | The gateway honestly computes `action_hash`↔action | **Mathematically required, unverified by broker** (N5) | "Exact-action" binding collapses to gateway trust |
| 4 | Policy checks are complete | **Unrealistic** (N1, demonstrably false) | Untrusted-image/secret-`envFrom`/SA-swap manifests admitted |
| 5 | One shared transactional replay store reachable by all instances | Engineering shortcut (N7) | Distributed double-commit / replay across hosts |
| 6 | No crash between cluster write and audit/finalize | **Unrealistic** (N3) | Unaudited mutation; audit-completeness claim void |
| 7 | Teardown always succeeds or its failure is safe | Engineering (false — N2) | Double-commit + residual capability + audit gap |
| 8 | Single-threaded gateway is not a target | Engineering (false — N4) | Agent DoS via the allowed channel |
| 9 | apiserver + PodSecurity + optimistic concurrency correct | Mathematically/operationally required | If false, all enforcement void (reasonable to assume) |
| 10 | `ecdsa` correct, sufficiently constant-time, and authentically fetched | Engineering shortcut (N8) | Signature integrity is the whole system; unpinned + pure-Python |
| 11 | `unshare --net` fully isolates the agent network | Operational (holds on this host) | UDS still crosses; a shared abstract socket or bind-mount would leak |
| 12 | Host/kernel not root-compromised; single host | Operational | Namespaces/users provide no defense against host root |

---

## Phase 4 — Proof obligations

| Claimed property | Assumptions | Theorem (informal) | Missing proof | Executable evidence today | Residual uncertainty |
|---|---|---|---|---|---|
| No unauthorized protected mutation | 1,3,4,9 | ∀ agent action reaching the cluster ⇒ it was admissible+approved | Completeness of `policy_semantic` | **Falsified** by N1 (initContainer) | High — policy is incomplete |
| Exact-action binding | 3 | committed action = approved action, byte-for-byte | Broker recomputation of `action_hash` | Partial (gateway builds it; broker trusts it — N5) | Medium |
| Single-use / no replay | 5,7 | each token/approval/commit used ≤ once | Atomicity across write+claim+teardown; cross-host | Single-host measured; **N2/N7 break it** | High off-host / on teardown fail |
| TOCTOU closed | 9 | no write on stale state | Coverage for create/delete under races (only `update` CAS measured) | `update` CAS measured (deterministic) | Medium (create/delete races unmeasured) |
| Complete tamper-evident audit | 6,2 | every commit is durably, unforgeably logged | Crash-atomicity of write↔audit; checkpoint liveness | Chain+checkpoint verify; **N3 breaks completeness** | High (dual-write) |
| Agent isolation | 11,12 | agent holds no creds and no path | — | **Measured** (probe: all `PermissionError`/unreachable) | Low (single host) |
| Non-forgeability of authz | 2,10 | agent/gateway cannot forge approvals/policy | Key custody realism; lib authenticity | Ed25519 cross-key reject measured | Medium (custody = file perms; unpinned lib) |
| At-most-one commit under concurrency | 5 | parallel duplicates ⇒ ≤1 commit | Cross-host coordination | On-host measured; **N7** off-host | High off-host |

---

## Phase 5 — Literature comparison (brutally honest)

The core idea — *bind authorization to an exact, canonically-hashed action and
mint a single-use, action-scoped, short-lived credential, gated by a signed
decision + human approval at a vendor-neutral choke point* — is a **recombination
of well-established prior art**, not a new primitive:

- **Object-capability systems / KeyKOS / EROS / seL4 / CHERI / CHERI-caps.** The
  broker-minted, resource/verb-scoped, short-lived token *is* an ocap: unforgeable,
  least-authority, near-single-use. "Authorize the exact operation, once" is the
  ocap principle. This system applies ocap to Kubernetes RBAC via TokenRequest —
  an engineering instantiation, not a new model.
- **Google Binary Authorization + in-toto + Sigstore + SLSA.** "Require signed
  provenance/attestation and approval before a deploy action" is exactly attestation-
  gated admission. The system's provenance/rollback/approval gates overlap this
  directly (and it does *not* apply these tools to its own build — N8).
- **Microsoft Entra PIM / CyberArk.** JIT approval → time-boxed, scoped, brokered
  credential is the closest operational analog. The delta here is *action-hash*
  binding + *single-use* instead of a time window — an increment on PIM, and one
  that overlaps HSM/payments **transaction authorization** (sign the exact
  transaction, not a session), which predates all of this by decades.
- **SPIFFE/SPIRE.** Used directly for workload identity (mTLS/SPIFFE IDs).
- **Zanzibar / Cedar / OPA / Kubernetes Admission (Kyverno/Gatekeeper).** The
  decision/policy layer overlaps; those engines are mature and would not have the
  N1 completeness gap. AWS IAM / BeyondCorp / Zero Trust cover per-request,
  identity-aware authorization.

**Conclusion:** every component (ocap credential, attestation-gated admission, JIT
approval, transaction-exact authorization, tamper-evident log, workload identity)
exists in the literature/products. No component is new. The *combination framed for
autonomous-agent tool-calls* is the only arguably-fresh element, and it is an
integration.

---

## Phase 6 — Novelty (architecture only)

**Score: B (good integration), reaching toward C but not achieving it.**

- Not **A**: it is more than obvious plumbing — the action-envelope canonicalization,
  the decision/broker split, and the ocap-over-RBAC mapping are non-trivial
  integration.
- **B** justified: a competent, coherent assembly of ocap + attestation-gated
  admission + JIT approval + tamper-evident audit + SPIFFE, aimed at a real emerging
  boundary (agent tool-calls).
- Falls short of **C**: the only candidate novel contribution — "exact-action,
  single-use authorization for heterogeneous agent tool-calls" — (i) is undercut by
  N5 (the broker doesn't actually bind to the action, only to a gateway-asserted
  label), and (ii) is substantially prior art (transaction authorization + ocap +
  Binary Authorization). There is no new abstraction, mechanism, or proof.
- Not **D/E**: no publishable systems contribution or new abstraction.

---

## Phase 7 — Academic review (SOSP / OSDI / USENIX Security / IEEE S&P)

**Recommendation: Reject (as a research paper).** Strong engineering artifact,
insufficient research contribution and evaluation.

**Major weaknesses**
1. No new abstraction or formal model; core idea is ocap + Binary Authorization +
   PIM recombined (Phase 5), unacknowledged.
2. Evaluation is single-host, single-broker; distributed/ Byzantine/ split-brain
   (N7) untested although the system claims multi-instance guarantees.
3. Demonstrated security holes within the threat model: policy incompleteness (N1),
   double-commit/residual on teardown failure (N2), agent DoS (N4).
4. ~35% of the red-team is asserted, not executed (N6); the headline "26/26" is not
   an empirical result.
5. The central "exact-action binding" is not enforced by the component that mints
   credentials (N5).

**Minor weaknesses**
Dual-write audit non-atomicity (N3); ad-hoc unframed hashing (N9); coarse mTLS
identity (N10); unpinned/unverified trust-base fetch (N8); pure-Python non-audited
crypto.

**Missing experiments**
Multi-host adversarial run; induced teardown/crash fault injection; slow-loris/
malformed-transport load; an *external* red-team (not the authors'); a policy-
completeness differential vs. Kyverno/Gatekeeper on a manifest corpus.

**Required comparisons**
Head-to-head with Binary Authorization + Kyverno + Entra PIM on the same workload,
showing an attack this stops that the composition does not.

**Rejected claims**
"No unauthorized protected-state mutation" (N1); "26/26 blocked" (N6);
"complete/immutable audit" (N3, N2); "closes the TOCTOU write gap" — only the
`update` path is shown, create/delete race coverage is asserted; "exact-action"
(N5).

**Acceptable claims**
Namespace+user isolation denies the agent creds/network (measured); Ed25519 removes
cross-boundary HMAC forgeability (measured); durable *single-host* replay and the
`update` CAS conflict work (measured).

---

## Phase 8 — VC diligence (Sequoia / a16z / Benchmark / Accel)

**Would not fund on the current security evidence.** The differentiator overlaps a
stack enterprises already run (Kyverno/OPA + Entra PIM/CyberArk + Binary
Authorization), and the prototype has in-scope, demonstrable breaks (N1, N2, N4)
plus a red-team that grades a third of its cases by author assertion (N6). The
"exact-action" moat is not actually enforced where credentials are minted (N5).

**Evidence that would change the decision** (fundable seed milestone):
1. An **external** red-team fails to breach a **multi-host, multi-broker** deployment
   (closing N7) with fault injection (N2/N3), and the harness measures every claim
   (closing N6).
2. A policy layer that is either provably complete or explicitly delegated to a
   mature engine (Kyverno/OPA), removing N1 — i.e., own only the *credential +
   approval + audit binding*, not the policy engine.
3. One design-partner incident where action-bound single-use authorization stops an
   agent action that the incumbent composition admits.

A thesis-driven agent-security investor might seed the *category* on team+timing,
but not on this artifact's security claims as stated.

---

## Phase 9 — Independent verdict

# PARTIALLY_SUPPORTED

**Justification (executable/code evidence only).**
- *Holds (measured):* the agent is genuinely isolated (no credentials, no network
  path — probe reproduced); cross-boundary authorization is asymmetric and non-
  forgeable by the agent/gateway (Ed25519, measured); single-host durable replay and
  the `update` CAS conflict work.
- *Falsified within the stated threat model (code-demonstrated):* the compromised
  agent can obtain an unauthorized protected-state mutation via `initContainers`/
  `envFrom` because the policy checker inspects only `spec.containers`
  (`policy_semantic.py:66`) — N1; a single teardown failure releases the commit
  claim after a successful write, enabling double-commit + residual privileged RBAC
  + a missing audit record (`broker_core.py:124-126,159-163`) — N2; the agent can
  DoS the single-threaded, timeout-less gateway through its only allowed channel —
  N4.
- *Overstated:* "26/26 blocked" is 17 measured + 9 asserted (N6); "complete audit"
  is not crash-atomic (N3); "multi-instance" is single-host only (N7); "exact-action
  binding" is gateway-asserted, not broker-verified (N5).

The isolation and asymmetric-authorization theses **survive** and were previously
under-credited as merely "conditional." But the "no unauthorized mutation,"
"complete audit," and "exact-action" theses **do not survive** independent
falsification — these are in-scope defects, not out-of-scope caveats. The prior
`STRONGLY_SUPPORTED`/"SUPPORTED" framing was **overly optimistic**; the honest
standing is **PARTIALLY_SUPPORTED**: a real isolation result wrapped around an
incomplete policy engine, a non-atomic commit/teardown path, and a partly-asserted
evaluation.

*Prioritized, evidence-driven fixes (only because weaknesses were demonstrated):*
inspect all container/`envFrom`/`serviceAccountName` fields or delegate policy to
Kyverno/OPA (N1); make finalize/teardown ordering fail-safe and never release a
claim after a successful write (N2); add server-side read timeouts + a threaded/
bounded transport (N4); recompute `action_hash` in the broker (N5); replace the 9
asserted attack outcomes with executed ones (N6).
