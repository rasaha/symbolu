"""Read-only handlers for the discovery/inspection phase.

Read-only tools carry NO execution authority: they return non-sensitive metadata
only, cause no side effects, obtain no credentials, and mint no execution token.
They are deliberately separate from the runtime gateway's mutating adapters (which
can only be driven by a verified token + broker capability).
"""

from __future__ import annotations


def kubernetes_get(args: dict) -> dict:
    # MOCK: no real cluster contact; metadata only.
    return {"kind": args.get("kind"), "name": args.get("name"),
            "namespace": args.get("namespace"), "phase": "Running",
            "mocked": "true", "read_only": "true"}


def iam_inspect(args: dict) -> dict:
    # MOCK: no real IAM control-plane contact.
    return {"role": args.get("role"), "attached_policies": ["ReadOnlyAccess"],
            "mocked": "true", "read_only": "true"}


def terraform_plan(args: dict) -> dict:
    # MOCK: preview only; the bound simulation evidence is produced separately.
    return {"workspace": args.get("workspace"), "summary": "1 to change, 0 to destroy",
            "mocked": "true", "read_only": "true"}


HANDLERS = {
    "kubernetes.get": kubernetes_get,
    "iam.inspect": iam_inspect,
    "terraform.plan": terraform_plan,
}
