# Workflow Graph Design

- **Deterministic layered layout** (`features/workflow/layout.ts`): layer =
  longest path from a source; row = stable index within a layer ordered by
  `node_id`. Identical API input → identical positions. No randomness, no
  animation-derived state.
- **Rendering**: SVG rectangles per node, straight edges with arrowheads. Node
  fill/accent derives from the AWC-authoritative disposition (the 8 categories);
  a non-color glyph accompanies every disposition.
- **Interaction**: zoom in/out/fit; scrollable region for pan; nodes selectable by
  mouse and keyboard (role="button", Enter/Space). A visible legend maps every
  disposition.
- **Accessibility**: a synchronized `WorkflowNodeList` is the primary keyboard
  path — name, kind, disposition (pill with glyph), in/out dependency counts,
  selection kept in sync with the graph via the shared store.
- **No client classification**: dispositions and edges come only from the API.
