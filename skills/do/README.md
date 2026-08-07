# `do` skill

Turn a project's `docs/TODO.md` into an autonomous plan-and-code loop. See [`SKILL.md`](./SKILL.md)
for the full behavior: the manual `/do` flow (evaluate the task list, then pick a planning mode by
complexity (doing a quick code investigation first when the complexity isn't clear from the TODO
wording) — `brainstorming` by default, auto mode for a single trivial task, and `ralphex-plan` →
`ralphex` only for genuinely complex work and only after asking the user via `AskUserQuestion`),
`do add` / `do remove`, `do early pr`, and `do finalize`.

## `statusline_block` — ccstatusline Custom Command

`statusline-block.sh` is a standalone bash command (not part of the LLM skill flow) for
[ccstatusline](https://github.com/sirmalloc/ccstatusline). It renders the project's
`docs/TODO.md` checkbox progress as a compact block — a faithful bash port of the tasks segment
from [`claude-statusline-todo`](https://github.com/popstas/claude-statusline-todo)'s
`statusline.cjs`.

Output is plain text — no ANSI escapes, so leave ccstatusline's "preserve ANSI colors" **off** and
let the widget's own color apply:

```
plain:  ☑ 3/8
split:  ☑ 7/23 week │ 48 week+
```

It reads Claude Code's status JSON on stdin (ccstatusline forwards it) to find the project cwd,
then reads `docs/TODO.md` relative to it. Missing file or no checkboxes → prints nothing.

**Wire it into ccstatusline** as a *Custom Command* widget, giving the script's path directly:

```
/path/to/skills/do/statusline-block.sh
```

ccstatusline executes that path itself rather than through a shell, so the file must keep its
executable bit — without it the widget fails with `exit: 126`.

**Env config (all optional):**

- `STATUSLINE_TODO` — TODO file, relative to cwd unless absolute (default `docs/TODO.md`).
- `STATUSLINE_TODO_SPLIT` — **on by default**; split by top-level (`# `) headers when 2+ sections
  exist (the lead section drives `done/total`, each later section adds its open count). Set
  `0|off|false` to force a single plain `done/total`.
- `STATUSLINE_TODO_TOPLEVEL` — **on by default**; count only col-0 checkboxes (ignore indented
  sub-tasks). Set `0|off|false` to also count indented sub-tasks.

## Files

- `SKILL.md` — the skill the LLM reads (manual `/do` flow).
- `statusline-block.sh` — the ccstatusline `statusline_block` custom command (above).
- `tests/` — `unittest` validation of the skill frontmatter/body and `statusline-block.sh`.
