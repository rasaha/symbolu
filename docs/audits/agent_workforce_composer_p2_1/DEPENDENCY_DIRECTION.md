# Dependency Direction — P2.1

AWC remains a leaf capability. Core dependency: `pydantic` only.

The new P2.1 modules (`adapter_v2.py`, `compatibility.py`) import ONLY: the standard
library, `pydantic` (via `AwcModel`), and other in-package AWC modules
(`.adapter`, `.canonical`, `.contracts`, `.dependency`, `.fingerprint`, `.version`,
`.workflow`). They import **nothing** from `ugence_policy_workflow_compiler`, Agent
Runtime, H16 (`agentic.agentic_framework`), H22, `ugence_model_selection`, ActionGate
execution, or any web framework (enforced by `test_no_forbidden_imports_in_p2_1_modules`
and `test_p2_1_does_not_import_compiler_package`).

The compiler's `workflow_ir.v2` is consumed as a serialized **document (dict)** —
the data-only seam is preserved and the dependency direction stays one-way: AWC
consumes the compiler's output; the compiler consumes nothing from AWC. The
compiler package is **not modified** by this PR.

The conformance generator (`conformance/generate_compiler_v2_conformance.py`) does
import the compiler to PRODUCE fixtures, but it is a build-time tool, not part of
the installed package or the runtime adapter; the committed fixtures let the test
suite run without the compiler present.
