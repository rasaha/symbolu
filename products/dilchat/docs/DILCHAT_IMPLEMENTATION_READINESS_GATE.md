# DilChat — Consolidated Implementation-Readiness Gate

**Audit:** Independent pre-implementation verification (all claims reproduced from primary evidence).
**Branch:** `claude/dilchat-backend-design-e0douc` · **HEAD at audit start:** `9bedde0a`.
**Scope:** documentation, schema, and draft rule-pack correctness only. **No production backend code
was written or authorized by this audit.**

This gate consolidates the six component audits. Each gate is **PASS**, **CONDITIONAL**, or
**BLOCKED**. Per the audit charter, the final verdict **cannot** be `READY_FOR_IMPLEMENTATION` while
any load-bearing astrology rule is `BLOCKED_DOMAIN_SOURCE` **or** while Swiss Ephemeris licensing is
unresolved — **both** conditions currently hold.

## Component-audit index

| Audit | Verdict |
|-------|---------|
| `DILCHAT_ARTIFACT_VALIDATION_REPORT.md` | Machine-readable validity **PASS** (2 Mermaid fixes applied) |
| `DILCHAT_GUNA_RULE_TRACEABILITY_AUDIT.md` | **RULE_PACK_BLOCKED** (8/8 kootas `BLOCKED_DOMAIN_SOURCE`) |
| `DILCHAT_ASTRONOMY_REPRODUCIBILITY_AUDIT.md` | **ASTRONOMY_REPRODUCIBLE_WITH_CONDITIONS** (12 PASS / 2 PARTIAL) |
| `DILCHAT_AUTHORIZATION_AND_LEAKAGE_AUDIT.md` | **AUTHZ_SOUND_WITH_FINDINGS** (AUTHZ-1..4) |
| `DILCHAT_SCORE_SEPARATION_AUDIT.md` | **SCORE_SEPARATION_ENFORCED_WITH_FINDINGS** (2 low) |
| `DILCHAT_LIVING_COMPATIBILITY_SAFETY_AUDIT.md` | **LIVING_COMPAT_NEEDS_SAFEGUARDS_BEFORE_PHASE_G** |

---

## The 13 gates

### 1. Repository integrity — **PASS**
24 files under `products/dilchat/` (10 docs + OpenAPI + 12 rule-pack + README + audits). No `.py`,
`.sql`, `Dockerfile`, `.tf`, migrations, ORM, or deploy manifests; no executable bits. Working tree
clean; branch 1 ahead / 0 behind default. Evidence: Artifact Validation Report §0.

### 2. Machine-readable artifact validity — **PASS**
OpenAPI 3.1 valid (34 paths, 28 schemas); all 11 JSON + 1 YAML parse with no duplicate keys;
rule-pack cross-reference 43/43 with maxima Σ = 36; **16/16 Mermaid blocks render** after two
semicolon fixes applied by this audit to `DILCHAT_BACKEND_ARCHITECTURE.md`. Evidence: Artifact
Validation Report §1–6.

### 3. Guna Milan domain correctness — **BLOCKED**
Structurally complete and internally consistent, but **every koota is `BLOCKED_DOMAIN_SOURCE`**:
`sources.json` has 9/9 citations `verified:false` and no confirmed authority. Highest-risk content:
the Vashya 5×5 reduction (should be the sourced 12×12 rashi-pair table) and the Yoni matrix's
missing friendly(3)/unfriendly(1) gradations (only {0,2,4} populated). Directionality of Varna/Tara/
Gana unconfirmed (OQ-2). **No user-facing Guna report may be generated until domain sign-off and a
frozen, non-draft pack version.** Evidence: Guna Traceability Audit.

### 4. Astronomy reproducibility — **CONDITIONAL**
Determinism, UTC/historical-tz, Julian Day, sidereal+Lahiri, `%360` normalization, rashi/nakshatra/
pada boundaries, version pinning, and ambiguous/nonexistent-time handling are specified (12 PASS).
Two PARTIALs: the blanket Moshier fallback and the undefined safety-epsilon. **Resolved by DEC-024**
(per-artifact-class fallback: binding classical reports fail-closed near boundaries; daily climate
may fall back with provenance) — condition: confirm the epsilon against Moshier's worst-case Moon
error in golden tests. Evidence: Astronomy Reproducibility Audit.

### 5. Swiss Ephemeris licensing — **BLOCKED**
AGPL-3.0 vs Astrodienst commercial license is **unresolved** for a hosted service (DEC-007, OQ-10).
This is a hard gate on public launch and a named blocker on the final verdict. The Moshier
public-domain fallback mitigates *availability* but **not** the licensing question for the Swiss
build. **Action:** obtain the professional license (or a written AGPL-compliance decision) before any
public-facing deployment. Evidence: Decision Log DEC-007; Astronomy Audit.

### 6. Authentication decision — **PASS**
Decided and sound (DEC-011, reconfirmed DEC-022): self-managed identity, Argon2id, ES256 short JWT +
rotating opaque refresh sessions, OIDC/OTP, vetted libraries only, no hand-rolled token crypto.
Social-provider ToS is a tracked legal-review item (does not block scaffolding). Evidence: Decision
Log DEC-022.

### 7. Geocoding decision — **PASS**
Decided and sound (DEC-017, reconfirmed DEC-023): self-hosted GeoNames authoritative; optional
external typeahead for UX only under an explicit no-store/no-send-true-birth-data privacy rule.

### 8. Three-scope authorization — **CONDITIONAL**
The model is strong: default-deny `authorize()`, existence non-disclosure (404-not-403 with timing-
oracle mitigation), consent-gated private→shared projection, RLS + app-layer defense-in-depth
(reconfirmed DEC-025). **Conditions before Phase D ships:**
- **AUTHZ-1 (GAP → DEC-027):** background jobs must re-validate couple membership/scope **at write
  time**, in-transaction, aborting+auditing post-unpair. Must be written into the spec.
- **AUTHZ-2 (PARTIAL → DEC-028):** SharedArtifacts must be immutable consented snapshots, not live
  private pointers. Now stated in the Decision Log; propagate to the data-model/consent spec text.
- **AUTHZ-4 (fixed by this audit):** `content_ref` encryption-tier wording harmonized in the data
  model (couple-DEK-encrypted immutable snapshot, SENSITIVE, consent-gated).
Evidence: Authorization & Leakage Audit.

### 9. Consent state machine — **PASS**
`requested → granted → revoked/expired` with SharedArtifact `created → access-frozen` on revoke/
unpair; ConsentEvent records granter, artifact_type, exact content/bounded-summary, purpose,
scope_from→scope_to, timestamp, expiry; honest revocation semantics (future access only). Evidence:
Privacy/Consent/Security spec §consent; Authorization Audit abuse-case 3.

### 10. AI context minimization — **PASS**
ContextBuilder assembles a minimized, scoped envelope; "never the other partner's private data";
AI consumes governed deterministic values and cannot recompute astrology; outputs schema-validated
with `prompt_pack_version` provenance. **AUTHZ-3 (legal-review):** confirm the AI provider's
zero-retention/no-train DPA terms before production (does not block scaffolding). Evidence: AI
Integration Spec §4–5; Authorization Audit abuse-cases 2 & 8.

### 11. Score-family separation — **PASS**
Enforced by separate tables, immutability triggers/RLS on `guna_report`/`astro_natal_chart`, and
mutation-rejection test PB-11 (INV-6/7); no co-mingled field exists (all "blended" mentions are
negations). Two **low-severity labeling findings** (ensure every user-facing surface labels family-2/
family-3 scores as DilChat-derived, not classical) — tracked, non-blocking. Evidence: Score
Separation Audit.

### 12. Test readiness — **PASS**
Comprehensive plan: unit (8 scorers + boundary/tz), integration (flagship flow + version-recalc),
authorization matrix, consent-leakage/canary, Hypothesis property invariants, golden charts (values
correctly marked PLACEHOLDER pending the oracle), boundary/historical-tz, pairing/unpairing, AI
schema-validation, performance/load, DR. Golden-value population is a Phase-A/B implementation task,
as expected. Evidence: Test & Validation Plan.

### 13. MVP scope readiness — **CONDITIONAL**
MVP cut line (Phases A–E → the flagship milestone + daily profiles) is coherent. **One discrepancy to
reconcile:** the PRD places the Living Compatibility *aggregate* in **Phase F**, while the Roadmap
places Living Compatibility in **Phase G**. Reconcile before those phases are planned. Living
Compatibility also **requires the safeguards** enumerated in the Living Compatibility Safety Audit
(SG-3/SG-4/SG-6 are ADDED-BY-THIS-AUDIT; SG-1/2/7/8 PARTIAL) written into the design **before Phase
F/G implementation**. Evidence: Living Compatibility Safety Audit §0; Roadmap vs PRD.

---

## Findings register (from all audits)

| ID | Source audit | Severity | Status | Resolution |
|----|--------------|----------|--------|------------|
| MERMAID-1/2 | Artifact validation | Low | **Fixed** | Semicolons → em-dash in 2 sequence diagrams |
| AUTHZ-4 | Authorization | Medium | **Fixed** | `content_ref` tier wording harmonized (DEC-028) |
| RULE-PACK (×8 koota) | Guna traceability | **High** | **BLOCKED_DOMAIN_SOURCE** | Domain sign-off + freeze non-draft pack |
| SWISS-LICENSE | Astronomy / DEC-007 | **High** | **BLOCKED** | Obtain Astrodienst license or AGPL decision |
| ASTRO-FALLBACK | Astronomy | Medium | **Corrected (DEC-024)** | Per-artifact-class fallback; confirm epsilon in golden tests |
| AUTHZ-1 | Authorization | High | **Control added (DEC-027)** | Job re-validates scope at write; spec it before Phase D |
| AUTHZ-2 | Authorization | Medium | **Control added (DEC-028)** | SharedArtifact immutable snapshot; propagate to spec text |
| AUTHZ-3 | Authorization / AI | Medium | **Open (legal review)** | Confirm AI provider zero-retention DPA before prod |
| SCORE-LABEL-1/2 | Score separation | Low | **Open (tracked)** | Ensure family-2/3 labeled DilChat-derived on every surface |
| LIVING-SG (3/4/6 new; 1/2/7/8 partial) | Living Compat safety | Medium | **Open (pre-Phase F/G)** | Write safeguards into design before implementation |
| MVP-PHASE | Readiness gate | Low | **Open** | Reconcile Living Compat Phase F vs G between PRD & Roadmap |

---

## Gate summary

| # | Gate | Verdict |
|---|------|---------|
| 1 | Repository integrity | **PASS** |
| 2 | Machine-readable artifact validity | **PASS** |
| 3 | Guna Milan domain correctness | **BLOCKED** |
| 4 | Astronomy reproducibility | **CONDITIONAL** |
| 5 | Swiss Ephemeris licensing | **BLOCKED** |
| 6 | Authentication decision | **PASS** |
| 7 | Geocoding decision | **PASS** |
| 8 | Three-scope authorization | **CONDITIONAL** |
| 9 | Consent state machine | **PASS** |
| 10 | AI context minimization | **PASS** |
| 11 | Score-family separation | **PASS** |
| 12 | Test readiness | **PASS** |
| 13 | MVP scope readiness | **CONDITIONAL** |

---

## FINAL VERDICT

# CONDITIONALLY_READY

The design is comprehensive, internally consistent, and machine-validated. It is **not**
`READY_FOR_IMPLEMENTATION` because two hard blockers stand: **Guna Milan domain correctness is
`RULE_PACK_BLOCKED`** (Gate 3) and **Swiss Ephemeris licensing is unresolved** (Gate 5). It is **not**
`NOT_READY_FOR_IMPLEMENTATION` because these are external approvals plus a small set of specified
spec corrections — not fundamental design defects — and the scope/consent architecture is sound.

### Exact next implementation phase allowed by this verdict

**Phase A, plus the non-blocked slices of Phase B — in a non-user-facing engineering context only.**
Specifically permitted:

- Calculation **proof-of-concept** and reference-chart validation against Swiss Ephemeris on an
  **AGPL/dev build** (internal, not deployed to users), including golden-vector generation and the
  Moshier worst-case-error measurement to fix the DEC-024 epsilon.
- Architecture/security scaffolding: repo skeleton, module boundaries, `identity`/`users`/
  `birth_profiles` data model, auth, and the **three-scope authorization boundary with its tests** —
  incorporating DEC-027 (job scope re-validation) and DEC-028 (shared snapshots) into the spec first.
- The classical Guna Milan **engine** may be built and unit-tested **against the draft rule pack in
  QA/test only**, with `guna_report` generation gated OFF for any user-facing path.

**Explicitly NOT permitted until the corresponding gate clears:**
- Any **user-facing Guna Milan report** — blocked until Gate 3 (domain sign-off + frozen non-draft
  pack).
- Any **public/production deployment of the Swiss Ephemeris build** — blocked until Gate 5
  (licensing).
- **Phase F/G Living Compatibility** implementation — blocked until its safeguards are specified and
  the Phase F/G discrepancy is reconciled (Gate 13).

### Go/no-go conditions to reach READY_FOR_IMPLEMENTATION (user-facing)

1. Gate 3 → domain expert confirms the authority, all `sources.json` `verified:true`, pack frozen
   non-draft, Vashya/Yoni tables completed from source, OQ-2 directionality confirmed.
2. Gate 5 → Swiss Ephemeris licensing resolved.
3. Gate 4 → DEC-024 epsilon confirmed empirically.
4. Gate 8 → DEC-027 / DEC-028 written into the authorization/consent/data-model spec text.
5. Gate 10 → AI provider zero-retention DPA confirmed (AUTHZ-3).
6. Gate 13 → Living Compatibility safeguards specified; Phase F/G reconciled.

**No production backend implementation was performed by this audit.**
