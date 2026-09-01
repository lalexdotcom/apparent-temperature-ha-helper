# apparent-temperature-ha-helper

A Home Assistant custom integration, domain `apparent_temperature`: a helper
producing one perceived-temperature sensor from three optional sensor groups
(temperature / humidity / wind speed) plus a weather entity as a per-quantity
fallback.

## State as of 2026-09-01

**Implemented and green.** Branch `feat/apparent-temperature-helper`, 20 commits
off `main`, 65 tests passing, ruff and biome clean. Not merged yet.

- Spec: `docs/superpowers/specs/2026-08-31-apparent-temperature-helper-design.md`
- Plan: `docs/superpowers/plans/2026-08-31-apparent-temperature-helper.md`
  (9 tasks, all complete, executed subagent-driven with a review per task and a
  whole-branch review at the end)

## Layout

```
custom_components/apparent_temperature/
  __init__.py  const.py  config_flow.py  sensor.py
  sources.py   units.py  formulas.py
  manifest.json  strings.json  translations/{en,fr}.json
tests/  hacs.json  scripts/ha-dev.ts
```

`formulas.py` and `units.py` are pure. `sources.py` is the only module importing
`homeassistant.components.group` — it builds headless `SensorGroup` instances,
never added to `hass`, constructed with device class, state class **and** unit
all explicitly passed. Those three arguments are load-bearing: each makes core
return early instead of negotiating from the members, which is what converts
every member to °C / % / km/h *before* aggregation and what stops core opening
repair issues keyed on an `entity_id` these groups do not have.
`tests/test_ha_internals.py` pins all of that against core.

Two formula modes: threshold indices (humidex above 15 °C, wind chill below
10 °C, air temperature between — what Météo-France publishes) and a continuous
Steadman formula. A missing quantity degrades to the air temperature and says so
in the `formula` attribute; the sensor is `unavailable` only when no source can
supply a temperature.

## Stack and commands

- **Python 3.13** via `uv`. `.venv` must run on **uv's managed CPython**:
  `homeassistant` pins `lru-dict==1.3.0`, which has no cp313 wheel and needs
  headers the devcontainer image lacks. `pyproject.toml` sets
  `[tool.uv] python-preference = "only-managed"` and post-create.sh runs
  `uv python install 3.13` — do not remove either.
- `.venv/bin/pytest`, `.venv/bin/ruff format`, `.venv/bin/ruff check --fix`.
  Ruff is line-length 100, `select = E,F,W,I,UP,B,SIM,RUF`.
- `pnpm run ha` boots Home Assistant from the **official Docker image** against
  a throwaway `.ha-dev/`, component bind-mounted read-only, with seed sensors in
  mixed units. `pnpm run ha -- --reset` starts from scratch. The venv holds
  `homeassistant` only for the test suite; nothing launches `hass` from it.
- TypeScript is tooling only, in `scripts/`, run with tsx; biome formats it
  (tabs, width 100).

## Conventions

- Chat with the user in **French**; code, comments, commits, docs in English.
- `AGENTS.md` is binding: user leads, one step at a time, no unsolicited
  suggestions, confirm before large changes, no trailing "should I continue?".
- Every subagent dispatch passes an explicit `model` per the tier table in
  `AGENTS.md`.
- Serena's symbolic tools are primary for code; built-in Read/Edit only for
  Markdown, JSON, YAML and other non-code. See `mem:serena_language_servers`.
- Feature branches, never worktrees — `mem:working_with_this_user`.
