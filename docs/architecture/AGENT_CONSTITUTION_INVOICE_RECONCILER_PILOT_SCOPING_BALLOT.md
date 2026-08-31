# Agent Constitution — invoice-reconciler pilot scoping ballot (transcription of record)

**Provenance.** This document is an **owner act recorded by this task**: the
repository owner put the ballot below in conversation on 2026-08-31, against
baseline `ac70994d9d4478628a17e96d0a656418302fbbdf`, and directed its verbatim
transcription into the repository so the ratification ADR can pin it by file
path, commit, digest, line count and ballot-block hash, on the standing
precedent of pinned ballot documents. The transcription below is the ballot as
put, unedited. The authority is the owner's conversational act; this file is
its record. The ratification ADR that records the owner's answers is
`ADR_UGENCE_AGENT_CONSTITUTION_INVOICE_RECONCILER_PILOT_RATIFICATION.md`.

**Ballot-block delimitation.** The ballot block runs from the line beginning
`Agent Constitution — invoice-reconciler pilot scoping ballot` through the
line ending `ruling that follows it.`, inclusive, inside the fence below.

---

```
Agent Constitution — invoice-reconciler pilot scoping ballot
Baseline: rasaha/symbolu default head ac70994d9d4478628a17e96d0a656418302fbbdf
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-* and ACC-IA-* as ratified.
Answer each with A or B. A = the recommended path.

PILOT_SURFACE  Ratify the fixed surface: the pilot is a committed declaration and
      its proof, driven through the shipped ACC-IA orchestration — no new
      authority surface, no change to any existing package's src, version or
      public_api.json; no signing key, trust root or approval artifact enters the
      repository (proof runs on ephemeral in-process keys); the only constitution
      values used are the ratified ACC-FC content values, and every role
      declaration sits inside the ratified bounds; no agent runs, is enrolled or
      is claimed governed in operation; /clauses/v2 stays out of scope and
      ACC-AM-4's re-arm stays untriggered — with the precedence rule: where an IR
      row and this surface overlap, the IR ruling governs.  YES/NO.

IR-1  The role artifact's home and form.
      A = one committed JSON document,
          packages/integration/agent-constitution-activation/pilot/
          invoice-reconciler-role.v1.json — data outside src/, never shipped in
          the wheel, constructed into the live contract type only inside tests.
      B = tests-only fixture, no committed artifact; the ACC-FC-3 gap stays open.

IR-2  The role's declared content (§2, arrives whole).
      A = the §2 table with its disclosures: the governed reference as document
          identity; tenant ugence; role_contract_id invoice-reconciler; full
          ratified disposition and review-action vocabularies; tool scopes
          exactly (invoice.read, ledger.read); constitution_ref equal to the
          signed reference; the named escalation and strategy references carried
          as opaque, ungoverned C5a values.
      B = the owner supplies different values; declarations must still sit
          inside the ratified bounds and both reference equalities must hold.

IR-3  Proof scope.
      A = the three-leg proof: document -> contract equality; conformance True
          from the document's facts with a widened-scope False control and the
          two pinning assertions; and the full issue -> activate -> resolve ->
          bind -> conform chain re-driven over this role, with a
          mismatched-reference refusal control.
      B = legs 1-2 only; the chain leg deferred.

IR-4  Packaging and versioning.
      A = document + one test module in the activation distribution; the shipped
          wheel is byte-identical and no version moves; a CHANGELOG note records
          the pilot as a repository act.
      B = a separate pilot package, or a version bump; the owner names which.

IR-5  Commitment and sequencing.
      A = the pilot commits a governed declaration and its proof only — no
          agent, no compute, no evidence access, no production issuance, no
          lifecycle act; the lifecycle round (roadmap step 3) is not
          commissioned by this ballot.
      B = additionally commission the lifecycle round's scoping ballot now, as
          its own document.

Record as: PILOT_SURFACE=? IR-1=? IR-2=? IR-3=? IR-4=? IR-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```
