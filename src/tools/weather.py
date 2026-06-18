"""天气查询工具。"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from langchain_core.tools import tool


GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_API = "https://api.open-meteo.com/v1/forecast"
WEATHER_CODE_MAP = {
    0: "晴朗",
    1: "晴",
    2: "少云",
    3: "阴天",
    45: "有雾",
    48: "冻雾",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "大毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "冰粒",
    80: "小阵雨",
    81: "阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "弱雷暴夹冰雹",
    99: "强雷暴夹冰雹",
}


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.load(response)


def _format_location_name(query: str, location: dict) -> str:
    admin = location.get("admin1")
    country = location.get("country")
    parts = [query]
    if admin and admin != query:
        parts.append(admin)
    if country:
        parts.append(country)
    return " / ".join(parts)


@tool("weather_query")
def get_weather(location: str) -> str:
    """查询指定城市的当前天气，适合回答实时天气、温度和风速相关问题。"""
    try:
        geocoding_query = urllib.parse.urlencode(
            {"name": location, "count": 1, "language": "zh", "format": "json"}
        )
        geo_data = _fetch_json(f"{GEOCODING_API}?{geocoding_query}")
        results = geo_data.get("results") or []
        if not results:
            return f"未找到“{location}”的地理位置，请尝试提供更完整的城市名。"

        matched = results[0]
        forecast_query = urllib.parse.urlencode(
            {
                "latitude": matched["latitude"],
                "longitude": matched["longitude"],
                "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
                "timezone": matched.get("timezone") or "auto",
            }
        )
        forecast_data = _fetch_json(f"{FORECAST_API}?{forecast_query}")
        current = forecast_data.get("current") or {}
        current_units = forecast_data.get("current_units") or {}

        temperature = current.get("temperature_2m")
        apparent_temperature = current.get("apparent_temperature")
        weather_code = current.get("weather_code")
        wind_speed = current.get("wind_speed_10m")
        weather_text = WEATHER_CODE_MAP.get(weather_code, f"天气代码 {weather_code}")
        temperature_unit = current_units.get("temperature_2m", "°C")
        wind_unit = current_units.get("wind_speed_10m", "km/h")

        return (
            f"{_format_location_name(location, matched)} 当前天气：{weather_text}，"
            f"气温 {temperature}{temperature_unit}，"
            f"体感 {apparent_temperature}{temperature_unit}，"
            f"风速 {wind_speed}{wind_unit}。"
        )
    except Exception as exc:  # noqa: BLE001 - 工具需返回友好错误文案
        return f"天气查询失败：{exc}"
