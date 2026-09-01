# Planned for 1.2 — backfilling the measurement entities' statistics

Raised by the user on 2026-09-01, right after 1.1.0 was finished, and
deliberately deferred: "on va finir ça, en faire la 1.1, et on fera ça pour la
1.2". Nothing is designed yet — this is the state of the discussion, not a
decision. `mem:project_overview` covers the 1.1.0 entities it would backfill.

## Why it comes up

The three measurement entities land disabled and, once enabled, their long-term
statistics start from that moment. Everything before is a hole, and the user
asked whether it can be filled.

## What was verified against core (2026-09-01)

- `recorder/import_statistics` — admin WebSocket command,
  `homeassistant/components/recorder/websocket_api.py:567`, and its Python
  twin `async_import_statistics`, `recorder/statistics.py:2832`. Inserts hourly
  rows (`start`, `mean`, `min`, `max`) for a `statistic_id` that must be an
  existing entity id, with `source` equal to the recorder domain. Re-importing
  an hour overwrites it, so the operation is replayable.
- `mean_type` and `unit_class` in the metadata are deprecated-when-absent and
  stop working in HA 2026.11 — pass both.
- The integration would have to gain `recorder` in its manifest dependencies;
  it does not load it today.

## What limits the result

| Source | Retention | Yields |
| --- | --- | --- |
| Members' hourly statistics | unlimited | mean / min / max per hour |
| 5-minute statistics | `purge_keep_days` (10 d) | enough to recompute properly |
| Raw states | 10 d | everything, weather entity included |

Fidelity follows the group's statistic: `min` and `max` are exact without
limit (the hourly min of a min-group is the min of the members' hourly mins);
a `mean` group's hourly mean is right but its hourly min/max is not; `median`
and `last` cannot be derived from hourly rows at all. **A weather entity
publishes no statistics**, so every hour that fell back to weather is
unrecoverable beyond the raw-state window.

## The user's idea, and the objections raised

Their proposal: a switch in the config flow, `false` at every opening, and if
it comes back `true` the backfill runs on the enabled entities. Mechanically it
works — `SchemaFlowFormStep(validate_user_input=...)` can pop the key before it
reaches `entry.options`, so it is never persisted.

Three objections put to them, unanswered when the topic was deferred: the job
is long so the flow must return immediately and the only feedback left is the
log or a persistent notification; a switch carries no parameters (depth,
quantities) although fidelity depends on them; and re-opening the options can
relaunch heavy work by accident. Two alternatives offered: an action
`apparent_temperature.backfill_statistics` targeting the device, or a `button`
entity on it.

Scope question also left open: once the three quantities are rebuilt hour by
hour, the **main sensor's own history** can be recomputed too, which is
probably where the value is.

This is a new subsystem — recorder reads, re-aggregation, statistics import —
so it should go through a full brainstorm, spec and plan, not a bounded change.
