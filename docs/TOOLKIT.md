# Agent toolkit

Shared setup for Claude Code, Antigravity CLI (`agy`) and opencode. Keep it lean: every MCP server and skill costs context.

## Global skills (user level)
Installed with `npx skills add <source> --skill <name> -g -a claude-code -a antigravity-cli -y`.
Canonical copies live in `~/.agents/skills/`, symlinked into `~/.claude/skills/` (Claude Code) and
`~/.gemini/config/skills/` (Antigravity CLI). opencode reads `~/.claude/skills` and `~/.agents/skills` natively.

| Skill | Source | Use for |
|---|---|---|
| frontend-design | anthropics/skills | Distinctive UI direction, typography |
| webapp-testing | anthropics/skills | Driving the local app with Playwright scripts |
| skill-creator | anthropics/skills | Writing/evaluating skills (evals call `claude -p`) |
| mcp-builder | anthropics/skills | Building MCP servers (evals need `ANTHROPIC_API_KEY`) |
| web-design-guidelines | vercel-labs/agent-skills | UI/a11y review against Web Interface Guidelines |
| vercel-react-best-practices | vercel-labs/agent-skills | React/Next.js performance rules |
| find-skills | vercel-labs/skills | Discovering skills (never install with `-y` without asking) |

Not installed (run yourself if wanted): obra/superpowers
- Claude Code: `/plugin install superpowers@claude-plugins-official`
- Antigravity: `agy plugin install https://github.com/obra/superpowers`
- opencode: follow `.opencode/INSTALL.md` in the obra/superpowers repo

## Project skills (this repo)
Single source of truth: `.agents/skills/` (read natively by Antigravity and opencode).
`.claude/skills` is a relative symlink to `../.agents/skills` for Claude Code.

| Skill | Invocation | Use when |
|---|---|---|
| newslice | `/newslice N` (manual only) | Building one vertical slice from docs/traceability.md |
| triage | `/triage <error>` or auto | A test fails or a slice breaks (two-strike rule) |
| harden | `/harden` or auto | Scope freeze: six-pillar audit, fix HIGH only |
| submitpack | `/submitpack [minutes] [post]` (manual only) | Submission README, video script, Q&A, AI_DISCLOSURE |
| demoprep | `/demoprep` (manual only) | Before recording and before judging |
| agentgraph | `/agentgraph` (manual only) | Building the LangGraph from agents/graph.md |

opencode duplicates: opencode v2 keys skills by ID and later sources win (`.agents/skills` is registered after
`.claude/skills`), so the symlink does not produce duplicates. If an older opencode ever lists a skill twice,
run it with `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1` (note: this also hides `~/.claude/skills`).

Claude-only extras: subagents in `.claude/agents/` (contract-reviewer, demo-tester) and the guard hook below.

## Global MCP servers (all three agents)
| Server | Transport | Claude Code | Antigravity | opencode |
|---|---|---|---|---|
| context7 | Streamable HTTP `https://mcp.context7.com/mcp` | `claude mcp add --scope user --transport http ...` | `~/.gemini/config/mcp_config.json` (`serverUrl`) | `~/.config/opencode/opencode.json` (`type: remote`) |
| playwright | stdio `npx @playwright/mcp@latest` | user scope | same file (`command`/`args`) | same file (`type: local`) |

Check: `claude mcp list` · `agy mcp list` (or `/mcp` in a session) · `opencode mcp list`.
Do NOT add GitHub, Supabase, Firebase, Sentry or n8n globally.

## Per-event MCP recipes
`bash scripts/event-mcp.sh <supabase_project_ref> [--read-only] [--n8n] [--firebase]` adds project-scoped servers
to `.mcp.json` (Claude Code, `--scope project`), `.agents/mcp_config.json` (Antigravity, `serverUrl`) and
`./opencode.json` (opencode). Idempotent; backs up existing files first.
- Supabase (OAuth on first use, feature-limited):
  `https://mcp.supabase.com/mcp?project_ref=<ref>&features=database,docs,debugging,development`
  `--read-only` appends `&read_only=true`: use it for anything holding real user data. Never write tokens into files.
- `--n8n`: n8n-MCP `npx n8n-mcp` (docs + validation tools). Workflow management needs `N8N_API_URL`/`N8N_API_KEY`:
  add those by hand from your shell env, never commit them.
- `--firebase`: Firebase MCP `npx -y firebase-tools@latest mcp` (run `npx -y firebase-tools@latest login` once).
The script prints removal commands; run them after the event.
Antigravity: workspace server names must differ from global ones (same name = the already-running one wins).

## SDKs for building our own MCP server
- Python: FastMCP 4.x (`uv add fastmcp`, `FastMCP.from_fastapi(app=app)`), docs via context7.
- Test any server: MCP Inspector `npx @modelcontextprotocol/inspector`.

## CLI-first rule
Prefer CLIs over MCP wrappers: `gh`, `git`, `supabase`, `vercel`, `uv`, `pytest`, `npm`.
They are cheaper on context and their output can be pasted as evidence. GitHub work always goes through `gh`.

## Security rules
- Inspect every third-party skill's `scripts/` before installing (network, deletes, env/secrets, shell).
- Before starting any agent in a cloned repo, read its `.mcp.json`, `opencode.json`, `.agents/mcp_config.json`,
  `.claude/settings.json` (hooks) and `.agents/skills/` — they can launch commands on your machine.
- Never put tokens in committed files; env var NAMES only in `.env.example`.
- Guard hook (`.claude/hooks/guard.sh`, PreToolUse, exit 2 = block): no push to main, no `.env` reads,
  no `openapi.yaml` edits.
- Antigravity guard hook (`.agents/hooks/guard.sh` via `.agents/hooks.json`, PreToolUse on `run_command`, `view_file`,
  `write_to_file`, `replace_file_content`, `multi_replace_file_content`, `grep_search`; replies `{"decision":"deny"}`):
  same rules as the Claude guard. Tests: `bash scripts/test-agy-guard.sh` (also run in CI).
- opencode permissions: see "opencode permissions" below.
- Back up any agent config (`<file>.bak-YYYYMMDD-HHMM`) before editing; merge, never overwrite.

## opencode permissions (`opencode.json`)
Rules are `{action, resource, effect}`; `*` matches anything including `/`; **the last matching rule wins**; no
match = `ask` (https://opencode.ai/docs/permissions). `read`/`edit` match the whole normalized path, `shell` the raw
command text. Each block lists denies first and the `.env.example` allow last.
- read/edit: deny `*.env`, `*.env.*` (+ edit `*openapi.yaml`), allow `*.env.example`.
- shell: deny `git push * main`, `git push * main *`, `git push *:main`, `git push *:main *` (same for master), so
  `feat/maintenance` still pushes; deny `cat *.env*`, `* .env`, `* .env.local*`, `* .env.production*`; allow `* .env.example*`.
- **opencode can't see the current branch:** a plain `git push` while on main is not caught; branch protection
  on main (required CI checks) is the backstop.
- **Precedence:** the global `~/.config/opencode/opencode.json` outranks a project `opencode.json` (its rules are
  appended later and the last match wins). A global `shell "*": ask` or `"cat *": allow` overrides these denies;
  add the same denies at the end of your global rules if you want them enforced everywhere.
- Known gaps: `cat .env.example .env.local` matches the final allow; `less dir/.env.local` falls to the default
  `ask`. The Claude Code and Antigravity guards check every token and do catch both.

Manual test (opencode has no CLI to evaluate a rule; run in a session in this repo, expect the result shown):
| Ask opencode to... | Expect |
|---|---|
| read `.env.local` / edit `.env.local` / edit `openapi.yaml` | denied |
| read or edit `.env.example` | allowed |
| run `cat .env.local`, `grep KEY .env` | denied |
| run `git push origin main`, `git push origin HEAD:main` | denied |
| run `git push origin feat/maintenance` (dry-run: add `--dry-run`) | not denied (ask/allow) |
