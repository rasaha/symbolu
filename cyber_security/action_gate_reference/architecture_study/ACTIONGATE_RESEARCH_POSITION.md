# ActionGate — Research Position & Category

**Status:** architecture study (documentation only). Answers (5) the most accurate category and
(7) whether there is publishable research. **[fact]** = code/test-grounded, **[interpretation]** =
reading, **[speculative]** / **evidence-required** = not yet demonstrated.

## Part A — Primary category (Question 5)

Candidate categories: authorization engine · policy engine · execution governance · AI firewall ·
transaction manager · runtime verifier · commit protocol.

Assessed against the architecture:

| category | fit | why |
|---|---|---|
| authorization engine | accurate for the **core** `D` **[fact]** | but omits the token/nonce/TOCTOU/audit machinery |
| policy engine | partial | operator set is fixed, not a general language (OPA is the policy-engine archetype) |
| AI firewall | misleading | it does not filter traffic/prompts; the LLM is simply outside the boundary |
| transaction manager | **over**states | no locking, no distributed 2PC, no resource rollback (see transaction analysis §3) |
| runtime verifier | partial | it verifies at commit, but also *authorizes*, mints capability, and records — more than a verifier |
| execution governance | accurate product framing | broad; captures "governs what may execute" |
| **commit protocol** | **most architecturally precise** | it is a BEGIN/VALIDATE/PREPARE/COMMIT protocol binding an authorization decision to a replay-proof, TOCTOU-checked, audited commit |

**Recommendation [interpretation]:** the single most architecturally accurate primary category is a
**deterministic action-commit protocol** (short: **commit protocol**) whose decision core is an
**authorization engine**. Precisely:

> **ActionGate is a deterministic, evidence-bound commit protocol for authorizing discrete
> high-consequence actions by autonomous agents.**

**On "AI Transaction Manager":** it is *marketing-accurate and partly technically accurate* — the
BEGIN/VALIDATE/PREPARE/COMMIT spine is real (`ACTIONGATE_TRANSACTION_ANALYSIS.md`) — but it
**overstates** the parts ActionGate does not implement (locking, distributed 2PC, resource
rollback). If the product name must use "transaction," the defensible form is **"AI
transaction-*authorization* engine"** or **"AI action-commit protocol,"** not a bare "transaction
manager." Use "execution governance" as the accessible product category and "commit protocol" as
the technical one.

## Part B — Is there publishable research? (Question 7)

### What is genuinely novel [interpretation, grounded in [fact]]
1. **Evidence-bound, per-action-instance authorization with a canonical action hash.** Decisions
   bind to `projection.action_hash` and to `evidence`/`approvals` that must reference that exact
   hash (`verify_binding`, `verify_approval`). This is unlike IAM (principal→permission) and unlike
   OPA (decision without commit binding).
2. **LLM strictly outside the trust boundary, yet the system is still useful to agents.** The
   decision is a pure deterministic function; R1/R1.5/R2 add *advisory* remediation and a *measured*
   study showing a deterministic remediation loop suffices and an LLM planner is not justified on
   current evidence. The "agents governed by a deterministic gate, planner excluded from the trust
   boundary, remediation as read-only advice" pattern is a defensible research framing.
3. **A single-action commit protocol** (token + nonce + commit-time TOCTOU revalidation +
   hash-chained audit) that gives **exactly-once, replay-proof** execution of agent tool calls.

### What evidence already exists [fact]
- A working reference implementation with a written canonicalization/hashing spec and **24 passing
  conformance vectors** (`conformance.py`), including replay (`E_NONCE_REPLAY`), TOCTOU
  (`E_STALE_STATE`), domain-separation, and projection-exclusion vectors.
- Deterministic decision function with pinned `action_hash` digests.
- The R1/R1.5/R2 milestones: a frozen remediation projection, runtime integration with
  compatibility/security tests, and a **measured** 153-scenario corpus + retry-governance study
  with security invariants (no DENY bypass, fresh hash per modification, no token reuse) and a
  reproducible metrics artifact.

### What evidence is still required (honest gaps) — **evidence-required**
- **Formal security model.** Determinism is demonstrated by tests; replay/TOCTOU impossibility is
  argued informally. A formal model (or model-checked spec) of the commit protocol's safety
  (no authority crosses action identities; exactly-once) would elevate a security-paper claim.
- **Production crypto & threat model.** Current signing is reference HMAC; a real asymmetric PKI,
  key-custody threat model, and audit tamper-*proofing* are out of scope and must exist before
  strong security claims.
- **Scale / performance evidence.** No throughput, latency, or contention data under real
  concurrency; a systems paper needs measured performance and a serializability argument for the
  commit critical section.
- **Independent domain prototypes.** The generalization claims (ERP/banking/robotics) are
  **[speculative]** until at least one non-cloud domain is implemented end-to-end.
- **Comparative evaluation.** No head-to-head against OPA/IAM on a shared benchmark.

### Which paper, honestly
- **Security paper — viable now-to-soon [interpretation].** "Deterministic, evidence-bound,
  commit-time authorization for autonomous agents, with the planner outside the trust boundary."
  The reference implementation + conformance vectors + R2 measured study are real evidence; a
  formal safety argument and production threat model would make it strong (workshop → conference).
- **Systems / transaction-processing paper — not yet [interpretation].** The transaction framing is
  a *design pattern*, not a novel concurrency/recovery algorithm; there is no new scheduler,
  distributed-commit protocol, or recovery mechanism. This would become viable only if a genuine
  multi-action / multi-resource coordinator (with a real isolation/recovery contribution) were
  built — which the current architecture deliberately does not include.
- **Product architecture — solid today [interpretation].** The design is coherent and defensible as
  a product: a per-action commit gate for agentic systems.

### Bottom line
**[interpretation]** There is a credible **security/systems-security** paper in the architecture and
the R2 evidence, contingent on a formal safety model and a production threat model. The
"transaction-processing" angle is a *framing*, publishable only if the missing transaction
machinery (multi-action atomicity, isolation/recovery) is actually built. The product-architecture
case stands on its own today.
