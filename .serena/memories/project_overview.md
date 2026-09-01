# apparent-temperature-ha-helper

A Home Assistant custom integration, domain `apparent_temperature`: a helper
producing one perceived-temperature sensor from three optional sensor groups
(temperature / humidity / wind speed) plus a weather entity as a per-quantity
fallback.

## State as of 2026-09-01

**Implemented and green, merged into `main`.** 75 tests passing, ruff and biome
clean.

**`1.1.0` was pushed to `main` on 2026-09-01** by the user — they push, the
agent does not. The manifest carried `1.1.0`, so the release chain should have
tagged and published `v1.1.0`; nobody checked from this side, because the
devcontainer has no `gh` CLI. Verify on GitHub before assuming it went out.

**`v1.0.0` is published.** The HACS packaging below landed as `4ecae90` on
`main` on 2026-09-01, and the chain ran end to end on its own: CI green, then
`Release` tagged `v1.0.0` and published it. The three `Release` runs marked
*skipped* on the same commit are the expected no-ops — every CI completion
triggers the workflow, and the job's `if` declines all but the right one.

Dependabot is live too: a pull request bumping `astral-sh/setup-uv` from 6 to
7 was open with CI green at the end of that session.

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
  brand/{icon.png,icon@2x.png}
tests/  dev/configuration.yaml  docker-compose.yml
hacs.json  CHANGELOG.md  LICENSE  scripts/brand-icons.ts
.github/dependabot.yml  .github/workflows/{ci,validate,release}.yml
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
  repository as a custom one.
- **The GitHub repository's description and topics are load-bearing, not
  cosmetic.** `hacs/action` runs `description.py` and `topics.py`, which fail
  on an empty one — and since that action is a CI job, an empty description
  would mean no release. Both were filled in on 2026-09-01. Should the default
  catalog ever be wanted, the `hacs/default` pull request template asks for
  links to a successful HACS run and a successful hassfest run (a link to one
  *job* inside a larger workflow is fine), with no `ignore` key on the action,
  and a release created after those runs went green.

`formulas.py` and `units.py` are pure. `sources.py` is the only module importing
`homeassistant.components.group` — it builds headless `SensorGroup` instances,
never added to `hass`, constructed with device class, state class **and** unit
all explicitly passed. Those three arguments are load-bearing: each makes core
return early instead of negotiating from the members, which is what converts
every member to °C / % / km/h *before* aggregation and what stops core opening
repair issues keyed on an `entity_id` these groups do not have.
`tests/test_ha_internals.py` pins all of that against core.

## 1.1.0 — one entity per measured quantity

Designed and built 2026-09-01, bounded path (no spec, no plan document).

- `sensor.py` now sets up four entities per entry. `SourceHub` owns the single
  `InputResolver`, subscribes once to every source, re-resolves on each change
  and hands the same `ResolvedInputs` to every entity — four entities each
  resolving on their own would mean twelve group aggregations per state change.
- `SourceMeasurementSensor` publishes one quantity in its canonical unit with a
  `source` attribute (`group` / `weather`), driven by a `SensorEntityDescription`
  per section in `MEASUREMENTS`. **Registered disabled** (`entity_registry_
  enabled_default=False`) — the user's call, and it only takes effect at first
  registration, so it cannot be revisited for existing installs.
- All four hang off a `DeviceInfo(identifiers={(DOMAIN, entry_id)},
  entry_type=SERVICE)` named after the helper. That device is what lets
  `has_entity_name` + `translation_key` compose and translate the names; the
  main sensor takes `name = None`, so its displayed name is the device's, i.e.
  exactly what it was before. Its `unique_id` never changed, so entity id and
  history survive.
- **The main sensor keeps every attribute**, `*_source` included. Removing them
  was decided, implemented, then reversed by the user on 2026-09-01 for one
  reason: the measurement entities are disabled by default, so dropping the
  attributes would have made the inputs unreadable until the user enabled
  something. 1.1.0 is therefore purely additive — no BREAKING note. The
  redundancy between attributes and entities is accepted, and the entities earn
  their place by being recorded rather than by being the only way to read a
  value.
- `DEFAULT_IGNORE_NON_NUMERIC = True` in `const.py` is read by both the config
  flow schema and `sources.py`'s fallback — they disagreed silently otherwise.
  Existing entries keep their stored value; only new helpers start from it.
- No config-entry migration: the options schema is untouched, `version` stays 1.

## Choosing a statistic, for two sensors in sun and shade

Worked out with the user on 2026-09-01, for their own house: one temperature +
humidity sensor per side. **Minimum on temperature, maximum on humidity.** Both
pick the same sensor — the shaded one — and they follow the sun through the
day, east in the morning, west in the afternoon.

The reason they agree: a sun-struck sensor is heated by radiation, so it reads
a temperature that is too high. Relative humidity is a ratio against what the
air could hold at that temperature, and the air on both sides holds the same
vapour, so the same sensor also reads a relative humidity that is too *low* —
28 °C / 60 % in the shade is about 40 % on a sensor baked to 35 °C. Mean or
minimum on humidity would pair a shaded temperature with a humidity measured at
another one, understating the vapour, hence the humidex, which rests on nothing
else.

It holds only while the divergence comes from insolation: two genuinely
different microclimates (a watered bed against a paved terrace) would make the
maximum pick the damper air for the wrong reason. And maximum has minimum's
symmetric flaw — a sensor drifting upwards or saturating at 99 % wins silently,
forever. Not written in the README.

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
- Nothing planned for 1.2: the statistics backfill that was slated for it was
  brainstormed and rejected on 2026-09-01 — see
  `mem:statistics_backfill_rejected`.
