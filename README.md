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
