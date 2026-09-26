#!/usr/bin/env python3
"""
Naval architecture compartment graph (NetworkX).

Mechanically rejects causal links that cannot propagate across watertight boundaries.
"""

from __future__ import annotations

import argparse
import json
import sys

import networkx as nx

# Physical adjacency for casualty propagation.
# Machinery space is intentionally isolated (watertight bulkhead barrier):
# forward hull damage cannot justify engine-room line items.
COMPARTMENT_EDGES: list[tuple[str, str]] = [
    ("hull_forward", "hull_mid"),
    ("hull_mid", "hull_aft"),
    ("hull_forward", "deck_forward"),
    ("hull_mid", "deck_mid"),
    ("hull_aft", "deck_aft"),
    ("hull_aft", "propulsion"),
    ("deck_forward", "deck_mid"),
    ("deck_mid", "deck_aft"),
    ("deck_mid", "superstructure"),
]

ISOLATED_NODES = ("machinery",)

ZONE_ALIASES: dict[str, str] = {
    "球状船首": "hull_forward",
    "船首": "hull_forward",
    "外板": "hull_mid",
    "船体": "hull_mid",
    "船尾": "hull_aft",
    "機関室": "machinery",
    "機関": "machinery",
    "推進器": "propulsion",
    "舵": "propulsion",
    "甲板": "deck_mid",
    "居住区": "superstructure",
    "ブリッジ": "superstructure",
}


def build_compartment_graph() -> nx.DiGraph:
    g = nx.DiGraph()
    nodes = sorted({n for e in COMPARTMENT_EDGES for n in e} | set(ISOLATED_NODES))
    g.add_nodes_from(nodes)
    for a, b in COMPARTMENT_EDGES:
        g.add_edge(a, b)
        g.add_edge(b, a)  # undirected physical adjacency as bidirectional
    return g


def normalize_zone(label: str) -> str | None:
    label = (label or "").strip()
    if label in ZONE_ALIASES.values():
        return label
    for key, node in ZONE_ALIASES.items():
        if key in label:
            return node
    return None


def validate_causality(damage_zone: str, repair_zone: str, graph: nx.DiGraph | None = None) -> dict:
    g = graph or build_compartment_graph()
    src = normalize_zone(damage_zone)
    dst = normalize_zone(repair_zone)
    if src is None or dst is None:
        return {
            "valid": False,
            "reason": "unknown_zone",
            "damage_node": src,
            "repair_node": dst,
        }
    if src == dst:
        return {"valid": True, "reason": "same_compartment", "damage_node": src, "repair_node": dst}
    ok = nx.has_path(g, src, dst)
    return {
        "valid": ok,
        "reason": "path_exists" if ok else "watertight_barrier_violation",
        "damage_node": src,
        "repair_node": dst,
        "path": nx.shortest_path(g, src, dst) if ok else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--damage-zone", required=True)
    parser.add_argument("--repair-zone", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate_causality(args.damage_zone, args.repair_zone)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "VALID" if result["valid"] else "REJECTED"
        print(f"{status}: {args.damage_zone!r} -> {args.repair_zone!r} ({result['reason']})")
        if result.get("path"):
            print("path:", " -> ".join(result["path"]))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
