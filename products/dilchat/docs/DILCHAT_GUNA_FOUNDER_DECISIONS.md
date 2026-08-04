# DilChat Guna Milan — Founder Decisions Required

**Status: OPEN — none of the decisions below has been made.** This document
*surfaces* the choices that only Ugence Labs' founder (with a qualified domain
reviewer) can make. It does **not** decide any of them, and nothing in the rule
pack, code, or other documents silently assumes an answer. Every item here maps
to a rule-pack status that stays `PENDING`/`BLOCKED`/`SOURCE_CONFLICT` until the
decision is recorded.

> These are product-and-tradition decisions, not engineering defaults. The
> engineering has deliberately left each one **unresolved and fail-closed**:
> the pack is `executable:false`, every directional koota carries a role-ordering
> `PENDING` flag, and every unresolved rule is excluded from execution.

Related: `DILCHAT_GUNA_V1_TRADITION_SCOPE.md`, `DILCHAT_GUNA_RULE_ADJUDICATION_LEDGER.md`,
`DILCHAT_GUNA_SOURCE_ACQUISITION_REPORT.md`, `DILCHAT_ASTROLOGY_GUNA_AUTHORITY_GATE.md`,
and the decision log (`DILCHAT_DECISION_LOG.md`).

---

## FD-1 — Exact v1 textual tradition
**Maps to:** OQ-1, DEC-009, DEC-039 · **Pack effect:** `manifest.tradition`, every rule's `regional_applicability`

The pack assumes **North-Indian Ashtakoota** (8 koota, 36-point) derived from
*Muhurta Chintamani* (normative) + B. V. Raman (engineering). This is an
**assumed default, not confirmed.** The founder must confirm the exact textual
tradition, because South-Indian Dashakoota / Dina-based systems and regional
variants produce **different** results. Until confirmed, the pack must not be
described as universal or pan-Indian.

- **Decision needed:** Confirm North-Indian Ashtakoota per MC as the v1 tradition, or name a different one.
- **Blocks:** every koota's `regional_applicability`; the product wording.

## FD-2 — Bride/groom directional-role handling
**Maps to:** OQ-2 · **Pack effect:** `manifest.role_mapping`, `directional` flags on varna/tara/gana

Several kootas are **directional** (Varna: groom's rank ≥ bride's; Tara counting
from/to; Gana 3×3 groom-row/bride-column). DilChat's neutral roles are
`seeker`/`partner`. The default map `seeker→bride, partner→groom` is **unconfirmed**;
reversing it flips real outcomes (e.g. Gana Deva×Manushya = 6 vs Manushya×Deva = 5).

- **Decision needed:** Confirm the neutral-role → classical-role mapping, or define a policy for choosing it per couple.
- **Blocks:** varna/tara/gana execution; several manual cases.

## FD-3 — Same-sex and role-neutral compatibility policy
**Maps to:** OQ-2 (extension) · **Pack effect:** methodology selector (not yet defined)

Classical Ashtakoota assumes a bride and a groom. For same-sex or role-neutral
couples there is **no traditional bride/groom assignment.** The engineering will
**not** invent a symmetric classical result and will **not** claim the traditional
model is preserved unchanged.

- **Decision needed:** For non-traditional-role couples, choose one: (a) require an explicit role selection; (b) define a separate, clearly-labelled DilChat-derived (non-classical) methodology; or (c) defer the feature. Founder + reviewer decision.
- **Blocks:** any user-facing calculation for these couples (currently unsupported / separately-defined, per tradition-scope doc).

## FD-4 — Regional pack strategy
**Maps to:** OQ-1 · **Pack effect:** whether additional `*_v1` packs are authored

Will v1 ship a single North-Indian pack, or support multiple regional traditions
as separate versioned packs?

- **Decision needed:** Single-tradition v1, or multi-tradition with user/region selection.
- **Blocks:** FD-8 (user selection), release scope.

## FD-5 — Bhakoot relief: score change vs interpretation only
**Maps to:** source-conflict topic 4, `parihara.bhakoot_relief_lords_friends` · **Pack effect:** parihara effect type

When the two Moon-sign lords are mutually friendly, does Bhakoot dosha relief
**restore numeric points** (full cancellation) or **only soften the interpretive
severity**? This is a recorded `SOURCE_CONFLICT`; both candidates are kept and
**not** resolved. "Dosha relief" must **not** be equated with automatic
restoration to 7/7 unless a frozen source explicitly states it.

- **Decision needed:** After edition freeze + reviewer, choose numeric vs interpretive (or exclude the rule).
- **Blocks:** `bhakoot_relief_lords_friends` (disabled); Bhakoot manual cases.

## FD-6 — Nadi pada exceptions in v1
**Maps to:** `parihara.nadi_cancel_same_nakshatra_diff_pada`, DEC-021 · **Pack effect:** parihara inclusion

Are the pada-based Nadi-dosha cancellations (same nakshatra, different pada;
same rashi, different nakshatra) included in v1? Nadi carries the highest single
weight (8) and its exceptions are school-variable. **DEC-021 is absolute:** Nadi
is constitutional-temperament framing **only** — never medical, genetic,
fertility, pregnancy, progeny, or health, regardless of this decision.

- **Decision needed:** Include / exclude each Nadi exception for v1.
- **Blocks:** `nadi_cancel_*` (disabled); Nadi exception manual cases.

## FD-7 — Do incomplete/excluded rules block the whole calculation?
**Maps to:** rule-pack verdict semantics · **Pack effect:** fail-closed policy

If a koota cannot be authoritatively resolved for a given couple (e.g. a Yoni
gradation cell that stays `BLOCKED`), does DilChat (a) refuse to produce any
score, (b) produce a partial score with the unresolved koota clearly excluded and
flagged, or (c) something else? The engineering default is **fail-closed** (no
silent approximation).

- **Decision needed:** Choose the whole-calculation policy for unresolved koota.
- **Blocks:** `RULE_PACK_READY_WITH_EXPLICIT_EXCLUSIONS` semantics.

## FD-8 — User-selectable regional tradition
**Maps to:** FD-4 · **Pack effect:** product surface

If multiple traditions exist (FD-4), may users select one, and how is the choice
communicated?

- **Decision needed:** Allow/deny user selection; define default.
- **Blocks:** product UX; not an engineering decision.

## FD-9 — First release: full classical pack vs smaller pack with explicit exclusions
**Maps to:** rule-pack verdict · **Pack effect:** which rules are enabled at launch

Does the first release require **all** 8 kootas + all exceptions authoritatively
resolved, or launch a **smaller** pack (e.g. the reliably-attested cells:
Yoni diagonal + mortal-enemy, Nadi same/different, Bhakoot dosha detection) with
the source-variable cells **explicitly excluded and fail-closed**?

- **Decision needed:** Full pack, or reduced pack with product-visible exclusions.
- **Blocks:** the target rule-pack verdict (`RULE_PACK_READY` vs `..._WITH_EXPLICIT_EXCLUSIONS`).

## FD-10 — Product copy: traditional vs DilChat-derived interpretation
**Maps to:** DEC-021, tradition scope · **Pack effect:** interpretation/AI layer wording

How does product copy distinguish **traditional classical output** (traceable to
a frozen source) from any **DilChat-derived interpretation**? Nadi wording must
never imply health/fertility (DEC-021); Guna score must never absorb Mangal or
any other family (DEC-019).

- **Decision needed:** Approve the wording policy and the traditional-vs-derived labelling.
- **Blocks:** the (out-of-scope, future) interpretation layer.

---

## Summary

| ID | Decision | Blocks | Owner |
|----|----------|--------|-------|
| FD-1 | v1 textual tradition | tradition scope; all regional applicability | Founder + reviewer |
| FD-2 | bride/groom role mapping | varna/tara/gana execution | Founder + reviewer |
| FD-3 | same-sex / role-neutral policy | non-traditional-role calculation | Founder + reviewer |
| FD-4 | regional pack strategy | release scope | Founder |
| FD-5 | Bhakoot relief: score vs interpretation | `bhakoot_relief_lords_friends` | Reviewer + founder |
| FD-6 | Nadi pada exceptions in v1 | `nadi_cancel_*` | Reviewer + founder |
| FD-7 | unresolved koota → block whole calc? | ready-with-exclusions semantics | Founder |
| FD-8 | user-selectable tradition | product UX | Founder |
| FD-9 | full vs reduced first release | rule-pack verdict | Founder |
| FD-10 | traditional vs derived product copy | interpretation layer | Founder |

**None of the above is decided.** The engineering stays fail-closed until each is
recorded (in the decision log) and, where it depends on classical authority,
signed off by a qualified domain reviewer against a frozen edition.
