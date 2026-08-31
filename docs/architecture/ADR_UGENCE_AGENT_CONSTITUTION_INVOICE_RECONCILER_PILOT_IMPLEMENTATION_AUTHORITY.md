# ADR: Ugence Agent Constitution — invoice-reconciler pilot, implementation-authority ruling

**Status:** **Accepted (owner ruling) — documentation only.** This is the
separate ruling the pilot ratification ADR sequenced after itself. It settles
**exactly two things**: the committed-JSON guard raised as `[G]` in that ADR's
§5, and the authorization of the pilot change set scoped by `ACC-PR-1` –
`ACC-PR-4`. It performs neither: no source, test, `public_api.json`,
`version.py`, CHANGELOG, package metadata or CI workflow is modified by this
document, and the authorized change set lands as its own later change.

**Date:** 2026-08-31.

**Decision owner:** the repository owner, ruling personally in conversation on
2026-08-31. On the standing precedent: **where the conversation and this ADR
differ, this ADR governs.**

**Governing record:** the pilot ratification ADR
[`ADR_UGENCE_AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_RATIFICATION.md)
(`ACC-PR-BASE`, `ACC-PR-1` – `ACC-PR-5`), over the ballot transcription pinned
at commit `f4b0c94c693375ee512bf71cf0b144bdabfc46e0`. This ruling rides the
same branch as that ADR and takes effect when they merge together; it decides
nothing the ratification did not already scope.

**Numbering.** `[R]` Two ADR-scoped labels on the standing precedent:
**`ACC-PR-IA-1`** (the guard) and **`ACC-PR-IA-2`** (the authorization). No
other register gains a number.

## 1. `ACC-PR-IA-1` — the committed-JSON guard: **extend the scan** `[R]`

**Ruled: extension, not waiver.** The activation distribution's
role-projection scan
(`packages/integration/agent-constitution-activation/tests/test_import_boundary.py:174`)
is extended from `.py` files to **every committed text file under the
distribution**, the `pilot/` directory and its JSON document included. No
waiver is granted for `pilot/invoice-reconciler-role.v1.json`, narrow or
otherwise.

**Rationale** `[V]`: the scan's markers are the `CognitiveRole` substring
family (`test_import_boundary.py:81-86`, assembled from fragments so the test
never spells them). Those markers name the barred role-*projection* concept —
they are not role-contract vocabulary. The pilot document's ratified content
(`ACC-PR-2`: governed reference, tenant, `role_contract_id`, the disposition
and review-action vocabularies, the two tool scopes, `constitution_ref`, the
opaque C5a references) contains none of them, so extension costs the pilot
nothing, while a waiver would exempt precisely the one committed file most
likely to drift toward projection language. A guard that the guarded document
passes on its merits beats an exemption.

**Bounds of the extension** `[R]`: it extends the *text-substring* projection
scan only. The AST-based custody and import scans are `.py`-shaped by nature
and keep their current coverage; the Agentic Proposer's repository-wide scan
(every `.py` under `packages/`) is not modified by this ruling — the
activation suite's extended scan is the guard that reaches the committed JSON,
caught by this distribution's own suite as that file's docstring already
prefers.

## 2. `ACC-PR-IA-2` — the pilot change set: **authorized** `[R]`

The change set scoped by `ACC-PR-1` – `ACC-PR-4` is authorized, as ruled and
nothing beyond:

* the committed JSON document
  `packages/integration/agent-constitution-activation/pilot/invoice-reconciler-role.v1.json`,
  data outside `src/`, never shipped in the wheel, constructed into the live
  contract type only inside tests (`ACC-PR-1`), carrying exactly the
  `ACC-PR-2` content;
* **one** test module in the activation distribution's suite carrying the
  three-leg proof — document → contract equality; conformance `True` from the
  document's facts with the widened-scope `False` control and the two pinning
  assertions; the full issue → activate → resolve → bind → conform chain
  re-driven over this role with the mismatched-reference refusal control
  (`ACC-PR-3`), on ephemeral in-process keys;
* the `ACC-PR-IA-1` scan extension, as a minimal edit to
  `test_import_boundary.py` — authorized here because the ratification left
  the guard open, and this is the ruling that closes it;
* a CHANGELOG note recording the pilot as a repository act; the shipped wheel
  byte-identical; no version moves; `public_api.json` and every `src/` file
  untouched (`ACC-PR-4`).

**Authorized for no one and nothing else** `[R]`: no other file, package,
scan, specification or workflow may change under this ruling; any content
departure from `ACC-PR-2`, any additional test module, any `src/` or version
edit, and any production issuance are outside it and require a new owner
ruling. The change set must satisfy the extended scan and the distribution's
existing suite as they stand — a change set that needs a further exemption is
not the authorized change set.

## 3. Non-claims, carried forward unchanged

No agent runs, is enrolled, or is claimed governed by virtue of this record or
of the authorized change set. Constitution binding grants no compute, tools,
evidence access or consequential execution; digest membership proves integrity
after construction, never provenance; no verifier emits a disposition or
reserved authority term (`OD-C3=B`); no lifecycle authority exists or is
implied (`OD-C4=A`); conformance replay proves conformance of presented facts
only; no constitution exists, is issued, or may be described as issued, and
the pilot's proof runs on ephemeral in-process keys — no signing key, trust
root or approval artifact enters the repository. **The lifecycle round
(roadmap step 3) remains uncommissioned** (`ACC-PR-5`); this ruling does not
convene it.

## 4. What this ADR changed

One new documentation file. Nothing else: no production source, test,
specification, CHANGELOG, `public_api.json`, `version.py`, package metadata,
CI workflow or platform-freeze artifact is modified. The activation
distribution remains at `0.1.0`.

**Next step after this merges:** implement the authorized change set of §2,
exactly as bounded, as its own change.
