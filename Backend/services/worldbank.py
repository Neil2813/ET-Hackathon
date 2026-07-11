"""
worldbank.py
============
World Bank Open Data API client — completely free, no API key required.

Fetches energy vulnerability and macroeconomic indicators for India and
key oil-exporting nations. Used to ground the Geopolitical RAG and
SPR scenario modeller with real, verifiable data rather than hardcoded constants.

Key Indicators Fetched
-----------------------
  EG.IMP.CONS.ZS  — Energy imports as % of total energy use (India's ~88% crude dependency)
  EG.USE.PCAP.KG.OE — Energy use per capita (kg of oil equivalent)
  NY.GDP.MKTP.CD  — GDP (current USD) — for economic impact scaling
  TM.VAL.FUEL.ZS.UN — Fuel imports as % of merchandise imports
  EN.ATM.CO2E.PC  — CO2 emissions per capita (ESG context)
"""
from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_WB_BASE = "https://api.worldbank.org/v2"
_WB_TIMEOUT = 10.0
_CACHE: dict[str, tuple[float, Any]] = {}   # key → (expiry_ts, data)
_CACHE_TTL = 86_400  # 24 hours — World Bank data changes annually

# India ISO code + key supplier nations
_INDIA = "IN"
_SUPPLIERS = ["SA", "IQ", "AE", "RU", "US", "NG", "AO"]   # Saudi, Iraq, UAE, Russia, USA, Nigeria, Angola

_INDICATORS = {
    "EG.IMP.CONS.ZS":   "energy_import_pct",          # Energy imports % of total use
    "TM.VAL.FUEL.ZS.UN": "fuel_import_pct_merch",      # Fuel imports % of merchandise imports
    "NY.GDP.MKTP.CD":   "gdp_usd",                     # GDP current USD
    "EG.USE.PCAP.KG.OE": "energy_use_per_capita_kgoe", # Energy use per capita
    "EN.ATM.CO2E.PC":   "co2_per_capita",              # CO2 per capita (ESG)
}


# ── Indian number formatting helpers ─────────────────────────────────────────

_INR_PER_USD: float = 84.0   # conservative fallback; updated at runtime


def _get_inr_rate() -> float:
    """
    Fetch live USD→INR nominal exchange rate from the World Bank API.
    Falls back to 87 if unavailable.
    """
    rows = _wb_get("country/IN/indicator/PA.NUS.FCRF")   # Official exchange rate (LCU per USD)
    val = _latest_value(rows)
    if val and 50.0 < val < 200.0:   # sanity check
        return float(val)
    return 87.0


def _get_ppp_rate() -> float:
    """
    Fetch India's PPP conversion factor from World Bank.
    Indicator: PA.NUS.PRVT.PP — LCU per international dollar (PPP).

    India's PPP rate is ~₹25-27/int'l $ vs ₹87 nominal.
    This means ₹1 in India buys ~3.3x more than ₹1 would at the nominal rate implies.

    Used to compute the REAL domestic economic impact of energy costs,
    separate from the foreign exchange outflow.
    """
    rows = _wb_get("country/IN/indicator/PA.NUS.PRVT.PP")
    val = _latest_value(rows)
    if val and 10.0 < val < 80.0:   # India PPP factor is typically 20-35
        return float(val)
    return 26.5   # World Bank 2022 fallback


def _fmt_inr(usd_value: float | None, rate: float = _INR_PER_USD) -> str:
    """
    Convert a USD value to a human-readable Indian Rupee string.
    Uses the Indian numbering system: lakh (1e5), crore (1e7), lakh crore (1e12).

    Examples
    --------
    3.38e12 USD → '₹2,83,920 crore'  (at ₹84/USD)
    1.06e12 USD → '₹89,040 crore'
    """
    if usd_value is None:
        return "N/A"
    inr = usd_value * rate
    if inr >= 1e12:                              # lakh crore (1 lakh crore = 10^12)
        return f"₹{inr / 1e12:.2f} lakh crore"
    elif inr >= 1e7:                             # crore
        return f"₹{inr / 1e7:,.0f} crore"
    elif inr >= 1e5:                             # lakh
        return f"₹{inr / 1e5:,.0f} lakh"
    else:
        return f"₹{inr:,.0f}"


def _wb_get(path: str, params: dict[str, str] | None = None) -> Any | None:
    """Synchronous World Bank API call (used from sync service context)."""
    p = {"format": "json", "per_page": "5", "mrv": "3", **(params or {})}
    query = urllib.parse.urlencode(p)
    url = f"{_WB_BASE}/{path}?{query}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SupplyShield/1.0"})
        with urllib.request.urlopen(req, timeout=_WB_TIMEOUT) as resp:
            raw = resp.read(500_000)
        payload = json.loads(raw.decode("utf-8"))
        # World Bank wraps data: [metadata_obj, data_array]
        if isinstance(payload, list) and len(payload) == 2:
            return payload[1]
        return payload
    except Exception as exc:
        logger.debug("[worldbank] GET %s failed: %s", url, exc)
        return None


def _cached(key: str, producer) -> Any | None:
    now = time.monotonic()
    if key in _CACHE and _CACHE[key][0] > now:
        return _CACHE[key][1]
    result = producer()
    if result is not None:
        _CACHE[key] = (now + _CACHE_TTL, result)
    return result


def _latest_value(rows: list[dict] | None) -> float | None:
    """Extract the most recent non-null value from a World Bank observation list."""
    if not rows:
        return None
    for row in sorted(rows, key=lambda r: str(r.get("date", "")), reverse=True):
        val = row.get("value")
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _latest_year(rows: list[dict] | None) -> str | None:
    if not rows:
        return None
    for row in sorted(rows, key=lambda r: str(r.get("date", "")), reverse=True):
        if row.get("value") is not None:
            return str(row.get("date", ""))
    return None


def fetch_india_energy_vulnerability() -> dict[str, Any]:
    """
    Returns India's energy vulnerability profile from World Bank Open Data.

    Returns two cost representations for every monetary figure:

      NOMINAL (forex)     — USD × official exchange rate (₹87/USD).
                            = What India actually pays in foreign currency.
                            Relevant for: BoP impact, forex reserve draw-down.

      PPP-ADJUSTED        — USD × PPP conversion factor (₹27/intl$).
                            = Real domestic purchasing-power equivalent.
                            Relevant for: consumer impact, inflation risk,
                            domestic policy cost-benefit analysis.

    Why they differ: ₹1 in India buys ~3x more than ₹1 at the nominal rate
    implies, because wages, land, services are far cheaper in India than the US.
    """
    def _fetch():
        out: dict[str, Any] = {"source": "World Bank Open Data", "fetched_at": datetime.now(timezone.utc).isoformat()}
        data_years: list[str] = []
        for indicator, field in _INDICATORS.items():
            rows = _wb_get(f"country/{_INDIA}/indicator/{indicator}")
            val = _latest_value(rows)
            year = _latest_year(rows)
            if val is not None:
                out[field] = round(val, 3)
                if year:
                    data_years.append(year)
        out["data_year"] = max(data_years) if data_years else "N/A"

        # ── Live exchange rates ──────────────────────────────────────────────
        inr_rate  = _get_inr_rate()   # nominal: ~₹87/USD (what India pays for imports)
        ppp_rate  = _get_ppp_rate()   # PPP: ~₹27/int'l$ (real domestic purchasing power)
        ppp_ratio = round(inr_rate / ppp_rate, 2) if ppp_rate else None

        out["usd_inr_rate"]   = round(inr_rate, 2)
        out["ppp_rate"]       = round(ppp_rate, 2)
        out["ppp_ratio"]      = ppp_ratio   # ~3.3 → India's money goes 3.3x further than nominal implies

        gdp_usd = out.get("gdp_usd")

        # ── GDP: nominal vs PPP ──────────────────────────────────────────────
        # Nominal GDP in INR = what India's economy is "worth" at forex rates
        out["gdp_inr_formatted"]     = _fmt_inr(gdp_usd, inr_rate)
        # PPP GDP: fetched directly (NY.GDP.MKTP.PP.CD = GDP at PPP in current intl $)
        gdp_ppp_rows = _wb_get("country/IN/indicator/NY.GDP.MKTP.PP.CD")
        gdp_ppp_usd  = _latest_value(gdp_ppp_rows)   # in international dollars
        out["gdp_ppp_usd"]           = round(gdp_ppp_usd, 0) if gdp_ppp_usd else None
        out["gdp_ppp_formatted"]     = _fmt_inr(gdp_ppp_usd, ppp_rate) if gdp_ppp_usd else "N/A"
        out["gdp_ppp_intl_formatted"] = (
            f"${gdp_ppp_usd / 1e12:.2f}T (intl $)" if gdp_ppp_usd else "N/A"
        )

        # ── Fuel import bill: nominal (forex burden) vs PPP (domestic impact) ─
        if gdp_usd and out.get("fuel_import_pct_merch"):
            total_imports_usd = gdp_usd * 0.22
            fuel_import_usd   = total_imports_usd * (out["fuel_import_pct_merch"] / 100.0)
            out["fuel_import_value_usd"]         = round(fuel_import_usd, 0)
            # Nominal = actual forex outflow
            out["fuel_import_value_inr"]         = _fmt_inr(fuel_import_usd, inr_rate)
            # PPP-adjusted = real domestic purchasing-power equivalent
            # (divide by PPP factor to get international $, then convert back)
            fuel_ppp_intl = fuel_import_usd * (ppp_rate / inr_rate)  # scale to int'l $
            out["fuel_import_value_ppp_inr"]     = _fmt_inr(fuel_ppp_intl, ppp_rate)
            out["fuel_import_value_usd_display"] = (
                f"${fuel_import_usd / 1e9:.1f}B"
            )
        else:
            out["fuel_import_value_inr"]     = "N/A"
            out["fuel_import_value_ppp_inr"] = "N/A"

        return out if len(out) > 4 else None

    return _cached("india_vulnerability", _fetch) or {
        # Curated static fallback — World Bank 2022 data
        "energy_import_pct":        38.5,
        "fuel_import_pct_merch":    27.2,
        "gdp_usd":                  3.385e12,
        "gdp_inr_formatted":        "\u20b9344.80 lakh crore",   # nominal ₹87/USD
        "gdp_ppp_formatted":        "\u20b9299.52 lakh crore",   # PPP ₹26.5/intl$
        "gdp_ppp_intl_formatted":   "$11.31T (intl $)",
        "usd_inr_rate":             87.0,
        "ppp_rate":                 26.5,
        "ppp_ratio":                3.28,
        "fuel_import_value_inr":    "\u20b923.93 lakh crore",    # nominal forex cost
        "fuel_import_value_ppp_inr":"\u20b97.29 lakh crore",    # PPP domestic impact
        "fuel_import_value_usd_display": "$27.5B",
        "energy_use_per_capita_kgoe": 637.0,
        "co2_per_capita":           1.89,
        "data_year":                "2022",
        "source":                   "World Bank Open Data (curated fallback)",
        "fetched_at":               datetime.now(timezone.utc).isoformat(),
    }


def fetch_supplier_gdp_profile() -> list[dict[str, Any]]:
    """
    Returns GDP and energy export profile for India's main oil suppliers.
    Used to assess how politically stable each alternative source is.
    """
    supplier_names = {
        "SA": "Saudi Arabia", "IQ": "Iraq", "AE": "United Arab Emirates",
        "RU": "Russia",       "US": "United States", "NG": "Nigeria", "AO": "Angola",
    }

    def _fetch():
        results: list[dict[str, Any]] = []
        for iso, name in supplier_names.items():
            gdp_rows = _wb_get(f"country/{iso}/indicator/NY.GDP.MKTP.CD")
            gdp = _latest_value(gdp_rows)
            fuel_rows = _wb_get(f"country/{iso}/indicator/TX.VAL.FUEL.ZS.UN")
            fuel_export_pct = _latest_value(fuel_rows)
            if gdp is not None:
                results.append({
                    "iso": iso,
                    "name": name,
                    "gdp_usd": round(gdp, 0) if gdp else None,
                    "fuel_export_pct": round(fuel_export_pct, 1) if fuel_export_pct else None,
                    "source": "World Bank",
                })
        return results or None

    return _cached("supplier_gdp", _fetch) or [
        {"iso": "SA", "name": "Saudi Arabia",       "gdp_usd": 1.062e12, "fuel_export_pct": 68.2, "source": "World Bank (fallback)"},
        {"iso": "IQ", "name": "Iraq",               "gdp_usd": 2.69e11,  "fuel_export_pct": 93.1, "source": "World Bank (fallback)"},
        {"iso": "AE", "name": "United Arab Emirates","gdp_usd": 4.99e11, "fuel_export_pct": 35.0, "source": "World Bank (fallback)"},
        {"iso": "RU", "name": "Russia",             "gdp_usd": 2.24e12,  "fuel_export_pct": 54.7, "source": "World Bank (fallback)"},
        {"iso": "US", "name": "United States",      "gdp_usd": 2.59e13,  "fuel_export_pct": 7.3,  "source": "World Bank (fallback)"},
        {"iso": "NG", "name": "Nigeria",            "gdp_usd": 4.72e11,  "fuel_export_pct": 81.6, "source": "World Bank (fallback)"},
        {"iso": "AO", "name": "Angola",             "gdp_usd": 9.23e10,  "fuel_export_pct": 94.4, "source": "World Bank (fallback)"},
    ]


def build_vulnerability_narrative(profile: dict[str, Any]) -> str:
    """Generate a human-readable risk narrative from the World Bank profile."""
    import_pct  = profile.get("energy_import_pct", 38.5)
    fuel_merch  = profile.get("fuel_import_pct_merch", 27.2)
    year        = profile.get("data_year", "N/A")
    inr_rate    = profile.get("usd_inr_rate", 87.0)
    ppp_rate    = profile.get("ppp_rate", 26.5)
    ppp_ratio   = profile.get("ppp_ratio", 3.28)

    gdp_nominal = profile.get("gdp_inr_formatted", "N/A")
    gdp_ppp_intl = profile.get("gdp_ppp_intl_formatted", "N/A")
    fuel_nominal = profile.get("fuel_import_value_inr", "N/A")
    fuel_ppp     = profile.get("fuel_import_value_ppp_inr", "N/A")
    fuel_usd     = profile.get("fuel_import_value_usd_display", "N/A")

    return (
        f"India's GDP ({year}): {gdp_nominal} at nominal forex (\u20b9{inr_rate:.0f}/USD), "
        f"or {gdp_ppp_intl} at PPP (\u20b9{ppp_rate:.0f}/int'l $). "
        f"PPP ratio {ppp_ratio:.1f}x means India's domestic purchasing power is {ppp_ratio:.1f}x "
        f"larger than the nominal exchange rate implies. "
        f"Annual fuel import bill: {fuel_usd} in foreign exchange (nominal: {fuel_nominal}); "
        f"real domestic purchasing-power equivalent: {fuel_ppp} (PPP-adjusted). "
        f"Energy import dependency: {import_pct:.1f}% of total energy, "
        f"{fuel_merch:.1f}% of merchandise imports. "
        f"A sustained Hormuz/Red Sea closure threatens ~40-45% of crude supply."
    )
