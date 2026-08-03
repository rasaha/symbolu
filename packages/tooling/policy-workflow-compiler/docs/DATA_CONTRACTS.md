# Data Contracts

Typed references replace opaque contract strings for role-relevant nodes.

- `DataContractRef`: `contract_id`, `contract_data_version`, `schema_ref`,
  `data_classification_ref`, `resolution`, `provenance`.
- `NodeInputRequirement`: a required input `DataContractRef` + resolved
  `producer_node_id` + `compatibility_requirement`.
- `NodeOutputDeclaration`: a produced `DataContractRef` + resolved `consumer_node_ids`.

## Derivation

Output declarations come from the node's `output_contract`; consumers are the
targets of its spine edges (`ON_PASS`/`NEXT`). Input requirements come from the
output contracts of spine predecessors, with the producer node resolved. Ordering is
canonical. Unknown compatibility fails closed at validation; malformed/dangling
contract references make a release `INVALID`. No compatibility is guessed from
similar names.

`contract_data_version` is explicit but empty for v1-sourced graphs (v1 carries no
per-contract version). A future compiler contract may emit typed `{contract_id,
contract_version}` at the node — see the P3A ownership recommendations.
