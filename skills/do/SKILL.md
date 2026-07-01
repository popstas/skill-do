---
name: do
description: Turn a project's docs/TODO.md into an autonomous plan-and-code loop — evaluate the task list and hand it to ralphex-adopt.
---

`do` is the orchestrator around a project's `docs/TODO.md`. You run it inside an agent to evaluate
the task list, optionally kick off the ralphex pipeline, and edit the task list
(`do add` / `do remove`).

## Manual `/do` flow

When invoked as `/do` (no sub-command):

1. Read project `CLAUDE.md` / `AGENTS.md` first (if present) — defer to any handoff or
   "how to launch work" instructions there before anything below.
2. Read `docs/TODO.md`. Count "task units" (markdown list items `- `, `- [ ]`, `* `, plus level
   1–3 headings other than the title). Summarize what's queued.
3. Use planning skill like `brainstorming`, `ralphex-plan` from available skills. Clarify the plan, update the TODO.md file, commit.
4. **Clear completed todos before implementing.** Remove already-completed (`[x]`) items from
   `docs/TODO.md` so the adopt/implement step only picks up open work, then commit the cleanup
   (standalone cleanup → `task:` prefix; if it rides along with related code, fold it into that
   commit). (Completed items live in git history / the merged PR — they don't need to linger in
   the task list.)
5. If the list looks ready (roughly 3+ open task units and no existing plan under `docs/plans/`),
   **before running `/ralphex:ralphex-adopt`, ask the user how e2e tests should be done** for
   this work (what to run, how to verify behavior end-to-end) so the adopted plan can include
   them. Then offer to run `/ralphex:ralphex-adopt docs/TODO.md`. This converts the free-form
   list into a structured ralphex plan in `docs/plans/`.
6. After the adopt plan is approved, offer to run `/ralphex:ralphex` to execute it autonomously.
7. If nothing is ready, say so and stop — don't manufacture work.
8. When `/ralphex:ralphex` is done, run the **`do finalize`** flow below (mark todo → PR → review → merge → release).

### `do add <task>` / `do remove <task>`

- `do add <task>`: append a `- [ ] <task>` line to `docs/TODO.md` (create the file with a
  top-level heading if it's missing). Keep existing formatting/sections.
- `do remove <task>`: remove the matching list item (match on the task text, confirm if ambiguous).
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
implementation is done, so skip the plan/adopt/implement steps and start directly at step 1 below.
(If `do early pr` already opened the PR, step 2 below just updates it instead of creating a new one.)

Run once implementation is complete and tests pass. Walk these steps in order, pausing for the
user where noted — **never merge or release without explicit human confirmation**.

1. **Mark the TODO.** Check off (`[x]`) the items that are actually done — verify each against the
   code/tests, don't assume. Commit it — fold the checkbox into the related code commit when one
   is part of this change, otherwise use a standalone `task:` commit.
2. **Create the PR.** Push the branch and open a PR against the default branch. **The PR title and
   description must match the actual changes**: read the diff (`git diff <base>...HEAD`) and write
   the summary from what changed, not from the original task wording. Keep it concise and
   reviewer-facing. Add checklist for manual checks of the features.
3. **Wait for human review.** Stop here. Let a human review the PR and do not proceed until the
   user explicitly approves/asks to merge.
4. **Merge the PR.** Once approved, inspect the branch commits first. If the history is noisy
   (fixups, `wip`, review-fix churn), prefer a **squash** merge — but **clarify with the user and
   ask which merge strategy** before merging. If the history is already clean, a normal merge is
   fine.
5. **Suggest a release.** After merge, offer to cut a version release. Decide the bump from the
   branch's changes — **patch** (bugfixes only), **minor** (backward-compatible features), or
   **major** (breaking changes). Propose your choice with a one-line rationale and **ask the user
   to confirm the bump level** before tagging.
6. **Release per the project's rules.** Follow the project's own release process (check
   `CLAUDE.md` / `deploy.py` / `.github/workflows`). **By default, releases are issued by a GitHub
   workflow that triggers on a version-tagged commit** — so bump the version, push the tag, and let
   CI create the GitHub release. Do **not** hand-create the release when the workflow owns it.
7. **Rewrite the release description.** Wait until the release has actually been issued (CI
   finished), then edit its description. Base it on the PR description but **trim it for project
   users, not developers**: drop code/module-level detail, keep what changed and how to use it.
   **Include the PR mention** (e.g. `#12`).
