"""Phase 4C prepared-bundle subsystem — slice 3A only.

Ratified in revision 4 (§2.1) and corrected in revision 17 of
``docs/architecture/WORKFLOW_FIT_PILOT_4C_COMMISSIONING_NOTE.md``: the prepared bundle is
exactly nine named JSON artifacts plus an ``index.json`` that is excluded from its own
artifact map. The commitment is the pair ``(commitment_identifier, index_digest)``; any
change to the algorithm, canonicalisation, path set or layout takes a new identifier —
``v1`` is never redefined.

Two role-specific identifiers share the same nine-path layout under different content
models (revision 14): ``workflow_fit_prepared_index.v1`` for a CONFIRMATORY bundle,
``workflow_fit_prepared_index.calibration.v1`` for a CALIBRATION bundle.

Three digests are kept strictly distinct (revision 17), never substituted for one another:

- ``sample_index_digest`` — which upstream BBH indexes were selected, under
  ``bbh_hash_rank_select.v1`` (this module never computes it from case digests);
- ``case_set_digest`` — the governed case set, via the pilot package's own benchmark
  contracts (``BenchmarkManifest.benchmark_manifest_digest``);
- ``index_digest`` — the prepared bundle's own ``index.json`` digest, derivable only once
  the exact nine-artifact set exists on disk.

This module writes and verifies the bundle only. It never constructs a ``CalibrationResult``,
never writes or reads custody evidence, and never starts a boundary process or a provider —
those are slice-3B work, gated on a later custody-write verification this module cannot
perform (revision 17).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from ugence_jcs import canonical_sha256_hex
from ugence_reasoning_method_advisor.api import ReasoningMethodAdvisory, RuleSet
from ugence_reasoning_method_governance.api import ReasoningMethodCatalog
from ugence_workflow_fit_pilot._canon import payload
from ugence_workflow_fit_pilot.contracts.benchmark import BenchmarkManifest
from ugence_workflow_fit_pilot.contracts.calibration import PilotRunRole
from ugence_workflow_fit_pilot.contracts.manifest import PilotStudyManifest, validate_manifest

from .bbh_sample import index_list_digest, select_indexes

INDEX_FILE = "index.json"

CONFIRMATORY_PREPARED_INDEX_IDENTIFIER = "workflow_fit_prepared_index.v1"
CALIBRATION_PREPARED_INDEX_IDENTIFIER = "workflow_fit_prepared_index.calibration.v1"
_KNOWN_IDENTIFIERS = (CONFIRMATORY_PREPARED_INDEX_IDENTIFIER, CALIBRATION_PREPARED_INDEX_IDENTIFIER)

# The nine paths ratified in revision 4 (§2.1). Flat file names: the note's layout carries no
# subdirectory. index.json is the tenth artifact and is excluded from this set and from its
# own map, per the ratified rule.
PREPARED_PATHS: Tuple[str, ...] = (
    "advisory.json",
    "benchmark_manifest.json",
    "case_set.json",
    "catalog.json",
    "experimental_design.json",
    "pilot_manifest.json",
    "preparation.json",
    "provider_configuration.json",
    "rule_set.json",
)

# Token-boundary matching, not raw substring and not whole-key equality. A key is normalised
# to lowercase and split on every non-alphanumeric run, then judged on its *tokens*:
#
# - a raw substring scan flags legitimate governed fields whose names merely contain one of
#   these words (``matched_tokens`` contains ``token``);
# - whole-key equality misses every realistic compound (``openai_api_key``, ``access_token``,
#   ``client_secret``, the plural ``credentials``, the hyphenated ``api-key``).
#
# Token equality avoids both: ``matched_tokens`` tokenises to {matched, tokens} and ``tokens``
# is not ``token``, while ``access_token`` tokenises to {access, token} and is caught.
_CREDENTIAL_TOKENS = frozenset(
    ("apikey", "authorization", "bearer", "credential", "credentials", "password", "secret")
)

# ``token`` needs the trailing-position rule rather than plain membership. This repository's
# own governed telemetry uses it as a *leading* qualifier — ``token_usage``,
# ``token_count_basis``, ``token_usage_availability`` on ``ExecutionTelemetry`` — while every
# credential spelling puts it last (``token``, ``access_token``, ``refresh_token``,
# ``auth_token``, ``id_token``). Plain membership would refuse legitimate artifacts as soon as
# an execution bundle carries telemetry.
_TRAILING_CREDENTIAL_TOKENS = frozenset(("token",))

# ``key`` alone is far too common to flag on its own (``sort_key``, ``primary_key``); it is a
# credential marker only alongside ``api``, which covers ``api_key``, ``api-key`` and
# ``openai_api_key`` alike.
_KEY_TOKEN = "key"
_API_TOKEN = "api"

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")

# ``package.module:function``. Identical to the shape the 4B loader already enforces
# (``experiments/workflow_fit_reference_pilot/loaders.py``, ``_FACTORY``), reused here so a
# prepared bundle cannot commit a provider_factory of any other shape.
_FACTORY_PATH = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")


def _is_credential_key(key: Any) -> bool:
    tokens = [t for t in _TOKEN_SPLIT.split(str(key).lower()) if t]
    if not tokens:
        return False
    unique = set(tokens)
    if unique & _CREDENTIAL_TOKENS:
        return True
    if tokens[-1] in _TRAILING_CREDENTIAL_TOKENS:
        return True
    return _KEY_TOKEN in unique and _API_TOKEN in unique

_UINT64_EXCLUSIVE_MAX = 2**64


class PreparedBundleError(ValueError):
    """The prepared bundle is not the ratified, unmodified nine-artifact set. Verification
    fails closed; nothing here is coerced, defaulted or inferred to repair it."""


# --------------------------------------------------------------------------- canonical JSON I/O


def _dumps(obj: Any) -> bytes:
    """Canonical payload shape (ints/bools as strings, datetimes RFC 3339 UTC, enums by
    value), sorted keys, so a rewrite of equal content is byte-identical. ``payload()``
    recurses through plain mappings/lists as well as dataclasses, so a loose dict of already
    JSON-safe values passes through unchanged."""
    return (json.dumps(payload(obj), indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _no_duplicate_keys(pairs):
    d: Dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise PreparedBundleError(f"duplicate key {k!r} in a prepared artifact")
        d[k] = v
    return d


def _loads(data: bytes) -> Any:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _scan_for_credentials(obj: Any, *, where: str = "$") -> None:
    """Recursively refuse any object whose key contains a credential-like substring, at any
    depth. Applied to every artifact before it is written and after it is read."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if _is_credential_key(k):
                raise PreparedBundleError(f"{where}: credential-like key {k!r} is never accepted in a prepared artifact")
            _scan_for_credentials(v, where=f"{where}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _scan_for_credentials(v, where=f"{where}[{i}]")


def _safe_rel_path(root: Path, rel: str) -> Path:
    """Refuse absolute paths, path traversal and any path that resolves outside root, and
    refuse a symlink anywhere on the resolved path."""
    if not rel or rel.startswith("/") or rel.startswith("\\") or ":" in rel:
        raise PreparedBundleError(f"artifact path {rel!r} is not a bare relative filename")
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise PreparedBundleError(f"artifact path {rel!r} contains a disallowed segment")
    unresolved = root / rel
    if unresolved.is_symlink():
        raise PreparedBundleError(f"artifact path {rel!r} is a symlink; refused")
    candidate = unresolved.resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        raise PreparedBundleError(f"artifact path {rel!r} escapes the bundle directory")
    return candidate


# --------------------------------------------------------------------------- role-specific artifacts


@dataclass(frozen=True)
class ProviderConfiguration:
    """D1 remains unratified; this carries only a dotted factory-path reference, never a
    credential, matching the existing provider_factory convention (4B loaders.py).

    The shape is *enforced*, not merely documented. Without it a credential-shaped string
    passed as ``provider_factory`` would be written into ``provider_configuration.json`` and
    permanently committed by ``index_digest`` — the exact outcome D1 forbids ("the credential
    never appears in … bundles"). The credential-key scan cannot catch this: it inspects key
    names, and here the secret would be a *value* under a legitimate key."""

    provider_factory: str

    def __post_init__(self) -> None:
        if not isinstance(self.provider_factory, str) or not self.provider_factory.strip():
            raise PreparedBundleError("ProviderConfiguration.provider_factory must be a non-blank string")
        if not _FACTORY_PATH.match(self.provider_factory):
            raise PreparedBundleError(
                "ProviderConfiguration.provider_factory must be a dotted factory path "
                "'package.module:function'; a value of any other shape is refused rather than committed"
            )


@dataclass(frozen=True)
class ExperimentalDesign:
    """The single selected, preregistered scenario (revision 4): generic facts required for
    both roles, plus the calibration-only sampling facts required exactly when
    ``run_role is CALIBRATION`` and refused otherwise (revision 17)."""

    manifest_id: str
    manifest_digest: str
    run_role: str
    benchmark_id: str
    benchmark_version: str
    benchmark_content_digest: str
    execution_order_rule: str
    verdict_custody_ref: str
    sampling_algorithm_id: Optional[str] = None
    sampling_algorithm_version: Optional[str] = None
    seed: Optional[str] = None
    population_size: Optional[int] = None
    sample_size: Optional[int] = None
    selected_indexes: Optional[Tuple[str, ...]] = None
    sample_index_digest: Optional[str] = None
    formula_id: Optional[str] = None
    formula_version: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("manifest_id", "manifest_digest", "benchmark_id", "benchmark_version", "benchmark_content_digest", "execution_order_rule", "verdict_custody_ref"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise PreparedBundleError(f"ExperimentalDesign.{name} must be a non-blank string")
        if self.run_role not in (r.value for r in PilotRunRole):
            raise PreparedBundleError(f"ExperimentalDesign.run_role must be one of {[r.value for r in PilotRunRole]}")
        calibration_fields = (
            self.sampling_algorithm_id, self.sampling_algorithm_version, self.seed, self.population_size,
            self.sample_size, self.selected_indexes, self.sample_index_digest, self.formula_id, self.formula_version,
        )
        is_calibration = self.run_role == PilotRunRole.CALIBRATION.value
        if is_calibration and any(f is None for f in calibration_fields):
            raise PreparedBundleError("a CALIBRATION experimental design requires every sampling field")
        if not is_calibration and any(f is not None for f in calibration_fields):
            raise PreparedBundleError("a CONFIRMATORY experimental design carries no sampling field")
        if is_calibration:
            self._validate_calibration_sampling()

    def _validate_calibration_sampling(self) -> None:
        if self.sampling_algorithm_id != "bbh_hash_rank_select" or self.sampling_algorithm_version != "1":
            raise PreparedBundleError("ExperimentalDesign.sampling_algorithm_id/version must name bbh_hash_rank_select v1")
        if not isinstance(self.seed, str) or not self.seed.isdigit() or not (0 <= int(self.seed) < _UINT64_EXCLUSIVE_MAX):
            raise PreparedBundleError("ExperimentalDesign.seed must be an unsigned 64-bit decimal string")
        for name in ("population_size", "sample_size"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v <= 0:
                raise PreparedBundleError(f"ExperimentalDesign.{name} must be a positive integer")
        if self.sample_size > self.population_size:
            raise PreparedBundleError("ExperimentalDesign.sample_size cannot exceed population_size")
        if not isinstance(self.selected_indexes, tuple) or not self.selected_indexes:
            raise PreparedBundleError("ExperimentalDesign.selected_indexes must be a non-empty tuple")
        if len(self.selected_indexes) != self.sample_size:
            raise PreparedBundleError("ExperimentalDesign.selected_indexes length must equal sample_size")
        parsed = []
        for i, s in enumerate(self.selected_indexes):
            if not isinstance(s, str) or not s.isdigit() or (len(s) > 1 and s[0] == "0"):
                raise PreparedBundleError(f"ExperimentalDesign.selected_indexes[{i}] must be a canonical decimal string")
            parsed.append(int(s))
        if parsed != sorted(parsed) or len(set(parsed)) != len(parsed):
            raise PreparedBundleError("ExperimentalDesign.selected_indexes must be ascending and unique")
        if any(v >= self.population_size for v in parsed):
            raise PreparedBundleError("ExperimentalDesign.selected_indexes must be within population_size")
        if index_list_digest(tuple(parsed)) != self.sample_index_digest:
            raise PreparedBundleError("ExperimentalDesign.sample_index_digest does not match selected_indexes")
        for name in ("formula_id", "formula_version"):
            if not isinstance(getattr(self, name), str) or not getattr(self, name).strip():
                raise PreparedBundleError(f"ExperimentalDesign.{name} must be a non-blank string")


def _experimental_design_payload(ed: ExperimentalDesign) -> Dict[str, Any]:
    return {
        "manifest_id": ed.manifest_id,
        "manifest_digest": ed.manifest_digest,
        "run_role": ed.run_role,
        "benchmark_id": ed.benchmark_id,
        "benchmark_version": ed.benchmark_version,
        "benchmark_content_digest": ed.benchmark_content_digest,
        "execution_order_rule": ed.execution_order_rule,
        "verdict_custody_ref": ed.verdict_custody_ref,
        "sampling_algorithm_id": ed.sampling_algorithm_id,
        "sampling_algorithm_version": ed.sampling_algorithm_version,
        "seed": ed.seed,
        "population_size": None if ed.population_size is None else str(ed.population_size),
        "sample_size": None if ed.sample_size is None else str(ed.sample_size),
        "selected_indexes": None if ed.selected_indexes is None else list(ed.selected_indexes),
        "sample_index_digest": ed.sample_index_digest,
        "formula_id": ed.formula_id,
        "formula_version": ed.formula_version,
    }


_EXPERIMENTAL_DESIGN_FIELD_NAMES = (
    "manifest_id", "manifest_digest", "run_role", "benchmark_id", "benchmark_version", "benchmark_content_digest",
    "execution_order_rule", "verdict_custody_ref", "sampling_algorithm_id", "sampling_algorithm_version", "seed",
    "population_size", "sample_size", "selected_indexes", "sample_index_digest", "formula_id", "formula_version",
)


def _load_experimental_design(data: Any) -> ExperimentalDesign:
    if not isinstance(data, Mapping) or set(data) != set(_EXPERIMENTAL_DESIGN_FIELD_NAMES):
        raise PreparedBundleError("experimental_design.json is not the ratified shape")
    kwargs = dict(data)
    if kwargs["population_size"] is not None:
        kwargs["population_size"] = int(kwargs["population_size"]) if isinstance(kwargs["population_size"], str) else kwargs["population_size"]
    if kwargs["sample_size"] is not None:
        kwargs["sample_size"] = int(kwargs["sample_size"]) if isinstance(kwargs["sample_size"], str) else kwargs["sample_size"]
    if kwargs["selected_indexes"] is not None:
        if not isinstance(kwargs["selected_indexes"], list):
            raise PreparedBundleError("experimental_design.json selected_indexes must be a JSON array")
        kwargs["selected_indexes"] = tuple(kwargs["selected_indexes"])
    return ExperimentalDesign(**kwargs)


def _load_provider_configuration(data: Any) -> ProviderConfiguration:
    if not isinstance(data, Mapping) or set(data) != {"provider_factory"}:
        raise PreparedBundleError("provider_configuration.json is not {provider_factory}")
    return ProviderConfiguration(provider_factory=data["provider_factory"])


# --------------------------------------------------------------------------- writer


@dataclass(frozen=True)
class PreparedBundleResult:
    """What ``prepare`` produced, returned typed rather than as loose strings."""

    root: Path
    commitment_identifier: str
    index_digest: str
    artifacts: Tuple[str, ...]


def prepare(
    out_dir: Path,
    *,
    manifest: PilotStudyManifest,
    benchmark: BenchmarkManifest,
    catalog: ReasoningMethodCatalog,
    rule_set: RuleSet,
    advisory: Optional[ReasoningMethodAdvisory],
    case_set: Mapping[str, Any],
    provider_configuration: ProviderConfiguration,
    experimental_design: ExperimentalDesign,
    preparation: Mapping[str, Any],
) -> PreparedBundleResult:
    """Write exactly the ratified nine artifacts plus ``index.json``. Refuses to overwrite an
    existing prepared bundle; refuses path traversal, absolute paths and symlinks; computes
    every digest from the bytes actually written."""
    if not isinstance(manifest, PilotStudyManifest) or not manifest.is_v2:
        raise PreparedBundleError("a prepared bundle requires a v2 manifest with a committed run_role")
    if manifest.run_role is None:
        raise PreparedBundleError("a prepared bundle requires a committed PilotRunRole")
    identifier = CALIBRATION_PREPARED_INDEX_IDENTIFIER if manifest.run_role is PilotRunRole.CALIBRATION else CONFIRMATORY_PREPARED_INDEX_IDENTIFIER
    expected_role = manifest.run_role.value
    if experimental_design.run_role != expected_role:
        raise PreparedBundleError("experimental_design.run_role does not match the manifest's committed run_role")
    if experimental_design.manifest_id != manifest.manifest_id or experimental_design.manifest_digest != manifest.manifest_digest:
        raise PreparedBundleError("experimental_design does not bind this manifest's id and digest")
    if experimental_design.benchmark_content_digest != benchmark.benchmark.content_digest:
        raise PreparedBundleError("experimental_design.benchmark_content_digest does not match the prepared benchmark head")
    if manifest.benchmark.benchmark_manifest_digest != benchmark.benchmark_manifest_digest:
        raise PreparedBundleError("manifest.benchmark and the prepared benchmark manifest disagree")

    artifacts: Dict[str, Any] = {
        "advisory.json": {} if advisory is None else advisory,
        "benchmark_manifest.json": benchmark,
        "case_set.json": dict(case_set),
        "catalog.json": catalog,
        "experimental_design.json": _experimental_design_payload(experimental_design),
        "pilot_manifest.json": manifest,
        "preparation.json": dict(preparation),
        "provider_configuration.json": {"provider_factory": provider_configuration.provider_factory},
        "rule_set.json": rule_set,
    }
    if set(artifacts) != set(PREPARED_PATHS):
        raise PreparedBundleError("internal: artifact set does not match PREPARED_PATHS")

    root = Path(out_dir)
    if root.exists():
        raise PreparedBundleError(f"refusing to overwrite an existing prepared bundle at {root}")
    root.mkdir(parents=True, exist_ok=False)

    digests: Dict[str, str] = {}
    for rel in PREPARED_PATHS:
        obj = artifacts[rel]
        raw = _dumps(obj)
        _scan_for_credentials(_loads(raw), where=rel)
        target = _safe_rel_path(root, rel)
        tmp = target.with_name(f".{target.name}.tmp")
        tmp.write_bytes(raw)
        os.replace(tmp, target)
        digests[rel] = sha256_bytes(raw)

    index_digest = canonical_sha256_hex({k: digests[k] for k in sorted(digests)})
    index_payload = {"commitment_identifier": identifier, "artifacts": digests, "index_digest": index_digest}
    index_raw = (json.dumps(index_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    index_target = _safe_rel_path(root, INDEX_FILE)
    tmp = index_target.with_name(f".{index_target.name}.tmp")
    tmp.write_bytes(index_raw)
    os.replace(tmp, index_target)

    return PreparedBundleResult(root=root, commitment_identifier=identifier, index_digest=index_digest, artifacts=PREPARED_PATHS)


# --------------------------------------------------------------------------- reader / verifier


@dataclass(frozen=True)
class VerifiedPreparedBundle:
    """Derived verification output only — not a new externally authored authority. Every
    field here was independently recomputed from the bytes on disk."""

    commitment_identifier: str
    index_digest: str
    sample_index_digest: Optional[str]
    case_set_digest: str
    verdict_custody_ref: str
    manifest_digest: str
    run_role: str


def _walk_files(root: Path) -> Tuple[str, ...]:
    out = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.is_symlink():
            raise PreparedBundleError(f"symlink present in the prepared bundle: {entry.name}")
        if entry.is_dir():
            raise PreparedBundleError(f"unexpected subdirectory in the prepared bundle: {entry.name}")
        out.append(entry.name)
    return tuple(out)


def verify(
    root: Path,
    *,
    catalog: ReasoningMethodCatalog,
    rule_set: RuleSet,
    advisory: Optional[ReasoningMethodAdvisory],
) -> VerifiedPreparedBundle:
    """Reject an unknown identifier; enforce identifier/role consistency; require exactly the
    nine paths (no extra, missing, renamed or symlinked); recompute every file digest and the
    index digest; reconstruct and fully re-validate the manifest (forcing its own role
    invariants, not trusting a carried digest); recompute the sampled indexes from algorithm,
    seed and population for a CALIBRATION bundle; verify every cross-file binding."""
    root = Path(root)
    if not root.is_dir():
        raise PreparedBundleError(f"prepared bundle directory {root} does not exist")
    on_disk = set(_walk_files(root))
    if INDEX_FILE not in on_disk:
        raise PreparedBundleError("index.json is absent")
    index_raw = (root / INDEX_FILE).read_bytes()
    index_payload = _loads(index_raw)
    if not isinstance(index_payload, Mapping) or set(index_payload) != {"commitment_identifier", "artifacts", "index_digest"}:
        raise PreparedBundleError("index.json is not {commitment_identifier, artifacts, index_digest}")
    identifier = index_payload["commitment_identifier"]
    if identifier not in _KNOWN_IDENTIFIERS:
        raise PreparedBundleError(f"unknown prepared-bundle commitment identifier {identifier!r}")
    digests: Mapping[str, Any] = index_payload["artifacts"]
    if not isinstance(digests, Mapping) or set(digests) != set(PREPARED_PATHS):
        raise PreparedBundleError("index.json's artifact map does not name exactly the nine ratified paths")
    recomputed_index_digest = canonical_sha256_hex({k: digests[k] for k in sorted(digests)})
    if index_payload["index_digest"] != recomputed_index_digest:
        raise PreparedBundleError("index_digest does not cover the indexed artifact set")

    non_index = on_disk - {INDEX_FILE}
    if non_index - set(PREPARED_PATHS):
        raise PreparedBundleError(f"unexpected artifacts present: {sorted(non_index - set(PREPARED_PATHS))}")
    if set(PREPARED_PATHS) - non_index:
        raise PreparedBundleError(f"required artifacts absent: {sorted(set(PREPARED_PATHS) - non_index)}")

    raw_by_path: Dict[str, bytes] = {}
    for rel in PREPARED_PATHS:
        raw = _safe_rel_path(root, rel).read_bytes()
        if sha256_bytes(raw) != digests[rel]:
            raise PreparedBundleError(f"artifact {rel} was substituted: sha256 differs from the index")
        raw_by_path[rel] = raw

    for rel, raw in raw_by_path.items():
        _scan_for_credentials(_loads(raw), where=rel)

    manifest = PilotStudyManifest(**_rebuild_manifest_kwargs(_loads(raw_by_path["pilot_manifest.json"])))
    validate_manifest(manifest, catalog=catalog, rule_set=rule_set, advisory=advisory)
    if not manifest.is_v2 or manifest.run_role is None:
        raise PreparedBundleError("the prepared manifest carries no committed run_role")
    is_calibration = manifest.run_role is PilotRunRole.CALIBRATION
    expected_identifier = CALIBRATION_PREPARED_INDEX_IDENTIFIER if is_calibration else CONFIRMATORY_PREPARED_INDEX_IDENTIFIER
    if identifier != expected_identifier:
        raise PreparedBundleError(f"commitment identifier {identifier!r} does not match the manifest's committed run_role")

    design = _load_experimental_design(_loads(raw_by_path["experimental_design.json"]))
    if design.run_role != manifest.run_role.value:
        raise PreparedBundleError("experimental_design.run_role does not match the prepared manifest's run_role")
    if design.manifest_id != manifest.manifest_id or design.manifest_digest != manifest.manifest_digest:
        raise PreparedBundleError("experimental_design does not bind the prepared manifest's id and digest")

    benchmark = BenchmarkManifest(**_rebuild_benchmark_kwargs(_loads(raw_by_path["benchmark_manifest.json"])))
    if manifest.benchmark.benchmark_manifest_digest != benchmark.benchmark_manifest_digest:
        raise PreparedBundleError("pilot_manifest.benchmark and benchmark_manifest.json disagree")
    if design.benchmark_content_digest != benchmark.benchmark.content_digest:
        raise PreparedBundleError("experimental_design.benchmark_content_digest does not match the prepared benchmark head")

    case_set = _loads(raw_by_path["case_set.json"])
    if not isinstance(case_set, Mapping) or set(case_set) != {"case_count", "cases"} or not isinstance(case_set["cases"], list):
        raise PreparedBundleError("case_set.json is not {case_count, cases}")
    case_digests = tuple(c["case_digest"] for c in case_set["cases"])
    if case_digests != benchmark.case_digests or str(len(case_digests)) != str(case_set["case_count"]):
        raise PreparedBundleError("case_set.json and benchmark_manifest.json disagree on the case-digest set")

    sample_index_digest: Optional[str] = None
    if is_calibration:
        recomputed = select_indexes(seed=int(design.seed), population_size=design.population_size, sample_size=design.sample_size)
        declared = tuple(int(s) for s in design.selected_indexes)
        if recomputed != declared:
            raise PreparedBundleError("selected_indexes do not reproduce from sampling_algorithm_id/version, seed and population_size")
        recomputed_sample_digest = index_list_digest(recomputed)
        if recomputed_sample_digest != design.sample_index_digest:
            raise PreparedBundleError("sample_index_digest does not match the recomputed selection")
        sample_index_digest = recomputed_sample_digest

    return VerifiedPreparedBundle(
        commitment_identifier=identifier,
        index_digest=recomputed_index_digest,
        sample_index_digest=sample_index_digest,
        case_set_digest=benchmark.benchmark_manifest_digest,
        verdict_custody_ref=design.verdict_custody_ref,
        manifest_digest=manifest.manifest_digest,
        run_role=manifest.run_role.value,
    )


def _rebuild_manifest_kwargs(data: Any) -> Dict[str, Any]:
    """A minimal, type-directed rebuild for the one dataclass the verifier must reconstruct
    through its real constructor (forcing full validation), not merely re-hash. Delegates
    nested-object reconstruction to the same JCS-compatible payload shapes the writer used."""
    from datetime import datetime, timezone

    from ugence_reasoning_method_governance.api import AggregationRef, ResearchComparisonPlan
    from ugence_workflow_fit_pilot.contracts.benchmark import BenchmarkManifest as _BM
    from ugence_workflow_fit_pilot.contracts.calibration import CalibrationProvenance, PilotRunRole as _Role
    from ugence_workflow_fit_pilot.contracts.evaluator import QualityEvaluatorDeclaration
    from ugence_workflow_fit_pilot.contracts.manifest import CaptureBoundaryDeclaration, PilotMethodAssignment, PilotRole, PreregistrationStatus

    if not isinstance(data, Mapping):
        raise PreparedBundleError("pilot_manifest.json must be a JSON object")

    def _dt(s: Any) -> Any:
        if not isinstance(s, str) or not s.endswith("Z"):
            raise PreparedBundleError("expected an RFC 3339 UTC instant")
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    d = dict(data)
    d["plan"] = ResearchComparisonPlan(**_plan_kwargs(d["plan"]))
    d["methods"] = tuple(
        PilotMethodAssignment(method=_method_ref(m["method"]), roles=tuple(PilotRole(r) for r in m["roles"])) for m in d["methods"]
    )
    d["benchmark"] = _BM(**_rebuild_benchmark_kwargs(d["benchmark"]))
    d["capture_boundary"] = CaptureBoundaryDeclaration(**{**d["capture_boundary"], "allowed_attested_fields": tuple(d["capture_boundary"]["allowed_attested_fields"])})
    from ugence_workflow_fit_pilot.contracts.evaluator import EvaluatorKind

    d["evaluator"] = QualityEvaluatorDeclaration(**{**d["evaluator"], "kind": EvaluatorKind(d["evaluator"]["kind"])})
    d["resource_aggregation"] = AggregationRef(**d["resource_aggregation"])
    d["quality_aggregation"] = AggregationRef(**d["quality_aggregation"])
    d["preregistration_status"] = PreregistrationStatus(d["preregistration_status"])
    d["preregistered_at"] = _dt(d["preregistered_at"])
    d["rule_set"] = None if d.get("rule_set") is None else _rule_set_ref(d["rule_set"])
    d["run_role"] = None if d.get("run_role") is None else _Role(d["run_role"])
    d["calibration_provenance"] = None if d.get("calibration_provenance") is None else CalibrationProvenance(**d["calibration_provenance"])
    return d


def _plan_kwargs(data: Mapping[str, Any]) -> Dict[str, Any]:
    from datetime import datetime

    from ugence_reasoning_method_governance.api import BindingRef, ChallengerSamplingPolicy, SamplingKind
    from ugence_workflow_fit_pilot.contracts.manifest import PILOT_MANIFEST_SCHEMA_VERSION  # noqa: F401  (import-boundary anchor only)

    d = dict(data)
    d["task_class"] = _task_class(d["task_class"])
    d["binding"] = BindingRef(**d["binding"])
    d["catalog"] = _catalog_ref(d["catalog"])
    d["baseline"] = _method_ref(d["baseline"])
    d["recommended"] = tuple(_method_ref(m) for m in d["recommended"])
    d["challengers"] = ChallengerSamplingPolicy(kind=SamplingKind(d["challengers"]["kind"]), policy_ref=d["challengers"]["policy_ref"], declared_coverage_ref=d["challengers"]["declared_coverage_ref"])
    d["preregistered_at"] = datetime.fromisoformat(d["preregistered_at"].replace("Z", "+00:00"))
    return d


def _task_class(data: Mapping[str, Any]) -> Any:
    from ugence_governance_contracts.api import BenchmarkReference
    from ugence_reasoning_method_governance.api import (
        AggregationRef,
        ComparisonPolicy,
        ConsequenceClass,
        ResourceDimension,
        SufficiencyKind,
        SufficiencyRule,
        TaskClassIdentity,
        TaskReversibility,
    )
    from ugence_uvi_policy_contracts.api import ComparisonOperator, GovernedThreshold

    d = dict(data)
    d["consequence_class"] = ConsequenceClass(d["consequence_class"])
    d["reversibility"] = TaskReversibility(d["reversibility"])
    d["evidence_requirement_refs"] = tuple(d["evidence_requirement_refs"])
    d["tool_requirement_refs"] = tuple(d["tool_requirement_refs"])
    d["structural_characteristics"] = tuple(d["structural_characteristics"])
    policy = d["comparison_policy"]
    rule = policy["sufficiency"]
    threshold_data = rule["threshold"]
    benchmark_ref = None if threshold_data.get("benchmark_ref") is None else BenchmarkReference(**threshold_data["benchmark_ref"])
    threshold = GovernedThreshold(
        threshold_data["threshold_id"], threshold_data["governed_unit"], ComparisonOperator(threshold_data["comparator"]),
        threshold_data.get("literal_value", ""), benchmark_ref,
    )
    required_dims = tuple(ResourceDimension(x) for x in policy["required_dimensions"])
    quality_agg = None if policy.get("quality_aggregation") is None else AggregationRef(**policy["quality_aggregation"])
    d["comparison_policy"] = ComparisonPolicy(
        policy["policy_id"], policy["policy_version"],
        SufficiencyRule(rule["rule_id"], rule["rule_version"], SufficiencyKind(rule["kind"]), threshold, rule.get("supporting_evidence_admission")),
        required_dims, quality_agg,
    )
    return TaskClassIdentity(**d)


def _method_ref(data: Mapping[str, Any]) -> Any:
    from ugence_reasoning_method_governance.api import ReasoningMethodRef

    return ReasoningMethodRef(catalog=_catalog_ref(data["catalog"]), method_id=data["method_id"], method_version=data["method_version"])


def _catalog_ref(data: Mapping[str, Any]) -> Any:
    from ugence_reasoning_method_governance.api import ReasoningMethodCatalogRef

    return ReasoningMethodCatalogRef(**data)


def _rule_set_ref(data: Mapping[str, Any]) -> Any:
    from ugence_reasoning_method_advisor.api import RuleSetRef

    return RuleSetRef(**data)


def _rebuild_benchmark_kwargs(data: Mapping[str, Any]) -> Dict[str, Any]:
    from datetime import datetime

    from ugence_governance_contracts.api import BenchmarkReference

    d = dict(data)
    d["benchmark"] = BenchmarkReference(**d["benchmark"])
    d["case_digests"] = tuple(d["case_digests"])
    d["case_count"] = int(d["case_count"])
    d["issued_at"] = datetime.fromisoformat(d["issued_at"].replace("Z", "+00:00"))
    return d


__all__ = [
    "PreparedBundleError",
    "INDEX_FILE",
    "PREPARED_PATHS",
    "CONFIRMATORY_PREPARED_INDEX_IDENTIFIER",
    "CALIBRATION_PREPARED_INDEX_IDENTIFIER",
    "ProviderConfiguration",
    "ExperimentalDesign",
    "PreparedBundleResult",
    "VerifiedPreparedBundle",
    "prepare",
    "verify",
    "sha256_bytes",
]
