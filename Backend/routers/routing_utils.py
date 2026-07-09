from __future__ import annotations

import asyncio
import csv
import io
import logging
import math
import httpx
from fastapi import APIRouter, HTTPException, Query

from currency.frankfurter import get_exchange_rate
from currency.worldbank import get_inflation_rate

from routers.schemas import (
    SeaRouteRequest,
    LandRouteRequest,
    AirRouteRequest,
    RouteCostRequest,
)

logger = logging.getLogger("routers.routing_utils")
router = APIRouter(tags=["Routing Utilities"])

_AIR_HUB_CACHE: list[dict] | None = None
_AIR_HUB_FETCH_LOCK: asyncio.Lock | None = None

_CARGO_HUBS_BUILTIN: list[dict] = [
    {"iata": "HKG", "name": "Hong Kong Intl",         "city": "Hong Kong",    "country": "HK", "lat": 22.308, "lng": 113.915},
    {"iata": "PVG", "name": "Shanghai Pudong",         "city": "Shanghai",     "country": "CN", "lat": 31.143, "lng": 121.805},
    {"iata": "ICN", "name": "Seoul Incheon",           "city": "Seoul",        "country": "KR", "lat": 37.460, "lng": 126.440},
    {"iata": "ANC", "name": "Ted Stevens Anchorage",   "city": "Anchorage",    "country": "US", "lat": 61.174, "lng": -149.996},
    {"iata": "MEM", "name": "Memphis Intl (FedEx HQ)", "city": "Memphis",      "country": "US", "lat": 35.042, "lng": -89.977},
    {"iata": "SDF", "name": "Louisville Muhammad Ali (UPS)", "city": "Louisville", "country": "US", "lat": 38.174, "lng": -85.736},
    {"iata": "FRA", "name": "Frankfurt",               "city": "Frankfurt",    "country": "DE", "lat": 50.033, "lng": 8.570},
    {"iata": "DXB", "name": "Dubai Intl",              "city": "Dubai",        "country": "AE", "lat": 25.252, "lng": 55.364},
    {"iata": "DOH", "name": "Hamad Intl",              "city": "Doha",         "country": "QA", "lat": 25.261, "lng": 51.614},
    {"iata": "SIN", "name": "Singapore Changi",        "city": "Singapore",    "country": "SG", "lat": 1.360,  "lng": 103.989},
    {"iata": "NRT", "name": "Tokyo Narita",             "city": "Tokyo",        "country": "JP", "lat": 35.765, "lng": 140.386},
    {"iata": "LHR", "name": "London Heathrow",          "city": "London",       "country": "GB", "lat": 51.477, "lng": -0.461},
    {"iata": "AMS", "name": "Amsterdam Schiphol",      "city": "Amsterdam",    "country": "NL", "lat": 52.308, "lng": 4.764},
    {"iata": "CDG", "name": "Paris Charles de Gaulle", "city": "Paris",        "country": "FR", "lat": 49.012, "lng": 2.551},
    {"iata": "LGG", "name": "Liège (TNT/DHL)",         "city": "Liège",        "country": "BE", "lat": 50.637, "lng": 5.443},
    {"iata": "JFK", "name": "New York JFK",             "city": "New York",     "country": "US", "lat": 40.639, "lng": -73.779},
    {"iata": "LAX", "name": "Los Angeles Intl",        "city": "Los Angeles",  "country": "US", "lat": 33.942, "lng": -118.408},
    {"iata": "MIA", "name": "Miami Intl",               "city": "Miami",        "country": "US", "lat": 25.795, "lng": -80.287},
    {"iata": "ORD", "name": "Chicago O'Hare",           "city": "Chicago",      "country": "US", "lat": 41.978, "lng": -87.904},
    {"iata": "BOM", "name": "Mumbai Chhatrapati Shivaji", "city": "Mumbai",    "country": "IN", "lat": 19.089, "lng": 72.868},
    {"iata": "DEL", "name": "Delhi Indira Gandhi",      "city": "Delhi",        "country": "IN", "lat": 28.556, "lng": 77.100},
    {"iata": "BLR", "name": "Bengaluru Intl",           "city": "Bengaluru",    "country": "IN", "lat": 13.199, "lng": 77.706},
    {"iata": "IST", "name": "Istanbul",                 "city": "Istanbul",     "country": "TR", "lat": 41.275, "lng": 28.752},
    {"iata": "CAI", "name": "Cairo Intl",               "city": "Cairo",        "country": "EG", "lat": 30.121, "lng": 31.405},
    {"iata": "JNB", "name": "Johannesburg O.R. Tambo",  "city": "Johannesburg", "country": "ZA", "lat": -26.139, "lng": 28.246},
    {"iata": "NBO", "name": "Nairobi Jomo Kenyatta",    "city": "Nairobi",      "country": "KE", "lat": -1.319, "lng": 36.928},
    {"iata": "GRU", "name": "São Paulo Guarulhos",      "city": "São Paulo",    "country": "BR", "lat": -23.432, "lng": -46.469},
    {"iata": "EZE", "name": "Buenos Aires Ezeiza",      "city": "Buenos Aires", "country": "AR", "lat": -34.822, "lng": -58.536},
    {"iata": "SYD", "name": "Sydney Kingsford Smith",   "city": "Sydney",       "country": "AU", "lat": -33.947, "lng": 151.179},
    {"iata": "MEL", "name": "Melbourne Tullamarine",    "city": "Melbourne",    "country": "AU", "lat": -37.673, "lng": 144.843},
    {"iata": "KUL", "name": "Kuala Lumpur KLIA",        "city": "Kuala Lumpur", "country": "MY", "lat": 2.745,   "lng": 101.709},
    {"iata": "CGK", "name": "Jakarta Soekarno-Hatta",   "city": "Jakarta",      "country": "ID", "lat": -6.126,  "lng": 106.656},
    {"iata": "PEK", "name": "Beijing Capital",          "city": "Beijing",      "country": "CN", "lat": 40.080, "lng": 116.584},
    {"iata": "CAN", "name": "Guangzhou Baiyun",         "city": "Guangzhou",    "country": "CN", "lat": 23.392, "lng": 113.299},
    {"iata": "CTU", "name": "Chengdu Tianfu",            "city": "Chengdu",      "country": "CN", "lat": 30.313, "lng": 103.947},
    {"iata": "BKK", "name": "Bangkok Suvarnabhumi",     "city": "Bangkok",      "country": "TH", "lat": 13.681, "lng": 100.747},
    {"iata": "KHI", "name": "Karachi Jinnah",           "city": "Karachi",      "country": "PK", "lat": 24.906, "lng": 67.161},
    {"iata": "MEX", "name": "Mexico City Benito Juárez", "city": "Mexico City", "country": "MX", "lat": 19.436, "lng": -99.072},
    {"iata": "MXP", "name": "Milan Malpensa",            "city": "Milan",        "country": "IT", "lat": 45.630, "lng": 8.724},
    {"iata": "MSP", "name": "Minneapolis-St. Paul",     "city": "Minneapolis",  "country": "US", "lat": 44.882, "lng": -93.222},
    {"iata": "OSA", "name": "Osaka Kansai",              "city": "Osaka",        "country": "JP", "lat": 34.427, "lng": 135.244},
    {"iata": "TPE", "name": "Taipei Taoyuan",            "city": "Taipei",       "country": "TW", "lat": 25.077, "lng": 121.232},
    {"iata": "GVA", "name": "Geneva",                   "city": "Geneva",       "country": "CH", "lat": 46.238, "lng": 6.109},
    {"iata": "VCP", "name": "Campinas Viracopos",       "city": "Campinas",     "country": "BR", "lat": -23.007, "lng": -47.135},
    {"iata": "LIM", "name": "Lima Jorge Chávez",         "city": "Lima",         "country": "PE", "lat": -12.022, "lng": -77.114},
    {"iata": "BOG", "name": "Bogotá El Dorado",          "city": "Bogotá",       "CO": "CO", "lat": 4.702,  "lng": -74.147},
    {"iata": "CMN", "name": "Casablanca Mohammed V",    "city": "Casablanca",   "country": "MA", "lat": 33.367, "lng": -7.590},
    {"iata": "ACC", "name": "Accra Kotoka",              "city": "Accra",        "country": "GH", "lat": 5.605,  "lng": -0.167},
    {"iata": "AUH", "name": "Abu Dhabi Intl",           "city": "Abu Dhabi",    "country": "AE", "lat": 24.433, "lng": 54.651},
    {"iata": "RUH", "name": "Riyadh King Khalid",        "city": "Riyadh",       "country": "SA", "lat": 24.958, "lng": 46.699},
    {"iata": "MNL", "name": "Manila Ninoy Aquino",       "city": "Manila",       "country": "PH", "lat": 14.509, "lng": 121.019},
]


async def _get_cargo_hubs() -> list[dict]:
    global _AIR_HUB_CACHE, _AIR_HUB_FETCH_LOCK

    if _AIR_HUB_CACHE is not None:
        return _AIR_HUB_CACHE

    if _AIR_HUB_FETCH_LOCK is None:
        _AIR_HUB_FETCH_LOCK = asyncio.Lock()

    async with _AIR_HUB_FETCH_LOCK:
        if _AIR_HUB_CACHE is not None:
            return _AIR_HUB_CACHE
        try:
            url = "https://davidmegginson.github.io/ourairports-data/airports.csv"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            reader = csv.DictReader(io.StringIO(resp.text))
            hubs: list[dict] = []
            for row in reader:
                iata = str(row.get("iata_code") or "").strip().upper()
                atype = str(row.get("type") or "").strip()
                if not iata or len(iata) != 3:
                    continue
                if atype not in ("large_airport", "medium_airport"):
                    continue
                try:
                    lat = float(row["latitude_deg"])
                    lng = float(row["longitude_deg"])
                except (KeyError, ValueError):
                    continue
                is_cargo_hub = iata in {h["iata"] for h in _CARGO_HUBS_BUILTIN}
                if atype == "large_airport" or is_cargo_hub:
                    hubs.append({
                        "iata": iata,
                        "name": str(row.get("name") or iata),
                        "city": str(row.get("municipality") or ""),
                        "country": str(row.get("iso_country") or ""),
                        "lat": lat,
                        "lng": lng,
                        "is_cargo_hub": is_cargo_hub,
                    })
            if len(hubs) > 50:
                logger.info("OurAirports: loaded %d airports for air routing", len(hubs))
                _AIR_HUB_CACHE = hubs
                return hubs
        except Exception as exc:
            logger.warning("OurAirports CSV fetch failed: %s — using builtin list", exc)

    _AIR_HUB_CACHE = _CARGO_HUBS_BUILTIN
    return _AIR_HUB_CACHE


def _decode_polyline6(encoded: str) -> list[list[float]]:
    """Decode Valhalla's precision-6 encoded polyline → [[lon, lat], ...]"""
    result: list[list[float]] = []
    index = lat = lng = 0
    while index < len(encoded):
        shift = result_val = 0
        while True:
            b = ord(encoded[index]) - 63; index += 1
            result_val |= (b & 0x1F) << shift; shift += 5
            if b < 0x20: break
        lat += (~result_val if result_val & 1 else result_val >> 1)
        shift = result_val = 0
        while True:
            b = ord(encoded[index]) - 63; index += 1
            result_val |= (b & 0x1F) << shift; shift += 5
            if b < 0x20: break
        lng += (~result_val if result_val & 1 else result_val >> 1)
        result.append([round(lng / 1e6, 6), round(lat / 1e6, 6)])
    return result


@router.post("/api/sea-route")
async def api_sea_route(payload: SeaRouteRequest) -> dict:
    from_lat, from_lng = payload.from_lat, payload.from_lng
    to_lat, to_lng = payload.to_lat, payload.to_lng

    try:
        import importlib.util as _ilu
        if _ilu.find_spec("searoute") is None:
            raise ImportError("searoute not on path")
        import searoute as sr  # type: ignore[import-untyped]
        origin = [from_lng, from_lat]
        destination = [to_lng, to_lat]
        route = sr.searoute(origin, destination, units="km")
        coords = route["geometry"]["coordinates"]
        distance_km = float(route.get("properties", {}).get("length", 0))
        return {
            "coordinates": coords,
            "distance_km": round(distance_km, 1),
            "source": "searoute",
        }
    except Exception:
        pass

    WAYPOINTS = {
        "gibraltar":   (-5.35, 35.99),
        "suez_n":      (32.57, 30.42),
        "suez_s":      (32.55, 29.92),
        "bab_el_mand": (43.40, 12.60),
        "cape_good":   (18.42, -34.36),
        "cape_horn":   (-67.28, -55.98),
        "panama_n":    (-79.92, 9.38),
        "panama_s":    (-79.55, 8.88),
        "malacca_w":   (98.76, 5.55),
        "malacca_e":   (103.83, 1.26),
        "hormuz":      (56.46, 26.57),
        "lombok":      (115.73, -8.72),
        "luzon":       (121.27, 18.82),
        "taiwan_str":  (120.40, 24.10),
        "mid_atlantic": (-30.0, 10.0),
        "mid_indian":  (70.0, -10.0),
        "mid_pacific":  (180.0, 5.0),
        "s_atlantic":  (-15.0, -30.0),
    }

    def _hav_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371
        r = math.pi / 180
        dLat = (lat2 - lat1) * r
        dLon = (lon2 - lon1) * r
        a = math.sin(dLat/2)**2 + math.cos(lat1*r) * math.cos(lat2*r) * math.sin(dLon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def _interpolate_sea(lat1: float, lon1: float, lat2: float, lon2: float, steps: int = 20) -> list:
        return [
            [lon1 + (lon2 - lon1) * i / steps, lat1 + (lat2 - lat1) * i / steps]
            for i in range(steps + 1)
        ]

    def _choose_waypoints(flat: float, flng: float, tlat: float, tlng: float) -> list:
        wps = []
        is_europe_west = flng < 30 and flat > 30
        is_europe_west_dest = tlng < 30 and tlat > 30
        is_asia_indian = flng > 60 or (flng > 30 and flat < 30)
        is_asia_indian_dest = tlng > 60 or (tlng > 30 and tlat < 30)
        is_americas = flng < -30
        is_americas_dest = tlng < -30
        is_pacific = flng > 150 or flng < -100
        is_pacific_dest = tlng > 150 or tlng < -100
        is_southern = flat < -20
        is_southern_dest = tlat < -20

        if (is_europe_west and is_asia_indian_dest) or (is_asia_indian and is_europe_west_dest):
            wps += ["gibraltar", "suez_n", "suez_s", "bab_el_mand"]
        if (is_europe_west and is_americas_dest) or (is_americas and is_europe_west_dest):
            wps += ["gibraltar", "mid_atlantic"]
        if (is_pacific and is_americas_dest) or (is_americas and is_pacific_dest):
            wps += ["luzon", "mid_pacific", "panama_n", "panama_s"]
        if (flng > 45 and flng < 100 and flat < 25) and (tlng > 100):
            wps += ["hormuz", "malacca_w", "malacca_e"]
        elif (flng > 100) and (tlng > 45 and tlng < 100 and tlat < 25):
            wps += ["malacca_e", "malacca_w", "hormuz"]
        if (is_southern or is_southern_dest) and not (
            (is_europe_west or is_europe_west_dest) and (is_asia_indian or is_asia_indian_dest)
        ):
            if (is_americas or is_americas_dest) and (30 < flng < 55 or 30 < tlng < 55):
                wps += ["cape_good", "s_atlantic"]
            elif is_pacific or is_pacific_dest:
                wps += ["cape_horn"]
        if (flng > 120 and flat > 20) and (tlng > 120 and tlat > 20):
            wps += ["taiwan_str"]
        return wps

    wp_names = _choose_waypoints(from_lat, from_lng, to_lat, to_lng)
    all_points = [(from_lat, from_lng)] + [
        (WAYPOINTS[w][1], WAYPOINTS[w][0]) for w in wp_names if w in WAYPOINTS
    ] + [(to_lat, to_lng)]

    coords: list = []
    total_km = 0.0
    for i in range(len(all_points) - 1):
        la1, lo1 = all_points[i]
        la2, lo2 = all_points[i + 1]
        seg = _interpolate_sea(la1, lo1, la2, lo2, steps=12)
        if i > 0:
            seg = seg[1:]
        coords.extend(seg)
        total_km += _hav_km(la1, lo1, la2, lo2)

    return {
        "coordinates": coords,
        "distance_km": round(total_km, 1),
        "waypoints": wp_names,
        "source": "waypoint_fallback",
    }


@router.post("/api/land-route")
async def api_land_route(payload: LandRouteRequest) -> dict:
    def _hav_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371; r = math.pi / 180
        dLat = (lat2 - lat1) * r; dLon = (lon2 - lon1) * r
        a = math.sin(dLat/2)**2 + math.cos(lat1*r) * math.cos(lat2*r) * math.sin(dLon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    straight_km = _hav_km(payload.from_lat, payload.from_lng, payload.to_lat, payload.to_lng)

    if straight_km > 6000:
        return {
            "viable": False,
            "reason": f"Straight-line distance {int(straight_km):,} km exceeds road viability (6,000 km). Use Sea or Air.",
            "distance_km": round(straight_km, 1),
            "coordinates": [],
        }

    try:
        valhalla_url = "https://valhalla1.openstreetmap.de/route"
        valhalla_body = {
            "locations": [
                {"lon": payload.from_lng, "lat": payload.from_lat, "type": "break"},
                {"lon": payload.to_lng,   "lat": payload.to_lat,   "type": "break"},
            ],
            "costing": "truck",
            "costing_options": {
                "truck": {
                    "weight":    21.77,
                    "axle_load": 9.07,
                    "height":    4.11,
                    "width":     2.60,
                    "length":   21.64,
                }
            },
            "units": "km",
            "directions_options": {"units": "km"},
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(valhalla_url, json=valhalla_body)
            data = resp.json()

        trip = data.get("trip") or {}
        legs = trip.get("legs") or []
        if not legs:
            raise ValueError("Valhalla: no legs in response")

        shape    = legs[0].get("shape", "")
        summary  = trip.get("summary") or {}
        dist_km  = float(summary.get("length") or 0)
        dur_s    = float(summary.get("time") or 0)
        coords   = _decode_polyline6(shape)

        if not coords or dist_km <= 0:
            raise ValueError("Valhalla: empty shape or zero distance")

        return {
            "viable": True,
            "coordinates": coords,
            "distance_km": round(dist_km, 1),
            "duration_hours": round(dur_s / 3600, 1),
            "source": "valhalla_truck",
            "source_label": "Valhalla truck routing (OSM)",
        }
    except Exception as exc:
        logger.warning("Valhalla truck routing failed: %s — trying OSRM", exc)

    try:
        osrm_url = (
            f"https://router.project-osrm.org/route/v1/driving/"
            f"{payload.from_lng},{payload.from_lat};{payload.to_lng},{payload.to_lat}"
            f"?overview=full&geometries=geojson"
        )
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(osrm_url)
            data = resp.json()

        route = (data.get("routes") or [{}])[0]
        geom  = (route.get("geometry") or {}).get("coordinates") or []
        dist_m = float(route.get("distance") or 0)
        dur_s  = float(route.get("duration") or 0)

        if not geom or dist_m <= 0:
            raise ValueError("OSRM: empty geometry")

        return {
            "viable": True,
            "coordinates": geom,
            "distance_km": round(dist_m / 1000, 1),
            "duration_hours": round(dur_s / 3600, 1),
            "source": "osrm",
            "source_label": "OSRM routing (OpenStreetMap)",
        }
    except Exception as exc:
        logger.warning("OSRM routing failed: %s — using straight-line estimate", exc)

    steps = 60
    coords = [
        [
            payload.from_lng + (payload.to_lng - payload.from_lng) * i / steps,
            payload.from_lat + (payload.to_lat - payload.from_lat) * i / steps,
        ]
        for i in range(steps + 1)
    ]
    road_km = round(straight_km * 1.35, 1)
    return {
        "viable": True,
        "coordinates": coords,
        "distance_km": road_km,
        "duration_hours": round(road_km / 80, 1),
        "source": "estimate",
        "source_label": "Straight-line estimate (routing APIs unavailable)",
    }


@router.post("/api/air-route")
async def api_air_route(payload: AirRouteRequest) -> dict:
    HUBS = await _get_cargo_hubs()

    def _hav_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371; r = math.pi / 180
        dLat = (lat2 - lat1) * r; dLon = (lon2 - lon1) * r
        a = math.sin(dLat/2)**2 + math.cos(lat1*r) * math.cos(lat2*r) * math.sin(dLon/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _nearest_hub(lat: float, lng: float) -> dict:
        return min(HUBS, key=lambda h: _hav_km(lat, lng, h["lat"], h["lng"]))

    def _top_hubs(lat: float, lng: float, n: int = 5) -> list[dict]:
        return sorted(HUBS, key=lambda h: _hav_km(lat, lng, h["lat"], h["lng"]))[:n]

    def _arc(lat1: float, lon1: float, lat2: float, lon2: float, steps: int = 80) -> list:
        r, d = math.pi / 180, 180 / math.pi
        lo1, la1, lo2, la2 = lon1*r, lat1*r, lon2*r, lat2*r
        cosO = max(-1.0, min(1.0, math.sin(la1)*math.sin(la2) + math.cos(la1)*math.cos(la2)*math.cos(lo1-lo2)))
        Om = math.acos(cosO)
        if Om == 0 or abs(Om - math.pi) < 1e-6:
            return [[lon1, lat1], [lon2, lat2]]
        sinO = math.sin(Om)
        coords, prevLon, lonOffset = [], None, 0
        for i in range(steps + 1):
            f = i / steps
            A = math.sin((1-f)*Om) / sinO
            B = math.sin(f*Om) / sinO
            x = A*math.cos(la1)*math.cos(lo1)+B*math.cos(la2)*math.cos(lo2)
            y = A*math.cos(la1)*math.sin(lo1)+B*math.cos(la2)*math.sin(lo2)
            z = A*math.sin(la1)+B*math.sin(la2)
            lat_pt = math.atan2(z, math.sqrt(x*x+y*y))*d
            lon_pt = math.atan2(y, x)*d
            if prevLon is not None:
                diff = lon_pt - prevLon
                if diff > 180: lonOffset -= 360
                elif diff < -180: lonOffset += 360
            prevLon = lon_pt
            coords.append([lon_pt + lonOffset, lat_pt])
        return coords

    origin_hub = _nearest_hub(payload.from_lat, payload.from_lng)
    dest_hub   = _nearest_hub(payload.to_lat,   payload.to_lng)

    direct_km = _hav_km(payload.from_lat, payload.from_lng, payload.to_lat, payload.to_lng)
    hub_km    = _hav_km(origin_hub["lat"], origin_hub["lng"], dest_hub["lat"], dest_hub["lng"])

    arc_coords = _arc(payload.from_lat, payload.from_lng, payload.to_lat, payload.to_lng)
    hub_arc_coords = (
        _arc(origin_hub["lat"], origin_hub["lng"], dest_hub["lat"], dest_hub["lng"])
        if origin_hub["iata"] != dest_hub["iata"] else arc_coords
    )

    alt_hub = None
    mid_lat = (payload.from_lat + payload.to_lat) / 2
    mid_lng = (payload.from_lng + payload.to_lng) / 2
    for h in _top_hubs(mid_lat, mid_lng, 8):
        if h["iata"] not in (origin_hub["iata"], dest_hub["iata"]):
            alt_hub = h
            break

    alt_coords = None
    alt_km = 0.0
    if alt_hub:
        leg1 = _arc(payload.from_lat, payload.from_lng, alt_hub["lat"], alt_hub["lng"])
        leg2 = _arc(alt_hub["lat"], alt_hub["lng"], payload.to_lat, payload.to_lng)
        alt_coords = leg1 + leg2[1:]
        alt_km = (
            _hav_km(payload.from_lat, payload.from_lng, alt_hub["lat"], alt_hub["lng"]) +
            _hav_km(alt_hub["lat"], alt_hub["lng"], payload.to_lat, payload.to_lng)
        )

    airport_source = "ourairports_csv" if len(HUBS) > 60 else "builtin_cargo_hubs"

    return {
        "direct": {
            "coordinates": arc_coords,
            "distance_km": round(direct_km, 1),
        },
        "via_hubs": {
            "coordinates": hub_arc_coords,
            "distance_km": round(hub_km, 1),
            "origin_hub": origin_hub,
            "dest_hub": dest_hub,
        },
        "via_alt_hub": {
            "coordinates": alt_coords,
            "distance_km": round(alt_km, 1),
            "hub": alt_hub,
        } if alt_hub and alt_coords else None,
        "source": "great_circle",
        "airport_source": airport_source,
        "airport_count": len(HUBS),
        "source_label": f"Great-circle orthodrome · {airport_source} ({len(HUBS)} airports)",
    }


@router.post("/api/route-cost")
async def api_route_cost(payload: RouteCostRequest) -> dict:
    km = max(1.0, float(payload.distance_km))
    kg = max(100.0, float(payload.weight_kg))
    mode = (payload.mode or "air").strip().lower()

    if mode == "air":
        if km < 500:
            rate_per_kg = 5.80
        elif km < 3000:
            rate_per_kg = 4.20
        elif km < 8000:
            rate_per_kg = 3.50
        else:
            rate_per_kg = 2.90
        fuel_surcharge = 0.50 + (km * 0.0001)
        security_fee   = 0.25
        handling       = 600
        total = kg * (rate_per_kg + fuel_surcharge + security_fee) + handling
        breakdown = {
            "freight": round(kg * rate_per_kg, 2),
            "fuel_surcharge": round(kg * fuel_surcharge, 2),
            "security": round(kg * security_fee, 2),
            "handling": handling,
        }

    elif mode == "sea":
        teu = max(1.0, kg / 24000.0)
        if km < 2000:
            rate_per_teu_km = 0.28
        elif km < 8000:
            rate_per_teu_km = 0.20
        else:
            rate_per_teu_km = 0.14
        port_fees = 800 * teu
        fuel      = 0.06 * km * teu
        total = teu * km * rate_per_teu_km + port_fees + fuel
        breakdown = {
            "ocean_freight": round(teu * km * rate_per_teu_km, 0),
            "port_fees": round(port_fees, 0),
            "bunker_surcharge": round(fuel, 0),
        }

    elif mode == "land":
        trucks = max(1.0, kg / 20000.0)
        if km < 500:
            rate_per_km = 2.50
        elif km < 2000:
            rate_per_km = 2.20
        else:
            rate_per_km = 1.90
        tolls    = 0.10 * km * trucks
        handling = 300 * trucks
        total = trucks * km * rate_per_km + tolls + handling
        breakdown = {
            "trucking": round(trucks * km * rate_per_km, 0),
            "tolls_border": round(tolls, 0),
            "handling": round(handling, 0),
        }

    elif mode == "rail":
        wagons = max(1.0, kg / 60000.0)
        rate_per_km = 1.10
        terminal = 400 * wagons
        total = wagons * km * rate_per_km + terminal
        breakdown = {
            "rail_freight": round(wagons * km * rate_per_km, 0),
            "terminal_fees": round(terminal, 0),
        }

    elif mode == "hybrid":
        sea_km  = km * 0.70
        land_km = km * 0.30
        teu     = max(1.0, kg / 24000.0)
        trucks  = max(1.0, kg / 20000.0)
        sea_cost  = teu * sea_km * 0.18 + 800 * teu
        land_cost = trucks * land_km * 2.10 + 300 * trucks
        total = sea_cost + land_cost
        breakdown = {
            "sea_leg": round(sea_cost, 0),
            "land_leg": round(land_cost, 0),
        }

    else:
        total = km * 2.0
        breakdown = {"estimate": round(total, 0)}

    speed = {"air": 900, "sea": 35 * 1.852, "land": 35, "rail": 40, "hybrid": 35}
    kmh = speed.get(mode, 80)
    transit_days = (km / kmh) / 24.0
    overhead = {"air": 0.5, "sea": 2.0, "land": 1.0, "rail": 1.5, "hybrid": 2.5}
    transit_days += overhead.get(mode, 0.5)

    return {
        "mode": mode,
        "distance_km": round(km, 1),
        "weight_kg": round(kg, 0),
        "total_usd": round(total, 0),
        "transit_days": round(transit_days, 1),
        "breakdown": breakdown,
        "co2_kg": round(km * kg / 1000 * {
            "air": 0.602, "sea": 0.012, "land": 0.096, "rail": 0.028, "hybrid": 0.045
        }.get(mode, 0.1), 0),
    }


@router.get("/currency/rates")
async def currency_rates(from_currency: str = Query(default="USD", min_length=3, max_length=3), to_currency: str = Query(default="INR", min_length=3, max_length=3)) -> dict:
    rate = await get_exchange_rate(from_currency.upper(), to_currency.upper())
    return {"from": from_currency.upper(), "to": to_currency.upper(), "rate": rate}


@router.get("/currency/inflation/{code}")
async def currency_inflation(code: str) -> dict:
    return {"country_code": code.upper(), "inflation_rate": await get_inflation_rate(code)}
