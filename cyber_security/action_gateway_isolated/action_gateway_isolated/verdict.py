"""Preregistered mechanical kill criterion.

Emits exactly one of:
  * ISOLATED_GATE_THESIS_SUPPORTED
  * ISOLATED_GATE_THESIS_NOT_SUPPORTED
  * ISOLATION_NOT_PROVEN

The criteria are fixed BEFORE the run (see README/THREAT_MODEL) and evaluated
mechanically from the environment facts + attack results. Missing infrastructure
forces ISOLATION_NOT_PROVEN — never a positive verdict.
"""

from __future__ import annotations

SUPPORTED = "ISOLATED_GATE_THESIS_SUPPORTED"
NOT_SUPPORTED = "ISOLATED_GATE_THESIS_NOT_SUPPORTED"
NOT_PROVEN = "ISOLATION_NOT_PROVEN"

# environment capabilities that MUST be truly enforced (else NOT_PROVEN)
REQUIRED_ENV = ("cluster", "asymmetric", "netns_isolation", "user_separation",
                "durable_store", "conditional_write", "audit_key_separation")


def decide(env: dict, attacks: list) -> dict:
    missing = [k for k in REQUIRED_ENV if not env.get(k)]
    if missing:
        return {"verdict": NOT_PROVEN, "reason": f"unenforced prerequisites: {missing}",
                "missing": missing}

    # any successful unauthorized mutation or unblocked attack -> NOT_SUPPORTED
    breaches = [a for a in attacks if not a.get("blocked")]
    if breaches:
        return {"verdict": NOT_SUPPORTED,
                "reason": f"{len(breaches)} attack(s) not blocked",
                "breaches": [b["id"] for b in breaches]}

    return {"verdict": SUPPORTED,
            "reason": "all attacks blocked under enforced isolation, asymmetric authz, "
                      "durable replay, conditional writes, and separated audit keys",
            "attacks_blocked": len(attacks)}
