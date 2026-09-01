"""The flow is one step with three collapsible sections."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_ENTITIES, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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

USER_INPUT = {
    CONF_NAME: "Garden",
    CONF_FORMULA: FORMULA_THRESHOLDS,
    CONF_WEATHER_ENTITY: "weather.home",
    SECTION_TEMPERATURE: {
        CONF_ENTITIES: ["sensor.garden_temperature"],
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
        CONF_TYPE: "max",
        CONF_IGNORE_NON_NUMERIC: True,
    },
}


async def test_full_flow_creates_an_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Garden"
    # Helper flows store everything in options; data stays empty.
    assert result["options"][CONF_FORMULA] == FORMULA_THRESHOLDS
    assert result["options"][SECTION_WIND_SPEED][CONF_TYPE] == "max"
    assert result["options"][SECTION_WIND_SPEED][CONF_IGNORE_NON_NUMERIC] is True


async def test_flow_accepts_an_empty_configuration(hass: HomeAssistant) -> None:
    # Everything is optional; a helper with nothing configured is valid and
    # simply reports unavailable.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Empty",
            CONF_FORMULA: FORMULA_THRESHOLDS,
            SECTION_TEMPERATURE: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
            SECTION_HUMIDITY: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
            SECTION_WIND_SPEED: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_non_numeric_sensors_are_ignored_by_default(hass: HomeAssistant) -> None:
    # A group is more useful missing one broken member than falling back whole.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Default",
            CONF_FORMULA: FORMULA_THRESHOLDS,
            SECTION_TEMPERATURE: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
            SECTION_HUMIDITY: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
            SECTION_WIND_SPEED: {CONF_ENTITIES: [], CONF_TYPE: "mean"},
        },
    )
    await hass.async_block_till_done()

    for sect in (SECTION_TEMPERATURE, SECTION_HUMIDITY, SECTION_WIND_SPEED):
        assert result["options"][sect][CONF_IGNORE_NON_NUMERIC] is True


async def test_options_flow_updates_the_formula(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, options=USER_INPUT, title="Garden")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    changed = {key: value for key, value in USER_INPUT.items() if key != CONF_NAME}
    changed[CONF_FORMULA] = FORMULA_STEADMAN
    result = await hass.config_entries.options.async_configure(result["flow_id"], changed)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FORMULA] == FORMULA_STEADMAN
    # The name is not part of the options flow's schema but must survive the
    # merge: sensor.py subscripts entry.options[CONF_NAME] unguarded, so a
    # dropped key would raise KeyError during the reload below.
    assert entry.options[CONF_NAME] == "Garden"
    assert hass.states.get("sensor.garden") is not None


async def test_translations_cover_every_flow_key() -> None:
    import json
    from pathlib import Path

    base = Path("custom_components/apparent_temperature")
    strings = json.loads((base / "strings.json").read_text())
    english = json.loads((base / "translations/en.json").read_text())
    french = json.loads((base / "translations/fr.json").read_text())

    def keys(node: object, prefix: str = "") -> set[str]:
        if not isinstance(node, dict):
            return {prefix}
        return {k for key, value in node.items() for k in keys(value, f"{prefix}.{key}")}

    assert keys(english) == keys(strings)
    assert keys(french) == keys(strings)
