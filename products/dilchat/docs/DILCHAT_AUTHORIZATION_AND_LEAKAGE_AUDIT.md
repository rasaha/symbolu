# DilChat — Authorization & Leakage Audit

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Document type:** Independent security verification audit (design-phase).
**Auditor role:** External authorization & data-leakage verification. This document
does **not** author design; it verifies the design already stated in the four
primary sources and records findings. Where it recommends, it recommends *additions
to the spec*, not code.

**Primary evidence (quoted with line refs):**
- `DILCHAT_PRIVACY_CONSENT_AND_SECURITY.md` — cited as **[PRIV Lnn]**
- `DILCHAT_DATA_MODEL.md` — cited as **[DM Lnn]**
- `DILCHAT_API_SPEC.md` — cited as **[API Lnn]**
- `DILCHAT_AI_INTEGRATION_SPEC.md` — cited as **[AI Lnn]**

**Verdict (summary):** **AUTHZ_SOUND_WITH_FINDINGS.** The three-scope model,
existence non-disclosure, and consent-gated projection are strong and internally
consistent. Two items must be closed in the spec before Phase D implementation:
**AUTHZ-1 (GAP)** — in-flight background-job authorization, and **AUTHZ-2
(PARTIAL)** — self-containment of shared projections vs. deleted private sources.
Full findings table in §5.

---

## 0. Method and default-deny baseline

The design declares default-deny as its first principle and repeats it at every
layer. This audit treats any access path that does **not** resolve to an explicit
grant as a **FINDING**, per the design's own rule:

> "**P1 — Default deny.** Absence of an explicit grant is a denial, everywhere, at
> every layer. No code path treats 'unknown' as 'allow.'" — **[PRIV L52]**

The decision function is the spine of the whole model and is quoted in full because
every matrix cell below resolves through it:

```
authorize(ctx: ScopeContext, action: Action, resource: ResourceRef) -> Decision
Decision ∈ { ALLOW, DENY_NOT_FOUND, DENY_FORBIDDEN }
# Ordered rules; first match wins. No fallthrough to ALLOW.
R0  if ctx.actor_user_id is None or session invalid:      return DENY_FORBIDDEN
R1  if resource.scope in {PRIVATE_A, PRIVATE_B}:
        if resource.owner_user_id == ctx.actor_user_id:   return ALLOW
        else:                                             return DENY_NOT_FOUND
R2  if resource.scope == SHARED:
        if resource.couple_id != ctx.couple_id:           return DENY_NOT_FOUND
        if ctx.membership_status != ACTIVE:               return DENY_FORBIDDEN
        if action requires DUAL_APPROVAL and not dual_ok: return DENY_FORBIDDEN
        return ALLOW
R3  default:                                              return DENY_FORBIDDEN
```
— **[PRIV L292–L308]**

Confirmed occurrences of the default-deny commitment (reproduced, not contradicted):
- Privacy doc: P1 **[PRIV L52]**, INV-3 **[PRIV L83]**, R3 **[PRIV L307]**, RLS
  "Default deny" **[PRIV L—/DM L731]**, ScopeContext "default deny at the data
  layer" **[PRIV L263]**, TB-2 authorize() default-deny **[PRIV L196]**, denial
  quick-reference **[PRIV L1061]**, checklist INV-3 **[PRIV L1005]**.
- Data model: canon "default-deny" **[DM L24]**, RLS "Default deny: enable + force
  RLS, no permissive policy" **[DM L731]**, "default-deny in code, mirroring RLS
  default-deny" **[DM L790]**, "default-deny is the initial state" **[DM L926]**,
  ScopeContext rule 1 **[DM L789]**, guna preview fallback default-deny posture.
- API: "**Default deny** — a query without a resolved scope is refused by the
  repository layer" **[API L173–174]**, and the scope-model recap **[API L171]**.

RLS is an independent backstop enforcing the same predicate:

> "RLS is enabled **and forced** on every scope-bearing table… Default deny: enable
> + force RLS, no permissive policy unless stated." — **[DM L726, L731]**

---

## 1. PART 1 — Authorization matrix

Legend: **ALLOW** = explicit grant · **DENY-404** = `DENY_NOT_FOUND` (existence
hidden, uniform 404) · **DENY-403** = `DENY_FORBIDDEN` (existence known, action
refused) · **DENY(dual)** = allowed only with two-party approval · **n/a** = actor
cannot be positioned against this resource at all.

"Partner A private data" / "Partner B private data" = `PRIVATE_A` / `PRIVATE_B`
rows (`pchat_*`, `agree_outcome_feedback`, private `fb_feedback_event`, birth
profile, natal chart, personal daily profile — all `owner_user_id`-bound). "Shared
couple data" = `SHARED` rows (`schat_*`, `couple_*`, journeys, agreements bodies,
`CoupleClimate`, `LivingCompatScore`, live `SharedArtifact`). "Guna report" =
`guna_report` (couple-scoped when paired, USER-preview when `couple_id NULL`).
"Daily profile" = `transit_daily_personal` (USER scope). "Agreement approval" =
`POST /v1/agreements/{id}:approve` effect.

| Principal | Partner A private | Partner B private | Shared couple data | Guna report | Daily profile | Agreement approval |
|---|---|---|---|---|---|---|
| **Partner A** | ALLOW (R1 owner) | **DENY-404** (R1) | ALLOW (R2 ACTIVE) | ALLOW (R2 couple) | ALLOW (own USER) | DENY(dual) — 1 of 2 |
| **Partner B** | **DENY-404** (R1) | ALLOW (R1 owner) | ALLOW (R2 ACTIVE) | ALLOW (R2 couple) | ALLOW (own USER) | DENY(dual) — 1 of 2 |
| **Unpaired user** (no couple) | ALLOW *own* only | **DENY-404** | **DENY-404** (R2 couple mismatch) | ALLOW own preview `couple_id NULL`; **DENY-404** others | ALLOW own | **DENY-403** (no membership) |
| **Holder of expired invitation** | ALLOW *own* only | **DENY-404** | **DENY-404** (never became a member) | ALLOW own preview only | ALLOW own | **DENY-403 / 410** |
| **Former partner** (post-unpair) | ALLOW *own* only | **DENY-404** | **DENY-403** (R2 membership REVOKED) | **DENY-403** (couple-scoped) | ALLOW own | **DENY-403** (COUPLE_NOT_ACTIVE) |
| **Administrator** | **DENY-403 / ciphertext-blind** | **DENY-403 / ciphertext-blind** | ref/status only, no plaintext | ref/status only | ref/status only | n/a (cannot approve) |
| **Background job (arq)** | scope of enqueuing owner | scope of enqueuing owner | couple scope at enqueue — **⚠ FINDING** | job scope | job scope | n/a |
| **AI prompt builder** (ContextBuilder) | own-task subset only | **DENY** (physically excluded) | consented `SharedArtifact` only | derived labels only | own derived labels | n/a (suggest/draft only) |
| **Support personnel** | **DENY** (no capability) | **DENY** (no capability) | status only, no content | status only | status only | n/a |

### 1.1 Cell-by-cell control citations

**Partner A / Partner B — cross-private = DENY-404, not 403.** The defining
control, reproduced as confirmed evidence:

> "if resource.owner_user_id == ctx.actor_user_id: return ALLOW … else: return
> DENY_NOT_FOUND   # INV-9: existence hidden" — **[PRIV L300–L301]**

> "Reading `GET /v1/birth-profiles/{id}` for an id you don't own → `404`
> (indistinguishable from a nonexistent id)." — **[API L323]**

> "INV-9 · A partner **cannot query whether the other used private chat**.
> Cross-private access returns `NOT_FOUND`." — **[PRIV L89]**

The `resolved_scope` type itself makes `PRIVATE_OTHER` unrepresentable — a
structural, not merely procedural, guarantee:

> "there is no `PRIVATE_OTHER` value the system can even represent — the *other*
> partner's private scope is not addressable (INV-1, INV-9)." — **[PRIV L283–L284]**

**Partner A/B — shared data = ALLOW while ACTIVE.** R2 requires
`membership_status == ACTIVE` **[PRIV L304]**; reachability is `iff` an active
membership exists:

> "A `SHARED` row … is reachable **iff** the requester has an `active`
> `couple_membership` for that `couple_id`. There is no other path." — **[DM L655–L657]**

Membership is re-resolved every request (INV-4), so a stale ACTIVE cannot be
replayed: "`couple_id` and `membership_status` are **re-resolved on every
request**… A cached membership is never trusted across requests." — **[PRIV L281–L282]**

**Partner A/B — agreement approval = DENY(dual).** A single caller cannot commit;
this is the only class where one authenticated member is structurally insufficient:

> ":approve requires **both** members before the agreement becomes `active` (OQ-8).
> The second distinct member's approval is the commit point; a member cannot
> approve twice." — **[API L538–L539]**

> "if action requires DUAL_APPROVAL and not dual_ok: return DENY_FORBIDDEN" —
> **[PRIV L305]**; surfaced as `403 DUAL_APPROVAL_REQUIRED` **[API L304]**.

**Unpaired user & expired-invitation holder — shared/guna = DENY-404.** These
actors have no `couple_id` matching the resource, so R2's first clause fires with
the existence-hiding shape: "if resource.couple_id != ctx.couple_id: return
DENY_NOT_FOUND   # not this couple" — **[PRIV L303]**. The expired-invitation holder
additionally never crosses into membership: an expired invite yields
`410 INVITATION_EXPIRED` **[API L308, L698]** and no `couple_membership` row is
written, so there is no ACTIVE slot to resolve. Both retain full access to their
**own** private and USER-scoped data (the guna *preview* with `couple_id NULL`
falls back to the owning chart's user, **[DM L762–L768]**).

**Former partner (post-unpair) — shared/guna/approval = DENY-403.** This is the one
place the design deliberately returns 403 rather than 404, because the ex already
legitimately knew the couple existed:

> "**`DENY_FORBIDDEN`** (403) is returned only when the *existence* is already known
> and non-sensitive but the action is not permitted — e.g. a **former** member
> (post-unpair) touching *their own couple's* shared data (they already know the
> couple existed)." — **[PRIV L319–L321]**

Immediacy is guaranteed by the unpair transaction flipping every membership to
`revoked` in one transaction:

> "**All** `couple_membership` rows for the couple: `status → 'revoked'`,
> `revoked_at = now()` — **immediately**. This alone severs SHARED reachability…
> every SHARED RLS policy requires `status='active'`." — **[DM L829–L832]**

Critically, the former partner **never** gains the other's private scope, and their
*own* private scope is untouched by unpair: "Each partner's PRIVATE data is
untouched… entirely unaffected by unpairing." — **[DM L852–L855]**. Cross-private
therefore remains DENY-404 even for the ex (they never had a path; AC-6 **[PRIV
L577–L578]**).

**Administrator — all private = DENY-403 / ciphertext-blind.** Two independent
controls stack. First, no admin action decrypts private content:

> "There is no admin action that decrypts private message content or birth
> coordinates for viewing. Any legitimate low-level access … is (a)
> app-encryption-blind (sees ciphertext) and (b) audited/alarmed on KMS `Decrypt`
> volume." — **[PRIV L797–L799]**

Second, envelope encryption means even direct DB access yields only ciphertext
because the DB never holds the key: "The database **never** holds a plaintext DEK
or the KEK." — **[PRIV L671]**. Admin is not positioned to approve agreements
(no membership slot), hence n/a there.

**Background job (arq) — shared write carries a FINDING.** Jobs inherit the
enqueuing actor's scope, and read paths run through the same `authorize()` +
export-time membership resolution (e.g. export "assembles data **within the
requester's authorization**" **[PRIV L899–L900]**; "Export runs through
`authorize()` exactly like any read" **[PRIV L893–L894]**). But no source states
that a job which **began before** an unpair re-validates membership at the moment
of **write**. See **AUTHZ-1** in §2.4 and §5.

**AI prompt builder (ContextBuilder) — cross-private = DENY (structurally
excluded).** The AI is the tightest-budgeted actor:

> "A `PRIVATE_A` task can never receive `PRIVATE_B` data and vice-versa. `SHARED`
> tasks receive only data with a valid ConsentEvent." — **[AI L1157–L1158]**

> "**Never the other partner's private data.** No task, ever, mixes one partner's
> private content into the other's context or into a shared context without a
> ConsentEvent covering exactly that projection." — **[AI L1159–L1161]**

> "The context assembler physically excludes any private-scope rows not covered by
> an active ConsentEvent." — **[PRIV L382–L384]** (INV-10). Guna/daily are handed
> only **derived labels**, never raw inputs: "The AI receives only derived,
> already-computed labels (nakshatra name, house number, Koota flags), never the
> inputs" — **[AI L1164–L1165]**.

**Support personnel — all private = DENY (no capability).** Not a policy toggle but
an absence of any code path:

> "**Support cannot reveal a user's private scope.** There is no support workflow
> that decrypts or displays private message content, private notes, or birth
> coordinates … support literally has no such capability." — **[PRIV L870–L872]**

### 1.2 Default-deny verdict on the matrix

Every populated cell resolves to an explicit `authorize()` branch (R0–R3) with no
fallthrough to ALLOW; RLS re-enforces the same predicate as a backstop **[DM
L726–L772]**. The **one** cell where the design does not clearly enforce
default-deny at the decisive moment is **Background job → Shared couple data at
write time** (matrix ⚠), recorded as **AUTHZ-1**. All other cells are sound.

---

## 2. PART 2 — Abuse-case tracing

### 2.1 AC — Partner A guesses Partner B private object IDs → **MITIGATED**

**Attack:** A enumerates/guesses opaque IDs (`bp_…`, `conv_…`, `msg_…`) hoping a
direct `GET` returns B's private row.

**Controls (quoted):** IDs are opaque and client-must-treat-as-opaque —
"opaque, prefixed, ULID-backed strings … Clients must treat them as opaque." —
**[API L76–L77]**. Even a correctly-guessed ID resolves through R1 to the
existence-hiding shape: "else: return DENY_NOT_FOUND" — **[PRIV L301]**; "Reading
someone else's `private/conversations/{id}` → `404`." — **[API L325]**. RLS is the
backstop — the owner-only policy `USING (user_id = current_setting('app.user_id'))`
**[DM L736, L739–L742]** returns zero rows regardless of the app layer. The 404 is
"deliberately indistinguishable from a nonexistent id" — **[API L895–L896]**.

**VERDICT: MITIGATED.** Opaque IDs + R1 scope guard + RLS backstop + uniform 404.

### 2.2 AC — Partner A asks AI whether Partner B uses private chat → **MITIGATED**

**Attack:** A uses an AI task, hoping the model's context or output confirms B's
private-chat activity ("does my partner journal about me?").

**Controls (quoted):** The context the AI receives never contains B's private rows:
"the context assembler physically excludes any private-scope rows not covered by an
active ConsentEvent. The AI cannot infer 'the other partner said X in private'
because that string never entered its context window." — **[PRIV L382–L384]**;
reinforced by **[AI L1159–L1161]** and the allow-list "Anything not listed is
dropped. Default deny." — **[AI L1154–L1155]**. Existence non-disclosure covers the
metadata channel too: "no endpoint returns a count, timestamp, 'last active in
private,' typing indicator, or unread badge scoped to the partner's private data."
— **[PRIV L532–L534]** (AC-2). Any scope-crossing attempt aborts and is audited as
`AI_SCOPE_VIOLATION` **[PRIV/AI L1476–L1477]**; prohibited task P9 "Automatic
disclosure of private info … Structurally impossible; attempt logged as
`AI_SCOPE_VIOLATION`" — **[AI L1127]**.

**VERDICT: MITIGATED.** Context minimization + existence non-disclosure + fail-closed
scope-violation abort.

### 2.3 AC — Private summary accidentally attached to shared conversation → **MITIGATED (with an integrity note)**

**Attack:** A private artifact reaches `SHARED` without a `ConsentEvent` — via a bug,
a bulk copy, or an errant `INSERT ... SELECT`.

**Controls (quoted):** The consent bridge is the *only* path, one-way, and DB-copy
is structurally blocked:

> "There is no ordinary DB copy path (INV-7): the `shared_chat` module cannot
> `INSERT ... SELECT FROM private_chat`. Cross-module raw SQL is blocked by the
> import-linter contract (DEC-002); the only supported route is
> `consent.project(consent_event) -> SharedArtifact`." — **[PRIV L505–L507]**

The schema enforces the integrity control the abuse case asks for: a
`SharedArtifact` **cannot exist without** a `ConsentEvent`, via a mandatory NOT NULL
FK with `ON DELETE RESTRICT`:

> "`consent_event_id UUID NOT NULL REFERENCES consent_event(id) ON DELETE RESTRICT`
> … **no SharedArtifact can exist without a ConsentEvent**." — **[DM L1025;
> L670–L671]**; ERD confirms the non-edge: "**absence of any edge from
> `PrivateMessage` to `SharedMessage`** — that non-edge is a security invariant"
> — **[DM L119–L121]**, and `pchat_message` "intentionally NO column referencing
> schat_message" **[DM L1044]**.

**Integrity verification (does a private artifact reach SHARED without a
ConsentEvent?):** No — the FK makes it impossible at the datastore, the import-linter
blocks the raw-SQL route at the code boundary, and `consent.project()` is the sole
constructor. This is the one genuine integrity control the abuse case demands, and
it is present at three layers (FK + linter + single constructor).

**VERDICT: MITIGATED.** The `NOT NULL consent_event_id` FK is the decisive integrity
control; a `SharedArtifact` without provenance cannot be inserted.

### 2.4 AC — Pair dissolved while a background job is running → **FINDING AUTHZ-1 (GAP)**

**Attack:** An arq job (daily-profile precompute sweep, async AI task, or export)
is enqueued while the couple is ACTIVE and reads/writes SHARED data. Between enqueue
and the job's write, either partner unpairs (membership → `revoked`,
**[DM L829–L832]**). The job then completes and writes into — or reads from —
SHARED scope **after** authorization was revoked.

**What the docs provide (quoted):** Only a *generic* conflict code and read-time
authorization:
- "409 | `CONFLICT` | State conflict / idempotency in-flight / version race." —
  **[API L306]** — a generic conflict, not a membership-revocation semantics.
- Export reads run "within the requester's authorization" **[PRIV L899–L900]** and
  "through `authorize()` exactly like any read" **[PRIV L893–L894]** — but this
  describes **read assembly**, and does not state that a *long-running* job
  re-checks membership at the moment it commits.
- Unpair is described as a single transaction over membership/artifacts
  **[DM L826–L834]** with "the guard denies SHARED on next request" **[DM L836]** —
  but an in-flight worker's write is **not** framed as "the next request," and no
  source binds the job's write to a fresh membership check inside the write
  transaction.

**Gap:** There is **no explicit design** for a job that *began before* unpair and
*writes after* it. The `authorize()` function is defined for request-time; the
`ScopeContext` is "constructed once per request, at TB-2" **[PRIV L261]** — a
worker sweep is not obviously a "request." Nothing states the worker re-resolves
`membership_status` (which INV-4 requires *per request*, **[PRIV L84]**) at write
time, nor that a post-unpair shared write is rejected. A daily-profile precompute is
USER-scoped and low-risk, but an **async AI task** or an **export** that materializes
a `SharedArtifact` or shared row after revocation is a real leakage/authorization
window.

**RECORD: FINDING AUTHZ-1 (GAP).** Severity **High**.

**Recommended control (spec addition):** Every background job must **re-validate
couple membership / scope at the moment of WRITE**, not merely at enqueue, **inside
the same transaction** as the write. Concretely: (a) jobs carry their originating
`ScopeContext` (actor, couple_id, expected slot); (b) before any SHARED write the
worker re-resolves `couple_membership.status` and aborts if not `ACTIVE`; (c) an
aborted job appends an audit event (`action=job_aborted_membership_revoked`) and
performs no partial write; (d) shared writes are unconditionally rejected
post-unpair; (e) USER/PRIVATE-scoped writes (e.g. own daily profile) remain valid
since they do not depend on membership. Add proving tests
`test_inflight_job_revalidates_membership_on_write` and
`test_unpair_during_export_rejects_shared_write` to the test plan referenced at
**[PRIV L997–L999]**.

### 2.5 AC — Shared agreement references deleted private source content → **FINDING AUTHZ-2 (PARTIAL)**

**Attack:** A `SharedArtifact` (or an agreement built from one) points back into the
private source. The granter later deletes the private message, or crypto-shred on
account deletion destroys the private DEK. The shared side either breaks (dangling
read) or, worse, re-exposes/leaks on a later access.

**What the docs state (quoted, in favor of self-containment):**

> "The projected payload is **materialized once** into the `SharedArtifact` and
> decoupled from the private source. Editing or appending to the private
> conversation afterward does **not** change what was shared — no live view, no
> trailing pointer." — **[PRIV L495–L497]**

> "It stores the projected text (or rollup), never a live handle back into the
> private stream." — **[PRIV L426–L427]**

Agreements themselves are self-contained SHARED rows: `agree_agreement.title/body`
are authored directly in SHARED scope **[DM L487–L489]**, not pointers into private
content, and unpair leaves private data untouched **[DM L852–L855]**.

**What is under-specified (the tension):**
1. The data model calls `SharedArtifact.content_ref` a **"ref to bounded projection
   (not raw private stream)"** — **[DM L398, L1024]** — the word *ref* is a pointer,
   not obviously an inline immutable snapshot. The privacy doc says the *text* is
   stored **[PRIV L426–L427]**, but the schema field is a `TEXT` **ref**, leaving
   *where the projected bytes live* and *what deletes them* unstated.
2. **Encryption-class mismatch.** The privacy doc says the SharedArtifact projected
   payload is "Encrypted under the **couple DEK**" **[PRIV L691]** — which would
   survive private-source crypto-shred (that destroys the *per-user* DEK, **[PRIV
   L678–L679]**). But the data model classifies `content_ref` as **SENSITIVE**
   (disk-encrypted only), **not** HIGHLY-SENSITIVE app-enc **[DM L398; L695]**.
   The two documents disagree on how (and under which key) the crossed bytes are
   stored, so "private-source deletion never re-exposes / never breaks shared" is
   **not** provable from a single consistent statement.
3. No source explicitly says "deleting the private source **never cascades** to the
   SharedArtifact and **never re-exposes** private content." It is strongly implied
   by "materialized once / decoupled" but never asserted as an invariant with a
   deletion-path test.

**RECORD: FINDING AUTHZ-2 (PARTIAL).** Severity **Medium**.

**Recommended control (spec addition):** State explicitly that `SharedArtifact`
stores an **immutable snapshot** of the projected bytes captured at consent time
(the `bounded_summary_hash`/`content_ref` computed over *those* bytes, per **[PRIV
L501–L503]**), encrypted under the **couple DEK** so it is independent of the
granter's per-user DEK. Assert as an invariant: **private-source deletion (row
delete or crypto-shred) never cascades to a `SharedArtifact` and never re-exposes
private content**; the frozen artifact persists for audit only **[PRIV L429–L432]**.
Reconcile the `content_ref` encryption class between **[DM L398]** (SENSITIVE) and
**[PRIV L691]** (couple-DEK app-enc) — they must name the same key and tier. Add
`test_shared_artifact_survives_private_source_deletion` and
`test_shared_artifact_is_snapshot_not_pointer`.

### 2.6 AC — Account compromise on a shared device → **MITIGATED / PARTIAL**

**Attack:** ADV-4/ADV-10 with physical access to an unlocked or left-open device, or
a phished credential, tries to read the victim's private scope.

**Controls (quoted):** Server-side revocable sessions — "Any session is revocable
immediately … revocation takes effect within one access-token lifetime at most,
instantly for refresh." — **[PRIV L830–L831]**; short ES256 JWT (10 min) + rotating
opaque refresh **[PRIV L826–L828]**, **[API L124–L125]**. Refresh-reuse detection
"revokes the entire session family (`AUTH_REFRESH_REUSE`)" **[API L159, L299]**.
Biometric/PIN re-auth gates private sections even when the app is open: "entering
private chat or private notes requires a fresh biometric/PIN even if the app is
open; a short inactivity timeout re-locks private sections automatically." — **[PRIV
L637–L640]**. Password reset does **not** immediately unlock private scope: "A
password reset re-establishes *authentication* but triggers a **private-scope
recovery lock**" — **[PRIV L857–L860]**. Notification previews are generic **[PRIV
L610–L613]**, and app-switcher snapshots are obscured **[PRIV L646–L648]**.

**Residual (why PARTIAL for the physical-coercion sub-case):** The design honestly
concedes it cannot stop real-time on-screen viewing under physical compulsion: "We
cannot prevent a screenshot of content the user is actively viewing — this is
documented as a residual risk" — **[PRIV L544–L545, L986–L990]**.

**VERDICT: MITIGATED for credential/session compromise; PARTIAL for real-time
physical coercion** (residual risk, honestly disclosed and minimized).

### 2.7 AC — Notification reveals sensitive content → **MITIGATED**

**Attack:** ADV-4 reads the lock-screen/notification tray to learn message content,
sender, or astrology detail.

**Controls (quoted):** Generic-by-default previews (INV-15): "Default push text is
generic: **'DilChat: You have a new update.'** No sender name, no message excerpt …
including on the lock screen." — **[PRIV L611–L613]**. The sensitive payload is not
in the push at all: "Push payloads carry only an opaque `notification_id` + type +
generic title. The client authenticates, then calls the API to retrieve the actual
content, which is authorized through `authorize()`." — **[PRIV L629–L631]**. The
default is safe by schema: `users_preferences.notification_privacy … DEFAULT
'hidden'` — **[DM L184]**. Private-scope notifications can *never* be upgraded to
show content on the lock screen **[PRIV L621–L623]**.

**VERDICT: MITIGATED.** Previews hidden by default; no sensitive content in the push
transport; safe default persisted in schema.

### 2.8 AC — AI provider receives unauthorized context → **MITIGATED (with legal-review caveat)**

**Attack:** ADV-7 (compromised/misconfigured provider) receives, and could
reconstruct, unshared private data or cross-partner content.

**Controls (quoted):** Context minimization is the primary control — allow-list per
task, scope isolation, no other partner's private data, no raw coordinates, no
durable IDs **[AI L1154–L1170]**; the envelope "carries **no** raw coordinates,
**no** durable IDs, **no** other partner's private data" — **[AI L1185–L1186]**.
Provider terms: "The provider must offer **zero-retention / no-training** API
terms for user content (DEC-014, OQ-12)." — **[AI L1482–L1483]**; and "DilChat does
not use user content to train or fine-tune any model." — **[AI L1486–L1487]**.
STRIDE control at TB-5: "Zero-retention/no-train contract (DEC-014); send only
authorized, minimized context (INV-10)." — **[PRIV L222]**. Prompt-injection
exfil is contained: "Structured governed inputs only … output schema validation; AI
cannot address the *other* scope; no tool that reads private scope." — **[PRIV L223]**.

**Legal-review caveat (quoted):** The zero-retention term is **not yet
contractually confirmed**: "Until contractually confirmed and recorded, this is
**[Requires legal review]**." — **[AI L1483–L1485]**. The provider is treated as
"semi-trusted at best" **[PRIV L146–L149]**, so the *technical* control (we never
send unshared/cross-partner data) does not depend on the provider honoring terms.

**VERDICT: MITIGATED** on the technical channel (minimization means little of value
is ever sent), **with a standing [Requires legal review] caveat** that the
zero-retention/no-train contract be executed and recorded before GA.

---

## 3. PART 3 — Default-deny verification of `authorize()` and endpoint classes

### 3.1 The decision function defaults to deny

Confirmed: `authorize()` is "Pure function, no side effects, default-deny" **[PRIV
L288]** with an explicit terminal `R3 default: return DENY_FORBIDDEN   # INV-3
default deny` **[PRIV L307]** and the stated rule "Ordered rules; first match wins.
No fallthrough to ALLOW." **[PRIV L296]**. Every non-matching path therefore denies.
The repository layer mirrors this ("Repositories reject any query lacking a
`ScopeContext`" **[DM L789]**; "a query without a resolved scope is refused by the
repository layer" **[API L173–L174]**), and RLS is a forced backstop with no
permissive policy by default **[DM L731]**. The denial-shape is correctly bifurcated
into 404 (existence-hiding) vs 403 (existence-known) per the quick-reference table
**[PRIV L1053–L1061]**. **This portion is SOUND.**

### 3.2 Endpoint-class scope-check review

Walking the endpoint inventory **[API §6, L389–L577]** against the authorization
matrix **[API L182–L221]**:

| Endpoint class | Scope stated | Explicit check present? |
|---|---|---|
| `identity` auth/session/devices | public / self | Yes — public routes flagged; self routes "own sessions/account only" **[API L402–L410]** |
| `users` (`/me`, export, delete) | self | Yes — "own account" **[API L193]** |
| `birth_profiles` | self/PRIVATE | Yes — "owner only; **404** for others" **[API L195, L323]** |
| `astrology` charts | self/PRIVATE | Yes — "owner only" **[API L196]** |
| `guna_milan :preview` | self/PRIVATE | Yes — "single user, PRIVATE, no couple" **[API L197]** |
| `guna_milan` shared scorecard | SHARED | Yes — "membership re-checked" **[API L198]** |
| `moon_transits` `/me/daily` | self | Yes — "owner's transit profile" **[API L199]** |
| `moon_transits` climate | SHARED | Yes **[API L200]** |
| `couples` invitations/unpair | self / SHARED | Yes — accepter ≠ inviter; unpair either member **[API L202–L203]** |
| `consent` grants/:grant/:revoke | either / owner / grantor | Yes — ":grant … **only the data owner**" **[API L205–L206]** |
| `private_chat` | PRIVATE (own) | Yes — "strictly PRIVATE_A **or** PRIVATE_B (own)" **[API L207]** |
| `shared_chat` | SHARED | Yes **[API L208]** |
| `journeys` | SHARED (templates: self) | Yes **[API L209, L521–L524]** |
| `agreements` create/submit/commit | SHARED | Yes **[API L210, L530–L536]** |
| `agreements :approve` | both (dual) | Yes — dual approval **[API L211, L533]** |
| `ai_guidance` | self / either / SHARED / PRIVATE | Yes — "scope depends on inputs supplied" **[API L212, L553–L557]** |
| `feedback` POST | PRIVATE | Yes — "private input" **[API L213]** |
| `living-compatibility` GET | SHARED | Yes — "aggregate only" **[API L214, L564–L566]** |
| `audit` `/me/audit` | self | Yes — "user-visible subset only" **[API L216, L575–L576]** |

**No endpoint class in the published inventory lacks an explicit scope
declaration.** Every row of §6 carries a `Scope` column and every representative
endpoint in the authorization matrix **[API L189–L216]** carries an explicit
principal set. **This portion is SOUND** at the HTTP contract layer.

### 3.3 The one class the request-time verification does not cover

The `authorize()` proof is a **request-time** proof. The **background-worker write
path** is the endpoint-analog that is *not* covered by a stated per-write scope
check — it is the runtime manifestation of **AUTHZ-1**. This is flagged, not as a
missing HTTP endpoint, but as a missing enforcement point at the worker→datastore
boundary. All *synchronous* endpoint classes are covered.

---

## 4. Cross-document consistency observations (non-blocking unless noted)

1. **`SharedArtifact.content_ref` key/tier mismatch** — SENSITIVE **[DM L398]** vs
   couple-DEK app-enc **[PRIV L691]**. Feeds **AUTHZ-2**; must be reconciled.
2. **"Request" vs "worker"** — `ScopeContext` is "per request" **[PRIV L261]** and
   INV-4 re-checks membership "on every … request" **[PRIV L84]**; the worker is not
   defined as a request. Feeds **AUTHZ-1**.
3. **Guna preview scope label** — `guna_report.id` marked `SHARED*` with a
   USER-preview fallback when `couple_id NULL` **[DM L246–L247, L263–L264]**; the RLS
   policy correctly handles both arms **[DM L762–L768]**. Consistent; noted for
   reviewers because the same row type spans two scopes.
4. **Positive:** immutability of `guna_report`/`astro_natal_chart`/`consent_event`/
   `audit_event` is enforced by *both* trigger and RLS omission **[DM L775–L776,
   L983–L984, L1015–L1016, L1065–L1066]** — belt-and-suspenders, as claimed
   **[PRIV L67]**.

---

## 5. Findings table & overall verdict

| ID | Finding | Severity | Status | Enforcing/absent control | Recommended control |
|---|---|---|---|---|---|
| **AUTHZ-1** | In-flight arq job (daily-profile precompute, async AI, export) that began before unpair may write to / read SHARED after membership is revoked; docs give only a generic `409 CONFLICT` **[API L306]** and request-time `authorize()` **[PRIV L288]**, with no per-write re-validation. | **High** | **GAP** | *Absent:* no write-time membership re-check inside the job's write transaction; `ScopeContext` is defined "per request" **[PRIV L261]**, not per worker write. | Every job re-validates couple membership/scope at WRITE (not enqueue), in the same transaction; job carries scope context; abort+audit if membership revoked; SHARED writes rejected post-unpair; USER/PRIVATE writes unaffected. Tests: `test_inflight_job_revalidates_membership_on_write`, `test_unpair_during_export_rejects_shared_write`. |
| **AUTHZ-2** | Self-containment of `SharedArtifact` vs deleted private source is under-specified: `content_ref` is a "ref" **[DM L398]**, encryption tier disagrees with **[PRIV L691]**, and no invariant asserts deletion never cascades/re-exposes. | **Medium** | **PARTIAL** | *Present but incomplete:* "materialized once … decoupled … no trailing pointer" **[PRIV L495–L497]**; *missing:* explicit snapshot + independent-key + no-cascade invariant. | SharedArtifact stores an immutable snapshot at consent time, encrypted under the couple DEK (independent of granter per-user DEK); assert private-source deletion never cascades and never re-exposes; reconcile `content_ref` tier. Tests: `test_shared_artifact_survives_private_source_deletion`, `test_shared_artifact_is_snapshot_not_pointer`. |
| **AUTHZ-3** | Zero-retention / no-training provider contract is asserted but **not yet executed** — "**[Requires legal review]**" **[AI L1483–L1485]**. Technical minimization already limits exposure. | **Low** | **PARTIAL (open dependency)** | *Present:* context minimization **[AI L1154–L1186]**, provider treated semi-trusted **[PRIV L146–L149]**; *pending:* signed contract. | Execute and record the zero-retention/no-train DPA before GA; keep the adapter's retention/training-disable flags set **[AI L1484–L1485]**. |
| **AUTHZ-4** | Doc-consistency: `content_ref` encryption class conflict (SENSITIVE vs couple-DEK app-enc). | **Low** | **PARTIAL** | Conflicting statements **[DM L398]** / **[PRIV L691]**. | Single authoritative statement of the key and tier for crossed bytes (folds into AUTHZ-2). |

### 5.1 What is affirmatively SOUND

- **Three-scope isolation (INV-1/INV-9):** cross-private returns uniform `DENY_404`,
  `PRIVATE_OTHER` is unrepresentable, timing is uniform **[PRIV L300–L301, L283–L284,
  L323–L328]**. Verified across matrix rows and AC-1/AC-2.
- **Existence non-disclosure:** 404-vs-403 bifurcation is correct and tested-invariant
  **[API L315–L329]**, **[PRIV L1053–L1061]**.
- **Consent-gated projection (INV-6/INV-7):** `NOT NULL consent_event_id` FK + import
  linter + single `consent.project()` constructor make an unconsented SharedArtifact
  structurally impossible **[DM L1025, L670–L671]**, **[PRIV L505–L507]**. This is the
  strongest single control in the design.
- **Immediate unpair revocation (INV-5):** one-transaction membership flip severs
  SHARED reachability at request time **[DM L829–L836]**.
- **Default-deny at three layers:** `authorize()` R3, repository refusal, forced RLS
  **[PRIV L307]**, **[DM L789, L731]**.
- **AI as tightest-budgeted actor (INV-10/INV-11):** physical context exclusion,
  no auto-send, no impersonation **[PRIV L382–L388]**, **[AI L1515–L1517, L1533–L1536]**.
- **Notification & shared-device privacy (INV-15):** safe default persisted in schema
  **[DM L184]**, no sensitive push payload **[PRIV L629–L631]**.
- **Admin/support cannot reach plaintext private scope:** capability-absence +
  ciphertext-blindness **[PRIV L797–L799, L870–L872]**.

### 5.2 Overall verdict

**AUTHZ_SOUND_WITH_FINDINGS.**

The three-scope model, existence non-disclosure, and consent gating are strong,
internally reinforcing, and enforced at multiple independent layers (app guard, RLS,
schema FK, import-linter). The design earns its default-deny claim on every
synchronous access path examined. Two findings must be closed **in the spec before
Phase D implementation**: **AUTHZ-1 (GAP, High)** — bind every background-job write to
a fresh, in-transaction membership/scope re-validation so an unpair mid-job cannot
produce a post-revocation shared write; and **AUTHZ-2 (PARTIAL, Medium)** — assert the
`SharedArtifact` snapshot/independent-key/no-cascade invariant and reconcile the
`content_ref` encryption tier. AUTHZ-3 (provider DPA) and AUTHZ-4 (doc consistency)
are lower-severity open dependencies. None of the findings undermine the core
invariants; they close under-specified edges at the worker→datastore and
deletion→projection boundaries.

---

*End of audit. Design-phase verification only; no production code implied or
authored. This document verifies and cites the DilChat privacy, data-model, API, and
AI-integration specifications and records findings against them.*
