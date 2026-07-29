# skill-do

- [ ] Decide the fate of `skills/do/` in `ai-slash-commands` — keep the copy, make it a submodule,
      or drop it and install `/do` from this repo only. Until then its `install-configs` step will
      overwrite the `~/.claude/skills/do` symlink that points here (it does `rm -rf` then copies),
      silently reverting local development to the stale copy.
- [ ] The `/do` command shims in `~/.cursor/commands/do.md` and `~/.codex/prompts/do.md` are still
      generated from the `ai-slash-commands` copy, so they are frozen at v0.7.0's predecessor. Either
      port a small generator here or rely on the plugin/skill path in both agents.
- [ ] Verify the Cursor install path end to end (`.cursor-plugin/plugin.json` is written to the
      convention `superpowers` uses, but the install flow here is untested).
- [ ] Consider Gemini/Antigravity (`gemini-extension.json`) and opencode (`.opencode/`) packaging if
      either becomes a place `/do` is actually used.
