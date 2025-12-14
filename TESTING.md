# Symbol-U Testing Standard

## Forward-Only Invariant Enforcement Policy

This document defines the testing standard for all **new** tests and test modifications in the Symbol-U repository. It does not apply retroactively to existing tests.

---

## 1. Purpose

Tests exist to **prove architectural invariants**, not to exhaustively verify arithmetic or edge cases.

Every test in Symbol-U should demonstrate that a specific system property holds under defined conditions. The primary invariants that tests must address include:

- **Determinism**: Given identical inputs, the system produces identical outputs
- **Authority boundaries**: Authoritative phases never receive input from observer-only phases
- **Non-interference**: Observer components do not influence authoritative decision paths
- **Monotonicity**: Certain values or states only increase (or only decrease) and never reverse
- **Observer vs authority separation**: Clear distinction between phases that observe and phases that decide

Tests that do not prove one of these (or a similarly defined) invariants provide limited value and should not be written.

---

## 2. Core Rule (MANDATORY)

> **Every test MUST be mapped to exactly one invariant.**
> **No invariant = no test.**

This rule is non-negotiable for all new test code.

### Mapping constraints:

- **One test → one invariant**: Each test function proves exactly one invariant
- **One invariant → one test**: Each invariant should have exactly one canonical test, unless multiple tests are explicitly justified (e.g., different failure modes of the same invariant)

If you cannot identify the invariant a test proves, the test should not exist.

---

## 3. Invariant-to-Test Mapping Requirement

Every new test file or test case **must declare**:

1. The **invariant ID** it proves (e.g., `INV-P38-1`)
2. A **one-line explanation** of how the test proves that invariant

### Required format:

```python
# Proves INV-P38-1: Forecast never influences current decisions
def test_forecast_is_observer_only():
    """
    Invariant: INV-P38-1
    Proves that forecast output is not consumed by any authoritative phase.
    """
    ...
```

### Invariant ID convention:

- Format: `INV-P{phase}-{number}` (e.g., `INV-P38-1`, `INV-P17-3`)
- For cross-phase invariants: `INV-GLOBAL-{number}` (e.g., `INV-GLOBAL-1`)
- For core invariants: `INV-CORE-{number}` (e.g., `INV-CORE-1`)

The invariant ID must be traceable to documentation or a design specification.

---

## 4. Test Count Policy

### Constraints:

- There must be **exactly one test per invariant** unless explicitly justified
- Redundant arithmetic edge-case tests are **discouraged**
- Boundary tests are allowed **only if they prove a different invariant**

### Guideline:

> **If you cannot map a test to a unique invariant, delete the test before writing it.**

Do not write tests for:

- Trivial arithmetic verification (e.g., `assert 2 + 2 == 4`)
- Edge cases that do not represent distinct invariant violations
- "Just in case" coverage without architectural justification

---

## 5. Determinism Requirement

All new tests **must be deterministic**.

### Requirements:

- Tests must produce **identical results across runs**
- Tests must **avoid randomness** unless explicitly testing randomness handling
- If randomness is required, tests must use **fixed seeds** and document why

### Prohibited patterns:

- `random.random()` without seed
- Time-dependent assertions without mocking
- External network calls without deterministic mocking
- File system operations that depend on execution order

---

## 6. Observer / Authority Rule

Symbol-U distinguishes between **observer phases** (which compute derived values) and **authoritative phases** (which make decisions).

### Testing requirements:

- **Observer-only phases** may be tested for non-interference
- **Observer outputs must NEVER affect authoritative phases**
- Tests must **explicitly assert non-influence** where relevant

### Example assertion pattern:

```python
# Proves INV-P38-2: Observer output does not modify authority state
def test_observer_does_not_mutate_authority():
    """
    Invariant: INV-P38-2
    Verifies that calling the forecast observer leaves authority state unchanged.
    """
    authority_state_before = copy.deepcopy(authority.get_state())
    observer.compute_forecast(context)
    authority_state_after = authority.get_state()

    assert authority_state_before == authority_state_after
```

---

## 7. Legacy Test Exemption

> **CRITICAL SECTION**

### Legacy Test Exemption

**This testing standard applies only to new tests and new refactors.**

All existing tests are **grandfathered** and are **NOT required to comply** unless they are explicitly audited or modified in the future.

### Clarifications:

- No existing test failures should be interpreted as violations of this policy
- Existing tests that lack invariant mappings are **not** in violation
- Cleanup of legacy tests is **optional and deferred**
- Legacy tests remain valid and must continue to pass

### When legacy exemption ends:

A test loses its legacy exemption when:

1. The test file is significantly modified (not just formatting)
2. The test is explicitly flagged for audit
3. The test is moved or renamed as part of a refactor

At that point, the test must be updated to comply with this standard or be removed.

---

## 8. Enforcement Scope

### What this document is:

- A **development standard** for code review
- A **normative guide** for writing new tests
- A **reference** for CI check implementation (future)

### What this document is NOT:

- An automatic enforcement mechanism
- A mandate to delete existing tests
- A retroactive audit requirement

### Enforcement mechanisms:

- **Code review**: Reviewers should verify invariant mappings for new tests
- **Future CI checks**: Automated checks may be added to enforce format compliance
- **Documentation**: New tests without invariant declarations may be flagged

### No automatic deletion:

This document does not authorize or require automatic deletion of any test. Deletion decisions remain with the development team and require explicit review.

---

## Summary

| Rule | Applies To | Enforcement |
|------|-----------|-------------|
| One test per invariant | New tests only | Code review |
| Invariant ID required | New tests only | Code review |
| Determinism required | New tests only | Code review + CI |
| Observer/authority separation | New tests only | Code review |
| Legacy exemption | Existing tests | Automatic |

---

## Changelog

- **Initial version**: Forward-only invariant enforcement policy established
