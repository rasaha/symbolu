# Workflow Visualization

Deterministic layered-DAG SVG graph plus a synchronized accessible node list. Node
disposition (the 8 AWC categories) drives color + a non-color glyph. Zoom / fit /
scroll-pan; selectable by mouse and keyboard. All nodes, edges and dispositions
come from `GET /scenarios/{id}/workflow`; nothing is inferred client-side.
