"""Deterministic in-memory S1-S8 paired episode construction and encoding."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from .config import FROZEN_MODEL_RECIPE, FROZEN_TRAIN_RECIPE, ModelRecipe, SCENARIO_IDS
from .execution import guard_seed
from .schema import CanonicalEpisode, Entity, Evidence, Query, Relation, StructuredOutput
from .serializers import assert_information_equivalent, serialize_b0, serialize_b1
from .tokenizer import LexicalTokenizer

Arm = Literal["B0", "B1"]


@dataclass(frozen=True)
class PairedEpisode:
    episode: CanonicalEpisode
    b0: str
    b1: str
    fact_hash: str

    @property
    def b0_text(self) -> str:
        return self.b0

    @property
    def b1_text(self) -> str:
        return self.b1

    @property
    def output_json(self) -> str:
        return self.episode.authoritative_output.canonical_json()


@dataclass(frozen=True)
class EncodedArm:
    arm: Arm
    input_ids: tuple[int, ...]
    labels: tuple[int, ...]
    prompt_token_count: int
    output_token_count: int
    fact_hash: str

    @property
    def prompt_tokens(self) -> int:
        return self.prompt_token_count

    @property
    def output_tokens(self) -> int:
        return self.output_token_count


# The trainer consumes encoded arms as training examples.
EncodedExample = EncodedArm


class SyntheticEpisodeGenerator:
    """Local-RNG deterministic generator. It never mutates global RNG state."""

    def __init__(
        self,
        seed: int,
        token: str | None = None,
    ) -> None:
        guard_seed(seed, token)
        self.seed = seed
        self._rng = random.Random(seed)

    def _suffix(self) -> str:
        return f"{self._rng.randrange(100, 999):03d}"

    def _base_ids(self) -> tuple[str, str, str]:
        suffix = self._suffix()
        return f"i{suffix}", f"v{suffix}", f"c{suffix}"

    def build(self, scenario_id: str) -> CanonicalEpisode:
        if scenario_id not in SCENARIO_IDS:
            raise ValueError(f"unknown scenario: {scenario_id}")
        builder = getattr(self, f"_{scenario_id.lower()}")
        return builder()

    def generate(self, scenario_id: str) -> CanonicalEpisode:
        return self.build(scenario_id)

    def generate_all(self) -> tuple[CanonicalEpisode, ...]:
        return tuple(self.build(scenario_id) for scenario_id in SCENARIO_IDS)

    def _s1(self) -> CanonicalEpisode:
        invoice_id, vendor_a, _ = self._base_ids()
        vendor_b = f"v{int(vendor_a[1:]) + 1}"
        tenant = "t01"
        evidence_ref = "e101"
        output = StructuredOutput(
            "ANSWERED", vendor_b, "approved_vendor", True, (evidence_ref,), tenant, "MATCH_FOUND"
        )
        return CanonicalEpisode(
            "s1-duplicate-name",
            "S1",
            tenant,
            Query("select_relation_target", "invoice", invoice_id, "approved_vendor"),
            (
                Entity("invoice", invoice_id, tenant, attributes=(("amount", "4200"),)),
                Entity("vendor", vendor_a, tenant, "atlas", (("suffix", "41"),)),
                Entity("vendor", vendor_b, tenant, "atlas", (("suffix", "42"),)),
            ),
            (
                Relation(
                    "approved_vendor", "invoice", invoice_id, "vendor", vendor_b, evidence_ref, tenant
                ),
            ),
            (Evidence(evidence_ref, "approved_vendor", tenant),),
            output,
        )

    def _s2(self) -> CanonicalEpisode:
        invoice_id, _, contract_id = self._base_ids()
        contract_b = f"c{int(contract_id[1:]) + 1}"
        tenant, evidence_ref = "t01", "e202"
        output = StructuredOutput(
            "ANSWERED", contract_id, "belongs_to_contract", True, (evidence_ref,), tenant, "MATCH_FOUND"
        )
        return CanonicalEpisode(
            "s2-foreign-key",
            "S2",
            tenant,
            Query("select_relation_target", "invoice", invoice_id, "belongs_to_contract"),
            (
                Entity("invoice", invoice_id, tenant, attributes=(("amount", "4200"),)),
                Entity("contract", contract_id, tenant, attributes=(("status", "active"),)),
                Entity("contract", contract_b, tenant, attributes=(("status", "draft"),)),
            ),
            (
                Relation(
                    "belongs_to_contract",
                    "invoice",
                    invoice_id,
                    "contract",
                    contract_id,
                    evidence_ref,
                    tenant,
                ),
            ),
            (Evidence(evidence_ref, "belongs_to_contract", tenant),),
            output,
        )

    def _s3(self) -> CanonicalEpisode:
        suffix = self._suffix()
        employee_id, department_id = f"u{suffix}", f"d{suffix}"
        tenant, evidence_ref = "t01", "e303"
        output = StructuredOutput(
            "ANSWERED", department_id, "member_of", True, (evidence_ref,), tenant, "RELATION_SUPPORTED"
        )
        return CanonicalEpisode(
            "s3-supported-relation",
            "S3",
            tenant,
            Query("validate_relation", "employee", employee_id, "member_of"),
            (
                Entity("employee", employee_id, tenant, "mira"),
                Entity("department", department_id, tenant, "research"),
            ),
            (Relation("member_of", "employee", employee_id, "department", department_id, evidence_ref, tenant),),
            (Evidence(evidence_ref, "member_of", tenant),),
            output,
        )

    def _s4(self) -> CanonicalEpisode:
        invoice_id, vendor_a, _ = self._base_ids()
        vendor_b = f"v{int(vendor_a[1:]) + 2}"
        tenant, evidence_ref = "t01", "e404"
        output = StructuredOutput(
            "ANSWERED", vendor_a, "approved_vendor", True, (evidence_ref,), tenant, "IDENTITY_MATCH"
        )
        return CanonicalEpisode(
            "s4-attribute-disambiguation",
            "S4",
            tenant,
            Query("select_entity", "invoice", invoice_id, "approved_vendor"),
            (
                Entity("invoice", invoice_id, tenant, attributes=(("region", "west"),)),
                Entity("vendor", vendor_a, tenant, "nova", (("region", "west"),)),
                Entity("vendor", vendor_b, tenant, "nova", (("region", "east"),)),
            ),
            (Relation("approved_vendor", "invoice", invoice_id, "vendor", vendor_a, evidence_ref, tenant),),
            (Evidence(evidence_ref, "approved_vendor", tenant),),
            output,
        )

    def _s5(self) -> CanonicalEpisode:
        invoice_id, vendor_id, contract_id = self._base_ids()
        tenant, ev1, ev2 = "t01", "e505", "e515"
        output = StructuredOutput(
            "ANSWERED", contract_id, "belongs_to_contract", True, (ev1,), tenant, "EVIDENCE_FOUND"
        )
        return CanonicalEpisode(
            "s5-evidence-selection",
            "S5",
            tenant,
            Query("select_evidence", "invoice", invoice_id, "belongs_to_contract"),
            (
                Entity("invoice", invoice_id, tenant),
                Entity("contract", contract_id, tenant),
                Entity("vendor", vendor_id, tenant),
            ),
            (
                Relation("belongs_to_contract", "invoice", invoice_id, "contract", contract_id, ev1, tenant),
                Relation("approved_vendor", "invoice", invoice_id, "vendor", vendor_id, ev2, tenant),
            ),
            (
                Evidence(ev1, "belongs_to_contract", tenant, "supports", True),
                Evidence(ev2, "approved_vendor", tenant, "supports", True),
            ),
            output,
        )

    def _s6(self) -> CanonicalEpisode:
        invoice_id, _, contract_id = self._base_ids()
        tenant = "t01"
        output = StructuredOutput(
            "INSUFFICIENT_EVIDENCE",
            None,
            "belongs_to_contract",
            None,
            (),
            tenant,
            "NO_AUTHORIZED_RELATION",
        )
        return CanonicalEpisode(
            "s6-no-match",
            "S6",
            tenant,
            Query("select_relation_target", "invoice", invoice_id, "belongs_to_contract"),
            (Entity("invoice", invoice_id, tenant), Entity("contract", contract_id, tenant)),
            (),
            (),
            output,
        )

    def _s7(self) -> CanonicalEpisode:
        invoice_id, _, contract_id = self._base_ids()
        tenant, foreign_tenant, evidence_ref = "t01", "t99", "e707"
        output = StructuredOutput(
            "INSUFFICIENT_EVIDENCE",
            None,
            "belongs_to_contract",
            None,
            (),
            tenant,
            "TENANT_BLOCKED",
        )
        return CanonicalEpisode(
            "s7-cross-tenant",
            "S7",
            tenant,
            Query("select_relation_target", "invoice", invoice_id, "belongs_to_contract"),
            (
                Entity("invoice", invoice_id, tenant),
                Entity("contract", contract_id, foreign_tenant, attributes=(("status", "active"),)),
            ),
            (
                Relation(
                    "belongs_to_contract",
                    "invoice",
                    invoice_id,
                    "contract",
                    contract_id,
                    evidence_ref,
                    foreign_tenant,
                ),
            ),
            (Evidence(evidence_ref, "belongs_to_contract", foreign_tenant),),
            output,
        )

    def _s8(self) -> CanonicalEpisode:
        suffix = self._suffix()
        employee_id, department_id = f"u{suffix}", f"d{suffix}"
        tenant, evidence_ref = "t01", "e808"
        output = StructuredOutput(
            "ANSWERED", department_id, "member_of", False, (evidence_ref,), tenant, "RELATION_UNSUPPORTED"
        )
        return CanonicalEpisode(
            "s8-contradicted-relation",
            "S8",
            tenant,
            Query("validate_relation", "employee", employee_id, "member_of"),
            (Entity("employee", employee_id, tenant), Entity("department", department_id, tenant)),
            (Relation("member_of", "employee", employee_id, "department", department_id, evidence_ref, tenant),),
            (Evidence(evidence_ref, "member_of", tenant, "contradicts", True),),
            output,
        )


def make_pair(episode: CanonicalEpisode) -> PairedEpisode:
    fact_hash = assert_information_equivalent(episode)
    return PairedEpisode(episode, serialize_b0(episode), serialize_b1(episode), fact_hash)


def encode_pair_arm(
    pair: PairedEpisode,
    arm: Arm,
    tokenizer: LexicalTokenizer | None = None,
    recipe: ModelRecipe = FROZEN_MODEL_RECIPE,
) -> EncodedArm:
    tokenizer = tokenizer or LexicalTokenizer()
    ignore = FROZEN_TRAIN_RECIPE.ignore_index
    serialized = pair.b0 if arm == "B0" else pair.b1
    prompt = serialized + FROZEN_TRAIN_RECIPE.output_marker
    prompt_ids = tokenizer.encode(prompt)
    output_ids = tokenizer.encode(pair.output_json)
    n_prompt, n_output = len(prompt_ids), len(output_ids)
    input_prefix = 1 + n_prompt  # bos + prompt (the model-visible input before generation)
    if input_prefix > recipe.max_input_tokens:
        raise ValueError(
            f"{arm} input has {input_prefix} tokens, exceeds the common {recipe.max_input_tokens}-token limit"
        )
    if n_output + 1 > recipe.max_output_tokens:
        raise ValueError(
            f"output has {n_output + 1} tokens, exceeds the {recipe.max_output_tokens}-token limit"
        )
    # input:  [bos, prompt..., output..., eos]
    input_ids = (tokenizer.bos_id, *prompt_ids, *output_ids, tokenizer.eos_id)
    if len(input_ids) > recipe.max_seq:
        raise ValueError("complete sequence exceeds frozen model context")
    # labels == the full sequence with bos+prompt masked; loss shifts internally so
    # logits[i] predict input_ids[i+1]. labels[-1] == eos; first supervised label at input_prefix.
    labels = (
        *(ignore for _ in range(input_prefix)),
        *output_ids,
        tokenizer.eos_id,
    )
    if len(labels) != len(input_ids):
        raise AssertionError("input/label length mismatch")
    return EncodedArm(
        arm,
        tuple(input_ids),
        tuple(labels),
        input_prefix,
        n_output,
        pair.fact_hash,
    )


def collate_encoded(batch):
    """Pad a batch of encoded examples: input_ids with PAD, labels with the ignore index."""
    import torch

    from .tokenizer import PAD_ID

    ignore = FROZEN_TRAIN_RECIPE.ignore_index
    width = max(len(item.input_ids) for item in batch)
    input_rows, label_rows = [], []
    for item in batch:
        pad = width - len(item.input_ids)
        input_rows.append(list(item.input_ids) + [PAD_ID] * pad)
        label_rows.append(list(item.labels) + [ignore] * pad)
    return (
        torch.tensor(input_rows, dtype=torch.long),
        torch.tensor(label_rows, dtype=torch.long),
    )
