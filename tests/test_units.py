"""Only the weather-entity path needs these. Sensor groups are pinned to the
canonical unit at construction and convert their own members."""

from __future__ import annotations

import pytest
from homeassistant.const import UnitOfSpeed, UnitOfTemperature

from custom_components.apparent_temperature.units import (
    to_celsius,
    to_kilometers_per_hour,
)


def test_celsius_passes_through() -> None:
    assert to_celsius(21.0, UnitOfTemperature.CELSIUS) == pytest.approx(21.0)


def test_fahrenheit_converts() -> None:
    assert to_celsius(212.0, UnitOfTemperature.FAHRENHEIT) == pytest.approx(100.0)


def test_temperature_without_unit_is_discarded() -> None:
    assert to_celsius(21.0, None) is None


def test_temperature_with_a_nonsense_unit_is_discarded() -> None:
    assert to_celsius(21.0, "bananas") is None


def test_kilometers_per_hour_passes_through() -> None:
    assert to_kilometers_per_hour(12.0, UnitOfSpeed.KILOMETERS_PER_HOUR) == (pytest.approx(12.0))


def test_meters_per_second_converts() -> None:
    assert to_kilometers_per_hour(10.0, UnitOfSpeed.METERS_PER_SECOND) == (pytest.approx(36.0))


def test_miles_per_hour_converts() -> None:
    assert to_kilometers_per_hour(10.0, UnitOfSpeed.MILES_PER_HOUR) == (pytest.approx(16.09344))


def test_beaufort_converts_non_linearly() -> None:
    # 0.836 * 5**1.5 m/s = 9.348 m/s = 33.65 km/h. Proof that the conversion is
    # not a ratio, which is why aggregation must happen after it, never before.
    assert to_kilometers_per_hour(5.0, UnitOfSpeed.BEAUFORT) == (pytest.approx(33.65, abs=0.1))


def test_wind_speed_without_unit_is_discarded() -> None:
    assert to_kilometers_per_hour(12.0, None) is None
