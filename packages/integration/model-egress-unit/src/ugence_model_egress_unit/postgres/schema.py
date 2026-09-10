"""The exchange schema: three roles, two tables, forced row-level security.

Why three roles
---------------
``meu_exchange_owner`` owns the schema and every table in it, and **cannot log
in**. Neither application role owns anything, so neither can ``DROP``, ``ALTER``
or disable a policy on the tables it uses. Compromising the worker's credentials
gets an attacker the worker's grants and nothing structural; there is no login
path to the role that could change the shape of the exchange.

``meu_worker`` is the governance worker: it submits requests, reads results and
acknowledges consumption. ``meu_unit`` is the egress unit: it claims pending
requests and writes results. The grants are deliberately asymmetric — the worker
can ``INSERT`` a request but never ``UPDATE`` one, and the unit can ``UPDATE`` a
request's disposition but never ``INSERT`` one. Neither side can forge the other
side of the conversation.

Why the row security is FORCEd
------------------------------
``ENABLE ROW LEVEL SECURITY`` alone does not bind the table's owner, so a policy
that looks airtight is bypassed by exactly the role that owns the data. ``FORCE``
is what makes tenant isolation true for every role rather than for every role
somebody remembered. The package's RLS tests assert this by removing ``FORCE``
and observing the cross-tenant read succeed — the property is measured, not
asserted.

Why the tenant setting is read with ``current_setting(..., false)``
-------------------------------------------------------------------
The two-argument form with ``missing_ok=true`` returns ``NULL`` when the setting
is absent, and ``tenant_id = NULL`` is not an error — it is simply false for
every row. A session that forgot to establish a tenant identity would therefore
read an empty table and conclude there was no work, which is the most dangerous
possible answer: indistinguishable from a correct one. The one-argument form
raises instead. **A session with no tenant identity cannot read or write
anything**, and finds out immediately.
"""

from __future__ import annotations

__all__ = [
    "SCHEMA_NAME",
    "OWNER_ROLE",
    "WORKER_ROLE",
    "UNIT_ROLE",
    "TENANT_SETTING",
    "ROLE_NAMES",
]

#: This package's own schema. Nothing here lives in ``public``: a dedicated
#: schema is what lets the owner role own precisely this exchange and nothing
#: else in the database.
SCHEMA_NAME = "meu_exchange"

#: The non-login owner. Every object in :data:`SCHEMA_NAME` belongs to it.
OWNER_ROLE = "meu_exchange_owner"

#: The governance worker: submits requests, reads and acknowledges results.
WORKER_ROLE = "meu_worker"

#: The egress unit: claims requests, writes results.
UNIT_ROLE = "meu_unit"

#: The session setting carrying tenant identity. Read without ``missing_ok``, so
#: an unset session fails closed rather than reading an empty exchange.
TENANT_SETTING = "ugence.tenant_id"

ROLE_NAMES = (OWNER_ROLE, WORKER_ROLE, UNIT_ROLE)
