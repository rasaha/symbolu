#!/usr/bin/env python3
"""Gate inventory and measured gate-deletion mutation sweep.

Enumerates **every load-bearing gate** in the package — every predecessor-state
gate, every predecessor-``declared_outcome`` gate, every terminality gate, every
digest-binding gate, plus the actor-separation, exact-type, encoder and
vocabulary gates that hold the rest of the contract up — neutralizes them **one
at a time**, and records whether the full suite plus the author-owned adversarial
probes notice.

Method
------
The whole package tree is copied to a scratch directory once and kept as a
**pristine snapshot**. For each mutant the working copy is restored from that
snapshot, exactly one gate is neutralized by a textual substitution in the
source, and the suite and probes are run against the mutated copy. The result is
KILLED (something failed) or SURVIVED (everything passed).

Every mutant names the **first** failing test or probe, so the ledger records
what actually caught it rather than only that something did.

Honesty rules this sweep follows
--------------------------------
* Production behaviour is **never** changed to chase a zero-survivor number. A
  survivor is reported and classified, not designed away.
* Every survivor is classified as *equivalent* (the mutation changes no
  observable behaviour), *shadowed* (a different gate catches the same thing —
  and the shadowing gate is named), or *a real gap*.
* A mutation that fails to apply is reported as an error, never silently
  skipped: a substitution that no longer matches means the inventory has drifted
  from the source, and a drifted inventory reporting "all killed" would be
  reporting nothing.

Run:
    python packages/benchmark-registry-authority/gate_mutation_sweep.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

PKG = pathlib.Path(__file__).resolve().parent
REPO = PKG.parents[1]
BR1_SRC = REPO / "packages" / "benchmark-registry" / "src"
SRC_REL = pathlib.Path("src") / "ugence_benchmark_registry_authority"


class Gate:
    """One load-bearing gate, and the edit that neutralizes it."""

    def __init__(self, gate_id, category, module, description, old, new):
        self.gate_id = gate_id
        self.category = category
        self.module = module
        self.description = description
        self.old = old
        self.new = new

    def apply(self, root: pathlib.Path) -> None:
        path = root / SRC_REL / "contracts" / self.module
        text = path.read_text()
        if self.old not in text:
            raise LookupError(
                f"{self.gate_id}: the mutation target no longer appears in "
                f"{self.module}. The gate inventory has drifted from the "
                "source; a sweep run against a drifted inventory proves nothing."
            )
        if text.count(self.old) != 1:
            raise LookupError(
                f"{self.gate_id}: the mutation target appears "
                f"{text.count(self.old)} times in {self.module}; it must "
                "identify exactly one gate."
            )
        path.write_text(text.replace(self.old, self.new))


# --------------------------------------------------------------------------- #
# The complete gate inventory
# --------------------------------------------------------------------------- #
GATES = [
    # ---------------- predecessor-state / predecessor-outcome ------------- #
    Gate(
        "G-01",
        "predecessor-declared_outcome",
        "chain.py",
        "the shared ADMITTED-predecessor gate, which both the registration "
        "event and the post-admission rejection event depend on",
        "    if decision.declared_outcome is not BenchmarkAdmissionOutcome.ADMITTED:",
        "    if False:",
    ),
    Gate(
        "G-02",
        "predecessor-state",
        "chain.py",
        "the registration event's exact-type gate on its nested admission "
        "decision — the gate that fixes its predecessor STATE",
        """        require_exact_type(
            self.admission_decision,
            BenchmarkAdmissionDecisionPayload,
            "admission_decision",
        )
        require_aware_datetime(self.declared_recorded_at, "declared_recorded_at")
        _require_admitted_predecessor(
            self.admission_decision,
            "BenchmarkRegistrationEventPayload",
            "ADMITTED → REGISTERED",
        )""",
        """        require_aware_datetime(self.declared_recorded_at, "declared_recorded_at")
        _require_admitted_predecessor(
            self.admission_decision,
            "BenchmarkRegistrationEventPayload",
            "ADMITTED → REGISTERED",
        )""",
    ),
    Gate(
        "G-03",
        "predecessor-state",
        "chain.py",
        "the post-admission rejection event's exact-type gate on its nested "
        "admission decision",
        """        require_exact_type(
            self.admission_decision,
            BenchmarkAdmissionDecisionPayload,
            "admission_decision",
        )
        require_enum_member(
            self.declared_refusal_reason,""",
        """        require_enum_member(
            self.declared_refusal_reason,""",
    ),
    Gate(
        "G-04",
        "predecessor-state",
        "chain.py",
        "the revocation event's exact-type gate on its nested registration "
        "event — the gate that forbids a shortened chain",
        """        require_exact_type(
            self.registration_event,
            BenchmarkRegistrationEventPayload,
            "registration_event",
        )""",
        "        pass",
    ),
    Gate(
        "G-05",
        "predecessor-state",
        "chain.py",
        "the admission decision's exact-type gate on its nested submission "
        "record",
        """        require_exact_type(
            self.submission_record,
            BenchmarkSubmissionRecordPayload,
            "submission_record",
        )
        require_exact_type(
            self.approval_envelope,
            BenchmarkApprovalEnvelope,
            "approval_envelope",
        )""",
        """        require_exact_type(
            self.approval_envelope,
            BenchmarkApprovalEnvelope,
            "approval_envelope",
        )""",
    ),
    Gate(
        "G-06",
        "predecessor-state",
        "chain.py",
        "the submission record's exact-type gate on its nested publisher "
        "envelope",
        """        require_exact_type(
            self.publisher_submission_envelope,
            BenchmarkPublisherSubmissionEnvelope,
            "publisher_submission_envelope",
        )""",
        "        pass",
    ),
    # ---------------- terminality ---------------------------------------- #
    Gate(
        "G-07",
        "terminality",
        "chain.py",
        "the admission decision's terminality report, which tells a consumer a "
        "REJECTED decision has no successor",
        """        return self.declared_outcome is BenchmarkAdmissionOutcome.REJECTED""",
        """        return False""",
    ),
    Gate(
        "G-08",
        "terminality",
        "chain.py",
        "the post-admission rejection event's terminality report",
        '''        """Always ``True``. ``REJECTED`` has an empty admissible-successor set."""

        return True''',
        '''        """Always ``True``. ``REJECTED`` has an empty admissible-successor set."""

        return False''',
    ),
    Gate(
        "G-09",
        "terminality",
        "lifecycle.py",
        "the empty admissible-successor set for REVOKED — the terminal state's "
        "own relation entry",
        "        _S.REVOKED: frozenset(),",
        "        _S.REVOKED: frozenset({_S.REGISTERED}),",
    ),
    Gate(
        "G-10",
        "terminality",
        "lifecycle.py",
        "the empty admissible-successor set for REJECTED",
        "        _S.REJECTED: frozenset(),",
        "        _S.REJECTED: frozenset({_S.ADMITTED}),",
    ),
    # ---------------- digest binding ------------------------------------- #
    Gate(
        "G-11",
        "digest-binding",
        "chain.py",
        "the admission decision's byte-identity proof across its two nested "
        "paths to the publisher envelope",
        """        if record_bytes != approval_bytes:""",
        """        if False:""",
    ),
    Gate(
        "G-12",
        "digest-binding",
        "chain.py",
        "the admission decision's digest-identity proof across its two nested "
        "paths",
        """        if canonical_digest(through_record) != canonical_digest(through_approval):""",
        """        if False:""",
    ),
    Gate(
        "G-13",
        "digest-binding",
        "chain.py",
        "the revocation event's admitted-digest binding to the registration "
        "chain",
        """        if (
            self.revocation_envelope.admitted_digest
            != self.registration_event.benchmark_identity_digest
        ):""",
        """        if False:""",
    ),
    Gate(
        "G-14",
        "digest-binding",
        "chain.py",
        "the revocation event's locator binding to the registration event",
        """        if self.revocation_envelope.coordinate != self.registration_event.coordinate:""",
        """        if False:""",
    ),
    Gate(
        "G-15",
        "digest-binding",
        "canonical.py",
        "the exact-type identity boundary in the encoder — the check that a "
        "root or nested node IS a registered class",
        """    entry = _entry_for_contract_type(cls)
    if entry is None:""",
        """    entry = _entry_for_contract_type(cls)
    if False:""",
    ),
    Gate(
        "G-16",
        "digest-binding",
        "canonical.py",
        "the root-canonicalizability gate that refuses a frozen BR-1 contract "
        "as a BR-2 digest root",
        "    if not root_ok:",
        "    if False:",
    ),
    Gate(
        "G-17",
        "digest-binding",
        "canonical.py",
        "graph revalidation of every nested node before any byte is produced",
        """    for f in fields(contract):
        _revalidate_value(getattr(contract, f.name), f"{path}.{f.name}")
    try:
        cls.__post_init__(contract)""",
        """    try:
        cls.__post_init__(contract)""",
    ),
    Gate(
        "G-18",
        "digest-binding",
        "canonical.py",
        "the trusted-class validator invocation — replacing it with the "
        "instance-resolved call an attacker could override",
        "        cls.__post_init__(contract)",
        "        contract.__post_init__()",
    ),
    Gate(
        "G-19",
        "digest-binding",
        "canonical.py",
        "the domain-separation element in the canonical frame",
        '        "domain": domain,',
        '        "domain": "",',
    ),
    Gate(
        "G-20",
        "digest-binding",
        "canonical.py",
        "the type element in the canonical frame, which keeps two artifact "
        "classes in distinct byte spaces",
        '        "type": cls.__name__,',
        '        "type": "",',
    ),
    # ---------------- actor separation ----------------------------------- #
    Gate(
        "G-21",
        "actor-separation",
        "_validation.py",
        "the actor-separation primitive every four-party check is built from",
        "    if first == second:",
        "    if False:",
    ),
    Gate(
        "G-22",
        "actor-separation",
        "envelopes.py",
        "the approval envelope's publisher-is-not-approver check",
        """        require_distinct_actors(
            self.approval_authority_identity,
            self.publisher_submission_envelope.publisher_identity,""",
        """        require_distinct_actors(
            self.approval_authority_identity,
            self.approval_authority_identity + "-x",""",
    ),
    Gate(
        "G-23",
        "actor-separation",
        "chain.py",
        "the submission record's registry-is-not-publisher check",
        """        require_distinct_actors(
            self.declared_registry_authority_identity,
            self.publisher_submission_envelope.publisher_identity,""",
        """        require_distinct_actors(
            self.declared_registry_authority_identity,
            self.declared_registry_authority_identity + "-x",""",
    ),
    Gate(
        "G-24",
        "actor-separation",
        "chain.py",
        "the admission decision's registry-is-not-approver check",
        """        require_distinct_actors(
            self.submission_record.declared_registry_authority_identity,
            self.approval_envelope.approval_authority_identity,""",
        """        require_distinct_actors(
            self.submission_record.declared_registry_authority_identity,
            self.submission_record.declared_registry_authority_identity + "-x",""",
    ),
    Gate(
        "G-25",
        "actor-separation",
        "chain.py",
        "the revocation event's revoker-is-not-registry check",
        """        require_distinct_actors(
            self.revocation_envelope.revoker_identity,
            self.registration_event.registry_authority_identity,""",
        """        require_distinct_actors(
            self.revocation_envelope.revoker_identity,
            self.revocation_envelope.revoker_identity + "-x",""",
    ),
    # ---------------- refusal-reason coupling ---------------------------- #
    Gate(
        "G-26",
        "outcome-coupling",
        "chain.py",
        "the rule that a REJECTED admission decision must carry a refusal reason",
        "            if self.declared_refusal_reason is None:",
        "            if False:",
    ),
    Gate(
        "G-27",
        "outcome-coupling",
        "chain.py",
        "the rule that an ADMITTED admission decision must not carry one",
        "        elif self.declared_refusal_reason is not None:",
        "        elif False:",
    ),
    # ---------------- encoder discipline --------------------------------- #
    Gate(
        "G-28",
        "encoder",
        "canonical.py",
        "the float rejection",
        "    if isinstance(value, float):",
        "    if False:",
    ),
    Gate(
        "G-29",
        "encoder",
        "canonical.py",
        "the NFC requirement in the encoder",
        '    if unicodedata.normalize("NFC", value) != value:',
        "    if False:",
    ),
    Gate(
        "G-30",
        "encoder",
        "canonical.py",
        "the aware-datetime requirement in the encoder",
        "    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:",
        "    if False:",
    ),
    Gate(
        "G-31",
        "encoder",
        "canonical.py",
        "the sealed registry's identity comparison, replaced with a "
        "dict-membership check a metaclass can forge",
        "            if cls is registered_cls:",
        "            if cls == registered_cls:",
    ),
    Gate(
        "G-32",
        "encoder",
        "canonical.py",
        "the seal itself — allowing the contract-type registry to be widened "
        "after package initialization",
        "        if sealed:",
        "        if False:",
    ),
    # ---------------- validation primitives ------------------------------ #
    Gate(
        "G-33",
        "validation",
        "_validation.py",
        "the exact-type primitive, replaced with isinstance so a subclass "
        "passes",
        '''    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} "
            f"(got {type(value).__name__}); subclasses and duck-typed "''',
        '''    if not isinstance(value, expected):
        raise _fail(
            f"{name} must be exactly a {expected.__name__} "
            f"(got {type(value).__name__}); subclasses and duck-typed "''',
    ),
    Gate(
        "G-34",
        "validation",
        "_validation.py",
        "the closed-enum primitive, so a bare string spelling of a member is "
        "accepted",
        '''    if type(value) is not expected:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} member "''',
        '''    if False:
        raise _fail(
            f"{name} must be exactly a {expected.__name__} member "''',
    ),
    Gate(
        "G-35",
        "validation",
        "_validation.py",
        "the detached-signature encoding gate",
        "    if not _ED25519_HEX_RE.match(text):",
        "    if False:",
    ),
    Gate(
        "G-36",
        "validation",
        "_validation.py",
        "the pinned signing-frame constant gate, so a caller-chosen frame is "
        "accepted",
        "    if text != expected:",
        "    if False:",
    ),
    Gate(
        "G-37",
        "validation",
        "_validation.py",
        "the digest single-spelling gate",
        "    if not _SHA256_RE.match(text):",
        "    if False:",
    ),
    # ---------------- scope, binding and vocabulary ----------------------- #
    Gate(
        "G-38",
        "scope",
        "requests.py",
        "the platform scope expectation's kind gate",
        "        if self.scope.kind is not BenchmarkScopeKind.PLATFORM_WIDE:",
        "        if False:",
    ),
    Gate(
        "G-39",
        "scope",
        "requests.py",
        "the tenant scope expectation's kind gate",
        "        if self.scope.kind is not BenchmarkScopeKind.TENANT:",
        "        if False:",
    ),
    Gate(
        "G-40",
        "transition-binding",
        "binding.py",
        "the bound-payload exact-type gate",
        "    if type(payload) is not expected_cls:",
        "    if False:",
    ),
    Gate(
        "G-41",
        "transition-binding",
        "binding.py",
        "the bound-payload required-declared_outcome gate",
        "        if actual is not required_outcome:",
        "        if False:",
    ),
    Gate(
        "G-42",
        "transition-binding",
        "lifecycle.py",
        "the closed-relation membership test",
        "    return to_state in BENCHMARK_REGISTRATION_TRANSITIONS[from_state]",
        "    return True",
    ),
    Gate(
        "G-43",
        "vocabulary",
        "reasons.py",
        "the import-time guard that BR-1's frozen prefix and frozen set agree",
        "if frozenset(_BR1_PREFIX) != BR1_BENCHMARK_REFUSAL_REASONS:",
        "if False:",
    ),
    Gate(
        "G-44",
        "vocabulary",
        "reasons.py",
        "the BR-1-declaration-order source of the composite prefix, replaced "
        "with the frozenset whose iteration order is a hash artifact",
        "_BR1_PREFIX: tuple = tuple(BenchmarkRefusalReason)",
        "_BR1_PREFIX: tuple = tuple(BR1_BENCHMARK_REFUSAL_REASONS)",
    ),
    Gate(
        "G-45",
        "vocabulary",
        "reasons.py",
        "the fault-class exact-type gate",
        "    if type(reason) is not BenchmarkRegistryRefusalReason:",
        "    if False:",
    ),
    # ---------------- no-authority derivations ---------------------------- #
    Gate(
        "G-46",
        "no-authority",
        "_authority.py",
        "the permanently-False derivation itself",
        "    def _always_false(self) -> bool:\n        return False",
        "    def _always_false(self) -> bool:\n        return True",
    ),
    Gate(
        "G-47",
        "no-authority",
        "_authority.py",
        "the guard that refuses to overwrite a class's own declaration of a "
        "no-authority property",
        "        if name in cls.__dict__:\n            raise TypeError(\n                f\"{cls.__name__} already declares {name!r}; the five \"",
        "        if False:\n            raise TypeError(\n                f\"{cls.__name__} already declares {name!r}; the five \"",
    ),
    # ---------------- approval interval ----------------------------------- #
    Gate(
        "G-48",
        "validation",
        "envelopes.py",
        "the approval envelope's strictly-ordered validity interval gate",
        "        if not self.validity_from < self.validity_to:",
        "        if False:",
    ),
    # ---------------- BR-2B planning (kernel + planning) ------------------ #
    Gate(
        "G-49",
        "planning-fail-closed",
        "planning.py",
        "the fail-closed refusal when an unoccupied slot is handed an occupant",
        """        if occupant_record is not None:
            return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)
        return plan_transition(snapshot, _S.SUBMITTED)""",
        """        return plan_transition(snapshot, _S.SUBMITTED)""",
    ),
    Gate(
        "G-50",
        "planning-fail-closed",
        "planning.py",
        "the fail-closed refusal when the asserted occupant sits at another locator",
        """    if occupant_envelope.coordinate != snapshot.coordinate:
        return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)""",
        """    if False:
        return _refuse(snapshot, _S.SUBMITTED, _R.STALE_REGISTRY_SNAPSHOT)""",
    ),
    Gate(
        "G-51",
        "planning-idempotence",
        "planning.py",
        "the canonical-byte comparison D-06 requires for idempotence",
        "    return canonical_bytes(proposed_record) == canonical_bytes(occupant_record)",
        "    return True",
    ),
    Gate(
        "G-52",
        "planning-rejection-only",
        "planning.py",
        "the unequal-locator branch that keeps confusable handling rejection-only",
        """        return _refuse(snapshot, _S.SUBMITTED, _R.CONFUSABLE_COORDINATE)""",
        """        return plan_transition(snapshot, _S.SUBMITTED)""",
    ),
    Gate(
        "G-53",
        "planning-totality",
        "kernel.py",
        "the ADMITTED -> REJECTED record-presence gate, through the total layer",
        """            and self.snapshot.asserted_registration_record_presence
            is not _P.NO_RECORD_APPENDED""",
        """            and False""",
    ),
    Gate(
        "G-54",
        "boundary-plan-consumption",
        "planning.py",
        "the plan-consumption boundary, attacked with an aliased parameter on a "
        "private helper — the exact shape the substring rule walked past",
        """def _refuse(
    snapshot: BenchmarkRegistrySnapshotAssertion,
    to_state: BenchmarkRegistrationState,
    reason: BenchmarkRegistryRefusalReason,
) -> BenchmarkTransitionRefusal:""",
        """_PlanAlias = BenchmarkTransitionPlan


def _apply(plan: Optional[_PlanAlias]) -> None:
    return None


def _refuse(
    snapshot: BenchmarkRegistrySnapshotAssertion,
    to_state: BenchmarkRegistrationState,
    reason: BenchmarkRegistryRefusalReason,
) -> BenchmarkTransitionRefusal:""",
    ),
    Gate(
        "G-55",
        "boundary-plan-consumption",
        "planning.py",
        "the same boundary, attacked with an unannotated parameter — skipped "
        "rather than failed by the previous gate",
        """def is_byte_identical_resubmission(""",
        """def _apply(plan) -> None:
    return None


def is_byte_identical_resubmission(""",
    ),
    Gate(
        "G-56",
        "boundary-return-widening",
        "planning.py",
        "the planning-outcome alias, widened to admit a registry event — "
        "invisible to a gate that read the alias name as a string",
        """BenchmarkPlanningOutcome = Union[
    BenchmarkTransitionPlan, BenchmarkTransitionRefusal
]""",
        """from .chain import BenchmarkRegistrationEventPayload as _Event

BenchmarkPlanningOutcome = Union[
    BenchmarkTransitionPlan, BenchmarkTransitionRefusal, _Event
]""",
    ),
]


def _snapshot(destination: pathlib.Path) -> None:
    shutil.copytree(
        PKG,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "build", "dist", "*.egg-info", ".pytest_cache"
        ),
    )


def _restore(pristine: pathlib.Path, working: pathlib.Path) -> None:
    shutil.rmtree(working, ignore_errors=True)
    shutil.copytree(pristine, working)


def _tree_manifest(root: pathlib.Path) -> dict:
    """``{relative path: sha256}`` for every file under ``root``.

    Bytecode is excluded from the snapshot, so a ``.pyc`` appearing here at all
    would mean something wrote one despite ``PYTHONDONTWRITEBYTECODE`` — which
    is exactly the condition that can mask a mutation, so it is surfaced rather
    than filtered out.
    """

    manifest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            manifest[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    return manifest


def _assert_pristine(working: pathlib.Path, expected: dict, gate_id: str) -> None:
    """Prove the working tree is byte-identical to the proven-green baseline.

    The baseline suite runs once, on a tree whose hashes are recorded here.
    Asserting that each restore reproduces those exact bytes is what makes that
    single run stand for "the baseline passes before this mutation" — a restore
    that silently left a previous mutant behind, or dropped a stray ``.pyc``,
    would otherwise turn every later result into a measurement of the wrong
    tree.
    """

    actual = _tree_manifest(working)
    if actual != expected:
        added = sorted(set(actual) - set(expected))
        removed = sorted(set(expected) - set(actual))
        changed = sorted(
            p for p in set(actual) & set(expected) if actual[p] != expected[p]
        )
        raise RuntimeError(
            f"{gate_id}: the restored tree is not the pristine baseline "
            f"(added={added[:3]} removed={removed[:3]} changed={changed[:3]}); "
            "a sweep run against a drifted tree measures nothing"
        )


def _assert_mutant_loaded(working: pathlib.Path, gate) -> str:
    """Prove the interpreter actually imports the mutated source.

    Editing a file on disk is not evidence that the run under measurement used
    it. A stale ``__pycache__`` entry, a shadowing entry earlier on
    ``sys.path``, or a package resolved from the real repository instead of the
    working copy would all produce a green suite against **unmutated** code —
    reported as SURVIVED, and read as a missing gate that is in fact present.

    So the check is made from inside a subprocess with the same environment the
    suite gets, and it asks the import system rather than the filesystem:
    :func:`inspect.getsource` reads through the module's own loader, so it
    reflects what Python imported. The module's ``__file__`` must also resolve
    inside the working copy.

    A mutation that makes the module **refuse to import** is the strongest kill
    there is — several gates in this package are import-time structural
    invariants — so that case is reported as a kill, not as an unprovable
    result. It is still proven rather than assumed: the traceback must name the
    mutated file inside the working copy, which only happens if the interpreter
    executed it.

    Returns a short status used as the ledger's ``first_failure`` when the
    mutant is refused at import; raises only when neither outcome can be
    established.
    """

    module = f"ugence_benchmark_registry_authority.contracts.{gate.module[:-3]}"
    target = working / SRC_REL / "contracts" / gate.module
    probe = (
        "import inspect,pathlib,traceback\n"
        f"here = pathlib.Path({str(working)!r}).resolve()\n"
        f"target = pathlib.Path({str(target)!r}).resolve()\n"
        "disk = target.read_text()\n"
        f"assert {gate.new!r} in disk, 'mutated text absent from the file on disk'\n"
        "try:\n"
        f"    import {module} as m\n"
        "except Exception as exc:\n"
        "    tb = ''.join(traceback.format_exc())\n"
        "    assert str(target) in tb, 'import failed without executing the mutant'\n"
        "    print('MUTANT-REFUSED-AT-IMPORT', type(exc).__name__, str(exc)[:90])\n"
        "else:\n"
        "    f = pathlib.Path(m.__file__).resolve()\n"
        "    assert here in f.parents, f'loaded {f}, outside the working copy'\n"
        "    src = inspect.getsource(m)\n"
        f"    assert {gate.new!r} in src, 'mutated text absent from the loaded module'\n"
        # Only for a genuine replacement. An additive mutation's new text
        # contains the original, so the original legitimately remains and
        # demanding its absence would report a correctly applied insertion as an
        # unprovable mutant.
        + (
            f"    assert {gate.old!r} not in src, 'original text still present'\n"
            if gate.old not in gate.new
            else ""
        )
        + "    print('MUTANT-LOADED')\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(working / "src"), str(BR1_SRC), str(working / "tests")]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(working),
    )
    if "MUTANT-LOADED" in result.stdout:
        return ""
    if "MUTANT-REFUSED-AT-IMPORT" in result.stdout:
        return "import:" + result.stdout.split("MUTANT-REFUSED-AT-IMPORT", 1)[
            1
        ].strip()
    raise RuntimeError(
        f"{gate.gate_id}: could not prove the mutant was loaded — "
        f"{(result.stderr or result.stdout).strip().splitlines()[-1:]}"
    )



def _first_failure(output: str) -> str:
    for line in output.splitlines():
        if line.startswith("FAILED "):
            return line[len("FAILED ") :].strip()
        if line.startswith("FAIL  "):
            return line[len("FAIL  ") :].strip()
        if line.startswith("ERROR "):
            return line[len("ERROR ") :].strip()
    for line in output.splitlines():
        if " failed" in line or "Error" in line:
            return line.strip()
    return "(no named failure in output)"


def _run_suite(working: pathlib.Path):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(working / "src"), str(BR1_SRC), str(working / "tests")]
    )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    suite = subprocess.run(
        [sys.executable, "-m", "pytest", str(working / "tests"), "-q",
         "-p", "no:cacheprovider", "-x"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(working),
    )
    if suite.returncode != 0:
        return False, f"test:{_first_failure(suite.stdout + suite.stderr)}"
    probes = subprocess.run(
        [sys.executable, str(working / "adversarial_probes.py")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(working),
    )
    if probes.returncode != 0:
        return False, f"probe:{_first_failure(probes.stdout + probes.stderr)}"
    return True, ""


#: Survivors classified after the sweep, so a survivor is explained rather than
#: hidden. Production behaviour was **not** changed to move any gate out of this
#: list; where a survivor was moved to KILLED it was by adding a test for a
#: requirement the ratification already states, never by editing the package.
SURVIVOR_CLASSIFICATIONS: dict = {
    "G-12": (
        "SHADOWED by G-11. G-11 proves the two nested paths reach "
        "byte-identical publisher envelopes; identical bytes necessarily hash "
        "to identical digests, so with G-11 in place removing G-12 changes no "
        "observable behaviour. G-12 is retained as defence in depth: if G-11 "
        "were ever weakened to a structural comparison, G-12 would be the gate "
        "that still refused a mismatch. Killing it in isolation would require "
        "a hash collision."
    ),
    "G-28": (
        "SHADOWED by construction-time validation and by G-17. No "
        "caller-constructible path can place a float in a contract field: "
        "every field is validated at construction, and graph revalidation "
        "(G-17) re-runs those validators before the encoder is reached, so a "
        "float planted by object.__setattr__ is refused before the encoder's "
        "own float branch executes. The branch is unreachable defence in depth "
        "against a future field type, not a live gate."
    ),
    "G-29": (
        "SHADOWED by require_canonical_str and by G-17, for the same reason as "
        "G-28: NFC is required at construction and re-checked by revalidation, "
        "so the encoder's own NFC branch is never the first refusal."
    ),
    "G-30": (
        "SHADOWED by require_aware_datetime and by G-17, for the same reason "
        "as G-28: a naive datetime is refused at construction and again by "
        "revalidation before the encoder formats it."
    ),
    "G-43": (
        "EQUIVALENT while BR-1 is frozen. The guard fires only if BR-1's "
        "BenchmarkRefusalReason enum and BR1_BENCHMARK_REFUSAL_REASONS ever "
        "disagree, which cannot happen against the frozen 0.1.0 layer this "
        "package pins. Killing it would require shipping a mutated BR-1, which "
        "the freeze matrix exists to prevent and which this sweep deliberately "
        "does not do. The BR-1 freeze matrix (verify_br1_freeze_matrix.py) is "
        "the gate that would catch that drift independently."
    ),
}


def main() -> int:
    print("=" * 78)
    print("BR-2A GATE INVENTORY AND MEASURED GATE-DELETION MUTATION SWEEP")
    print("=" * 78)
    by_category: dict = {}
    for gate in GATES:
        by_category.setdefault(gate.category, []).append(gate.gate_id)
    print(f"gates inventoried: {len(GATES)}")
    for category in sorted(by_category):
        print(f"  {category:28s} {len(by_category[category]):2d}  "
              f"{', '.join(by_category[category])}")
    print("-" * 78)

    work = pathlib.Path(tempfile.mkdtemp(prefix="br2a-mutants-"))
    pristine = work / "pristine"
    working = work / "working"
    ledger = []
    try:
        _snapshot(pristine)

        # Baseline: the pristine tree must pass, or every KILLED result below
        # would be meaningless.
        _restore(pristine, working)
        passed, detail = _run_suite(working)
        if not passed:
            print(f"BASELINE FAILED on the pristine tree: {detail}")
            return 1
        baseline_manifest = _tree_manifest(working)

        # HARNESS CONTROL — a check that cannot fail proves nothing. Apply a
        # real mutation, revert the file underneath it, and require
        # _assert_mutant_loaded to object. If it stays silent, every
        # "MUTANT-LOADED" below is worthless and the sweep must not proceed.
        control_gate = GATES[0]
        control_path = working / SRC_REL / "contracts" / control_gate.module
        control_gate.apply(working)
        control_path.write_text(
            control_path.read_text().replace(control_gate.new, control_gate.old)
        )
        try:
            _assert_mutant_loaded(working, control_gate)
        except RuntimeError:
            print("harness control: a reverted mutant is correctly detected as "
                  "not loaded")
        else:
            print("HARNESS CONTROL FAILED: _assert_mutant_loaded accepted a tree "
                  "whose mutation had been reverted; every result below would be "
                  "unfounded")
            return 1
        _restore(pristine, working)
        _assert_pristine(working, baseline_manifest, "harness-control")

        print("baseline: the pristine tree passes the suite and the probes")
        print(f"baseline: {len(baseline_manifest)} files hashed; every restore "
              "below is proven byte-identical to this tree before mutating")
        print("-" * 78)

        for gate in GATES:
            _restore(pristine, working)
            try:
                _assert_pristine(working, baseline_manifest, gate.gate_id)
                gate.apply(working)
                import_refusal = _assert_mutant_loaded(working, gate)
            except (LookupError, RuntimeError) as exc:
                print(f"ERROR {gate.gate_id}: {exc}")
                ledger.append(
                    {
                        "gate": gate.gate_id,
                        "category": gate.category,
                        "module": gate.module,
                        "description": gate.description,
                        "result": "ERROR",
                        "first_failure": str(exc),
                    }
                )
                continue
            if import_refusal:
                # The mutated module refuses to import at all. Proven executed,
                # and killed by the package's own import-time invariant.
                passed, detail = False, import_refusal
            else:
                passed, detail = _run_suite(working)
            result = "SURVIVED" if passed else "KILLED"
            ledger.append(
                {
                    "gate": gate.gate_id,
                    "category": gate.category,
                    "module": gate.module,
                    "description": gate.description,
                    "result": result,
                    "first_failure": detail,
                }
            )
            marker = "ok   " if result == "KILLED" else "SURV "
            print(f"{marker} {gate.gate_id} {result:8s} {gate.category:22s} "
                  f"{detail[:70]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    killed = [row for row in ledger if row["result"] == "KILLED"]
    survived = [row for row in ledger if row["result"] == "SURVIVED"]
    errored = [row for row in ledger if row["result"] == "ERROR"]

    print("-" * 78)
    print(f"TOTALS  inventoried {len(GATES)}  killed {len(killed)}  "
          f"survived {len(survived)}  errored {len(errored)}")
    if survived:
        print("\nSURVIVOR CLASSIFICATION (each survivor is explained, not hidden):")
        for row in survived:
            classification = SURVIVOR_CLASSIFICATIONS.get(
                row["gate"], "UNCLASSIFIED — this is a real gap until explained"
            )
            print(f"  {row['gate']}  {classification}")
            print(f"        {row['description']}")
    if errored:
        print("\nERRORED MUTATIONS — the inventory has drifted from the source:")
        for row in errored:
            print(f"  {row['gate']}: {row['first_failure']}")

    (PKG / "gate_inventory.json").write_text(
        json.dumps(
            {
                "distribution": "ugence-benchmark-registry-authority",
                "milestone": "BR-2A",
                "note": (
                    "Complete inventory of every load-bearing gate, and the "
                    "measured result of neutralizing each one in turn against "
                    "the full suite and the author-owned adversarial probes. "
                    "Production behaviour was not changed to chase a "
                    "zero-survivor number; any survivor is classified as "
                    "equivalent, shadowed (naming the shadowing gate), or a "
                    "real gap. Regenerate by running gate_mutation_sweep.py."
                ),
                "gates_inventoried": len(GATES),
                "killed": len(killed),
                "survived": len(survived),
                "errored": len(errored),
                "categories": {c: sorted(g) for c, g in by_category.items()},
                "ledger": ledger,
                "survivor_classifications": SURVIVOR_CLASSIFICATIONS,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"\nledger written to {(PKG / 'gate_inventory.json').name}")

    if errored:
        return 1
    if survived and any(
        row["gate"] not in SURVIVOR_CLASSIFICATIONS for row in survived
    ):
        print("\nUNCLASSIFIED SURVIVOR(S) PRESENT — sweep is not clean")
        return 1
    print("\nGATE-DELETION MUTATION SWEEP COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
