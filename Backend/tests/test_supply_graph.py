import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timezone

from models.supply_graph import CustomerSupplyGraph, SupplyNode, SupplyEdge

def test_supply_node_creation():
    raw_supplier = {
        "id": "sup-01",
        "name": "Global Tech Supplier",
        "tier": 1,
        "country": "Germany",
        "lat": 51.1657,
        "lng": 10.4515,
        "contract_value_usd": 500000,
        "criticality": "high",
        "single_source": True
    }
    node = SupplyNode.from_context_supplier("tenant_123", raw_supplier)
    
    assert node.id == "sup-01"
    assert node.tenant_id == "tenant_123"
    assert node.tier == 1
    assert node.contract_value_usd == 500000.0
    assert node.location_precision == "exact"
    assert node.single_source is True
    assert node.criticality == "high"


def test_graph_from_context():
    context = {
        "company_name": "Test Corp",
        "suppliers": [
            {
                "id": "t1-01",
                "name": "Tier 1 Supplier",
                "tier": 1,
                "country": "Germany",
                "single_source": False
            },
            {
                "id": "t2-01",
                "name": "Tier 2 Sub-Supplier",
                "tier": 2,
                "country": "China",
                "single_source": True
            }
        ],
        "logistics_nodes": [
            {
                "id": "port-01",
                "name": "Port of Hamburg",
                "country": "Germany",
                "lat": 53.5511,
                "lng": 9.9937
            }
        ]
    }
    
    graph = CustomerSupplyGraph.from_context("tenant_123", context)
    
    assert len(graph.nodes) == 3
    assert "t1-01" in graph.nodes
    assert "t2-01" in graph.nodes
    assert "port-01" in graph.nodes
    
    # Check auto-wiring of edges (Tier 2 -> Tier 1)
    assert len(graph.edges) >= 1
    edge = next(e for e in graph.edges if e.from_id == "t2-01" and e.to_id == "t1-01")
    assert edge is not None
    assert edge.tier_level == 2

def test_gnn_adapter():
    context = {
        "suppliers": [{"id": "t1-01", "name": "Tier 1 Supplier", "tier": 1, "country": "Germany"}]
    }
    graph = CustomerSupplyGraph.from_context("tenant_123", context)
    gnn_graph = graph.to_gnn_graph()
    
    assert len(gnn_graph.nodes) == 1
    assert gnn_graph.nodes["t1-01"].name == "Tier 1 Supplier"
