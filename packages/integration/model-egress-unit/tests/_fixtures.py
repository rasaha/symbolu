"""Builders for the ratified request shape, shared by every suite."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from ugence_model_egress_unit import (
    EgressRequest,
    MinimizedUnit,
    reference_clearance,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
LEASE = timedelta(minutes=5)
VENDOR = "reference-vendor"
MODEL = "reference-model-a"

#: The ordered units a run admitted. Order is part of the digest, so these are a
#: sequence and never a set.
CONTEXT = (
    MinimizedUnit(unit_id="unit-1", text="the first admitted unit", token_count=5),
    MinimizedUnit(unit_id="unit-2", text="the second admitted unit", token_count=6),
)


def binding(tenant, *, vendor=VENDOR, model=MODEL, **kw):
    return reference_clearance(tenant_id=tenant, vendor=vendor, model=model, **kw)


def request(tenant, *, context=CONTEXT, submitted_at=NOW, valid_for=timedelta(hours=2),
            authorization=None, parameters=None, request_id=None,
            correlation_id=None):
    return EgressRequest.create(
        request_id=request_id or uuid.uuid4(),
        tenant_id=tenant,
        correlation_id=correlation_id or uuid.uuid4(),
        submitted_at=submitted_at,
        not_valid_after=submitted_at + valid_for,
        authorization=authorization or binding(tenant),
        minimized_context=context,
        parameters=parameters or {"temperature_milli": 0},
    )
