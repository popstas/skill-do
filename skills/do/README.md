# `do` skill

Turn a project's `docs/TODO.md` into an autonomous plan-and-code loop. See [`SKILL.md`](./SKILL.md)
for the full behavior (manual `/do` flow, `do add` / `do remove`, and execution-environment
detection). This README is the quick operational reference for the cron path and its environment.

## Files

- `SKILL.md` — the skill the LLM reads (manual flow + environment detection).
- `todo_check_ready.py` — stdlib-only Python readiness check (run by cron).
- `telegram-send` — self-contained POSIX `sh` wrapper around the Telegram Bot API.
- `install-cron.sh` — installs/prints a ~daily crontab line for the current project.
- `tests/` — `unittest`, `node --test`, and shell tests.

## Environment variables

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

`DRY_RUN=1` makes both `todo_check_ready.py` and `telegram-send` print the request they would send
instead of calling the network — the test seam.

## What "ready" means

The file exists and is non-empty, has at least `DO_MIN_TASKS` task units, no plan already exists
under `docs/plans/`, and the content has *changed* since the last notification (content-hash
debounce, so daily runs don't spam).

## Inspect the message without sending

```sh
DRY_RUN=1 TELEGRAM_TOKEN=x TELEGRAM_CHAT_ID=1 python3 todo_check_ready.py --dry-run
```

## Cron setup

```sh
# install (idempotent) for the current project:
sh install-cron.sh

# just print the line:
sh install-cron.sh --print

# target a specific project:
sh install-cron.sh --project /path/to/project
```

Or add the line by hand (point at the installed copy, e.g. `~/.claude/skills/do/todo_check_ready.py`):

```cron
# 09:17 daily: nudge me when this project's TODO.md is ready to plan
17 9 * * *  cd /path/to/project && TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python3 ~/.claude/skills/do/todo_check_ready.py >> ~/.cache/ai-slash-commands/do/cron.log 2>&1
```

If `telegram-send` is not on `PATH`, `todo_check_ready.py` self-heals by symlinking the bundled
copy into `~/.local/bin`.
