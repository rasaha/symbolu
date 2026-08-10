# Deliverable 9 — Open Governance

If CER became an open specification, how should it evolve? RFC process, working group, versioning, capability negotiation, extensions, profiles, compliance suite, certification. Modeled on how real standards are actually governed.

Labels: `RECOMMENDATION` · `INTERPRETATION` · `EXTERNAL KNOWLEDGE` (governance models of OAuth/IETF, CloudEvents/CNCF, OCI, MCP are general knowledge).

**Premise (from Deliverable 8, T4):** CER is not an open standard unless its governance is neutral. This deliverable designs that neutrality; Deliverable 12 decides whether to accept it.

---

## 1. Standards body & process — **RFC-style under a neutral foundation**

**RECOMMENDATION.** Two viable homes (`EXTERNAL KNOWLEDGE`):
- **CNCF** (like CloudEvents, OCI) — best fit: CER's structural template is CloudEvents, its identity model is OCI-like, its deployment surface is cloud/K8s-native, and CNCF's profile/extension governance is exactly what CER needs. **Primary recommendation.**
- **IETF** (like OAuth, HTTP) — if CER is framed as a wire protocol with formal RFCs; heavier process, stronger formal-spec culture. Secondary.

Process: **RFC-style versioned documents** (a core spec RFC + per-profile RFCs), a public proposal/review/last-call cycle, and a rule that **deviations are appended, never silently edited** — a discipline the repo already practices in its preregistration docs (`FACT`: "Deviations are appended post-hoc, never edited in place," ACP prereg).

## 2. Working group composition — **multi-vendor from day one**

**RECOMMENDATION.** A neutral technical working group requires ≥3 independent implementers before "standard" status (the CloudEvents/OCI bar). Seed it with: Ugence (reference control plane), ≥1 framework vendor (LangChain/CrewAI are plausible — Deliverable 7), ≥1 enterprise adopter (the demand-side driver), and ideally ≥1 cloud/domain implementer. **Ugence stewards but does not control** — a single-vendor WG is T4 (vendor lock) in disguise.

## 3. Versioning — **three independent semver axes** (from Deliverable 3.5)
- `cer_version` (envelope), `profile` version (domain semantics), `policy_ref` version (enterprise policy). Never conflated. A breaking envelope change is a new major `cer_version` and a new digest namespace (OCI media-type discipline).

## 4. Capability negotiation — **the interop backbone**

**RECOMMENDATION.** A control plane advertises a **capability descriptor**: `{cer_versions[], profiles[], operation_classes[], optional_layers[]}`. An adapter/runtime selects a mutually supported (cer_version, profile) before emitting. Unknown profile → `UNSUPPORTED_PROFILE` fail-closed (Deliverable 4.5). This is what prevents T14 (profile explosion) from becoming interop collapse: you never have to support every profile, only negotiate a common one — the TLS/HTTP-content-negotiation pattern.

## 5. Extensions & profiles — **the CloudEvents split**
- **Core (frozen, small):** envelope, identity rule, operation classes, authority model, verdict contract.
- **Profiles (registered, per-domain):** k8s, db, filesystem, robot, cloud, http/api, workflow. Each profile RFC defines its action schema, its verb→operation-class mapping, and its conformance vectors.
- **Extensions (optional attributes):** additive metadata/evidence that a control plane may ignore. Extensions **may only raise scrutiny**, never alter core semantics (the "optional never lowers a bar" rule).

## 6. Compliance suite — **already seeded in-repo**

**RECOMMENDATION.** A public compliance suite = the reference conformance corpus. `FACT`: the repo already ships `fixtures/conformance_vectors.json`, `conformance.py`, `test_conformance.py`, `test_canonicalization.py`, `test_hashing.py`. Donate and expand these into the standard's compliance suite:
- **Canonicalization/digest conformance:** action → expected `action_digest` (proves cross-implementation identity).
- **Adapter conformance:** the same actuation from N runtimes → identical digest (the `../execution_proposal_universality/05` experiment, as a CI gate).
- **Control-plane conformance:** CER + policy + state → expected verdict (proves interoperable enforcement).

This is what turns "the same action yields the same CER" from a claim into a *certifiable, testable* property — the difference between a spec and a standard.

## 7. Certification — **two levels, conformance-gated**
**RECOMMENDATION.**
- **CER-Emitter Certified** (a runtime/adapter): passes the canonicalization + adapter conformance suite for declared profiles.
- **CER-Governor Certified** (a control plane): passes the control-plane conformance suite; implements fail-closed on unknown profiles; enforces credential brokering (T7).
Certification is self-service against the public suite (like OCI conformance), not a Ugence gatekeeping function — otherwise it re-introduces T4.

## 8. Evolution guardrails
**RECOMMENDATION — three rules to keep the standard from rotting:**
1. **The core only shrinks or stays fixed; growth happens in profiles/extensions.** (Prevents the envelope from accreting vendor features.)
2. **No optional field may ever lower a bar** — enforced in the compliance suite, not just prose.
3. **Two independent interoperating implementations required to advance any feature to core** — the "running code + rough consensus" bar (IETF). Prevents paper features.

**INTERPRETATION.** The governance design is not exotic — it is deliberately the *proven* CloudEvents/OCI/OAuth playbook, because a novel governance process is itself an adoption risk. The one Ugence-specific asset is that the **compliance suite already exists in embryo** (`FACT`), which materially shortens the path from "spec" to "certifiable standard."
