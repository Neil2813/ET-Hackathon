"""
ERP Integration — Live Inventory & Throughput Synchronization

Status: SIMULATED (development / demo mode)

Real-world SCRM cannot rely on static `safety_stock_days` captured during onboarding.
This service is the planned integration layer with SAP/Oracle/Dynamics ERP systems.
In production, fetch_live_node_state() would call SAP OData (S/4HANA) or Oracle
NetSuite REST APIs to obtain real-time inventory burns and production ramp data.

For demo purposes, a deterministic random simulation is used so the output is
stable across the same incident run without requiring live ERP credentials.
"""
import random
from datetime import datetime, timezone
from typing import Dict, Any

def fetch_live_node_state(duns_number: str, internal_id: str) -> Dict[str, Any]:
    """
    Returns simulated real-time ERP telemetry.

    Production implementation would call:
      - SAP S/4HANA OData API (MM60/MBEW inventory views)
      - Oracle NetSuite SuiteQL REST endpoint
      - Dynamics 365 Supply Chain Management inventory API

    Current mode: SIMULATED — uses a deterministic seed so demo output is
    stable across the same node without requiring live ERP credentials.
    """
    # Deterministic seed: same node always produces same simulated values
    random.seed(hash(duns_number or internal_id) % 10000)

    return {
        "live_safety_stock_days": max(1, int(random.gauss(5, 3))),
        "live_daily_throughput_usd": max(0.0, random.gauss(12000.0, 5000.0)),
        "margin_percentage": random.uniform(0.15, 0.40),
        "sync_mode": "simulated",
        "sync_note": "Demo mode — deterministic simulation. Production wires to SAP OData/Oracle NetSuite REST.",
        "last_sync_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " (simulated)",
    }
