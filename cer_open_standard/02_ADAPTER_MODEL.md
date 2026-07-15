# Deliverable 5 — The Universal Adapter Contract

`Runtime → Adapter → CER`. Should adapters be declarative or programmable? What is the smallest possible adapter?

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `EXTERNAL KNOWLEDGE`. Builds on the per-runtime adapter analysis in `../execution_proposal_universality/02_RUNTIME_AUDIT_AND_ADAPTERS.md`.

---

## 1. The adapter contract (what every adapter must implement)

**RECOMMENDATION.** An adapter is a component that implements two functions at a runtime's **actuation boundary**:

```
   toCER(native_action, context) -> CER            // intercept + normalize + emit
   fromVerdict(verdict, token)   -> native_control // map decision back to the runtime
```

- `toCER` intercepts the runtime *at the point of a concrete tool/API call* (not the plan), normalizes it to the CER envelope + domain-profile action, asserts the principal and credential_scope, attaches optional state_binding/evidence, and **excludes provenance from the digest**.
- `fromVerdict` translates the control plane's response — `ALLOW`+token → execute; `DENY`/`HOLD`/`ESCALATE`/`SIMULATE_AND_RETRY`/`REQUEST_MORE_EVIDENCE` → the runtime's native pause/deny/HITL primitive.

**FACT-anchored constraints (from prior milestones):**
- The adapter must intercept at the **actuation boundary** — the actual call — because plan-level actions can be opaque (free-form code/shell, FF2). This is the one non-negotiable placement rule.
- The adapter **must broker credentials**, not merely observe — a translate-only adapter that leaves the runtime holding durable credentials is monitoring, not enforcement (`FACT`: `ACTIONGATE_VC_BRIEF.md:39–41`).

---

## 2. Declarative or programmable? — **Both, in two tiers**

**RECOMMENDATION — a declarative core with a programmable escape hatch:**

### Tier 1 — Declarative mapping (covers structured runtimes)
For runtimes that emit **structured tool calls** (OpenAI Agents, LangGraph tool nodes, Semantic Kernel functions, MCP servers, Google ADK, most of Claude Code's tools), the adapter is a **declarative map**:
```yaml
# adapter.cer.yaml  (illustrative)
profile: cer.k8s/1.0
intercept: mcp.tools/call            # or: openai.tool_lifecycle, sk.function_filter, adk.before_tool_callback
map:
  tool:      { namespace: "$server", name: "$tool_name" }
  operation: { from: "$tool_name", via: operation_table }   # scale->WRITE, delete->DELETE
  targets:   { from: "$args.target" }
  arguments: "$args"
  reversibility: { from: "$tool_name", via: reversibility_table }
principal:   { from: "$session.agent_id" }
exclude_from_identity: [runtime, model, objective, correlation_id]
```
Declarative adapters are **auditable, portable, and safe** — no arbitrary code runs in the governance path. This should be the default and cover the majority of runtimes (`EXTERNAL KNOWLEDGE`: most frameworks expose a structured tool/function boundary).

### Tier 2 — Programmable adapter (for opaque/managed runtimes)
For runtimes whose actions are **opaque** (AutoGen arbitrary code, Claude Code `Bash`) or **managed** (Bedrock), a declarative map is insufficient — the adapter needs code to parse a shell string, shim a syscall, or hook a return-control callback. These use a **programmable adapter** implementing `toCER`/`fromVerdict` in a sandboxed extension.

**INTERPRETATION.** The declarative/programmable split maps exactly onto the falsification finding: structured+pre-commit runtimes → declarative (trivial); opaque/managed runtimes → programmable (the hard cases, FF2/FF3). The standard should *specify the declarative format* (so 80% of adapters are config, not code) and *specify the programmable interface* (so the hard 20% are possible).

---

## 3. The smallest possible adapter

**RECOMMENDATION.** For an MCP-speaking runtime, the minimal adapter is a **single interception hook that forwards the MCP `tools/call` into `toCER` with a declarative profile map** — effectively a few dozen lines of config plus the shared CER library. `FACT`: the repo already prototypes an MCP→ActionGate adapter (`action_gateway_mcp`). Because MCP is the convergence point (OpenAI, ADK, Claude Code, Semantic Kernel increasingly speak it — `EXTERNAL KNOWLEDGE`), **one declarative MCP adapter is the smallest adapter that covers the most runtimes** — the 80/20 of the whole adapter ecosystem.

The theoretical floor: an adapter that maps `{tool_name, args}` → `{tool, operation, targets, arguments}`, asserts a principal, and forwards. Everything else (state_binding, evidence, delegation) is optional. So the smallest conforming adapter is: **one intercept point + one operation table + a principal assertion.**

---

## 4. Adapter conformance (ties to the compliance suite, Deliverable 9)

**RECOMMENDATION.** An adapter is *conformant* iff, for the shared conformance corpus, it produces CERs whose `action_digest` matches the reference digest for the same actuation (provenance excluded). This is directly testable with the existing `fixtures/conformance_vectors.json` mechanism (`FACT`). Conformance is what makes "the same action from any runtime yields the same CER" a *certifiable* property rather than a hope — and it is the artifact the cross-runtime experiment (`../execution_proposal_universality/05`) would exercise.

---

## 5. What the adapter must never do (the discipline that keeps CER neutral)

**RECOMMENDATION.**
- Never inject reasoning/prompt/memory/model internals into the CER (Deliverable 2 exclusions).
- Never make the authorization decision — it translates and forwards; the control plane decides.
- Never hold or reuse a token across actions (single-use, §3.4).
- Never guess semantics for an unknown domain — emit the profile id and let the control plane fail-closed on `UNSUPPORTED_PROFILE`.

**INTERPRETATION.** The adapter is the *only* place runtime-specificity is allowed to exist, and even there it is confined to *translation*. This is what makes the same standard serve every runtime: all the variance lives in a thin, auditable, mostly-declarative translation layer, and none of it reaches the CER or the control plane.
