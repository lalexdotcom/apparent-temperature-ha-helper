# Apparent Temperature Helper — Design

- Date: 2026-08-31
- Status: approved, pending implementation plan
- Domain: `apparent_temperature`

## Goal

A Home Assistant custom integration that adds an "Apparent temperature" helper.
The helper produces one sensor whose state is a perceived temperature, computed
from three quantities — air temperature, relative humidity and wind speed. Each
quantity is aggregated from a user-chosen group of sensors, exactly like the
native "Combine the state of several sensors" helper, and falls back to a
weather entity when its group yields nothing.

## Non-goals

- No solar radiation, no radiant temperature, no UTCI.
- No adjustable thresholds. The 15 °C / 10 °C / 4.8 km/h cut-offs are fixed.
- No YAML configuration. The helper is created and edited through the UI only.
- No device. Helper config entries create an entity, not a device.

## Decisions

| Decision | Choice |
| --- | --- |
| Deliverable | Python custom integration, HACS-installable, config flow + options flow |
| Tooling language | Python for the integration; TypeScript in `scripts/` for tooling only |
| Formulas | Two modes: threshold indices (Météo-France) and continuous (Steadman) |
| Weather fallback | Per quantity, independently |
| Groups | All three optional; sensor is `unavailable` when temperature cannot be resolved |
| Statistics | `min`, `max`, `mean`, `median`, `last` |
| Invalid members | Delegated to native `SensorGroup`, driven by `ignore_non_numeric` |
| Native reuse | Headless `SensorGroup` instances, never added to `hass` |
| Output | State as `device_class: temperature` in °C, raw index exposed as an attribute |
| Localisation | `strings.json` as source, `en` and `fr` translations |
| Entity id | Derived from the helper title, HA default behaviour |

## Formulas

All formulas take canonical inputs: temperature in °C, humidity in %, wind speed
in km/h. `formulas.py` is pure computation — it never touches `hass`.

Saturation vapour pressure uses the Magnus form
`es(T) = 6.112 · exp(17.62·T / (243.12 + T))` in hPa; actual vapour pressure is
`e = es(T) · RH/100`. Dew point comes from the same coefficients:
`Td = 243.12·a / (17.62 − a)` with `a = ln(RH/100) + 17.62·T / (243.12 + T)`.

### Mode `thresholds` — Météo-France (default)

Météo-France publishes humidex above 15 °C and wind chill below 10 °C, and the
plain air temperature in between.

- `T > 15 °C` → **humidex** = `T + 0.5555 · (e_dew − 10)`, where `e_dew` is the
  vapour pressure derived from the dew point,
  `e_dew = 6.11 · exp(5417.7530 · (1/273.16 − 1/(273.15 + Td)))`.
- `T < 10 °C` → **wind chill (JAG/TI 2001)**:
  - `V > 4.8 km/h`: `13.12 + 0.6215·T + (0.3965·T − 11.37) · V^0.16`
  - `0 < V ≤ 4.8 km/h`: `T + 0.2 · (0.1345·T − 1.59) · V`
  - `V = 0`: `T`
- `10 ≤ T ≤ 15 °C` → **air temperature**, unchanged.

### Mode `steadman` — continuous

`AT = T + 0.33·e − 0.70·ws − 4.00`, with `e` in hPa and `ws` in **m/s** — the
only place where wind is not in km/h, so `sources` hands over km/h and
`formulas` divides by 3.6 internally.

### Degradation

One rule for both modes: when a formula needs a quantity that could not be
resolved, the helper falls back to the air temperature and records
`air_temperature` in the `formula` attribute. So: no humidity above 15 °C, no
wind below 10 °C, or either one missing in Steadman mode. Dropping a single
term instead was rejected — Steadman's `− 4.00` constant assumes the humidity
and wind terms are both present, so a partial evaluation would be silently
wrong rather than merely degraded.

## Config flow

One step, one schema shared with the options flow (which reuses it minus the
name).

| Key | Selector | Notes |
| --- | --- | --- |
| `name` | text | Config entry title; drives the default `entity_id` |
| `weather_entity` | entity, `domain: weather` | Optional, clearable |
| `formula` | select | `thresholds` (default), `steadman` |
| `temperature` | section, collapsed | see below, `device_class: temperature` |
| `humidity` | section, collapsed | `device_class: humidity` |
| `wind_speed` | section, collapsed | `device_class: wind_speed` |

Each section holds three fields:

| Key | Selector | Default |
| --- | --- | --- |
| `entities` | entity, multiple, filtered by device class | empty |
| `type` | select over `min`/`max`/`mean`/`median`/`last` | `mean` |
| `ignore_non_numeric` | boolean | `false` (HA's own default) |

Sections use `homeassistant.data_entry_flow.section` with
`{"collapsed": True}`. Everything is optional; no cross-field validation is
performed at creation time — a helper configured with nothing simply reports
`unavailable`.

## Runtime architecture

```
custom_components/apparent_temperature/
  __init__.py      async_setup_entry / async_unload_entry / options update listener
  const.py         DOMAIN, configuration keys, enumerations
  config_flow.py   config flow + options flow, shared schema
  sensor.py        ApparentTemperatureSensor — orchestration, state, attributes
  sources.py       quantity resolution: headless SensorGroup, then weather
  units.py         normalisation to °C / % / km/h
  formulas.py      formula registry
  manifest.json  strings.json  translations/{en,fr}.json
tests/  hacs.json
```

The sensor is event-driven. It subscribes with `async_track_state_change_event`
to every configured source entity plus the weather entity, and recomputes on
each change. No `DataUpdateCoordinator`: that helper exists to pace I/O, and
every input here already lives in the state machine. No polling.

### `sources.py` — quantity resolution

One rule, applied per quantity, independently of the other two:

1. If the quantity has configured entities, ask its `SensorGroup`. If the group
   is available and produced a value, use it, tagged `group`.
2. Otherwise, if a weather entity is configured and exposes the quantity, use
   it, tagged `weather`.
3. Otherwise the quantity is absent, tagged `null`.

Weather entities are read from their state attributes: `temperature` with
`temperature_unit`, `humidity` (always %), `wind_speed` with `wind_speed_unit`.
The declared units are read, never assumed.

Groups are native `SensorGroup` instances built through
`homeassistant.components.group.sensor.async_create_preview_sensor(hass, name,
config)`, which takes a validated config dict and is a more stable entry point
than the constructor. They are **never** added to `hass`: no entity registry
entry, nothing visible in the UI. The helper calls `async_update_group_state()`
itself, then reads `available`, `native_value` and
`native_unit_of_measurement`. This delegates availability, member filtering,
unit conversion, `ignore_non_numeric` semantics and warning logs to Home
Assistant, which is the point — the helper is ISO with the native behaviour by
construction rather than by imitation.

`manifest.json` declares `"dependencies": ["group"]`, which is honest about the
import; `group` ships in `default_config` anyway.

### `units.py` — normalisation

`SensorGroup` aggregates in the unit of its first valid member. The helper then
converts the aggregate once, to °C / % / km/h, using
`homeassistant.util.unit_conversion.TemperatureConverter` and `SpeedConverter`
— never hand-written constants.

Converting after aggregating is exact here: `min`, `max`, `mean`, `median` and
`last` all commute with an affine conversion. This is precisely why `range` and
`sum` were excluded — a range converted with the °F→°C offset would be wrong —
alongside the fact that neither is meaningful as an input to a comfort formula.

## Entity

- State: the computed value in °C, `device_class: temperature`,
  `state_class: measurement`, `suggested_display_precision: 1`. Home Assistant
  converts it for display according to the user's unit system.
- Attributes:
  - `index_value` — the raw number the formula produced, unconverted. Humidex
    and wind chill are dimensionless indices, not temperatures; this attribute
    keeps the unconverted value reachable.
  - `formula` — `humidex`, `wind_chill`, `steadman` or `air_temperature`.
  - `temperature_source`, `humidity_source`, `wind_speed_source` — `group`,
    `weather` or `null`.
  - `temperature`, `humidity`, `wind_speed` — the canonical values actually
    used.
- Availability: `unavailable` when temperature cannot be resolved from any
  source.
- `entity_id`: HA's default derivation from the entity name, so the helper
  title the user types. `Entity.suggested_object_id` is left untouched.

## Localisation

`strings.json` is the source; `translations/en.json` mirrors it and
`translations/fr.json` carries the French translation. Translated surfaces: step and section titles, field
labels and descriptions, the two formula names, the five statistic names, and
error messages. Keys stay neutral (`formula.thresholds`, `formula.steadman`) so
that no mode reads as more universal than the other in any language.

## Testing

`pytest` with `pytest-homeassistant-custom-component`.

- `formulas` and `units` are pure functions, tested against reference vectors
  from the Environment Canada humidex and wind chill tables, plus threshold
  boundary cases (exactly 10 °C, 15 °C, 4.8 km/h, 0 km/h).
- `sources` is tested for per-quantity fallback: group available, group empty,
  group unavailable, weather missing the attribute, mixed units within a group.
- The config flow and options flow are tested for round-tripping a full
  configuration and an empty one.
- One dedicated test pins the Home Assistant internals the helper depends on
  (`async_create_preview_sensor`, `async_update_group_state`, the
  `available` / `native_value` / `native_unit_of_measurement` properties) so a
  core refactor fails loudly here rather than silently in production.

## Packaging

- `manifest.json`: `domain: apparent_temperature`, `config_flow: true`,
  `integration_type: helper`, `iot_class: calculated`,
  `dependencies: ["group"]`.
- `hacs.json` for HACS custom-repository installation.
- Python 3.13, matching Home Assistant's own requirement.

## Risks

The helper depends on `homeassistant.components.group.sensor`, which is Home
Assistant internal code with no API stability guarantee. The dependency is
confined to `sources.py` and pinned by a dedicated test. Should core break it,
the fallback is to import the module-level `calc_*` functions and reimplement
the ~80 lines of filtering and unit handling from `async_update_group_state()`.
