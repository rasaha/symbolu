"""
Phase-4A Error Types
====================

Explicit error types for Phase-4A ontology lookup failures.

Phase-4A is the ontology lookup sub-module within the composite Phase-4
of the Phase-1b → Phase-14 experimental pipeline.

All errors are fail-fast: they indicate irrecoverable data inconsistencies
that require upstream ontology file fixes. Phase-4A never infers, smooths,
or compensates for missing data.
"""

from typing import Optional, Tuple


class Phase4AError(Exception):
    """
    Base exception for all Phase-4A failures.

    Phase-4A errors are always fatal and indicate ontology
    inconsistencies that require file-level fixes.
    """

    def __init__(self, message: str, context: Optional[dict] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.context:
            return f"[Phase-4A Error] {self.message}"
        ctx_str = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
        return f"[Phase-4A Error] {self.message} | Context: {ctx_str}"


class Phase4AValidationError(Phase4AError):
    """
    Raised when ontology file validation fails.

    This indicates structural inconsistency between the three frozen files:
    - varna_bridge_map_v1.json
    - ontological_layers_v1.json
    - varna_layer_interaction_v1.json
    """

    def __init__(
        self,
        message: str,
        missing_varnas: Tuple[str, ...] = (),
        missing_layers: Tuple[str, ...] = (),
        orphan_interactions: Tuple[str, ...] = ()
    ):
        context = {}
        if missing_varnas:
            context["missing_varnas"] = missing_varnas
        if missing_layers:
            context["missing_layers"] = missing_layers
        if orphan_interactions:
            context["orphan_interactions"] = orphan_interactions
        super().__init__(message, context)
        self.missing_varnas = missing_varnas
        self.missing_layers = missing_layers
        self.orphan_interactions = orphan_interactions


class Phase4AVarnaMissingError(Phase4AError):
    """
    Raised when a requested varna does not exist in varna_bridge_map_v1.json.

    Phase-4A does NOT infer or substitute. If the varna is missing, fail.
    """

    def __init__(self, varna: str):
        super().__init__(
            f"Varna '{varna}' not found in varna_bridge_map_v1.json",
            context={"varna": varna}
        )
        self.varna = varna


class Phase4ALayerMissingError(Phase4AError):
    """
    Raised when a requested layer does not exist in ontological_layers_v1.json.

    Valid layers are O3_EXECUTION through O12_ABSOLVING.
    """

    def __init__(self, layer: str, valid_layers: Tuple[str, ...] = ()):
        context = {"layer": layer}
        if valid_layers:
            context["valid_layers"] = valid_layers
        super().__init__(
            f"Layer '{layer}' not found in ontological_layers_v1.json",
            context=context
        )
        self.layer = layer
        self.valid_layers = valid_layers


class Phase4AInteractionMissingError(Phase4AError):
    """
    Raised when a (varna, layer) pair has no entry in varna_layer_interaction_v1.json.

    This indicates the interaction file is incomplete for the given pair.
    """

    def __init__(self, varna: str, layer: str):
        super().__init__(
            f"No interaction entry for (varna='{varna}', layer='{layer}')",
            context={"varna": varna, "layer": layer}
        )
        self.varna = varna
        self.layer = layer


class Phase4AFieldMissingError(Phase4AError):
    """
    Raised when a required field is missing from an interaction entry.

    Required fields for each (varna, layer) interaction:
    - manifestation_positive
    - manifestation_negative
    - distortion_vector
    - sublimate_vector
    """

    REQUIRED_FIELDS = (
        "manifestation_positive",
        "manifestation_negative",
        "distortion_vector",
        "sublimate_vector",
    )

    def __init__(self, varna: str, layer: str, missing_field: str):
        super().__init__(
            f"Required field '{missing_field}' missing in interaction (varna='{varna}', layer='{layer}')",
            context={
                "varna": varna,
                "layer": layer,
                "missing_field": missing_field,
                "required_fields": self.REQUIRED_FIELDS,
            }
        )
        self.varna = varna
        self.layer = layer
        self.missing_field = missing_field


class Phase4AFileNotFoundError(Phase4AError):
    """
    Raised when a frozen ontology file cannot be located.
    """

    def __init__(self, file_name: str, expected_path: str):
        super().__init__(
            f"Frozen ontology file '{file_name}' not found",
            context={"file_name": file_name, "expected_path": expected_path}
        )
        self.file_name = file_name
        self.expected_path = expected_path


class Phase4AFileParseError(Phase4AError):
    """
    Raised when a frozen ontology file cannot be parsed as JSON.
    """

    def __init__(self, file_name: str, parse_error: str):
        super().__init__(
            f"Failed to parse frozen ontology file '{file_name}'",
            context={"file_name": file_name, "parse_error": parse_error}
        )
        self.file_name = file_name
        self.parse_error = parse_error
