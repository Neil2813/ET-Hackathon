"""Infer coordinates for text-only signals (news headlines, etc.)."""
from __future__ import annotations

import os
import re
import httpx
import logging
import asyncio
import concurrent.futures
from typing import Any
from pydantic import BaseModel
from services.llm_provider import structured_complete

logger = logging.getLogger(__name__)

# Major supply-chain hubs — used when feeds omit lat/lng
_CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.7041, 77.1025),
    "chennai": (13.0827, 80.2707),
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "kolkata": (22.5726, 88.3639),
    "shanghai": (31.2304, 121.4737),
    "shenzhen": (22.5431, 114.0579),
    "guangzhou": (23.1291, 113.2644),
    "beijing": (39.9042, 116.4074),
    "singapore": (1.3521, 103.8198),
    "tokyo": (35.6762, 139.6503),
    "osaka": (34.6937, 135.5023),
    "taipei": (25.0330, 121.5654),
    "hong kong": (22.3193, 114.1694),
    "dubai": (25.2048, 55.2708),
    "rotterdam": (51.9244, 4.4777),
    "hamburg": (53.5511, 9.9937),
    "felixstowe": (51.9539, 1.3511),
    "los angeles": (34.0522, -118.2437),
    "new york": (40.7128, -74.0060),
    "houston": (29.7604, -95.3698),
    "chicago": (41.8781, -87.6298),
    "london": (51.5074, -0.1278),
    "paris": (48.8566, 2.3522),
    "frankfurt": (50.1109, 8.6821),
    "saigon": (10.8231, 106.6297),
    "ho chi minh": (10.8231, 106.6297),
    "hanoi": (21.0278, 105.8342),
    "bangkok": (13.7563, 100.5018),
    "jakarta": (6.2088, 106.8456),
    "manila": (14.5995, 120.9842),
    "sydney": (33.8688, 151.2093),
    "melbourne": (37.8136, 144.9631),
    "sao paulo": (-23.5505, -46.6333),
    "mexico city": (19.4326, -99.1332),
}

# Country aliases → (lat, lng, display name)
_COUNTRY_LOOKUP: dict[str, tuple[float, float, str]] = {
    "india": (20.5937, 78.9629, "India"),
    "in": (20.5937, 78.9629, "India"),
    "germany": (51.1657, 10.4515, "Germany"),
    "de": (51.1657, 10.4515, "Germany"),
    "japan": (36.2048, 138.2529, "Japan"),
    "jp": (36.2048, 138.2529, "Japan"),
    "usa": (37.0902, -95.7129, "United States"),
    "us": (37.0902, -95.7129, "United States"),
    "united states": (37.0902, -95.7129, "United States"),
    "china": (35.8617, 104.1954, "China"),
    "cn": (35.8617, 104.1954, "China"),
    "taiwan": (23.6978, 120.9605, "Taiwan"),
    "tw": (23.6978, 120.9605, "Taiwan"),
    "vietnam": (14.0583, 108.2772, "Vietnam"),
    "vn": (14.0583, 108.2772, "Vietnam"),
    "united kingdom": (55.3781, -3.4360, "United Kingdom"),
    "uk": (55.3781, -3.4360, "United Kingdom"),
    "gb": (55.3781, -3.4360, "United Kingdom"),
    "france": (46.2276, 2.2137, "France"),
    "fr": (46.2276, 2.2137, "France"),
    "italy": (41.8719, 12.5674, "Italy"),
    "it": (41.8719, 12.5674, "Italy"),
    "spain": (40.4637, -3.7492, "Spain"),
    "es": (40.4637, -3.7492, "Spain"),
    "netherlands": (52.1326, 5.2913, "Netherlands"),
    "nl": (52.1326, 5.2913, "Netherlands"),
    "brazil": (-14.2350, -51.9253, "Brazil"),
    "br": (-14.2350, -51.9253, "Brazil"),
    "mexico": (23.6345, -102.5528, "Mexico"),
    "mx": (23.6345, -102.5528, "Mexico"),
    "canada": (56.1304, -106.3468, "Canada"),
    "ca": (56.1304, -106.3468, "Canada"),
    "australia": (-25.2744, 133.7751, "Australia"),
    "au": (-25.2744, 133.7751, "Australia"),
    "south korea": (35.9078, 127.7669, "South Korea"),
    "korea": (35.9078, 127.7669, "South Korea"),
    "kr": (35.9078, 127.7669, "South Korea"),
    "indonesia": (-0.7893, 113.9213, "Indonesia"),
    "id": (-0.7893, 113.9213, "Indonesia"),
    "thailand": (15.8700, 100.9925, "Thailand"),
    "th": (15.8700, 100.9925, "Thailand"),
    "malaysia": (4.2105, 101.9758, "Malaysia"),
    "my": (4.2105, 101.9758, "Malaysia"),
    "philippines": (12.8797, 121.7740, "Philippines"),
    "ph": (12.8797, 121.7740, "Philippines"),
    "pakistan": (30.3753, 69.3451, "Pakistan"),
    "pk": (30.3753, 69.3451, "Pakistan"),
    "bangladesh": (23.6850, 90.3563, "Bangladesh"),
    "bd": (23.6850, 90.3563, "Bangladesh"),
    "sri lanka": (7.8731, 80.7718, "Sri Lanka"),
    "lk": (7.8731, 80.7718, "Sri Lanka"),
    "myanmar": (21.9162, 95.9560, "Myanmar"),
    "mm": (21.9162, 95.9560, "Myanmar"),
    "turkey": (38.9637, 35.2433, "Turkey"),
    "tr": (38.9637, 35.2433, "Turkey"),
    "saudi arabia": (23.8859, 45.0792, "Saudi Arabia"),
    "sa": (23.8859, 45.0792, "Saudi Arabia"),
    "united arab emirates": (23.4241, 53.8478, "United Arab Emirates"),
    "uae": (23.4241, 53.8478, "United Arab Emirates"),
    "egypt": (26.8206, 30.8025, "Egypt"),
    "eg": (26.8206, 30.8025, "Egypt"),
    "nigeria": (9.0820, 8.6753, "Nigeria"),
    "ng": (9.0820, 8.6753, "Nigeria"),
    "south africa": (-30.5595, 22.9375, "South Africa"),
    "za": (-30.5595, 22.9375, "South Africa"),
    "ukraine": (48.3794, 31.1656, "Ukraine"),
    "ua": (48.3794, 31.1656, "Ukraine"),
    "russia": (61.5240, 105.3188, "Russia"),
    "ru": (61.5240, 105.3188, "Russia"),
    "poland": (51.9194, 19.1451, "Poland"),
    "pl": (51.9194, 19.1451, "Poland"),
    "israel": (31.0461, 34.8516, "Israel"),
    "il": (31.0461, 34.8516, "Israel"),
    "iran": (32.4279, 53.6880, "Iran"),
    "ir": (32.4279, 53.6880, "Iran"),
}

_GLOBAL_SENTINELS = frozenset({"", "global", "unknown", "world", "worldwide", "n/a", "na", "none"})

# Legacy flat alias map used by incident_engine supplier fallback
COUNTRY_CENTROIDS: dict[str, tuple[float, float]] = {
    key: (coords[0], coords[1]) for key, coords in _COUNTRY_LOOKUP.items()
}


def _is_global_sentinel(value: str | None) -> bool:
    return str(value or "").strip().lower() in _GLOBAL_SENTINELS


def lookup_country(term: str) -> tuple[float, float, str] | None:
    """Resolve a country name or ISO-style alias to (lat, lng, display_name)."""
    key = str(term or "").strip().lower()
    if not key or _is_global_sentinel(key):
        return None
    return _COUNTRY_LOOKUP.get(key)


def match_country_in_text(text: str) -> tuple[float, float, str] | None:
    """Find the first country mention in free text."""
    lowered = str(text or "").lower()
    if not lowered.strip():
        return None

    for key in sorted(_COUNTRY_LOOKUP, key=len, reverse=True):
        if len(key) <= 3:
            if re.search(rf"\b{re.escape(key)}\b", lowered):
                return _COUNTRY_LOOKUP[key]
        elif key in lowered:
            return _COUNTRY_LOOKUP[key]
    return None


def _apply_geo(
    signal: dict[str, Any],
    lat: float,
    lng: float,
    *,
    precision: str,
    location: str | None = None,
) -> dict[str, Any]:
    out = dict(signal)
    out["lat"] = lat
    out["lng"] = lng
    out["location_precision"] = precision
    if location is not None:
        out["location"] = location
    return out


class LocationExtraction(BaseModel):
    country: str
    city: str | None
    search_query: str
    reasoning: str


async def extract_location_entities(headline: str) -> LocationExtraction:
    prompt = (
        f"Analyze the geopolitical incident headline: '{headline}'. "
        "Extract the primary affected country, city, or maritime chokepoint, and construct an optimized "
        "search query (e.g., 'Strait of Hormuz' or 'Port of Jamnagar') to resolve its exact coordinates. "
        "Return the details in the specified JSON format."
    )
    return await structured_complete(prompt=prompt, output_model=LocationExtraction)


async def lookup_coordinates_via_serpapi(search_query: str) -> tuple[float, float] | None:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        return None

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "q": search_query,
        "api_key": api_key
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, params=params)
        if response.status_code != 200:
            return None
        data = response.json()

    # 1. Try maps place results
    place_results = data.get("place_results", {})
    if place_results and "gps_coordinates" in place_results:
        gps = place_results["gps_coordinates"]
        return float(gps.get("latitude", 0.0)), float(gps.get("longitude", 0.0))

    # 2. Fallback to local map search results
    local_results = data.get("local_results", [])
    if local_results and isinstance(local_results, list):
        gps = local_results[0].get("gps_coordinates", {})
        if gps:
            return float(gps.get("latitude", 0.0)), float(gps.get("longitude", 0.0))

    return None


async def geocode_text_via_llm_and_serpapi(headline: str) -> tuple[float, float, str] | None:
    try:
        extraction = await extract_location_entities(headline)
        query = extraction.search_query.strip()
        if not query:
            return None
        coords = await lookup_coordinates_via_serpapi(query)
        if coords:
            lat, lng = coords
            location_label = extraction.city if extraction.city else extraction.country
            if not location_label:
                location_label = query
            return lat, lng, location_label
    except Exception as e:
        logger.warning("Gemini/SerpAPI geocoding failed: %s", e)
    return None


def _run_async_sync(coro):
    """Run an async coroutine synchronously, handling existing event loops safely."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(lambda: asyncio.run(coro))
        return future.result()


def geocode_signal(signal: dict[str, Any]) -> dict[str, Any]:
    lat = float(signal.get("lat") or signal.get("event_lat") or signal.get("latitude") or 0)
    lng = float(signal.get("lng") or signal.get("event_lng") or signal.get("longitude") or 0)
    if lat != 0.0 or lng != 0.0:
        out = dict(signal)
        out["lat"] = lat
        out["lng"] = lng
        out["event_lat"] = lat
        out["event_lng"] = lng
        return out

    # Try SerpAPI geocoding if API key is present
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if api_key:
        headline = str(signal.get("title") or signal.get("description") or "")
        if headline:
            try:
                res = _run_async_sync(geocode_text_via_llm_and_serpapi(headline))
                if res:
                    flat_lat, flat_lng, location_name = res
                    return _apply_geo(signal, flat_lat, flat_lng, precision="llm_serpapi", location=location_name)
            except Exception as exc:
                logger.warning("Failed to execute SerpAPI geocoding synchronously: %s", exc)

    # Rule-based fallback
    text = " ".join(
        str(signal.get(key) or "")
        for key in ("title", "location", "description", "summary", "event_type")
    ).lower()

    for city in sorted(_CITY_CENTROIDS, key=len, reverse=True):
        if city in text:
            clat, clng = _CITY_CENTROIDS[city]
            location = city.title()
            if not _is_global_sentinel(str(signal.get("location") or "")):
                location = str(signal.get("location") or location)
            return _apply_geo(signal, clat, clng, precision="city", location=location)

    for field in ("location", "region", "country"):
        resolved = lookup_country(str(signal.get(field) or ""))
        if resolved:
            clat, clng, display = resolved
            return _apply_geo(signal, clat, clng, precision="country", location=display)

    resolved = match_country_in_text(text)
    if resolved:
        clat, clng, display = resolved
        location = display if _is_global_sentinel(str(signal.get("location") or "")) else str(signal.get("location") or display)
        return _apply_geo(signal, clat, clng, precision="country", location=location)

    return signal
