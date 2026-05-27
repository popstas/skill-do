---
name: do
description: Turn a project's docs/TODO.md into an autonomous plan-and-code loop — evaluate the task list, hand it to ralphex-adopt, and nudge via Telegram when there's enough work queued.
---

`do` is the orchestrator around a project's `docs/TODO.md`. It has two faces:

1. A **cron-driven readiness check** (`todo_check_ready.py`) that decides daily whether the
   task list has accumulated enough work and, if so, sends a Telegram nudge with a command/link
   that opens Claude in the project and runs `/ralphex:ralphex-adopt docs/TODO.md`.
2. A **manual `/do`** flow you run inside an agent to evaluate the task list, optionally kick off
   the ralphex pipeline, and edit the task list (`do add` / `do remove`).

## Manual `/do` flow

When invoked as `/do` (no sub-command):

1. Read project `CLAUDE.md` / `AGENTS.md` first (if present) — defer to any handoff or
   "how to launch work" instructions there before anything below.
2. Read `docs/TODO.md`. Count "task units" (markdown list items `- `, `- [ ]`, `* `, plus level
   1–3 headings other than the title). Summarize what's queued.
3. If the list looks ready (roughly 3+ task units and no existing plan under `docs/plans/`),
   offer to run `/ralphex:ralphex-adopt docs/TODO.md`. This converts the free-form list into a
   structured ralphex plan in `docs/plans/`.
4. After the adopt plan is approved, offer to run `/ralphex:ralphex` to execute it autonomously.
5. If nothing is ready, say so and stop — don't manufacture work.

### `do add <task>` / `do remove <task>`

- `do add <task>`: append a `- [ ] <task>` line to `docs/TODO.md` (create the file with a
  top-level heading if it's missing). Keep existing formatting/sections.
- `do remove <task>`: remove the matching list item (match on the task text, confirm if ambiguous).
- **Commit prefix for task-list edits is `task:`** (e.g. `task: add telegram retry task`).
  This is distinct from code commits — only `docs/TODO.md` changes use `task:`.

## Execution-environment detection

There is no reliable environment variable that names the host agent, so detect by what tools and
context are present. Pick the **first** matching branch:

1. **Telegram-capable agent** (claudeclaw / openclaw / hermes-with-telegram): an inbound
   `<channel source="telegram" chat_id="..." ...>` block is present, or a telegram MCP `reply`
   tool is available. → Reply via that tool, passing the context `chat_id`. Do **not** shell out
   to `telegram-send` here.
2. **hermes** (or any agent without a telegram reply tool but with terminal/handoff ability):
   do **not** just print a link. **Offer to launch a terminal** and run the work — present the
   copy-paste command and the `claude-code://` URL as an actionable "open a terminal and run this"
   suggestion. If the project `CLAUDE.md` / `AGENTS.md` specifies how to hand off or launch work,
   follow that instead of the default terminal offer.
3. **Standalone / cron** (no telegram tool, no agent context): shell out to the bundled
   `telegram-send` CLI (resolved from PATH or next to the script).

In all branches the payload is the same message produced by `build_message()` in
`todo_check_ready.py`: a short task-count summary, a copy-paste shell command
(`cd <abs project> && claude "/ralphex:ralphex-adopt docs/TODO.md"`), a best-effort
`claude-code://open?cwd=...&prompt=...` URL, the `/ralphex:ralphex` follow-up note, and the
`todo:` commit-prefix reminder.

## Cron path

`todo_check_ready.py` is stdlib-only Python — no venv, no deps — so cron has zero install friction.
It is configured entirely through environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `DO_TODO_PATH` | `docs/TODO.md` | task-list path, relative to the project dir |
| `DO_PROJECT_DIR` | git root or cwd | project root |
| `DO_MIN_TASKS` | `3` | readiness threshold (task units) |
| `DO_STATE_DIR` | `~/.cache/ai-slash-commands/do` | debounce state directory |
| `DO_AGENT` | `codex` | agent to launch in opt-in mode |
| `DO_LAUNCH_AGENT` | `0` | set `1` to also spawn `$DO_AGENT /do` when ready |
| `TELEGRAM_TOKEN` | — | Bot API token (required to send) |
| `TELEGRAM_CHAT_ID` | — | target chat id (required to send) |

**"Ready"** means: the file exists and is non-empty, has at least `DO_MIN_TASKS` task units, no
plan already exists under `docs/plans/`, and the content has *changed* since the last notification
(content-hash debounce, so daily runs don't spam).

Inspect the message without sending:

```sh
DRY_RUN=1 TELEGRAM_TOKEN=x TELEGRAM_CHAT_ID=1 python3 skills/do/todo_check_ready.py --dry-run
```

Run it ~daily per project via crontab (adjust the path to where the skill is installed, e.g.
`~/.claude/skills/do/todo_check_ready.py`):

```cron
# 09:17 daily: nudge me when this project's TODO.md is ready to plan
17 9 * * *  cd /path/to/project && TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python3 ~/.claude/skills/do/todo_check_ready.py >> ~/.cache/ai-slash-commands/do/cron.log 2>&1
```
