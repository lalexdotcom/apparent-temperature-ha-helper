# apparent-temperature-ha-helper

A Home Assistant custom integration, domain `apparent_temperature`: a helper
producing one perceived-temperature sensor from three optional sensor groups
(temperature / humidity / wind speed) plus a weather entity as a per-quantity
fallback.

## State as of 2026-08-31

Design and implementation plan are written and committed. **No integration code
exists yet** — `custom_components/` does not exist. Execution has not started
and the execution mode (subagent-driven vs inline) was never chosen.

- `docs/superpowers/specs/2026-08-31-apparent-temperature-helper-design.md`
- `docs/superpowers/plans/2026-08-31-apparent-temperature-helper.md` — 8 TDD
  tasks, 50 steps, full code in every step. Read it before writing anything.

## Stack

- **Python 3.13** for the integration, managed by `uv`. `uv sync` creates
  `.venv`; run tools as `.venv/bin/pytest`, `.venv/bin/ruff`.
- `pyproject.toml`: ruff (line-length 100, `select = E,F,W,I,UP,B,SIM,RUF`),
  pytest with `asyncio_mode = "auto"`, `testpaths = ["tests"]`.
- **TypeScript** is tooling only. `AGENTS.md` requires any script to live in
  `scripts/` as TypeScript run with `pnpm exec tsx`. pnpm + biome (tab indent,
  width 100) cover that side. Playwright/chromium is installed for driving a
  Home Assistant frontend.
- Devcontainer reproduces all of it via `.devcontainer/post-create.sh`
  (`uv sync`, `pnpm install`, serena, playwright).

## Planned layout

```
custom_components/apparent_temperature/
  __init__.py  const.py  config_flow.py  sensor.py
  sources.py   units.py  formulas.py
  manifest.json  strings.json  translations/{en,fr}.json
tests/  hacs.json
```

`formulas.py` and `units.py` are pure. `sources.py` is the only module allowed
to touch the state machine or to import `homeassistant.components.*` — it
builds headless `SensorGroup` instances, never added to `hass`, pinned to
canonical units (°C / % / km/h) so members convert before aggregation.

## Conventions

- Chat with the user in **French**; code, comments, commits, docs in English.
- `AGENTS.md` is binding: user leads, one step at a time, no unsolicited
  suggestions, confirm before large changes, no trailing "should I continue?".
- Every subagent dispatch must pass an explicit `model` and `effort` per the
  tier table in `AGENTS.md`.
- Serena's symbolic tools are primary for code; built-in Read/Edit only for
  Markdown, JSON, YAML and other non-code.
