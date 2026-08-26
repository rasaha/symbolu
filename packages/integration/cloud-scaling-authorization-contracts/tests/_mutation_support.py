"""Load a copy of this package with exactly one canonical guard neutralised.

This exists so a regression test can prove, *inside the suite*, the two things a mutation
sweep would otherwise have to be trusted for:

* **Admission proof.** With the gate under test removed — and nothing else changed — the
  attack the test submits really does reach candidate construction. A test whose input was
  already refused by some earlier gate would pass with the gate under test unguarded, and
  prove nothing about it.
* **Misattribution proof.** With a *sibling* gate removed instead — one that shares the
  typed rejection reason, or that a reader might assume is doing the work — the attack is
  still refused. The kill therefore belongs to the gate under test and to no other.

Nothing here is a mock. The mutated package is the real package source with one ``if``
header rewritten to ``if False:``; every validator, digest and canonicalization is the
genuine one. The copy is disposable and the tracked worktree is never written to.

The guard numbering is the canonical inventory recomputed from the source being copied:
``raise`` sites that sit alone in the body of their immediately enclosing ``if``, taken in
source order over ``reconciliation.py`` then ``candidate.py``. It is recomputed rather than
hardcoded so a line-number shift cannot silently retarget a mutation.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import shutil
import sys
from typing import Any, Iterator

PKG_NAME = "ugence_cloud_scaling_authorization_contracts"
SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / PKG_NAME
IN_SCOPE = ("reconciliation.py", "candidate.py")


PERIPHERAL_SCOPE = ("attestation.py", "target.py")
"""Files the canonical inventory deliberately does **not** cover.

The canonical inventory is owner-ratified at 65 over ``IN_SCOPE``, and widening it would
move a ratified denominator. These two files nevertheless carry real admissions — the
signed policy ceiling and the schema identifiers among them — and "present in the source"
is not "executed by a sweep". :func:`peripheral_guards` inventories them **separately**,
so their guards can be neutralised and scored without touching the ratified 65. No claim
of exhaustive coverage follows from either inventory; the measured figures are reported in
``test_peripheral_guard_coverage_is_reported_honestly``.
"""


def canonical_guards(
    srcdir: pathlib.Path, scope: tuple[str, ...] = IN_SCOPE
) -> list[dict[str, Any]]:
    """The canonical in-scope guard inventory, in the audit's deterministic order."""

    strict: list[tuple[str, ast.If]] = []
    for path in sorted(srcdir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                child._parent = node  # type: ignore[attr-defined]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise):
                continue
            parent = getattr(node, "_parent", None)
            holder: Any = node
            found: ast.If | None = None
            while parent is not None:
                if isinstance(parent, ast.If) and any(s is holder for s in parent.body):
                    found = parent
                    break
                holder = parent
                parent = getattr(parent, "_parent", None)
            if found is not None and len(found.body) == 1 and found.body[0] is node:
                strict.append((path.name, found))
    guards: list[dict[str, Any]] = []
    for name in scope:
        for fname, ifnode in strict:
            if fname == name:
                guards.append(
                    {
                        "file": fname,
                        "if_line": ifnode.lineno,
                        "body_line": ifnode.body[0].lineno,
                        "cond": ast.unparse(ifnode.test),
                    }
                )
    return guards


def _neutralise(srcdir: pathlib.Path, guard: dict[str, Any]) -> None:
    path = srcdir / guard["file"]
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    start, end = guard["if_line"] - 1, guard["body_line"] - 1
    indent = lines[start][: len(lines[start]) - len(lines[start].lstrip())]
    lines[start:end] = [f"{indent}if False:  # guard neutralised for this proof\n"]
    path.write_text("".join(lines), encoding="utf-8")


class MutatedPackage:
    """The package, importable, with one guard removed. Use as a context manager."""

    def __init__(self, module: Any) -> None:
        self.module = module

    # -- artifact builders bound to THIS module's classes -------------------------------
    # The builder refuses anything that is not an *exact* instance of its own types, so the
    # three Phase 5 artifacts must be rebuilt against the mutated module. They are built
    # with the same values conftest uses, through the same public constructors.

    def attestation(
        self, *, recommendation_digest: str, issued_at: Any = None
    ) -> Any:
        """``issued_at`` overrides the genuine stamp.

        Without it a sweep of ``_require_utc``'s gates is vacuous: every guard number
        produces the same honest attestation, so the mutated half passes whatever was
        neutralised. The override is what lets a naive instant reach the gate under test.
        """

        from risk_authority.crypto import SigningKey, canonical_bytes

        import conftest as C

        payload = {
            "schema_version": "cloud-scaling-producer-attestation-evidence-1",
            "producer_id": C.PRODUCER_ID,
            "producer_key_id": C.PRODUCER_KEY_ID,
            "signature_algorithm": "ed25519",
            "signing_purpose": self.module.PRODUCER_SIGNING_PURPOSE,
            "recommendation_id": C.RECOMMENDATION_ID,
            "recommendation_digest": recommendation_digest,
            "issued_at": C.REC_TIME if issued_at is None else issued_at,
        }
        signature = SigningKey.from_seed(C.PRODUCER_SEED).sign(canonical_bytes(payload))
        return self.module.ProducerAttestationEvidence(
            producer_id=C.PRODUCER_ID,
            producer_key_id=C.PRODUCER_KEY_ID,
            signature_algorithm="ed25519",
            signature=signature.hex(),
            recommendation_id=C.RECOMMENDATION_ID,
            recommendation_digest=recommendation_digest,
            signing_purpose=self.module.PRODUCER_SIGNING_PURPOSE,
            signing_payload_digest=self.module.canonical_digest(payload),
            issued_at=C.REC_TIME if issued_at is None else issued_at,
        )

    def target_scope(
        self, projection: Any, *, max_magnitude: Any = None, max_delta: Any = None
    ) -> Any:
        """``max_magnitude``/``max_delta`` override the fixture ceilings.

        Needed to score the magnitude ceiling on its own: with both ceilings at their
        fixture values, an attack that clears one is caught by its sibling, and the
        neutralisation proves nothing about the guard it was aimed at.
        """

        import conftest as C

        context = projection.context
        return self.module.ExecutionTargetScope(
            tenant_id=projection.tenant_id,
            account_id=C.ACCOUNT_ID,
            environment=context.environment,
            region=context.region,
            zone=context.zone,
            namespace=None,
            compute_group=context.compute_group,
            resource_class=context.resource_class,
            action_type=context.action_type,
            magnitude_before=context.magnitude_before,
            requested_magnitude=context.magnitude_after,
            max_permitted_magnitude=(
                C.MAX_MAGNITUDE if max_magnitude is None else max_magnitude
            ),
            max_permitted_delta=C.MAX_DELTA if max_delta is None else max_delta,
        )

    def policy_binding(self, target_scope: Any) -> Any:
        from risk_authority.crypto import SigningKey, canonical_bytes

        policy_id, policy_version = "cloud-scaling.capacity-bounds", "3.1.0"
        body = dict(
            policy_id=policy_id,
            policy_version=policy_version,
            policy_artifact_digest=self.module.canonical_digest(
                {"policy": policy_id, "v": policy_version}
            ),
            policy_issuer="ugence.policy-authority",
            policy_key_id="policy-signing-key-7",
            target_scope_digest=target_scope.digest(),
            max_permitted_magnitude=target_scope.max_permitted_magnitude,
            max_permitted_delta=target_scope.max_permitted_delta,
            policy_signature_algorithm="ed25519",
        )
        payload = {"schema_version": "cloud-scaling-policy-target-binding-1", **body}
        signature = SigningKey.from_seed(bytes(range(64, 96))).sign(canonical_bytes(payload))
        return self.module.PolicyTargetBindingReference(
            policy_signature=signature.hex(),
            binding_digest=self.module.canonical_digest(payload),
            **body,
        )

    def policy_coordinate_binding(self, target_scope: Any) -> Any:
        """The V2 coordinate, built from the **mutated** module's own type.

        Built here rather than imported from ``conftest``: the builder admits exact types
        only, and a coordinate minted by the pristine package is a different class than the
        mutated copy's.
        """

        import hashlib

        from risk_authority.crypto import canonical_bytes

        policy_id, policy_version = "cloud-scaling.capacity-bounds", "3.1.0"
        digest = hashlib.sha256(
            canonical_bytes({"policy": policy_id, "v": policy_version, "body": "fixture"})
        ).hexdigest()
        body = dict(
            policy_family="capacity-bounds",
            policy_id=policy_id,
            policy_version=policy_version,
            policy_content_digest=digest,
            policy_scope="TENANT",
            policy_tenant_id=target_scope.tenant_id,
            policy_body_digest=digest,
            issuing_authority_id="ugence.policy-authority",
            key_id="policy-signing-key-7",
            signature_alg="ed25519",
            target_scope_digest=target_scope.digest(),
        )
        payload = {"schema_version": "cloud-scaling-policy-target-binding-2", **body}
        return self.module.PolicyTargetBindingReferenceV2(
            binding_digest=self.module.canonical_digest(payload), **body
        )

    def build(self, projection: Any, decision: Any, attestation: Any = None) -> Any:
        """Run the mutated package's REAL public builder on this projection/decision.

        ``attestation`` overrides the genuine one, for the sweeps whose attack lives on the
        attestation rather than the projection or the decision. It must be an instance of
        **this** module's ``ProducerAttestationEvidence`` — the builder admits exact types
        only — which is what :meth:`attestation` above is for.
        """

        scope = self.target_scope(projection)
        return self.module.build_capacity_authorization_candidate(
            projection=projection,
            decision=decision,
            producer_attestation=attestation if attestation is not None else self.attestation(
                recommendation_digest=projection.recommendation_digest
            ),
            policy_binding=self.policy_binding(scope),
            policy_coordinate_binding=self.policy_coordinate_binding(scope),
            target_scope=scope,
        )


def peripheral_guards(srcdir: pathlib.Path) -> list[dict[str, Any]]:
    """The separate inventory over :data:`PERIPHERAL_SCOPE`. Never mixed with the 65."""

    return canonical_guards(srcdir, PERIPHERAL_SCOPE)


def mutated_peripheral(tmp_path: pathlib.Path, guard_number: int) -> MutatedPackage:
    """Import a copy of this package with *peripheral* guard ``guard_number`` neutralised.

    Deliberately a separate entry point from :func:`mutated_package`: the two numbering
    spaces are disjoint, and a caller that confuses them neutralises the wrong guard.
    """

    dst = tmp_path / f"per{guard_number}"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, dst / PKG_NAME)
    guards = peripheral_guards(dst / PKG_NAME)
    # No ratified count is asserted here on purpose. The 65 is a governance number; this
    # inventory is a coverage instrument, and pinning it would invent a second denominator
    # nobody ratified. What *is* asserted is that the guard being neutralised is the one the
    # caller named — see ``peripheral_guard_condition``.
    _neutralise(dst / PKG_NAME, guards[guard_number - 1])

    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == PKG_NAME}
    for key in saved:
        del sys.modules[key]
    sys.path.insert(0, str(dst))
    try:
        module = importlib.import_module(PKG_NAME)
        importlib.import_module(f"{PKG_NAME}.reconciliation")
        importlib.import_module(f"{PKG_NAME}.candidate")
        return MutatedPackage(module)
    finally:
        sys.path.remove(str(dst))
        for key in [k for k in sys.modules if k.split(".")[0] == PKG_NAME]:
            del sys.modules[key]
        sys.modules.update(saved)


def peripheral_guard_condition(guard_number: int) -> str:
    """The source text of a peripheral guard's condition, for self-documenting asserts."""

    return peripheral_guards(SRC)[guard_number - 1]["cond"]


def mutated_package(tmp_path: pathlib.Path, guard_number: int) -> MutatedPackage:
    """Import a copy of this package with canonical guard ``guard_number`` neutralised.

    ``sys.modules`` is unwound around the import so the mutated copy never leaks into any
    other test, and the pristine package remains the one every other test sees.
    """

    dst = tmp_path / f"mut{guard_number}"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SRC, dst / PKG_NAME)
    guards = canonical_guards(dst / PKG_NAME)
    # 65 since the R-12b ordering repair. The lineage: 5B-1 brought the builder to 51, 5B-2 part 1 added R-9's
    # cross-tenant guard at 52, R-12 added five (three temporal-coherence guards plus the two
    # inside `_comparable_instant`) for 57, and R-12b adds seven in `reconciliation.py`: the
    # decision snapshot must carry `evaluated_at`, `expires_at` and `issued_at`; each outer
    # field must equal the value bound in the snapshot; and two orderings over the bound
    # instants — the decision cannot have been evaluated before the recommendation it decides
    # became valid, nor issued before the evaluation it binds was made.
    #
    # The 65th is `_bound_instant`'s **exact-string type gate**, not the awareness check that
    # helper once had — that check became unreachable once only canonical strings are admitted
    # and was removed. The two swapped one-for-one, which is why the count did not fall to 64,
    # and the type gate is written as `if type(value) is not str: raise` precisely so the sweep
    # inventories, neutralises and scores it: it is the only thing standing between a live
    # `datetime` subclass and both orderings. Owner-ratified; do not rewrite it into an
    # `else`-branch shape to reproduce the old denominator.
    #
    # The orderings moved off canonical strings onto parsed instants because `strftime` does
    # not zero-pad `%Y` below year 1000, so a three-digit year sorted above every four-digit
    # one and both orderings inverted. That work shifted every guard after `_require_datetime`
    # by +1.
    #
    # Adding R-12b's seven in `reconciliation.py` shifted every `candidate.py` guard by +7. The sweep's
    # numbered anchors are asserted against their condition text in
    # `test_the_canonical_guard_numbers_still_name_these_conditions`, so a shift fails loudly
    # rather than silently retargeting a mutation — which is exactly what it did here.
    # The count is asserted so a guard that disappears cannot go unnoticed.
    if len(guards) != 65:
        raise AssertionError(
            f"canonical inventory drifted: {len(guards)} in-scope guards, expected 65"
        )
    _neutralise(dst / PKG_NAME, guards[guard_number - 1])

    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == PKG_NAME}
    for key in saved:
        del sys.modules[key]
    sys.path.insert(0, str(dst))
    try:
        module = importlib.import_module(PKG_NAME)
        # Bind the mutated submodules too, then detach the whole tree from sys.modules so
        # the pristine package is restored for every later import.
        importlib.import_module(f"{PKG_NAME}.reconciliation")
        importlib.import_module(f"{PKG_NAME}.candidate")
        return MutatedPackage(module)
    finally:
        sys.path.remove(str(dst))
        for key in [k for k in sys.modules if k.split(".")[0] == PKG_NAME]:
            del sys.modules[key]
        sys.modules.update(saved)


def guard_condition(guard_number: int) -> str:
    """The source text of a canonical guard's condition, for self-documenting asserts."""

    return canonical_guards(SRC)[guard_number - 1]["cond"]
