"""Weather entities publish their own units; they are read, never assumed."""

from __future__ import annotations

import pytest
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.apparent_temperature.sources import read_weather


@pytest.fixture
def imperial_weather(hass: HomeAssistant) -> str:
    hass.states.async_set(
        "weather.home",
        "sunny",
        {
            "temperature": 68.0,
            "temperature_unit": UnitOfTemperature.FAHRENHEIT,
            "humidity": 55,
            "wind_speed": 10.0,
            "wind_speed_unit": UnitOfSpeed.MILES_PER_HOUR,
        },
    )
    return "weather.home"


async def test_reads_and_converts_every_quantity(
    hass: HomeAssistant, imperial_weather: str
) -> None:
    reading = read_weather(hass, imperial_weather)

    assert reading.temperature == pytest.approx(20.0)
    assert reading.humidity == pytest.approx(55.0)
    assert reading.wind_speed == pytest.approx(16.09344)


async def test_missing_entity_yields_an_empty_reading(hass: HomeAssistant) -> None:
    reading = read_weather(hass, "weather.absent")

    assert reading.temperature is None
    assert reading.humidity is None
    assert reading.wind_speed is None


async def test_no_weather_configured_yields_an_empty_reading(
    hass: HomeAssistant,
) -> None:
    reading = read_weather(hass, None)

    assert reading.temperature is None


async def test_quantities_are_independent(hass: HomeAssistant) -> None:
    # A weather entity without wind still provides temperature and humidity.
    hass.states.async_set(
        "weather.partial",
        "cloudy",
        {
            "temperature": 12.0,
            "temperature_unit": UnitOfTemperature.CELSIUS,
            "humidity": 80,
        },
    )

    reading = read_weather(hass, "weather.partial")

    assert reading.temperature == pytest.approx(12.0)
    assert reading.humidity == pytest.approx(80.0)
    assert reading.wind_speed is None


async def test_unavailable_weather_yields_an_empty_reading(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set("weather.home", "unavailable", {})

    reading = read_weather(hass, "weather.home")

    assert reading.temperature is None


async def test_non_numeric_attribute_is_discarded(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "weather.broken",
        "sunny",
        {"temperature": "warm", "temperature_unit": UnitOfTemperature.CELSIUS},
    )

    reading = read_weather(hass, "weather.broken")

    assert reading.temperature is None
