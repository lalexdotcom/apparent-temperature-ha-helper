"""Aggregation is delegated to Home Assistant's own SensorGroup, pinned to the
canonical unit so every member converts before the statistic is applied."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TYPE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant

from custom_components.apparent_temperature.const import (
    CONF_FORMULA,
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    FORMULA_THRESHOLDS,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
)
from custom_components.apparent_temperature.sources import (
    SOURCE_GROUP,
    SOURCE_WEATHER,
    InputResolver,
)


def _options(**overrides: Any) -> dict[str, Any]:
    """Build a full options mapping, as the config flow produces it."""
    options: dict[str, Any] = {
        CONF_NAME: "Test",
        CONF_FORMULA: FORMULA_THRESHOLDS,
        SECTION_TEMPERATURE: {
            CONF_ENTITIES: [],
            CONF_TYPE: "mean",
            CONF_IGNORE_NON_NUMERIC: False,
        },
        SECTION_HUMIDITY: {
            CONF_ENTITIES: [],
            CONF_TYPE: "mean",
            CONF_IGNORE_NON_NUMERIC: False,
        },
        SECTION_WIND_SPEED: {
            CONF_ENTITIES: [],
            CONF_TYPE: "mean",
            CONF_IGNORE_NON_NUMERIC: False,
        },
    }
    options.update(overrides)
    return options


def _set_temperature(hass: HomeAssistant, entity_id: str, value: Any, unit: str) -> None:
    hass.states.async_set(
        entity_id,
        value,
        {"device_class": "temperature", "unit_of_measurement": unit},
    )


async def test_group_mixing_celsius_and_fahrenheit_averages_correctly(
    hass: HomeAssistant,
) -> None:
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)
    _set_temperature(hass, "sensor.b", 68.0, UnitOfTemperature.FAHRENHEIT)  # 20 °C

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a", "sensor.b"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                }
            }
        ),
    )

    temperature = resolver.resolve().temperature

    assert temperature.value == pytest.approx(15.0)
    assert temperature.source == SOURCE_GROUP


async def test_wind_group_mixing_beaufort_and_kmh_averages_in_kmh(
    hass: HomeAssistant,
) -> None:
    # Beaufort 5 is 33.65 km/h. Averaged with 66.35 km/h the answer is 50 km/h
    # only if each member is converted before the mean, not after.
    hass.states.async_set(
        "sensor.wind_a",
        5.0,
        {"device_class": "wind_speed", "unit_of_measurement": UnitOfSpeed.BEAUFORT},
    )
    hass.states.async_set(
        "sensor.wind_b",
        66.35,
        {
            "device_class": "wind_speed",
            "unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR,
        },
    )

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_WIND_SPEED: {
                    CONF_ENTITIES: ["sensor.wind_a", "sensor.wind_b"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                }
            }
        ),
    )

    assert resolver.resolve().wind_speed.value == pytest.approx(50.0, abs=0.2)


async def test_statistic_is_honoured(hass: HomeAssistant) -> None:
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)
    _set_temperature(hass, "sensor.b", 20.0, UnitOfTemperature.CELSIUS)

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a", "sensor.b"],
                    CONF_TYPE: "max",
                    CONF_IGNORE_NON_NUMERIC: False,
                }
            }
        ),
    )

    assert resolver.resolve().temperature.value == pytest.approx(20.0)


async def test_ignore_non_numeric_false_invalidates_the_group(
    hass: HomeAssistant,
) -> None:
    # Home Assistant's own rule, not ours: with the flag off, one broken member
    # takes the whole group down.
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)
    _set_temperature(hass, "sensor.b", "unknown", UnitOfTemperature.CELSIUS)

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a", "sensor.b"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                }
            }
        ),
    )

    assert resolver.resolve().temperature.value is None


async def test_ignore_non_numeric_true_keeps_the_valid_member(
    hass: HomeAssistant,
) -> None:
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)
    _set_temperature(hass, "sensor.b", "unknown", UnitOfTemperature.CELSIUS)

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a", "sensor.b"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: True,
                }
            }
        ),
    )

    assert resolver.resolve().temperature.value == pytest.approx(10.0)


async def test_weather_takes_over_per_quantity(hass: HomeAssistant) -> None:
    # The temperature group works; humidity has no group at all. Only humidity
    # falls back.
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)
    hass.states.async_set(
        "weather.home",
        "sunny",
        {
            "temperature": 30.0,
            "temperature_unit": UnitOfTemperature.CELSIUS,
            "humidity": 55,
        },
    )

    resolver = InputResolver(
        hass,
        _options(
            **{
                CONF_WEATHER_ENTITY: "weather.home",
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                },
            }
        ),
    )
    resolved = resolver.resolve()

    assert resolved.temperature.value == pytest.approx(10.0)
    assert resolved.temperature.source == SOURCE_GROUP
    assert resolved.humidity.value == pytest.approx(55.0)
    assert resolved.humidity.source == SOURCE_WEATHER


async def test_unavailable_group_falls_back_to_weather(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.a", "unavailable", {"device_class": "temperature"})
    hass.states.async_set(
        "weather.home",
        "sunny",
        {"temperature": 30.0, "temperature_unit": UnitOfTemperature.CELSIUS},
    )

    resolver = InputResolver(
        hass,
        _options(
            **{
                CONF_WEATHER_ENTITY: "weather.home",
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                },
            }
        ),
    )
    resolved = resolver.resolve()

    assert resolved.temperature.value == pytest.approx(30.0)
    assert resolved.temperature.source == SOURCE_WEATHER


async def test_nothing_configured_resolves_to_nothing(hass: HomeAssistant) -> None:
    resolved = InputResolver(hass, _options()).resolve()

    assert resolved.temperature.value is None
    assert resolved.temperature.source is None


async def test_tracked_entity_ids_cover_every_source(hass: HomeAssistant) -> None:
    resolver = InputResolver(
        hass,
        _options(
            **{
                CONF_WEATHER_ENTITY: "weather.home",
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                },
                SECTION_WIND_SPEED: {
                    CONF_ENTITIES: ["sensor.wind"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                },
            }
        ),
    )

    assert set(resolver.tracked_entity_ids) == {
        "sensor.a",
        "sensor.wind",
        "weather.home",
    }


async def test_groups_stay_out_of_the_entity_registry(hass: HomeAssistant) -> None:
    _set_temperature(hass, "sensor.a", 10.0, UnitOfTemperature.CELSIUS)

    resolver = InputResolver(
        hass,
        _options(
            **{
                SECTION_TEMPERATURE: {
                    CONF_ENTITIES: ["sensor.a"],
                    CONF_TYPE: "mean",
                    CONF_IGNORE_NON_NUMERIC: False,
                }
            }
        ),
    )
    resolver.resolve()
    await hass.async_block_till_done()

    # No group entity is added to hass, so no sensor.* appears beyond the source.
    assert hass.states.async_entity_ids("sensor") == ["sensor.a"]
