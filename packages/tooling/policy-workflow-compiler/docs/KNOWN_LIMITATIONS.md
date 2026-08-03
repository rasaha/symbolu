# Known Limitations

This is a Phase 1 tooling product. Its scope is deliberately narrow, and the
boundaries below are design decisions, not defects. Documenting them keeps
expectations honest and prevents misuse.

## No ingestion, NLP, or LLM

The compiler consumes an **already-structured, already-reviewed** policy pack. It
does **not** extract policy from documents, parse natural language, or use a
language model. Document extraction is not implemented
(`document_extraction_implemented=false`). Turning source documents into a
structured pack is out of scope and must happen upstream.

## No runtime

The compiler produces a workflow IR and an assurance package — structure. It does
**not** execute the workflow, evaluate live cases, or deploy anything. Runtime
deployment is not implemented (`runtime_deployment_implemented=false`).
Downstream capabilities, not this tooling, execute.

## No connectors

Although the object model includes `ConnectorMapping`, the compiler does not
operate connectors or perform any integration. It emits mappings as data; it does
not call external systems. There are no network calls and no credentials.

## Declarative predicates only

Rules and conditions are declarative triples (`fact_key` + `Comparator` +
`value`), never executable Python (see `POLICY_PACK_SCHEMA.md`). The compiler
cannot express or run arbitrary logic. Anything requiring imperative computation
is outside the model.

## Exact, not semantic, diff

The structural diff compares objects exactly, at the field level. It performs no
natural-language semantic comparison and will not recognize two differently
worded but "equivalent" descriptions as the same (see `STRUCTURAL_DIFF.md`).

## Equivalence limited to Procurement

The reference-equivalence harness validates the compiler's interpretation against
exactly one live product, `ugence-procurement`, across five modeled dimensions
(see `PROCUREMENT_REFERENCE_VALIDATION.md`). No equivalence claim is made for any
other domain or product.

## Maturity gates not yet met

`pilot_validated=false` and `production_certified=false`. This product has not
been pilot-validated or production-certified. See `MATURITY.md` for the full set
of maturity booleans and what each asserts.
