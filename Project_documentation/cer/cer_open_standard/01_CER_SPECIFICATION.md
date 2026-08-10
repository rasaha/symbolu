# CER Specification — Definition, Identity, Execution Semantics (Deliverables 2, 3, 4)

Standards-committee draft. Design only; no implementation. Builds on the schema in `../execution_proposal_universality/01_CANONICAL_PROPOSAL_FIELDS.md`, recast as a formal spec with the CloudEvents-style **envelope + domain-profile** structure (falsification TF4).

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION`.

---

## Deliverable 2 — Define CER (minimal specification)

### 2.1 Structure: a neutral envelope + a domain-profiled action

**RECOMMENDATION.** CER has two parts, mirroring CloudEvents (a fixed envelope, a producer-defined `data`):
- **The CER envelope** — fixed, universal, standardized. Identity, principal, authority, verdict-binding, audit anchors.
- **The action body** — shaped by a **domain profile** (k8s, db, filesystem, robot, …). The envelope treats it as content-addressed bytes; the profile defines its schema and semantics.

This is the single most important structural decision: **the standard fixes the envelope; profiles fix the semantics.** It is what keeps CER universal without becoming either too abstract or too domain-specific.

### 2.2 The seven sections (per the deliverable's required split)

```jsonc
{
  "cer_version": "1.0",                         // spec version (semver)
  "profile": "cer.k8s/1.0",                     // domain profile id (which action semantics)

  // ── IDENTITY ─────────────────────────────────────────────────
  "identity": {
    "action_digest": "sha256:…"                 // DERIVED: H(canonical action bytes); the request's name
  },

  // ── AUTHORIZATION (what authority is requested) ──────────────
  "authorization": {
    "principal":   { "id": "…", "key_id": "…", "signature": "…" },
    "credential_scope": { "principal": "…", "permissions": ["…"], "ttl_s": 0 },
    "delegation_chain": [ { "id": "…", "type": "…", "grants": ["…"] } ],
    "policy_ref": { "version": "…", "digest": "…" }   // WHICH policy, never the policy itself
  },

  // ── EXECUTION (what is to be done + lifecycle) ───────────────
  "execution": {
    "kind": "ACT | CANCEL | ROLLBACK | RETRY | SIMULATE",  // request kind (§4.3)
    "references": "sha256:…|null",              // for CANCEL/ROLLBACK/RETRY: the prior action_digest
    "action": {                                 // domain-profiled body (for ACT/SIMULATE)
      "tool":       { "namespace": "k8s", "name": "scale" },
      "operation":  "WRITE",                    // universal class (§4.1)
      "targets":    [ { "type": "deployment", "id": "protected/web" } ],
      "arguments":  { "replicas": "3" },        // canonical, typed-string numerics
      "reversibility": "REVERSIBLE",
      "mode":       "COMMIT | LONG_RUNNING"     // §4.4
    },
    "state_binding": { "world_state_hash": "…|null", "observed_at": "…", "source": "…" }
  },

  // ── EVIDENCE (optional; may only raise scrutiny) ─────────────
  "evidence": { "risk_level": "…", "uncertainty": 0.0, "expected_effects": [], "attestation": {} },

  // ── METADATA (never affects identity) ────────────────────────
  "metadata": { "runtime": "…", "model": "…", "objective": "…", "correlation_id": "…", "created_at": "…" },

  // ── AUDIT (anchors, not the log) ─────────────────────────────
  "audit": { "prev_digest": "sha256:…|null", "trace_ref": "…" }
}
```

### 2.3 The four buckets (Mandatory / Optional / Metadata / Identity)

| Bucket | Fields | Rule (FACT/INTERPRETATION) |
|---|---|---|
| **Mandatory** | `cer_version`, `profile`, `authorization.{principal, credential_scope, policy_ref}`, `execution.{kind, action.{tool, operation, targets, arguments, reversibility}}` | producible by any action-taking runtime; read by ActionGate's predicates (`FACT`: `gate.py:46–234`) |
| **Optional** | `execution.state_binding`, `authorization.delegation_chain`, `evidence.*`, `audit.*` | raise scrutiny / enable a layer; **never lower a bar** (`FACT`: ActionGate evidence contract) |
| **Metadata** | `metadata.*` (runtime, model, objective, correlation_id, created_at) | recorded; **MUST NOT** affect identity (Deliverable 3) |
| **Identity** | `identity.action_digest` (derived) | a pure function of the canonical **action**, nothing else |

### 2.4 What MUST NOT belong inside CER

**RECOMMENDATION — normative exclusions (a CER carrying these is malformed):**
- **Reasoning internals:** prompt, system message, chain-of-thought, scratchpad, reasoning trace, plan graph, reflection state — `FACT`: the Control Plane reads none of these (grep-clean, `../ai_control_plane_v3/02`).
- **Model internals:** weights, logits, sampling params.
- **The policy itself:** only `policy_ref`. Embedding policy couples the standard to one governor (TF3).
- **The world-model / live state values beyond a `state_binding` hash:** the domain owns the world; CER carries only a *binding*, not the world.
- **Runtime/session/orchestration state:** graph, crew, conversation history.
- **The verdict:** CER is a *request*; the verdict is the control plane's *response* (kept in a separate response object, §Deliverable 10).

**INTERPRETATION.** The exclusions are the spec's backbone: every one of them, if admitted, would couple CER to a runtime, a model, a governor, or a domain — destroying universality. The discipline "CER describes a *governed actuation request*, nothing about how it was thought of or who will judge it" is the whole standard.

---

## Deliverable 3 — Identity Model

### 3.1 What defines a request's identity
**RECOMMENDATION.** `action_digest = H( canonical_bytes( execution.action ⊕ authorization.credential_scope ⊕ execution.references ⊕ policy_ref ⊕ profile ) )`.
Identity = *the exact actuation + the authority it requests + the policy in force + (for lifecycle kinds) the request it acts on*. Two requests with the same identity are the same governed request.

### 3.2 Metadata that must NEVER affect identity
**FACT-motivated (fixes the R3/K8 bug from prior milestones — ActionGate currently hashes these, `projection.py:44–46`):**
- `metadata.runtime`, `metadata.model`, `metadata.objective`, `metadata.correlation_id`, `metadata.created_at`
- `authorization.principal.signature`, per-attempt ids/timestamps
- `evidence.*` (a runtime's opinion of the action, not the action)

**Why:** so the *same actuation from OpenAI, LangGraph, and Claude Code collapses to one identity* (`../execution_proposal_universality/`, Deliverable 5). If provenance were hashed, cross-vendor requests could never match — fatal for a universal standard.

### 3.3 Hashing
**RECOMMENDATION** — reuse the in-repo profile (`FACT`: it exists): **JCS (RFC 8785)** canonical JSON — UTF-8/NFC, keys sorted by UTF-16 code unit, **typed-string numerics (no bare JSON numbers)**, NaN/Inf/dup-keys rejected (`jcs.py`) — then a **domain-separated, length-prefixed digest** `H(LP(tag)‖LP(canon_ver)‖LP(schema_ver)‖LP(bytes))` (`hashing.py`). SHA-256 default; the digest is prefixed with its algorithm (`sha256:…`) for agility. Conformance vectors already anchor this (`fixtures/conformance_vectors.json`).

### 3.4 Replay
**RECOMMENDATION.** Replay protection is a property of *execution*, not identity: a CER is authorized **once** and consumed with a **single-use nonce/token** (`FACT`: ActionGate mints single-use tokens). The *same* `action_digest` may legitimately recur (retrying the same action later) — so replay is defended by (a) nonce single-use at authorization and (b) commit-time state revalidation (`FACT`: `CommitStateRevalidator`), **not** by forbidding identical digests. Identity stability and replay defense are orthogonal — a subtle but essential standards point.

### 3.5 Versioning
**RECOMMENDATION** — three independent version axes, each semver, never conflated:
- `cer_version` — the envelope spec version.
- `profile` version — the domain action schema (e.g., `cer.k8s/1.0`).
- `policy_ref.version` — the enterprise policy.
Digests are computed *within* a (cer_version, profile) pair; cross-version equality is undefined by design (a spec change is a new namespace, like OCI media-type versions). **Capability negotiation** (Deliverable 9) resolves which versions a control plane accepts.

---

## Deliverable 4 — Execution Semantics

### 4.1 The universal operation taxonomy (small, closed, domain-neutral)
**RECOMMENDATION.** A closed set of *consequence classes* — not domain verbs: `READ · WRITE · EXECUTE · DELETE · GRANT · TRANSFER · CONFIGURE · DEPLOY · COMMUNICATE · OTHER`. These classify *what kind of consequence* an action has, which is what policy and safety reason about, and they are stable across domains. Domain verbs (k8s `scale`, db `UPDATE`, robot `move`) live in `action.tool` + the profile; the profile maps its verbs to these classes.

### 4.2 How each required operation domain is expressed
| Domain | Expressed as (profile) | Notes |
|---|---|---|
| **API** | `tool={api,method}`, operation per HTTP verb class | REST/gRPC call as an action |
| **Database** | `tool={db,query}`, operation WRITE/DELETE/READ, targets=tables/rows | args carry the parameterized statement |
| **Filesystem** | `tool={fs,op}`, operation WRITE/DELETE/READ, targets=paths | |
| **Kubernetes** | `tool={k8s,verb}`, targets=namespaced objects | the in-repo reference domain (`FACT`) |
| **Robot** | `tool={robot,actuation}`, operation EXECUTE, args=kinematics | ACP's native domain (`FACT`: robotics core) |
| **Cloud** | `tool={cloud,op}`, operation CONFIGURE/DEPLOY | |
| **Workflow** | a workflow *step* is one CER; the workflow is a sequence of CERs sharing `correlation_id` | CER governs *actions*, not the orchestration between them |
| **External service** | `tool={svc,call}`, operation COMMUNICATE/TRANSFER | |

### 4.3 Lifecycle operations are REQUEST KINDS, not new action types
**INTERPRETATION — a key design decision.** Cancellation, rollback, retry, and simulation are not new *actions*; they are *requests about a prior request*. So they are `execution.kind` values that reference a prior `action_digest`:

| `kind` | Meaning | References | Governed how |
|---|---|---|---|
| `ACT` | perform the action | — | full authorization + safety |
| `SIMULATE` | dry-run; produce expected_effects, never commit | — | authorized as a read-equivalent; the CP may require it before an ACT (`SIMULATE_AND_RETRY`) |
| `CANCEL` | stop an in-flight/long-running action | prior digest | authorized against the *right to cancel* that action |
| `ROLLBACK` | reverse a committed action | prior digest | **itself a new governed action** — a compensating actuation that ActionGate/ACP authorize independently (never an ungoverned undo) |
| `RETRY` | re-attempt a failed action | prior digest | a fresh authorization; same `action_digest`, new nonce (§3.4) |

**Why this matters for universality:** every runtime already has these lifecycle notions in some form; modeling them as *kinds referencing a digest* means the standard needs **no per-runtime lifecycle vocabulary** — just the digest reference. And it enforces the safety rule that a rollback is a governed action, not a trusted escape hatch.

### 4.4 Long-running tasks and human approval (the two that aren't simple actions)
- **Long-running task:** `action.mode = LONG_RUNNING`. The CER opens a durable execution handle; the control plane authorizes the *opening*, and the runtime must re-bind state and re-authorize at defined checkpoints (`FACT`: ACP evaluates against *live* state per tick, so long-running work cannot cache authority). The task's progress/observations return to the runtime (the loop, from `../execution_proposal_engine/` F1).
- **Human approval:** **not a CER the runtime emits.** It is a *verdict the control plane returns* (`ESCALATE_TO_HUMAN`) and an approval object bound to the `action_digest` (`FACT`: ActionGate approvals bound to action_hash). The runtime *routes* the approval UX; it never owns the approval authority. This keeps "human approval" out of the request schema and in the response/verdict, where it belongs.

### 4.5 Semantic-ambiguity guard (falsification TF4, closed)
**RECOMMENDATION.** Because operation *classes* are universal but operation *verbs* are profiled, a control plane must **reject a CER whose `profile` it does not understand** (fail-closed) rather than guess semantics. Capability negotiation (Deliverable 9) advertises supported profiles. This prevents the "DELETE means different things" ambiguity from ever reaching a decision: an unknown profile is an explicit `UNSUPPORTED_PROFILE`, not a mis-authorization.
