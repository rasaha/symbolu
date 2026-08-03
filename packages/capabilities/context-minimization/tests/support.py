"""Deterministic test doubles — a family of neutral oracles, protection providers,
and a token counter, plus small context builders. NOTHING here imports ActionGate,
a model, or a product; these are self-contained fakes that exercise the neutral
contract exactly as a real integration adapter would.
"""

from __future__ import annotations

from ugence_context_minimization.api import (
    Context,
    ContextUnit,
    OracleEvaluation,
    ProtectionResult,
)

DEFAULT_KEYWORDS = ("deploy", "backup", "approval", "credential")


# --------------------------------------------------------------------------- #
# Oracles
# --------------------------------------------------------------------------- #
class KeywordOracle:
    """Equivalence key = the sorted set of 'critical' keywords present in surviving
    units. Removing a unit with no critical keyword is invariant; removing the last
    carrier of a keyword changes the key."""

    def __init__(self, keywords=DEFAULT_KEYWORDS, oracle_id="keyword-oracle",
                 contract_version="1.0", valid_until=None, lock_correlation=True):
        self.keywords = tuple(keywords)
        self.oracle_id = oracle_id
        self.contract_version = contract_version
        self.valid_until = valid_until
        self.lock_correlation = lock_correlation
        self.calls = 0

    def evaluate(self, context, *, evaluation_time=None):
        self.calls += 1
        present = sorted({
            kw for u in context.units for kw in self.keywords if kw in (u.text or "").lower()
        })
        corr = context.correlation_id if self.lock_correlation else None
        return OracleEvaluation(
            equivalence_key="kw:" + ",".join(present),
            oracle_id=self.oracle_id,
            contract_version=self.contract_version,
            evaluation_ref="eval-ref",
            correlation_id=corr,
            valid_until=self.valid_until,
        )


class AtLeastOneOracle:
    """Requirement is met iff at least one of ``members`` is present. Produces a true
    JOINT effect: removing any single member individually is invariant, but removing
    all of them together is not — so per-unit restoration cannot recover it."""

    oracle_id = "at-least-one-oracle"
    contract_version = "1.0"

    def __init__(self, members):
        self.members = frozenset(members)

    def evaluate(self, context, *, evaluation_time=None):
        present = any(u.id in self.members for u in context.units)
        return OracleEvaluation(
            equivalence_key="REQ_MET" if present else "REQ_UNMET",
            oracle_id=self.oracle_id,
            contract_version=self.contract_version,
            correlation_id=context.correlation_id,
        )


class RaisingOracle:
    def evaluate(self, context, *, evaluation_time=None):
        raise RuntimeError("oracle boom")


class MalformedOracle:
    def evaluate(self, context, *, evaluation_time=None):
        return {"equivalence_key": "not-an-OracleEvaluation"}


class NonStringKeyOracle:
    """Returns a non-string (None) equivalence key — malformed."""

    def evaluate(self, context, *, evaluation_time=None):
        return OracleEvaluation(equivalence_key=None, oracle_id="nullkey", contract_version="1.0")


class ExpiringOracle:
    """valid_until is always strictly before the supplied evaluation_time."""

    def evaluate(self, context, *, evaluation_time=None):
        et = 1000.0 if evaluation_time is None else evaluation_time
        return OracleEvaluation(
            equivalence_key="k", oracle_id="expiring", contract_version="1.0",
            valid_until=et - 1.0,
        )


class WrongCorrelationOracle:
    def evaluate(self, context, *, evaluation_time=None):
        return OracleEvaluation(
            equivalence_key="k", oracle_id="wrongcorr", contract_version="1.0",
            correlation_id="a-different-correlation",
        )


class DriftingContractOracle:
    """Returns a different contract_version once the context shrinks below ``threshold``
    units — simulating an oracle whose contract silently changed between calls."""

    oracle_id = "drift"

    def __init__(self, threshold):
        self.threshold = threshold

    def evaluate(self, context, *, evaluation_time=None):
        cv = "1.0" if len(context.units) >= self.threshold else "2.0"
        return OracleEvaluation(equivalence_key="k", oracle_id=self.oracle_id, contract_version=cv)


class RecordingOracle:
    """Wraps another oracle and records that it was reached only via ``evaluate``."""

    def __init__(self, inner):
        self.inner = inner
        self.evaluate_calls = 0

    def evaluate(self, context, *, evaluation_time=None):
        self.evaluate_calls += 1
        return self.inner.evaluate(context, evaluation_time=evaluation_time)


# --------------------------------------------------------------------------- #
# Protection providers
# --------------------------------------------------------------------------- #
class KeywordProtection:
    """Protect units whose text contains any protected keyword; optionally mark some
    ids uncertain (which must be RETAINED, fail-closed)."""

    def __init__(self, keywords=("credential",), uncertain_ids=()):
        self.keywords = tuple(keywords)
        self.uncertain_ids = frozenset(uncertain_ids)

    def protect(self, context):
        protected = {
            u.id for u in context.units
            if any(kw in (u.text or "").lower() for kw in self.keywords)
        }
        return ProtectionResult(
            protected_ids=frozenset(protected),
            uncertain_ids=self.uncertain_ids,
            provider_id="keyword-protection",
        )


class RaisingProtection:
    def protect(self, context):
        raise RuntimeError("protection boom")


class MalformedProtection:
    def protect(self, context):
        return {"protected_ids": []}


# --------------------------------------------------------------------------- #
# Token counter
# --------------------------------------------------------------------------- #
class WordCounter:
    def count(self, text):
        return len((text or "").split())


# --------------------------------------------------------------------------- #
# Builders
# --------------------------------------------------------------------------- #
def unit(uid, text, **kw):
    return ContextUnit(id=uid, text=text, **kw)


def context(units, cid="ctx", correlation_id="corr-1", **kw):
    return Context(id=cid, units=tuple(units), correlation_id=correlation_id, **kw)
