"""Reference vectors come from the Environment Canada humidex and wind chill
tables, which are what Météo-France's published values follow."""

from __future__ import annotations

import pytest

from custom_components.apparent_temperature.const import (
    FORMULA_STEADMAN,
    FORMULA_THRESHOLDS,
)
from custom_components.apparent_temperature.formulas import (
    RESULT_AIR_TEMPERATURE,
    RESULT_HUMIDEX,
    RESULT_STEADMAN,
    RESULT_WIND_CHILL,
    compute,
    dew_point,
    humidex,
    steadman,
    wind_chill,
)


def test_dew_point_matches_magnus() -> None:
    # 30 °C at 40.2 % RH is a dew point of 15 °C.
    assert dew_point(30.0, 40.2) == pytest.approx(15.0, abs=0.05)


def test_humidex_matches_environment_canada() -> None:
    # 30 °C with a dew point of 15 °C is humidex 34.
    assert humidex(30.0, 40.2) == pytest.approx(34.0, abs=0.1)


def test_humidex_below_the_air_temperature_when_very_dry() -> None:
    # The index can fall under the air temperature; nothing clamps it.
    assert humidex(30.0, 10.0) < 30.0


@pytest.mark.parametrize(
    ("temperature", "wind", "expected"),
    [
        (-20.0, 30.0, -32.6),  # Environment Canada table: -33
        (0.0, 10.0, -3.3),  # Environment Canada table: -3
        (-10.0, 50.0, -21.8),
    ],
)
def test_wind_chill_matches_environment_canada(
    temperature: float, wind: float, expected: float
) -> None:
    assert wind_chill(temperature, wind) == pytest.approx(expected, abs=0.1)


def test_wind_chill_is_the_air_temperature_without_wind() -> None:
    assert wind_chill(-5.0, 0.0) == -5.0


def test_wind_chill_is_continuous_across_the_low_wind_switch() -> None:
    # The linear branch below 4.8 km/h and the power branch above it must not
    # produce a visible step at the boundary.
    below = wind_chill(0.0, 4.79)
    above = wind_chill(0.0, 4.81)
    assert below == pytest.approx(above, abs=0.1)


def test_steadman_subtracts_wind_and_adds_humidity() -> None:
    # 30 °C, 60 % RH, 7.2 km/h (2 m/s).
    assert steadman(30.0, 60.0, 7.2) == pytest.approx(33.0, abs=0.2)


def test_thresholds_uses_humidex_above_15_degrees() -> None:
    result = compute(FORMULA_THRESHOLDS, 25.0, 70.0, 5.0)
    assert result.formula == RESULT_HUMIDEX


def test_thresholds_uses_wind_chill_below_10_degrees() -> None:
    result = compute(FORMULA_THRESHOLDS, 5.0, 70.0, 20.0)
    assert result.formula == RESULT_WIND_CHILL


@pytest.mark.parametrize("temperature", [10.0, 12.5, 15.0])
def test_thresholds_returns_air_temperature_in_the_dead_band(
    temperature: float,
) -> None:
    result = compute(FORMULA_THRESHOLDS, temperature, 70.0, 20.0)
    assert result.formula == RESULT_AIR_TEMPERATURE
    assert result.value == temperature


def test_thresholds_degrades_when_humidity_is_missing() -> None:
    result = compute(FORMULA_THRESHOLDS, 25.0, None, 5.0)
    assert result.formula == RESULT_AIR_TEMPERATURE
    assert result.value == 25.0


def test_thresholds_degrades_when_wind_is_missing() -> None:
    result = compute(FORMULA_THRESHOLDS, 5.0, 70.0, None)
    assert result.formula == RESULT_AIR_TEMPERATURE
    assert result.value == 5.0


def test_steadman_mode_degrades_when_any_input_is_missing() -> None:
    # Steadman's -4.00 constant assumes both terms are present, so a partial
    # evaluation would be wrong rather than degraded.
    result = compute(FORMULA_STEADMAN, 25.0, None, 5.0)
    assert result.formula == RESULT_AIR_TEMPERATURE
    assert result.value == 25.0


def test_steadman_mode_ignores_the_thresholds() -> None:
    result = compute(FORMULA_STEADMAN, 12.0, 70.0, 5.0)
    assert result.formula == RESULT_STEADMAN
