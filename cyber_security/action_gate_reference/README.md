# Action Gate — Stage-1 Reference Conformance Harness

An executable, dependency-light reference implementation of the **pre-commit
agent-action admissibility gate**: the deterministic checks that decide whether
an autonomous agent's proposed production-infrastructure action is *admissible*
before it is committed. This harness is the ground-truth oracle for the frozen
byte-level and interface contracts — it exists so a second implementation can be
proven conformant against pinned canonical bytes and digests.

> **Reference-only.** No network services, no MCP server, no live credential
> broker, no production key custody, no AI/ML, and none of the BCVF/USE/SCC
> research machinery. It is the *minimum deterministic core*: canonicalize →
> hash → bind → decide → audit. See **Security boundaries** below.

## Frozen contracts implemented

This code is subordinate to three frozen specifications in the parent directory;
where code and spec disagree, the spec wins and the divergence is logged in
[`IMPLEMENTATION_FINDINGS.md`](IMPLEMENTATION_FINDINGS.md):

| Spec | What this harness realizes |
|------|----------------------------|
| [`../ACTION_GATE_SPECIFICATION.md`](../ACTION_GATE_SPECIFICATION.md) | 24-field envelope, six decision outcomes, deterministic state machine, hard-invariant operators |
| [`../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`](../ACTION_CANONICALIZATION_AND_HASHING_SPEC.md) | JCS + Action Profile canonicalization, domain-separated length-prefixed hashing, action-hash projection, conformance vectors |
| [`../AGENT_ACTION_ADMISSIBILITY_MVP.md`](../AGENT_ACTION_ADMISSIBILITY_MVP.md) | MVP scope, operation taxonomy, acceptance scenarios |

## Requirements

- **Python 3.11+**, standard library only (`hashlib`, `hmac`, `json`,
  `unicodedata`, `re`, `argparse`, `datetime`, `struct`). No third-party runtime
  dependencies.
- **`pytest`** only to run the test suite (dev-only; the library itself needs no
  external packages).

## Install / run

```bash
cd cyber_security/action_gate_reference

# 1. run the full test suite (unit + transitions + acceptance + conformance)
python3 -m pytest -q

# 2. run just the conformance vectors
python3 -m action_gate_ref.cli run-conformance

# 3. regenerate the pinned fixtures (only after an intentional contract change)
python3 -c "from action_gate_ref import conformance; conformance.generate_pinned()"
```

## CLI

`python3 -m action_gate_ref.cli <command>` — all output is single-line JSON;
exit code is non-zero on `ok:false`. Raw secrets are never printed.

| Command | Purpose |
|---------|---------|
| `validate-envelope <env.json>` | Structural + Action-Profile validation of an action envelope |
| `canonicalize <value.json>` | Emit canonical JCS+Profile bytes and byte length |
| `hash-action <env.json>` | Action-hash (sha-256 and sha-512/256) + projection manifest |
| `verify-approval <ap.json> <env.json> --policy-hash H --now TS` | Validate an approval's binding to an action |
| `verify-token <tok.json> <env.json> --policy-hash H --now TS [--require-reeval]` | Validate an execution-authorization token at commit time |
| `verify-audit-chain <chain.json>` | Recompute and verify an audit hash chain |
| `decide <env.json> --now TS [--evidence ev.json] [--approvals aps.json]` | Run the gate against the default reference policy; emit the decision |
| `run-conformance` | Run all conformance vectors |

## What the harness contains

```
action_gate_ref/
  canon_profile.py   frozen versions, hash algorithms, the ten domain tags
  jcs.py             RFC 8785 JCS + Action Profile canonicalizer (fail-closed)
  hashing.py         domain-separated, length-prefixed digests; audit chain hash
  schema.py          24-field envelope validation (rejects what JSON Schema cannot)
  projection.py      action-hash projection (inclusion/exclusion manifest)
  signing.py         reference-only HMAC test-key signing (NOT production)
  policy.py          signed policy bundle + the ten example hard-invariant rules
  approval.py        approval object + binding validation (SoD, quorum, replay)
  evidence.py        evidence/simulation envelopes bound to action_hash
  token.py           execution-authorization token (replay/TOCTOU/scope checks)
  audit.py           immutable audit record + append-only tamper-evident chain
  gate.py            deterministic evaluator: six outcomes by fixed precedence
  conformance.py     24 executable conformance vectors + pinned-digest generator
  cli.py             local JSON CLI
  errors.py          machine-readable, fail-closed error codes
fixtures/
  conformance_vectors.json   pinned canonical bytes + sha-256/sha-512-256 digests
  transitions.json           ten operation-class happy-path decisions
  envelope.schema.json       non-normative JSON Schema mirror of the 24 fields
tests/                        unit + transition + acceptance + conformance tests
IMPLEMENTATION_FINDINGS.md    contract contradictions found and how they resolved
```

## Conformance vectors and pinned values

`run-conformance` executes **24 vectors** covering: key-order/whitespace
independence, omit-vs-null, bare-number/NaN/Inf/dup-key/non-NFC rejection,
ordered-vs-set arrays, timestamp normalization, action-hash sensitivity
(argument/target/scope/policy/rollback/runtime/model) and stability
(action_id/timestamp excluded), domain separation, secret-reference versioning,
approval/token replay + TOCTOU, audit-chain tamper localization, and the
low-entropy-secret HMAC-commitment policy.

Pinned reference values (regenerated into `fixtures/conformance_vectors.json`;
the tests fail on any drift):

| Value | Digest |
|-------|--------|
| Reference action canonical byte length | `965` |
| Reference `action_hash` (sha-256) | `40af208b568da0a8a52356231b17eccca317f1c129cc3d4054b14e3fdbe3697f` |
| Reference `action_hash` (sha-512/256) | `9bb7639d34d5882acd218890d0b7108da6759963ca10843424fb96fd3851fba2` |
| Default reference `policy_hash` (sha-256) | `b93b95d182bf796c1f83407ff7d94d51ae62ed83f00e9f2b7fe25e9fdc2ddd90` |
| Sample `{"a":"2","b":"1"}` ACTION digest (sha-256) | `5d4439343a125d09ca5ebb09bf3346cf3e4f3a486f975477a79e72d63aa8d5d2` |

## Security boundaries (reference-only status)

**In scope (and enforced here):**
- Deterministic, byte-exact canonicalization that fails closed on ambiguity
  (duplicate keys, bare numbers, NaN/Infinity, non-NFC, invalid UTF-8).
- Domain separation with length-prefix framing so digests from different
  contexts (action vs. approval vs. audit …) can never be confused.
- Action-identity projection: approvals/tokens bind to the *authorization-
  relevant* content, not to per-attempt ids or signatures.
- Binding + replay defenses: nonce single-use, action-hash rebinding,
  policy-hash rebinding, scope subsumption, Separation-of-Duties, quorum, and
  commit-time TOCTOU state checks.
- Tamper-**evident** audit chaining with first-tampered-record localization.

**Explicitly out of scope (production requirements NOT met by this harness):**
- **Key custody & asymmetric signing.** Signatures use HMAC over named *test*
  keys in `signing.py` purely so the reference is self-contained and
  deterministic. Production requires asymmetric signatures (e.g. Ed25519/ECDSA)
  via an audited crypto library, hardware-backed keys, rotation, and revocation.
  The HMAC test keyring is **not secret and not production**.
- **Tamper-proof storage.** The audit chain is tamper-*evident* given a
  protected audit key; it is **not** a blockchain and **not** tamper-proof
  external/WORM storage. Durable, access-controlled, replicated storage is a
  production concern.
- **Live credential broker / enforcement point.** `token.py` models the token a
  broker would check; it does **not** mint real cloud credentials or sit inline
  on a real tool-invocation path.
- **Real state oracles.** `current_state_hash`/`state_freshness` are validated
  and compared, but the harness does not query live infrastructure; the
  domain-adapter fact extraction (`gate.extract_facts`) is a deterministic stub.
- **Secret handling.** No raw secret is ever hashed or stored; low-entropy
  secret commitment must use HMAC (vector V24 asserts no bare-hash-of-secret API
  exists). Production secret material, sinks, and export controls are out of
  scope.

## Determinism & integrity

Every hash, decision, and canonical-byte string is a pure function of its
inputs; `tests/test_*` assert reproducibility across repeated runs, and the
committed fixtures are regression-pinned so any change to canonicalization,
projection, hashing, policy, or decision precedence surfaces as a failing test.
Contract contradictions encountered while implementing are not silently patched —
they are recorded in [`IMPLEMENTATION_FINDINGS.md`](IMPLEMENTATION_FINDINGS.md)
with the fail-closed resolution and its (decision-layer-only) blast radius.
