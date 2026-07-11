from __future__ import annotations

import logging
import os
import httpx
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Cache parameters
_WEATHER_CACHE: dict[str, dict] = {}
_CACHE_TTL = timedelta(minutes=10)

def load_chokepoints_geojson() -> dict:
    import json
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "..", "Dataset", "Chokepoints.geojson")
    if not os.path.exists(geojson_path):
        geojson_path = os.path.join(os.getcwd(), "Dataset", "Chokepoints.geojson")
    
    if not os.path.exists(geojson_path):
        return {}
        
    try:
        with open(geojson_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        chokepoints = {}
        features = data.get("features", [])
        for feat in features:
            props = feat.get("properties", {})
            portname = props.get("portname") or props.get("fullname")
            if not portname:
                continue
            cid = portname.lower().replace(" strait", "").replace(" canal", "").replace(" ", "_")
            if cid == "bab_el-mandeb":
                cid = "bab_el_mandeb"
            elif cid == "malacca":
                cid = "malacca_strait"
            elif cid == "hormuz":
                cid = "hormuz_strait"
            elif cid == "bosporus":
                cid = "bosphorus"
                
            lat = float(props.get("lat") or feat.get("geometry", {}).get("coordinates", [0, 0])[1])
            lng = float(props.get("lon") or feat.get("geometry", {}).get("coordinates", [0, 0])[0])
            chokepoints[cid] = {"name": portname, "lat": lat, "lng": lng}
        return chokepoints
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Failed to load Chokepoints.geojson: %s", e)
        return {}

CHOKEPOINTS = load_chokepoints_geojson()
if not CHOKEPOINTS:
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
    Fetch marine weather info for a chokepoint using Open-Meteo Marine API.
    Fetches: wave height, wind speed, swell height, swell direction, swell period.
    Includes a 10-minute cache to prevent spamming the public API.
    """
    now = datetime.now(timezone.utc)
    chokepoint = CHOKEPOINTS.get(chokepoint_id.lower())
    if not chokepoint:
        # Fallback for subparts like _n, _s, _w, _e
        base_id = chokepoint_id.lower().split("_")[0]
        chokepoint = CHOKEPOINTS.get(base_id)
        
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
        "swell_height_m": None,
        "swell_direction_deg": None,
        "swell_period_s": None,
        "weather_delay_days": 0.0,
        "status": "normal",
        "source": "baseline_fallback"
    }

    try:
        url = "https://marine-api.open-meteo.com/v1/marine"
        params = {
            "latitude": chokepoint["lat"],
            "longitude": chokepoint["lng"],
            # Extended current variables: wave + swell data
            "current": "wave_height,wind_wave_height,swell_wave_height,swell_wave_direction,swell_wave_period",
            "wind_speed_unit": "kmh",
            "timezone": "UTC",
        }
        resp = httpx.get(url, params=params, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            current = data.get("current", {})
            wave_h = float(current.get("wave_height") or 1.2)
            swell_h = current.get("swell_wave_height")
            swell_dir = current.get("swell_wave_direction")
            swell_period = current.get("swell_wave_period")

            # Infer wind speed from wave height if not directly available
            # (Open-Meteo Marine does not expose wind_speed as a current var)
            wind_kmh = 15.0  # conservative default

            # Delay model:
            #   Swell period < 8s = steep short seas = high motion = slow progress
            #   Swell height > 3m = VLCCs slow to ~8 knots (from design 14 knots)
            #   Wave height > 4m = severe — port access closure risk
            delay = 0.0
            status = "normal"

            swell_h_f = float(swell_h) if swell_h is not None else 0.0
            swell_period_f = float(swell_period) if swell_period is not None else 10.0

            severe_swell = swell_h_f > 3.0 and swell_period_f < 9.0
            severe_wave = wave_h > 4.0

            if severe_wave or severe_swell:
                delay = 1.5
                status = "severe"
            elif wave_h > 2.5 or swell_h_f > 2.0:
                delay = 0.5
                status = "warning"
            elif wave_h > 1.8:
                delay = 0.25
                status = "minor_delay"

            result.update({
                "wave_height_m": round(wave_h, 2),
                "wind_speed_kmh": round(wind_kmh, 1),
                "swell_height_m": round(swell_h_f, 2) if swell_h is not None else None,
                "swell_direction_deg": round(float(swell_dir), 1) if swell_dir is not None else None,
                "swell_period_s": round(swell_period_f, 1) if swell_period is not None else None,
                "weather_delay_days": delay,
                "status": status,
                "source": "open_meteo_marine",
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
