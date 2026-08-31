# Deliverable 8 — Threat Analysis (attempt to destroy CER)

Every architectural weakness I could find, each rated **FATAL** (kills the standard), **SERIOUS** (mitigable, must be designed for), or **MINOR**. The goal is destruction, not reassurance.

Labels: `FACT` · `INTERPRETATION` · `RECOMMENDATION` · `SPECULATION` · `EXTERNAL KNOWLEDGE`.

---

| # | Threat | Rating | Analysis & mitigation |
|---|---|---|---|
| **T1** | **Too abstract** — a universal action schema means nothing concrete; every real decision needs domain detail | **SERIOUS** | If CER standardized only abstract operations it would be useless. Mitigation: **envelope + domain profiles** (Deliverable 2/TF4) — the envelope is universal, the profile is concrete. Abstract core, concrete profiles. |
| **T2** | **Too domain-specific** — the in-repo reality is K8s-shaped (`KubernetesOperation`, `FACT`); the "universal" claim rides on one domain | **SERIOUS** | `FACT`: only cloud + robotics domains are actually implemented. Mitigation: the cross-domain reuse of the ACP core (robotics + K8s on one engine, `FACT`) is real evidence the pattern generalizes; but each new domain needs a profile + world-model. **Honest limit: universality is proven for 2 domains, designed for N.** |
| **T3** | **Identity instability** — same action yields different digests across runtimes | **SERIOUS (currently real)** | `FACT`: ActionGate hashes runtime/model/objective (`projection.py:44–46`), so cross-vendor digests *don't* collide today. Mitigation: the Deliverable-3 exclusion rule. Until fixed, cross-runtime identity is broken — this is the one concrete code-level defect. |
| **T4** | **Vendor lock** — "open standard" authored/owned/versioned by Ugence is a proprietary API in disguise | **FATAL if unaddressed** | The deepest threat to *openness*. Mitigation: donate to a neutral body (CNCF/IETF), multi-vendor working group, open conformance suite (Deliverable 9). Without this, CER cannot be an industry standard by definition. |
| **T5** | **Adapter complexity** — if every runtime needs a bespoke code adapter, the ecosystem never forms | **SERIOUS** | Mitigation: declarative Tier-1 adapters + one MCP adapter covering most runtimes (Deliverable 5). Complexity is bounded to the opaque/managed minority. |
| **T6** | **Semantic ambiguity** — `DELETE`/`EXECUTE` mean different things across domains; a control plane could mis-authorize | **SERIOUS** | Mitigation: operation *classes* are universal (consequence type), verbs are profiled; a control plane **fails closed on unknown profiles** (`UNSUPPORTED_PROFILE`), never guesses (Deliverable 4.5). |
| **T7** | **Execution leakage** — a runtime that keeps a durable credential can act *around* the CER; the standard governs a request the runtime can bypass | **SERIOUS** | `FACT`: `ACTIONGATE_VC_BRIEF.md:39–41` — an observed agent holding a durable credential acts despite the observer. Mitigation: mandatory **credential brokering** in the adapter (single-use, per-action). A translate-only adapter is non-conformant. **If credential brokering isn't enforced, CER is advisory, not governing.** |
| **T8** | **Policy coupling** — if CER embeds policy, it couples to one governor and can't be universal | **FATAL if violated; avoided by design** | Mitigation: CER carries only `policy_ref`, never policy (Deliverable 2 exclusions). Policy stays with the enterprise. Already correct in the design. |
| **T9** | **World-model coupling** — if CER carried live state, it couples to one domain and one observer | **FATAL if violated; avoided by design** | Mitigation: CER carries only a `state_binding` hash; the control plane pulls live state from a domain `WorldStateProvider` (`FACT`: `interfaces.py:24–36`). Already correct. |
| **T10** | **Canonicity impossible** — you cannot deterministically canonicalize arbitrary actions across implementations | **SERIOUS, partly refuted** | `FACT`: a JCS profile + domain-separated hashing + conformance vectors *already exist and pass* in-repo (`jcs.py`, `conformance.py`, `fixtures/conformance_vectors.json`). Canonicity is achieved *within a profile*. The residual hard case: **free-form actions (code/shell)** can't be canonicalized pre-execution (FF2) — intercept lower. So canonicity is *possible for structured actions, hard for opaque ones*. |
| **T11** | **Opaque-action bypass** — free-form code/shell actions are only canonicalizable at the syscall layer, which most adapters can't reach | **SERIOUS** | Mitigation: programmable Tier-2 adapters + `SIMULATE_AND_RETRY`; or restrict high-risk runtimes to structured tools. Real cost for AutoGen/Bash. |
| **T12** | **Operational-identity divergence** — the same action against differently-observed state gets different operational verdicts | **MINOR–SERIOUS** | `FACT` (FF4): operational identity is the loosest equivalence. Mitigation: standardize the domain `WorldStateProvider`; treat state as domain-authoritative, not runtime-supplied. |
| **T13** | **Standard capture / fragmentation** — a hyperscaler forks CER or MCP absorbs governance, splitting the ecosystem | **SERIOUS (strategic)** | `SPECULATION`. Mitigation: MCP-complementary posture, neutral governance, speed (Deliverables 6, 7, 9). Can't be designed away — only out-executed. |
| **T14** | **Version/profile explosion** — every domain and vendor spawns profiles; interop collapses under N×M combinations | **SERIOUS** | Mitigation: a small set of *blessed* core profiles + capability negotiation + a compliance suite gating profile registration (Deliverable 9). CloudEvents manages this; CER must too. |
| **T15** | **Latency** — per-action canonicalize+authorize+safety round-trips break interactive/high-frequency runtimes | **SERIOUS** | `EXTERNAL KNOWLEDGE`. Mitigation: risk-tiered fast path (low-consequence reads take a cheap path); from `../execution_proposal_engine/` F2. A standard that's too slow won't be emitted. |
| **T16** | **Trust in the digest ≠ trust in the actuation** — the CER digest binds the *described* action, but the runtime could execute a *different* action than it described | **SERIOUS** | The description-vs-execution gap. Mitigation: credential brokering binds the *granted credential* to the exact action (`FACT`), and commit-time revalidation checks state; the agent can only actuate what it was granted for. Closes most of the gap; a fully compromised adapter remains a trust root. |

---

## Summary — where CER could actually die

**INTERPRETATION.**
- **Two FATAL-if-violated threats are already avoided by design:** policy coupling (T8) and world-model coupling (T9). The spec is correct here.
- **One FATAL threat is a governance decision, not a technical one:** vendor lock (T4) — CER is *not* an open standard unless Ugence cedes control (Deliverable 9/12).
- **The most under-appreciated technical threats are T7 (execution leakage) and T16 (description≠execution):** if credential brokering isn't mandatory and enforced, CER governs a *request the runtime can bypass* — reducing a "governance standard" to an "advisory format." **This is the threat most likely to be glossed over and most damaging if it is.**
- **The rest are SERIOUS-but-mitigable engineering/process costs** (adapters, canonicity of opaque actions, profiles, latency, identity fix).

**RECOMMENDATION.** The standard is destroyable in exactly two ways: (1) by not ceding governance (T4 → it's not open), and (2) by not mandating credential brokering (T7/T16 → it's not governing). Both must be non-negotiable requirements in the spec, not optional profiles. Everything else is survivable.
