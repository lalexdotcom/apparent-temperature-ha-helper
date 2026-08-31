#!/usr/bin/env bash
set -euo pipefail

sudo chown -R node:node /ai-tools

uv tool install -p 3.13 "serena-agent==1.7.0"
uv tool install mempalace

# The four hooks in .claude/settings.json call `serena-hooks` by name. If uv's
# executable directory ever stops matching the PATH set in devcontainer.json,
# every one of them becomes a silent no-op — fail the build here instead.
command -v serena-hooks >/dev/null || {
	echo "serena-hooks is not on PATH; check the PATH entry in devcontainer.json" >&2
	exit 1
}

claude plugin marketplace add anthropics/claude-plugins-official
claude plugin install superpowers@claude-plugins-official --scope user

claude plugin marketplace add MemPalace/mempalace
claude plugin install mempalace@mempalace --scope user

claude mcp remove serena --scope user 2>/dev/null || true
claude mcp add serena --scope user -- serena start-mcp-server --context=claude-code --project-from-cwd

# `index` lives under the `project` group and takes the project as a positional
# argument — there is no top-level `serena index` and no `--project-root` flag.
# It auto-creates `.serena/project.yml` when absent and is safe to re-run: a
# second pass just refreshes the LSP cache under `.serena/cache/`.
#
# When auto-creating, Serena enables the majority language and then asks, one
# `input()` per language, whether to enable each additional one it detected.
# There is no non-interactive flag (`interactive=True` is hardcoded), and
# `ask_yes_no` does not catch EOFError, so a closed stdin fails the build with
# an empty error message. Feeding it "n" declines each extra server, which is
# the default those prompts offer anyway. `printf` rather than `yes`: a finite
# write fits the pipe buffer and exits 0, whereas `yes` would die of SIGPIPE
# and `pipefail` would surface that 141 as the status of a successful index.
printf 'n\n%.0s' {1..100} | serena project index "$PWD"

# pnpm honours `packageManager` on its own — with the field set it switches to
# that exact version, corepack not required, so an existing pin is respected
# without anything here. Seed it only when a project carries none, from the pnpm
# the feature just installed. Never overwrite: from then on the pin is the
# authority, and `pnpm self-update` is what moves it. `npm pkg get` prints `{}`
# for a missing key and the quoted value otherwise.
if [ "$(npm pkg get packageManager)" = "{}" ]; then
	npm pkg set "packageManager=pnpm@$(pnpm --version)"
fi

pnpm install

# Playwright browsers + OS deps, for browser-mode unit tests and for driving a
# Home Assistant frontend end to end. Scoped to chromium: HA's frontend is
# Chromium-based everywhere it matters, and this saves ~200 MB and tens of
# seconds per rebuild over the default, which pulls all three browser families.
# `pnpm exec` (not `pnpm dlx`) so the browsers match the `playwright` version
# devDependencies pins — `dlx` would fetch the latest and download browsers the
# pinned runtime cannot launch.
pnpm exec playwright install --with-deps chromium
