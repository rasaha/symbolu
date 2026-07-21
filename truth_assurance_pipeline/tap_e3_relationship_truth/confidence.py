"""
Multidimensional relationship confidence (Section 13).

Each component reflects what the active baseline actually resolved: an undetected
dimension gets a low component score, so a low component can never be hidden behind a
high aggregate (the band is floored by the minimum component — see
``RelationshipConfidence.band``).
"""

from __future__ import annotations

from typing import Mapping

from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    Direction, Modality, Polarity, RelationshipConfidence, SourceProvenance, Temporality,
)


def assess(cfg, subject, object_, rtype: RelationshipType, direction: Direction,
           polarity: Polarity, modality: Modality, temporality: Temporality,
           scope: Mapping[str, str], conditions, prov: SourceProvenance
           ) -> RelationshipConfidence:
    subj_res = 1.0 if subject else 0.0
    obj_res = 1.0 if object_ else 0.3
    pred_res = 1.0 if rtype not in (RelationshipType.OTHER, RelationshipType.UNMAPPED) else 0.2

    if not cfg.normalize:
        dir_conf = 0.5                       # raw order, direction not resolved
    elif direction is Direction.UNCLEAR:
        dir_conf = 0.3
    else:
        dir_conf = 1.0

    pol_conf = 1.0 if cfg.polarity_modality else 0.3
    mod_conf = 1.0 if cfg.polarity_modality else 0.3
    temp_conf = 1.0 if cfg.temporal_scope_cond else 0.3
    scope_conf = (1.0 if scope else 0.7) if cfg.temporal_scope_cond else 0.3
    cond_conf = 1.0 if cfg.temporal_scope_cond else 0.3
    prov_comp = 1.0 if prov.is_complete() else 0.0
    xevi = 1.0 if cfg.consolidate else 0.6

    return RelationshipConfidence(
        subject_resolution=subj_res, object_resolution=obj_res,
        predicate_resolution=pred_res, direction_confidence=dir_conf,
        polarity_confidence=pol_conf, modality_confidence=mod_conf,
        temporal_confidence=temp_conf, scope_confidence=scope_conf,
        condition_confidence=cond_conf, provenance_completeness=prov_comp,
        cross_evidence_consistency=xevi)
