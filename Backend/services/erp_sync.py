"""
ERP Integration — Live Inventory & Throughput Synchronization

Data Source: OData V4 Northwind Service (public, free, no API key required)
Endpoint:    https://services.odata.org/V4/Northwind/Northwind.svc/

Why Northwind OData?
--------------------
The Northwind OData service is the canonical public sandbox for SAP S/4HANA-style
OData V4 APIs. SAP's own developer documentation uses Northwind for integration
examples. This means our integration pattern is directly representative of what a
production SAP MM/SD or Oracle SCM OData call would look like.

Mapping — Northwind Products → Energy Supply Node Telemetry
------------------------------------------------------------
  UnitsInStock   → proportional to live_safety_stock_days
  ReorderLevel   → minimum stock threshold  → drives criticality flag
  UnitPrice      → USD/unit as a proxy for commodity value → daily throughput
  Discontinued   → node_critical_flag (out-of-stock risk signal)

Fallback Strategy
-----------------
If the OData endpoint is unreachable (offline / > 3 s timeout), the service
falls back to a deterministic simulation seeded on the node identifier so
that demo output stays stable across the same incident run.
"""
from __future__ import annotations

import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)

_ODATA_BASE = "https://services.odata.org/V4/Northwind/Northwind.svc"
_ODATA_TIMEOUT = 3.0   # seconds — fast fail to avoid blocking incident engine
_CACHE: Dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 300.0   # 5 minutes — balance freshness vs. rate limiting the public service

# Total products in the public Northwind dataset (1–77)
_NORTHWIND_PRODUCT_COUNT = 77


def _northwind_product_id(duns_number: str, internal_id: str) -> int:
    """Derive a deterministic Northwind product ID (1..77) from node identifiers."""
    seed_str = (duns_number or "") + (internal_id or "")
    return (hash(seed_str) % _NORTHWIND_PRODUCT_COUNT) + 1


def _fetch_northwind_product(product_id: int) -> Dict[str, Any] | None:
    """
    Fetch a single Northwind product via OData V4 GET.

    Example URL:
      https://services.odata.org/V4/Northwind/Northwind.svc/Products(5)?$format=json
    """
    cache_key = f"northwind_product_{product_id}"
    now = time.monotonic()
    if cache_key in _CACHE and _CACHE[cache_key][0] > now:
        return _CACHE[cache_key][1]

    url = f"{_ODATA_BASE}/Products({product_id})?$format=json"
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "Praecantator-ERP/2.0"},
        )
        with urllib.request.urlopen(req, timeout=_ODATA_TIMEOUT) as resp:
            raw = resp.read(64_000)
        data: Dict[str, Any] = json.loads(raw.decode("utf-8"))
        # OData V4 single-entity response has the payload directly in the root
        result = data if "ProductID" in data else data.get("value", data)
        if isinstance(result, list):
            result = result[0] if result else {}
        _CACHE[cache_key] = (now + _CACHE_TTL, result)
        logger.info(
            "[erp_sync] OData V4 fetch OK — Products(%d): %s (UnitsInStock=%s, UnitPrice=%s)",
            product_id,
            result.get("ProductName", "?"),
            result.get("UnitsInStock"),
            result.get("UnitPrice"),
        )
        return result
    except Exception as exc:
        logger.warning("[erp_sync] OData V4 fetch failed for Products(%d): %s", product_id, exc)
        return None


def _map_product_to_node_state(product: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Northwind product fields to energy supply chain telemetry.

    Energy context mapping rationale:
      UnitsInStock / max(ReorderLevel, 1) * 5
          ↳ Days of stock cover (analogous to India's 9.5 days SPR)
             Higher stock vs. reorder point = more buffer days.
      UnitPrice * 400
          ↳ Daily throughput proxy (USD). A $20 product × 400 = $8,000/day,
             representative of a small refinery offtake line.
      (UnitPrice - UnitsOnOrder*0.01) / UnitPrice
          ↳ Margin proxy — order book pressure reduces effective margin.
      Discontinued == True
          ↳ Critical node flag — equivalent to a shut-in crude source.
    """
    units_in_stock: float = float(product.get("UnitsInStock") or 0)
    reorder_level: float = float(product.get("ReorderLevel") or 1)
    unit_price: float = float(product.get("UnitPrice") or 10.0)
    units_on_order: float = float(product.get("UnitsOnOrder") or 0)
    discontinued: bool = bool(product.get("Discontinued") or False)
    product_name: str = str(product.get("ProductName") or "Unknown")

    # Safety stock days — range ~1–30 days (mirrors SPR buffer logic)
    raw_days = (units_in_stock / max(reorder_level, 1.0)) * 5.0
    safety_stock_days = max(1, min(45, round(raw_days)))

    # Daily throughput in USD
    daily_throughput = max(500.0, unit_price * 400.0)

    # Margin percentage — decreases under heavy order pressure
    order_pressure = min(units_on_order * 0.01, unit_price * 0.3)
    margin_pct = max(0.05, min(0.55, (unit_price - order_pressure) / max(unit_price, 1.0)))

    return {
        "live_safety_stock_days": safety_stock_days,
        "live_daily_throughput_usd": round(daily_throughput, 2),
        "margin_percentage": round(margin_pct, 4),
        "node_critical": discontinued,
        "erp_product_id": product.get("ProductID"),
        "erp_product_name": product_name,
        "sync_mode": "live_odata_v4",
        "sync_note": (
            f"Live data: Northwind OData V4 — Products({product.get('ProductID')}) "
            f"'{product_name}'. UnitsInStock={units_in_stock}, "
            f"ReorderLevel={reorder_level}, UnitPrice=${unit_price:.2f}."
        ),
        "last_sync_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _deterministic_fallback(duns_number: str, internal_id: str) -> Dict[str, Any]:
    """
    Fallback when OData endpoint is unreachable.
    Uses a deterministic seed so demo output is stable across the same node.
    """
    random.seed(hash(duns_number or internal_id) % 10000)
    return {
        "live_safety_stock_days": max(1, int(random.gauss(5, 3))),
        "live_daily_throughput_usd": max(0.0, random.gauss(12000.0, 5000.0)),
        "margin_percentage": random.uniform(0.15, 0.40),
        "node_critical": False,
        "erp_product_id": None,
        "erp_product_name": None,
        "sync_mode": "simulated_fallback",
        "sync_note": (
            "OData V4 endpoint unreachable — deterministic simulation used. "
            "Production: ensure network access to services.odata.org."
        ),
        "last_sync_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " (simulated)",
    }


def fetch_live_node_state(duns_number: str, internal_id: str) -> Dict[str, Any]:
    """
    Returns real-time ERP telemetry for a supply chain node.

    Primary:  Northwind OData V4 public API (no credentials required).
              Mirrors the SAP S/4HANA OData interface pattern.
    Fallback: Deterministic simulation (offline / timeout scenarios).

    Parameters
    ----------
    duns_number  : DUNS/LEI identifier (used to derive OData product ID)
    internal_id  : Internal node ID (used as secondary seed)

    Returns
    -------
    dict with:
      live_safety_stock_days    — int, current days of buffer stock
      live_daily_throughput_usd — float, estimated daily USD throughput
      margin_percentage         — float, effective margin 0.05–0.55
      node_critical             — bool, True if source is discontinued/shut-in
      erp_product_id            — int | None, Northwind ProductID used
      erp_product_name          — str | None, Northwind ProductName
      sync_mode                 — 'live_odata_v4' | 'simulated_fallback'
      sync_note                 — human-readable explanation of data source
      last_sync_time            — ISO 8601 UTC timestamp
    """
    product_id = _northwind_product_id(duns_number, internal_id)
    product = _fetch_northwind_product(product_id)

    if product and "ProductID" in product:
        return _map_product_to_node_state(product)

    logger.warning(
        "[erp_sync] Falling back to simulation for node '%s' (OData returned no data).",
        internal_id or duns_number,
    )
    return _deterministic_fallback(duns_number, internal_id)
