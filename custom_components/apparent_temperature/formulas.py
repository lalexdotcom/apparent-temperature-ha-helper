"""Perceived-temperature formulas.

Pure computation: no Home Assistant import, no I/O, no state. Inputs are
canonical — temperature in °C, humidity in %, wind speed in km/h.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from .const import FORMULA_THRESHOLDS

# Values exposed in the sensor's `formula` attribute.
RESULT_AIR_TEMPERATURE: Final = "air_temperature"
RESULT_HUMIDEX: Final = "humidex"
RESULT_WIND_CHILL: Final = "wind_chill"
RESULT_STEADMAN: Final = "steadman"

# Météo-France publishes humidex above 15 °C and wind chill below 10 °C.
HUMIDEX_MIN_TEMPERATURE: Final = 15.0
WIND_CHILL_MAX_TEMPERATURE: Final = 10.0
# JAG/TI 2001 switches to a linear approximation below this wind speed.
WIND_CHILL_LOW_WIND_KMH: Final = 4.8

_KMH_TO_MS: Final = 1 / 3.6


@dataclass(frozen=True)
class FormulaResult:
    """A computed value and the formula that produced it."""

    value: float
    formula: str


def saturation_vapour_pressure(temperature_c: float) -> float:
    """Return saturation vapour pressure in hPa (Magnus)."""
    return 6.112 * math.exp(17.62 * temperature_c / (243.12 + temperature_c))


def vapour_pressure(temperature_c: float, humidity_pct: float) -> float:
    """Return actual vapour pressure in hPa."""
    return saturation_vapour_pressure(temperature_c) * humidity_pct / 100


def dew_point(temperature_c: float, humidity_pct: float) -> float:
    """Return the dew point in °C, inverting the Magnus form."""
    alpha = math.log(humidity_pct / 100) + 17.62 * temperature_c / (243.12 + temperature_c)
    return 243.12 * alpha / (17.62 - alpha)


def humidex(temperature_c: float, humidity_pct: float) -> float:
    """Return the humidex index."""
    dew_point_k = 273.15 + dew_point(temperature_c, humidity_pct)
    # Environment Canada's expression: 273.16 is the triple point, and the
    # dew point is converted with 273.15. The asymmetry is theirs, not a typo.
    pressure = 6.11 * math.exp(5417.7530 * (1 / 273.16 - 1 / dew_point_k))
    return temperature_c + 0.5555 * (pressure - 10)


def wind_chill(temperature_c: float, wind_speed_kmh: float) -> float:
    """Return the JAG/TI 2001 wind chill index."""
    if wind_speed_kmh <= 0:
        return temperature_c
    if wind_speed_kmh <= WIND_CHILL_LOW_WIND_KMH:
        return temperature_c + 0.2 * (0.1345 * temperature_c - 1.59) * wind_speed_kmh
    return 13.12 + 0.6215 * temperature_c + (0.3965 * temperature_c - 11.37) * wind_speed_kmh**0.16


def steadman(temperature_c: float, humidity_pct: float, wind_speed_kmh: float) -> float:
    """Return Steadman's apparent temperature.

    The only formula wanting m/s; every caller passes km/h.
    """
    pressure = vapour_pressure(temperature_c, humidity_pct)
    return temperature_c + 0.33 * pressure - 0.70 * (wind_speed_kmh * _KMH_TO_MS) - 4.00


def compute(
    mode: str,
    temperature_c: float,
    humidity_pct: float | None,
    wind_speed_kmh: float | None,
) -> FormulaResult:
    """Apply the configured mode, degrading to the air temperature.

    When a formula needs a quantity that could not be resolved, the air
    temperature is returned instead and the caller can see that in `formula`.
    """
    # A humidity outside (0, 100] is a broken sensor, not a valid reading (a
    # dead DHT-family sensor commonly reports 0 %). Treat it as unresolved,
    # same as None: degrading to the air temperature tells the truth, whereas
    # clamping it would feed math.log() with 0 (a domain error) or invent a
    # plausible-looking humidex from garbage.
    if humidity_pct is not None and not (0 < humidity_pct <= 100):
        humidity_pct = None

    if mode == FORMULA_THRESHOLDS:
        if temperature_c > HUMIDEX_MIN_TEMPERATURE and humidity_pct is not None:
            return FormulaResult(humidex(temperature_c, humidity_pct), RESULT_HUMIDEX)
        if temperature_c < WIND_CHILL_MAX_TEMPERATURE and wind_speed_kmh is not None:
            return FormulaResult(wind_chill(temperature_c, wind_speed_kmh), RESULT_WIND_CHILL)
        return FormulaResult(temperature_c, RESULT_AIR_TEMPERATURE)

    if humidity_pct is None or wind_speed_kmh is None:
        return FormulaResult(temperature_c, RESULT_AIR_TEMPERATURE)
    return FormulaResult(steadman(temperature_c, humidity_pct, wind_speed_kmh), RESULT_STEADMAN)
