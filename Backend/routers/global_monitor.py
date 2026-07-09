from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder

from services.firebase_auth import verify_firebase_or_local_token
from services.worldmonitor_fetcher import (
    get_natural_hazards, get_earthquakes, get_conflict_events,
    get_gdalt_events, get_gdacs_alerts, get_supply_chain_news,
    get_market_quotes, get_energy_prices, get_macro_indicators,
    get_chokepoint_status, get_shipping_stress, get_shipping_indices,
    get_shipping_rates, get_country_instability, get_strategic_risk,
    get_market_implications, get_active_fires, get_aviation_intel,
    get_air_quality, get_critical_minerals, get_worldmonitor_bundle_snapshot,
)
from routers.helpers import (
    _set_cache_headers,
    _cached_json,
    _enqueue_celery_task,
)

logger = logging.getLogger("routers.global_monitor")
router = APIRouter(tags=["Global Monitoring"])


async def _cached_global_response(response: Response, suffix: str, producer, ttl_seconds: int = 900) -> Any:
    _set_cache_headers(response, public=True, max_age=30)
    data = await _cached_json(f"api:global:{suffix}", ttl_seconds, producer)
    return jsonable_encoder(data)


@router.get("/api/global/hazards")
async def api_global_hazards(response: Response):
    """Natural hazards: wildfires, storms, floods (NASA EONET)."""
    return await _cached_global_response(
        response,
        "hazards",
        lambda: {"data": get_natural_hazards(), "source": "NASA EONET"},
    )


@router.get("/api/global/earthquakes")
async def api_global_earthquakes(response: Response):
    """Earthquake feed M4.5+ worldwide (USGS)."""
    return await _cached_global_response(
        response,
        "earthquakes",
        lambda: {"data": get_earthquakes(), "source": "USGS"},
    )


@router.get("/api/global/conflict")
async def api_global_conflict(response: Response):
    """Armed conflict and protest events (ACLED)."""
    return await _cached_global_response(
        response,
        "conflict",
        lambda: {"data": get_conflict_events(), "source": "ACLED"},
    )


@router.get("/api/global/gdelt")
async def api_global_gdelt(response: Response):
    """Geopolitical event articles (GDELT)."""
    return await _cached_global_response(
        response,
        "gdelt",
        lambda: {"data": get_gdalt_events(), "source": "GDELT"},
        ttl_seconds=900,
    )


@router.get("/api/global/disasters")
async def api_global_disasters(response: Response):
    """Global disaster alerts (GDACS)."""
    return await _cached_global_response(
        response,
        "disasters",
        lambda: {"data": get_gdacs_alerts(), "source": "GDACS"},
    )


@router.get("/api/global/news/supply-chain")
async def api_global_supply_chain_news(response: Response):
    """Supply-chain focused news headlines (NewsAPI)."""
    return await _cached_global_response(
        response,
        "news-supply-chain",
        lambda: {"data": get_supply_chain_news(), "source": "NewsAPI"},
    )


@router.get("/api/global/market/quotes")
async def api_global_market_quotes(response: Response):
    """Equity quotes for shipping/logistics bellwethers (Finnhub)."""
    return await _cached_global_response(
        response,
        "market-quotes",
        lambda: {"data": get_market_quotes(), "source": "Finnhub"},
    )


@router.get("/api/global/energy")
async def api_global_energy(response: Response):
    """US crude inventories, natural gas storage (EIA)."""
    return await _cached_global_response(
        response,
        "energy",
        lambda: {"data": get_energy_prices(), "source": "EIA"},
    )


@router.get("/api/global/macro")
async def api_global_macro(response: Response):
    """Macro indicators: CPI, PMI, unemployment (FRED)."""
    return await _cached_global_response(
        response,
        "macro",
        lambda: {"data": get_macro_indicators(), "source": "FRED"},
    )


@router.get("/api/global/chokepoints")
async def api_global_chokepoints(response: Response):
    """Live-scored supply chain chokepoint risk (composite)."""
    return await _cached_global_response(
        response,
        "chokepoints",
        lambda: {"data": get_chokepoint_status(), "source": "Praecantator"},
    )


@router.get("/api/global/shipping/stress")
async def api_global_shipping_stress(response: Response):
    """Shipping stress index and carrier risk levels."""
    return await _cached_global_response(
        response,
        "shipping-stress",
        get_shipping_stress,
    )


@router.get("/api/global/shipping/indices")
async def api_global_shipping_indices(response: Response):
    """Reference shipping index metadata (SCFI, BDI, WCI, etc.)."""
    return await _cached_global_response(
        response,
        "shipping-indices",
        lambda: {"data": get_shipping_indices()},
        ttl_seconds=300,
    )


@router.get("/api/global/shipping/rates")
async def api_global_shipping_rates(response: Response):
    """Live shipping index values (FRED proxies + index registry)."""
    return await _cached_global_response(
        response,
        "shipping-rates",
        get_shipping_rates,
        ttl_seconds=300,
    )


@router.get("/api/global/country-instability")
async def api_global_country_instability(response: Response):
    """Country instability ranked list (ACLED + EONET aggregate)."""
    return await _cached_global_response(
        response,
        "country-instability",
        lambda: {"data": get_country_instability()},
    )


@router.get("/api/global/strategic-risk")
async def api_global_strategic_risk(response: Response):
    """Composite global strategic risk score (0-100) and level."""
    return await _cached_global_response(
        response,
        "strategic-risk",
        get_strategic_risk,
    )


@router.get("/api/global/market-implications")
async def api_global_market_implications(response: Response):
    """AI-generated market implications from active disruptions."""
    return await _cached_global_response(
        response,
        "market-implications",
        get_market_implications,
        ttl_seconds=900,
    )


@router.get("/api/global/fires")
async def api_global_fires(response: Response):
    """Active fire detections (NASA FIRMS satellite)."""
    return await _cached_global_response(
        response,
        "fires",
        lambda: {"data": get_active_fires(), "source": "NASA FIRMS"},
    )


@router.get("/api/global/aviation")
async def api_global_aviation(response: Response):
    """Live cargo flight data for major hubs (AviationStack)."""
    return await _cached_global_response(
        response,
        "aviation",
        lambda: {"data": get_aviation_intel(), "source": "AviationStack"},
    )


@router.get("/api/global/air-quality")
async def api_global_air_quality(response: Response):
    """Air quality index for major port cities (OpenAQ)."""
    return await _cached_global_response(
        response,
        "air-quality",
        lambda: {"data": get_air_quality(), "source": "OpenAQ"},
    )


@router.get("/api/global/minerals")
async def api_global_minerals(response: Response):
    """Critical mineral supply risk reference data."""
    return await _cached_global_response(
        response,
        "minerals",
        lambda: {"data": get_critical_minerals()},
        ttl_seconds=300,
    )


@router.post("/api/global/refresh")
async def api_global_refresh(user=Depends(verify_firebase_or_local_token)):
    """Force-trigger an immediate refresh of all worldmonitor data sources."""
    result = _enqueue_celery_task("scheduler.tasks.refresh_worldmonitor")
    result["message"] = "All worldmonitor data sources are being refreshed"
    return result


def _build_global_summary_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    def _as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, dict):
            nested = value.get("data")
            if isinstance(nested, list):
                return nested
            items = value.get("items")
            if isinstance(items, list):
                return items
            values = value.get("values")
            if isinstance(values, list):
                return values
        return []

    chokepoints = _as_list(snapshot.get("chokepoints"))
    instability = _as_list(snapshot.get("country_instability"))
    hazards = _as_list(snapshot.get("hazards"))
    fires = _as_list(snapshot.get("fires"))
    conflict = _as_list(snapshot.get("conflict"))

    return {
        "strategic_risk": snapshot.get("strategic_risk", {}),
        "shipping_stress": snapshot.get("shipping_stress", {}),
        "chokepoints": chokepoints[:5],
        "top_instability": instability[:10],
        "market_implications": snapshot.get("market_implications", {}),
        "active_hazards": len(hazards),
        "active_fires": len(fires),
        "conflict_events": len(conflict),
        "minerals": snapshot.get("minerals", []),
    }


def _build_global_dashboard_bundle_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    def _as_list(value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, dict):
            nested = value.get("data")
            if isinstance(nested, list):
                return nested
            items = value.get("items")
            if isinstance(items, list):
                return items
            values = value.get("values")
            if isinstance(values, list):
                return values
        return []

    return {
        "summary": _build_global_summary_from_snapshot(snapshot),
        "hazards": {"data": _as_list(snapshot.get("hazards")), "source": "NASA EONET"},
        "earthquakes": {"data": _as_list(snapshot.get("earthquakes")), "source": "USGS"},
        "conflict": {"data": _as_list(snapshot.get("conflict")), "source": "ACLED"},
        "gdelt": {"data": _as_list(snapshot.get("gdelt")), "source": "GDELT"},
        "disasters": {"data": _as_list(snapshot.get("disasters")), "source": "GDACS"},
        "news": {"data": _as_list(snapshot.get("news")), "source": "NewsAPI"},
        "market_quotes": {"data": _as_list(snapshot.get("market_quotes")), "source": "Finnhub"},
        "energy": {"data": snapshot.get("energy", {}), "source": "EIA"},
        "macro": {"data": snapshot.get("macro", {}), "source": "FRED"},
        "chokepoints": {"data": _as_list(snapshot.get("chokepoints")), "source": "Praecantator"},
        "shipping_stress": snapshot.get("shipping_stress", {}),
        "shipping_indices": {"data": _as_list(snapshot.get("shipping_indices"))},
        "shipping_rates": snapshot.get("shipping_rates", {}),
        "country_instability": {"data": _as_list(snapshot.get("country_instability"))},
        "strategic_risk": snapshot.get("strategic_risk", {}),
        "market_implications": snapshot.get("market_implications", {}),
        "fires": {"data": _as_list(snapshot.get("fires")), "source": "NASA FIRMS"},
        "aviation": {"data": _as_list(snapshot.get("aviation")), "source": "AviationStack"},
        "air_quality": {"data": _as_list(snapshot.get("air_quality")), "source": "OpenAQ"},
        "minerals": {"data": snapshot.get("minerals", [])},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/global/summary")
async def api_global_summary(response: Response):
    """Aggregate summary panel combining all worldmonitor data feeds."""
    return await _cached_global_response(
        response,
        "summary",
        lambda: _build_global_summary_from_snapshot(get_worldmonitor_bundle_snapshot()),
    )


@router.get("/api/global/dashboard-bundle")
async def api_global_dashboard_bundle(response: Response):
    """Aggregated worldmonitor payload for dashboard screens."""
    try:
        return await _cached_global_response(
            response,
            "dashboard-bundle",
            lambda: _build_global_dashboard_bundle_from_snapshot(get_worldmonitor_bundle_snapshot()),
            ttl_seconds=900,
        )
    except Exception as exc:
        logger.exception("dashboard-bundle failed: %s", exc)
        fallback = _build_global_dashboard_bundle_from_snapshot(get_worldmonitor_bundle_snapshot())
        return jsonable_encoder(fallback)
