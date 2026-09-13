"""Shared builders. Every digest is a caller input, as it is in the contracts."""

from __future__ import annotations

import hashlib

from ugence_change_effect_records import (
    AdmissionState,
    BlockingObligation,
    ClassificationRecord,
    ClosureEffectBundle,
    EffectClass,
    EvaluationStatus,
    JurisdictionalRoute,
    ObligationKind,
    PrimitiveEffect,
    PrimitiveEffectKind,
    RegistryEffectResult,
    chain_id,
    obligation_id,
)

REGISTRIES = (
    "subject_classes", "governance_roles", "observables", "context_predicates",
    "constraint_inputs", "identity_links", "obligated_actions",
)


def d(seed: str) -> str:
    """A full 64-hex digest standing for one the caller would have computed."""

    return hashlib.sha256(seed.encode()).hexdigest()


CHAIN = chain_id(
    tenant="tenant-1", candidate_digest=d("cand"), anomaly_family="family-7",
    family_seed_digest=d("seed"), chain_instance_id="inst-1",
)
OBLIGATION = obligation_id(
    chain=CHAIN, introducing_role="CLASSIFICATION",
    obligation_kind=ObligationKind.UNDERSIZED_CELL.value,
    coordinate="subject_classes/cell.1", ordinal=0,
)


def measured_results() -> tuple[RegistryEffectResult, ...]:
    return tuple(
        RegistryEffectResult(
            registry=r,
            evaluation_status=EvaluationStatus.MEASURED,
            effect_class=EffectClass.DESCRIPTIVE_STATE,
        )
        for r in REGISTRIES
    )


def classification(**overrides) -> ClassificationRecord:
    kwargs = dict(
        chain_id=CHAIN, tenant="tenant-1", candidate_digest=d("cand"),
        anomaly_family="family-7", chain_instance_id="inst-1",
        family_seed_digest=d("seed"), family_sample_digest=d("sample"),
        anchor_snapshot_digest=d("anchor"), current_snapshot_digest=d("current"),
        proposed_snapshot_digest=d("proposed"), evaluator_version="ev-1",
        replay_environment_digest=d("env"), model_code_digest=d("code"),
        policy_versions=("p-1",), delegation_table_version="dt-1",
        registry_list_version="rl-1", mapping_version="closure-bundle-mapping/2026-09-13",
        results=measured_results(), jurisdictional_route=JurisdictionalRoute.GERL_BASE,
        signer="classifier",
    )
    kwargs.update(overrides)
    return ClassificationRecord(**kwargs)


def obligation(**overrides) -> BlockingObligation:
    kwargs = dict(
        obligation_id=OBLIGATION, obligation_kind=ObligationKind.UNDERSIZED_CELL,
        coordinate="subject_classes/cell.1", ordinal=0,
    )
    kwargs.update(overrides)
    return BlockingObligation(**kwargs)


def bundle(**overrides) -> ClosureEffectBundle:
    kwargs = dict(
        obligation_id=OBLIGATION,
        mapping_version="closure-bundle-mapping/2026-09-13",
        evaluation_result_digest=d("eval"),
        effects=(
            PrimitiveEffect(
                kind=PrimitiveEffectKind.SET_CELL_MEASUREMENT,
                target="subject_classes/cell.1", value_digest=d("cell"),
            ),
        ),
        declared_write_set=("subject_classes/cell.1",),
    )
    kwargs.update(overrides)
    return ClosureEffectBundle(**kwargs)
