# Working with this user

## Memory lives in Serena

Stated on 2026-08-31: Serena is **the** memory store for this project. Write
with `write_memory`, read with `list_memories` / `read_memory`. Do not build a
parallel store under `CLAUDE_CONFIG_DIR`; the only thing left there is a
one-line signpost in `MEMORY.md` pointing back here, because the harness
auto-loads that file at session start and does not auto-read Serena memories.

Related: `mem:project_overview`.

## Verify Home Assistant APIs against core source

When this user questions a Home Assistant API claim, fetch the current core
source and read it — never answer from recollection. On 2026-08-31 they
challenged two claims in a row and both checks paid off:

- the native "Combine the state of several sensors" helper is
  `homeassistant.components.group.sensor.SensorGroup`, **not** `min_max`;
- the `wind_speed` / `speed` device-class question surfaced a real design bug —
  `SpeedConverter` maps Beaufort as `0.836·B^1.5`, so aggregating before
  converting yields a wrong mean.

Their counter-questions are not requests for reassurance; they point at
something that smells wrong, and they have been right both times. Home
Assistant also gives no API stability guarantee for
`homeassistant.components.*`, so recollection goes stale silently.

**How:** `curl` the file from
`https://raw.githubusercontent.com/home-assistant/core/dev/...` into the
scratchpad, grep it, quote what it actually says with the path. Then say
plainly whether the finding changes the design, and ask before editing the
spec — a question is answered, not acted on.

## Rhythm

They answer design questions fast, often with a counter-question rather than a
plain choice — answer it, then re-put the decision. They dislike labels that
imply one option is more universal than another (they rejected "Météo-France"
vs "Apparent temperature" as framing, and asked for names describing the
mechanism instead).
