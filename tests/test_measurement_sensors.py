"""The three per-quantity measurement entities, and the device holding them."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TYPE,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.apparent_temperature.const import (
    CONF_FORMULA,
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    FORMULA_THRESHOLDS,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
)

MAIN = "sensor.garden_feel"
TEMPERATURE = "sensor.garden_feel_temperature"
HUMIDITY = "sensor.garden_feel_humidity"
WIND_SPEED = "sensor.garden_feel_wind_speed"
MEASUREMENTS = [TEMPERATURE, HUMIDITY, WIND_SPEED]


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


async def _enable_measurements(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Turn on the three entities the integration registers disabled."""
    registry = er.async_get(hass)
    for entity_id in MEASUREMENTS:
        registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str, value: Any, device_class: str, unit: str) -> None:
    hass.states.async_set(
        entity_id,
        value,
        {"device_class": device_class, "unit_of_measurement": unit},
    )


async def test_measurements_are_registered_but_disabled_by_default(
    hass: HomeAssistant,
) -> None:
    _state(hass, "sensor.t", 20.0, "temperature", UnitOfTemperature.CELSIUS)
    await _setup(hass, **{SECTION_TEMPERATURE: _section(["sensor.t"])})
    registry = er.async_get(hass)

    for entity_id in MEASUREMENTS:
        assert registry.async_get(entity_id).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        assert hass.states.get(entity_id) is None


async def test_temperature_publishes_the_group_aggregate_in_celsius(
    hass: HomeAssistant,
) -> None:
    # Fahrenheit in, Celsius out: the entity must expose what the formula ate.
    _state(hass, "sensor.t", 68.0, "temperature", UnitOfTemperature.FAHRENHEIT)
    entry = await _setup(hass, **{SECTION_TEMPERATURE: _section(["sensor.t"])})

    await _enable_measurements(hass, entry)
    state = hass.states.get(TEMPERATURE)

    assert float(state.state) == pytest.approx(20.0)
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["state_class"] == "measurement"
    assert state.attributes["source"] == "group"


async def test_humidity_and_wind_speed_publish_their_own_units(
    hass: HomeAssistant,
) -> None:
    _state(hass, "sensor.h", 55.0, "humidity", PERCENTAGE)
    _state(hass, "sensor.w", 10.0, "wind_speed", UnitOfSpeed.METERS_PER_SECOND)
    entry = await _setup(
        hass,
        **{
            SECTION_HUMIDITY: _section(["sensor.h"]),
            SECTION_WIND_SPEED: _section(["sensor.w"]),
        },
    )

    await _enable_measurements(hass, entry)
    humidity = hass.states.get(HUMIDITY)
    wind_speed = hass.states.get(WIND_SPEED)

    assert float(humidity.state) == pytest.approx(55.0)
    assert humidity.attributes["unit_of_measurement"] == PERCENTAGE
    assert float(wind_speed.state) == pytest.approx(36.0)
    assert wind_speed.attributes["unit_of_measurement"] == UnitOfSpeed.KILOMETERS_PER_HOUR


async def test_a_measurement_falling_back_to_weather_says_so(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "weather.home",
        "cloudy",
        {"humidity": 72.0},
    )
    entry = await _setup(hass, **{CONF_WEATHER_ENTITY: "weather.home"})

    await _enable_measurements(hass, entry)
    state = hass.states.get(HUMIDITY)

    assert float(state.state) == pytest.approx(72.0)
    assert state.attributes["source"] == "weather"


async def test_a_measurement_without_any_source_is_unavailable(hass: HomeAssistant) -> None:
    entry = await _setup(hass)

    await _enable_measurements(hass, entry)
    state = hass.states.get(WIND_SPEED)

    assert state.state == STATE_UNAVAILABLE
    assert "source" not in state.attributes


async def test_a_measurement_follows_its_source(hass: HomeAssistant) -> None:
    _state(hass, "sensor.t", 20.0, "temperature", UnitOfTemperature.CELSIUS)
    entry = await _setup(hass, **{SECTION_TEMPERATURE: _section(["sensor.t"])})
    await _enable_measurements(hass, entry)

    _state(hass, "sensor.t", 25.0, "temperature", UnitOfTemperature.CELSIUS)
    await hass.async_block_till_done()

    assert float(hass.states.get(TEMPERATURE).state) == pytest.approx(25.0)


async def test_every_entity_belongs_to_one_device_named_after_the_helper(
    hass: HomeAssistant,
) -> None:
    entry = await _setup(hass)
    await _enable_measurements(hass, entry)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, entry.entry_id)})
    registry = er.async_get(hass)

    assert device.name == "Garden feel"
    for entity_id in [MAIN, *MEASUREMENTS]:
        assert registry.async_get(entity_id).device_id == device.id


async def test_names_keep_the_helper_as_their_prefix(hass: HomeAssistant) -> None:
    _state(hass, "sensor.t", 20.0, "temperature", UnitOfTemperature.CELSIUS)
    entry = await _setup(hass, **{SECTION_TEMPERATURE: _section(["sensor.t"])})
    await _enable_measurements(hass, entry)

    # The main sensor's displayed name must survive the move to a device.
    assert hass.states.get(MAIN).attributes["friendly_name"] == "Garden feel"
    assert hass.states.get(TEMPERATURE).attributes["friendly_name"] == "Garden feel Temperature"
    assert hass.states.get(WIND_SPEED).attributes["friendly_name"] == "Garden feel Wind speed"
