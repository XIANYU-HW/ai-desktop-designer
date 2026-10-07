"""Weather from Open-Meteo (free, no account), cached on disk so the desktop works offline."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import VERSION, env

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = f"OrbitDesktop/{VERSION} (+https://github.com/XIANYU-HW/orbit-desktop)"

# WMO weather code -> (kind, Chinese, English)
WMO = {
    0: ("clear", "晴", "Clear"),
    1: ("partly", "晴间少云", "Mostly clear"),
    2: ("partly", "多云", "Partly cloudy"),
    3: ("cloudy", "阴", "Overcast"),
    45: ("fog", "雾", "Fog"),
    48: ("fog", "雾凇", "Rime fog"),
    51: ("drizzle", "毛毛雨", "Light drizzle"),
    53: ("drizzle", "毛毛雨", "Drizzle"),
    55: ("drizzle", "密毛毛雨", "Dense drizzle"),
    56: ("drizzle", "冻毛毛雨", "Freezing drizzle"),
    57: ("drizzle", "冻毛毛雨", "Freezing drizzle"),
    61: ("rain", "小雨", "Light rain"),
    63: ("rain", "中雨", "Rain"),
    65: ("rain", "大雨", "Heavy rain"),
    66: ("rain", "冻雨", "Freezing rain"),
    67: ("rain", "冻雨", "Freezing rain"),
    71: ("snow", "小雪", "Light snow"),
    73: ("snow", "中雪", "Snow"),
    75: ("snow", "大雪", "Heavy snow"),
    77: ("snow", "米雪", "Snow grains"),
    80: ("rain", "阵雨", "Rain showers"),
    81: ("rain", "阵雨", "Rain showers"),
    82: ("rain", "强阵雨", "Violent showers"),
    85: ("snow", "阵雪", "Snow showers"),
    86: ("snow", "强阵雪", "Heavy snow showers"),
    95: ("storm", "雷雨", "Thunderstorm"),
    96: ("storm", "雷雨伴冰雹", "Thunderstorm with hail"),
    99: ("storm", "雷雨伴冰雹", "Thunderstorm with hail"),
}


def describe(code: Optional[int], lang: str) -> Dict[str, str]:
    kind, zh, en = WMO.get(int(code) if code is not None else -1, ("unknown", "未知", "Unknown"))
    return {"kind": kind, "condition": zh if lang.startswith("zh") else en}


def _get(url: str, params: Dict[str, Any], timeout: float = 8.0) -> Any:
    full = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https host
        return json.loads(response.read().decode("utf-8"))


def geocode(query: str, lang: str, count: int = 5) -> List[Dict[str, Any]]:
    data = _get(GEOCODE_URL, {"name": query, "count": count, "language": "zh" if lang.startswith("zh") else "en", "format": "json"})
    places = []
    for item in (data or {}).get("results") or []:
        places.append({
            "name": item.get("name"),
            "admin1": item.get("admin1"),
            "country": item.get("country"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "timezone": item.get("timezone") or "auto",
        })
    return places


def fetch(location: Dict[str, Any], units: str, lang: str) -> Dict[str, Any]:
    imperial = units == "imperial"
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": location.get("timezone") or "auto",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m",
        "hourly": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset,weather_code",
        "forecast_days": 2,
    }
    if imperial:
        params["temperature_unit"] = "fahrenheit"
        params["wind_speed_unit"] = "mph"
    raw = _get(FORECAST_URL, params)
    current = raw.get("current") or {}
    daily = raw.get("daily") or {}
    hourly = raw.get("hourly") or {}
    now_key = (current.get("time") or "")[:13]
    hours = []
    times = hourly.get("time") or []
    start = next((i for i, t in enumerate(times) if t[:13] >= now_key), 0)
    for index in range(start, min(start + 12, len(times))):
        code = (hourly.get("weather_code") or [None])[index]
        hours.append({
            "time": times[index],
            "temperature": (hourly.get("temperature_2m") or [None])[index],
            **describe(code, lang),
        })

    def first(key: str) -> Any:
        values = daily.get(key) or []
        return values[0] if values else None

    code = current.get("weather_code")
    return {
        "ok": True,
        "place": location.get("name"),
        "units": "imperial" if imperial else "metric",
        "temperature": current.get("temperature_2m"),
        "apparent": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind": current.get("wind_speed_10m"),
        "code": code,
        "is_day": bool(current.get("is_day", 1)),
        "high": first("temperature_2m_max"),
        "low": first("temperature_2m_min"),
        "sunrise": first("sunrise"),
        "sunset": first("sunset"),
        "utc_offset_seconds": raw.get("utc_offset_seconds"),
        "hourly": hours,
        **describe(code, lang),
    }


def get(config: Dict[str, Any], cache_path: Path, max_age: float = 1200) -> Dict[str, Any]:
    """Return weather for the configured place, using the cache when fresh or when offline."""
    lang = config.get("language") or "en"
    location = config.get("location")
    if not isinstance(location, dict) or "latitude" not in location:
        return {"ok": False, "reason": "no-location"}
    units = config.get("units") or "metric"
    cached = env.read_json(cache_path)
    key = f"{location.get('latitude')},{location.get('longitude')},{units},{lang}"
    if isinstance(cached, dict) and cached.get("key") == key and time.time() - cached.get("fetched", 0) < max_age:
        return cached["data"]
    try:
        data = fetch(location, units, lang)
        data["updated"] = time.time()
        env.write_json(cache_path, {"key": key, "fetched": time.time(), "data": data})
        return data
    except Exception as exc:  # offline or blocked: fall back to the last good reading
        if isinstance(cached, dict) and cached.get("key") == key:
            stale = dict(cached["data"])
            stale["stale"] = True
            return stale
        return {"ok": False, "reason": "unavailable", "detail": str(exc)[:200]}
