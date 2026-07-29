# skill-do

- [ ] Decide the fate of `skills/do/` in `ai-slash-commands` — keep the copy, make it a submodule,
      or drop it and install `/do` from this repo only. Until then two skills named `do` can exist
      on one machine.
- [ ] Verify the Cursor install path end to end (`.cursor-plugin/plugin.json` is written to the
      convention `superpowers` uses, but the install flow here is untested).
- [ ] Verify `codex plugin marketplace add` against the published repo, not just a local path.
- [ ] Consider Gemini/Antigravity (`gemini-extension.json`) and opencode (`.opencode/`) packaging if
      either becomes a place `/do` is actually used.
