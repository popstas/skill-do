# `do` skill

Turn a project's `docs/TODO.md` into an autonomous plan-and-code loop. See [`SKILL.md`](./SKILL.md)
for the full behavior: the manual `/do` flow (evaluate the task list → `ralphex-adopt` → `ralphex`),
`do add` / `do remove`, `do early pr`, and `do finalize`.

## Files

- `SKILL.md` — the skill the LLM reads (manual `/do` flow).
- `tests/` — `unittest` validation of the skill frontmatter/body.
