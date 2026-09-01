"""Resolving each quantity from the state machine.

The only module that talks to Home Assistant's state machine, and the only one
allowed to import from homeassistant.components.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .units import to_celsius, to_kilometers_per_hour

# Documented weather state attributes. Kept as literals rather than imported
# from homeassistant.components.weather: they are part of the entity's public
# state, so there is nothing to gain from a second internal import.
ATTR_TEMPERATURE = "temperature"
ATTR_TEMPERATURE_UNIT = "temperature_unit"
ATTR_HUMIDITY = "humidity"
ATTR_WIND_SPEED = "wind_speed"
ATTR_WIND_SPEED_UNIT = "wind_speed_unit"


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
