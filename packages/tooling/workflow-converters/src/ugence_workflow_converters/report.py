"""The conversion report (CV-3) and the refusal a converter raises (CV-4).

Every model is frozen and ``extra='forbid'``, like the compiler's. The report is
content-addressed: ``report_digest`` is the digest of the report with that one field
blank, so two runs over the same input produce the same digest and a changed report
cannot keep an old one.

Vocabulary is deliberately narrow (CV-5). A conversion ends in exactly one of two
states, ``STRUCTURALLY_TRANSLATED`` or ``PARTIAL``; a row of the mapping table has
exactly one of three outcomes, ``MAPPED``, ``UNMAPPED`` or ``UNSUPPORTED``. None of
these words is "equivalent", "governed", "approved" or "validated", and a test in
this package asserts that no report text ever carries them.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from ugence_policy_workflow_compiler.serialization import hashing

from .version import CLAIM, CONVERSION_REPORT_SCHEMA, DISTRIBUTION_VERSION


class ConverterModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversionState(str, Enum):
    #: Every construct of the source was mapped or is a known no-op for governance.
    STRUCTURALLY_TRANSLATED = "STRUCTURALLY_TRANSLATED"
    #: At least one construct is unsupported, or a translated construct lost meaning.
    PARTIAL = "PARTIAL"


class RowOutcome(str, Enum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    UNSUPPORTED = "UNSUPPORTED"


class RefusalCode(str, Enum):
    NOT_JSON = "NOT_JSON"
    NOT_AN_OBJECT = "NOT_AN_OBJECT"
    NOT_AN_EXPORT_OF_THIS_FORMAT = "NOT_AN_EXPORT_OF_THIS_FORMAT"
    TOO_LARGE = "TOO_LARGE"
    TOO_MANY_NODES = "TOO_MANY_NODES"
    TOO_DEEP = "TOO_DEEP"
    EMBEDDED_SECRET = "EMBEDDED_SECRET"
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"
    DEFERRED_FORMAT = "DEFERRED_FORMAT"


class ConversionRefused(Exception):
    """The whole conversion is refused and nothing is written (CV-4)."""

    def __init__(self, code: RefusalCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message


class MappingRow(ConverterModel):
    source_construct_id: str
    source_construct_type: str
    source_name: str = ""
    outcome: RowOutcome
    #: Pack object ids this construct became; empty unless MAPPED.
    target_object_ids: Tuple[str, ...] = ()
    target_object_types: Tuple[str, ...] = ()
    reason_code: str
    note: str = ""
    #: Loss codes attached to this construct (also listed under semantic_loss_warnings).
    semantic_loss: Tuple[str, ...] = ()


class SemanticLossWarning(ConverterModel):
    source_construct_id: str
    code: str
    detail: str


class GovernanceGap(ConverterModel):
    source_construct_id: str
    gap_code: str
    detail: str


class ToolRequirement(ConverterModel):
    source_construct_id: str
    tool: str
    target: str = ""


class CredentialRequirement(ConverterModel):
    """A handle only. The converter never sees, copies or names a secret value."""
    source_construct_id: str
    credential_type: str
    credential_handle: str


class SourceSummary(ConverterModel):
    format: str
    format_detail: str = ""
    input_digest: str
    input_bytes: int
    workflow_name: str = ""
    construct_count: int
    connection_count: int


class PackSummary(ConverterModel):
    pack_id: str
    status: str
    pack_digest: str
    object_counts: Dict[str, int]


class ValidationSummary(ConverterModel):
    ok: bool
    counts: Dict[str, int]
    blocking: Tuple[Dict[str, str], ...] = ()


class PreviewSummary(ConverterModel):
    status: str
    ir_version: str
    preview_digest: str
    node_count: int
    edge_count: int


class ConversionReport(ConverterModel):
    schema_: str = Field(default=CONVERSION_REPORT_SCHEMA, alias="schema")
    converter: Dict[str, str]
    claim: str = CLAIM
    source: SourceSummary
    conversion_state: ConversionState
    mapping_table: Tuple[MappingRow, ...]
    unsupported_constructs: Tuple[MappingRow, ...]
    semantic_loss_warnings: Tuple[SemanticLossWarning, ...]
    governance_gaps: Tuple[GovernanceGap, ...]
    tool_requirements: Tuple[ToolRequirement, ...]
    credential_requirements: Tuple[CredentialRequirement, ...]
    pack: PackSummary
    validation: ValidationSummary
    preview: Optional[PreviewSummary] = None
    report_digest: str = ""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    def as_document(self) -> dict:
        return self.model_dump(mode="json", by_alias=True)

    def sealed(self) -> "ConversionReport":
        """The same report with ``report_digest`` computed over everything else."""
        body = self.model_copy(update={"report_digest": ""}).as_document()
        return self.model_copy(update={"report_digest": hashing.digest(body)})


def converter_identity(name: str) -> Dict[str, str]:
    return {"name": name, "distribution": "ugence-workflow-converters",
            "distribution_version": DISTRIBUTION_VERSION}
