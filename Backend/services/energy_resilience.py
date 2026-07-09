from __future__ import annotations

import math
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents.spr_optimization_agent import optimize_spr_drawdown

DB_PATH = Path(os.getenv("LOCAL_DB_PATH") or (Path(__file__).resolve().parent.parent / "local_fallback.db"))
LIVE_API_ENABLED = os.getenv("ENERGY_RESILIENCE_USE_LIVE_APIS", "true").strip().lower() in {"1", "true", "yes"}
HTTP_TIMEOUT_SECONDS = max(2.0, float(os.getenv("ENERGY_RESILIENCE_API_TIMEOUT_SECONDS", "8")))
GDELT_DOC_URL = os.getenv("ENERGY_RESILIENCE_GDELT_URL", "https://api.gdeltproject.org/api/v2/doc/doc")
PORTWATCH_TRANSIT_URL = os.getenv(
    "ENERGY_RESILIENCE_PORTWATCH_URL",
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query",
)
EIA_BRENT_URL = os.getenv(
    "ENERGY_RESILIENCE_EIA_BRENT_URL",
    "https://api.eia.gov/v2/petroleum/pri/spt/data/",
)
EIA_API_KEY = os.getenv("EIA_API_KEY", "").strip()


CRUDE_PROFILES: list[dict[str, Any]] = [
    {
        "id": "iranian_light",
        "name": "Iranian Light",
        "country": "Iran",
        "api_gravity": 33.4,
        "sulfur_pct": 1.5,
        "viscosity_cst": 6.2,
        "daily_available_mbd": 0.0,
        "blocked": True,
        "logistics": "Hormuz dependent",
    },
    {
        "id": "basrah_medium",
        "name": "Basrah Medium",
        "country": "Iraq",
        "api_gravity": 29.7,
        "sulfur_pct": 3.0,
        "viscosity_cst": 9.0,
        "daily_available_mbd": 0.42,
        "blocked": False,
        "logistics": "Gulf liftings, Suezmax/VLCC",
    },
    {
        "id": "arab_light",
        "name": "Arab Light",
        "country": "Saudi Arabia",
        "api_gravity": 33.0,
        "sulfur_pct": 1.8,
        "viscosity_cst": 5.8,
        "daily_available_mbd": 0.55,
        "blocked": False,
        "logistics": "Gulf liftings, high schedule reliability",
    },
    {
        "id": "us_permian_wti",
        "name": "US Permian WTI",
        "country": "United States",
        "api_gravity": 41.5,
        "sulfur_pct": 0.22,
        "viscosity_cst": 3.1,
        "daily_available_mbd": 0.34,
        "blocked": False,
        "logistics": "Long-haul Atlantic voyage, sweet blending candidate",
    },
    {
        "id": "bonny_light",
        "name": "Bonny Light",
        "country": "Nigeria",
        "api_gravity": 35.3,
        "sulfur_pct": 0.14,
        "viscosity_cst": 3.8,
        "daily_available_mbd": 0.21,
        "blocked": False,
        "logistics": "West Africa parcel cargo, piracy watch",
    },
    {
        "id": "dalia",
        "name": "Angola Dalia",
        "country": "Angola",
        "api_gravity": 23.6,
        "sulfur_pct": 0.51,
        "viscosity_cst": 12.5,
        "daily_available_mbd": 0.18,
        "blocked": False,
        "logistics": "Heavy sweet blending component",
    },
]

REFINERY_CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "jamnagar",
        "name": "Reliance Jamnagar",
        "operator": "Reliance",
        "api_min": 20.0,
        "api_max": 45.0,
        "sulfur_max_pct": 3.8,
        "viscosity_max_cst": 14.0,
        "demand_mbd": 1.24,
        "inventory_days": 8.0,
        "privacy_band": "private-aggregate",
    },
    {
        "id": "paradip",
        "name": "IOCL Paradip",
        "operator": "IOCL",
        "api_min": 24.0,
        "api_max": 42.0,
        "sulfur_max_pct": 3.2,
        "viscosity_max_cst": 11.0,
        "demand_mbd": 0.30,
        "inventory_days": 5.5,
        "privacy_band": "public-sector",
    },
    {
        "id": "mumbai_bpcl",
        "name": "BPCL Mumbai",
        "operator": "BPCL",
        "api_min": 28.0,
        "api_max": 42.0,
        "sulfur_max_pct": 2.2,
        "viscosity_max_cst": 8.5,
        "demand_mbd": 0.24,
        "inventory_days": 4.2,
        "privacy_band": "public-sector",
    },
    {
        "id": "vizag_hpcl",
        "name": "HPCL Visakhapatnam",
        "operator": "HPCL",
        "api_min": 26.0,
        "api_max": 40.0,
        "sulfur_max_pct": 2.8,
        "viscosity_max_cst": 9.5,
        "demand_mbd": 0.27,
        "inventory_days": 6.0,
        "privacy_band": "public-sector",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _http_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any] | None:
    if not LIVE_API_ENABLED:
        return None
    query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None})
    target = f"{url}?{query}" if query else url
    try:
        req = urllib.request.Request(target, headers={"User-Agent": "SupplyShield-EnergyResilience/1.0"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            if int(resp.status) != 200:
                return None
            raw = resp.read(2_000_000)
        import json

        parsed = json.loads(raw.decode("utf-8"))
        return parsed if isinstance(parsed, (dict, list)) else None
    except Exception:
        return None


def _latest_portwatch_transit(portwatch_name: str) -> dict[str, Any] | None:
    data = _http_json(
        PORTWATCH_TRANSIT_URL,
        {
            "where": f"portname='{portwatch_name.replace(chr(39), chr(39) + chr(39))}'",
            "outFields": "date,n_total",
            "orderByFields": "date DESC",
            "resultRecordCount": "14",
            "f": "json",
        },
    )
    if not isinstance(data, dict):
        return None
    features = data.get("features")
    if not isinstance(features, list) or not features:
        return None
    values: list[float] = []
    latest_date = ""
    for feature in features:
        attrs = feature.get("attributes") if isinstance(feature, dict) else {}
        if not isinstance(attrs, dict):
            continue
        if not latest_date and attrs.get("date") is not None:
            latest_date = str(attrs.get("date"))
        try:
            values.append(float(attrs.get("n_total")))
        except Exception:
            continue
    if not values:
        return None
    latest = values[0]
    baseline = sum(values[1:]) / max(1, len(values[1:])) if len(values) > 1 else latest
    wow_change_pct = ((latest - baseline) / baseline * 100.0) if baseline else 0.0
    return {
        "latest_transit_count": round(latest, 2),
        "baseline_transit_count": round(baseline, 2),
        "wow_change_pct": round(wow_change_pct, 2),
        "latest_date": latest_date,
        "source": "IMF PortWatch",
    }


def _fetch_brent_trend() -> dict[str, Any] | None:
    if not EIA_API_KEY:
        return None
    data = _http_json(
        EIA_BRENT_URL,
        {
            "frequency": "daily",
            "data[0]": "value",
            "facets[series][]": "RBRTE",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": "0",
            "length": "10",
            "api_key": EIA_API_KEY,
        },
    )
    if not isinstance(data, dict):
        return None
    rows = (((data.get("response") or {}) if isinstance(data.get("response"), dict) else {}).get("data") or [])
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    try:
        latest = float(rows[0].get("value"))
        previous = float(rows[-1].get("value"))
    except Exception:
        return None
    trend_pct = ((latest - previous) / previous * 100.0) if previous else 0.0
    return {
        "brent_latest_usd": round(latest, 2),
        "brent_trend_pct": round(trend_pct, 2),
        "observations": len(rows),
        "source": "U.S. EIA",
    }


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def migrate_energy_resilience_schema() -> None:
    """Add crude/refinery compatibility fields to the normalized graph table."""

    with _connect() as con:
        for ddl in [
            "ALTER TABLE graph_nodes ADD COLUMN api_gravity REAL",
            "ALTER TABLE graph_nodes ADD COLUMN sulfur_pct REAL",
            "ALTER TABLE graph_nodes ADD COLUMN viscosity_cst REAL",
            "ALTER TABLE graph_nodes ADD COLUMN crude_grade TEXT",
            "ALTER TABLE graph_nodes ADD COLUMN distillation_profile_json TEXT",
            "ALTER TABLE graph_nodes ADD COLUMN inventory_days REAL",
            "ALTER TABLE graph_nodes ADD COLUMN privacy_band TEXT",
        ]:
            try:
                con.execute(ddl)
            except Exception:
                pass
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS exchange_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                from_refinery TEXT NOT NULL,
                to_refinery TEXT NOT NULL,
                crude_grade TEXT NOT NULL,
                transfer_mbd REAL NOT NULL,
                privacy_band TEXT NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def _tenant_graph_nodes(tenant_id: str) -> list[dict[str, Any]]:
    try:
        with _connect() as con:
            rows = con.execute(
                """
                SELECT node_id, node_type, name, country, tier, daily_throughput_usd,
                       safety_stock_days, criticality, api_gravity, sulfur_pct,
                       viscosity_cst, crude_grade, inventory_days, privacy_band
                FROM graph_nodes
                WHERE tenant_id = ?
                """,
                (tenant_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception:
        return []


def _score_match(crude: dict[str, Any], refinery: dict[str, Any]) -> dict[str, Any]:
    api = float(crude["api_gravity"])
    sulfur = float(crude["sulfur_pct"])
    viscosity = float(crude["viscosity_cst"])
    api_ok = float(refinery["api_min"]) <= api <= float(refinery["api_max"])
    sulfur_ok = sulfur <= float(refinery["sulfur_max_pct"])
    viscosity_ok = viscosity <= float(refinery["viscosity_max_cst"])
    api_mid = (float(refinery["api_min"]) + float(refinery["api_max"])) / 2
    api_span = max(1.0, float(refinery["api_max"]) - float(refinery["api_min"]))
    api_score = max(0.0, 1.0 - abs(api - api_mid) / api_span)
    sulfur_score = max(0.0, 1.0 - sulfur / max(0.1, float(refinery["sulfur_max_pct"])))
    viscosity_score = max(0.0, 1.0 - viscosity / max(0.1, float(refinery["viscosity_max_cst"])))
    logistics_penalty = 0.08 if "long-haul" in str(crude["logistics"]).lower() else 0.0
    score = (api_score * 0.40) + (sulfur_score * 0.35) + (viscosity_score * 0.20) - logistics_penalty + 0.05
    compatible = api_ok and sulfur_ok and viscosity_ok and not bool(crude.get("blocked"))
    return {
        "compatible": compatible,
        "score": round(max(0.0, min(1.0, score)), 3),
        "constraints": {
            "api_gravity": "pass" if api_ok else "fail",
            "sulfur": "pass" if sulfur_ok else "fail",
            "viscosity": "pass" if viscosity_ok else "fail",
        },
    }


def build_ais_anomaly_forecast() -> dict[str, Any]:
    fallback_vessels = [
        {
            "mmsi": "419001241",
            "name": "MT Narmada Spirit",
            "corridor": "Strait of Hormuz",
            "lat": 26.55,
            "lng": 56.28,
            "speed_knots": 5.1,
            "expected_speed_knots": 12.4,
            "ais_gap_minutes": 148,
            "route_deviation_nm": 18.7,
        },
        {
            "mmsi": "419008771",
            "name": "MT Konkan Star",
            "corridor": "Bab el-Mandeb",
            "lat": 12.72,
            "lng": 43.25,
            "speed_knots": 14.2,
            "expected_speed_knots": 13.8,
            "ais_gap_minutes": 18,
            "route_deviation_nm": 3.4,
        },
        {
            "mmsi": "419004902",
            "name": "MT Kaveri Bridge",
            "corridor": "Strait of Hormuz",
            "lat": 26.31,
            "lng": 56.78,
            "speed_knots": 0.8,
            "expected_speed_knots": 11.5,
            "ais_gap_minutes": 39,
            "route_deviation_nm": 7.2,
        },
    ]
    portwatch = {
        "Strait of Hormuz": _latest_portwatch_transit("Strait of Hormuz"),
        "Bab el-Mandeb": _latest_portwatch_transit("Bab el-Mandeb Strait"),
    }
    vessels = []
    for vessel in fallback_vessels:
        # Fetch weather data
        corridor_name = str(vessel["corridor"]).lower()
        choke_key = ""
        if "hormuz" in corridor_name:
            choke_key = "hormuz"
        elif "mandeb" in corridor_name or "mand" in corridor_name:
            choke_key = "bab_el_mand"
        elif "malacca" in corridor_name:
            choke_key = "malacca_w"
        elif "suez" in corridor_name:
            choke_key = "suez_s"
        elif "panama" in corridor_name:
            choke_key = "panama_n"
        elif "good hope" in corridor_name:
            choke_key = "cape_good"

        weather_info = {}
        if choke_key:
            from services.marine_weather import get_chokepoint_weather
            weather_info = get_chokepoint_weather(choke_key)

        live_corridor = portwatch.get(str(vessel["corridor"]))
        if live_corridor:
            drop_pct = max(0.0, -float(live_corridor.get("wow_change_pct") or 0.0))
            vessel = {
                **vessel,
                "latest_transit_count": live_corridor.get("latest_transit_count"),
                "transit_wow_change_pct": live_corridor.get("wow_change_pct"),
                "source": live_corridor.get("source"),
                "source_date": live_corridor.get("latest_date"),
                "ais_gap_minutes": max(float(vessel["ais_gap_minutes"]), drop_pct * 4.0),
                "route_deviation_nm": max(float(vessel["route_deviation_nm"]), drop_pct / 2.0),
            }
        else:
            vessel = {**vessel, "source": "curated fallback"}

        vessel.update({
            "wave_height_m": weather_info.get("wave_height_m", 1.2),
            "wind_speed_kmh": weather_info.get("wind_speed_kmh", 15.0),
            "weather_delay_days": weather_info.get("weather_delay_days", 0.0),
            "weather_status": weather_info.get("status", "normal"),
        })
        vessels.append(vessel)
    scored = []
    for vessel in vessels:
        speed_delta = abs(float(vessel["speed_knots"]) - float(vessel["expected_speed_knots"]))
        dark_score = min(1.0, float(vessel["ais_gap_minutes"]) / 180.0)
        speed_score = min(1.0, speed_delta / 10.0)
        deviation_score = min(1.0, float(vessel["route_deviation_nm"]) / 20.0)
        anomaly_score = round((dark_score * 0.45) + (speed_score * 0.30) + (deviation_score * 0.25), 3)
        if anomaly_score >= 0.74:
            status = "critical"
        elif anomaly_score >= 0.45:
            status = "watch"
        else:
            status = "normal"
        scored.append({**vessel, "anomaly_score": anomaly_score, "status": status})
    return {
        "model": "spatial-temporal anomaly surrogate with IMF PortWatch live corridor proxy",
        "lead_time_hours": 18,
        "high_risk_corridors": sorted({str(v["corridor"]) for v in scored if str(v["status"]) in {"critical", "watch"}}),
        "vessels": scored,
        "live_sources": {
            "portwatch_enabled": LIVE_API_ENABLED,
            "portwatch_used": any(v is not None for v in portwatch.values()),
            "fallback_used": not any(v is not None for v in portwatch.values()),
        },
        "generated_at": _now(),
    }


def build_spr_policy(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    inputs = dict(payload or {})
    brent = _fetch_brent_trend()
    if brent:
        trend = float(brent.get("brent_trend_pct") or 0.0)
        if "supply_gap_mbd" not in inputs and trend > 5:
            inputs["supply_gap_mbd"] = min(2.4, 1.4 + (trend / 20.0))
        inputs.setdefault("brent_trend_pct", trend)
    spr = optimize_spr_drawdown(inputs)
    schedule = spr.get("schedule", [])
    first_week_draw = sum(float(day.get("spr_draw_mbd") or 0.0) for day in schedule[:7])
    avg_draw = first_week_draw / 7 if schedule else 0.0
    peak_stress = max((float(day.get("stress_index") or 0.0) for day in schedule), default=0.0)
    return {
        **spr,
        "agent": "PPO/SAC-ready transparent policy controller",
        "state_space": ["spr_cover_days", "refinery_demand", "brent_trend", "shipping_queue_time"],
        "action_space": ["drawdown_mbd", "replenishment_mbd", "forward_procurement"],
        "recommended_action": {
            "drawdown_rate_mbd": round(avg_draw, 3),
            "replenishment_eta_days": inputs.get("replenishment_eta_days", 21),
            "forward_procurement": "secure non-Hormuz cargo optionality for days 14-30",
            "human_gate_required": peak_stress >= 0.35 or spr.get("exhaustion_day") is not None,
        },
        "market_inputs": brent or {
            "source": "curated fallback",
            "brent_latest_usd": None,
            "brent_trend_pct": inputs.get("brent_trend_pct", 0.0),
            "fallback_used": True,
        },
    }


def build_compatibility_matches(blocked_grade: str = "iranian_light") -> dict[str, Any]:
    blocked = next((c for c in CRUDE_PROFILES if c["id"] == blocked_grade), CRUDE_PROFILES[0])
    matches = []
    for refinery in REFINERY_CAPABILITIES:
        alternatives = []
        for crude in CRUDE_PROFILES:
            if crude["id"] == blocked["id"]:
                continue
            match = _score_match(crude, refinery)
            if match["compatible"]:
                alternatives.append({
                    "crude": crude,
                    "compatibility_score": match["score"],
                    "constraints": match["constraints"],
                    "blend_note": _blend_note(blocked, crude),
                })
        alternatives.sort(key=lambda item: item["compatibility_score"], reverse=True)
        matches.append({
            "refinery": refinery,
            "blocked_grade": blocked,
            "alternatives": alternatives[:3],
        })
    return {
        "blocked_grade": blocked,
        "matches": matches,
        "generated_at": _now(),
    }


def _blend_note(blocked: dict[str, Any], crude: dict[str, Any]) -> str:
    blocked_sour = float(blocked["sulfur_pct"]) > 1.0
    sweet = float(crude["sulfur_pct"]) < 0.5
    if blocked_sour and sweet:
        return "Sweet crude can dilute sulfur but may require heavier blend stock for yield balance."
    if float(crude["api_gravity"]) < 26:
        return "Heavy component improves residue yield balance but needs high-conversion refinery capacity."
    return "Closest operational substitute with standard assay checks before nomination."


def build_geopolitical_rag() -> dict[str, Any]:
    fallback_documents = [
        {
            "source": "GDELT",
            "title": "Naval advisory reports elevated drone activity near Gulf tanker lane",
            "corridor": "Strait of Hormuz",
            "actors": ["regional militia", "naval forces"],
            "threat_type": "kinetic attacks",
            "likelihood": 0.78,
            "severity": 0.86,
        },
        {
            "source": "ReliefWeb",
            "title": "Port labor disruption warning extends Red Sea cargo clearance times",
            "corridor": "Bab el-Mandeb",
            "actors": ["port authority", "labor union"],
            "threat_type": "port disruption",
            "likelihood": 0.44,
            "severity": 0.47,
        },
        {
            "source": "Maritime Registry",
            "title": "War-risk insurance premium widens for India-bound Gulf cargoes",
            "corridor": "Strait of Hormuz",
            "actors": ["marine insurers"],
            "threat_type": "market access",
            "likelihood": 0.69,
            "severity": 0.72,
        },
    ]
    live_documents = _fetch_gdelt_maritime_documents()
    documents = live_documents or fallback_documents
    risk_by_corridor: dict[str, dict[str, Any]] = {}
    for doc in documents:
        key = str(doc["corridor"])
        current = risk_by_corridor.setdefault(key, {"likelihood": 0.0, "severity": 0.0, "count": 0})
        current["likelihood"] += float(doc["likelihood"])
        current["severity"] += float(doc["severity"])
        current["count"] += 1
    for item in risk_by_corridor.values():
        count = max(1, int(item.pop("count")))
        item["likelihood"] = round(item["likelihood"] / count, 3)
        item["severity"] = round(item["severity"] / count, 3)
        item["risk_score"] = round(math.sqrt(item["likelihood"] * item["severity"]), 3)
    return {
        "vector_store": "GDELT maritime-risk corpus" if live_documents else "local maritime-risk corpus",
        "documents": documents,
        "risk_by_corridor": risk_by_corridor,
        "live_sources": {
            "gdelt_enabled": LIVE_API_ENABLED,
            "gdelt_used": bool(live_documents),
            "fallback_used": not bool(live_documents),
        },
        "generated_at": _now(),
    }


def _fetch_gdelt_maritime_documents() -> list[dict[str, Any]]:
    data = _http_json(
        GDELT_DOC_URL,
        {
            "query": '"Strait of Hormuz" OR "Bab el-Mandeb" tanker OR maritime OR oil shipping',
            "mode": "ArtList",
            "maxrecords": "20",
            "format": "json",
            "timespan": "48h",
        },
    )
    if not isinstance(data, dict):
        return []
    articles = data.get("articles")
    if not isinstance(articles, list):
        return []
    out: list[dict[str, Any]] = []
    for article in articles[:12]:
        if not isinstance(article, dict):
            continue
        title = str(article.get("title") or "").strip()
        if not title:
            continue
        text = f"{title} {article.get('seendate') or ''}".lower()
        if "bab" in text or "red sea" in text or "yemen" in text:
            corridor = "Bab el-Mandeb"
        elif "hormuz" in text or "iran" in text or "gulf" in text:
            corridor = "Strait of Hormuz"
        else:
            corridor = "Strait of Hormuz"
        threat_type = _classify_threat(title)
        severity = _severity_from_text(title)
        likelihood = min(0.92, 0.38 + severity * 0.45)
        out.append({
            "source": str(article.get("domain") or "GDELT"),
            "title": title,
            "url": article.get("url"),
            "published_at": article.get("seendate"),
            "corridor": corridor,
            "actors": _actors_from_text(title),
            "threat_type": threat_type,
            "likelihood": round(likelihood, 3),
            "severity": round(severity, 3),
        })
    return out


def _classify_threat(title: str) -> str:
    low = title.lower()
    if any(token in low for token in ["attack", "missile", "drone", "strike", "explosion"]):
        return "kinetic attacks"
    if any(token in low for token in ["sanction", "embargo", "restriction"]):
        return "sanctions"
    if any(token in low for token in ["cyber", "hack", "outage"]):
        return "cyber threats"
    if any(token in low for token in ["insurance", "premium", "freight", "rate"]):
        return "market access"
    return "maritime security"


def _severity_from_text(title: str) -> float:
    low = title.lower()
    score = 0.42
    for token, bump in {
        "attack": 0.22,
        "missile": 0.20,
        "drone": 0.18,
        "closure": 0.24,
        "war": 0.16,
        "sanction": 0.14,
        "tanker": 0.10,
        "oil": 0.08,
    }.items():
        if token in low:
            score += bump
    return max(0.15, min(0.95, score))


def _actors_from_text(title: str) -> list[str]:
    low = title.lower()
    actors = []
    if "iran" in low:
        actors.append("Iran")
    if "houthi" in low or "yemen" in low:
        actors.append("Houthi/Yemen actors")
    if "navy" in low or "naval" in low:
        actors.append("naval forces")
    if "insurer" in low or "insurance" in low:
        actors.append("marine insurers")
    return actors or ["open-source reporting"]


def build_exchange_ledger(tenant_id: str) -> dict[str, Any]:
    graph_nodes = _tenant_graph_nodes(tenant_id)
    refineries = [n for n in graph_nodes if str(n.get("node_type") or "").lower() == "refinery"]
    if len(refineries) < 2:
        refineries = REFINERY_CAPABILITIES
    normalized = []
    for item in refineries:
        normalized.append({
            "id": str(item.get("id") or item.get("node_id") or item.get("name")),
            "name": str(item.get("name")),
            "operator": str(item.get("operator") or "tenant"),
            "inventory_days": float(item.get("inventory_days") or item.get("safety_stock_days") or 6.0),
            "demand_mbd": float(item.get("demand_mbd") or 0.25),
            "privacy_band": str(item.get("privacy_band") or "aggregated"),
        })
    short = min(normalized, key=lambda row: row["inventory_days"])
    surplus = max(normalized, key=lambda row: row["inventory_days"])
    transfer_mbd = round(min(0.16, max(0.02, (surplus["inventory_days"] - short["inventory_days"]) * 0.025)), 3)
    recommendation = {
        "from_refinery": surplus,
        "to_refinery": short,
        "crude_grade": "Arab Light / compatible medium sour basket",
        "transfer_mbd": transfer_mbd,
        "privacy_boundary": "Only inventory band and transfer availability are exposed; refinery-level economics remain private.",
        "reason": f"{short['name']} is closest to critical stockout band at {short['inventory_days']:.1f} days.",
    }
    return {
        "tenant_id": tenant_id,
        "participants": normalized,
        "recommendation": recommendation,
        "generated_at": _now(),
    }


def build_energy_resilience_dashboard(tenant_id: str) -> dict[str, Any]:
    ais = build_ais_anomaly_forecast()
    spr = build_spr_policy({
        "supply_gap_mbd": 1.8 if "Strait of Hormuz" in ais["high_risk_corridors"] else 1.2,
        "replenishment_eta_days": 24,
    })
    compatibility = build_compatibility_matches()
    rag = build_geopolitical_rag()
    ledger = build_exchange_ledger(tenant_id)
    corridor_risk = max((v["risk_score"] for v in rag["risk_by_corridor"].values()), default=0.0)
    anomaly_risk = max((v["anomaly_score"] for v in ais["vessels"]), default=0.0)
    reserve_stress = float(spr.get("average_stress_index") or 0.0)
    national_score = round((corridor_risk * 0.40) + (anomaly_risk * 0.35) + (reserve_stress * 0.25), 3)

    # Compute ESG CO2 comparison data
    try:
        from routing.sea import crude_tanker_route
        from services.co2_optimizer import compute_co2_comparison
        routes = [
            crude_tanker_route(26.5, 56.0, 22.5, 70.0, tanker_class="VLCC"),
            crude_tanker_route(26.5, 56.0, 22.5, 70.0, tanker_class="Suezmax"),
            crude_tanker_route(26.5, 56.0, 22.5, 70.0, tanker_class="VLCC", force_cape=True)
        ]
        for r in routes:
            r["cost"] = {"usd": r["cost_usd"], "local": r["cost_usd"], "currency": "USD", "rate": 1.0}
        esg_comparison = compute_co2_comparison(routes)
    except Exception:
        esg_comparison = []

    return {
        "tenant_id": tenant_id,
        "generated_at": _now(),
        "national_resilience_score": national_score,
        "status": "critical" if national_score >= 0.72 else "watch" if national_score >= 0.45 else "stable",
        "ais": ais,
        "spr": spr,
        "compatibility": compatibility,
        "rag": rag,
        "exchange_ledger": ledger,
        "esg": {
            "routes": esg_comparison,
            "carbon_price_per_ton": 85.00,
            "average_esg_score": round(sum(r["co2_data"]["esg_score"] for r in esg_comparison) / len(esg_comparison), 1) if esg_comparison else 85.0,
            "total_emissions_avoided_tons": 3450.0,
        }
    }
