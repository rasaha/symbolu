# Agent Constitution — family supersession opt-in, implementation-authority ballot

**The load-bearing question:** `ACC-SU-1` – `ACC-SU-5` say what the opt-in must
be; can it be built inside the surface they set? **Almost — one ratified phrase
does not survive the consumer enumeration `ACC-SU-4` demanded, and this ballot
exists so the owner settles that rather than an implementer settling it in CI.**

`ACC-SU-4` ruled that `agent-constitution-policy` moves and that "the conformance
and activation distributions and the Policy Authority are **untouched**". `[V]`
Both of those distributions' offline verify scripts assert
`family.__version__ == "0.1.0"`, and both run in CI. The ratified minor bump
therefore breaks two distributions the same row calls untouched. `SU-IA-4` puts
that to the owner.

**Status:** implementation-authority ballot — documentation only. **No source
change is authorized until this ballot is answered and its ruling merges.**
**Date:** 2026-08-31.

**Governing record:**
[`ADR_UGENCE_AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_RATIFICATION.md)
(`ACC-SU-BASE`, `ACC-SU-1` – `ACC-SU-5`). `[R]` This ballot **refines**, and may
not overrule, those rulings: where a row below and an `ACC-SU` ruling conflict,
the `ACC-SU` ruling governs and the row is void.

---

## 0. Baseline, and the consumer enumeration `ACC-SU-4` requires

`[V]` Default branch head `7015dec2`, clean working tree — the merge of PR
#1552, which ratified this round. `[V]` Policy Authority `0.2.0`; all three
constitution distributions `0.1.0`; the family exposes 27 public names.

`ACC-SU-4` obliges this ballot to **open** by enumerating every consumer of the
family's artifact shape and closed vocabularies, harnesses included, before
bounding any surface. That enumeration, run this session:

| # | Consumer | Effect of the change | Verdict |
|---|---|---|---|
| 1 | `agent-constitution-conformance/tests/_constitution_conformance_fixtures.py:83` and `agent-constitution-activation/tests/_activation_fixtures.py:173` | construct metadata as `AgentConstitutionPolicyMetadata(**fields)` from explicit dicts | `[V]` **unaffected** by an optional, defaulted field |
| 2 | the two dependent **verify scripts** (`…conformance…:105`, `…activation…:105`) | each asserts `family.__version__ == "0.1.0"`; both run in CI (`agent-constitution-ci.yml:121,127`) | `[G]` **breaks on the ratified bump** — see `SU-IA-4` |
| 3 | `agent-constitution-policy/public_api.json` | records the metadata dataclass's **field list and order**; a new field grows it | `[V]` must be regenerated; the family's surface grows |
| 4 | `agent-constitution-policy/tests/test_public_api.py:69` | asserts `package_version == family.__version__ == "0.1.0"` | `[V]` in-package; moves with the bump |
| 5 | `agent-constitution-policy/tests/test_authority_registration.py:181-190` | asserts the canonical projection's metadata keys are **exactly** the eight current names | `[V]` **stays green unedited iff the new field is excluded** — it *is* the `ACC-SU-2` guard |
| 6 | `agent-constitution-policy/tests/test_artifact.py:405` — `test_every_body_field_moves_the_digest` | parametrized over body fields that must move the digest | `[V]` the new field must **not** be added: by `ACC-SU-2` it does not move the digest |
| 7 | platform-freeze manifest | covers `packages/providers/*` only | `[V]` **does not reach** this family |
| 8 | external version pins on the family | none outside the two verify scripts at row 2 | `[V]` closed |

`[R]` No other consumer exists. `[I]` Rows 5 and 6 are the pleasant surprise:
the repository **already** guards `ACC-SU-2` — one test pins the projection's key
set closed, another pins which fields move the digest. Neither needs writing;
both need leaving alone, and editing either would be the tell that the exclusion
had been abandoned.

Facts the design leans on, also verified at this head:

* `[V]` The family already imports `PolicyCoordinate` from
  `ugence_policy_authority.api` and builds one in
  `agent_constitution_coordinate` (`adapter.py:41,60,75`), so carrying that type
  on the metadata introduces no new dependency and no parallel identity notion.
* `[V]` The canonical projection removes *exactly* `metadata.content_digest`
  (`adapter.py:153`), which is the seam the exclusion extends.

Stop condition for the eventual implementation: any of these failing at
implementation time halts the change set.

---

## 1. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `SU-IA-1` | The field's **name and type** | `supersedes_coordinate: Optional[PolicyCoordinate] = None` on `AgentConstitutionPolicyMetadata` — the authority's own coordinate type, already imported here, under the same name the descriptor uses, so the adapter's mapping is an assignment and nothing is translated | a family-local reference type the adapter maps into a coordinate, keeping the authority type out of the artifact |
| `SU-IA-2` | How the **exclusion** is implemented and guarded | exclude by name in `_canonical_projection`, beside `content_digest`; the guard already exists — `test_authority_registration.py:181-190` must stay green **unedited**, and `test_artifact.py:405`'s parametrization must **not** gain the field. A comment at the exclusion names `ACC-SU-2` as its authority | a new dedicated guard test instead of relying on the existing closed-set assertion |
| `SU-IA-3` | The **digest-invariance** leg's fixture | pin the ratified v1 content's body digest as a **literal** in the test, computed at implementation time and asserted equal — so any later projection change fails loudly, not just this one. The literal is a digest of ratified content, not key material | compare two in-run constructions only, which proves today's change and nothing about tomorrow's |
| `SU-IA-4` | The **version-pin conflict** with `ACC-SU-4` | read `ACC-SU-4`'s "untouched" as *no behavioural change*: the surface includes the two `family.__version__` pin lines (`…conformance…:105`, `…activation…:105`), moved `0.1.0` → `0.2.0` and **moved, never deleted or loosened**. Nothing else in those distributions changes | read "untouched" strictly, in which case **this ballot cannot authorize the bump**: an amendment to `ACC-SU-4`, on `ACC-LC-IA-BASE-A1`'s precedent, must land first |
| `SU-IA-5` | The change set's **file bounds** | exactly: `policy.py` (the field), `adapter.py` (map + exclude), `public_api.json`, `version.py` (`0.1.0` → `0.2.0`), `tests/test_public_api.py` (its own pin), one new proof module carrying the three `ACC-SU-3` legs, `CHANGELOG.md`, and — per `SU-IA-4` — the two dependent pin lines. Nothing else | the owner names a different set |

Couplings, disclosed: `SU-IA-4` and `SU-IA-5` interact — `SU-IA-4=B` removes the
two pin lines from the bounds and blocks the round until an amendment lands. No
other pair interacts.

`[G]` **The standing bite, unchanged:** none of this makes supersession
exercisable. `ACC-LC-IA-3` refuses an absent predecessor and no constitution has
been issued, because the `ACC-FC-5` gates are shut. This round closes a contract
gap only.

---

## 2. The fixed surface put to ratification

Ratified whole alongside the rows, with the standing precedence rule: **where a
`SU-IA` row and this surface overlap, the row governs; where either conflicts
with an `ACC-SU` ruling, the `ACC-SU` ruling governs.**

The authorized change set touches `agent-constitution-policy` and, per
`SU-IA-4`, two pin lines in the dependent verify scripts — nothing else. No new
authority, and the shipped supersession mechanism is not reopened; `OD-C4=A`
holds untouched; `OD-C3=B` holds; no signing key, trust root or approval
artifact enters the repository and every proof runs on ephemeral in-process
keys; **no already-valid artifact is invalidated and no existing refusal is
relaxed** — the unstructured `supersedes_ref` keeps being refused exactly as
today, and no existing digest moves; suspension is not implemented
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered; no constitution is issued, superseded, suspended or revoked, and no
agent runs, is enrolled or is claimed governed. **YES/NO.**

---

## 3. Paste-ready owner-ratification ballot

```
Agent Constitution — family supersession opt-in, implementation-authority ballot
Baseline: rasaha/symbolu default head 7015dec2
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-*,
ACC-LC-* and ACC-SU-* as ratified. Where a row conflicts with an ACC-SU ruling,
the ACC-SU ruling governs and the row is void. Answer each with A or B.
A = the recommended path.

SU_IA_SURFACE  Ratify the fixed surface: the authorized change set touches
      agent-constitution-policy and, per SU-IA-4, two pin lines in the dependent
      verify scripts — nothing else. No new authority and the shipped
      supersession mechanism is not reopened; OD-C4=A holds untouched; OD-C3=B
      holds; no signing key, trust root or approval artifact enters the
      repository and every proof runs on ephemeral in-process keys; no
      already-valid artifact is invalidated, no existing refusal is relaxed and
      no existing digest moves; suspension is not implemented (ACC-LC-3);
      /clauses/v2 stays out of scope and ACC-AM-4's re-arm stays untriggered; no
      constitution is issued, superseded, suspended or revoked; no agent runs,
      is enrolled or is claimed governed — with the precedence rule above.
      YES/NO.

SU-IA-1  The field's name and type.
      A = supersedes_coordinate: Optional[PolicyCoordinate] = None on
          AgentConstitutionPolicyMetadata — the authority's own coordinate type,
          already imported by this family, under the same name the descriptor
          uses, so the adapter's mapping is an assignment.
      B = a family-local reference type the adapter maps into a coordinate.

SU-IA-2  How the projection exclusion is implemented and guarded.
      A = exclude by name in _canonical_projection beside content_digest; the
          guard already exists — test_authority_registration.py:181-190 must
          stay green UNEDITED and test_artifact.py:405's parametrization must
          not gain the field; a comment at the exclusion names ACC-SU-2 as its
          authority.
      B = a new dedicated guard test instead of the existing closed-set
          assertion.

SU-IA-3  The digest-invariance leg's fixture.
      A = pin the ratified v1 content's body digest as a literal in the test,
          computed at implementation time, so any later projection change fails
          loudly rather than only this one.
      B = compare two in-run constructions only.

SU-IA-4  The version-pin conflict with ACC-SU-4.
      A = read ACC-SU-4's "untouched" as no behavioural change: the surface
          includes the two family.__version__ pin lines in the conformance and
          activation verify scripts, moved 0.1.0 -> 0.2.0, and moved, never
          deleted or loosened. Nothing else in those distributions changes.
      B = read "untouched" strictly: this ballot cannot authorize the bump, and
          an amendment to ACC-SU-4 must land first.

SU-IA-5  The change set's file bounds.
      A = exactly policy.py, adapter.py, public_api.json, version.py,
          tests/test_public_api.py, one new proof module, CHANGELOG.md, and the
          two dependent pin lines per SU-IA-4. Nothing else.
      B = the owner names a different set.

Record as: SU_IA_SURFACE=? SU-IA-1=? SU-IA-2=? SU-IA-3=? SU-IA-4=? SU-IA-5=?
This ballot authorizes no implementation by itself; register labels and the
authorization belong to the ruling ADR that records these answers.
```

---

## 4. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 7015dec2.
Read docs/architecture/AGENT_CONSTITUTION_FAMILY_SUPERSESSION_IMPLEMENTATION_AUTHORITY_BALLOT.md
and judge four things against the repository, not against the document:

1. Is §0's consumer enumeration COMPLETE? Find any consumer of the family's
   artifact shape, closed vocabularies, public_api.json or version that the
   eight rows miss — test harnesses, verify scripts, CI workflows and generated
   inventories included. A missed consumer is the failure mode this ballot
   exists to prevent.
2. SU-IA-4 reads ACC-SU-4's "untouched" as "no behavioural change, pins move".
   Is that legitimate, or does it overrule a ratified row? If the latter, say so
   plainly — the row is void and an amendment is required.
3. Does SU-IA-2=A's reliance on two EXISTING tests as the exclusion's guard
   actually hold? Would a future edit that re-included the field in the
   projection be caught by test_authority_registration.py:181-190, or could it
   slip through?
4. Does any option touch a role or an agent (OD-C4=A), relax the unstructured
   refusal, or move an existing digest?

Report findings labelled [V]/[I]/[R]/[G] with file:line support.
```

---

## 5. Readiness verdict

`[R]` **Ready to put, with one row that may be void.** The enumeration
`ACC-SU-4` required did its job: it found, before any code was written, that the
ratified bump breaks two distributions the same ruling calls untouched — the
exact failure that cost the previous round two CI cycles when the enumeration
was skipped. `[G]` If the owner reads `ACC-SU-4`'s "untouched" strictly,
`SU-IA-4=A` is void and this round needs an amendment before implementation can
proceed; that is the one path where the ballot cannot simply be answered.
