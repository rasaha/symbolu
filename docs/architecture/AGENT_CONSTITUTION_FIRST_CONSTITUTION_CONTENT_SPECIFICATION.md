# Agent Constitution — the first constitution's content ballot

**Status: proposal — documentation only. Nothing here is ratified, no constitution
is issued, and no implementation is authorized by it.** The analysis was performed
read-only: it modified no production source, test, package metadata,
`public_api.json`, `version.py`, CI workflow or platform-freeze artifact, and this
document is the only file its change set adds. The five owner decisions in §5 are
**open**; §6 is the ballot that would settle them.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `f5edbec9765c6768fd14ff167b37173bcfdff5a8` — which **is** the merge commit of
PR #1530, the `OD-C1=B` amendment change set. Every `[V]` claim below is
verifiable against that head.

**Governing scope.** The first-slice record leaves exactly this open: *"the
constitution's substantive clause content beyond the three structural bounds, and
who authors the first constitution"*
(`ADR_UGENCE_AGENT_CONSTITUTION_FIRST_SLICE_RATIFICATION.md:226-227`). This
document convenes the ballot for the first constitution's **content on the
ratified `/clauses/v1` vocabulary** and its **authorship**. It designs within
every standing ruling, reopens none, and assigns **no** new `OD`, `S2B-*`, `P`,
`RCG-D`, `ACC-S1` or `ACC-AM` number; ballot rows are labeled `FC-1` – `FC-5`,
proposal-local, register labels the ratification ADR's to assign on the standing
precedent.

**Load-bearing question, answered first.** This ballot settles the first
constitution's **complete field-level content** — identity, scope, the governed
role list, and the three structural bounds that are the whole of the `/clauses/v1`
clause vocabulary — and **who authors it**. It deliberately does **not** issue
anything: issuance is a deployment act requiring a signing key, configured trust
roots and external approval evidence, none of which a repository file may lawfully
contain (§4). And it does **not** ratify clause content beyond the three
structural bounds: that requires a `/clauses/v2` vocabulary round, which this
ballot leaves un-commissioned — so the `ACC-AM-4` re-derivation re-arm condition
is **not** triggered by anything here.

**Evidence labels.** `[V]` verified against this repository at the cited
`file:line` or the named basis; `[I]` architectural inference; `[R]` owner ruling
required; `[G]` unresolved gap.

> *This specification changes **no** production source, test, package metadata,
> CHANGELOG, `public_api.json`, `version.py`, CI workflow or platform-freeze
> artifact. `[V]` The substantive freeze digest was recomputed in this session
> and is unchanged, all checks PASS:
> `d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`.*

---

## 0. Baseline verification

| Check | Result |
|---|---|
| Default-branch head | `[V]` `f5edbec9765c6768fd14ff167b37173bcfdff5a8` — exact match; the working tree was verified clean |
| The whole `ACC-S1-Q5` sequencing merged | `[V]` ratification ADR (PR #1522), both distributions (PRs #1524/#1525), the amendment round (PR #1526) and its change set (PR #1530, `051d3b78`) are all ancestors of the head |
| Agentic Proposer | `[V]` `0.4.0`, 51 public names; the role surface bears required `constitution_ref` and the advisory binds the constitution pair (`ACC-AM-1`/`ACC-AM-2`) |
| Constitution distributions | `[V]` both at `0.1.0`; the family refuses to construct any artifact departing from the §2 shape, and the conformance predicate is the §3 check |
| Clause vocabulary | `[V]` `ugence.agent-constitution/clauses/v1`, fixed by `ACC-S1-Q1`; its members are exactly the three structural bounds |
| Substantive freeze digest | `[V]` recomputed via `python -m platform_freeze.verify`: PASS, `d9930935…fac036`, unchanged |

**No baseline mismatch. Proceeding.**

---

## 1. What "the first constitution's content" can lawfully mean today

`[V]` The ratified `/clauses/v1` vocabulary carries exactly three clauses, all
structural: `permitted_candidate_dispositions_bound`,
`permitted_review_actions_bound` and `permitted_tool_scopes_bound`
(`packages/integration/agent-constitution-policy/src/ugence_agent_constitution_policy/policy.py`,
the §2.3 surface `ACC-S1-BASE` fixed). The family's constructor refuses any other
shape: no free-text clause, no obligation, no procedure, no value statement is
representable, and `constitution_vocabulary_version` must equal the `v1` constant
exactly. `[I]` The first constitution's "clause content" is therefore its
**values**: which roles it governs, and where the three ceilings sit. Anything
richer is a `/clauses/v2` question — a digest-moving vocabulary change requiring
its own design round, deliberately not commissioned here (§5, `FC-5`).

**Never, in this ballot** (each prohibition stated once): no clause beyond the
three structural bounds is ratified; no constitution is issued, signed or
registered; no signing key, trust root or approval evidence enters the
repository; no role is minted, activated or changed (`OD-C4=A`); no verifier
disposition is created (`OD-C3=B`); no package changes; and the absent
`UGENCE_AGENT_CONSTITUTION_AND_CONFORMANCE_INITIAL_DESIGN_SPEC_v0.1` name is not
claimed.

---

## 2. The proposed content, field by field

The table is the ballot's substance: `FC-2`, `FC-3` and `FC-4` ratify or return
its rows. Grammar and ordering constraints are the family's own and are enforced
at construction, so a ratified value that violated one could not be built —
none below does.

| Field | Proposed value | Basis |
|---|---|---|
| `policy_id` | `agent-constitution-ugence` | C5b `Token`; the id names the constitution, not its version |
| `version` | `1.0.0` | C5b; a string, never a number |
| `agent_constitution_ref` | `ugence.agent-constitution/ugence/baseline/v1` | C5a; the signed reference roles will carry in `constitution_ref`, and the conformance resolver's fourth post-check compares |
| `scope` / `tenant_id` | `GLOBAL` / the canonical empty tenant | `[I]` no production tenant exists yet; a tenant-scoped first constitution would name a tenant nothing operates. A later tenant constitution is a new issuance, not an edit |
| `lifecycle_state` | `APPROVED_ACTIVE` at issuance | the only resolvable state |
| `effective_from` / `effective_to` | the issuance instant / `None` | stated as a **rule**: the window opens at issuance and is unbounded until superseded or revoked; the instant itself is an issuance-time fact, not a ballot value |
| `governed_role_refs` | `("ugence.roles/ugence/invoice-reconciler/v1",)` | `FC-3`; see §3 |
| `permitted_candidate_dispositions_bound` | `("ESCALATE_EXCEPTION", "RECOMMEND_MATCHED_FOR_APPROVAL", "RECOMMEND_WITHHOLD", "REQUEST_EVIDENCE")` | `FC-4`; the full ratified closed vocabulary, ascending |
| `permitted_review_actions_bound` | `("CREATE_EXCEPTION_REVIEW_BUNDLE", "ROUTE_APPROVAL_BUNDLE")` | `FC-4`; the full ratified closed vocabulary, ascending |
| `permitted_tool_scopes_bound` | `("invoice.read", "ledger.read")` | `FC-4`; the MVP reconciliation scenario's two read scopes, ascending — the one bound with real bite today |
| `constitution_vocabulary_version` | `ugence.agent-constitution/clauses/v1` | fixed by `ACC-S1-Q1`; not a ballot value |

**Where the bite is, disclosed plainly.** `[I]` The two closed bounds proposed at
their full vocabularies exclude nothing **today**: they become binding the day
either enum gains a member, since the bound is digest-frozen while the vocabulary
may grow. The genuine constraints the first constitution imposes are the
**membership check** — exactly one governed role; every other role fails
resolution's signed-side binding and the predicate's first clause — and the
**tool-scope ceiling**: a role declaring any scope beyond the two read scopes
does not conform. A reconciliation role that needs `invoice.write` is a new
constitution version, deliberately.

---

## 3. The governed role, and what naming it does not do

`[R]` `FC-3` proposes one governed role reference,
`ugence.roles/ugence/invoice-reconciler/v1` — the invoice-reconciliation role the
MVP scenario centres on. Minted here as a **reference**, on the C5a discipline:
an opaque handle, carried and compared whole.

`[G]` **Disclosed honestly, three ways.** No role artifact bearing this
reference exists in this repository — roles are externally issued input facts,
and none has been issued. The `(tenant_id, role_contract_ref)` reference-map
population that would route this role to its constitution remains ungoverned,
carried unchanged from the scoping ADR. And naming the role governs it only once
a constitution is actually issued and resolved: ratifying this list is a
statement of intent with a signed future, not present governance of anything.

---

## 4. Why issuance is not this ballot's to perform

`[V]` Issuance requires an Ed25519 signing key, configured trust roots, and
external approval evidence checked by an always-supplied approval verifier —
and the shipped default refuses everything: permissive verifiers exist under
`tests/` only, asserted by packaged scans in both constitution distributions.
`[R]` A repository file may lawfully contain **none** of these: a committed
private key is a compromised key, and an in-repo "issued" constitution would be
exactly the self-authenticated artifact the whole design refuses. `[I]` The
first issuance is therefore a **deployment act**, gated on trust configuration
that does not exist yet: key custody, an approving authority, a composition
root, and reference-map population. `FC-5` sequences it without performing it.

---

## 5. Owner-decision register (five)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| FC-1 | Authorship | the repository owner authors the first constitution personally; the ratification ADR records the authorship as an owner act | the owner commissions another author; the ballot returns until one is named |
| FC-2 | Identity and scope | the §2 identity rows whole: id, version, reference, `GLOBAL` scope, the effective-window rule | return the rows; owner supplies values under the same grammars |
| FC-3 | Governed roles | exactly one: `ugence.roles/ugence/invoice-reconciler/v1`, with §3's disclosures | owner supplies a different list, same disclosures required |
| FC-4 | The three bounds | full closed vocabularies for dispositions and review actions; tool scopes `{invoice.read, ledger.read}` — the §2 bite disclosure accepted | owner supplies narrower or different sets, ascending and in-vocabulary |
| FC-5 | Issuance and the v2 round | content is ratified now, documentation-only; first issuance is a deployment act gated on key custody, an approving authority, a composition root and reference-map population — each raised, none performed; the `/clauses/v2` vocabulary round is **not** commissioned, and `ACC-AM-4`'s re-arm stays untriggered | also commission the `/clauses/v2` scoping round now, as its own ballot |

Couplings, disclosed: `FC-2` and `FC-3` interact only through the reference the
governed role's future `constitution_ref` must equal — both sides of that
equality come from this one table, so ratifying the table whole keeps them
consistent by construction. `FC-4=B` with narrower disposition bounds would make
some lawful advisory flows non-conforming for the governed role; that is a
legitimate owner choice, not an error, and is why the row exists. No other pair
interacts. The fixed surface (§1's vocabulary confinement and §4's issuance
posture) is put to ratification whole alongside the rows, with the standing
precedence rule: where an `FC` row and the fixed surface overlap, **the `FC`
ruling governs**.

---

## 6. Paste-ready owner-ratification ballot

```
Agent Constitution — first-constitution content ballot
Baseline: rasaha/symbolu default head f5edbec9765c6768fd14ff167b37173bcfdff5a8
Governed by OD-C1..OD-C5, ACC-S1-* and ACC-AM-* as ratified. Answer each with A or B.
A = the recommended path.

CONTENT_SURFACE  Ratify the fixed surface: the first constitution's clause content is
      confined to the ratified /clauses/v1 vocabulary (the three structural bounds,
      nothing richer representable); no constitution is issued by this round; no
      signing key, trust root or approval evidence enters the repository; the
      /clauses/v2 question is out of scope unless FC-5=B — with the precedence rule:
      where an FC row and this surface overlap, the FC ruling governs.  YES/NO.

FC-1  Authorship.
      A = the repository owner authors the first constitution personally; the
          ratification ADR records it as an owner act.
      B = the owner commissions another author; the ballot returns until named.

FC-2  Identity and scope (§2, arrive together).
      A = policy_id agent-constitution-ugence; version 1.0.0; agent_constitution_ref
          ugence.agent-constitution/ugence/baseline/v1; GLOBAL scope with the
          canonical empty tenant; effective window opening at issuance, unbounded.
      B = return the rows; the owner supplies values under the same grammars.

FC-3  Governed roles.
      A = exactly one: ugence.roles/ugence/invoice-reconciler/v1, with the §3
          disclosures (no role artifact exists; the reference map stays ungoverned;
          governance begins at issuance and resolution, not at ratification).
      B = the owner supplies a different list, same disclosures required.

FC-4  The three bounds (the /clauses/v1 content).
      A = dispositions bound = the full ratified closed vocabulary (4 members);
          review-actions bound = the full ratified closed vocabulary (2 members);
          tool-scopes bound = {invoice.read, ledger.read} — accepting §2's
          disclosure that the closed bounds bite only as the vocabularies grow and
          the tool-scope ceiling and role membership are today's real constraints.
      B = the owner supplies narrower or different sets, ascending, in-vocabulary.

FC-5  Issuance sequencing and the v2 round.
      A = content ratified documentation-only; first issuance is a deployment act
          gated on key custody, an approving authority, a composition root and
          reference-map population — each raised as a gap, none performed here; the
          /clauses/v2 vocabulary round is not commissioned and ACC-AM-4's re-arm
          condition stays untriggered.
      B = additionally commission the /clauses/v2 scoping round now, on its own
          ballot.

Record as: CONTENT_SURFACE=? FC-1=? FC-2=? FC-3=? FC-4=? FC-5=?
No issuance and no implementation is authorized by this ballot; register labels and
any later authorization belong to the ratification ADR that records these answers.
```

---

## 7. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: f5edbec9765c6768fd14ff167b37173bcfdff5a8
Artifact under review: docs/architecture/AGENT_CONSTITUTION_FIRST_CONSTITUTION_CONTENT_SPECIFICATION.md

Verify the baseline first (head, clean tree, the full ACC-S1-Q5 sequencing merged through
PR #1530, proposer 0.4.0/51, both constitution distributions 0.1.0, freeze digest
d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036 unchanged); stop on
mismatch. Then judge against the repository, not this document's prose:

1. Is every proposed §2 value constructible by the family exactly as stated — grammars,
   ordering, vocabulary membership — and is the claim that /clauses/v1 admits nothing
   richer than the three bounds accurate against the family's constructor?
2. Are the two enum bounds genuinely the full ratified vocabularies, and is the "where
   the bite is" disclosure honest — including that full closed bounds exclude nothing
   today?
3. Are the §3 and §4 disclosures accurate: no role artifact exists, the reference map is
   ungoverned, issuance requires key custody / approval / trust configuration absent from
   the repository, and permissive verifiers live under tests/ only?
4. Does anything here issue, sign, or self-authenticate a constitution; trigger
   ACC-AM-4's re-arm; ratify clause content beyond the bounds; or violate OD-C3=B or
   OD-C4=A?
5. Are the five FC rows genuinely open decisions with defensible recommendations, and is
   anything described as implemented, issued, settled or ratified that is not?
Return SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, findings cited to file:line.
```

---

## 8. Readiness verdict

**READY_FOR_OWNER_RATIFICATION.** Baseline verified in full; the substantive
freeze digest is unchanged; five owner decisions plus the fixed-surface question
are open, and none is settled here. Next steps after ratification: the
ratification ADR recording the answers and assigning register labels; then —
outside this repository's files — the deployment work `FC-5` sequences: key
custody, an approving authority, a composition root, reference-map population,
and the first genuine issuance, at which point the invoice-reconciler role's
`constitution_ref` has a signed value to equal and the conformance replay has a
live constitution to answer against.
