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
| Native reuse | Headless `SensorGroup` instances, never added to `hass`, pinned to canonical units |
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

The wind filter is `wind_speed`, not `speed`. Both device classes exist in
current Home Assistant and neither is deprecated, but `speed` also accepts
`UnitOfVolumetricFlux` — mm/h, in/d. A rain gauge picked by mistake would be a
valid speed as far as `SpeedConverter` is concerned and would convert to km/h
without complaint.

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

Groups are native `SensorGroup` instances
(`homeassistant.components.group.sensor`), constructed directly so that
`device_class` and `unit_of_measurement` can be imposed: `temperature` in °C,
`humidity` in %, `wind_speed` in km/h. `_calculate_unit_of_measurement()` opens
with `if unit_of_measurement: return unit_of_measurement`, so a configured unit
wins outright; `_get_valid_units()` then sets `_can_convert = True` and every
member is converted to the canonical unit **before** aggregation. The helper
therefore never post-converts a group's result.

That ordering is not cosmetic. `UnitOfSpeed.BEAUFORT` is convertible but not
linearly — `SpeedConverter._beaufort_to_ms` is `0.836 · B^1.5` — so a group
aggregating in Beaufort and converted afterwards would yield a wrong `mean`.
Converting each member first removes the whole class of problem.

The groups are **never** added to `hass`: no entity registry entry, nothing
visible in the UI. Home Assistant does the same for config-flow previews in
`async_create_preview_sensor()`, which builds a `SensorGroup` with
`unique_id=None`; that function is not used here only because it hardcodes
`None` for the device class and unit. The helper calls
`async_update_group_state()` itself, then reads `available` and `native_value`.
This delegates availability, member filtering, unit conversion,
`ignore_non_numeric` semantics and warning logs to Home Assistant, which is the
point — the helper is ISO with the native behaviour by construction rather than
by imitation.

`manifest.json` declares `"dependencies": ["group"]`, which is honest about the
import; `group` ships in `default_config` anyway.

### `units.py` — normalisation

Groups already produce canonical values, so this module covers the one path
that does not: the weather entity, whose `temperature_unit` and
`wind_speed_unit` are read from its attributes and converted with
`homeassistant.util.unit_conversion.TemperatureConverter` and `SpeedConverter`
— never hand-written constants. It also holds the km/h → m/s step Steadman
needs.

`range` and `sum` were excluded from the statistics for a second reason beyond
being meaningless as comfort-formula inputs: neither survives a unit change
cleanly. A range converted with the °F→°C offset is simply wrong.

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
  (the `SensorGroup` constructor signature, `async_update_group_state`, the
  `available` and `native_value` properties, and the fact that a configured
  `unit_of_measurement` wins over the members' own units) so a core refactor
  fails loudly here rather than silently in production. A Beaufort member in a
  km/h group is part of that test.

## Packaging

- `manifest.json`: `domain: apparent_temperature`, `config_flow: true`,
  `integration_type: helper`, `iot_class: calculated`,
  `dependencies: ["group"]`.
- `hacs.json` for HACS custom-repository installation.
- Python 3.13, matching Home Assistant's own requirement.

## Risks

The helper depends on `homeassistant.components.group.sensor`, which is Home
Assistant internal code with no API stability guarantee. The dependency is
confined to `sources.py` and pinned by a dedicated test. Constructing
`SensorGroup` directly rather than through `async_create_preview_sensor()`
widens that exposure slightly — a constructor signature is easier to change
than a config-dict entry point — which is the price of imposing the canonical
units, and it is the same object either way. Should core break it,
the fallback is to import the module-level `calc_*` functions and reimplement
the ~80 lines of filtering and unit handling from `async_update_group_state()`.
