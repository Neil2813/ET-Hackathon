from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import time

import httpx

_GDELT_RATE_LIMIT_UNTIL: float = 0.0

async def fetch_nasa_eonet() -> list[dict]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            "https://eonet.gsfc.nasa.gov/api/v3/events",
            params={
                "status": "open",
                "limit": 50,
                "days": 14,
            },
        )
        r.raise_for_status()
        data = r.json()
    events = []
    for e in data.get("events", []):
        coord = (e.get("geometry") or [{}])[-1].get("coordinates", [0, 0])
        source_url = ""
        sources = e.get("sources") or []
        if sources and isinstance(sources, list):
            source_url = str((sources[0] or {}).get("url") or "")
        events.append(
            {
                "id": f"eonet_{e.get('id')}",
                "event_type": (e.get("categories") or [{"id": "unknown"}])[0].get("id", "unknown"),
                "location": e.get("title", "unknown"),
                "severity": 7.0,
                "lng": coord[0] if len(coord) > 1 else 0,
                "lat": coord[1] if len(coord) > 1 else 0,
                "source": "nasa_eonet",
                "source_category": "disaster",
                "title": e.get("title", "unknown"),
                "url": source_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return events


async def fetch_gdelt() -> list[dict]:
    """
    GDELT Doc 2.0 API — completely free, no API key.
    Queries both general supply-chain terms AND energy/oil-specific terms
    (OPEC decisions, Iran crude, Hormuz tanker incidents, refinery disruptions)
    for the Geopolitical Risk Intelligence Agent.
    """
    global _GDELT_RATE_LIMIT_UNTIL
    now_ts = time.monotonic()
    if now_ts < _GDELT_RATE_LIMIT_UNTIL:
        return []

    # General supply chain + Energy/oil-specific queries for energy resilience
    queries = [
        "supply chain",
        "crude oil sanctions Iran OPEC",
        "Strait Hormuz tanker oil disruption",
        "refinery disruption petroleum shortage",
    ]
    # Severity hints: energy-specific queries get higher baseline severity
    _query_severity: dict[str, float] = {
        "supply chain": 5.5,
        "crude oil sanctions Iran OPEC": 7.2,
        "Strait Hormuz tanker oil disruption": 8.0,
        "refinery disruption petroleum shortage": 6.8,
    }
    seen: set[str] = set()
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for q in queries:
            try:
                r = await client.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc",
                    params={
                        "query": q,
                        "mode": "artlist",
                        "maxrecords": 10,
                        "format": "json",
                        "timespan": "24h",
                        "sort": "DateDesc",
                    },
                )
                if r.status_code == 429:
                    retry_after = int(r.headers.get("Retry-After") or 1800)
                    _GDELT_RATE_LIMIT_UNTIL = now_ts + max(300, retry_after)
                    break
                r.raise_for_status()
                data = r.json()
            except Exception:
                continue

            base_severity = _query_severity.get(q, 5.5)
            # Classify event type based on query category
            if "oil" in q or "Hormuz" in q or "refinery" in q or "OPEC" in q:
                event_type = "energy_geopolitical"
                source_category = "energy_risk"
            else:
                event_type = "geopolitical_news"
                source_category = "geopolitical"

            for article in (data.get("articles") or []):
                url = str(article.get("url") or "")
                if url in seen:
                    continue
                seen.add(url)
                sid = f"sig_{hashlib.sha256(f'gdelt|{url}'.encode('utf-8')).hexdigest()[:16]}"
                results.append({
                    "id": sid,
                    "event_type": event_type,
                    "location": str(article.get("sourcecountry") or "Global"),
                    "severity": base_severity,
                    "lat": 0.0,
                    "lng": 0.0,
                    "source": "gdelt",
                    "source_category": source_category,
                    "title": str(article.get("title") or "GDELT Signal"),
                    "url": url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "query_context": q,
                })
    return results


async def fetch_newsapi(api_key: str | None) -> list[dict]:
    if not api_key:
        return []
    queries = [
        "supply chain disruption",
        "port congestion freight delay",
        "factory shutdown manufacturing",
        "customs backlog logistics",
        # Energy/oil-specific queries for the energy resilience module
        "crude oil price OPEC Iran sanctions",
        "Strait of Hormuz shipping tanker",
        "India crude oil import refinery",
    ]
    seen: set[str] = set()
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for q in queries:
            try:
                r = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={"q": q, "pageSize": 10, "sortBy": "publishedAt", "apiKey": api_key},
                )
                r.raise_for_status()
                articles = r.json().get("articles") or []
            except Exception:
                continue

            for i, item in enumerate(articles):
                url = str(item.get("url") or "")
                if url in seen:
                    continue
                seen.add(url)
                basis = url or f"{q}|{i}"
                sid = f"sig_{hashlib.sha256(f'newsapi|{basis}'.encode('utf-8')).hexdigest()[:16]}"
                results.append({
                    "id": sid,
                    "event_type": "news_signal",
                    "location": "global",
                    "severity": 4.0,
                    "lat": 0.0,
                    "lng": 0.0,
                    "source": "newsapi",
                    "source_category": "news",
                    "title": str(item.get("title") or "NewsAPI Signal"),
                    "url": url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
    return results


async def fetch_gnews(api_key: str | None) -> list[dict]:
    if not api_key:
        return []
    queries = [
        "logistics disruption",
        "supply shortage",
        "port delay shipping",
    ]
    seen: set[str] = set()
    results: list[dict] = []

    async with httpx.AsyncClient(timeout=20.0) as client:
        for q in queries:
            try:
                r = await client.get(
                    "https://gnews.io/api/v4/search",
                    params={"q": q, "lang": "en", "max": 10, "apikey": api_key},
                )
                r.raise_for_status()
                articles = r.json().get("articles") or []
            except Exception:
                continue

            for i, item in enumerate(articles):
                url = str(item.get("url") or "")
                if url in seen:
                    continue
                seen.add(url)
                basis = url or f"{q}|{i}"
                sid = f"sig_{hashlib.sha256(f'gnews|{basis}'.encode('utf-8')).hexdigest()[:16]}"
                results.append({
                    "id": sid,
                    "event_type": "regional_news",
                    "location": "global",
                    "severity": 4.0,
                    "lat": 0.0,
                    "lng": 0.0,
                    "source": "gnews",
                    "source_category": "news",
                    "title": str(item.get("title") or "GNews Signal"),
                    "url": url,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
    return results
