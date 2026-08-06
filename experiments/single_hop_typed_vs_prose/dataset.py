"""Paired episode construction and deterministic synthetic fixtures."""
from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable, Sequence

import torch

from .config import BOS_ID, EOS_ID, FROZEN_MODEL_RECIPE, OUTPUT_MARKER, PAD_ID, ModelRecipe
from .schema import CanonicalEpisode, Entity, Evidence, Query, Relation, StructuredOutput
from .serializers import assert_information_equivalent, serialize_b0, serialize_b1
from .tokenizer import LexicalTokenizer


@dataclass(frozen=True)
class PairedEpisode:
    episode: CanonicalEpisode
    b0_text: str
    b1_text: str
    fact_hash: str

    def text_for_arm(self, arm: str) -> str:
        if arm == "B0":
            return self.b0_text
        if arm == "B1":
            return self.b1_text
        raise ValueError("arm must be B0 or B1")


@dataclass(frozen=True)
class EncodedExample:
    episode_id: str
    arm: str
    input_ids: tuple[int, ...]
    labels: tuple[int, ...]
    prompt_tokens: int
    output_tokens: int
    fact_hash: str


def make_pair(episode: CanonicalEpisode) -> PairedEpisode:
    digest = assert_information_equivalent(episode)
    return PairedEpisode(
        episode=episode,
        b0_text=serialize_b0(episode),
        b1_text=serialize_b1(episode),
        fact_hash=digest,
    )


def encode_pair_arm(
    pair: PairedEpisode,
    arm: str,
    *,
    tokenizer: LexicalTokenizer | None = None,
    recipe: ModelRecipe = FROZEN_MODEL_RECIPE,
) -> EncodedExample:
    tokenizer = tokenizer or LexicalTokenizer()
    prompt = pair.text_for_arm(arm) + OUTPUT_MARKER
    output = pair.episode.authoritative_output.to_json()
    prompt_ids = tokenizer.encode(prompt)
    output_ids = tokenizer.encode(output)
    if len(prompt_ids) > recipe.max_input_tokens:
        raise ValueError(
            f"{pair.episode.episode_id}/{arm} input has {len(prompt_ids)} tokens; "
            f"limit is {recipe.max_input_tokens}"
        )
    if len(output_ids) > recipe.max_output_tokens:
        raise ValueError(
            f"{pair.episode.episode_id} output has {len(output_ids)} tokens; "
            f"limit is {recipe.max_output_tokens}"
        )
    sequence = [BOS_ID, *prompt_ids, *output_ids, EOS_ID]
    if len(sequence) > recipe.max_seq:
        raise ValueError("complete sequence exceeds frozen model context")
    input_ids = sequence[:-1]
    labels = sequence[1:]
    first_output_target = len(prompt_ids)
    labels = [-100] * first_output_target + labels[first_output_target:]
    if len(input_ids) != len(labels):
        raise AssertionError("input/label length mismatch")
    return EncodedExample(
        episode_id=pair.episode.episode_id,
        arm=arm,
        input_ids=tuple(input_ids),
        labels=tuple(labels),
        prompt_tokens=len(prompt_ids),
        output_tokens=len(output_ids),
        fact_hash=pair.fact_hash,
    )


def collate_encoded(examples: Sequence[EncodedExample]) -> tuple[torch.Tensor, torch.Tensor]:
    if not examples:
        raise ValueError("cannot collate an empty batch")
    max_len = max(len(item.input_ids) for item in examples)
    inputs = torch.full((len(examples), max_len), PAD_ID, dtype=torch.long)
    labels = torch.full((len(examples), max_len), -100, dtype=torch.long)
    for row, item in enumerate(examples):
        length = len(item.input_ids)
        inputs[row, :length] = torch.tensor(item.input_ids, dtype=torch.long)
        labels[row, :length] = torch.tensor(item.labels, dtype=torch.long)
    return inputs, labels


class SyntheticEpisodeGenerator:
    """Deterministic in-memory episode generator.

    The generator uses a private ``random.Random`` instance and never mutates global
    Python or PyTorch RNG state. It emits no files and performs no training.
    """

    SPLITS = tuple(f"S{i}" for i in range(1, 9))

    def __init__(self, seed: int):
        self.seed = int(seed)
        self._rng = random.Random(self.seed)

    def generate(self, split: str, index: int = 0) -> CanonicalEpisode:
        if split not in self.SPLITS:
            raise ValueError(f"unsupported split: {split}")
        nonce = self._rng.randrange(1_000_000)
        suffix = f"{index % 100:02d}{nonce % 10000:04d}"
        tenant = f"t{(index % 7) + 1:02d}"
        other_tenant = f"x{(index % 5) + 1:02d}"
        invoice_id = f"i{suffix}"
        contract_a = f"c{suffix}a"
        contract_b = f"c{suffix}b"
        evidence_a = f"e{suffix}a"
        evidence_b = f"e{suffix}b"
        vendor_a = f"v{suffix}a"
        vendor_b = f"v{suffix}b"

        if split in {"S1", "S4"}:
            entities = (
                Entity("vendor", vendor_a, {"name": "atlas", "suffix": "41"}, tenant),
                Entity("vendor", vendor_b, {"name": "atlas", "suffix": "42"}, tenant),
            )
            return CanonicalEpisode(
                episode_id=f"{split.lower()}-{suffix}",
                split=split,
                tenant_id=tenant,
                query=Query("vendor", vendor_b, None),
                entities=entities,
                relations=(),
                evidence=(),
                authoritative_output=StructuredOutput(
                    "ANSWERED", vendor_b, None, None, (), tenant, "EXACT_ENTITY_ID"
                ),
            )

        base_entities = [
            Entity("invoice", invoice_id, {"amount": str(4200 + index)}, tenant),
            Entity("contract", contract_a, {"status": "active"}, tenant),
            Entity("contract", contract_b, {"status": "pending"}, tenant),
        ]
        relation_a = Relation(
            "belongs_to_contract",
            "invoice",
            invoice_id,
            "contract",
            contract_a,
            evidence_a,
            tenant,
        )
        relation_b = Relation(
            "references_contract",
            "invoice",
            invoice_id,
            "contract",
            contract_b,
            evidence_b,
            tenant,
        )
        evidence = [Evidence(evidence_a, "belongs_to_contract", tenant)]
        relations = [relation_a]

        if split == "S5":
            relations.append(relation_b)
            evidence.append(Evidence(evidence_b, "references_contract", tenant))
        if split == "S6":
            relations = [relation_b]
            evidence = [Evidence(evidence_b, "references_contract", tenant)]
            output = StructuredOutput(
                "INSUFFICIENT_EVIDENCE", None, "belongs_to_contract", None, (), tenant, "RELATION_MISSING"
            )
        else:
            output = StructuredOutput(
                "ANSWERED",
                contract_a,
                "belongs_to_contract",
                True,
                (evidence_a,),
                tenant,
                {
                    "S2": "FOREIGN_KEY_TARGET",
                    "S3": "RELATION_SUPPORTED",
                    "S5": "EVIDENCE_SELECTED",
                    "S7": "TENANT_SAFE_TARGET",
                    "S8": "DIRECT_RELATION",
                }.get(split, "DIRECT_RELATION"),
            )

        if split == "S7":
            base_entities = base_entities[:2]
            cross_id = f"c{suffix}x"
            cross_evidence = f"e{suffix}x"
            base_entities.append(Entity("contract", cross_id, {}, other_tenant))
            relations.append(
                Relation(
                    "belongs_to_contract",
                    "invoice",
                    invoice_id,
                    "contract",
                    cross_id,
                    cross_evidence,
                    other_tenant,
                )
            )
            evidence.append(Evidence(cross_evidence, "belongs_to_contract", other_tenant))

        return CanonicalEpisode(
            episode_id=f"{split.lower()}-{suffix}",
            split=split,
            tenant_id=tenant,
            query=Query("invoice", invoice_id, "belongs_to_contract"),
            entities=tuple(base_entities),
            relations=tuple(relations),
            evidence=tuple(evidence),
            authoritative_output=output,
        )

    def generate_all(self, *, index: int = 0) -> tuple[CanonicalEpisode, ...]:
        return tuple(self.generate(split, index=index) for split in self.SPLITS)


def paired_arm_order(pairs: Iterable[PairedEpisode]) -> tuple[str, ...]:
    return tuple(pair.episode.episode_id for pair in pairs)
