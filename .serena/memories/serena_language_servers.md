# Serena language servers in this project

`.serena/project.yml` declares `language_servers: bash, python, typescript`.

## Editing that list requires an MCP restart

The Serena MCP server reads the project config **once, at startup**. Changing
`language_servers` in a running session does nothing: the server keeps whatever
it loaded, and every symbolic tool fails with
`Cannot extract symbols from <file>. Active language servers: ['bash']`.

Fix: restart the Serena MCP server (in Claude Code, `/mcp` then reconnect
`serena`, or restart the session). Only the user can do this — there is no tool
for it. Ask them, do not work around it silently.

## Installing the servers

`serena project index "$PWD"` installs and warms whichever servers the config
declares, but it only pulls a server it has files for. Run on a tree with no
`.py` in it, the Pyright install times out
(`Timeout waiting for Pyright analysis completion`) and leaves
`$SERENA_HOME/language_servers/static/PyrightServer/` empty. Re-run the index
once real source files exist and it completes — verified 2026-09-01, when it
went from `bash=1` to `python=7`.

Feed it `printf 'n\n%.0s' {1..100} |` as `.devcontainer/post-create.sh` does:
its extra-language prompts are hardcoded interactive and die on a closed stdin.

## Fallback

When the Python server is not live, `AGENTS.md`'s Serena-first rule falls back
to the built-in Read/Grep/Edit tools — that is the documented escape hatch, but
say out loud that you are in fallback rather than pretending it is nominal.

Related: `mem:project_overview`.
