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
            "path": None,
        }
    if src == dst:
        return {
            "valid": True,
            "reason": "same_compartment",
            "damage_node": src,
            "repair_node": dst,
            "path": [src],
        }
    ok = nx.has_path(g, src, dst)
    return {
        "valid": ok,
        "reason": "path_exists" if ok else "watertight_barrier_violation",
        "damage_node": src,
        "repair_node": dst,
        "path": nx.shortest_path(g, src, dst) if ok else None,
    }


def validate_claims_causality(
    damage_zone: str,
    repair_zone: str,
    *,
    max_hops: int = 1,
    graph: nx.DiGraph | None = None,
) -> dict:
    """
    Stricter gate for concurrent-repair screening.

    Graph connectivity alone would allow bow damage to reach propulsion via mid/aft hull.
    Claims screening only accepts same compartment or adjacent compartments (default max_hops=1).
    """
    base = validate_causality(damage_zone, repair_zone, graph=graph)
    if not base["valid"]:
        return base
    if base["reason"] == "same_compartment":
        return {**base, "hops": 0}
    path = base.get("path") or []
    hops = max(0, len(path) - 1)
    if hops <= max_hops:
        return {**base, "reason": "adjacent_compartment", "hops": hops}
    return {
        "valid": False,
        "reason": "beyond_casualty_propagation_limit",
        "damage_node": base["damage_node"],
        "repair_node": base["repair_node"],
        "path": path,
        "hops": hops,
        "max_hops": max_hops,
    }


def any_damage_allows_repair(
    damaged_components: list[str],
    repair_zone: str,
    *,
    max_hops: int = 1,
    graph: nx.DiGraph | None = None,
) -> dict:
    """Return the best (valid preferred) claims-causality result across casualty damage labels."""
    g = graph or build_compartment_graph()
    best_invalid: dict | None = None
    for label in damaged_components:
        result = validate_claims_causality(label, repair_zone, max_hops=max_hops, graph=g)
        if result["valid"]:
            return result
        best_invalid = result
    if best_invalid is not None:
        return best_invalid
    return {
        "valid": False,
        "reason": "no_damage_zones",
        "damage_node": None,
        "repair_node": normalize_zone(repair_zone),
        "path": None,
    }


# Ordered rules: first match wins. Used by appraisal pipeline dual-check.
_REPAIR_ZONE_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (
        (
            "主機関",
            "ピストン",
            "吸排気弁",
            "燃料噴射弁",
            "発電機関",
            "機関室",
            "カロリーファイヤー",
            "汚物処理",
            "減速機",
            "クラッチ",
            "ポンプ",
            "シリンダー",
            "波止弁",
            "亜鉛",
            "電磁弁",
        ),
        "machinery",
    ),
    (("プロペラ軸", "プロペラ", "推進器", "舵頭", "舵板", "ラダー"), "propulsion"),
    (("バウスラスター", "球状船首", "錨鎖", "船首"), "hull_forward"),
    (("船体外板", "船側外板", "船底外板"), "hull_mid"),
    (("居住区", "船橋", "ブリッジ"), "superstructure"),
    (("甲板",), "deck_mid"),
]


def infer_repair_zone(description: str, category: str = "") -> str | None:
    """Map a repair line-item description to a compartment node (or None if unmapped)."""
    blob = f"{category} {description}"
    # Bow thruster work is forward-hull; check before propeller/propulsion keywords.
    if "バウスラスター" in description and "機関室" not in description:
        if description.strip().startswith("バウスラスター") or "プロペラ研磨" in description:
            return "hull_forward"
    if "機関" in category and "甲板" not in description:
        for keys, zone in _REPAIR_ZONE_PATTERNS:
            if any(k in blob for k in keys):
                return zone
        return "machinery"
    for keys, zone in _REPAIR_ZONE_PATTERNS:
        if any(k in blob for k in keys):
            return zone
    return None


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
