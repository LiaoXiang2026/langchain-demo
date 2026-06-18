"""天气工具与 Agent 集成测试。"""

from __future__ import annotations

import io
import json

import pytest


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def _json_response(payload: dict) -> _FakeResponse:
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def test_get_weather_returns_current_conditions(monkeypatch: pytest.MonkeyPatch):
    """能先地理编码，再返回格式化后的当前天气。"""
    from src.tools import weather as weather_module

    responses = iter(
        [
            _json_response(
                {
                    "results": [
                        {
                            "name": "Beijing",
                            "country": "China",
                            "admin1": "Beijing",
                            "latitude": 39.9042,
                            "longitude": 116.4074,
                            "timezone": "Asia/Shanghai",
                        }
                    ]
                }
            ),
            _json_response(
                {
                    "current_units": {
                        "temperature_2m": "°C",
                        "apparent_temperature": "°C",
                        "wind_speed_10m": "km/h",
                    },
                    "current": {
                        "temperature_2m": 30.2,
                        "apparent_temperature": 32.1,
                        "weather_code": 1,
                        "wind_speed_10m": 12.3,
                    },
                }
            ),
        ]
    )
    requested_urls: list[str] = []

    def fake_urlopen(url: str, timeout: int = 10):  # noqa: ARG001
        requested_urls.append(url)
        return next(responses)

    monkeypatch.setattr(weather_module.urllib.request, "urlopen", fake_urlopen)

    result = weather_module.get_weather.invoke({"location": "北京"})

    assert "北京" in result
    assert "China" in result
    assert "晴" in result
    assert "30.2°C" in result
    assert "体感 32.1°C" in result
    assert "风速 12.3km/h" in result
    assert any("geocoding-api.open-meteo.com" in url for url in requested_urls)
    assert any("api.open-meteo.com" in url for url in requested_urls)


def test_get_weather_returns_not_found_when_location_missing(monkeypatch: pytest.MonkeyPatch):
    """找不到地点时返回友好提示，不继续查天气。"""
    from src.tools import weather as weather_module

    requested_urls: list[str] = []

    def fake_urlopen(url: str, timeout: int = 10):  # noqa: ARG001
        requested_urls.append(url)
        return _json_response({"results": []})

    monkeypatch.setattr(weather_module.urllib.request, "urlopen", fake_urlopen)

    result = weather_module.get_weather.invoke({"location": "火星基地"})

    assert result == "未找到“火星基地”的地理位置，请尝试提供更完整的城市名。"
    assert len(requested_urls) == 1


def test_weather_tool_is_registered_in_agent(monkeypatch: pytest.MonkeyPatch):
    """Agent 应注册 weather_query 工具，并在系统提示词中提到它。"""
    from src.agent.agent import Agent, SYSTEM_PROMPT
    from src.config import settings

    monkeypatch.setattr(settings, "api_key", "test-key")

    agent = Agent()

    tool_names = [tool.name for tool in agent.tools]
    assert "weather_query" in tool_names
    assert "weather_query" in SYSTEM_PROMPT
