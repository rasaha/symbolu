# Dependencies

- **Runtime:** Node.js v22 standard library only. No npm packages, no `package.json` dependencies, no network, no LLM, no embedding model, no external entity database.
- Unicode NFC is provided by the built-in `String.prototype.normalize('NFC')`; SHA-256 and hex/base64 by the built-in `crypto`/`Buffer`; strict UTF-8 validation by `TextDecoder({fatal:true})`.
- No dependency is shared with Implementation A (a Python project). The only shared inputs are the immutable v1.1.1 package resources/schemas.
