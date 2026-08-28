---
name: do
description: Turn a project's docs/TODO.md into a plan-and-code loop — evaluate the task list, brainstorm the approach, and escalate to ralphex-plan only for the most complex work.
argument-hint: "[add | remove | finalize | early pr]"
---

`do` is the orchestrator around a project's `docs/TODO.md`. You run it inside an agent to evaluate
the task list, optionally kick off the ralphex pipeline, and edit the task list
(`do add` / `do remove`).

## `docs/TODO.md` layout

The default layout is two top-level sections:

```markdown
# next

- [ ] work queued for the next run

# backlog

- [ ] later / maybe — not picked up by `/do`
```

- **`# next` is the working queue** — `/do` plans and implements from it. `# backlog` is parked
  work: never plan or implement it unless the user asks, or `# next` is empty (then offer to
  promote items from `# backlog` instead of manufacturing work).
- **Creating the file** (missing or empty): write **only `# next`** — don't add an empty
  `# backlog`. Create `# backlog` the first time something is actually parked there.
- **Don't restructure an existing TODO** that uses another layout (a `# TODO` title, dated
  sections, etc.) — keep its formatting and add to the section that matches. Only introduce
  `# next` / `# backlog` when creating the file or when the user asks for the split.

## Manual `/do` flow

When invoked as `/do` (no sub-command):

1. Read project `CLAUDE.md` / `AGENTS.md` first (if present) — defer to any handoff or
   "how to launch work" instructions there before anything below.
2. Read `docs/TODO.md`. Count "task units" (markdown list items `- `, `- [ ]`, `* `, plus level
   1–3 headings other than the title) **in `# next`** — that's what's queued. Mention the
   `# backlog` size in one line, but don't plan from it.
3. **Pick a planning mode** from the task summary — match the ceremony to the work. If the
   complexity isn't clear from the TODO wording alone, do a **quick code investigation** first
   (grep/read the files the task touches — just enough to gauge scope: how many files/modules are
   involved, whether it's a localized tweak or a cross-cutting change) so you pick the right mode
   deliberately rather than guessing. Keep it lightweight — don't turn it into full planning.

   **The default is `brainstorming`.** ralphex is the exception, reserved for the hardest work —
   don't reach for it just because there are several checkboxes.
   - **Default — anything from a couple of tasks up to ordinary multi-task work** → use the
     `brainstorming` skill, clarify the approach, then implement it in-session.
   - **A single trivial task** → suggest **auto mode**: skip planning entirely and just implement
     it directly in-session (no plan file, no ralphex).
   - **Genuinely complex work only** (cross-cutting change across many modules, a long
     multi-session effort, or work you can't hold in one session) → ralphex may be warranted.
     **Never start it silently: ask the user first with `AskUserQuestion`**, offering
     `brainstorming` (recommended) vs. `/ralphex:ralphex-plan` → `/ralphex:ralphex`, with a
     one-line rationale for why this task might justify ralphex. Only take the ralphex path
     (step 5) if the user picks it; otherwise fall back to brainstorming.

   In every mode, clarify the plan with the user, update `docs/TODO.md`, and commit.

   **Commit each task before starting the next one.** Working through several tasks and committing
   at the end forces a choice between one lumped commit and hunk-splitting that may be impossible:
   two features whose new functions land on adjacent lines share a single diff hunk, and `git
   add -p` is interactive, so it is unavailable in this harness. Commit while the working tree
   still holds one task's worth of change. If it is already too late, say so in the commit message
   and explain both changes there — don't pretend one commit is one change.
4. **Clear completed todos before implementing.** Remove already-completed (`[x]`) items from
   `docs/TODO.md` so the plan/implement step only picks up open work, then commit the cleanup
   (standalone cleanup → `task:` prefix; if it rides along with related code, fold it into that
   commit). (Completed items live in git history / the merged PR — they don't need to linger in
   the task list.)
5. **ralphex-plan path** (only when the user explicitly chose ralphex in step 3 and no plan
   already exists under `docs/plans/`): run `/ralphex:ralphex-plan` referencing the queued TODO items.
   It gathers context and asks about testing strategy interactively and writes a structured plan
   to `docs/plans/` — make sure end-to-end verification (what to run, how to confirm behavior) is
   captured while it asks.
6. After the ralphex-plan is approved, offer to run `/ralphex:ralphex` to execute it autonomously
   (Full mode).
7. If `# next` is empty, say so and stop — don't manufacture work. Offer to promote a `# backlog`
   item into `# next` if the backlog has something worth doing.
8. When `/ralphex:ralphex` is done, run the **`do finalize`** flow below (mark todo → verify live → PR → review → merge → release).

### `do add <task>` / `do remove <task>`

- `do add <task>`: append a `- [ ] <task>` line to the **`# next`** section of `docs/TODO.md`
  (create the file with just `# next` if it's missing or empty). Keep existing
  formatting/sections. If the request parks the task ("backlog", "later", "не сейчас"), append it
  under `# backlog` instead, creating that heading if it doesn't exist yet.
- `do remove <task>`: remove the matching list item from either section (match on the task text,
  confirm if ambiguous).
- **Commit prefix for standalone task-list edits is `task:`** (e.g. `task: add telegram
  retry task`) — use it when the change touches only `docs/TODO.md` with no related code.
- **A TODO edit that accompanies related code may be folded into that code's commit** instead
  of a separate `task:` commit. When you check off / remove an item as part of implementing it,
  stage `docs/TODO.md` together with the code and commit under the code's type
  (`feat:` / `fix:` / etc.) — no extra `task:` commit needed. Only split it out when the TODO
  change stands alone or relates to unrelated work.
- Don't commit if not requested to do so.
- **If the request mentions `push`** (e.g. `do add <task> push`, "add … and push"): after
  editing `docs/TODO.md`, commit it (standalone → `task:` prefix and stage only `docs/TODO.md`
  so unrelated working-tree changes are left untouched; alongside related code → fold into that
  commit) and `git push`.

### `do early pr`

**Only when the user explicitly asks "do early pr"** (never automatically). This opens the PR as
soon as ralphex finishes *implementing* — without waiting for the review pipeline — so a human can
start reviewing while ralphex's own review passes keep refining the branch.

ralphex (full mode) emits ordered markers into its progress file
(`.ralphex/progress/progress-{plan-stem}.txt`): `<<<RALPHEX:ALL_TASKS_DONE>>>` once every task's
checkboxes are implemented, then the review pipeline runs and emits `<<<RALPHEX:REVIEW_DONE>>>`
(Claude) → `<<<RALPHEX:CODEX_REVIEW_DONE>>>` (Codex) → `<<<RALPHEX:REVIEW_DONE>>>` (final Claude).
Each phase commits to the plan's branch.

Flow:

1. **Watch for tasks-done.** While ralphex runs, watch the progress file for
   `<<<RALPHEX:ALL_TASKS_DONE>>>` (a background `until grep -q ... ; do sleep 5; done` loop gives a
   single wake-up; also stop watching if the ralphex process exits first).
2. **Open the PR immediately** when the marker appears — push the branch and `gh pr create` against
   the default branch. Write the title/description from the **actual diff** (`git diff <base>...HEAD`),
   not the task wording. Mark the PR as a draft (`--draft`) since review passes are still pending.
3. **Keep pushing review commits.** Let the review pipeline continue. Each time it commits (after a
   `REVIEW_DONE` / `CODEX_REVIEW_DONE` marker, and at final run completion), `git push` so the open
   PR stays current. When the whole ralphex run finishes, do a final push and mark the PR ready for
   review (`gh pr ready`).
4. **Do not merge or release here.** Early-PR only opens and keeps the PR fresh; merge + release
   still go through `do finalize` with explicit human confirmation.

### `do finalize`

An explicit `do finalize` means **ralphex has finished and the branch is ready to PR** — the
implementation is done, so skip the plan/implement steps and start directly at step 1 below.
(If `do early pr` already opened the PR, step 3 below just updates it instead of creating a new one.)

Run once implementation is complete and tests pass. Walk these steps in order, pausing for the
user where noted — **never merge or release without explicit human confirmation**.

1. **Mark the TODO.** Check off (`[x]`) the items that are actually done — verify each against the
   code/tests, don't assume. Commit it — fold the checkbox into the related code commit when one
   is part of this change, otherwise use a standalone `task:` commit.

   **Sync the project's own docs and skills.** A branch that changes the project's *surface* — a
   CLI flag, a config key, a path, an output format — has to update everything that documents that
   surface, not just the README: `CLAUDE.md` / `AGENTS.md` and any `skills/*/SKILL.md` living in
   the repo. Check it by diffing the source of truth against the doc (e.g. list the flags the
   argument parser defines and grep each one in the skill), not from memory — a flag that made it
   into the README and the GUI still goes missing from a skill nobody reopened.

2. **Verify against the real thing before the PR.** A green unit suite only covers what you thought
   to assert. Run whatever live/end-to-end check the project defines (`CLAUDE.md` / `AGENTS.md`
   usually names it — an opt-in e2e marker, a real export, a dev server) and exercise **every**
   output path the branch touches, not just the one you had in mind: a change that adds a field to
   one renderer can break a different renderer outright while every test stays green. Fix anything
   found here TDD-style (failing test first) and commit it apart from the feature.

   In the PR, state what you verified live and what you **could not** verify (no viewer installed,
   no browser, no credentials) — an unverifiable path becomes a reviewer checklist item, never a
   silent gap.
3. **Create the PR.** Push the branch and open a PR against the default branch. **The PR title and
   description must match the actual changes**: read the diff (`git diff <base>...HEAD`) and write
   the summary from what changed, not from the original task wording. Keep it concise and
   reviewer-facing. Add checklist for manual checks of the features.

   **`gh pr edit` may fail where `gh pr create` worked.** On repos that ever touched Projects
   (classic) it dies with `GraphQL: Projects (classic) is being deprecated ...
   (repository.pullRequest.projectCards)` — the edit path reads fields the create path does not.
   Fall back to REST, which has no such field:

   ```
   gh api repos/<owner>/<repo>/pulls/<n> --method PATCH \
     -f title="..." -F body=@<file>
   ```

   Write the body to a file and pass it with `-F body=@file` rather than inline: bodies are long
   and contain backticks and newlines.

   **Keep the PR in step with the branch.** When more commits land after the PR is open (the user
   adds a task mid-session, review fixes, a follow-up feature), update title, description and the
   manual checklist in the same turn as the push — a PR describing half the branch is worse than
   one describing none of it, because the reviewer trusts it. Drop statements that the new commits
   made untrue, e.g. a note about what is not yet deployed.
4. **Wait for human review.** Stop here. Let a human review the PR and do not proceed until the
   user explicitly approves/asks to merge.
5. **Merge the PR.** Once approved, inspect the branch commits first. If the history is noisy
   (fixups, `wip`, review-fix churn), prefer a **squash** merge — but **clarify with the user and
   ask which merge strategy** before merging. If the history is already clean, a normal merge is
   fine.

   **Если PR стоят стеком** (PR-B нацелен на ветку PR-A, а не на default) — мержи снизу вверх и
   **не передавай `--delete-branch` на нижнем**: удаление базы автоматически закрывает верхний PR,
   после чего он попадает в тупик (реопен требует существующей базы, ретаргет — открытого PR).
   Порядок: смержить PR-A без `--delete-branch` → перенацелить PR-B на default
   (`gh api repos/<owner>/<repo>/pulls/<n> --method PATCH --field base=main`) → смержить PR-B →
   удалить ветки. Если тупик уже случился, восстанови удалённую ветку из её последнего коммита
   (`git push origin <sha>:refs/heads/<branch>`), затем реопен → ретаргет → удалить временную ветку.

   **Если проект генерирует CHANGELOG из сообщений коммитов** (git-cliff, conventional commits) —
   squash уничтожает разбивку: вся ветка схлопывается в одну запись. В таких репозиториях
   рекомендуй merge commit и назови эту причину, когда спрашиваешь про стратегию.
6. **Suggest a release.** After merge, offer to cut a version release. Decide the bump from the
   branch's changes — **patch** (bugfixes only), **minor** (backward-compatible features), or
   **major** (breaking changes). Propose your choice with a one-line rationale and **ask the user
   to confirm the bump level** before tagging.
7. **Release per the project's rules.** Follow the project's own release process (check
   `CLAUDE.md` / `deploy.py` / `.github/workflows`). **By default, releases are issued by a GitHub
   workflow that triggers on a version-tagged commit** — so bump the version, push the tag, and let
   CI create the GitHub release. Do **not** hand-create the release when the workflow owns it.
8. **Rewrite the release description.** Wait until the release has actually been issued (CI
   finished), then edit its description. Base it on the PR description but **trim it for project
   users, not developers**: drop code/module-level detail, keep what changed and how to use it.
   **Include the PR mention** (e.g. `#12`).
