"""End to end: options in, sensor state out."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.apparent_temperature.const import (
    CONF_FORMULA,
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    FORMULA_STEADMAN,
    FORMULA_THRESHOLDS,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
)


def _section(entities: list[str], statistic: str = "mean") -> dict[str, Any]:
    return {
        CONF_ENTITIES: entities,
        CONF_TYPE: statistic,
        CONF_IGNORE_NON_NUMERIC: False,
    }


async def _setup(hass: HomeAssistant, **overrides: Any) -> MockConfigEntry:
    options: dict[str, Any] = {
        CONF_NAME: "Garden feel",
        CONF_FORMULA: FORMULA_THRESHOLDS,
        SECTION_TEMPERATURE: _section([]),
        SECTION_HUMIDITY: _section([]),
        SECTION_WIND_SPEED: _section([]),
    }
    options.update(overrides)
    entry = MockConfigEntry(domain=DOMAIN, options=options, title=options[CONF_NAME])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _sensor(hass: HomeAssistant, entity_id: str, value: Any, unit: str) -> None:
    hass.states.async_set(
        entity_id,
        value,
        {"device_class": "temperature", "unit_of_measurement": unit},
    )


async def test_entity_id_comes_from_the_helper_name(hass: HomeAssistant) -> None:
    await _setup(hass)

    assert hass.states.get("sensor.garden_feel") is not None


async def test_unavailable_without_any_temperature_source(
    hass: HomeAssistant,
) -> None:
    await _setup(hass)

    assert hass.states.get("sensor.garden_feel").state == STATE_UNAVAILABLE


async def test_computes_humidex_above_15_degrees(hass: HomeAssistant) -> None:
    _sensor(hass, "sensor.t", 30.0, UnitOfTemperature.CELSIUS)
    hass.states.async_set(
        "sensor.h",
        40.2,
        {"device_class": "humidity", "unit_of_measurement": "%"},
    )

    await _setup(
        hass,
        **{
            SECTION_TEMPERATURE: _section(["sensor.t"]),
            SECTION_HUMIDITY: _section(["sensor.h"]),
        },
    )
    state = hass.states.get("sensor.garden_feel")

    assert float(state.state) == pytest.approx(34.0, abs=0.1)
    assert state.attributes["formula"] == "humidex"
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_exposes_its_sources_and_inputs(hass: HomeAssistant) -> None:
    _sensor(hass, "sensor.t", 5.0, UnitOfTemperature.CELSIUS)
    hass.states.async_set(
        "weather.home",
        "windy",
        {
            "wind_speed": 20.0,
            "wind_speed_unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        },
    )

    await _setup(
        hass,
        **{
            CONF_WEATHER_ENTITY: "weather.home",
            SECTION_TEMPERATURE: _section(["sensor.t"]),
        },
    )
    attributes = hass.states.get("sensor.garden_feel").attributes

    assert attributes["formula"] == "wind_chill"
    assert attributes["temperature_source"] == "group"
    assert attributes["wind_speed_source"] == "weather"
    assert attributes["humidity_source"] is None
    assert attributes["temperature"] == pytest.approx(5.0)
    assert attributes["wind_speed"] == pytest.approx(20.0)
    assert attributes["humidity"] is None
    # The raw index, unconverted: humidex and wind chill are not temperatures.
    assert attributes["index_value"] == pytest.approx(
        float(hass.states.get("sensor.garden_feel").state)
    )


async def test_recomputes_when_a_source_changes(hass: HomeAssistant) -> None:
    _sensor(hass, "sensor.t", 20.0, UnitOfTemperature.CELSIUS)
    await _setup(hass, **{SECTION_TEMPERATURE: _section(["sensor.t"])})
    assert float(hass.states.get("sensor.garden_feel").state) == pytest.approx(20.0)

    _sensor(hass, "sensor.t", 25.0, UnitOfTemperature.CELSIUS)
    await hass.async_block_till_done()

    assert float(hass.states.get("sensor.garden_feel").state) == pytest.approx(25.0)


async def test_reloads_when_options_change(hass: HomeAssistant) -> None:
    _sensor(hass, "sensor.t", 12.0, UnitOfTemperature.CELSIUS)
    hass.states.async_set(
        "sensor.h", 60.0, {"device_class": "humidity", "unit_of_measurement": "%"}
    )
    hass.states.async_set(
        "sensor.w",
        10.0,
        {
            "device_class": "wind_speed",
            "unit_of_measurement": UnitOfSpeed.KILOMETERS_PER_HOUR,
        },
    )
    entry = await _setup(
        hass,
        **{
            SECTION_TEMPERATURE: _section(["sensor.t"]),
            SECTION_HUMIDITY: _section(["sensor.h"]),
            SECTION_WIND_SPEED: _section(["sensor.w"]),
        },
    )
    # 12 °C sits in the dead band of the threshold mode.
    assert hass.states.get("sensor.garden_feel").attributes["formula"] == ("air_temperature")

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FORMULA: FORMULA_STEADMAN}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.garden_feel").attributes["formula"] == "steadman"


async def test_survives_a_zero_percent_humidity_reading(hass: HomeAssistant) -> None:
    # A humidity of 0 % used to reach math.log(0 / 100) and raise, which core
    # would swallow while leaving the sensor's last good value in place. It
    # must instead degrade to the air temperature and stay live.
    _sensor(hass, "sensor.t", 30.0, UnitOfTemperature.CELSIUS)
    hass.states.async_set(
        "sensor.h",
        "0",
        {"device_class": "humidity", "unit_of_measurement": "%"},
    )

    await _setup(
        hass,
        **{
            SECTION_TEMPERATURE: _section(["sensor.t"]),
            SECTION_HUMIDITY: _section(["sensor.h"]),
        },
    )
    state = hass.states.get("sensor.garden_feel")

    assert state.state != STATE_UNAVAILABLE
    assert float(state.state) == pytest.approx(30.0)
    assert state.attributes["formula"] == "air_temperature"
