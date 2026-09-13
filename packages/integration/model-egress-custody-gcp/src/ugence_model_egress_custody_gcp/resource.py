"""The pinned secret-version resource, parsed and refused before any client call.

``latest`` never reaches Google from here: the resource is validated, split and matched
against the designation *in this process*, so a misconfiguration is a local refusal
rather than a request that resolves to whatever the alias points at today.
"""

from __future__ import annotations

from dataclasses import dataclass

from ugence_model_egress_unit import is_pinned_secret_version, looks_like_a_credential

__all__ = ["SecretVersionResource", "ResourceRefused", "parse_secret_version"]


class ResourceRefused(ValueError):
    """A secret-version resource this adapter will not send to Secret Manager. The
    message names the rule and never echoes a value that carried a credential shape."""


@dataclass(frozen=True)
class SecretVersionResource:
    """``projects/<project>/secrets/<secret>/versions/<n>``, already validated."""

    project: str
    secret: str
    version: int

    @property
    def resource(self) -> str:
        return f"projects/{self.project}/secrets/{self.secret}/versions/{self.version}"

    @property
    def secret_resource(self) -> str:
        return f"projects/{self.project}/secrets/{self.secret}"


def parse_secret_version(resource: str) -> SecretVersionResource:
    """The parsed resource, or :class:`ResourceRefused`.

    Refused: a non-string; surrounding whitespace; ``latest`` or any other alias; a
    non-numeric, zero, negative or zero-padded version; a missing or empty segment; a
    trailing slash; anything that is not exactly six segments; and a value carrying a
    credential shape, which is how a pasted key in the wrong field is caught.
    """

    if not isinstance(resource, str) or not resource:
        raise ResourceRefused("a secret version resource is required "
                              "(projects/<project>/secrets/<secret>/versions/<n>)")
    if resource != resource.strip():
        raise ResourceRefused("the secret version resource carries surrounding whitespace")
    if looks_like_a_credential(resource):
        raise ResourceRefused(
            "the secret version field carries a credential shape; this field names WHERE the "
            "secret lives and never the secret itself")
    if not is_pinned_secret_version(resource):
        parts = resource.split("/")
        if len(parts) == 6 and parts[4] == "versions" and not parts[5].isdigit():
            raise ResourceRefused(
                f"the version segment must be an exact number; "
                f"{'an alias or other non-numeric segment' if parts[5] else 'an empty segment'} "
                f"resolves during execution and is never pinned (LP-2)")
        raise ResourceRefused(
            "the resource must be exactly projects/<project>/secrets/<secret>/versions/<n> with a numeric <n>")
    _, project, _, secret, _, version = resource.split("/")
    if version != str(int(version)):
        raise ResourceRefused("the version segment is zero-padded; a version is written as its own number")
    if int(version) < 1:
        raise ResourceRefused("secret versions are numbered from 1")
    return SecretVersionResource(project=project, secret=secret, version=int(version))
