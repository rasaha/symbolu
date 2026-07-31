"""Shipped ontologies: the composite-threat recipe libraries.

A recipe is deliberately data, not code — the "story of a crime" is expressed as
"which benign fragments, assembled, constitute which dangerous capability". The
library is versioned (``version``) so a finding can name the exact recipe set it
was evaluated against, the same way the gate names its ``policy_version``.

The recipes are intentionally conservative and few. This detector's job is not to
enumerate every attack; it is to notice when a *correlation* of individually
admissible steps has quietly assembled a coherent offensive capability, and to
ask a human to look — before the last part is fitted.
"""

from __future__ import annotations

from . import fragments as F
from .model import Fragment, Ontology, Recipe

# ---------------------------------------------------------------------------
# Digital ontology
# ---------------------------------------------------------------------------
_DIGITAL_FRAGMENTS = {
    f.fragment_id: f
    for f in [
        Fragment(F.RECON_MAP, "Reconnaissance / discovery",
                 "enumerated resources, secrets, or topology", "casing the target"),
        Fragment(F.CREDENTIAL_MATERIAL, "Credential material",
                 "obtained a secret, token, or key", "key to a lock"),
        Fragment(F.PRIVILEGE, "Elevated privilege",
                 "acquired rights beyond the starting scope", "a uniform / badge"),
        Fragment(F.DATA_ACCESS, "Reach into stored data",
                 "touched or moved data in a store", "hand into the vault"),
        Fragment(F.EGRESS_PATH, "Outbound path",
                 "opened a route out of the boundary", "an open door outward"),
        Fragment(F.OBSERVABILITY_GAP, "Observability gap",
                 "reduced monitoring or logging", "cutting the CCTV feed"),
        Fragment(F.PERSISTENCE, "Persistence / foothold",
                 "established durable access or lock-in", "changing the locks"),
        Fragment(F.STAGING, "Staging capacity",
                 "provisioned resource to stage from", "a getaway vehicle"),
    ]
}

_DIGITAL_RECIPES = (
    Recipe(
        recipe_id="DATA_EXFILTRATION_ASSEMBLY",
        name="Data-exfiltration capability",
        narrative=(
            "individually-admissible steps have assembled the means to remove "
            "data: credential material to authenticate, a reach into stored "
            "data, and an outbound path to carry it out"
        ),
        required=frozenset({F.CREDENTIAL_MATERIAL, F.DATA_ACCESS, F.EGRESS_PATH}),
        optional=frozenset({F.RECON_MAP, F.OBSERVABILITY_GAP}),
        physical_analogue="barrel + firing mechanism + ammunition = a firearm",
    ),
    Recipe(
        recipe_id="PRIVILEGE_TAKEOVER_ASSEMBLY",
        name="Account/privilege takeover capability",
        narrative=(
            "reconnaissance, an elevation of privilege, and a durable foothold "
            "have been assembled into standing control of the environment"
        ),
        required=frozenset({F.RECON_MAP, F.PRIVILEGE, F.PERSISTENCE}),
        optional=frozenset({F.OBSERVABILITY_GAP}),
        physical_analogue="lock survey + master key cut + changing the locks",
    ),
    Recipe(
        recipe_id="COVERED_SABOTAGE_ASSEMBLY",
        name="Covered-sabotage capability",
        narrative=(
            "an observability gap, a reach into stored data, and a durable "
            "foothold have been assembled into the means to alter systems while "
            "blind to defenders"
        ),
        required=frozenset({F.OBSERVABILITY_GAP, F.DATA_ACCESS, F.PERSISTENCE}),
        optional=frozenset({F.STAGING}),
        physical_analogue="cut the alarm + reach the safe + hold the keys",
    ),
)

DIGITAL_ONTOLOGY = Ontology(
    ontology_id="ctd.digital.actiongate",
    version="1.0.0",
    fragments=_DIGITAL_FRAGMENTS,
    recipes=_DIGITAL_RECIPES,
    extract=F.extract_digital,
)

# ---------------------------------------------------------------------------
# Physical firearm illustration ontology (the original prompt, made runnable)
# ---------------------------------------------------------------------------
_FIREARM_FRAGMENTS = {
    f.fragment_id: f
    for f in [
        Fragment(F.BARREL_STOCK, "Barrel stock",
                 "a rigid tube/rod that can become a barrel", "steel rod / pipe"),
        Fragment(F.FIRING_MECHANISM, "Firing mechanism",
                 "a striker/trigger able to initiate firing", "piston / trigger / nail"),
        Fragment(F.PROJECTILE_FEED, "Projectile / feed",
                 "projectiles or a feed device", "bearings / magazine"),
        Fragment(F.PROPELLANT, "Propellant",
                 "an energetic charge", "powder / match heads"),
    ]
}

_FIREARM_RECIPES = (
    Recipe(
        recipe_id="IMPROVISED_FIREARM_ASSEMBLY",
        name="Improvised firearm",
        narrative=(
            "separately-acquired, individually-innocuous parts have assembled "
            "into a working firearm: a barrel, a firing mechanism, and a means "
            "to propel a projectile"
        ),
        required=frozenset({F.BARREL_STOCK, F.FIRING_MECHANISM, F.PROJECTILE_FEED}),
        optional=frozenset({F.PROPELLANT}),
        physical_analogue="the prompt's original example",
    ),
)

PHYSICAL_FIREARM_ONTOLOGY = Ontology(
    ontology_id="ctd.physical.firearm",
    version="1.0.0",
    fragments=_FIREARM_FRAGMENTS,
    recipes=_FIREARM_RECIPES,
    extract=F.extract_physical_firearm,
)

ONTOLOGIES = {
    DIGITAL_ONTOLOGY.ontology_id: DIGITAL_ONTOLOGY,
    PHYSICAL_FIREARM_ONTOLOGY.ontology_id: PHYSICAL_FIREARM_ONTOLOGY,
}
