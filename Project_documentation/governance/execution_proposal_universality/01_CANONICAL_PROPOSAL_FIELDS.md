# Deliverable 1 — The Canonical Execution Proposal (fields only truly universal)

Refines the schema in `../execution_proposal_engine/EXECUTION_PROPOSAL_SCHEMA.md` for this milestone's specific requirement: separate fields into **Mandatory / Optional / Runtime-specific / Control-plane-specific**, keeping only what is *truly* universal in the mandatory set.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION`.

**Design axiom (from the falsification, FF1):** the proposal describes an **actuation** — the exact tool/API call the runtime is about to make — not the runtime's intent or reasoning. A field is *truly universal* only if it is a property of the actuation that every action-taking runtime necessarily has.

---

## 1. The four buckets

### MANDATORY — every runtime must supply; identity-bearing; producible by all
| Field | Why truly universal (FACT/INTERPRETATION) |
|---|---|
| `action.tool {namespace, name}` | every runtime actuates through *some* named tool/API |
| `action.operation` (READ/WRITE/EXECUTE/DELETE/GRANT/TRANSFER/CONFIGURE/DEPLOY/COMMUNICATE/OTHER) | every actuation has a consequence class |
| `action.targets[]` | every actuation touches resources |
| `action.arguments` (canonical, JCS typed-string numerics) | the actuation's parameters |
| `action.reversibility` (REVERSIBLE/COMPENSATABLE/IRREVERSIBLE/UNKNOWN) | consequence class; UNKNOWN is legal for opaque actions (FF2) |
| `principal {id, key_id, signature}` | *something* initiates every action; the adapter can always assert a principal |
| `authority.credential_scope {principal, permissions, ttl}` | the privilege the actuation needs |
| `policy_ref {version, digest}` | which enterprise policy to judge against (supplied by the enterprise, threaded by the adapter) |

`FACT`: these are exactly the fields ActionGate's predicates read (`gate.py:46–234`). Nothing here requires a specific reasoning/memory/planning internal.

### OPTIONAL — raise scrutiny or enable a layer; never lower a bar
| Field | Purpose |
|---|---|
| `state_binding {world_state_hash, observed_at, source}` | enables ACP operational safety + TOCTOU closure. Absent → ACP abstains (fail-closed), not bypass. **Strongly recommended** where a state exists. |
| `authority.delegation_chain[]` | privilege provenance for monotonicity checks |
| `evidence {risk_level, uncertainty, expected_effects, attestation, citations}` | the runtime's own opinion; scrutiny-only |
| `human_context {linked_ticket, approvals[]}` | SoD + action-bound approvals |
| `principal.on_behalf_of` | the human/service the agent acts for |

### RUNTIME-SPECIFIC — recorded as metadata, **excluded from identity** (del. 5)
| Field | Why it must not be identity-bearing |
|---|---|
| `provenance.runtime` | "langgraph" vs "openai-agents" — same action, must not fork the ID (FF1, K8) |
| `provenance.model` | producer model; control-inert |
| `provenance.objective` | free-text task label; "Tier-3 advisory only" (`FACT`) |
| `provenance.correlation_id` | session/trace correlation |

### CONTROL-PLANE-SPECIFIC — the CP produces/consumes these; **not runtime-supplied**
| Field | Owner |
|---|---|
| `action_digest` (DERIVED) | computed by the adapter/CP from the action bytes; a pure function of the actuation |
| `context_bundle` | Context Minimization input — **optional & pipeline-specific**, ActionGate-coupled (`FACT`: not universal); `null` for runtimes not in an ActionGate+ContextMin pipeline |
| world-state (for ACP) | pulled from a domain `WorldStateProvider`, **not** the proposal (`FACT`: `interfaces.py:24–36`) |
| policy bundle content | enterprise root-of-trust, out-of-band (`FACT`: `policy.py:5–6`); the proposal carries only `policy_ref` |
| verdict + token | ActionGate/ACP output, returned to the adapter |

---

## 2. The universality filter (why each rejected field was rejected)

**RECOMMENDATION — a field is admitted to MANDATORY only if it passes all three tests:**
1. **Actuation test:** is it a property of the tool/API call itself? (rejects prompt, reasoning, memory, plan)
2. **Weakest-runtime test:** can the *least* structured runtime supply it? (rejects anything needing a trace, a plan graph, a logit — moves them to OPTIONAL/evidence)
3. **Identity test:** does it change *what action is being authorized*? If not, it cannot be identity-bearing (moves runtime/model/objective to metadata)

`FACT`-anchored rejections: prompt/CoT/memory/planner/reflection fields fail test 1 (the Control Plane never reads them — grep-clean, `../ai_control_plane_v3/02`). `evidence.uncertainty` (Ugence's strength) fails test 2 as *mandatory* — a runtime without an uncertainty signal must still be able to propose — so it is OPTIONAL. `provenance.*` fails test 3 — it describes the producer, not the action.

---

## 3. The single non-universal wrinkle to state plainly

**FACT.** `context_bundle` is the one field that is *not* universal even as optional: it only yields a guarantee inside an ActionGate + Context-Minimization pipeline with ActionGate-shaped spans; on generic input it degenerates to a vacuous guarantee (`compressor.py:36–58`, `extractor.py:76–79`). **RECOMMENDATION:** keep it in the schema as CP-specific/optional, default `null`, and have the CP **fail loud** (refuse to certify) if a runtime supplies spans whose invariance signature is constant — so misuse cannot masquerade as a passing compression. Do not present it as universal context governance.

---

## 4. Minimal proposal (the irreducible core)

**RECOMMENDATION.** The smallest proposal any runtime must emit for the Control Plane to govern its action with zero dependence on runtime internals:

> `principal` + `action{tool, operation, targets, arguments, reversibility}` + `authority.credential_scope` + `policy_ref`

With this eight-field core, ActionGate renders a deterministic verdict; add `state_binding` and ACP renders an operational verdict. Everything else is enrichment or metadata. This is the contract every runtime in `02_RUNTIME_AUDIT_AND_ADAPTERS.md` is tested against.
