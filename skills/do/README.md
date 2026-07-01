# `do` skill

Turn a project's `docs/TODO.md` into an autonomous plan-and-code loop. See [`SKILL.md`](./SKILL.md)
for the full behavior: the manual `/do` flow (evaluate the task list, then pick a planning mode by
complexity — `ralphex-plan` → `ralphex` for complex/3+ work, a lighter `brainstorming`/`plan` for
1–2 tasks, or auto mode for a single trivial task), `do add` / `do remove`, `do early pr`, and
`do finalize`.

## Files

- `SKILL.md` — the skill the LLM reads (manual `/do` flow).
- `tests/` — `unittest` validation of the skill frontmatter/body.
