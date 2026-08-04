# Authority Boundary

```
authority_class:                        ADVISORY
execution_capability:                   NONE
provider_invocation_capability:         NONE
credential_access:                      NONE
routing_decision_is_authority:          false
live_provider_calls_enabled_by_default: false
recommendation_only:                    true
```

## What the controller does

It **recommends** a model/provider route: it discovers candidates, filters them against hard policy and
capability constraints, scores the survivors, and returns a ranked recommendation with fallback and
escalation *recommendations*, an explanation, and reproducible evidence. Every recommendation is stamped
`execution_status = NOT_EXECUTED` and `recommendation_only = True`.

## What the controller must never do

- Call a provider API or execute a model inference request.
- Load, read, or discover provider credentials (env vars, cloud profiles, key files).
- Open a socket, make an HTTP request, or transmit anything over the network.
- Execute a retry, a fallback, or an escalation.
- Run a tool, an agent, or a subprocess; start a background worker.
- Commit billing or change provider configuration.

A steering **recommendation is not authority**: it is advice for a separately governed runtime, which
owns the decision of whether and how to execute.

## Fallback & escalation are recommendations

`FallbackRecommendation` lists ordered fallback candidates and the *conditions* under which fallback is
appropriate, plus whether human/governance escalation is *recommended* and why. The controller executes
none of it. Fallback and retry **execution** belong to the Agent Runtime or another governed execution
layer.

## How this is enforced

1. **Static (source):** `tests/boundaries/test_advisory_boundary.py` parses every module and forbids
   provider-SDK / network / subprocess imports and credential/network usage patterns.
2. **Static (wheel):** the distribution verifier repeats the scan over the **packaged** wheel source.
3. **Runtime:** the verifier and `tests/side_effects/` run import and recommendation under a Python
   audit hook that hard-fails on any `socket.connect`/`bind`, `subprocess.Popen`, or `os.exec`, and
   poison credential-shaped env vars to prove they are never read.
4. **Manifest:** `module_manifest.json` declares the authority fields above; a test asserts they match.
