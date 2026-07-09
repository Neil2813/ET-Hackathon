from __future__ import annotations

import logging
import os
import httpx
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Cache parameters
_WEATHER_CACHE: dict[str, dict] = {}
_CACHE_TTL = timedelta(minutes=10)

CHOKEPOINTS = {
    "hormuz": {"name": "Strait of Hormuz", "lat": 26.58, "lng": 56.25},
    "suez_n": {"name": "Suez Canal (North)", "lat": 31.25, "lng": 32.35},
    "suez_s": {"name": "Suez Canal (South)", "lat": 29.95, "lng": 32.55},
    "bab_el_mand": {"name": "Bab-el-Mandeb", "lat": 12.58, "lng": 43.33},
    "malacca_w": {"name": "Strait of Malacca (West)", "lat": 5.60, "lng": 95.00},
    "malacca_e": {"name": "Strait of Malacca (East)", "lat": 1.35, "lng": 103.95},
    "panama_n": {"name": "Panama Canal (North)", "lat": 9.38, "lng": -79.92},
    "panama_s": {"name": "Panama Canal (South)", "lat": 8.92, "lng": -79.52},
    "cape_good": {"name": "Cape of Good Hope", "lat": -34.35, "lng": 18.47},
}


def get_chokepoint_weather(chokepoint_id: str) -> dict:
    """
    Fetch weather info (wave height, wind speed) for a chokepoint.
    Includes a 10-minute cache to prevent spamming the public API.
    """
    now = datetime.now(timezone.utc)
    chokepoint = CHOKEPOINTS.get(chokepoint_id.lower())
    if not chokepoint:
        return {"error": "Unknown chokepoint"}

    cache_key = chokepoint_id.lower()
    if cache_key in _WEATHER_CACHE:
        cached = _WEATHER_CACHE[cache_key]
        if now - cached["timestamp"] < _CACHE_TTL:
            return cached["data"]

    # Default fallback
    result = {
        "chokepoint": chokepoint["name"],
        "lat": chokepoint["lat"],
        "lng": chokepoint["lng"],
        "wave_height_m": 1.2,
        "wind_speed_kmh": 15.0,
        "weather_delay_days": 0.0,
        "status": "normal",
        "source": "baseline_fallback"
    }

    try:
        url = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": chokepoint["lat"],
            "longitude": chokepoint["lng"],
            "current": "wave_height,wind_speed",
            "timezone": "UTC"
        }
        resp = httpx.get(url, params=params, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current", {})
            wave_h = float(current.get("wave_height", 1.2))
            wind_s = float(current.get("wind_speed", 15.0))

            delay = 0.0
            status = "normal"
            if wave_h > 4.0 or wind_s > 50.0:
                delay = 1.5
                status = "severe"
            elif wave_h > 2.5 or wind_s > 35.0:
                delay = 0.5
                status = "warning"

            result.update({
                "wave_height_m": round(wave_h, 2),
                "wind_speed_kmh": round(wind_s, 1),
                "weather_delay_days": delay,
                "status": status,
                "source": "open_meteo"
            })
    except Exception as exc:
        logger.warning("Failed to fetch marine weather from Open-Meteo for %s: %s", chokepoint_id, exc)

    _WEATHER_CACHE[cache_key] = {"timestamp": now, "data": result}
    return result


def get_all_chokepoint_delays() -> dict[str, float]:
    """Return a mapping of chokepoint_id -> weather_delay_days."""
    delays = {}
    for cid in CHOKEPOINTS:
        data = get_chokepoint_weather(cid)
        delays[cid] = data.get("weather_delay_days", 0.0)
    return delays
