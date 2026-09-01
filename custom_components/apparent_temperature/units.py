"""Conversion to the canonical units used past this module.

Home Assistant's own converters do the arithmetic; hand-written constants would
drift from them and would not track new units.
"""

from __future__ import annotations

from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import SpeedConverter, TemperatureConverter


def to_celsius(value: float, unit: str | None) -> float | None:
    """Return the temperature in °C, or None if the unit is unusable."""
    if unit is None:
        return None
    try:
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    except (HomeAssistantError, ValueError):
        return None


def to_kilometers_per_hour(value: float, unit: str | None) -> float | None:
    """Return the speed in km/h, or None if the unit is unusable."""
    if unit is None:
        return None
    try:
        return SpeedConverter.convert(value, unit, UnitOfSpeed.KILOMETERS_PER_HOUR)
    except (HomeAssistantError, ValueError):
        return None
