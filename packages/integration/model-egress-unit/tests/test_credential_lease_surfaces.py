"""Every routine surface a credential could escape through, asserted closed.

This file is the regression record for the adversarial pass of 2026-09-13 and the
owner's correction of the same day. Four leaks were found; all four are covered here.
The class under test is deliberately **not a dataclass** and has ``__slots__``, so there
is no ``__dict__`` to hand out and no ``fields()`` to walk.

The boundary this file does NOT claim: it does not protect against arbitrary
same-process memory inspection. Code in this process can reach the slot through
``CredentialLease.__slots__``, ``gc.get_referents`` or a debugger, and no Python object
can prevent that. What is asserted is that every surface a serializer, logger, debugger
repr, exception renderer or copy routine touches *without being asked to go looking*
yields nothing.
"""

from __future__ import annotations

import copy
import dataclasses
import gc
import io
import json
import logging
import pickle
import traceback
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ugence_model_egress_unit import CredentialLease, CustodyRefused

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

#: One string, searched for in full in every captured value below. It is a marker, not a
#: credential shape, so this file carries no credential-shaped literal.
SECRET = "MARKER-CREDENTIAL-VALUE-THAT-MUST-NEVER-APPEAR"


def lease(**over) -> CredentialLease:
    kwargs = dict(lease_id="lease-0001", custody_authority_id="gsm-nonprod",
                  credential_profile="openai-validation", vendor="openai", tenant_id=uuid4(),
                  secret_version_ref="projects/p/secrets/s/versions/3", issued_at=NOW,
                  expires_at=NOW + timedelta(minutes=5), is_production_authoritative=False,
                  _secret=SECRET)
    kwargs.update(over)
    return CredentialLease(**kwargs)


# --- the structural guarantees ---------------------------------------------------------

def test_the_lease_has_no_instance_dict_and_vars_raises():
    held = lease()
    assert not hasattr(held, "__dict__"), "a __dict__ is a routine surface and there must be none"
    with pytest.raises(AttributeError):
        held.__dict__  # noqa: B018
    with pytest.raises(TypeError):
        vars(held)
    assert "_held" in CredentialLease.__slots__


def test_the_lease_is_not_a_dataclass_so_asdict_and_astuple_cannot_walk_it():
    held = lease()
    assert not dataclasses.is_dataclass(held)
    with pytest.raises(TypeError):
        dataclasses.asdict(held)
    with pytest.raises(TypeError):
        dataclasses.astuple(held)
    with pytest.raises(TypeError):
        dataclasses.fields(held)


def test_the_lease_is_immutable_after_birth():
    held = lease()
    with pytest.raises(AttributeError, match="immutable"):
        held.lease_id = "other"
    with pytest.raises(AttributeError, match="immutable"):
        held._held = "other"
    with pytest.raises(AttributeError, match="immutable"):
        del held.lease_id


# --- every capture surface, in one table -------------------------------------------------

def _captures(held: CredentialLease) -> dict:
    """Every routine surface, each either a value or the exception it raised."""

    def attempt(name, call):
        try:
            return name, call()
        except Exception as exc:  # noqa: BLE001 - a refusal is a valid, and better, answer
            return name, f"<raised {type(exc).__name__}: {exc}>"

    surfaces = [
        ("repr", lambda: repr(held)),
        ("str", lambda: str(held)),
        ("format", lambda: format(held)),
        ("format-spec", lambda: f"{held:>10}"),
        ("f-string", lambda: f"{held}"),
        ("f-string-repr", lambda: f"{held!r}"),
        ("percent-s", lambda: "%s" % (held,)),
        ("as_record", lambda: json.dumps(held.as_record())),
        ("vars", lambda: vars(held)),
        ("dict", lambda: held.__dict__),
        ("dir-values", lambda: {n: getattr(held, n, None) for n in dir(held) if not n.startswith("_")}),
        ("asdict", lambda: dataclasses.asdict(held)),
        ("astuple", lambda: dataclasses.astuple(held)),
        ("json", lambda: json.dumps(held)),
        ("json-default-str", lambda: json.dumps(held, default=str)),
        ("json-default-repr", lambda: json.dumps(held, default=repr)),
        ("json-default-vars", lambda: json.dumps(held, default=vars)),
        ("pickle", lambda: pickle.dumps(held)),
        ("copy", lambda: copy.copy(held)),
        ("deepcopy", lambda: copy.deepcopy(held)),
        ("reduce", lambda: held.__reduce__()),
        ("reduce_ex", lambda: held.__reduce_ex__(2)),
        ("getstate", lambda: held.__getstate__()),
        ("eq-self", lambda: held == held),
        ("eq-other", lambda: held == lease()),
        ("hash", lambda: hash(held)),
    ]
    return dict(attempt(name, call) for name, call in surfaces)


@pytest.mark.parametrize("surface", sorted(_captures(lease())))
def test_no_routine_surface_yields_the_credential(surface):
    captured = _captures(lease())[surface]
    assert SECRET not in repr(captured), f"{surface} yielded the credential"
    assert SECRET not in str(captured), f"{surface} yielded the credential"


def test_copying_and_pickling_are_explicitly_refused_rather_than_silently_partial():
    held = lease()
    for call in (lambda: pickle.dumps(held), lambda: copy.copy(held), lambda: copy.deepcopy(held)):
        with pytest.raises(TypeError, match="never pickled, copied or serialized"):
            call()


def test_equality_and_hashing_are_identity_and_never_read_the_credential():
    one, two = lease(), lease()
    assert one == one and one != two, "two leases with identical content are still two leases"
    assert hash(one) != hash(two) or one is two
    assert {one, two} == {one, two} and len({one, two}) == 2


# --- rendering surfaces: exceptions, logging, structured logging --------------------------

def test_an_expired_lease_refuses_without_rendering_the_credential():
    held = lease()
    with pytest.raises(CustodyRefused) as info:
        held.use(lambda s: s, now=NOW + timedelta(hours=1))
    rendered = "".join(traceback.format_exception(type(info.value), info.value, info.value.__traceback__))
    assert SECRET not in str(info.value) and SECRET not in rendered
    chain, exc = [], info.value
    while exc is not None and exc not in chain:
        chain.append(exc)
        exc = exc.__context__ or exc.__cause__
    assert all(SECRET not in str(link) for link in chain)


def test_an_exception_raised_inside_use_does_not_render_the_credential_from_its_frame():
    """A consumer that raises puts the secret in a live frame. The traceback renders the
    frame's *source line*, never its locals, so the rendered text carries nothing."""

    held = lease()

    def explode(secret: str) -> None:
        raise RuntimeError("the consumer failed")

    with pytest.raises(RuntimeError) as info:
        held.use(explode, now=NOW)
    rendered = "".join(traceback.format_exception(type(info.value), info.value, info.value.__traceback__))
    assert SECRET not in rendered


@pytest.mark.parametrize("emit", [
    lambda log, held: log.info("lease %s", held),
    lambda log, held: log.info("lease %r", held),
    lambda log, held: log.info(f"lease {held}"),
    lambda log, held: log.info("lease", extra={"lease": held}),
    lambda log, held: log.info("lease %(lease)s", {"lease": held}),
    lambda log, held: log.error("lease %s", held, exc_info=RuntimeError("boom")),
])
def test_no_logging_or_structured_logging_shape_renders_the_credential(emit):
    held = lease()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s %(asctime)s"))
    log = logging.getLogger(f"lease-surfaces-{id(emit)}")
    log.handlers = [handler]
    log.setLevel(logging.DEBUG)
    log.propagate = False
    emit(log, held)
    assert SECRET not in stream.getvalue()


def test_a_structured_logger_that_serializes_its_record_cannot_reach_the_credential():
    """The common structured-logging shape: take the record's fields and JSON them. The
    lease is not serializable and ``vars`` on it raises, so the encoder fails loudly
    rather than emitting a secret."""

    held = lease()
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "lease", (), None)
    record.lease = held
    for default in (None, str, repr):
        try:
            emitted = json.dumps(record.__dict__, default=default)
        except TypeError:
            continue
        assert SECRET not in emitted


# --- the honest boundary -------------------------------------------------------------------

def test_the_credential_is_reachable_only_through_use():
    held = lease()
    assert held.use(lambda s: s, now=NOW) == SECRET
    public = [name for name in dir(held) if not name.startswith("_")]
    for name in public:
        value = getattr(held, name)
        assert SECRET not in repr(value() if name == "as_record" else value), name


def test_the_stated_boundary_is_same_process_inspection_and_it_is_not_claimed_closed():
    """Documented rather than asserted away: a slot is still reachable in-process. This
    test exists so the claim in the docstring stays true and is not quietly widened."""

    held = lease()
    assert any(SECRET == referent for referent in gc.get_referents(held)) or True
    assert getattr(held, "_held") == SECRET, "in-process inspection reaches it, as documented"
