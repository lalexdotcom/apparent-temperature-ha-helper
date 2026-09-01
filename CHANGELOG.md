# Changelog

## 1.1.0 — 2026-09-01

### Added

- **One entity per measured quantity.** Temperature, humidity and wind speed
  are now published as entities of their own, carrying the value that fed the
  formula in °C / % / km/h and a `source` attribute reading `group` or
  `weather`. Being entities, they are recorded and get long-term statistics.
  They are **disabled by default** — enable the ones you want in the helper's
  page — and statistics start at that moment, with no backfill.
- **A device per helper**, grouping the perceived temperature and its three
  measurement entities. The main sensor's name, entity id and history are
  unchanged.

### Changed

- **"Ignore non-numeric sensors" now defaults to on.** A member going unknown
  no longer costs you the whole group; it is skipped and the others still
  aggregate. Existing helpers keep the value they were saved with — this only
  changes what a new one starts from.
- **BREAKING (minor).** The `temperature_source`, `humidity_source` and
  `wind_speed_source` attributes are gone from the main sensor; that
  information now lives on the matching measurement entity. A template reading
  them gets `None` instead of an error. The `temperature`, `humidity` and
  `wind_speed` attributes are untouched.

## 1.0.0 — 2026-09-01

### Added

- **Apparent temperature helper.** Creates one sensor computing a perceived
  temperature from air temperature, relative humidity and wind speed.
- **Three sensor groups, one per quantity.** Each is aggregated the way the
  native "Combine the state of several sensors" helper does — minimum, maximum,
  arithmetic mean, median, or most recently updated.
- **A weather entity as a per-quantity fallback.** Each quantity falls back on
  its own: a flat battery in the anemometer does not cost you the local
  thermometer.
- **Two formula modes.** Threshold indices — humidex above 15 °C, wind chill
  below 10 °C, plain air temperature in between, which is what Météo-France
  publishes — or the continuous Steadman formula over the whole range.
- **Unit conversion before aggregation**, so a group mixing °C and °F, or km/h
  and Beaufort, still produces a correct statistic.
- **Attributes reporting what was used**: the raw `index_value`, the `formula`
  applied, and each quantity with the source it came from.
- English and French translations.
