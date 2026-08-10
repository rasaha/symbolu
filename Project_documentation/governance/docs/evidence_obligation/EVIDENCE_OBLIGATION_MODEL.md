# Evidence-Obligation Model (Phase 2)

*`evidence_obligation/schema.py`. The canonical obligation record and the 14-type vocabulary. An
obligation says **what evidence standard a claim must meet** — nothing more.*

## Four things kept strictly separate

| Concern | Owner | This model |
|---|---|---|
| **Evidence obligation** — what standard applies | EvidenceObligation (this track) | assigns it |
| **Available evidence** — what evidence exists | Evidence binding | untouched |
| **Evidence sufficiency** — does available meet the standard | EvidenceAssurance (frozen) | never decided here |
| **Delivery decision** — allow / qualify / withhold | AssertionGate / ActionGate (frozen) | never decided here |

The single most important rule: **"no external evidence required" is represented as *obligation
satisfied by context*, never as *claim is verified*.** The obligation model cannot mark a claim true,
cannot judge sufficiency, and cannot authorize delivery or action.

## The 14 canonical obligation types

| Type | Meaning |
|---|---|
| EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | medical/legal/regulatory/current-policy/financial-risk |
| INDEPENDENT_CORROBORATION_REQUIRED | consequential/scientific/conflict-risk/high-impact factual |
| INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | approved policy / signed spec / authoritative internal record |
| IMPLEMENTATION_EVIDENCE_SUFFICIENT | code/API/schema/test-backed capability |
| TELEMETRY_OR_MEASUREMENT_REQUIRED | performance/latency/reliability/cost/operational status |
| ATTRIBUTION_VERIFICATION_REQUIRED | "according to X", quotes, reported third-party claims |
| POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | permissions/actions/approvals/authority |
| LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED | calculations/derivations/deterministic transforms |
| TEMPORAL_VERIFICATION_REQUIRED | current status / latest version / active incident |
| CONTEXTUAL_SUPPORT_SUFFICIENT | explanatory/local-summary/non-consequential description |
| NO_FACTUAL_EVIDENCE_GATE | opinion/preference/hypothetical/rhetorical/formatting |
| QUALIFY_BY_DEFAULT | uncertain but non-high-risk |
| HUMAN_REVIEW_REQUIRED | ambiguous authority / conflicting standard / novel high-impact |
| INDETERMINATE_OBLIGATION | unknown or unresolvable |

These are **never** collapsed into a binary "evidence required / not required" flag.

## Obligation groupings (used by policy + safety checks)

- **LOW_EXTERNAL_BURDEN** = {internal-authoritative, implementation, contextual, no-gate} — the utility
  levers: they permit clean delivery without *external/independent* evidence, but each still requires
  **its own** standard met by EvidenceAssurance.
- **HIGH_EXTERNAL_BURDEN** = {external-authoritative, independent-corroboration, telemetry,
  policy/authority} — never satisfiable by the artifact itself; unreachable by a low-burden shortcut on
  a high-risk claim.
- **REVIEW_OR_INDETERMINATE** = {human-review, indeterminate} — routed to a human, never auto-permitted.

## The obligation record

`EvidenceObligation` carries claim characterization (type, domain, risk, intended use), source
characterization (source_role, source_authority, artifact_authority), claim properties (actionability,
temporal/jurisdiction/population sensitivity, attribution_state, implementation_inspectability,
telemetry/policy/approval dependency), the obligation itself (type, minimum standard, required source
classes, independence/freshness/authority/contradiction-search/citation/human-review requirements,
no-gate rationale), and meta (confidence, unresolved ambiguity, reason codes, vocab/policy versions).

## Fail-closed structural validation

`validate_obligation` returns violation codes; three are hard structural errors:

- `OBL.UNKNOWN_TYPE` / `OBL.UNKNOWN_RISK` — unknown vocabulary.
- `OBL.NO_GATE_ON_HIGH_RISK` — `NO_FACTUAL_EVIDENCE_GATE` on a high/critical-risk claim (the Phase-13
  pilot blocker, enforced structurally).
- `OBL.LOW_BURDEN_ON_ACTION` — a low-external-burden obligation on an action proposal/directive (an
  action must always carry a policy/authority/approval path).

Unknown or unresolved obligations resolve to `INDETERMINATE_OBLIGATION` / `HUMAN_REVIEW_REQUIRED`, never
to a permissive class.
