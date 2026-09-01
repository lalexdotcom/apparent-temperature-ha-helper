# Agent Operating Rules

## Pair Programming Protocol

1. User leads, agent follows. Wait for the explicit next step.
2. One step at a time. Do not preview future steps unless asked.
3. Be concise. No boilerplate, no over-engineering.
4. No trailing questions ("should I continue?"). Deliver and stop.
5. No unsolicited suggestions. Flag issues in one sentence; do not act.
6. Confirm before large changes (more than a few files or significant refactor).
7. When two approaches reach the same result, choose the non-destructive one —
   or ask first. Never pick a data-losing path (reset, drop, overwrite, force)
   when a data-preserving one exists.
8. No hollow praise or flattery ("Great idea!", "Excellent question!", etc.).
9. A question is answered, not acted on — even if it implies an action.
   Proposing is part of answering; changing anything is not. No edit, no
   dispatch, no commit without explicit validation.


## Language

ALWAYS use **French** language for chat. Everything else: **English**.

## Formatting

Run the project's linter/formatter after every modification if one is configured.

## Scripts

A script a human runs — a development helper, a one-off — goes in `scripts/`,
written in TypeScript and run with `pnpm exec tsx scripts/<name>.ts`. No bash,
no inline `node -e`. Until the project has its own `tsconfig.json`, rely on
tsx's defaults rather than adding one.

Logic a CI workflow runs is the exception: it stays inline in the job's `run:`
block, in shell. Calling `scripts/` from a workflow would drag a whole Node
toolchain into the job to execute a few lines, and actionlint already runs
ShellCheck over every `run:` block.

## Tooling — Serena (symbol-aware MCP)

Serena's symbolic tools are PRIMARY for code; built-in Read/Glob/Grep/Edit are
SECONDARY and must not touch code files when a Serena equivalent exists.

- Explore → `get_symbols_overview`; read a symbol → `find_symbol` (`include_body`);
  callers → `find_referencing_symbols`; definition/overrides → `find_declaration` /
  `find_implementations`.
- Edit → `replace_symbol_body` / `insert_before_symbol` / `insert_after_symbol` /
  `replace_content` (`replace_in_files` to span files); rename → `rename_symbol`;
  delete → `safe_delete_symbol`.
- After an edit → `get_diagnostics_for_file`: language-server errors for any
  language, without a per-language linter being configured.
- Absent under `--context claude-code`, do not look for them: `read_file`,
  `list_dir`, `find_file`, `search_for_pattern`, `create_text_file` and
  `execute_shell_command` are excluded by that context (the built-ins cover them);
  `move`, `inline` and `type_hierarchy` exist only in the JetBrains plugin.
- Built-in Read/Edit/Grep on code only as fallback (Serena failed or file
  unparseable). Read/Edit are fine for non-code (`.md`, JSON, YAML, TOML,
  config, lockfiles).
- Self-check before any Read/Glob/Grep/Edit on a code file: is there a Serena
  tool for this? If yes, switch — every time, not once per session.
- Subagents: every subagent prompt that touches code MUST carry this same rule.

## Memory

Serena owns memory. `write_memory` / `read_memory` / `list_memories` /
`delete_memory` are the only store: their files live in `.serena/memories/`,
they are versioned with the project, and they are what the next session reads.

Do not write to Claude Code's own file-based memory. Its `MEMORY.md` holds a
single entry pointing here and nothing else — a fact recorded in two places
drifts, and the copy Serena cannot see is the one that goes stale.

## Onboarding — First Run

When starting on an unknown or fresh codebase, run a codebase tour before any
task:

1. `get_symbols_overview` on the root and key directories.
2. Populate Serena memory with: stack, entry points, conventions observed.
3. Report a one-paragraph summary to the user before proceeding.

Do not ask the user to describe the project — explore first, ask only what
cannot be inferred.

## Model & Effort Policy (binds superpowers § Model Selection)

Superpowers names tiers, never models. This is the binding mapping, and it
governs **every** subagent dispatch — superpowers or not.

| Tier     | `model` | `effort` |
| -------- | ------- | -------- |
| cheap    | haiku   | low      |
| standard | sonnet  | medium   |
| capable  | opus    | high     |

Use these short aliases, not full model IDs — the Agent tool's `model`
parameter only accepts `sonnet`, `opus`, `haiku`, `fable`, and
`CLAUDE_CODE_SUBAGENT_MODEL` takes an alias too. A full ID pins a snapshot that
goes stale; nothing here should carry one.

- **Never dispatch a subagent without an explicit `model`.** An omitted model
  falls back to `CLAUDE_CODE_SUBAGENT_MODEL` — a default, not a decision.
- **Always pass `effort` too.** An omitted effort inherits the session level
  (`high`), cancelling most of the saving a cheap tier is chosen for.
- Tier choice follows superpowers § Model Selection: complete-spec task over
  1-2 files → cheap; multi-file integration, debugging, and all reviewers →
  standard (mid-tier is the floor — turn count beats token price);
  architecture, design, and the final whole-branch review → capable. Fix-loop
  rounds 4-5 escalate one tier above the implementer that got stuck.
