# DilChat — Documentation Index

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com

This index groups the DilChat design, audit, and requirements documents by track.
The canonical reference for names, versions, and decisions is
[`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md); on any conflict, the Decision
Log wins.

> **Product status (verified):** Mobile Phase 1 **merged** (account, birth profile,
> invitation, pairing, consent, paired status, unpairing). Mobile Phase 2 not
> started. Secure partner chat, AI Assist, and user-facing Guna scores **do not
> exist**. Classical Guna authority remains **BLOCKED**; the classical rule pack is
> **non-executable** and fail-closed.

## AI Assist (V1 direction — DEC-048, requirements only)

| Doc | Purpose |
|-----|---------|
| [DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md](DILCHAT_AI_ASSIST_PRODUCT_REQUIREMENTS.md) | Founder decision, four-component model, posture taxonomy, topic domains, output categories, example behavior, disclosure. |
| [DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md](DILCHAT_RELATIONSHIP_SIGNAL_FUSION_REQUIREMENTS.md) | Signal hierarchy, 60 %→30 % structural-prior weighting, qualified evidence, recommendation precedence. |
| [DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md](DILCHAT_AI_ASSIST_CHAT_OVERLAY_SPEC.md) | Approved chat-overlay UI template and content structure. |
| [DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md](DILCHAT_AI_ASSIST_PRIVACY_PROVENANCE_AND_SAFETY.md) | Data scope, consent, Moon safety language, provenance, auditability. |
| [DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md](DILCHAT_AI_ASSIST_DEVELOPMENT_ROADMAP.md) | Phase 2 → 3 → 4A–4D sequencing and gating. |
| [DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md](DILCHAT_AI_ASSIST_ACCEPTANCE_CRITERIA.md) | `AIA-*` requirements, 17 acceptance criteria, 17 open questions. |
| [DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md](DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md) | The founder-approved V1 direction (FD-AIA-1…10), mapped to DEC-048. |
| [ai_assist_requirements.json](ai_assist_requirements.json) | Machine-readable mirror of the requirements/acceptance/open-questions catalog. |

## Product & architecture

| Doc | Purpose |
|-----|---------|
| [DILCHAT_DECISION_LOG.md](DILCHAT_DECISION_LOG.md) | **Canonical** architecture decision log (DEC-###). |
| [DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md](DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md) | Backend product requirements. |
| [DILCHAT_BACKEND_ARCHITECTURE.md](DILCHAT_BACKEND_ARCHITECTURE.md) | Backend architecture. |
| [DILCHAT_DATA_MODEL.md](DILCHAT_DATA_MODEL.md) | Data model. |
| [DILCHAT_API_SPEC.md](DILCHAT_API_SPEC.md) | API specification. |
| [DILCHAT_IMPLEMENTATION_ROADMAP.md](DILCHAT_IMPLEMENTATION_ROADMAP.md) | Phased delivery plan (Phases A–G). |
| [DILCHAT_IMPLEMENTATION_READINESS_GATE.md](DILCHAT_IMPLEMENTATION_READINESS_GATE.md) | Implementation readiness gate. |
| [DILCHAT_AI_INTEGRATION_SPEC.md](DILCHAT_AI_INTEGRATION_SPEC.md) | AI integration spec (provider ports, deterministic-astrology boundary). |

## Mobile

| Doc | Purpose |
|-----|---------|
| [DILCHAT_MOBILE_ARCHITECTURE.md](DILCHAT_MOBILE_ARCHITECTURE.md) | Mobile architecture + post–Phase-1 phase sequence. |
| [DILCHAT_MOBILE_API_CONTRACT_MAP.md](DILCHAT_MOBILE_API_CONTRACT_MAP.md) | Screen → backend operation contract map. |
| [DILCHAT_MOBILE_SECURITY_AND_PRIVACY.md](DILCHAT_MOBILE_SECURITY_AND_PRIVACY.md) | Mobile security & privacy. |
| [DILCHAT_MOBILE_PHASE1_IMPLEMENTATION_REPORT.md](DILCHAT_MOBILE_PHASE1_IMPLEMENTATION_REPORT.md) | Phase 1 implementation report. |
| [DILCHAT_MOBILE_PHASE1_MERGE_READINESS_REPORT.md](DILCHAT_MOBILE_PHASE1_MERGE_READINESS_REPORT.md) | Phase 1 merge-readiness report. |
| [DILCHAT_MOBILE_PHASE2_REQUIREMENTS.md](DILCHAT_MOBILE_PHASE2_REQUIREMENTS.md) | Phase 2 (device/deep-link/lifecycle/privacy/native) requirements + exclusions. |
| [DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md](DILCHAT_MOBILE_PHASE2_IMPLEMENTATION_REPORT.md) | Phase 2 implementation report + exact verdict. |
| [DILCHAT_MOBILE_PHASE2_BUILD_AND_TOOLCHAIN_REPORT.md](DILCHAT_MOBILE_PHASE2_BUILD_AND_TOOLCHAIN_REPORT.md) | Phase 2 Expo toolchain fix, Metro export, native config/manifest. |
| [DILCHAT_MOBILE_PHASE2_PRIVACY_AND_LIFECYCLE_TESTS.md](DILCHAT_MOBILE_PHASE2_PRIVACY_AND_LIFECYCLE_TESTS.md) | Phase 2 privacy/lifecycle/deep-link/offline test matrix. |
| [DILCHAT_MOBILE_PHASE2_DEVICE_TEST_PLAN.md](DILCHAT_MOBILE_PHASE2_DEVICE_TEST_PLAN.md) | Phase 2 closed-pilot device harness (synthetic; execution pending). |
| [DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md](DILCHAT_MOBILE_PHASE2_KNOWN_LIMITATIONS.md) | Phase 2 deferrals + traced security-advisory dispositions. |

## Guna authority (classical track — BLOCKED)

| Doc | Purpose |
|-----|---------|
| [DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md](DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md) | Consolidated authority gate (four verdicts; Guna BLOCKED). |
| [DILCHAT_GUNA_FOUNDER_DECISIONS.md](DILCHAT_GUNA_FOUNDER_DECISIONS.md) | Classical Guna founder decisions (FD-1…FD-10, **OPEN**). |
| [DILCHAT_GUNA_V1_TRADITION_SCOPE.md](DILCHAT_GUNA_V1_TRADITION_SCOPE.md) | v1 tradition scope (draft). |
| [DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md](DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md) | Rule adjudication ledger + conflict dossiers. |
| [DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md](DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md) | Source acquisition status (`SOURCE_MATERIAL_REQUIRED`). |

> The AI Assist track (above) is **separate** from the classical Guna authority
> track and does **not** change its blocked status. See
> [DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md](DILCHAT_AI_ASSIST_FOUNDER_DECISIONS.md)
> ("Two tracks").

## Privacy, security & audits

| Doc | Purpose |
|-----|---------|
| [DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md](DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md) | Privacy, consent & security design. |
| [DILCHAT_AUTHORIZATION_AND_LEAKAGE_AUDIT.md](DILCHAT_AUTHORIZATION_AND_LEAKAGE_AUDIT.md) | Authorization & leakage audit. |
| [DILCHAT_SECURITY_DEFINER_RLS_AUDIT.md](DILCHAT_SECURITY_DEFINER_RLS_AUDIT.md) | RLS / SECURITY DEFINER audit. |
| [DILCHAT_SCORE_SEPARATION_AUDIT.md](DILCHAT_SCORE_SEPARATION_AUDIT.md) | Score-separation audit. |
| [DILCHAT_TEST_AND_VALIDATION_PLAN.md](DILCHAT_TEST_AND_VALIDATION_PLAN.md) | Test & validation plan. |

*This index is a convenience map; it is not exhaustive of every file under
`docs/`. When adding a document, add its row to the appropriate section.*
