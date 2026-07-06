from __future__ import annotations

from services.data_registry import registry
from .utils import haversine_km

AVG_VESSEL_SPEED_KMH = 26.0
TANKER_PROFILES: dict[str, dict[str, float]] = {
    "VLCC": {"speed_kmh": 27.5, "charter_usd_day": 95000.0, "capacity_mmbbl": 2.0, "draft_m": 20.5},
    "Suezmax": {"speed_kmh": 26.0, "charter_usd_day": 72000.0, "capacity_mmbbl": 1.0, "draft_m": 17.0},
}
DEFAULT_MULTIPLIERS: dict[str, float] = {
    "Pacific": 1.15,
    "Suez": 1.35,
    "Cape": 1.65,
    "Atlantic": 1.20,
    "Intra-Asia": 1.10,
    "Indian": 1.25,
}


def detect_lane(origin_lng: float, dest_lng: float, origin_lat: float, dest_lat: float) -> str:
    if abs(origin_lng - dest_lng) > 120:
        return "Pacific"
    if min(origin_lat, dest_lat) > 45 and abs(origin_lng - dest_lng) < 80:
        return "Atlantic"
    if min(origin_lng, dest_lng) > 30 and max(origin_lng, dest_lng) < 105:
        return "Indian"
    if abs(origin_lng - dest_lng) > 70:
        return "Suez"
    return "Intra-Asia"


def lane_multiplier(lane: str) -> float:
    dataset_value = registry.sea_lane_multiplier.get(lane)
    if dataset_value:
        return dataset_value
    return DEFAULT_MULTIPLIERS.get(lane, 1.2)


def sea_cost(distance_km: float) -> float:
    baseline = registry.mode_cost_baseline.get("sea", 3000.0)
    per_km = max(0.4, baseline / 1800.0)
    return round(distance_km * per_km, 2)


def sea_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> dict:
    distance_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    lane = detect_lane(origin_lng, dest_lng, origin_lat, dest_lat)
    adjusted_km = distance_km * lane_multiplier(lane)
    transit_days = adjusted_km / (AVG_VESSEL_SPEED_KMH * 24.0)
    return {
        "mode": "sea",
        "lane": lane,
        "distance_km": round(adjusted_km, 2),
        "transit_days": round(transit_days, 1),
        "cost_usd": sea_cost(adjusted_km),
    }


def crude_tanker_route(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    *,
    tanker_class: str = "VLCC",
    force_cape: bool = False,
    chokepoint: str = "Strait of Hormuz",
) -> dict:
    profile = TANKER_PROFILES.get(tanker_class, TANKER_PROFILES["VLCC"])
    direct_km = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    lane = "Cape of Good Hope" if force_cape else detect_lane(origin_lng, dest_lng, origin_lat, dest_lat)
    multiplier = 2.05 if force_cape else lane_multiplier(lane)
    distance_km = direct_km * multiplier
    transit_days = distance_km / (profile["speed_kmh"] * 24.0)
    if force_cape:
        transit_days += 14.0
    bunker_cost = distance_km * 18.0
    charter_cost = transit_days * profile["charter_usd_day"]
    war_risk_premium = 0.18 if chokepoint in {"Strait of Hormuz", "Bab el-Mandeb", "Red Sea"} and not force_cape else 0.06
    total_cost = (bunker_cost + charter_cost) * (1 + war_risk_premium)
    restrictions = []
    if tanker_class == "VLCC":
        restrictions.append("Requires deep-draft discharge or lightering at compatible ports.")
    if force_cape:
        restrictions.append("Avoids Red Sea/Bab el-Mandeb; adds about 14 days plus bunker and charter cost.")

    return {
        "mode": f"tanker_{tanker_class.lower()}",
        "engine": "maritime_tanker",
        "lane": lane,
        "chokepoint": chokepoint,
        "distance_km": round(distance_km, 2),
        "transit_days": round(transit_days, 1),
        "cost_usd": round(total_cost, 2),
        "capacity_mmbbl": profile["capacity_mmbbl"],
        "draft_m": profile["draft_m"],
        "charter_rate_usd_day": profile["charter_usd_day"],
        "risk_score": 0.58 if not force_cape else 0.31,
        "status_label": "Blocked corridor" if not force_cape else "Recommended alternate",
        "restrictions": restrictions,
    }
