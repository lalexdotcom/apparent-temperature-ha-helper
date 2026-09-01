# Apparent Temperature Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Home Assistant custom integration `apparent_temperature` that adds a helper producing one perceived-temperature sensor from three optional sensor groups plus a weather-entity fallback.

**Architecture:** Pure computation (`formulas.py`, `units.py`) sits underneath a resolution layer (`sources.py`) that is the only module talking to the state machine, and a thin entity (`sensor.py`) that orchestrates. Aggregation is delegated to Home Assistant's own `SensorGroup`, instantiated headless — never added to `hass` — with `device_class`, `state_class` and `unit_of_measurement` imposed so members are converted to canonical units before aggregation. The entity is event-driven via `async_track_state_change_event`; there is no coordinator and no polling.

**Tech Stack:** Python 3.13, Home Assistant custom component, `voluptuous` schemas via `SchemaConfigFlowHandler`, pytest with `pytest-homeassistant-custom-component`, ruff.

**Spec:** `docs/superpowers/specs/2026-08-31-apparent-temperature-helper-design.md`

## Global Constraints

- Domain is `apparent_temperature`. It is frozen: it appears in entity ids and config entries.
- Python `>=3.13`, matching Home Assistant's own floor.
- Canonical units, everywhere past `units.py`: temperature °C, humidity %, wind speed km/h. Steadman converts km/h to m/s internally.
- Fixed thresholds: humidex above 15 °C, wind chill below 10 °C, air temperature between them; wind chill switches formula at 4.8 km/h.
- Statistics offered: `min`, `max`, `mean`, `median`, `last`. Never `range`, `sum`, `stdev`, `product`, `first_available`.
- Every source group is optional. The sensor is `unavailable` only when temperature cannot be resolved from any source.
- Fallback is per quantity, independently: group first, weather entity second, absent third.
- Imports from `homeassistant.components.*` are confined to `sources.py`. Everything else uses `homeassistant.helpers`, `homeassistant.const`, `homeassistant.core`, `homeassistant.util`.
- Chat with the user is French; all code, comments, commit messages and documentation are English.
- Run `.venv/bin/ruff format` and `.venv/bin/ruff check --fix` on touched Python files before every commit.

---

### Task 1: Test harness and integration skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `custom_components/apparent_temperature/__init__.py`
- Create: `custom_components/apparent_temperature/const.py`
- Create: `custom_components/apparent_temperature/manifest.json`
- Create: `hacs.json`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Test: `tests/test_manifest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: every constant later tasks import from `const.py` — `DOMAIN`, `CONF_WEATHER_ENTITY`, `CONF_FORMULA`, `CONF_IGNORE_NON_NUMERIC`, `SECTION_TEMPERATURE`, `SECTION_HUMIDITY`, `SECTION_WIND_SPEED`, `FORMULA_THRESHOLDS`, `FORMULA_STEADMAN`, `FORMULA_MODES`, `STATISTIC_TYPES`, `DEFAULT_STATISTIC`.

- [ ] **Step 1: Add the test dependencies**

Replace the `[dependency-groups]` block in `pyproject.toml` with:

```toml
[dependency-groups]
dev = [
    "ruff>=0.14",
    "pytest-homeassistant-custom-component>=0.13",
]
```

`pytest-homeassistant-custom-component` pulls in `pytest`, `pytest-asyncio` and a pinned `homeassistant`, so pytest is no longer declared on its own — a second pin would fight the one it needs.

Then extend the pytest configuration in the same file:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Install them**

Run: `uv sync`
Expected: `homeassistant`, `pytest`, `pytest-homeassistant-custom-component` installed into `.venv`.

- [ ] **Step 3: Write the failing test**

Create `tests/__init__.py` as an empty file, then `tests/test_manifest.py`:

```python
"""The manifest is what Home Assistant reads before any of our code runs."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST = Path("custom_components/apparent_temperature/manifest.json")


def test_manifest_declares_a_loadable_helper() -> None:
    manifest = json.loads(MANIFEST.read_text())

    assert manifest["domain"] == "apparent_temperature"
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "helper"
    assert manifest["iot_class"] == "calculated"
    # Declared because sources.py imports homeassistant.components.group.sensor.
    assert manifest["dependencies"] == ["group"]
    # Custom components are rejected by HACS and by HA without a version.
    assert manifest["version"]
```

- [ ] **Step 4: Run it to verify it fails**

Run: `.venv/bin/pytest tests/test_manifest.py -v`
Expected: FAIL with `FileNotFoundError`.

- [ ] **Step 5: Create the manifest**

`custom_components/apparent_temperature/manifest.json`:

```json
{
  "domain": "apparent_temperature",
  "name": "Apparent temperature",
  "codeowners": ["@lalexdotcom"],
  "config_flow": true,
  "dependencies": ["group"],
  "documentation": "https://github.com/lalexdotcom/apparent-temperature-ha-helper",
  "integration_type": "helper",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/lalexdotcom/apparent-temperature-ha-helper/issues",
  "version": "0.1.0"
}
```

- [ ] **Step 6: Run it to verify it passes**

Run: `.venv/bin/pytest tests/test_manifest.py -v`
Expected: PASS.

- [ ] **Step 7: Write the constants**

`custom_components/apparent_temperature/const.py`:

```python
"""Constants for the apparent temperature helper."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "apparent_temperature"

# Configuration keys. CONF_NAME, CONF_ENTITIES and CONF_TYPE come from
# homeassistant.const; only the keys HA has no constant for live here.
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_FORMULA: Final = "formula"
# Same literal as homeassistant.components.group.const, repeated rather than
# imported: SensorGroup reads it from a plain dict, so a second import of HA
# internals would buy nothing.
CONF_IGNORE_NON_NUMERIC: Final = "ignore_non_numeric"

# Collapsible sections of the config flow, and the keys their options nest under.
SECTION_TEMPERATURE: Final = "temperature"
SECTION_HUMIDITY: Final = "humidity"
SECTION_WIND_SPEED: Final = "wind_speed"

# Formula modes offered by the config flow.
FORMULA_THRESHOLDS: Final = "thresholds"
FORMULA_STEADMAN: Final = "steadman"
FORMULA_MODES: Final = [FORMULA_THRESHOLDS, FORMULA_STEADMAN]

# Subset of SensorGroup's statistics. range, sum, stdev, product and
# first_available are deliberately absent: the first two are meaningless as
# comfort-formula inputs and do not survive a unit change, the rest are noise.
STATISTIC_TYPES: Final = ["min", "max", "mean", "median", "last"]
DEFAULT_STATISTIC: Final = "mean"
```

- [ ] **Step 8: Write the package entry point**

`custom_components/apparent_temperature/__init__.py`:

```python
"""The apparent temperature helper integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a helper from a config entry."""
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rebuild the helper when its options change.

    A full reload is the right answer here: changing the entity lists changes
    which sensor groups exist and which entities are tracked, so patching the
    live entity would be more code for the same result.
    """
    await hass.config_entries.async_reload(entry.entry_id)
```

- [ ] **Step 9: Write the test fixtures**

`tests/conftest.py`:

```python
"""Shared fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Load custom_components/ in every test.

    Home Assistant ignores custom components in tests unless this fixture is
    requested, and forgetting it produces an "Integration not found" error that
    looks like a bug in the integration rather than in the test setup.
    """
    yield
```

- [ ] **Step 10: Create the HACS descriptor**

`hacs.json`:

```json
{
  "name": "Apparent temperature",
  "homeassistant": "2025.2.0",
  "render_readme": true
}
```

- [ ] **Step 11: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: PASS.

- [ ] **Step 12: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add pyproject.toml uv.lock hacs.json custom_components tests
git commit -m "Add apparent temperature integration skeleton and test harness"
```

---

### Task 2: Formulas

**Files:**
- Create: `custom_components/apparent_temperature/formulas.py`
- Test: `tests/test_formulas.py`

**Interfaces:**
- Consumes: `FORMULA_THRESHOLDS`, `FORMULA_STEADMAN` from `const.py`.
- Produces:
  - `FormulaResult(value: float, formula: str)` — frozen dataclass.
  - `RESULT_AIR_TEMPERATURE`, `RESULT_HUMIDEX`, `RESULT_WIND_CHILL`, `RESULT_STEADMAN` — the strings the entity exposes in its `formula` attribute.
  - `saturation_vapour_pressure(temperature_c: float) -> float`
  - `dew_point(temperature_c: float, humidity_pct: float) -> float`
  - `vapour_pressure(temperature_c: float, humidity_pct: float) -> float`
  - `humidex(temperature_c: float, humidity_pct: float) -> float`
  - `wind_chill(temperature_c: float, wind_speed_kmh: float) -> float`
  - `steadman(temperature_c: float, humidity_pct: float, wind_speed_kmh: float) -> float`
  - `compute(mode: str, temperature_c: float, humidity_pct: float | None, wind_speed_kmh: float | None) -> FormulaResult`

This module is pure. It never imports `homeassistant`.

- [ ] **Step 1: Write the failing tests**

`tests/test_formulas.py`:

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_formulas.py -v`
Expected: FAIL with `ModuleNotFoundError: custom_components.apparent_temperature.formulas`.

- [ ] **Step 3: Write the implementation**

`custom_components/apparent_temperature/formulas.py`:

```python
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
    alpha = math.log(humidity_pct / 100) + 17.62 * temperature_c / (
        243.12 + temperature_c
    )
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
    return (
        13.12
        + 0.6215 * temperature_c
        + (0.3965 * temperature_c - 11.37) * wind_speed_kmh**0.16
    )


def steadman(
    temperature_c: float, humidity_pct: float, wind_speed_kmh: float
) -> float:
    """Return Steadman's apparent temperature.

    The only formula wanting m/s; every caller passes km/h.
    """
    pressure = vapour_pressure(temperature_c, humidity_pct)
    return (
        temperature_c
        + 0.33 * pressure
        - 0.70 * (wind_speed_kmh * _KMH_TO_MS)
        - 4.00
    )


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
    if mode == FORMULA_THRESHOLDS:
        if temperature_c > HUMIDEX_MIN_TEMPERATURE and humidity_pct is not None:
            return FormulaResult(humidex(temperature_c, humidity_pct), RESULT_HUMIDEX)
        if temperature_c < WIND_CHILL_MAX_TEMPERATURE and wind_speed_kmh is not None:
            return FormulaResult(
                wind_chill(temperature_c, wind_speed_kmh), RESULT_WIND_CHILL
            )
        return FormulaResult(temperature_c, RESULT_AIR_TEMPERATURE)

    if humidity_pct is None or wind_speed_kmh is None:
        return FormulaResult(temperature_c, RESULT_AIR_TEMPERATURE)
    return FormulaResult(
        steadman(temperature_c, humidity_pct, wind_speed_kmh), RESULT_STEADMAN
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_formulas.py -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/formulas.py tests/test_formulas.py
git commit -m "Add humidex, wind chill and Steadman formulas"
```

---

### Task 3: Unit normalisation

**Files:**
- Create: `custom_components/apparent_temperature/units.py`
- Test: `tests/test_units.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `to_celsius(value: float, unit: str | None) -> float | None`
  - `to_kilometers_per_hour(value: float, unit: str | None) -> float | None`

Both return `None` when the unit is missing or not convertible, which is how a
malformed weather entity is discarded rather than trusted.

- [ ] **Step 1: Write the failing tests**

`tests/test_units.py`:

```python
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
    assert to_kilometers_per_hour(12.0, UnitOfSpeed.KILOMETERS_PER_HOUR) == (
        pytest.approx(12.0)
    )


def test_meters_per_second_converts() -> None:
    assert to_kilometers_per_hour(10.0, UnitOfSpeed.METERS_PER_SECOND) == (
        pytest.approx(36.0)
    )


def test_miles_per_hour_converts() -> None:
    assert to_kilometers_per_hour(10.0, UnitOfSpeed.MILES_PER_HOUR) == (
        pytest.approx(16.09344)
    )


def test_beaufort_converts_non_linearly() -> None:
    # 0.836 * 5**1.5 m/s = 9.348 m/s = 33.65 km/h. Proof that the conversion is
    # not a ratio, which is why aggregation must happen after it, never before.
    assert to_kilometers_per_hour(5.0, UnitOfSpeed.BEAUFORT) == (
        pytest.approx(33.65, abs=0.1)
    )


def test_wind_speed_without_unit_is_discarded() -> None:
    assert to_kilometers_per_hour(12.0, None) is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_units.py -v`
Expected: FAIL with `ModuleNotFoundError: custom_components.apparent_temperature.units`.

- [ ] **Step 3: Write the implementation**

`custom_components/apparent_temperature/units.py`:

```python
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
```

Home Assistant's converters raise `HomeAssistantError` for a unit they do not know; `ValueError` covers the non-numeric case.

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_units.py -v`
Expected: PASS, 9 tests.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/units.py tests/test_units.py
git commit -m "Add canonical unit conversion for weather readings"
```

---

### Task 4: Weather entity reading

**Files:**
- Create: `custom_components/apparent_temperature/sources.py`
- Test: `tests/test_weather_source.py`

**Interfaces:**
- Consumes: `to_celsius`, `to_kilometers_per_hour` from `units.py`.
- Produces:
  - `WeatherReading(temperature: float | None, humidity: float | None, wind_speed: float | None)` — frozen dataclass, canonical units.
  - `read_weather(hass: HomeAssistant, entity_id: str | None) -> WeatherReading`

`sources.py` grows a second half in Task 5; this task writes only the weather part.

- [ ] **Step 1: Write the failing tests**

`tests/test_weather_source.py`:

```python
"""Weather entities publish their own units; they are read, never assumed."""

from __future__ import annotations

import pytest
from homeassistant.const import UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant

from custom_components.apparent_temperature.sources import read_weather


@pytest.fixture
def imperial_weather(hass: HomeAssistant) -> str:
    hass.states.async_set(
        "weather.home",
        "sunny",
        {
            "temperature": 68.0,
            "temperature_unit": UnitOfTemperature.FAHRENHEIT,
            "humidity": 55,
            "wind_speed": 10.0,
            "wind_speed_unit": UnitOfSpeed.MILES_PER_HOUR,
        },
    )
    return "weather.home"


async def test_reads_and_converts_every_quantity(
    hass: HomeAssistant, imperial_weather: str
) -> None:
    reading = read_weather(hass, imperial_weather)

    assert reading.temperature == pytest.approx(20.0)
    assert reading.humidity == pytest.approx(55.0)
    assert reading.wind_speed == pytest.approx(16.09344)


async def test_missing_entity_yields_an_empty_reading(hass: HomeAssistant) -> None:
    reading = read_weather(hass, "weather.absent")

    assert reading.temperature is None
    assert reading.humidity is None
    assert reading.wind_speed is None


async def test_no_weather_configured_yields_an_empty_reading(
    hass: HomeAssistant,
) -> None:
    reading = read_weather(hass, None)

    assert reading.temperature is None


async def test_quantities_are_independent(hass: HomeAssistant) -> None:
    # A weather entity without wind still provides temperature and humidity.
    hass.states.async_set(
        "weather.partial",
        "cloudy",
        {
            "temperature": 12.0,
            "temperature_unit": UnitOfTemperature.CELSIUS,
            "humidity": 80,
        },
    )

    reading = read_weather(hass, "weather.partial")

    assert reading.temperature == pytest.approx(12.0)
    assert reading.humidity == pytest.approx(80.0)
    assert reading.wind_speed is None


async def test_unavailable_weather_yields_an_empty_reading(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set("weather.home", "unavailable", {})

    reading = read_weather(hass, "weather.home")

    assert reading.temperature is None


async def test_non_numeric_attribute_is_discarded(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "weather.broken",
        "sunny",
        {"temperature": "warm", "temperature_unit": UnitOfTemperature.CELSIUS},
    )

    reading = read_weather(hass, "weather.broken")

    assert reading.temperature is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_weather_source.py -v`
Expected: FAIL with `ImportError: cannot import name 'read_weather'`.

- [ ] **Step 3: Write the implementation**

`custom_components/apparent_temperature/sources.py`:

```python
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
            else to_celsius(
                temperature, state.attributes.get(ATTR_TEMPERATURE_UNIT)
            )
        ),
        # Weather entities always express humidity in percent; there is no
        # humidity_unit attribute to read.
        humidity=_float(state, ATTR_HUMIDITY),
        wind_speed=(
            None
            if wind_speed is None
            else to_kilometers_per_hour(
                wind_speed, state.attributes.get(ATTR_WIND_SPEED_UNIT)
            )
        ),
    )
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_weather_source.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/sources.py tests/test_weather_source.py
git commit -m "Read weather entity quantities in canonical units"
```

---

### Task 5: Headless sensor groups and input resolution

**Files:**
- Modify: `custom_components/apparent_temperature/sources.py`
- Test: `tests/test_group_source.py`
- Test: `tests/test_ha_internals.py`

**Interfaces:**
- Consumes: `WeatherReading`, `read_weather` from Task 4; `SECTION_TEMPERATURE`, `SECTION_HUMIDITY`, `SECTION_WIND_SPEED`, `CONF_IGNORE_NON_NUMERIC`, `CONF_WEATHER_ENTITY`, `DEFAULT_STATISTIC`, `DOMAIN` from `const.py`.
- Produces:
  - `SOURCE_GROUP = "group"`, `SOURCE_WEATHER = "weather"`
  - `Quantity(value: float | None, source: str | None)` — frozen dataclass.
  - `ResolvedInputs(temperature: Quantity, humidity: Quantity, wind_speed: Quantity)` — frozen dataclass.
  - `InputResolver(hass: HomeAssistant, options: Mapping[str, Any])` with
    `tracked_entity_ids: list[str]` (property) and `resolve() -> ResolvedInputs`.

- [ ] **Step 1: Write the failing tests**

`tests/test_group_source.py`:

```python
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


def _set_temperature(
    hass: HomeAssistant, entity_id: str, value: Any, unit: str
) -> None:
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
    hass.states.async_set(
        "sensor.a", "unavailable", {"device_class": "temperature"}
    )
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
```

`tests/test_ha_internals.py`:

```python
"""Pins the Home Assistant internals this integration depends on.

sources.py builds SensorGroup by hand. Home Assistant makes no API promise for
homeassistant.components.*, so this file exists to fail loudly on the next core
refactor instead of letting the helper drift silently in production.
"""

from __future__ import annotations

import inspect

import pytest
from homeassistant.components.group.sensor import SensorGroup
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant


def test_constructor_signature_is_unchanged() -> None:
    parameters = list(inspect.signature(SensorGroup.__init__).parameters)

    assert parameters == [
        "self",
        "hass",
        "unique_id",
        "name",
        "entity_ids",
        "ignore_non_numeric",
        "sensor_type",
        "unit_of_measurement",
        "state_class",
        "device_class",
    ]


async def test_configured_unit_wins_over_member_units(hass: HomeAssistant) -> None:
    """A configured unit must short-circuit unit negotiation.

    This is what lets members be converted before aggregation. If core ever
    stops honouring it, the helper's means become wrong for non-linear units.
    """
    hass.states.async_set(
        "sensor.a",
        68.0,
        {
            "device_class": "temperature",
            "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
        },
    )

    group = SensorGroup(
        hass,
        None,
        "pin",
        ["sensor.a"],
        False,
        "mean",
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
    )
    group.async_update_group_state()

    assert group.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert group.native_value == pytest.approx(20.0)
    assert group.available is True


async def test_update_works_without_being_added_to_hass(
    hass: HomeAssistant,
) -> None:
    """The group is never added to hass, so entity_id stays None.

    Core logs a warning naming self.entity_id on a bad member; that must not
    raise. It also must not open a repair issue, which is why the constructor
    receives an explicit device class, state class and unit.
    """
    hass.states.async_set(
        "sensor.broken",
        "not a number",
        {
            "device_class": "temperature",
            "unit_of_measurement": UnitOfTemperature.CELSIUS,
        },
    )

    group = SensorGroup(
        hass,
        None,
        "pin",
        ["sensor.broken"],
        False,
        "mean",
        UnitOfTemperature.CELSIUS,
        SensorStateClass.MEASUREMENT,
        SensorDeviceClass.TEMPERATURE,
    )
    group.async_update_group_state()

    assert group.native_value is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_group_source.py tests/test_ha_internals.py -v`
Expected: `test_group_source.py` FAILs with `ImportError: cannot import name 'InputResolver'`; `test_ha_internals.py` should already PASS — it pins core, not our code. If it fails, stop: the assumption the design rests on is broken, and the plan needs revisiting before any further task.

- [ ] **Step 3: Add the group wrapper and resolver**

Append to `custom_components/apparent_temperature/sources.py`:

```python
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
            entity_id
            for group in self._groups.values()
            for entity_id in group.entity_ids
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
```

Extend the module's imports to:

```python
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
```

and add the two source markers next to the weather attribute constants:

```python
SOURCE_GROUP: Final = "group"
SOURCE_WEATHER: Final = "weather"
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_group_source.py tests/test_ha_internals.py -v`
Expected: PASS, 13 tests.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/sources.py tests/test_group_source.py tests/test_ha_internals.py
git commit -m "Resolve inputs from headless sensor groups with weather fallback"
```

---

### Task 6: Config flow and translations

**Files:**
- Create: `custom_components/apparent_temperature/config_flow.py`
- Create: `custom_components/apparent_temperature/strings.json`
- Create: `custom_components/apparent_temperature/translations/en.json`
- Create: `custom_components/apparent_temperature/translations/fr.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: every constant from `const.py`.
- Produces: `ApparentTemperatureConfigFlowHandler`, registered for `DOMAIN`. The options mapping it writes is exactly what `InputResolver` consumes: `name`, `formula`, optional `weather_entity`, and the three sections each holding `entities`, `type`, `ignore_non_numeric`.

- [ ] **Step 1: Write the failing tests**

`tests/test_config_flow.py`:

```python
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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
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


async def test_options_flow_updates_the_formula(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, options=USER_INPUT, title="Garden")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    changed = {key: value for key, value in USER_INPUT.items() if key != CONF_NAME}
    changed[CONF_FORMULA] = FORMULA_STEADMAN
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], changed
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_FORMULA] == FORMULA_STEADMAN
    # The name is not part of the options flow and must survive it.
    assert entry.title == "Garden"


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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: FAIL — the flow is not registered, so `async_init` raises `UnknownHandler`.

- [ ] **Step 3: Write the flow**

`custom_components/apparent_temperature/config_flow.py`:

```python
"""Config and options flow for the apparent temperature helper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_ENTITIES, CONF_NAME, CONF_TYPE
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
)

from .const import (
    CONF_FORMULA,
    CONF_IGNORE_NON_NUMERIC,
    CONF_WEATHER_ENTITY,
    DEFAULT_STATISTIC,
    DOMAIN,
    FORMULA_MODES,
    FORMULA_THRESHOLDS,
    SECTION_HUMIDITY,
    SECTION_TEMPERATURE,
    SECTION_WIND_SPEED,
    STATISTIC_TYPES,
)


def _group_schema(device_class: SensorDeviceClass) -> vol.Schema:
    """Build the three fields every source group shares.

    The entity selector filters on the device class, which is also what makes
    unit conversion possible downstream: a sensor with no device class cannot
    be converted, so hiding it here is the honest behaviour.
    """
    return vol.Schema(
        {
            vol.Optional(CONF_ENTITIES, default=list): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class=device_class, multiple=True
                )
            ),
            vol.Required(
                CONF_TYPE, default=DEFAULT_STATISTIC
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=STATISTIC_TYPES,
                    translation_key=CONF_TYPE,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_IGNORE_NON_NUMERIC, default=False
            ): selector.BooleanSelector(),
        }
    )


# vol.Optional without a default renders a clearable field: the weather entity
# can be removed after the fact, which a default would prevent.
_COMMON: dict[Any, Any] = {
    vol.Optional(CONF_WEATHER_ENTITY): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="weather")
    ),
    vol.Required(CONF_FORMULA, default=FORMULA_THRESHOLDS): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=FORMULA_MODES,
            translation_key=CONF_FORMULA,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    ),
    vol.Required(SECTION_TEMPERATURE): section(
        _group_schema(SensorDeviceClass.TEMPERATURE), {"collapsed": True}
    ),
    vol.Required(SECTION_HUMIDITY): section(
        _group_schema(SensorDeviceClass.HUMIDITY), {"collapsed": True}
    ),
    vol.Required(SECTION_WIND_SPEED): section(
        _group_schema(SensorDeviceClass.WIND_SPEED), {"collapsed": True}
    ),
}

OPTIONS_SCHEMA = vol.Schema(_COMMON)
CONFIG_SCHEMA = vol.Schema(
    {vol.Required(CONF_NAME): selector.TextSelector(), **_COMMON}
)

CONFIG_FLOW: dict[str, SchemaFlowFormStep] = {
    "user": SchemaFlowFormStep(CONFIG_SCHEMA)
}
OPTIONS_FLOW: dict[str, SchemaFlowFormStep] = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
}


class ApparentTemperatureConfigFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle the config and options flow."""

    config_flow = CONFIG_FLOW
    options_flow = OPTIONS_FLOW

    def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
        """Name the entry after what the user typed."""
        return cast(str, options[CONF_NAME])
```

- [ ] **Step 4: Write the source strings**

`custom_components/apparent_temperature/strings.json`:

```json
{
  "title": "Apparent temperature",
  "config": {
    "step": {
      "user": {
        "title": "Apparent temperature",
        "description": "Combine local sensors with a weather entity to compute a perceived temperature. Everything is optional: each quantity falls back to the weather entity on its own.",
        "data": {
          "name": "Name",
          "weather_entity": "Weather entity",
          "formula": "Formula"
        },
        "data_description": {
          "weather_entity": "Used for any quantity no sensor group can provide.",
          "formula": "How the perceived temperature is derived from temperature, humidity and wind."
        },
        "sections": {
          "temperature": {
            "name": "Temperature sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          },
          "humidity": {
            "name": "Humidity sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          },
          "wind_speed": {
            "name": "Wind speed sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          }
        }
      }
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Apparent temperature",
        "description": "Combine local sensors with a weather entity to compute a perceived temperature. Everything is optional: each quantity falls back to the weather entity on its own.",
        "data": {
          "weather_entity": "Weather entity",
          "formula": "Formula"
        },
        "data_description": {
          "weather_entity": "Used for any quantity no sensor group can provide.",
          "formula": "How the perceived temperature is derived from temperature, humidity and wind."
        },
        "sections": {
          "temperature": {
            "name": "Temperature sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          },
          "humidity": {
            "name": "Humidity sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          },
          "wind_speed": {
            "name": "Wind speed sensors",
            "data": {
              "entities": "Sensors",
              "type": "Statistic characteristic",
              "ignore_non_numeric": "Ignore non-numeric sensors"
            },
            "data_description": {
              "ignore_non_numeric": "When off, a single unusable sensor makes the whole group fall back to the weather entity."
            }
          }
        }
      }
    }
  },
  "selector": {
    "formula": {
      "options": {
        "thresholds": "Threshold indices (humidex / wind chill)",
        "steadman": "Continuous formula (Steadman)"
      }
    },
    "type": {
      "options": {
        "min": "Minimum",
        "max": "Maximum",
        "mean": "Arithmetic mean",
        "median": "Median",
        "last": "Most recently updated"
      }
    }
  }
}
```

- [ ] **Step 5: Create the English translation**

Copy `strings.json` verbatim:

```bash
mkdir -p custom_components/apparent_temperature/translations
cp custom_components/apparent_temperature/strings.json \
   custom_components/apparent_temperature/translations/en.json
```

- [ ] **Step 6: Create the French translation**

`custom_components/apparent_temperature/translations/fr.json` — same key structure, French values:

```json
{
  "title": "Température ressentie",
  "config": {
    "step": {
      "user": {
        "title": "Température ressentie",
        "description": "Combine des capteurs locaux et une entité météo pour calculer une température ressentie. Tout est facultatif : chaque grandeur bascule seule sur l'entité météo.",
        "data": {
          "name": "Nom",
          "weather_entity": "Entité météo",
          "formula": "Formule"
        },
        "data_description": {
          "weather_entity": "Utilisée pour toute grandeur qu'aucun groupe de capteurs ne fournit.",
          "formula": "Comment la température ressentie est déduite de la température, de l'humidité et du vent."
        },
        "sections": {
          "temperature": {
            "name": "Capteurs de température",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          },
          "humidity": {
            "name": "Capteurs d'humidité",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          },
          "wind_speed": {
            "name": "Capteurs de vitesse du vent",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          }
        }
      }
    }
  },
  "options": {
    "step": {
      "init": {
        "title": "Température ressentie",
        "description": "Combine des capteurs locaux et une entité météo pour calculer une température ressentie. Tout est facultatif : chaque grandeur bascule seule sur l'entité météo.",
        "data": {
          "weather_entity": "Entité météo",
          "formula": "Formule"
        },
        "data_description": {
          "weather_entity": "Utilisée pour toute grandeur qu'aucun groupe de capteurs ne fournit.",
          "formula": "Comment la température ressentie est déduite de la température, de l'humidité et du vent."
        },
        "sections": {
          "temperature": {
            "name": "Capteurs de température",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          },
          "humidity": {
            "name": "Capteurs d'humidité",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          },
          "wind_speed": {
            "name": "Capteurs de vitesse du vent",
            "data": {
              "entities": "Capteurs",
              "type": "Caractéristique statistique",
              "ignore_non_numeric": "Ignorer les capteurs non numériques"
            },
            "data_description": {
              "ignore_non_numeric": "Désactivé, un seul capteur inexploitable fait basculer tout le groupe sur l'entité météo."
            }
          }
        }
      }
    }
  },
  "selector": {
    "formula": {
      "options": {
        "thresholds": "Indices par seuils (humidex / refroidissement éolien)",
        "steadman": "Formule continue (Steadman)"
      }
    },
    "type": {
      "options": {
        "min": "Minimum",
        "max": "Maximum",
        "mean": "Moyenne arithmétique",
        "median": "Médiane",
        "last": "Dernière valeur reçue"
      }
    }
  }
}
```

- [ ] **Step 7: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_config_flow.py -v`
Expected: PASS, 4 tests. `test_options_flow_updates_the_formula` needs `sensor.py` from Task 7 to set the entry up; if it errors on the missing platform, run it again after Task 7 and leave it failing here only if the failure is `PlatformNotReady` or an import of `sensor`.

If `test_options_flow_updates_the_formula` shows empty section fields instead
of the saved ones, `SchemaFlowFormStep` is not pushing suggested values into
nested sections on this Home Assistant version. Read
`homeassistant/helpers/schema_config_entry_flow.py`, and if it genuinely does
not recurse into `section`, replace `SchemaConfigFlowHandler` with a plain
`ConfigFlow` / `OptionsFlow` pair that calls
`self.add_suggested_values_to_schema(OPTIONS_SCHEMA, entry.options)`. The
schema, the strings and the produced options mapping stay exactly as written.

- [ ] **Step 8: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/config_flow.py custom_components/apparent_temperature/strings.json custom_components/apparent_temperature/translations tests/test_config_flow.py
git commit -m "Add config and options flow with English and French strings"
```

---

### Task 7: The sensor entity

**Files:**
- Create: `custom_components/apparent_temperature/sensor.py`
- Test: `tests/test_sensor.py`

**Interfaces:**
- Consumes: `InputResolver`, `ResolvedInputs`, `Quantity` from `sources.py`; `compute`, `FormulaResult` from `formulas.py`; constants from `const.py`.
- Produces: `ApparentTemperatureSensor`, added by `async_setup_entry(hass, entry, async_add_entities)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sensor.py`:

```python
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
    assert attributes["index_value"] == pytest.approx(float(
        hass.states.get("sensor.garden_feel").state
    ))


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
    assert hass.states.get("sensor.garden_feel").attributes["formula"] == (
        "air_temperature"
    )

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_FORMULA: FORMULA_STEADMAN}
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.garden_feel").attributes["formula"] == "steadman"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/pytest tests/test_sensor.py -v`
Expected: FAIL — `sensor` platform not found.

- [ ] **Step 3: Write the entity**

`custom_components/apparent_temperature/sensor.py`:

```python
"""The apparent temperature sensor entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_FORMULA
from .formulas import compute
from .sources import InputResolver

ATTR_INDEX_VALUE = "index_value"
ATTR_FORMULA = "formula"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the helper's single sensor."""
    async_add_entities([ApparentTemperatureSensor(hass, entry)])


class ApparentTemperatureSensor(SensorEntity):
    """Perceived temperature derived from three resolved quantities."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise from the config entry's options."""
        self._attr_name = entry.options[CONF_NAME]
        self._attr_unique_id = entry.entry_id
        self._mode: str = entry.options[CONF_FORMULA]
        self._resolver = InputResolver(hass, entry.options)
        self._attr_extra_state_attributes: dict[str, Any] = {}

    async def async_added_to_hass(self) -> None:
        """Subscribe to every source and compute a first value."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._resolver.tracked_entity_ids, self._handle_change
            )
        )
        self._recalculate()

    @callback
    def _handle_change(self, _event: Event[EventStateChangedData]) -> None:
        """Recompute when any source changes."""
        self._recalculate()
        self.async_write_ha_state()

    @callback
    def _recalculate(self) -> None:
        """Resolve the inputs, apply the formula, publish the attributes."""
        inputs = self._resolver.resolve()
        attributes: dict[str, Any] = {
            "temperature": inputs.temperature.value,
            "temperature_source": inputs.temperature.source,
            "humidity": inputs.humidity.value,
            "humidity_source": inputs.humidity.source,
            "wind_speed": inputs.wind_speed.value,
            "wind_speed_source": inputs.wind_speed.source,
        }

        if inputs.temperature.value is None:
            # Without a temperature there is nothing to derive anything from.
            self._attr_available = False
            self._attr_native_value = None
            attributes[ATTR_FORMULA] = None
            attributes[ATTR_INDEX_VALUE] = None
            self._attr_extra_state_attributes = attributes
            return

        result = compute(
            self._mode,
            inputs.temperature.value,
            inputs.humidity.value,
            inputs.wind_speed.value,
        )
        self._attr_available = True
        self._attr_native_value = result.value
        # The state is converted for display by Home Assistant; index_value
        # keeps the number the formula actually produced.
        attributes[ATTR_INDEX_VALUE] = result.value
        attributes[ATTR_FORMULA] = result.formula
        self._attr_extra_state_attributes = attributes
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/pytest tests/test_sensor.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -v`
Expected: PASS, including the config flow test that needed the sensor platform.

- [ ] **Step 6: Lint and commit**

```bash
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check --fix custom_components tests
git add custom_components/apparent_temperature/sensor.py tests/test_sensor.py
git commit -m "Add the apparent temperature sensor entity"
```

---

### Task 8: Documentation

**Files:**
- Create: `README.md`
- Modify: `package.json:3` (the placeholder description)
- Modify: `pyproject.toml` (the placeholder description)

**Interfaces:**
- Consumes: the finished integration.
- Produces: nothing other modules import.

- [ ] **Step 1: Write the README**

`README.md`:

````markdown
# Apparent temperature — Home Assistant helper

Adds an **Apparent temperature** helper that computes a perceived temperature
from local sensors, with a weather entity as a fallback.

## What it does

Three quantities feed the computation: air temperature, relative humidity and
wind speed. Each one is aggregated from a group of sensors, the way the native
"Combine the state of several sensors" helper does — pick the sensors, pick a
statistic (minimum, maximum, arithmetic mean, median, most recently updated).

Each quantity falls back to the weather entity **on its own**. A flat battery in
the anemometer does not cost you the local thermometer.

## Formulas

- **Threshold indices (humidex / wind chill)** — what Météo-France publishes.
  Humidex above 15 °C, wind chill below 10 °C, plain air temperature in between.
- **Continuous formula (Steadman)** — one equation over the whole range, using
  all three quantities at once.

When a formula needs a quantity that is not available, the helper reports the
air temperature and says so in its `formula` attribute.

## Attributes

| Attribute | Meaning |
| --- | --- |
| `index_value` | The raw number the formula produced, unconverted |
| `formula` | `humidex`, `wind_chill`, `steadman` or `air_temperature` |
| `temperature`, `humidity`, `wind_speed` | The values used, in °C / % / km/h |
| `temperature_source`, `humidity_source`, `wind_speed_source` | `group`, `weather` or `null` |

The state carries `device_class: temperature`, so Home Assistant converts it for
display according to your unit system. Humidex and wind chill are indices rather
than true temperatures, which is why `index_value` keeps the unconverted number.

## Units

Sensors are converted before being aggregated, so a group mixing °C and °F, or
km/h and Beaufort, still produces a correct statistic. Sensors are filtered by
device class in the picker: a sensor published without a `device_class` cannot
be converted, and will not appear.

## Install

Add this repository to HACS as a custom repository, install it, restart Home
Assistant, then go to **Settings → Devices & services → Helpers → Create helper
→ Apparent temperature**.

## Development

```bash
uv sync
.venv/bin/pytest
.venv/bin/ruff check custom_components tests
```
````

- [ ] **Step 2: Replace the two placeholder descriptions**

In `package.json`, set `"description": "Home Assistant apparent temperature helper — tooling"`.
In `pyproject.toml`, set `description = "Home Assistant helper computing a perceived temperature from sensor groups and a weather entity"`.

- [ ] **Step 3: Verify the suite is still green**

Run: `.venv/bin/pytest -v`
Expected: PASS, every test green.

- [ ] **Step 4: Commit**

```bash
git add README.md package.json pyproject.toml
git commit -m "Document the apparent temperature helper"
```

---
### Task 9: A runnable Home Assistant instance

Depends on Task 7 — before the sensor platform exists there is nothing to look
at. It does not depend on Task 8.

**Files:**
- Create: `scripts/ha-dev.ts`
- Modify: `package.json` (add the `ha` script)
- Modify: `.gitignore` (ignore the throwaway config directory)

**Interfaces:**
- Consumes: the finished integration in `custom_components/apparent_temperature/`.
- Produces: `pnpm run ha`, which boots the official Home Assistant container on
  http://localhost:8123 with this repository's component mounted in. Nothing
  imports it.

The running instance is the **official Docker image**, not the venv. The
devcontainer already has docker-in-docker. The venv keeps `homeassistant` only
because `pytest-homeassistant-custom-component` needs it to run the test suite;
nothing launches `hass` from it.

`AGENTS.md` requires scripts to be TypeScript run with tsx, which is why the
launcher is not a shell script.

- [ ] **Step 1: Ignore the throwaway config directory**

Append to `.gitignore`:

```
.ha-dev/
```

- [ ] **Step 2: Write the launcher**

`scripts/ha-dev.ts`:

```ts
/**
 * Launch a throwaway Home Assistant instance from the official image, with
 * this repository's custom component mounted into it.
 *
 *   pnpm run ha             reuse .ha-dev/, keeping whatever was configured
 *   pnpm run ha -- --reset  start from an empty config directory
 *
 * The config directory is deliberately reused between runs: helpers created
 * through the UI, and the onboarding account, survive a restart. Only --reset
 * throws that away.
 *
 * HA_VERSION overrides the image tag (default: stable).
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const configDir = join(repoRoot, ".ha-dev");
const componentSource = join(repoRoot, "custom_components", "apparent_temperature");
const image = `ghcr.io/home-assistant/home-assistant:${process.env.HA_VERSION ?? "stable"}`;

// Seed sensors, deliberately in mixed units, so the helper has something to
// select and the unit conversion is visible rather than theoretical.
const CONFIGURATION = `default_config:

logger:
  default: info
  logs:
    custom_components.apparent_temperature: debug

template:
  - sensor:
      - name: Dev temperature celsius
        unique_id: dev_temperature_celsius
        state: "18.4"
        unit_of_measurement: "°C"
        device_class: temperature
        state_class: measurement
      - name: Dev temperature fahrenheit
        unique_id: dev_temperature_fahrenheit
        state: "68.0"
        unit_of_measurement: "°F"
        device_class: temperature
        state_class: measurement
      - name: Dev humidity
        unique_id: dev_humidity
        state: "62"
        unit_of_measurement: "%"
        device_class: humidity
        state_class: measurement
      - name: Dev wind kmh
        unique_id: dev_wind_kmh
        state: "24"
        unit_of_measurement: "km/h"
        device_class: wind_speed
        state_class: measurement
      - name: Dev wind beaufort
        unique_id: dev_wind_beaufort
        state: "5"
        unit_of_measurement: "Beaufort"
        device_class: wind_speed
        state_class: measurement
`;

if (spawnSync("docker", ["info"], { stdio: "ignore" }).status !== 0) {
	console.error("Docker is not reachable. The devcontainer's docker-in-docker feature provides it.");
	process.exit(1);
}
if (!existsSync(componentSource)) {
	console.error(`No component at ${componentSource}.`);
	process.exit(1);
}

if (process.argv.includes("--reset") && existsSync(configDir)) {
	rmSync(configDir, { recursive: true, force: true });
	console.log("Reset .ha-dev/");
}

mkdirSync(configDir, { recursive: true });
const configurationYaml = join(configDir, "configuration.yaml");
if (!existsSync(configurationYaml)) {
	writeFileSync(configurationYaml, CONFIGURATION);
}

console.log(`Home Assistant (${image}) starting on http://localhost:8123`);
console.log("Settings > Devices & services > Helpers > Create helper > Apparent temperature");
console.log("Ctrl-C stops it; --rm means the container leaves nothing behind.");

// The component is a second, read-only bind nested inside /config: Home
// Assistant never writes there, and mounting it separately keeps the source of
// truth in the repository rather than a copy that silently goes stale.
const child = spawn(
	"docker",
	[
		"run", "--rm", "-it",
		"--name", "apparent-temperature-ha-dev",
		"-p", "8123:8123",
		"-e", `TZ=${process.env.TZ ?? "Europe/Paris"}`,
		"-v", `${configDir}:/config`,
		"-v", `${componentSource}:/config/custom_components/apparent_temperature:ro`,
		image,
	],
	{ stdio: "inherit" },
);
child.on("exit", (code) => process.exit(code ?? 0));
```

- [ ] **Step 3: Add the package script**

In `package.json`, add a `scripts` block (the file has none yet):

```json
"scripts": {
    "ha": "tsx scripts/ha-dev.ts"
}
```

- [ ] **Step 4: Verify it boots**

Run: `pnpm run ha`
Expected: the image is pulled on first run, Home Assistant logs start, and
`http://localhost:8123` answers. After onboarding, the helper appears under
**Settings → Devices & services → Helpers → Create helper** as "Apparent
temperature". Create one against `sensor.dev_temperature_celsius` and
`sensor.dev_humidity` and check the state appears. Stop with Ctrl-C.

If Home Assistant refuses to start on the seeded template sensors, remove the
`template:` block from `.ha-dev/configuration.yaml` and re-run — the helper
itself needs none of it.

- [ ] **Step 5: Commit**

```bash
pnpm exec biome check --write scripts package.json
git add scripts/ha-dev.ts package.json .gitignore
git commit -m "Add a dockerised Home Assistant dev instance"
```
