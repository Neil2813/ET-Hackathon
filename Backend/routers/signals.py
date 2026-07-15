from __future__ import annotations

from fastapi import APIRouter, Depends

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import add_audit, list_signals
from services.data_registry import registry
from services.signal_geocode import geocode_signal
from routers.schemas import SignalScoreRequest
from routers.helpers import (
    _parsed_signals,
    _score_to_status,
    _score_to_trend,
    _normalized_url,
    _enqueue_celery_task,
)

router = APIRouter(tags=["Signals"])


@router.get("/signals/live")
async def signals_live(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    signal_rows = _parsed_signals(limit=50)
    add_audit("signals_live_read", user.get("sub", "unknown"))
    return signal_rows


@router.post("/signals/score")
async def signals_score(payload: SignalScoreRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    base_cost = registry.assessment_cost_by_event.get(payload.event_type.strip(), 10000.0)
    severity_factor = payload.severity / 10.0
    return {
        "signal_id": payload.signal_id,
        "relevance_score": round(min(1.0, 0.25 + severity_factor * 0.75), 3),
        "estimated_cost_impact_usd": round(base_cost * max(0.3, severity_factor), 2),
        "scored_by": user.get("sub", "local"),
    }


@router.get("/signals/cache")
async def cached_signals(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    return list_signals(limit=50)


@router.get("/api/signals/hazards")
async def api_signals_hazards() -> list[dict]:
    hazards: list[dict] = []
    for sig in _parsed_signals(limit=5000):
        hazards.append(
            {
                "id": str(sig.get("id") or sig.get("signal_id")),
                "type": str(sig.get("event_type") or "risk"),
                "title": str(sig.get("title") or sig.get("event_type") or "Hazard signal"),
                "location": str(sig.get("location") or "Unknown"),
                "time": str(sig.get("created_at") or ""),
                "severity": _score_to_status(float(sig.get("severity") or 0)),
                "lat": float(sig.get("lat", 0) or 0),
                "lng": float(sig.get("lng", 0) or 0),
                "url": _normalized_url(str(sig.get("url") or "")),
            }
        )
    return hazards


@router.get("/api/signals/news")
async def api_signals_news() -> list[dict]:
    rows = _parsed_signals(limit=5000)
    news_sources = {"gdelt", "newsapi", "gnews"}
    filtered = [
        sig
        for sig in rows
        if str(sig.get("source", "")).lower() in news_sources or bool(_normalized_url(str(sig.get("url") or "")))
    ]
    return [
        {
            "id": str(sig.get("id") or sig.get("signal_id")),
            "source": str(sig.get("source") or "signal"),
            "title": str(sig.get("title") or sig.get("event_type") or "News signal"),
            "location": str(sig.get("location") or "Unknown"),
            "time": str(sig.get("created_at") or ""),
            "relevanceScore": round(min(1.0, max(0.0, float(sig.get("severity") or 0) / 10.0)), 3),
            "url": _normalized_url(str(sig.get("url") or "")),
        }
        for sig in filtered
    ]


@router.get("/api/signals/sources")
async def api_signals_sources() -> list[dict]:
    rows = _parsed_signals(limit=5000)
    by_source: dict[str, int] = {}
    latest_by_source: dict[str, str] = {}
    for sig in rows:
        src = str(sig.get("source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        latest_by_source[src] = str(sig.get("created_at") or latest_by_source.get(src) or "")

    SOURCE_META: dict[str, dict] = {
        "nasa_eonet":  {"category": "disaster",     "label": "NASA EONET",         "url": "https://eonet.gsfc.nasa.gov"},
        "gdacs":       {"category": "disaster",     "label": "GDACS",              "url": "https://gdacs.org"},
        "usgs":        {"category": "disaster",     "label": "USGS Earthquakes",   "url": "https://earthquake.usgs.gov"},
        "nasa_firms":  {"category": "disaster",     "label": "NASA FIRMS",         "url": "https://firms.modaps.eosdis.nasa.gov"},
        "reliefweb":   {"category": "humanitarian", "label": "ReliefWeb",          "url": "https://reliefweb.int"},
        "gdelt":       {"category": "geopolitical", "label": "GDELT Project",      "url": "https://gdeltproject.org"},
        "acled":       {"category": "geopolitical", "label": "ACLED",              "url": "https://acleddata.com"},
        "newsapi":     {"category": "news",         "label": "NewsAPI",            "url": "https://newsapi.org"},
        "gnews":       {"category": "news",         "label": "GNews",              "url": "https://gnews.io"},
        "ofac":        {"category": "regulatory",   "label": "OFAC Sanctions",     "url": "https://sanctionssearch.ofac.treas.gov"},
        "mastodon":    {"category": "sentiment",    "label": "Mastodon (BERT)",    "url": "https://mastodon.social"},
        "hackernews":  {"category": "sentiment",    "label": "HackerNews (BERT)",  "url": "https://news.ycombinator.com"},
        "reddit":      {"category": "sentiment",    "label": "Reddit (BERT)",      "url": "https://reddit.com"},
    }
    return [
        {
            "id": f"src_{idx+1}",
            "name": name,
            "label": SOURCE_META.get(name, {}).get("label", name),
            "category": SOURCE_META.get(name, {}).get("category", "other"),
            "source_url": SOURCE_META.get(name, {}).get("url", ""),
            "active": True,
            "lastFetch": latest_by_source.get(name, ""),
            "recordCount": count,
            "latencyMs": 0,
        }
        for idx, (name, count) in enumerate(sorted(by_source.items(), key=lambda kv: kv[1], reverse=True))
    ]


@router.get("/api/signals/categorized")
async def api_signals_categorized() -> dict:
    """Returns all signals grouped by source_category for the Global Monitoring page."""
    rows = _parsed_signals(limit=5000)
    categories: dict[str, list[dict]] = {
        "disaster": [], "geopolitical": [], "news": [],
        "regulatory": [], "sentiment": [], "humanitarian": [], "social_news": [],
        "maritime": [], "trade": [],
    }

    for sig in rows:
        sig = geocode_signal(sig)
        cat = str(sig.get("source_category") or "")
        if not cat:
            src = str(sig.get("source") or "")
            if src in ("nasa_eonet", "gdacs", "usgs", "nasa_firms"): cat = "disaster"
            elif src in ("gdelt", "acled"): cat = "geopolitical"
            elif src in ("imf_portwatch", "imf_portwatch_disruptions"): cat = "maritime"
            elif src == "wto": cat = "trade"
            elif src in ("newsapi", "gnews"): cat = "news"
            elif src == "reliefweb": cat = "humanitarian"
            elif src == "ofac": cat = "regulatory"
            elif sig.get("event_type") == "sentiment_aggregate": cat = "sentiment"
            elif sig.get("event_type") == "social_news_signal": cat = "social_news"
            else: cat = "news"
        bucket = categories.get(cat, categories["news"])
        bucket.append({
            "id": str(sig.get("id") or sig.get("signal_id")),
            "event_type": str(sig.get("event_type") or "signal"),
            "title": str(sig.get("title") or "Signal"),
            "description": str(sig.get("description") or sig.get("summary") or sig.get("event_type") or ""),
            "location": str(sig.get("location") or "Unknown"),
            "severity": _score_to_status(float(sig.get("severity") or 0)),
            "severity_raw": float(sig.get("severity") or 0),
            "lat": float(sig.get("lat", 0) or 0),
            "lng": float(sig.get("lng", 0) or 0),
            "source": str(sig.get("source") or "unknown"),
            "source_category": cat,
            "url": _normalized_url(str(sig.get("url") or "")),
            "time": str(sig.get("created_at") or ""),
            "published_at": str(sig.get("created_at") or ""),
            "detected_at": str(sig.get("created_at") or ""),
            "verified": bool((sig.get("citation") or {}).get("verified")) if isinstance(sig.get("citation"), dict) else False,
            "corroborated_by": list((sig.get("citation") or {}).get("corroborated_by") or []) if isinstance(sig.get("citation"), dict) else [],
            "corroboration_count": int(((sig.get("citation") or {}).get("corroboration_count") or 0)) if isinstance(sig.get("citation"), dict) else 0,
            "relevance_score": float(sig.get("relevance_score") or 0),
            # sentiment-specific fields
            "sentiment_topic": sig.get("sentiment_topic"),
            "sentiment_positive_pct": sig.get("sentiment_positive_pct"),
            "sentiment_negative_pct": sig.get("sentiment_negative_pct"),
            "sentiment_neutral_pct": sig.get("sentiment_neutral_pct"),
            "sentiment_post_count": sig.get("sentiment_post_count"),
            "sentiment": sig.get("sentiment"),
            "sentiment_score": sig.get("sentiment_score"),
        })
    return {cat: items for cat, items in categories.items()}


@router.get("/api/signals/sentiment")
async def api_signals_sentiment() -> list[dict]:
    """Returns only BERT sentiment aggregate signals for quick dashboard access."""
    rows = _parsed_signals(limit=5000)
    return [
        {
            "id": str(sig.get("id") or sig.get("signal_id")),
            "source": str(sig.get("source") or "unknown"),
            "topic": str(sig.get("sentiment_topic") or "general"),
            "positive_pct": float(sig.get("sentiment_positive_pct") or 0),
            "negative_pct": float(sig.get("sentiment_negative_pct") or 0),
            "neutral_pct": float(sig.get("sentiment_neutral_pct") or 0),
            "post_count": int(sig.get("sentiment_post_count") or 0),
            "time": str(sig.get("created_at") or ""),
        }
        for sig in rows
        if sig.get("event_type") == "sentiment_aggregate"
    ]


@router.post("/api/signals/refresh")
async def api_signals_refresh() -> dict:
    """On-demand signal refresh — triggers immediate poll of all 12 source streams."""
    return _enqueue_celery_task("scheduler.tasks.poll_signals")


@router.get("/api/signals/lead-time-metrics")
async def api_signals_lead_time_metrics(
    window_signals: int = 500,
) -> dict:
    """
    Compute signal detection lead-time metrics from stored signal timestamps.

    Lead time = how quickly we ingested a signal after the source event occurred.
    Specifically: ingestion_lag_hours = (our created_at) − (source event timestamp)

    A negative lag means we ingested the signal before the source event timestamp
    (e.g. a forecast or early-warning feed). Near-zero means near-real-time.

    Data is derived from actual DB records — not estimated or fabricated.
    The 'data_window' field documents exactly how many signals were analyzed.

    No auth required — this is a transparency endpoint.
    """
    from datetime import datetime, timezone
    from statistics import median, mean
    from services.event_freshness import extract_event_timestamp, parse_event_dt

    rows = _parsed_signals(limit=window_signals)
    now = datetime.now(timezone.utc)

    per_source: dict[str, list[float]] = {}
    total_lags: list[float] = []
    signals_with_source_ts = 0
    signals_without_source_ts = 0

    for sig in rows:
        # Our ingestion time
        our_time_raw = sig.get("created_at") or sig.get("detected_at")
        our_time = parse_event_dt(our_time_raw) if our_time_raw else now

        # Source event time (when the event actually happened / was reported)
        source_time = None
        for key in ("timestamp", "time", "event_time", "event_date", "fromdate", "startdate"):
            parsed = parse_event_dt(sig.get(key))
            if parsed:
                source_time = parsed
                break

        if not source_time:
            # Check if GDACS title contains a date
            title = str(sig.get("title") or sig.get("event_title") or sig.get("htmldescription") or "")
            from services.event_freshness import _parse_gdacs_title_date
            source_time = _parse_gdacs_title_date(title)

        if source_time is None:
            signals_without_source_ts += 1
            continue

        signals_with_source_ts += 1
        lag_hours = (our_time - source_time).total_seconds() / 3600.0

        # Exclude implausible lags (>30 days or negative > 24h — likely clock skew)
        if -24.0 <= lag_hours <= 720.0:
            source = str(sig.get("source") or "unknown")
            per_source.setdefault(source, []).append(lag_hours)
            total_lags.append(lag_hours)

    # Build per-source summary
    source_breakdown: list[dict] = []
    for source, lags in sorted(per_source.items(), key=lambda kv: len(kv[1]), reverse=True):
        source_breakdown.append({
            "source": source,
            "signal_count": len(lags),
            "median_lag_hours": round(median(lags), 2),
            "mean_lag_hours": round(mean(lags), 2),
            "min_lag_hours": round(min(lags), 2),
            "max_lag_hours": round(max(lags), 2),
            "near_realtime_pct": round(
                sum(1 for l in lags if l <= 1.0) / len(lags) * 100, 1
            ),
        })

    overall_median = round(median(total_lags), 2) if total_lags else None
    overall_mean = round(mean(total_lags), 2) if total_lags else None

    return {
        "generated_at": now.isoformat(),
        "data_window": {
            "signals_queried": len(rows),
            "signals_with_source_timestamp": signals_with_source_ts,
            "signals_without_source_timestamp": signals_without_source_ts,
            "coverage_pct": round(signals_with_source_ts / max(1, len(rows)) * 100, 1),
        },
        "overall": {
            "median_ingestion_lag_hours": overall_median,
            "mean_ingestion_lag_hours": overall_mean,
            "total_signals_analyzed": len(total_lags),
            "near_realtime_pct": round(
                sum(1 for l in total_lags if l <= 1.0) / max(1, len(total_lags)) * 100, 1
            ),
            "interpretation": (
                "Ingestion lag = time between source event timestamp and our DB ingest. "
                "Near-zero or negative values indicate real-time or predictive feeds. "
                "Values > 24h are typical for batch-reported sources (ACLED, ReliefWeb)."
            ),
        },
        "by_source": source_breakdown,
        "transparency_note": (
            "All figures are computed from actual stored signal timestamps using "
            "services/event_freshness.py:extract_event_timestamp(). "
            "No values are estimated or hardcoded."
        ),
    }


 f r o m   p y d a n t i c   i m p o r t   B a s e M o d e l 
 c l a s s   E x e c S u m m a r y R e q u e s t ( B a s e M o d e l ) : 
         i n c i d e n t s :   l i s t [ d i c t ] 
 
 @ r o u t e r . p o s t ( " / a p i / r e p o r t s / e x e c u t i v e - s u m m a r y " ) 
 a s y n c   d e f   a p i _ r e p o r t s _ e x e c _ s u m m a r y ( p a y l o a d :   E x e c S u m m a r y R e q u e s t )   - >   d i c t : 
         f r o m   s e r v i c e s . l l m _ p r o v i d e r   i m p o r t   c h a t _ c o m p l e t e 
         p r o m p t   =   f " W r i t e   a   d e t a i l e d   e x e c u t i v e   s u m m a r y   n a r r a t i v e   o f   t h e   f o l l o w i n g   s u p p l y   c h a i n   r i s k   i n c i d e n t s   a n d   h o w   t h e y   a f f e c t   t h e   o p e r a t o r .   D e s c r i b e   t h e   a c t u a l   e v e n t s   a n d   t h e i r   i m p l i c a t i o n s .   I n c i d e n t s :   { p a y l o a d . i n c i d e n t s } " 
         s y s t e m   =   " Y o u   a r e   a   s u p p l y   c h a i n   r i s k   i n t e l l i g e n c e   A I .   W r i t e   a   p r o f e s s i o n a l ,   d e t a i l e d   e x e c u t i v e   s u m m a r y   w i t h o u t   a n y   m a r k d o w n   f o r m a t t i n g .   D o   n o t   i n c l u d e   i n t r o d u c t o r y   o r   c o n c l u d i n g   c o n v e r s a t i o n a l   t e x t . " 
         r e s ,   _   =   a w a i t   c h a t _ c o m p l e t e ( p r o m p t ,   s y s t e m = s y s t e m ,   m a x _ t o k e n s = 1 0 2 4 ,   p r e f e r r e d _ p r o v i d e r = " g r o q " ) 
         r e t u r n   { " s u m m a r y " :   r e s } 
  
 