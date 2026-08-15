# skill-do

`/do` is a skill that turns your project's `docs/TODO.md` into a working loop: you write down tasks,
the agent decides how much planning each one deserves, implements it, opens the pull request and
cuts the release — pausing for you at every point where a human should decide.

## Install

For Claude Code. Add the marketplace:

```text
/plugin marketplace add popstas/skill-do
```

Then install the plugin:

```text
/plugin install do@skill-do
```

Codex CLI, Cursor, the `skills` CLI and a symlink setup for working on the skill itself are in
[`docs/details.md`](docs/details.md).

## Usage

Everything revolves around one file, `docs/TODO.md`:

```markdown
# next

- [ ] work queued for the next run

# backlog

- [ ] later / maybe — not picked up by `/do`
```

`# next` is the working queue — that's what `/do` plans and implements from. `# backlog` is parked
work that gets left alone until you ask for it. A fresh TODO gets only `# next`; `# backlog` appears
the first time you park something. An existing TODO in some other layout is kept as is.

The chain below is the normal path: add tasks → run them → finalize into a PR → release.

### Add

```text
/do add fix the retry timeout
/do remove fix the retry timeout
```

`add` appends `- [ ] <task>` to `# next` (or to `# backlog` if you say "later" / "backlog" /
"не сейчас"), `remove` deletes the matching line. Add `push` to the request to also commit and push
the change. Task-list-only commits use the `task:` prefix; when a TODO edit belongs to code you're
already writing, it rides along in that commit instead.

### Do

```text
/do
```

The agent reads `docs/TODO.md`, counts what's queued in `# next`, and — if the wording alone doesn't
show the scope — takes a quick look at the code the task touches. Then it picks the amount of
ceremony to match:

- **a single trivial task** → just implement it, no planning;
- **anything ordinary** (the default) → `brainstorming`: agree on the approach with you, then
  implement it in the same session;
- **genuinely complex work** (cross-cutting, multi-session) → it asks you first whether to go
  through `ralphex-plan` → `ralphex`. It never starts that silently.

Along the way it clears already-completed `[x]` items and **commits each task before starting the
next one**, so one commit stays one change. If `# next` is empty it says so and stops — it won't
invent work; it can offer to promote something from `# backlog` instead.

### Finalize: PR

```text
/do finalize
```

Run this when the implementation is done and tests pass. It checks off the TODO items it can verify
against the code, pushes the branch and opens a PR whose title and description are written **from
the actual diff**, not from the original task wording, plus a checklist of manual checks. If more
commits land later, the PR text is updated in the same turn as the push.

Then it stops and waits for a human review. Nothing is merged until you say so; when you do, it
asks which merge strategy to use (squash for noisy history, merge commit for repos that generate a
changelog from commit messages).

There's also `/do early pr` — only on explicit request — which opens a draft PR as soon as ralphex
finishes implementing, so you can start reviewing while its own review passes keep refining the
branch.

### Release

After the merge, the agent proposes a version bump — patch, minor or major — with a one-line
rationale and **asks you to confirm the level**. It then follows the project's own release process;
by default that means bumping the version and pushing a tag, letting CI create the GitHub release.
Once the release actually exists, it rewrites the description for users rather than developers,
dropping module-level detail and mentioning the PR.

## Statusline

`skills/do/statusline-block.sh` renders TODO progress in
[ccstatusline](https://github.com/sirmalloc/ccstatusline):

```
plain:  ☑ 3/8
split:  ☑ 7/23 week │ 48 week+
```

Wiring and options: [`skills/do/README.md`](skills/do/README.md).

## More

- [`docs/details.md`](docs/details.md) — other agents, local development, tests, releases.
- [`skills/do/SKILL.md`](skills/do/SKILL.md) — the full instructions the agent actually reads.

## License

MIT
