# Security

## Authorization is not execution
ActionGate returns an authorization decision only. It has no dispatch/execute/observe/
reconcile surface, so it cannot mutate enterprise state or cause an action to run.
Treating an AUTHORIZED result as proof of execution is a **caller** error the boundary
is designed to prevent.

## Fail closed
Unknown outcomes, malformed results, timeouts, unavailability, configuration and
protocol failures never authorize. Provider failures raise classified `ProviderError`s
that the framework normalizes to `INDETERMINATE`. Missing authority is never elevated.

## No secret material
Configuration accepts secret **references** only; observability records no secrets and
no vendor payloads.

## Remote transport
Remote mode is a client abstraction with no built-in transport. A real deployment must
supply independently secured transport and authentication; ActionGate does not provide
TLS, identity, or a credential system.

## Peer isolation
ActionGate and TAP are independent peers (neither imports the other), and the kernel
and framework never import ActionGate — verified by AST boundary tests and the wheel
content audit.

## Not production certified
Packaging verification is not a production certification. See `KNOWN_LIMITATIONS.md`.
