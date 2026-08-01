"""Shipped ontologies: the versioned capability-recipe libraries.

A recipe is data, not code — a prohibited/high-risk capability is expressed as
"which benign fragments, under which structural constraints, assemble it". The
library is versioned so a finding names the exact recipe (``recipe_id@version``)
it was evaluated against, the way the gate names its ``policy_version``.

Recipes are intentionally few and conservative. The analyzer's job is not to
enumerate every attack; it is to notice when a *linked* set of individually
admissible actions has assembled a coherent, encoded high-risk capability, and to
raise advisory sequence-risk evidence for an authoritative policy to weigh.
"""

from __future__ import annotations

from . import fragments as F
from .model import Fragment, Ontology, Recipe

# ---------------------------------------------------------------------------
# Digital ontology (the product target: AI-agent / infrastructure workflows)
# ---------------------------------------------------------------------------
_DIGITAL_FRAGMENTS = {
    fid: Fragment(fid, title, desc, decay_class=F.DIGITAL_DECAY[fid], physical_analogue=pa)
    for fid, title, desc, pa in [
        (F.RECON_MAP, "Reconnaissance / discovery",
         "enumerated resources, secrets, or topology", "casing the target"),
        (F.CREDENTIAL_MATERIAL, "Credential material",
         "obtained a secret, token, or key", "a key to a lock"),
        (F.PRIVILEGE, "Elevated privilege",
         "acquired rights beyond the starting scope", "a badge/uniform"),
        (F.DATA_ACCESS, "Protected-data access",
         "touched or moved data in a protected store", "a hand in the vault"),
        (F.EGRESS_PATH, "Outbound transfer path",
         "opened an untrusted/external route out of the boundary", "an open door out"),
        (F.OBSERVABILITY_GAP, "Observability gap",
         "reduced monitoring or logging", "cutting the CCTV feed"),
        (F.PERSISTENCE, "Persistence / foothold",
         "established durable access or lock-in", "changing the locks"),
        (F.STAGING, "Staging capacity",
         "provisioned resource to stage from", "a getaway vehicle"),
    ]
}

_BENIGN_TAGS = frozenset({
    "approved_data_migration", "authorized_security_test", "backup",
    "disaster_recovery", "compliance_export", "pre_authorized_deployment",
})

_DIGITAL_RECIPES = (
    Recipe(
        recipe_id="DATA_EXFILTRATION_ASSEMBLY", version="1.1.0",
        name="Data-exfiltration capability",
        required=frozenset({F.CREDENTIAL_MATERIAL, F.DATA_ACCESS, F.EGRESS_PATH}),
        optional=frozenset({F.RECON_MAP, F.OBSERVABILITY_GAP}),
        # credential + data access must precede the untrusted outbound path
        ordering=((F.CREDENTIAL_MATERIAL, F.EGRESS_PATH),
                  (F.DATA_ACCESS, F.EGRESS_PATH)),
        actor_scope="ANY_ACTOR", resource_scope="ANY",
        benign_exclusions=_BENIGN_TAGS,
        severity="HIGH", recommended_consequence="HOLD_FOR_REVIEW",
        physical_analogue="barrel + firing mechanism + ammunition = a firearm",
        explanation_template=(
            "Individually admissible actions have accumulated the credential-access, "
            "protected-data-access, and outbound-transfer fragments required by the "
            "versioned data-exfiltration recipe."),
    ),
    Recipe(
        recipe_id="PRIVILEGE_TAKEOVER_ASSEMBLY", version="1.1.0",
        name="Account/privilege takeover capability",
        required=frozenset({F.RECON_MAP, F.PRIVILEGE, F.PERSISTENCE}),
        optional=frozenset({F.OBSERVABILITY_GAP}),
        ordering=((F.RECON_MAP, F.PRIVILEGE), (F.PRIVILEGE, F.PERSISTENCE)),
        benign_exclusions=_BENIGN_TAGS,
        severity="HIGH", recommended_consequence="HOLD_FOR_REVIEW",
        physical_analogue="lock survey + master key cut + changing the locks",
        explanation_template=(
            "Linked actions have accumulated reconnaissance, privilege elevation, and "
            "a durable foothold — the fragments of the versioned takeover recipe."),
    ),
    Recipe(
        recipe_id="COVERED_SABOTAGE_ASSEMBLY", version="1.0.0",
        name="Covered-sabotage capability",
        required=frozenset({F.OBSERVABILITY_GAP, F.DATA_ACCESS, F.PERSISTENCE}),
        optional=frozenset({F.STAGING}),
        benign_exclusions=_BENIGN_TAGS,
        severity="HIGH", recommended_consequence="HOLD_FOR_REVIEW",
        physical_analogue="cut the alarm + reach the safe + hold the keys",
        explanation_template=(
            "Linked actions have accumulated an observability gap, protected-data "
            "access, and a durable foothold — the versioned covered-sabotage recipe."),
    ),
)

DIGITAL_ONTOLOGY = Ontology(
    ontology_id="ctd.digital.actiongate", version="1.1.0",
    fragments=_DIGITAL_FRAGMENTS, recipes=_DIGITAL_RECIPES, extract=F.extract_digital,
)

# ---------------------------------------------------------------------------
# Physical firearm illustration ontology (synthetic; kept only as illustration)
# ---------------------------------------------------------------------------
_FIREARM_FRAGMENTS = {
    fid: Fragment(fid, title, desc, decay_class=F.FIREARM_DECAY[fid], physical_analogue=pa)
    for fid, title, desc, pa in [
        (F.BARREL_STOCK, "Barrel stock", "a rigid tube/rod", "steel rod / pipe"),
        (F.FIRING_MECHANISM, "Firing mechanism", "a striker/trigger",
         "piston / trigger / nail"),
        (F.PROJECTILE_FEED, "Projectile / feed", "projectiles or a feed",
         "bearings / magazine"),
        (F.PROPELLANT, "Propellant", "an energetic charge", "powder / match heads"),
    ]
}

_FIREARM_RECIPES = (
    Recipe(
        recipe_id="IMPROVISED_FIREARM_ASSEMBLY", version="1.0.0",
        name="Improvised firearm",
        required=frozenset({F.BARREL_STOCK, F.FIRING_MECHANISM, F.PROJECTILE_FEED}),
        optional=frozenset({F.PROPELLANT}),
        severity="CRITICAL", recommended_consequence="HOLD_FOR_REVIEW",
        physical_analogue="the original prompt's synthetic example",
        explanation_template=(
            "Separately acquired parts have accumulated the barrel, firing-mechanism, "
            "and projectile-feed fragments of the synthetic firearm recipe."),
    ),
)

PHYSICAL_FIREARM_ONTOLOGY = Ontology(
    ontology_id="ctd.physical.firearm", version="1.0.0",
    fragments=_FIREARM_FRAGMENTS, recipes=_FIREARM_RECIPES,
    extract=F.extract_physical_firearm,
)

ONTOLOGIES = {
    DIGITAL_ONTOLOGY.ontology_id: DIGITAL_ONTOLOGY,
    PHYSICAL_FIREARM_ONTOLOGY.ontology_id: PHYSICAL_FIREARM_ONTOLOGY,
}
