"""Resolving each quantity from the state machine.

The only module that talks to Home Assistant's state machine, and the only one
allowed to import from homeassistant.components.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.group.sensor import SensorGroup
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_TYPE,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State

from .const import (
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    DEFAULT_STATISTIC,
    DOMAIN,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
)
from .units import to_celsius, to_kilometers_per_hour

# Documented weather state attributes. Kept as literals rather than imported
# from homeassistant.components.weather: they are part of the entity's public
# state, so there is nothing to gain from a second internal import.
ATTR_TEMPERATURE = "temperature"
ATTR_TEMPERATURE_UNIT = "temperature_unit"
ATTR_HUMIDITY = "humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_WIND_SPEED_UNIT = "wind_speed_unit"

SOURCE_GROUP: Final = "group"
SOURCE_WEATHER: Final = "weather"


@dataclass(frozen=True)
class WeatherReading:
    """What a weather entity can offer, in canonical units."""

    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None


def _float(state: State, attribute: str) -> float | None:
    """Return a numeric attribute, or None if it is absent or not a number."""
    value = state.attributes.get(attribute)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_weather(hass: HomeAssistant, entity_id: str | None) -> WeatherReading:
    """Read the three quantities from a weather entity.

    Each quantity is independent: a weather entity without wind still provides
    temperature and humidity.
    """
    if entity_id is None:
        return WeatherReading()
    state = hass.states.get(entity_id)
    if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return WeatherReading()

    temperature = _float(state, ATTR_TEMPERATURE)
    wind_speed = _float(state, ATTR_WIND_SPEED)

    return WeatherReading(
        temperature=(
            None
            if temperature is None
            else to_celsius(temperature, state.attributes.get(ATTR_TEMPERATURE_UNIT))
        ),
        # Weather entities always express humidity in percent; there is no
        # humidity_unit attribute to read.
        humidity=_float(state, ATTR_HUMIDITY),
        wind_speed=(
            None
            if wind_speed is None
            else to_kilometers_per_hour(wind_speed, state.attributes.get(ATTR_WIND_SPEED_UNIT))
        ),
    )


class _Group:
    """A headless SensorGroup pinned to a canonical unit.

    Never added to hass: no entity registry entry, nothing in the UI. Home
    Assistant does the same for config-flow previews. Passing an explicit
    device class, state class and unit is not optional — each one makes core
    return early instead of negotiating from the members, which both converts
    every member before aggregation and avoids repair issues keyed on an
    entity_id this group does not have.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        config: Mapping[str, Any],
        device_class: SensorDeviceClass,
        unit: str,
    ) -> None:
        self.entity_ids: list[str] = list(config.get(CONF_ENTITIES, []))
        self._group = SensorGroup(
            hass,
            None,
            name,
            self.entity_ids,
            config.get(CONF_IGNORE_NON_NUMERIC, False),
            config.get(CONF_TYPE, DEFAULT_STATISTIC),
            unit,
            SensorStateClass.MEASUREMENT,
            device_class,
        )

    def value(self) -> float | None:
        """Return the aggregate in canonical units, or None."""
        if not self.entity_ids:
            return None
        self._group.async_update_group_state()
        if not self._group.available:
            return None
        native = self._group.native_value
        return None if native is None else float(native)


@dataclass(frozen=True)
class Quantity:
    """One resolved input and where it came from."""

    value: float | None = None
    source: str | None = None


@dataclass(frozen=True)
class ResolvedInputs:
    """The three inputs a formula needs."""

    temperature: Quantity
    humidity: Quantity
    wind_speed: Quantity


class InputResolver:
    """Resolves each quantity: its group first, the weather entity second."""

    def __init__(self, hass: HomeAssistant, options: Mapping[str, Any]) -> None:
        self._hass = hass
        self._weather_entity_id: str | None = options.get(CONF_WEATHER_ENTITY)
        name = options.get(CONF_NAME, DOMAIN)
        self._groups = {
            SECTION_TEMPERATURE: _Group(
                hass,
                f"{name} temperature",
                options.get(SECTION_TEMPERATURE, {}),
                SensorDeviceClass.TEMPERATURE,
                UnitOfTemperature.CELSIUS,
            ),
            SECTION_HUMIDITY: _Group(
                hass,
                f"{name} humidity",
                options.get(SECTION_HUMIDITY, {}),
                SensorDeviceClass.HUMIDITY,
                PERCENTAGE,
            ),
            SECTION_WIND_SPEED: _Group(
                hass,
                f"{name} wind speed",
                options.get(SECTION_WIND_SPEED, {}),
                SensorDeviceClass.WIND_SPEED,
                UnitOfSpeed.KILOMETERS_PER_HOUR,
            ),
        }

    @property
    def tracked_entity_ids(self) -> list[str]:
        """Every entity whose change should trigger a recomputation."""
        entity_ids = [
            entity_id for group in self._groups.values() for entity_id in group.entity_ids
        ]
        if self._weather_entity_id is not None:
            entity_ids.append(self._weather_entity_id)
        return entity_ids

    def resolve(self) -> ResolvedInputs:
        """Resolve the three quantities, each one independently."""
        weather = read_weather(self._hass, self._weather_entity_id)
        return ResolvedInputs(
            temperature=self._resolve(SECTION_TEMPERATURE, weather.temperature),
            humidity=self._resolve(SECTION_HUMIDITY, weather.humidity),
            wind_speed=self._resolve(SECTION_WIND_SPEED, weather.wind_speed),
        )

    def _resolve(self, section: str, fallback: float | None) -> Quantity:
        value = self._groups[section].value()
        if value is not None:
            return Quantity(value, SOURCE_GROUP)
        if fallback is not None:
            return Quantity(fallback, SOURCE_WEATHER)
        return Quantity()
