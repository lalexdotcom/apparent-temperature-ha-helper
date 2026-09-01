# apparent-temperature-ha-helper

A Home Assistant custom integration, domain `apparent_temperature`: a helper
producing one perceived-temperature sensor from three optional sensor groups
(temperature / humidity / wind speed) plus a weather entity as a per-quantity
fallback.

## State as of 2026-09-01

**Implemented and green, merged into `main`.** 65 tests passing, ruff and biome
clean. Never released yet — the HACS packaging below lands `1.0.0`.

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
tests/  dev/configuration.yaml  docker-compose.yml
hacs.json  CHANGELOG.md  LICENSE  scripts/release-notes.ts
.github/workflows/{ci,validate,release}.yml
```

## Distribution (HACS)

Set up 2026-09-01, mirroring `lalexdotcom/picture-studio-card`, whose three
workflows are the reference whenever this side needs extending.

- **The manifest's `version` is the release trigger.** No tag is ever pushed by
  hand: `release.yml` hangs off a green `CI` on `main` (`workflow_run`), reads
  `.version` from the manifest, exits as a no-op if `vX.Y.Z` is already tagged,
  and otherwise publishes with `softprops/action-gh-release` pinned to a SHA.
  The body is the matching `CHANGELOG.md` section — extracted by an inline awk
  `run:` block that refuses an absent, empty or still `unreleased` section —
  followed by GitHub's generated notes —
  `generate_release_notes: true` appends to a body rather than replacing it.
  So: write the changelog section, bump the manifest, push. First release is
  `1.0.0`. The release job needs no Node at all — no pnpm install, no tsx.
- **`scripts/` is for development and one-offs, not for CI.** Stated
  2026-09-01 and now written into `AGENTS.md` § Scripts: logic a workflow runs
  belongs inline in its `run:` block, in shell. `scripts/brand-icons.ts` is the
  kind of thing that does belong there — a human runs it, and only when the
  icon changes.
- `ci.yml` lints the workflows first (`rhysd/actionlint` in Docker, pinned),
  then `uv sync --locked`, ruff and pytest. Ruff is scoped to
  `custom_components tests` on purpose: `ruff format` reformats the Python in
  the Markdown under `docs/`, which must not be touched.
- **hassfest and `hacs/action` run twice, on purpose.** In `ci.yml` they are
  jobs, so a red one makes CI red and no release goes out — the only way to
  gate it, since `workflow_run` with several `workflows:` fires on *either*,
  never on both, and a chained `Validate` would lose the PR context and the
  `event == 'push'` guard. In `validate.yml` the same two run on a nightly cron
  (plus `workflow_dispatch`), which catches the rules and the Home Assistant
  releases that move on their own under an untouched repository. Both carry
  `permissions: contents: read`.
- The `brands` check is satisfied locally: `scripts/brand-icons.ts` renders
  `custom_components/apparent_temperature/brand/icon.png` (+ `@2x`) with
  Playwright, from MDI's `thermometer-lines` split into three colourable
  groups. Its `--preview` mode writes contact sheets to `.brand-preview/` for
  picking a variant. Every geometry and colour decision is a named constant in
  that file.
- Not in the default HACS catalog: the README's install button is the
  `my.home-assistant.io/redirect/hacs_repository/` badge, which adds the
  repository as a custom one. Getting into the default catalog would also need
  a description and topics on the GitHub repository itself.

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
- `docker-compose.yml` boots Home Assistant from the **official Docker image**
  against a gitignored `.ha/config/`, with two read-only binds nested in
  `/config`: the component itself and `dev/configuration.yaml` (the seed —
  sensors in mixed units plus a weather entity in K/kn). Because the seed is
  mounted rather than copied once, editing it takes effect on the next start.
  Scripts: `pnpm ha:up` / `ha:logs` / `ha:down`, and `ha:reset` (destructive —
  drops `.ha/config`). The venv holds `homeassistant` only for the test suite;
  nothing launches `hass` from it.
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
