# Backfilling the measurement entities' statistics — designed, then rejected

Brainstormed end to end on 2026-09-01 and **decided against**. Replaces the
earlier `planned_statistics_backfill` note, which held the open question. Do not
reopen this without new facts — everything below was verified against core
source, not recalled. `mem:project_overview` covers the 1.1.0 entities it would
have filled.

## The decision

**No backfill in the integration.** No `update` entity, no
`apparent_temperature.backfill_statistics` action, no `recorder` in the
manifest dependencies. 1.1.0's CHANGELOG already says "statistics start at that
moment, with no backfill", and that stays true.

1.2 is therefore undefined — the backfill was the only thing planned for it.

## Why, in order of weight

1. **Only long-term statistics can be written at all.** There is no API to
   write past states. The recorder exposes eleven WebSocket commands and all
   are about statistics (`recorder/websocket_api.py`); its services are
   `purge`, `purge_entities`, `disable`, `enable`, `get_statistics`. And even
   forcing rows into `states` would be pointless: `purge_old_data`
   (`recorder/purge.py:55`) deletes states, events, `statistics_runs` **and**
   the 5-minute `statistics_short_term` rows past `purge_keep_days` (default
   10, `recorder/__init__.py:105`). Only the hourly `statistics` table is never
   purged. So the *History* tab would have stayed empty whatever we built —
   and "backfill" promises otherwise.
2. **The column the graph draws is the one we cannot get right.** See the
   fidelity table below. For a group aggregating on `min` — the user's own
   config — the exact column is `min`, while the long-term graph plots `mean`.
3. **`last` is irrecoverable and `median` only plausible.** "Last" means the
   most recently updated *member*; hourly rows do not say who updated last.
4. **A silent, undetectable drift.** With `ignore_non_numeric = True` (the
   default since 1.1.0) a member going `unknown` is dropped from the live
   aggregation, so the member count varies inside an hour — and an hourly row
   carries no sample count, so partial coverage cannot be detected. Worked
   example: A reads 25 °C all hour, B is offline until 10:30 then reads 20 °C.
   Live hourly mean = 23.75; reconstruction from hourly rows = 22.5.
5. **A permanent subsystem for a one-shot need.** The hole exists once, created
   by 1.1.0's "disabled by default" choice. After one run nothing needs it again.
6. **Nobody in the ecosystem does this**, and the project that came closest
   backed away from the recorder — see the survey below.

## Fidelity, if it is ever revisited

Reconstructing hour by hour from the members' hourly rows means applying the
group's statistic column by column: `mean` column = stat of the members'
`mean`s, and likewise for `min` and `max`.

| Group statistic | `mean` | `min` | `max` |
| --- | --- | --- | --- |
| `mean` | exact (full coverage) | tightens the extremes | tightens the extremes |
| `min` | `minᵢ(meanᵢ)`, biased high | **exact** | wrong |
| `max` | `maxᵢ(meanᵢ)`, biased low | wrong | **exact** |
| `median` | plausible, not exact | plausible | plausible |
| `last` | meaningless | meaningless | meaningless |

The exactness is an identity, not a fudge: for a `mean` group,
`(1/H)∫g = (1/N)·Σᵢ (1/H)∫xᵢ` by linearity, and extrema commute for a `min`
group. The bias on a `min` group's mean follows from
`meanₜ(minᵢ xᵢ) ≤ minᵢ(meanₜ xᵢ)` — the curve would read slightly too warm,
worst around midday when the two sensors cross.

**"Never average averages" does not apply here.** Core does exactly that
itself: the hourly statistic is `func.avg(StatisticsShortTerm.mean)`
(`recorder/statistics.py:173`), legitimate because the twelve 5-minute buckets
are equal-length. Our members likewise all cover the same hour — only item 4
above breaks it.

Two regimes were on the table: **A** = hourly rows only, one engine, the whole
depth; **C** = last ~10 days rebuilt exactly from 5-minute stats and raw states
(covering `median`, `last` and the weather fallback), regime A beyond. C is two
engines for a ten-day gain, while the hole 1.1.0 created lies beyond it.

Beyond the 10-day window, hours that fell back to the **weather** entity are
unrecoverable — a weather entity publishes no statistics. Conveniently the rule
"rebuild where the members have rows" leaves exactly those hours empty without
having to detect them.

## Trigger forms considered

The user proposed a config-flow switch, then an `update` entity; an action and a
`button` were also weighed. The landing point before the whole feature was
dropped: **the action is the real API, the `update` entity a parameterless
shortcut calling the same coroutine**, both gated by an "Enable backfill"
option. Worth keeping, because `update` turned out to be a better fit than its
semantic hijack suggests:

- `UpdateEntityFeature.PROGRESS` with `in_progress` and `update_percentage`
  0-100 (`update/__init__.py:324`, `:368`) — a real progress bar.
- Core refuses a concurrent run: `if entity.in_progress is not False` raises
  `update_in_progress` (`update/__init__.py:169`), and
  `async_install_with_progress` (`:513`) resets the flag in a `finally`.
- `install` is `admin_only=True` (`update/__init__.py:105`).
- "Raise on every config change" maps to bumping `latest_version`: the state is
  purely `installed_version` vs `latest_version` (`update/__init__.py:449`),
  with a `skipped_version` core restores across restarts (`:533`). The version
  must be an integer or calver — AwesomeVersion cannot compare an ISO
  timestamp, which would return `on` by accident. `installed_version` would
  have to be persisted by us, in `entry.data`.
- Its cost: the entity lands in *Settings → Updates* next to firmware, so an
  "install everything" automation would fire it. The user judged that
  acceptable — it only writes real data, and `Skip` exists.

## Ecosystem survey (2026-09-01)

Nine core integrations call `async_import_statistics` /
`async_add_external_statistics` (excluding `recorder` itself and the
`kitchen_sink` demo): `anglian_water`, `duke_energy`, `elvia`, `ista_ecotrend`,
`mill`, `opower`, `solaredge`, `suez_water`, `tibber`. Every one pulls history
from a utility provider's API. **None reconstructs anything from other HA
entities**, and no helper offers it.

Not an oversight — the feature request *"Ability to recalculate history for a
helper sensor"* has been open since December 2023, still unanswered in May 2026,
its only workaround being raw SQL.

- `klausj1/homeassistant-statistics` — imports/exports long-term statistics
  from CSV/TSV/JSON. External file, nothing derived from entities.
- `ldotlopez/ha-historical-sensor` — a library for integrations whose external
  source holds the history. Its **v3.0 removed state writing entirely**, keeping
  only the statistics API, because "directly manipulating Home Assistant's
  recorder database was extremely complex, fragile, and error-prone".
- `aamcrae/ha-backfill` — deletes and re-inserts rows in `statistics` and
  `statistics_short_term` directly. Out-of-band tooling, not an integration.

## The escape hatch, if the user ever wants their own history back

A one-shot script in `scripts/`, TypeScript run with tsx per `AGENTS.md`,
talking to the WebSocket API with a long-lived token:
`recorder/statistics_during_period` to read the members,
`recorder/import_statistics` to write. Re-importing an hour overwrites it, so
it is replayable. Keeps the integration clean and leaves the approximation with
whoever runs it. Offered, not chosen.

## What happens to history when a helper's config changes

Asked and answered on the way out, worth keeping:

- **Editing a helper preserves everything.** The `unique_id` does not change, so
  the `entity_id` does not either, and since a recorder sensor's
  `statistic_id` *is* its `entity_id`, every existing row stays. You get one
  continuous series whose meaning changes mid-stream with no marker — add a
  group member or switch `mean` to `min` and the curve simply steps. The
  reload makes the entities `unavailable` for a second; a micro-gap in states,
  none in the hourly statistics.
- **Deleting and recreating it loses everything.** New entry, new `unique_id`,
  new entity (`..._2`); the old statistics go orphaned and `validate_statistics`
  raises a `no_state` issue (`sensor/recorder.py:1041`) offering to delete them.
- **The `units_changed` path cannot reach us.** `_update_issues`
  (`sensor/recorder.py:844`) compares the entity's unit with the statistics
  metadata unit and, when they differ irreconcilably, raises a repair offering
  `change_statistics_unit` or `clear_statistics`. Our entities always publish
  their canonical unit (°C / % / km/h) because conversion happens before
  aggregation, so no config change can move it.

This is also the strongest surviving argument *for* a backfill — after a config
change the left half of the curve keeps the old semantics forever. It was put
to the user explicitly and did not change the decision: a rebuilt curve would
be wrong in a different way rather than honestly discontinuous.
