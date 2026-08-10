# Contributing to BCVF Autonomous

Thank you for considering a contribution. This document captures the
discipline the repository runs on; it's stricter than a typical OSS
project because the code is in the safety path of autonomous systems.
The rules exist so an integrator can audit a change without having
to re-read the whole codebase.

## §1 The six-step landing pattern

Every non-trivial change follows the same six steps. This is the
pattern every shipped feature has used; see the per-feature design
docs in the module root for examples.

1. **Design doc first.** A markdown file in the module root that
   names the problem, the surface being added, the failure modes
   it does and does not catch, and the explicit scope boundary.
   Pattern: `<FEATURE>_DESIGN.md`.
2. **Pinning tests before implementation.** Tests under
   `tests/test_<feature>_design_doc.py` that pin the design doc's
   structure (file exists, headings present, scope boundary stated)
   so the doc cannot drift silently.
3. **Implementation.** Frozen dataclasses, strict `__post_init__`
   validation, NumPy-stdlib only, no third-party deps unless gated
   behind a lazy import.
4. **Behavioural tests.** Tests under `tests/test_<feature>.py`
   that cover the §4 checks of the design doc. Coverage target is
   100% of public surfaces and 100% of failure modes named in the
   design doc.
5. **Safety-case wiring.** The feature's importable artifacts are
   added to `safety_case/traceability.py` against the relevant ISO
   21448 / ISO 26262 Part 6 clauses. The pinning test
   `tests/test_safety_case*.py` enforces importability.
6. **API stability bump + roadmap strikethrough + brief update.**
   The feature's public symbols are added to `_api.PROVISIONAL_API`
   (or `_api.STABLE_API` if graduating); the count is updated in
   `tests/test_api_stability.py::EXPECTED_PROVISIONAL_COUNT`; the
   relevant row in [`INDUSTRY_FEATURES_ROADMAP.md`](INDUSTRY_FEATURES_ROADMAP.md)
   is struck through with a pointer to the design doc; the
   evidence row is appended to
   [`AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md`](../../root_brief/AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md).

After step 6 the change is **independently audited** (the audit pass
runs by a different reviewer than the author, against the design
doc, looking for regressions and security issues) before merge.

## §2 API stability

See [`API_STABILITY.md`](API_STABILITY.md). The short version:

- **Stable** (`_api.STABLE_API`): a symbol's signature does not
  change in a backwards-incompatible way without a deprecation
  cycle. Stable promotion requires deployment-partner usage.
- **Provisional** (`_api.PROVISIONAL_API`): the symbol is shipped,
  supported, and tested, but the layout may shift in a minor
  version with a release-note line.
- **Internal**: anything not in either tuple. Free-form refactor
  target. Integrators that depend on internal surfaces do so at
  their own risk.

A new public surface starts in `PROVISIONAL_API`. Graduation to
`STABLE_API` requires (a) at least one minor version of cumulative
deployment-partner usage and (b) an updated `API_STABILITY.md` line
explaining the graduation.

## §3 Test discipline

- **NumPy-stdlib only** for the production path. Tests may use
  `pytest`, `pytest.fixture`, and `unittest.mock`. No `scipy`, no
  `cryptography`, no `pydantic`, no `pyyaml` (yaml is fine in
  tests if needed for fixture loading).
- **Frozen dataclasses everywhere.** `__post_init__` validates;
  invalid construction raises a typed exception (not `ValueError`).
- **No flaky tests.** Timing-sensitive tests are gated by a
  host-speed marker and excluded from the default sweep.
- **Pinning tests** on every public surface: a test that verifies
  the symbol is importable from the documented paths and has the
  documented signature.
- **Determinism.** Anywhere randomness exists, an explicit
  `random_seed` parameter is required and the seed is recorded in
  the episode record.

The full test suite must pass before a PR can be merged. Run it
via:

```bash
cd symbolu_robotics
pytest bcvf_autonomous/tests -q
```

## §4 Code style

- **No comments that explain the WHAT.** Comments only for the WHY:
  hidden constraints, subtle invariants, workarounds for specific
  bugs, behaviour that would surprise a reader.
- **No emojis** in code, comments, or commit messages.
- **No trailing whitespace.** No mixed tabs/spaces. PEP 8 indent.
- **Type hints on every public surface.** Internal helpers may be
  inferred. `from __future__ import annotations` at the top of
  every file.
- **Frozen dataclasses** preferred over plain classes for typed
  records. Strict `__post_init__` validation for every field.
- **No silent failures.** A misconfiguration raises a typed
  exception with a message that names the field and the violated
  invariant. A safety-relevant failure raises loud rather than
  returning a sentinel.

## §5 Audit-pass discipline

Every feature lands with an independent critical-audit pass. The
audit reviews:

1. Design-doc claims against implementation.
2. Failure modes named in the design doc against test coverage.
3. Security-relevant code (signatures, attestations, key handling)
   against well-known classes of vulnerability (timing attacks,
   replay, clock skew, naive serialisation).
4. API stability against the registry.
5. Traceability matrix against the safety-case pin.

Audit findings are categorised as HIGH / MEDIUM / LOW. HIGH and
MEDIUM findings are fixed before the audit pass closes; LOW
findings are filed as follow-up issues with a target version.

For an example of an audit pass with concrete findings, see the
sensor-attestation feature: 4 HIGH/MEDIUM findings (replay-window
invariant, naive timestamps, disabled-policy replay-cache update,
strict hex check) plus coverage hardening, all landed before the
feature merged.

## §6 What we don't accept

- **Half-finished implementations.** A change either lands the
  full pattern (design → tests → impl → safety-case → API) or it
  doesn't land at all. No "stub" PRs.
- **Speculative abstractions.** No "this might be useful later"
  helpers, registries, or factories. Three similar lines is
  better than a premature abstraction. Add the abstraction when
  there's a concrete second use case.
- **Backwards-compatibility shims** for code that hasn't shipped
  yet. The framework is pre-1.0; if a provisional surface needs
  to change, it changes (with a release-note line) — there are no
  legacy users to protect.
- **Feature flags** in production code paths. If a code path is
  experimental, it lives behind a separate import or under a
  documented `_research/` namespace. The main code path is the
  one we audit.
- **Cryptography that isn't stdlib.** All current attestation /
  signing / hashing uses `hmac` + `hashlib`. A dependency on
  `cryptography` would break the "auditable in one read" promise
  and is out of scope.
- **Direct dependency on a planner, perception stack, or vehicle
  hardware.** BCVF is the arbitration layer; it doesn't replace
  the things it sits between.

## §7 Reporting security issues

Security-relevant issues should not be filed as public GitHub
issues. Email the maintainer (see `pyproject.toml`) with:

- A short description of the issue.
- The affected version range.
- A reproducer if possible.
- Your suggested mitigation if you have one.

The maintainer will acknowledge within 5 business days, propose a
remediation timeline, and credit you in the release notes (unless
you prefer otherwise).

## §8 Commit + PR conventions

- **Commit messages** explain the WHY in the first line, with the
  WHAT in the body if needed. Reference the design doc.
- **PRs** include: a link to the design doc, a checklist mapping
  to the six steps in §1, the test count delta, and a one-line
  audit-pass summary.
- **Branch names** are one of:
  - `feature/<short-name>` for new features
  - `audit/<short-name>` for audit-pass landings
  - `fix/<short-name>` for bug fixes
  - `docs/<short-name>` for doc-only changes

Squash on merge unless the PR contains independently-meaningful
commits (design / impl / audit are typically squashed together;
multi-feature PRs aren't accepted in the first place).

## §9 First contribution

Good first issues are tagged `good-first-issue`. The lowest-friction
first contribution is typically:

- A doc-drift fix in one of the design docs.
- An additional pinning test for a provisional surface.
- A clarification of a scope-boundary statement in `NOTICE` or
  `DESIGN.md`.

If you'd like to land a larger change, open a discussion issue
first that proposes the design doc; the maintainer will respond
with whether the scope fits the framework's intended trajectory
before you write any code.

---

By contributing you agree that your contributions are licensed
under the same Apache License 2.0 that covers the rest of the
project. See [`LICENSE`](./LICENSE).
