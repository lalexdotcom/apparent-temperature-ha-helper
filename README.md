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

The helper itself reports `unavailable` when no source — group or weather
fallback — can supply a temperature. `ignore_non_numeric` is on by default, so
an unusable member is skipped and the rest of the group still aggregates; switch
it off for a group and a single unusable member drops the whole group to the
weather fallback instead.

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

## Measurement entities

Besides the perceived temperature, the helper registers one entity per quantity
it consumes — temperature, humidity and wind speed — each publishing the value
that actually fed the formula, in °C / % / km/h, with a `source` attribute
reading `group` or `weather`. A quantity no source can supply is `unavailable`.

They are **disabled by default**: enable the ones you want in the helper's page.
The attributes above carry the same values whether or not you do, so enable an
entity when you want the thing an attribute cannot give you — a recorded
history and long-term statistics, starting from the moment you enable it.

All four entities are grouped under a device named after the helper.

## Units

Sensors are converted before being aggregated, so a group mixing °C and °F, or
km/h and Beaufort, still produces a correct statistic. Sensors are filtered by
device class in the picker: a sensor published without a `device_class` cannot
be converted, and will not appear.

## Install

### Requirements

**Home Assistant 2026.2.3 or newer.** HACS enforces this and will refuse to
install on an older version.

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=lalexdotcom&repository=apparent-temperature-ha-helper&category=integration)

This helper is **not** in the default HACS catalog, so it has to be added as a
custom repository. The button above does exactly that: HACS asks you to
confirm, adds the repository, and opens its page. From there:

1. Choose **Download**.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Helpers → Create helper →
   Apparent temperature**.

<details>
<summary>If the button does not work</summary>

HACS may not be installed yet, or your instance URL may not be registered with
My Home Assistant. Add the repository by hand:

1. Open **HACS** in Home Assistant.
2. Open the **⋮** menu → **Custom repositories**.
3. Repository: `lalexdotcom/apparent-temperature-ha-helper` — Type:
   **Integration**.
4. **Add**, then open **Apparent temperature** from the list and download it as
   above.

</details>

<details>
<summary>Manual install</summary>

1. Download the source archive of the
   [latest release](https://github.com/lalexdotcom/apparent-temperature-ha-helper/releases/latest).
2. Copy `custom_components/apparent_temperature/` into your Home Assistant
   `config/custom_components/` directory. Create `custom_components` if it does
   not exist.
3. Restart Home Assistant, then create the helper as above.

Updates are on you from then on — HACS is what tracks releases.

</details>

## Development

```bash
uv sync
.venv/bin/pytest
.venv/bin/ruff format custom_components tests
.venv/bin/ruff check custom_components tests
```

A throwaway Home Assistant instance runs from the official image, with this
repository's component and a seeded `configuration.yaml` mounted into it:

```bash
pnpm ha:up      # http://localhost:8123
pnpm ha:logs
pnpm ha:down
pnpm ha:reset   # also throws away .ha/config — onboarding and helpers included
```

The seed lives in [`dev/configuration.yaml`](dev/configuration.yaml): sensors in
mixed units, plus a weather entity in kelvin and knots, so the conversions are
visible rather than theoretical. Everything Home Assistant writes stays in the
gitignored `.ha/config/`, which survives a restart.

## Releasing

`custom_components/apparent_temperature/manifest.json` holds the version, and
that is the whole trigger: add a section to [`CHANGELOG.md`](CHANGELOG.md), bump
the manifest, push to `main`. Once CI is green, the release workflow tags
`vX.Y.Z` and publishes the release, with the changelog section as its body and
GitHub's generated notes underneath. A version that is already tagged is a
no-op, so an ordinary push releases nothing.
