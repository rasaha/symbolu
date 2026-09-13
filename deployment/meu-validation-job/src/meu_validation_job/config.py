"""The job's configuration: references, a mode, and where to write the report.

Every field is a pointer or a posture. There is no field that could hold a provider
key, and a value that carries credential material is refused by the custody package's
scan before the job does anything else.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ugence_model_egress_custody_gcp import ConfigRefused, refuse_credential_material
from ugence_model_egress_unit import OPENAI_RESPONSES, looks_like_a_credential

from .version import CONFIG_SCHEMA

__all__ = ["JobConfig", "JobConfigRefused", "MODES", "load_config"]

MODES = ("offline", "live")


class JobConfigRefused(ValueError):
    """Configuration this job will not run on. Names the field, never the value."""


@dataclass(frozen=True)
class JobConfig:
    """What the operator supplies to one run.

    ``custody`` is the mapping the custody adapter validates for itself; the job never
    interprets it beyond handing it over, so there is exactly one place that decides
    what a custody configuration may contain.
    """

    #: ``offline`` (the default, and the only mode that can succeed in this slice) or
    #: ``live``, which fails closed.
    mode: str = "offline"
    environment: str = "non-production"
    #: LP-8: which deployed instance this is, and the identity it runs as.
    instance_reference: str = ""
    workload_identity_principal: str = ""
    #: Paths to the two canonical records and, later, the owner's typed authorization.
    designation_record_path: str = ""
    validation_record_path: str = ""
    authorization_record_path: str = ""
    #: The custody adapter's configuration, as a mapping of references.
    custody: Mapping[str, Any] = field(default_factory=dict)
    #: The exact endpoint the validation may use. Anything else is refused.
    endpoint: str = OPENAI_RESPONSES.url
    report_path: str = "/tmp/meu-validation-report.json"
    schema: str = CONFIG_SCHEMA

    def __post_init__(self) -> None:
        # The custody distribution owns the definition of "credential material", so its
        # refusal is re-raised as this job's type rather than re-implemented.
        try:
            refuse_credential_material(self.as_record())
        except ConfigRefused as refused:
            raise JobConfigRefused(str(refused)) from None
        if self.schema != CONFIG_SCHEMA:
            raise JobConfigRefused(f"config.schema: expected {CONFIG_SCHEMA}")
        if self.mode not in MODES:
            raise JobConfigRefused(f"config.mode: one of {MODES}")
        if str(self.environment).strip().lower() != "non-production":
            raise JobConfigRefused(
                "config.environment: this job runs in the non-production commissioning scope only; "
                "production is a separate commissioning record (LP-7, LP-8)")
        for name in ("instance_reference", "workload_identity_principal",
                     "designation_record_path", "validation_record_path"):
            if not str(getattr(self, name)).strip():
                raise JobConfigRefused(f"config.{name}: required")
        if looks_like_a_credential(self.endpoint) or self.endpoint != OPENAI_RESPONSES.url:
            raise JobConfigRefused(
                f"config.endpoint: the only designated destination is {OPENAI_RESPONSES.url} (LP-3)")
        if not isinstance(self.custody, Mapping) or not self.custody:
            raise JobConfigRefused("config.custody: a mapping of custody references is required")

    def as_record(self) -> dict:
        record = asdict(self)
        record["custody"] = dict(self.custody)
        return record


def load_config(path: pathlib.Path) -> JobConfig:
    """Read and validate one configuration file. Refuses unknown fields outright."""

    try:
        raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise JobConfigRefused(f"config: {path} does not exist") from None
    except json.JSONDecodeError as exc:
        raise JobConfigRefused(f"config: {path} is not valid JSON (line {exc.lineno})") from None
    if not isinstance(raw, Mapping):
        raise JobConfigRefused("config: the document must be a JSON object")
    try:
        refuse_credential_material(raw)
        # A key beginning with "_" is a comment: JSON has none, and an operator
        # configuration that cannot be annotated gets annotated in a wiki nobody reads.
        fields = {key: value for key, value in raw.items() if not str(key).startswith("_")}
        unknown = set(fields) - set(JobConfig.__dataclass_fields__)
        if unknown:
            raise JobConfigRefused(f"config: unknown field(s) {sorted(unknown)}")
        return JobConfig(**fields)
    except JobConfigRefused:
        raise
    except ConfigRefused as refused:
        raise JobConfigRefused(str(refused)) from None
