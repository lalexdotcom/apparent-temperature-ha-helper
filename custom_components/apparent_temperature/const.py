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
