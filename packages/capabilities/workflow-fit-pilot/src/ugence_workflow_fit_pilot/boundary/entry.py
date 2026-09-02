"""Boundary process entry point (§4.1). Started by the runner with the endpoint, the manifest
digest and a provider-factory dotted path. Performs exactly one dynamic import of that
module; the provider SDK is the caller's, never this package's."""

from __future__ import annotations

import argparse
import importlib
import json
import sys

from ..errors import PilotError, PilotErrorCode
from .server import BoundaryServer


def build_provider(factory_path: str):
    if ":" not in factory_path:
        raise PilotError(PilotErrorCode.PROVIDER_FACTORY_INVALID, "provider_factory must be 'package.module:function'")
    module_name, func_name = factory_path.split(":", 1)
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, func_name)
        provider = factory()
    except Exception as e:  # any failure aborts before a frame is served
        raise PilotError(PilotErrorCode.PROVIDER_FACTORY_INVALID, f"{type(e).__name__}: {e}") from None
    if not callable(getattr(provider, "complete", None)):
        raise PilotError(PilotErrorCode.PROVIDER_FACTORY_INVALID, "factory did not return a ProviderPort (no complete())")
    return provider


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True)
    p.add_argument("--manifest-digest", required=True)
    p.add_argument("--provider-factory", required=True)
    p.add_argument("--declaration-json", required=True, help="CaptureBoundaryDeclaration fields as JSON")
    args = p.parse_args(argv)
    try:
        provider = build_provider(args.provider_factory)
    except PilotError as e:
        sys.stderr.write(f"{e}\n")
        return 3
    decl = json.loads(args.declaration_json)
    decl["allowed_attested_fields"] = tuple(decl["allowed_attested_fields"])

    def ready() -> None:  # the runner blocks on this line; no clock or polling is needed
        sys.stderr.write("READY\n")
        sys.stderr.flush()

    BoundaryServer(manifest_digest=args.manifest_digest, provider=provider, declaration_fields=decl).serve(args.endpoint, ready=ready)
    return 0


if __name__ == "__main__":
    sys.exit(main())
