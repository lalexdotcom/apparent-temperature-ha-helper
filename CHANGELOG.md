# Changelog

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
