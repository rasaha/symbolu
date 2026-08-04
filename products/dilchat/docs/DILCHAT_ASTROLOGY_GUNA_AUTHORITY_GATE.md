# DilChat — Astrology & Guna Authority Gate (consolidated)

Consolidated readiness across astronomy validation, interval correctness, database
security, and classical-rule authority. This revision follows the four **separate**
verdicts required by the acquisition/adjudication phase. A verdict is issued only
when the evidence supports it; classical-authority verdicts stay **blocked** while
any edition is unfrozen, any included rule is `SOURCE_CONFLICT`/`BLOCKED`/`PENDING`,
manual verification is incomplete, or domain review is pending.

> **This phase advanced source *identification*, not source *freeze*.** Real,
> citable candidate editions were found (ISBNs, catalogue/archive identifiers), but
> none was acquired, opened, or reviewer-verified (Internet Archive content was
> blocked HTTP 403 in this environment). Nothing is frozen; no conflict is resolved;
> no reviewer has signed off. The rule pack therefore remains **blocked** — honestly.

---

## Final verdicts

| Axis | Verdict |
|------|---------|
| **Technical validation** | **`VALIDATION_INFRASTRUCTURE_COMPLETE`** |
| **Astronomy** | **`ASTRONOMY_VALIDATION_PASS_WITH_BOUNDARY_CONDITIONS`** |
| **Guna authority** | **`GUNA_AUTHORITY_VALIDATION_BLOCKED`** |
| **Rule pack** | **`RULE_PACK_BLOCKED`** |

### Why Guna authority is BLOCKED (any one suffices; all are true)
- No normative or engineering **edition is frozen** (all `EDITION_IDENTIFIED_NOT_ACQUIRED`; overall `PENDING_ACQUISITION`).
- **4 source-conflict topics** remain unresolved (Vashya form; Yoni gradations; Gana Deva×Rakshasa; Bhakoot friendly-lord relief) across 6 traceability rule-entries.
- **0 rules** are `DOMAIN_APPROVED`; every executable candidate lacks page/verse traceability.
- **Manual verification incomplete** — 24 cases, all `PENDING_DOMAIN_REVIEW`/`SOURCE_CONFLICT`, none `MANUAL_VERIFIED`.
- **Domain review pending** — no qualified reviewer sign-off (not fabricated).

### Why the rule pack is BLOCKED
`RULE_PACK_READY` / `RULE_PACK_READY_WITH_EXPLICIT_EXCLUSIONS` require all included
rules approved, all unresolved rules **excluded rather than approximated**, exclusions
product-visible and fail-closed, and reviewer acceptance of those exclusions. None of
these conditions is met. The machine-readable invariant agrees: `pack_control.json`
records `derived_executable=false` with 6 blockers, and the validator enforces it.

---

## Gate table

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | Repository integrity | **PASS** | forward-only migrations; no out-of-scope changes; no secrets/scans/db files committed |
| 2 | Phase A/B quality gates | **PASS** | ruff clean; mypy clean; full suite green |
| 3 | Independent astronomy | **PASS** | Astropy/ERFA (independent of Swiss), 16 cases, ≤ 19.8″; `test_independent_astro.py` |
| 4 | Interval boundary completeness | **CONDITIONAL** | `PROVEN_WITH_LIMITATIONS`; crossing-time refinement not implemented |
| 5 | Exact boundary arithmetic | **PASS** | half-open rational Decimal (DEC-033) |
| 6 | Provider provenance / Swiss dev-boundary | **PASS** | policy matrix (DEC-029) |
| 7 | Swiss production licensing | **BLOCKED** | AGPL vs Astrodienst license unresolved (external; DEC-007/OQ-10) |
| 8 | RLS + SECURITY DEFINER | **PASS** | `SECURITY_DEFINER_RLS_HARDENED`; `test_rls.py`, `test_security_definer.py` |
| 9 | Source edition **identification** | **PASS** | real candidate editions + ISBNs/catalogue IDs recorded (`GUNA_SOURCE_MANIFEST.json` v2) |
| 10 | Source edition **freeze** | **BLOCKED** | none acquired/opened/verified; overall `PENDING_ACQUISITION` |
| 11 | v1 tradition scope defined | **PASS (draft)** | `DILCHAT_GUNA_V1_TRADITION_SCOPE.md`; founder confirmation PENDING (FD-1) |
| 12 | Rule traceability ledger | **PASS (draft)** | 23 rules mapped; `DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md`; page/verse still null |
| 13 | Varna authority | **BLOCKED** | PENDING_DOMAIN_REVIEW; no frozen edition |
| 14 | Vashya authority | **BLOCKED** | SOURCE_CONFLICT (12×12 vs 5×5) + BLOCKED gradations |
| 15 | Tara authority | **BLOCKED** | directional counting convention PENDING (OQ-2) |
| 16 | Yoni authority | **BLOCKED** | friendly(3)/unfriendly(1) matrix BLOCKED_DOMAIN_SOURCE |
| 17 | Graha Maitri authority | **BLOCKED** | Naisargika-only PENDING_DOMAIN_REVIEW; BPHS edition unfrozen |
| 18 | Gana authority | **BLOCKED** | Deva×Rakshasa 0-vs-1 SOURCE_CONFLICT |
| 19 | Bhakoot authority | **BLOCKED** | friendly-lords cancel-vs-relief SOURCE_CONFLICT |
| 20 | Nadi authority | **BLOCKED** | classification + exceptions PENDING; DEC-021 constraint present |
| 21 | Parihara precedence | **PASS (model) / BLOCKED (rules)** | ordered deterministic (DEC-041); all 6 rules disabled/PENDING |
| 22 | Machine-readable pack controls | **PASS** | `pack_control.json` + `validate_rule_pack.py` + `test_rule_pack_controls.py` (12 tests) |
| 23 | Manual-case readiness | **CONDITIONAL** | 24 cases cover all 22 categories; expected values unverified |
| 24 | Domain reviewer approval | **BLOCKED** | `DOMAIN_REVIEW_PENDING`; no reviewer sign-off (never fabricated) |
| 25 | User-facing Guna readiness | **BLOCKED** | gated by 7, 10, 13–20, 24 |

## Per-Koota authority status

| Koota | Status | Blocking item |
|-------|--------|---------------|
| Varna | BLOCKED (review pending) | edition freeze + review |
| Vashya | SOURCE_CONFLICT + BLOCKED | 12×12 vs 5×5; off-diagonal gradations |
| Tara | BLOCKED (review pending) | directional counting convention (OQ-2) |
| Yoni | BLOCKED_DOMAIN_SOURCE | friendly/unfriendly matrix cells |
| Graha Maitri | BLOCKED (review pending) | Naisargika-only confirmation; BPHS edition |
| Gana | SOURCE_CONFLICT | Deva×Rakshasa = 0 vs 1 |
| Bhakoot | SOURCE_CONFLICT | friendly-lords: cancel vs interpretive relief |
| Nadi | BLOCKED (review pending) | classification + exceptions (DEC-021 medical-safety constraint present) |

**Four unresolved source conflicts** (both candidates recorded, `resolution: PENDING`):
Vashya table form; Yoni gradations; Gana Deva×Rakshasa; Bhakoot friendly-lord relief.

## What this phase DID advance
- **Source identification** (Gate 9): real, citable candidate editions with ISBNs and catalogue/archive identifiers for all four sources — a genuine step beyond the prior "no edition identified" state.
- **v1 tradition scope** (Gate 11) and **adjudication ledger** (Gate 12) drafted.
- **Machine-readable pack controls** (Gate 22): checksums, a derived executable invariant, and a validator with fail-closed tamper tests.
- **Manual coverage** (Gate 23): all 22 required categories represented (unverified).
- **Founder decisions** surfaced (FD-1…FD-10) without deciding them.

## What this phase did NOT do (honest exclusions)
- Did **not** freeze any edition, resolve any conflict, approve any rule, verify any manual case, or obtain any reviewer sign-off.
- Did **not** implement any Guna scoring engine, koota calculator, Guna API, compatibility report, or user-facing output.

---

## Exact next phase permitted

After the rule pack reaches `RULE_PACK_READY` or
`RULE_PACK_READY_WITH_EXPLICIT_EXCLUSIONS` — i.e. after the source editions are
**frozen**, the **four conflicts** are resolved, the manual cases are
**reviewer-verified**, and a **qualified Jyotisha/Sanskrit reviewer** signs off —
implement the internal deterministic classical Guna Milan engine and shared
compatibility report using **only** domain-approved rules. **Do not** begin that
engine now.

---

## Guna Source Acquisition & Qualified Domain Adjudication phase — update

**Repository integration.** The `dilchat-guna-domain-authority` branch (previously
stranded on the older baseline `36d2a340`, zero unique commits) was recreated by
fast-forward from the current default tip `e852812b`, so authority work starts from
the latest baseline (DilChat CI merged and green). No unique work was lost.

**Baseline gate (refreshed branch):** ruff clean · mypy clean (53 files) · **197
passed / 0 skipped** · migration up/down/up clean, single head `b2c3d4e5f6a7` · RLS +
SECURITY DEFINER · independent astronomy · rule-pack validator PASS · no-Guna guard ·
`RULE_PACK_BLOCKED` / `executable:false` / provider-licensing guards — all green.

**Source-material gate: `SOURCE_MATERIAL_REQUIRED`.** No source pages are lawfully
available in this environment (bibliographic metadata only; Internet Archive content
403-blocked). Per the phase rules, **no rule was adjudicated**; no source was frozen;
no reviewer was fabricated. A sanitized local-source intake tool
(`scripts/source_intake.py`, tested) is provided for lawful acquisition, and an exact
acquisition checklist is recorded in `DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md`.

### Four verdicts (unchanged this phase)

| Axis | Verdict |
|------|---------|
| Technical validation | **`VALIDATION_INFRASTRUCTURE_COMPLETE`** |
| Astronomy | **`ASTRONOMY_VALIDATION_PASS_WITH_BOUNDARY_CONDITIONS`** |
| Guna authority | **`GUNA_AUTHORITY_VALIDATION_BLOCKED`** |
| Rule pack | **`RULE_PACK_BLOCKED`** |

Guna authority and the rule pack remain **BLOCKED** because source pages are
unavailable, no exact edition is frozen, the four source conflicts (Vashya, Yoni,
Gana, Bhakoot) are unresolved, page/verse traceability is incomplete, manual cases
are pending, and qualified domain-reviewer sign-off is absent.

**Exact next action:** *Obtain the frozen source editions and qualified reviewer
input. Do not implement the Guna engine.*
