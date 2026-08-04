# DilChat — Astrology & Guna Authority Gate (consolidated)

Consolidated readiness across astronomy validation, interval correctness, database
security, and classical-rule authority. Each gate is **PASS**, **CONDITIONAL**,
**BLOCKED**, or **N/A**. The final verdicts follow the task's hard rules — in
particular, `RULE_PACK_READY` is **not** issued while any executable rule is
`BLOCKED_DOMAIN_SOURCE`, a source conflict is unresolved, or domain review is
pending.

## Gate table

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | Repository integrity | **PASS** | HEAD `d6aaf7f9`; forward-only migrations; no out-of-scope changes; no secrets/scans committed |
| 2 | Existing Phase A/B quality gates | **PASS** | ruff clean; mypy clean; full suite green (see §Tests) |
| 3 | Independent astronomical correctness | **PASS** | Astropy/ERFA (independent of Swiss), 16 cases, ≤ 19.8″; `test_independent_astro.py` |
| 4 | Timezone correctness | **PASS** | historical IANA tz; 23/25-h days; `test_birthinterval.py`, independent IND-06/07/08 |
| 5 | Exact boundary arithmetic | **PASS** | half-open rational Decimal (DEC-033); `test_derivation.py` |
| 6 | Interval boundary completeness | **CONDITIONAL** | `INTERVAL_BOUNDARY_COMPLETENESS_PROVEN_WITH_LIMITATIONS`; crossing-time refinement not implemented |
| 7 | Provider provenance | **PASS** | provenance tuple + `provider_kind`/`synthetic_calculation`; audit whitelist |
| 8 | Swiss development-use boundary | **PASS** | policy matrix (DEC-029); `test_licensing_guard.py` |
| 9 | Swiss production licensing | **BLOCKED** | AGPL vs Astrodienst license unresolved (external; DEC-007/OQ-10) |
| 10 | RLS policies | **PASS** | ENABLE+FORCE on 10 tables; non-owner tests `test_rls.py` |
| 11 | SECURITY DEFINER hardening | **PASS** | `SECURITY_DEFINER_RLS_HARDENED`; `test_security_definer.py` |
| 12 | Source-edition freeze | **BLOCKED** | `GUNA_SOURCE_MANIFEST.json` overall `PENDING_ACQUISITION`; no edition acquired |
| 13 | Varna authority | **BLOCKED** | traceability PENDING_DOMAIN_REVIEW; no frozen edition |
| 14 | Vashya authority | **BLOCKED** | SOURCE_CONFLICT (12×12 vs 5×5) + BLOCKED_DOMAIN_SOURCE gradations |
| 15 | Tara authority | **BLOCKED** | directional-counting convention PENDING (OQ-2) |
| 16 | Yoni authority | **BLOCKED** | friendly(3)/unfriendly(1) matrix BLOCKED_DOMAIN_SOURCE |
| 17 | Graha Maitri authority | **BLOCKED** | Naisargika-only decision PENDING_DOMAIN_REVIEW; BPHS edition pending |
| 18 | Gana authority | **BLOCKED** | Deva×Rakshasa 0-vs-1 SOURCE_CONFLICT |
| 19 | Bhakoot authority | **BLOCKED** | friendly-lords cancel-vs-relief SOURCE_CONFLICT |
| 20 | Nadi authority | **BLOCKED** | classification + same-rashi/same-lord exceptions PENDING; DEC-021 constraint present |
| 21 | Parihara precedence | **CONDITIONAL** | ordered deterministic model defined (DEC-041); all 6 rules disabled/PENDING |
| 22 | Regional-rule isolation | **CONDITIONAL** | North/South differences recorded per rule; resolution PENDING |
| 23 | Manual-case readiness | **CONDITIONAL** | 19 `DRAFT_MANUAL_VALIDATION_CASE` prepared; expected values unverified |
| 24 | Domain reviewer approval | **BLOCKED** | `DOMAIN_REVIEW_PENDING`; no reviewer sign-off (never fabricated) |
| 25 | User-facing Guna readiness | **BLOCKED** | gated by 9, 12–20, 24 |

## Per-Koota authority status

| Koota | Status | Blocking item |
|-------|--------|---------------|
| Varna | BLOCKED_DOMAIN_SOURCE (review pending) | edition freeze + review |
| Vashya | SOURCE_CONFLICT + BLOCKED | 12×12 vs 5×5; off-diagonal gradations |
| Tara | BLOCKED (review pending) | directional counting convention (OQ-2) |
| Yoni | BLOCKED_DOMAIN_SOURCE | friendly/unfriendly matrix cells |
| Graha Maitri | BLOCKED (review pending) | Naisargika-only confirmation; BPHS edition |
| Gana | SOURCE_CONFLICT | Deva×Rakshasa = 0 vs 1 |
| Bhakoot | SOURCE_CONFLICT | friendly-lords: cancel vs interpretive relief |
| Nadi | BLOCKED (review pending) | classification + exceptions (medical-safety constraint present) |

**Four unresolved source conflicts** (both candidates recorded, `resolution: PENDING`):
Vashya table form; Yoni gradations; Gana Deva×Rakshasa; Bhakoot friendly-lord relief.

## What IS validated this phase

- Independent natal-Moon astronomy (Gate 3) — **corroborated** to ≤ 20 arcsec by an
  implementation independent of Swiss Ephemeris.
- Interval boundary completeness (Gate 6) — **proven with limitations**.
- Database security (Gates 10, 11) — **hardened**, proven via non-owner roles.
- Guna evidence scaffolding (Gates 12–24) — **prepared** (source manifest,
  per-rule traceability, ordered Parihara model, domain-review package, 19 manual
  cases) with honest PENDING/BLOCKED/CONFLICT statuses and **no fabricated
  approvals, editions, pages, or reviewer sign-off**.

## Final verdicts

### Authority-validation verdict: **`AUTHORITY_VALIDATION_COMPLETE_WITH_EXPLICIT_EXCLUSIONS`**

The authorized validation and evidence workstreams (A–H) are complete: independent
astronomy validated, interval completeness proven-with-limitations, SECURITY
DEFINER/RLS hardened, and the full Guna authority evidence package prepared. The
following are **explicitly excluded** and remain open external gates: Swiss
production licensing (Gate 9), classical source-edition freeze (Gate 12), all eight
per-Koota rule authorities (Gates 13–20), and qualified domain-reviewer sign-off
(Gate 24). No user-facing Guna output is enabled (Gate 25 BLOCKED).

### Rule-pack verdict: **`RULE_PACK_BLOCKED`**

Issued because executable Guna rules remain `BLOCKED_DOMAIN_SOURCE`, four source
conflicts are unresolved, source editions are unfrozen, and domain review is
pending. (Independent natal-Moon validation and interval completeness — the two
astronomy preconditions the task names — are now satisfied, but the Guna authority
preconditions are not.)

## Exact next phase permitted

After the rule pack reaches `RULE_PACK_READY` or
`RULE_PACK_READY_WITH_EXPLICIT_EXCLUSIONS` — i.e., after the source editions are
frozen, the four conflicts are resolved, and a qualified Jyotisha/Sanskrit reviewer
signs off — implement the internal deterministic classical Guna Milan engine and
shared compatibility report using **only** the approved rules. **Do not** begin that
engine now.
