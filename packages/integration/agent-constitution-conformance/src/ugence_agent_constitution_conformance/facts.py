"""The package-local presented-role-facts input shape (§5.1).

**Why this type exists, and why it is local.** A repository-wide scan in the
Agentic Proposer's suite refuses the substrings naming that capability's role
projection in every ``.py`` under ``packages/`` outside it, docstrings and
comments included. This distribution therefore never receives, imports or names
the role contract: the conformance boundary is handed a **plain frozen dataclass
of presented facts** — a role reference, the declared vocabulary sets, and a
tenant — assembled by the caller.

**The presented-facts caveat, disclosed plainly.** Replay proves conformance of
the **presented** facts to the resolved constitution; that those facts equal a
live role's actual declarations is the caller's assertion, exactly as digest
membership proves integrity after construction, never provenance. Nothing here
can detect a caller that presents facts no role carries.

**Validation posture.** Types are exact, duplicates are refused (a set whose
membership is ambiguous cannot be subset-tested honestly), and grammars are the
role surface's own: the role reference is a C5a ``Identifier``, every declared
token a C5b ``Token``. The two closed-vocabulary declarations must be non-empty
— the role surface they mirror requires non-empty declarations — while declared
tool scopes may be empty, because a role's tool scopes default empty and an
empty declared set conforms to any bound. Declared members are deliberately
**not** checked against the proposer's enums here: presentation is not
vocabulary, and a token outside its enum can never sit inside a signed bound, so
the predicate answers ``False`` for it rather than this type refusing to state
it. Order is **not** enforced: the ratified predicate is set-semantics,
order-insensitive, and these are presented facts rather than a digested
artifact.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Tuple

from .errors import ConstitutionFactsError

__all__ = ["GovernedRoleFacts"]

# C5b ``Token`` and C5a ``Identifier``, the Agentic Proposer's ratified grammar —
# the same spellings the family package holds its own fields to, so a fact that
# could never appear on the role surface is refused here rather than compared.
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_MAX_IDENTIFIER_LENGTH = 200


def _require_str(value: object, name: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise ConstitutionFactsError(f"{name} must be exactly a str")
    if not allow_empty and not value.strip():
        raise ConstitutionFactsError(f"{name} must be a non-empty str")
    return value


def _require_grammar(value: str, name: str, pattern, grammar: str) -> str:
    if len(value) > _MAX_IDENTIFIER_LENGTH:
        raise ConstitutionFactsError(
            f"{name} exceeds {_MAX_IDENTIFIER_LENGTH} characters"
        )
    if pattern.match(value) is None:
        raise ConstitutionFactsError(
            f"{name} does not satisfy the {grammar} grammar {pattern.pattern!r}"
        )
    return value


def _require_token_set(
    values: object, name: str, *, allow_empty: bool
) -> Tuple[str, ...]:
    if type(values) is not tuple:
        raise ConstitutionFactsError(f"{name} must be a tuple")
    if not values and not allow_empty:
        raise ConstitutionFactsError(
            f"{name} must name at least one member; the declaring surface it "
            "mirrors requires a non-empty declaration"
        )
    for index, token in enumerate(values):
        if type(token) is not str:
            raise ConstitutionFactsError(f"{name}[{index}] must be exactly a str")
        _require_grammar(
            _require_str(token, f"{name}[{index}]"),
            f"{name}[{index}]",
            _TOKEN_PATTERN,
            "C5b Token",
        )
    if len(set(values)) != len(values):
        raise ConstitutionFactsError(
            f"{name} names one member twice; an ambiguous set cannot be "
            "subset-tested honestly"
        )
    return values


@dataclass(frozen=True)
class GovernedRoleFacts:
    """Presented facts about one role, assembled by the caller.

    ``tenant_id`` may be the canonical empty string when the governing
    constitution is GLOBAL-scoped; it is carried for the resolution boundary and
    plays no part in the conformance predicate itself, which the ratified
    surface fixes as role membership plus three subset checks and nothing else.
    """

    tenant_id: str
    role_contract_ref: str
    declared_candidate_dispositions: Tuple[str, ...]
    declared_review_actions: Tuple[str, ...]
    declared_tool_scopes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_str(self.tenant_id, "GovernedRoleFacts.tenant_id", allow_empty=True)
        _require_grammar(
            _require_str(self.role_contract_ref, "GovernedRoleFacts.role_contract_ref"),
            "GovernedRoleFacts.role_contract_ref",
            _IDENTIFIER_PATTERN,
            "C5a Identifier",
        )
        _require_token_set(
            self.declared_candidate_dispositions,
            "GovernedRoleFacts.declared_candidate_dispositions",
            allow_empty=False,
        )
        _require_token_set(
            self.declared_review_actions,
            "GovernedRoleFacts.declared_review_actions",
            allow_empty=False,
        )
        _require_token_set(
            self.declared_tool_scopes,
            "GovernedRoleFacts.declared_tool_scopes",
            allow_empty=True,
        )
