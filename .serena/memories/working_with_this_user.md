# Working with this user

## Memory lives in Serena

Stated on 2026-08-31: Serena is **the** memory store for this project. Write
with `write_memory`, read with `list_memories` / `read_memory`. Do not build a
parallel store under `CLAUDE_CONFIG_DIR`; the only thing left there is a
one-line signpost in `MEMORY.md` pointing back here, because the harness
auto-loads that file at session start and does not auto-read Serena memories.
`AGENTS.md` now carries the same rule, and `.serena/memories/` is versioned
with the project.

Related: `mem:project_overview`.

## Feature branches, never worktrees

Standing rule, stated 2026-09-01: work always happens on a `feat/...` branch in
the main checkout. Do not create git worktrees, and do not ask again — when a
skill calls for an isolated workspace, cut the branch and move on.

It also happens to be the right call here: a worktree would sit in a gitignored
directory, and `.serena/project.yml` has `ignore_all_files_in_gitignore: true`,
so Serena's symbolic tools — which `AGENTS.md` makes primary for code — would
be blind to every file created there. The `.venv` and `node_modules` of the
main checkout keep working too.

## Merge feature branches with `--no-ff`

Stated 2026-09-01: a merge commit is wanted, it is the normal superpowers
workflow. Do not flatten to a fast-forward for the sake of a linear history,
and do not offer to. The branch is deleted after the merge as usual.

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
