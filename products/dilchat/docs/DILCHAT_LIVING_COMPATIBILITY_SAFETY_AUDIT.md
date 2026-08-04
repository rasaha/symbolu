# DilChat — Living Compatibility Safeguards Safety Audit

**Subsystem audited:** Living Compatibility (`living_compat_model_version = dilchat_living_v1`,
DL §0 line 46), realized by module `feedback` (`fb_*`: `FeedbackEvent`, `LivingCompatScore`;
DM §2.13) and fed by `agreements` (`agree_outcome_feedback`, DM §2.12), `journeys`, and
consented `feedback` signals.
**Audit stance:** Independent safety review, **design-only** (no production code exists).
Living Compatibility is a *sensitive, abuse-prone* subsystem: it is derived from consented
couple behavior and, if built naively, becomes exactly the "control/surveillance score" the
rest of the design forbids (PRIV A-7 line 116). This audit tests whether eight required
safeguards are already written into the design surface, and specifies each one explicitly
(rule → enforcement → test → verdict) so they are buildable, not aspirational.
**Verdict labels per safeguard:** `COVERED` (design already binds it), `PARTIAL` (adjacent
coverage exists but the specific rule/enforcement/test is not yet written), `ADDED-BY-THIS-AUDIT`
(no binding rule exists; this audit introduces it).

> **Evidence key.** PRIV = `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md`;
> DM = `DILCHAT_DATA_MODEL.md`; DL = `DILCHAT_DECISION_LOG.md`;
> AI = `DILCHAT_AI_INTEGRATION_SPEC.md`; PRD = `DILCHAT_BACKEND_PRODUCT_REQUIREMENTS.md`;
> TVP = `DILCHAT_TEST_AND_VALIDATION_PLAN.md`. Line numbers are as read at audit time.

---

## 0. Phasing note (read first — corrects the brief's assumption)

The task frames Living Compatibility as "Phase G, post-MVP." The **PRD places it earlier**:
PRD §6 assigns the **Living Compatibility aggregate to Phase F** ("In | F", PRD line 420;
roadmap table PRD lines 399–400), with Phase G being cross-cutting "Hardening, Hindi,
observability, exit." So the MVP already ships a *minimal jointly-visible aggregate* in
Phase F. The richer subsystem implied by the design canon and this brief — **explainable
sub-scores** derived from check-ins, agreement completion, conflict-repair and feedback,
evolving over time — is the post-MVP build-out (`LivingCompatScore.subscores`, DM line 547,
exists as a JSONB slot but its scoring semantics are unspecified). **This audit's safeguards
must be written into the design before *either* is implemented**: the Phase-F aggregate is
small enough that the eight safeguards are cheap to embed now and expensive to retrofit once
sub-score behavior and UI framing exist. The verdict retains the requested label
(`LIVING_COMPAT_NEEDS_SAFEGUARDS_BEFORE_PHASE_G`) and reads it as "before the hardening gate
and before the post-MVP Living Compatibility expansion."

---

## 1. What the current design already establishes (baseline)

Before adding safeguards, the design already binds the following about Living Compatibility.
These are the load-bearing quotes the eight safeguards build on:

- **Score-family separation & no feedback into astrology** — DL DEC-019 (lines 358–373):
  "**Living Compatibility** — `dilchat_living_v1`, from consented behavioral data. Never
  feeds back into (1)." and "Behavioral personalization can adjust presentation of (2) within
  clamped bounds but can **never** rewrite (1) or astrology history." Mirrored PRD §0 (line 25),
  TVP INV-7 (line 24), PB-11 (line 374).
- **Jointly-visible aggregate only; inputs stay private** — DL OQ-9 (line 444):
  "**Jointly-visible aggregate** only; each partner's private inputs/ratings stay private."
  Schema-bound: `fb_living_compat_score.subscores` = "aggregate only; no per-partner raw
  inputs" (DM line 547) and `inputs_trace` = "de-identified aggregate trace (never raw private
  ratings)" (DM line 549). `fb_feedback_event` is "private to submitter" (DM line 530).
- **Consent gates every input** — `fb_feedback_event.consented BOOLEAN … gates use in Living
  Compat (DEC-019)` (DM line 538); retention keeps "only `consented=true` … for model use"
  (DM line 813); `users_preferences.behavioral_personalization_enabled BOOLEAN DEFAULT true …
  gates Living Compat inputs (DEC-019)" (DM line 186).
- **Not a surveillance score (prose commitment)** — PRIV §11.1 (lines 959–964): "**Living
  Compatibility is not a surveillance score (DEC-019 OQ-9):** it is a jointly-visible aggregate
  with each partner's private inputs kept private; it is framed in-product as a shared
  reflection, **never** as a compliance/behavior score one partner can hold over the other, and
  it never feeds back into the immutable classical score. The UI language avoids 'you're
  failing / your score dropped' framings." Also AC-4 (lines 547–556) and asset A-7 (line 116):
  "Behavioral ratings; must never become a control/surveillance score."
- **AI may only summarize the aggregate** — AI value→producer table (line 87): "Living-
  compatibility aggregate … consume as jointly-visible aggregate only (OQ-9)"; AI never
  computes it (INVARIANT AI-1, AI lines 64–68).

These are strong foundations. **But every one of them is stated at the level of the *aggregate's
visibility and provenance*, not the *scoring model's internal incentives or the UI's framing
verbs*.** The eight safeguards below are precisely the rules that the scoring model and the
presentation layer need, and most of them are not yet written as enforceable constraints.

---

## 2. The eight required safeguards

Each safeguard is specified as: **(a) rule** (design-level), **(b) enforcement point**
(schema constraint / API rule / scoring-model rule / UI framing requirement),
**(c) test assertion**, **(d) verdict**.

### SG-1 — No partner RANKING

**(a) Rule.** The Living Compatibility subsystem MUST NOT rank one partner as "better,"
"more compatible," "more committed," or "the problem," and MUST NOT expose any per-partner
comparative score, leaderboard, or A-vs-B differential. The only legitimate framings are
**couple-level** ("*we* are at…") or **self-reflective** ("*your own* consented reflection").
No output — score, sub-score, trace, or AI summary — may attribute the aggregate's level to
one partner over the other.

**(b) Enforcement point.**
- *Schema constraint:* `fb_living_compat_score` carries only `couple_id`, `subscores` (JSONB,
  "aggregate only; no per-partner raw inputs", DM line 547) and `aggregate` — **no
  `partner_a_score`/`partner_b_score` columns, no `rank`, no `who_contributed` field**. Add an
  explicit closed-vocabulary constraint that `subscores` keys are couple-level dimension names
  (e.g. `repair`, `follow_through`, `responsiveness`) and never a member identifier.
- *Scoring-model rule:* `dilchat_living_v1` emits couple-level dimensions only; it is
  structurally forbidden from writing a per-member scalar into any shared or jointly-visible row.
- *UI framing requirement:* copy uses first-person-plural or second-person-self; the presentation
  layer has no template slot for a comparative verb ("you scored higher than…").
- *AI rule:* extends AI P10 (line 1128, "declaring one partner right/wrong") to behavioral
  scores — the adjudication classifier rejects any summary that ranks partners.

**(c) Test assertion.** `test_living_compat_no_per_partner_score`: for any couple, the
serialized `LivingCompatScore` and every AI `living_compat` summary contain no member-scoped
scalar and no comparative token; the `subscores` object's keys validate against the couple-level
dimension enum. Adjacent: TVP CL-07 (line 320).

**(d) Verdict.** **PARTIAL.** The aggregate-only schema (DM line 547) and AI P10 make ranking
*structurally awkward*, and PRIV §11.1 forbids "a score one partner can hold over the other,"
but **no rule names per-partner ranking as prohibited**, no schema constraint forbids a
per-member column, and no test asserts its absence. Made explicit here.

### SG-2 — No COERCION

**(a) Rule.** Living Compatibility MUST NOT be usable by one partner to pressure the other.
No feature may let partner A see (or generate) a score, delta, or notification whose purpose or
effect is to pressure partner B into compliance ("our score dropped because of you"). Because
the aggregate is *symmetric and jointly-visible* (OQ-9), it must be **identical for both
partners at all times** — there is no A-only or B-only view, no private "your partner is
dragging the score down" surface, and no per-partner trend that isolates one member's behavior.

**(b) Enforcement point.**
- *API rule:* the `LivingCompatScore` read endpoint returns the **same bytes to both members**
  of an active couple (SHARED scope, DM line 545); there is no query parameter, filter, or
  companion endpoint that decomposes the aggregate by member. Cross-private existence rules
  (PRIV INV-9 line 89) already forbid A from probing B's private feedback.
- *Scoring-model rule:* no "responsibility attribution" output; deltas are couple-level.
- *UI framing requirement:* extends PRIV §11.1 (lines 962–964) — the presentation layer bans
  "your score dropped," second-person-blaming, and any push notification tying a score change to
  a partner's action. Score changes are surfaced as neutral, mutual reflection, if at all.

**(c) Test assertion.** `test_living_compat_symmetric_visibility`: the score payload for member
A byte-equals the payload for member B; no endpoint or field yields a member-decomposed value.
`test_no_score_change_blame_notification`: no notification template references a partner as the
cause of a score change.

**(d) Verdict.** **PARTIAL.** Symmetric visibility is implied by SHARED scope + OQ-9, and PRIV
§11.1 forbids the "hold over the other" framing in prose, but the **byte-equality guarantee and
the no-blame-notification rule are not written or tested.** Made explicit here.

### SG-3 — Not rewarding SURRENDER as compromise

**(a) Rule.** A "compromise" in which one partner simply capitulates MUST NOT increase the
Living Compatibility score. Repair/agreement *quality* is measured by **mutuality and durability**,
never by the mere existence of an agreement or by one-sided concession. Specifically: an agreement
whose terms serve only one partner, a repair recorded by only one side, or a pattern where the
same member always yields, must **not** raise the aggregate and should, if anything, be treated
as a low-quality signal (surfaced neutrally, never as blame — see SG-1/SG-2).

**(b) Enforcement point.**
- *Scoring-model rule (`dilchat_living_v1`):* agreement-derived inputs are weighted by
  **dual-approval symmetry and both-party outcome feedback**, not by completion alone. An
  `Agreement` reaching `active` already requires two-party approval (DM `agree_approval`,
  §2.12; OQ-8; PRD FR-1202); the score consumes the **presence of both approvals** and **both
  partners' `agree_outcome_feedback.rating`** (DM lines 516–524, private per OQ-9), not a single
  "completed" boolean. A concession detector: if outcome feedback is one-sided or divergent, the
  contribution is down-weighted, not up-weighted.
- *AI rule (already partially present):* `compromise_options` carries a **balance requirement** —
  "every option MUST address both `serves_a` and `serves_b` non-trivially… DilChat does not
  surface one-sided 'compromises'" (AI lines 852–855). This audit lifts that principle from the
  *AI suggestion layer* into the *scoring model*: what the AI won't *propose*, the score won't
  *reward*.
- *Design-level rule:* "agreement completion" as a raw input (PRD J-10 line 199) is **redefined**
  as "mutually-approved, mutually-rated agreement durability."

**(c) Test assertion.** `test_surrender_does_not_raise_score`: a synthetic history where member A
always yields (agreements serve only B; A's private outcome ratings are low while B's are high)
produces an aggregate **no higher** than a balanced-repair baseline, and strictly lower than a
mutual-repair history of the same volume. `test_completion_alone_insufficient`: an agreement
marked complete but lacking both-party positive outcome feedback contributes ≤ the neutral weight.

**(d) Verdict.** **ADDED-BY-THIS-AUDIT.** The AI *proposal* layer refuses one-sided compromises
(AI lines 852–855), but **no scoring-model rule exists** — `dilchat_living_v1`'s inputs are only
sketched ("agreement adherence, journey completion, ratings," PRD J-10 line 199) and would, as
written, reward capitulation as "adherence." This is the audit's most substantive scoring-model
addition.

### SG-4 — Not penalizing PRIVACY

**(a) Rule.** Declining to share, using private chat, withholding a rating, or setting
`behavioral_personalization_enabled = false` MUST NOT lower any *visible* score, and MUST NOT be
detectable by the partner. Two sub-rules: **(i) existence non-disclosure** — the fact that a
member opted out or shared nothing is never surfaced (INV-9); **(ii) no penalty** — the scoring
model treats absent/withheld input as *reduced confidence or "not enough signal yet,"* never as
a negative contribution, and the jointly-visible surface never shows a lowered number that a
partner could attribute to the other's privacy choice.

**(b) Enforcement point.**
- *Existence non-disclosure (already covered):* PRIV INV-9 (line 89); AC-2 (lines 528–535) — no
  count, timestamp, or "last active in private" for a partner's private data; AC-1(d) (line 526)
  — "No feature exposes 'you haven't shared anything.'"
- *Scoring-model rule (new):* opt-out or missing input yields a **confidence reduction**
  (`LivingCompatScore` should carry a confidence field, mirroring `transit_couple_climate.confidence`
  DM line 320 and `CoupleClimate` patterns) and **suppression of display below a minimum-signal
  threshold**, not a lower aggregate. When personalization is disabled, the subsystem does not
  compute a *worse* score — it computes *no new* score and the UI shows a neutral "reflection
  paused," identical whether the pause is A's or B's choice (so neither the number nor its absence
  fingerprints who opted out).
- *UI framing requirement:* the "paused/insufficient-signal" state is member-agnostic and
  non-accusatory.

**(c) Test assertion.** `test_optout_does_not_lower_score`: toggling one member's
`behavioral_personalization_enabled` to false does not decrease the last jointly-visible aggregate
and does not emit a partner-visible signal attributing any change. `test_withheld_rating_is_low_confidence_not_penalty`:
a withheld `fb_feedback_event` reduces confidence (or display-suppresses) rather than reducing the
aggregate. `test_optout_indistinguishable_between_partners`: the paused-state payload is identical
regardless of which member opted out.

**(d) Verdict.** **ADDED-BY-THIS-AUDIT** for the no-penalty scoring rule; **COVERED** for
existence non-disclosure (INV-9, AC-1, AC-2). The consent gate exists (DM lines 186, 538) but its
*effect on the visible score* is unspecified — as written, an opt-out simply removes inputs, which
a mean-based aggregate could render as a drop. The confidence/threshold/paused-state design is new.

### SG-5 — No exposure of private SATISFACTION scores

**(a) Rule.** One partner's private satisfaction/accuracy feedback — every `fb_feedback_event`,
every `agree_outcome_feedback` rating and note — is **never** shown to the other partner, directly
or by inference. Only the consented, de-identified **joint aggregate** crosses into shared view
(OQ-9). No sub-score, trace, or AI summary may be fine-grained enough to reconstruct a single
member's private rating.

**(b) Enforcement point.**
- *Schema constraint (already strong):* `fb_feedback_event` is USER/PRIVATE, "private to
  submitter" (DM line 530); `fb_feedback_event.accuracy`/`rating` are USER-scoped (DM lines 536–537);
  `agree_outcome_feedback` is `PRIVATE_A/B` with `note_encrypted` HIGHLY-SENSITIVE app-enc (DM
  lines 516–524; §7.2 line 692); `fb_living_compat_score.subscores` = "no per-partner raw inputs"
  (DM line 547) and `inputs_trace` = "de-identified aggregate trace (never raw private ratings)"
  (DM line 549).
- *API/scoring-model rule (new hardening):* the aggregation function must enforce a **k-anonymity /
  minimum-contributors floor** so a sub-score cannot mathematically equal a single member's raw
  rating (e.g., a "sub-score" computed from exactly one member's one rating is display-suppressed,
  reusing the SG-4 threshold). This closes the inference channel that "aggregate only" alone leaves
  open when one side has contributed nothing.
- *Authorization backstop:* PRIV `authorize()` R1 (lines 299–301) returns `NOT_FOUND` for any
  cross-private read of the partner's feedback rows.

**(c) Test assertion.** `test_private_satisfaction_never_in_shared` (extends TVP CL-07, line 320):
no `LivingCompatScore` field, trace, or AI summary contains or allows reconstruction of a single
member's raw `rating`/`accuracy`/note. `test_single_contributor_subscore_suppressed`: a sub-score
backed by one member's lone rating is not emitted.

**(d) Verdict.** **COVERED** for the core rule (OQ-9 + DM lines 530, 547, 549; INV-1/R1); **PARTIAL**
on the reconstruction/inference edge — the minimum-contributors floor that prevents an "aggregate"
of one from leaking a private rating is added here.

### SG-6 — No STREAK-based relationship pressure

**(a) Rule.** Living Compatibility (and the surrounding feedback/journey UX) MUST NOT use
gamified streaks, "don't break your streak," daily-login chains, decay timers, or any mechanic
that manufactures pressure to interact or to keep a number from falling. Engagement with a
relationship product must never be coerced by loss-aversion mechanics, which are especially
harmful in a coercive-partner context (PRIV ADV-2, lines 156, 166–172).

**(b) Enforcement point.**
- *Design-level rule (non-feature):* streaks/decay are a named **non-feature**, in the spirit of
  PRIV §11 "deliberate non-features" and PRD NG-4 (line 442, no surveillance). No `streak_count`,
  `consecutive_days`, or time-since-last-activity-penalty field in `fb_*` or presentation state.
- *Scoring-model rule:* the aggregate is **not** a function of interaction *recency or frequency
  cadence*; absence of recent activity lowers *confidence/freshness* (SG-4), never inflicts a
  score penalty, and is never framed as a broken streak.
- *UI framing requirement:* no countdown, no "keep it going," no red/declining-number urgency; no
  push notification whose purpose is to preserve a streak or arrest a decline.

**(c) Test assertion.** `test_no_streak_fields`: no schema or serialized state exposes a streak/
consecutive-count/decay-timer. `test_inactivity_no_score_penalty_no_streak_copy`: a gap in
activity reduces freshness/confidence only, and no notification or copy uses streak/loss-aversion
language.

**(d) Verdict.** **ADDED-BY-THIS-AUDIT.** Streaks are **not mentioned anywhere** in the design;
the anti-surveillance posture (NG-4, PRIV §11) is congenial but does not prohibit gamified
pressure. Named as a non-feature here.

### SG-7 — No inferring ABUSE from insufficient evidence

**(a) Rule.** The system MUST NOT label a relationship "abusive," "unhealthy," "toxic," or
"failing," nor flag a partner as an abuser, from behavioral signals (low repair score, conflict
frequency, declining aggregate, one-sided agreements). Living Compatibility is not a diagnostic
instrument. When a user **self-discloses** distress, abuse, or danger, the system surfaces
**neutral support resources** (never a diagnosis), via the AI `safety` object and crisis-resource
pathway.

**(b) Enforcement point.**
- *Scoring-model rule (new):* `dilchat_living_v1` has **no "relationship health" verdict output,
  no abuse/toxicity classifier, no risk label**. A low aggregate is presented as "an area to talk
  about together," never as a judgment about the relationship's safety or a partner's character.
  This complements DEC-019's separation but is a distinct, previously-unstated constraint on what
  the behavioral model may *conclude*.
- *AI safety layer (already covered on the AI side):* AI P4 (line 1122, no psychiatric diagnosis),
  P8 (line 1126, never pressure to remain; surface domestic-abuse resources; `escalate=true`; do
  not diagnose), §8.4 (lines 1446–1462): "surfaces *resources*, never a determination that the
  user 'has' a condition or that the partner 'is' an abuser"; ties to the `safety` object (AI §8.3,
  lines 1409–1444) and region-appropriate `crisis_resources` (India-first, OQ-13). DEC-021 (DL
  lines 399–400): "AI must never infer … psychiatric diagnosis, or pressure a user to remain in an
  unsafe relationship."
- *Design-level rule:* self-disclosure → resources is the **only** abuse-adjacent behavior; the
  score never triggers an abuse inference on its own.

**(c) Test assertion.** `test_low_score_no_abuse_label`: no aggregate value, however low, produces
a "relationship is unhealthy/abusive" or partner-is-abuser output in score, trace, notification, or
AI summary. `test_self_disclosure_surfaces_resources_not_diagnosis`: a self-disclosure yields
`safety.escalate=true` + `crisis_resources`, with no diagnostic or blame language (extends AI §8.4).

**(d) Verdict.** **PARTIAL.** The **AI self-disclosure pathway is COVERED** (AI P4/P8/§8.4, DEC-021).
The **scoring-model rule that behavioral signals never yield an abuse/health verdict is
ADDED-BY-THIS-AUDIT** — nothing today stops a future `dilchat_living_v1` from emitting a
"relationship risk" label from low sub-scores.

### SG-8 — No use in EMPLOYMENT, CREDIT, INSURANCE, MEDICAL, or LEGAL decisions

**(a) Rule.** Living Compatibility MUST NOT be used, or be usable, as evidence in employment,
credit, insurance, medical, or legal decisions about a person. DEC-021's existing prohibition —
written for *astrology* — is **restated and explicitly extended to behavioral Living
Compatibility**, which is otherwise textually outside its scope. A standing disclaimer accompanies
every Living Compatibility surface, and the subsystem is **never exported in a form suitable as
such evidence** (no signed/official-looking "compatibility certificate," no per-person score in an
export bundle that reads as an assessment of an individual).

**(b) Enforcement point.**
- *Existing coverage (astrology only):* PRIV INV-16 (line 96): astrology "may **not** be used as
  evidence for medical/psychiatric/employment/credit/insurance/legal decisions"; DL DEC-021 (lines
  397–398); PRD NG-3 (line 441); PRIV P9 (lines 71–72). **These name *astrology*, not behavioral
  scores** — the extension below is the gap this audit closes.
- *Design-level rule (new):* the DEC-021 non-evidentiary clause is amended to read "astrology
  outputs **and Living Compatibility / any DilChat behavioral score**." A standing disclaimer
  ("A private reflection tool for the two of you; not an assessment of any individual and not
  evidence for any employment, credit, insurance, medical, or legal decision") is required on every
  `LivingCompatScore` render, alongside the disclaimers already mandated on AI output (AI A.2, lines
  1592–1601).
- *Export rule (new):* the export job (PRIV §10.1–10.2) includes Living Compatibility only as the
  couple-level jointly-visible aggregate the requester already sees, **clearly labeled
  non-evidentiary**, never decomposed per-person, never rendered as a certificate. Because the
  score is couple-level and per-partner inputs stay private (SG-5), an export cannot produce an
  individual assessment.

**(c) Test assertion.** `test_living_compat_disclaimer_present` (extends TVP-style disclaimer
checks): every Living Compatibility render and export carries the non-evidentiary disclaimer.
`test_export_living_compat_not_per_person`: an export contains no per-individual behavioral score
and no certificate-shaped artifact. `test_dec021_extension_covers_behavioral`: the guardrail that
refuses adverse-decision framing (adjacent to PRIV `test_ai_refuses_adverse_decision_use`, line
1018) also fires for Living Compatibility, not only astrology.

**(d) Verdict.** **PARTIAL / ADDED-BY-THIS-AUDIT.** The prohibition is **COVERED for astrology**
(INV-16, DEC-021, NG-3) but **DEC-021 does not textually reach behavioral Living Compatibility**;
the explicit extension, the per-surface disclaimer, and the export-shape rule are added here.

---

## 3. Data-minimization & consent restatement

- **Only consented inputs.** Living Compatibility consumes an input **iff**
  `fb_feedback_event.consented = true` (DM line 538) and the submitter's
  `behavioral_personalization_enabled = true` (DM line 186). Retention keeps only
  `consented=true` events for model use (DM line 813). No private message content, no raw birth
  data, no non-consented rating ever enters `dilchat_living_v1`. The AI, when summarizing, receives
  only the already-computed aggregate (AI line 87), never the raw ratings (AI §4 ContextBuilder
  allow-list; §9 privacy controls).
- **Disable / reset semantics.** Setting `behavioral_personalization_enabled = false` (or an
  explicit "reset Living Compatibility") **clears/pauses behavioral personalization** — future
  aggregates are not computed, and a reset discards the derived `LivingCompatScore` history and the
  de-identified `inputs_trace` — **but does NOT touch immutable astrology**: `NatalChart` and
  `GunaMilanReport` are immutable per version tuple (DM §0 line 28, DEC-019) and are unaffected,
  because Living Compatibility "never feeds back into (1)" (DEC-019 line 369). Disable/reset is a
  behavioral-layer operation only. This must be stated in the UI so a user is not misled into
  thinking it alters their classical chart (it cannot) or that it deletes their partner's private
  ratings (those are the partner's to control).
- **Data minimization.** `LivingCompatScore` stores couple-level aggregate + de-identified trace
  only (DM lines 547–549); raw private satisfaction inputs remain in the submitter's private scope
  under app-level encryption where free-text (DM `agree_outcome_feedback.note_encrypted`, line 523).
  No new identifying field is introduced by Living Compatibility.

## 4. Explainability requirement (no hidden diagnosis)

- **Every sub-score has a human-readable trace.** Each dimension in `LivingCompatScore.subscores`
  MUST be accompanied by a plain-language explanation of *what it measures* and *which consented,
  de-identified signal classes moved it* ("this reflects how often agreements you both approved
  were followed through, as rated by both of you") — never a psychological profile, personality
  label, or clinical inference. This extends the product's existing explainability discipline
  (`DailyPersonalProfile.explanation_trace`, DM line 307; `calc_trace` on classical rows) to the
  behavioral family, which today only has an aggregate `inputs_trace` (DM line 549) with **no
  requirement that it be human-readable or per-sub-score**.
- **No hidden psychological diagnosis.** The trace and any AI rendering are bound by AI P1 (motive
  attribution), P4 (no psychiatric diagnosis), and SG-7: the explanation describes behavior
  categories, never diagnoses a person or the relationship.
- **Enforcement/test.** `test_every_subscore_has_readable_trace`: no `LivingCompatScore` is
  emitted with a sub-score lacking a non-empty, non-diagnostic human-readable trace;
  `test_trace_contains_no_clinical_terms`: the trace passes the clinical/diagnostic classifier
  used on AI output (AI §8.2). **Verdict: PARTIAL** — an aggregate trace field exists (DM line 549)
  but the per-sub-score, human-readable, non-diagnostic requirement is added here.

## 5. Living Compatibility is NOT a surveillance score

Restated as a first-class, testable commitment (elevating PRIV §11.1 lines 959–964 and asset A-7
line 116 from prose to requirement): Living Compatibility must **never** be presented, framed, or
built as a tool for one partner to *monitor* the other. It is a shared, symmetric reflection
(SG-2), with no per-partner decomposition (SG-1), no privacy penalty (SG-4), no private-rating
exposure (SG-5), and no engagement-coercion mechanics (SG-6). There is no "activity feed," no
"your partner's participation," no one-directional view. Any presentation that reads as *A watching
B* is a release-blocking defect, consistent with PRD NG-4 (line 442) and PRIV AC-4 (lines 547–556).
**Test:** `test_no_one_directional_living_compat_surface` — every Living Compatibility surface is
mutual and symmetric; no endpoint, field, or notification exposes one partner's participation to the
other.

---

## 6. Safeguards status table

| ID | Safeguard | Enforcement locus | Verdict |
|----|-----------|-------------------|---------|
| **SG-1** | No partner ranking / leaderboard | Schema (no per-member column) + scoring-model + UI + AI P10 | **PARTIAL** |
| **SG-2** | No coercion (symmetric, no blame) | API byte-equality + scoring-model + UI framing | **PARTIAL** |
| **SG-3** | Surrender ≠ compromise (mutuality-weighted) | Scoring-model (dual-approval + both-party outcome) + AI balance rule | **ADDED-BY-THIS-AUDIT** |
| **SG-4** | No privacy penalty (opt-out safe) | Existence non-disclosure (COVERED) + confidence/threshold scoring (ADDED) | **ADDED-BY-THIS-AUDIT** (+COVERED part) |
| **SG-5** | No private-satisfaction exposure | Schema (private inputs; aggregate-only) + min-contributors floor | **COVERED** (+PARTIAL edge) |
| **SG-6** | No streak / loss-aversion pressure | Non-feature rule + scoring-model + UI | **ADDED-BY-THIS-AUDIT** |
| **SG-7** | No abuse inference from signals; resources on self-disclosure | Scoring-model no-verdict (ADDED) + AI P4/P8/§8.4 (COVERED) | **PARTIAL** |
| **SG-8** | No employment/credit/insurance/medical/legal use | DEC-021 extension + per-surface disclaimer + export-shape rule | **PARTIAL / ADDED** |
| **DM/Consent** | Consented inputs only; disable/reset clears personalization, not astrology | `consented` + `behavioral_personalization_enabled` gates; DEC-019 no-feedback | **COVERED** (restated) |
| **Explainability** | Per-sub-score human-readable, non-diagnostic trace | `LivingCompatScore` trace requirement + clinical classifier | **PARTIAL** |
| **Not surveillance** | Symmetric, mutual, no monitoring surface | PRD NG-4 + PRIV §11.1 elevated to test | **PARTIAL** (prose→testable) |

**Tally:** 1 fully `COVERED` (SG-5 core), 3 `ADDED-BY-THIS-AUDIT` (SG-3, SG-4 scoring rule, SG-6),
4 `PARTIAL` (SG-1, SG-2, SG-7, SG-8), plus explainability and the surveillance restatement moving
from prose to enforceable requirement. **Zero of the eight safeguards is fully specified today as
rule + enforcement + test.**

## 7. Verdict

> ### **LIVING_COMPAT_NEEDS_SAFEGUARDS_BEFORE_PHASE_G**

The foundations are genuinely strong — score-family separation (DEC-019), jointly-visible
aggregate with private inputs (OQ-9, DM lines 547–549), consent gates (DM lines 186, 538), and a
clear "not a surveillance score" *intent* (PRIV §11.1). But intent is not enforcement. Of the eight
required safeguards, **three have no binding rule at all** (SG-3 surrender-weighting, SG-4 privacy-
penalty avoidance in the scoring model, SG-6 streaks), **four are only partially covered** (SG-1,
SG-2, SG-7 scoring side, SG-8 behavioral extension of DEC-021), and even the best-covered (SG-5)
has an open inference edge. Critically, the two documents that would carry these rules — the
scoring-model semantics of `dilchat_living_v1` and the presentation/UI framing spec — **do not yet
specify Living Compatibility's internal incentives or framing verbs at all**; `LivingCompatScore.subscores`
is an empty JSONB slot (DM line 547) whose behavior is undefined.

Therefore: the safeguards enumerated here (SG-1…SG-8, plus the data-minimization/consent,
explainability, and non-surveillance requirements) **MUST be written into the design surface —
DEC-019/DEC-021 amendments, the `feedback`/`dilchat_living_v1` scoring-model spec, the
`LivingCompatScore` schema constraints, the UI-framing spec, and the test plan — before Living
Compatibility is implemented** (the Phase-F aggregate and, above all, the post-MVP sub-score
expansion this brief calls Phase G). Several safeguards are cheapest to embed while the subsystem is
still a single aggregate row and no framing copy exists; retrofitting them after sub-scores, traces,
and notifications ship would be far more expensive and error-prone.

---

*End of audit. Design-only; no production code implied or written. This document adds required
safeguards to the design surface and does not modify other files. Authoritative sources remain the
Decision Log (DEC-019, DEC-021, OQ-8, OQ-9) and the Privacy/Consent/Security architecture; on any
conflict, the Decision Log wins and this audit is the bug.*
