"""Single source of truth for this distribution's version and posture."""

from __future__ import annotations

__version__ = "0.1.0"

#: This distribution is the PRODUCTION-FORM custody adapter: it is the one LP-8 names
#: as the only adapter that may materialize the credential for the validation. It is
#: production-*form* and not production-*use*: the deployment it serves is the
#: dedicated non-production commissioning path, and production needs its own record.
MATURITY = "PRODUCTION_FORM_NON_PRODUCTION_SCOPE"

#: The adapter name LP-8's execution-posture check requires
#: (``ugence_model_egress_unit.PRODUCTION_FORM_CUSTODY_ADAPTER``). Asserted equal by
#: ``tests/test_boundaries.py`` rather than duplicated by hope.
PRODUCTION_FORM_ADAPTER_NAME = "PRODUCTION_FORM_SECRET_MANAGER_ADAPTER"

#: No model-vendor egress exists in this distribution and none is configurable. This
#: package talks to Google Secret Manager and to nothing else, and only through an
#: injected client built at the deployment composition root.
LIVE_VENDOR_EGRESS = False

#: The one Secret Manager method this adapter may call. Listing secrets or versions is
#: not in the grant and not in the client protocol.
PERMITTED_SECRET_MANAGER_METHOD = "AccessSecretVersion"
