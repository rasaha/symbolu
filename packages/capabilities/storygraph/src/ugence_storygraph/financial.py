"""A small financial ontology so the account-takeover story runs end to end.

Fragments and an extractor for the canonical account-takeover-and-transfer
example. This exists so a story graph can be exercised against the *real*
analyzer pipeline (linkage → ledger → instances), demonstrating that the
structural edges (same beneficiary, same device, order, timing) are what decide
the outcome — not a raw event count.

The extractor stamps the financial entities (``account``, ``beneficiary``,
``device``, ``destination``, ``amount``) onto each fragment instance so the story
graph's ``SameEntity`` edges can be evaluated.
"""

from __future__ import annotations

from .model import PERSISTENT, ExtractContext, FragmentInstance, Fragment, Ontology

CRED_RESET = "CRED_RESET"
DEVICE_NEW = "DEVICE_NEW"
BENEFICIARY_ADD = "BENEFICIARY_ADD"
LIMIT_UP = "LIMIT_UP"
TRANSFER = "TRANSFER"

_OPS = {
    "PASSWORD_RESET": (CRED_RESET, "credential reset"),
    "DEVICE_REGISTER": (DEVICE_NEW, "new device registration"),
    "BENEFICIARY_ADD": (BENEFICIARY_ADD, "beneficiary added"),
    "LIMIT_INCREASE": (LIMIT_UP, "transaction limit increased"),
    "TRANSFER": (TRANSFER, "value transfer initiated"),
}

FINANCIAL_FRAGMENTS = {
    fid: Fragment(fid, title, title, decay_class=PERSISTENT)
    for fid, title in [
        (CRED_RESET, "Credential reset"), (DEVICE_NEW, "New device"),
        (BENEFICIARY_ADD, "Beneficiary added"), (LIMIT_UP, "Limit increase"),
        (TRANSFER, "Value transfer")]
}


def extract_financial(event: dict, ctx: ExtractContext) -> list[FragmentInstance]:
    op = event.get("operation")
    mapped = _OPS.get(op)
    if mapped is None:
        return []
    frag, note = mapped
    a = event.get("arguments", {}) or {}
    entities = dict(ctx.entities)
    for k in ("account", "beneficiary", "device", "destination", "amount"):
        v = event.get(k, a.get(k))
        if v is not None:
            entities[k] = str(v)
    return [FragmentInstance(
        fragment_id=frag, decay_class=PERSISTENT, tenant_id=ctx.tenant_id,
        correlation_id=ctx.correlation_id, sequence_id=ctx.sequence_id,
        event_id=ctx.event_id, idempotency_key=ctx.idempotency_key,
        operation=str(op), actor=ctx.entities.get("actor", ""), entities=entities,
        note=note, position=ctx.position, at_epoch=ctx.at_epoch)]


FINANCIAL_ONTOLOGY = Ontology(
    ontology_id="ctd.financial.account", version="1.0.0",
    fragments=FINANCIAL_FRAGMENTS, recipes=(), extract=extract_financial)
