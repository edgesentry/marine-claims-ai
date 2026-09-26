from __future__ import annotations

from marine_claims_ai.ontology.compartments import (
    build_compartment_graph,
    normalize_zone,
    validate_causality,
)


def test_normalize_zone_aliases():
    assert normalize_zone("球状船首") == "hull_forward"
    assert normalize_zone("機関室") == "machinery"
    assert normalize_zone("hull_mid") == "hull_mid"
    assert normalize_zone("未知の区画XYZ") is None


def test_same_compartment_is_valid():
    result = validate_causality("機関室", "機関")
    assert result["valid"] is True
    assert result["reason"] == "same_compartment"


def test_adjacent_hull_path_allowed():
    result = validate_causality("球状船首", "外板")
    assert result["valid"] is True
    assert result["reason"] == "path_exists"
    assert result["path"] == ["hull_forward", "hull_mid"]


def test_watertight_barrier_blocks_forward_hull_to_machinery():
    result = validate_causality("球状船首", "機関室")
    assert result["valid"] is False
    assert result["reason"] == "watertight_barrier_violation"
    assert result["path"] is None


def test_unknown_zone_rejected():
    result = validate_causality("球状船首", "未知区画アルファ")
    assert result["valid"] is False
    assert result["reason"] == "unknown_zone"


def test_graph_includes_isolated_machinery_node():
    g = build_compartment_graph()
    assert "machinery" in g.nodes
    assert g.degree("machinery") == 0
