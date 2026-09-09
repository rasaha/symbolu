# Published `LV-1` vocabularies

**What is in this directory:** the canonical content of the governance label
vocabularies, one immutable specification per vocabulary per version. **What is not:**
issued organizational policy. `PUB-1` is explicit on the distinction, and it is the
one thing to carry away from this page — a specification here establishes *what the
members are and what they mean*; production authority still requires an issued Policy
Authority coordinate, which no file here is or claims to be.

## Why the files come before the fields

A record cannot cite a vocabulary that does not exist. `PUB-1` sequences publication
ahead of every record binding for that reason: a reference to a missing referent is a
field that records nothing while appearing to record provenance. So these documents
exist first, and `PUB-2`'s record-local references follow.

## Layout and versioning

```
docs/vocabularies/<identifier>/<version>.json
```

`MAJOR.MINOR.PATCH`, no `v` prefix. **There is no `latest`**, by ruling and by gate:
any change to normative membership, meaning, ordering or interpretation takes a **new
major version**; a citation or wording correction that *provably* changes no meaning
may take a **patch**; **minor versions are reserved** until an additive-compatibility
rule is separately established.

Each file carries the six identity elements `PUB-1` requires — identifier, version,
authoritative content digest, scope or tenant, governing `LV` ruling, and normative
members (or, for an open vocabulary, its interpretation rules).

## The digest is the immutability

`content_digest` is SHA-256 over the canonical JSON of the specification with the
digest field removed — `sort_keys=True`, `separators=(",", ":")`, UTF-8.
`scripts/check_vocabulary_publications.py` recomputes it, so **editing a published
version fails CI**. That is what makes "immutable" a property of this repository
rather than a sentence in a document. The gate also holds each closed vocabulary's
members to the ballot section that ratified them, refuses a `latest` in any form, and
refuses any file that claims Policy Authority issuance. Its twin,
`tests/boundaries/test_vocabulary_publications.py`, provokes each of those failures to
prove the gate can fail.

To publish a new version: write the file with any digest, run the gate, and record the
digest it reports as expected.

## Published

| Identifier | Version | Ruling | Shape | Intended binding |
|---|---|---|---|---|
| `eu-ai-act-system-classification` | 1.0.0 | `LV-B` | closed, 5 members | `SystemRegistration.classification_label` |
| `data-classification` | 1.0.0 | `LV-A` / `DE-3` | closed, 4 members | `DataUseDeclaration.classification` |
| `data-use-purpose` | 1.0.0 | `LV-E` | open shape | `DataUseDeclaration.purpose_label` |
| `incident-severity` | 1.0.0 | `LV-D` | closed, 4 members | `IncidentRecord.severity_label` |

**No binding is implemented.** Every "intended binding" above names the field a future
`PUB-2` change will attach a reference to; none carries one today, and each file says
so of itself.

**`vendor-dependency-assessment-state` is ruled and not yet published.** Its name was
resolved by `PUB-1a` — the members `LV-C` ratified are assessment states, and the
earlier `vendor-dependency-permission` named a permission the members refuse and `VR-3`
forbids. Publication under the corrected name is authorized and remains to be done.

## Where the rulings live

- `docs/architecture/LV1_VOCABULARY_PUBLICATION_RULINGS.md` — `PUB-1` to `PUB-5`
- `docs/architecture/GOVERNANCE_LABEL_VOCABULARY_BALLOT.md` — `LV-A` to `LV-F`
- `docs/architecture/VOCABULARY_VERSION_FIELD_SCOPING.md` — `VV-A` to `VV-E`

Nothing in this directory interprets a label. `§2` of the ballot lists four conditions
that must hold before any package may interpret rather than record one; publication
satisfies the first, and the interpreting layer still does not exist.
