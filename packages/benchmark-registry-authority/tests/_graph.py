"""Graph-walking helpers shared by the adversarial suites.

Enumerating the reachable dataclass edges *mechanically* is what makes "at every
depth" a fact rather than a claim: the suites do not hand-list three or four
interesting nesting sites, they walk whatever the contract graph actually
contains, so a payload gaining a nested field automatically gains adversarial
coverage at that site.
"""

from __future__ import annotations

import dataclasses


def dataclass_edges(root, path="$"):
    """Yield ``(parent, field_name, child, path, depth)`` for every nested node.

    Depth-first, full depth, every reachable dataclass field — BR-2A payloads and
    the frozen BR-1 contracts nested inside them alike.
    """

    stack = [(root, path, 0)]
    while stack:
        node, node_path, depth = stack.pop()
        for f in dataclasses.fields(node):
            child = getattr(node, f.name)
            if dataclasses.is_dataclass(child) and not isinstance(child, type):
                child_path = f"{node_path}.{f.name}"
                yield node, f.name, child, child_path, depth + 1
                stack.append((child, child_path, depth + 1))


def max_depth(root) -> int:
    return max((depth for *_rest, depth in dataclass_edges(root)), default=0)
