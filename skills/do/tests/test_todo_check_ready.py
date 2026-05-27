"""Unit tests for todo_check_ready.py (stdlib unittest, no network)."""
import os
import shlex
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import todo_check_ready as mod  # noqa: E402


SAMPLE = """# My project TODO

Some intro prose.

## Backlog
- [ ] first task
- [ ] second task
- third loose item
* star item
"""


class TaskCountingTests(unittest.TestCase):
    def test_counts_list_items_and_headings_excluding_title(self):
        # "## Backlog" heading + 4 list items = 5
        self.assertEqual(mod.count_task_units(SAMPLE), 5)

    def test_empty_text_is_zero(self):
        self.assertEqual(mod.count_task_units(""), 0)

    def test_prose_only_is_zero(self):
        self.assertEqual(mod.count_task_units("# Title\n\njust words here\n"), 0)

    def test_completed_items_not_counted(self):
        # All work done: heading title skipped, checked items excluded.
        text = "# T\n- [x] done a\n- [X] done b\n"
        self.assertEqual(mod.count_task_units(text), 0)
        self.assertFalse(mod.is_ready(text, 1))

    def test_mixed_counts_only_open_items(self):
        text = "# T\n- [ ] open\n- [x] done\n- another open\n"
        self.assertEqual(mod.count_task_units(text), 2)


class ReadinessThresholdTests(unittest.TestCase):
    def test_below_threshold(self):
        text = "# T\n- [ ] a\n- [ ] b\n"  # 2 units
        self.assertFalse(mod.is_ready(text, 3))

    def test_at_threshold(self):
        text = "# T\n- [ ] a\n- [ ] b\n- [ ] c\n"  # 3 units
        self.assertTrue(mod.is_ready(text, 3))

    def test_above_threshold(self):
        self.assertTrue(mod.is_ready(SAMPLE, 3))

    def test_empty_never_ready(self):
        self.assertFalse(mod.is_ready("   \n", 1))


class DebounceTests(unittest.TestCase):
    def test_notify_when_no_prior_state(self):
        self.assertTrue(mod.should_notify(SAMPLE, {}))

    def test_no_renotify_on_identical_content(self):
        state = {"hash": mod.content_hash(SAMPLE)}
        self.assertFalse(mod.should_notify(SAMPLE, state))

    def test_renotify_on_changed_content(self):
        state = {"hash": mod.content_hash(SAMPLE)}
        self.assertTrue(mod.should_notify(SAMPLE + "\n- [ ] more\n", state))

    def test_state_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = mod.state_path(Path(tmp), Path("/some/project"))
            mod.save_state(path, "abc123")
            loaded = mod.load_state(path)
            self.assertEqual(loaded["hash"], "abc123")
            self.assertIn("notified_at", loaded)


class BuildMessageTests(unittest.TestCase):
    def _write_todo(self, tmp):
        project = Path(tmp) / "proj"
        (project / "docs").mkdir(parents=True)
        todo = project / "docs" / "TODO.md"
        todo.write_text(SAMPLE, encoding="utf-8")
        return project, todo

    def test_contains_copy_paste_command_with_absolute_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, todo = self._write_todo(tmp)
            msg = mod.build_message(project, todo)
            project_abs = str(project.resolve())
            self.assertTrue(Path(project_abs).is_absolute())
            # Command is shlex-quoted so paths with shell metacharacters paste
            # literally rather than expanding in the user's shell.
            expected = (
                f"cd {shlex.quote(project_abs)} "
                f"&& claude {shlex.quote(mod.ADOPT_PROMPT)}"
            )
            self.assertIn(expected, msg)

    def test_copy_paste_command_quotes_shell_metacharacters(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "p$(whoami)"
            (base / "docs").mkdir(parents=True)
            todo = base / "docs" / "TODO.md"
            todo.write_text(SAMPLE, encoding="utf-8")
            msg = mod.build_message(base, todo)
            # The raw, unquoted path must not appear as a bare cd target.
            self.assertNotIn(f"cd {base.resolve()} ", msg)
            self.assertIn(shlex.quote(str(base.resolve())), msg)

    def test_contains_percent_encoded_custom_scheme_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, todo = self._write_todo(tmp)
            msg = mod.build_message(project, todo)
            self.assertIn("claude-code://open?cwd=", msg)
            # the prompt has spaces and a slash; both must be percent-encoded
            self.assertIn("prompt=%2Fralphex%3Aralphex-adopt%20docs%2FTODO.md", msg)
            # a raw space from the prompt must not leak into the URL
            self.assertNotIn("prompt=/ralphex:ralphex-adopt docs/TODO.md", msg)

    def test_mentions_task_count_and_todo_prefix_and_ralphex(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, todo = self._write_todo(tmp)
            msg = mod.build_message(project, todo)
            self.assertIn(str(mod.count_task_units(SAMPLE)), msg)
            self.assertIn("todo:", msg)
            self.assertIn("/ralphex:ralphex", msg)

    def test_both_link_forms_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, todo = self._write_todo(tmp)
            msg = mod.build_message(project, todo)
            self.assertIn("claude ", msg)  # copy-paste command form
            self.assertIn("claude-code://", msg)  # custom-scheme URL form

    def test_underscore_path_is_plain_text_safe(self):
        # The message is sent as plain text, so an underscore in the path needs
        # no Markdown-specific escaping; it must survive intact in the command.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "my_cool_project"
            (project / "docs").mkdir(parents=True)
            todo = project / "docs" / "TODO.md"
            todo.write_text(SAMPLE, encoding="utf-8")
            msg = mod.build_message(project, todo)
            self.assertIn("my_cool_project", msg)
            # No Markdown decoration that an underscore could turn into an
            # unbalanced entity.
            self.assertNotIn("*TODO ready*", msg)
            self.assertNotIn("`", msg)

    def test_backtick_in_path_does_not_break_message(self):
        # A literal backtick in the project path cannot be escaped inside a
        # legacy-Markdown code span; plain text keeps the nudge intact.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "weird`name"
            (project / "docs").mkdir(parents=True)
            todo = project / "docs" / "TODO.md"
            todo.write_text(SAMPLE, encoding="utf-8")
            msg = mod.build_message(project, todo)
            # The shell-quoted command preserves the backtick for copy-paste,
            # and the message carries no Markdown code spans to corrupt.
            self.assertIn(shlex.quote(str(project.resolve())), msg)
            self.assertNotIn("`cd ", msg)

    def test_custom_todo_path_appears_in_message(self):
        # A non-default DO_TODO_PATH must be reflected in the command, URL, and
        # summary text instead of a hardcoded docs/TODO.md.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            (project / "tasks").mkdir(parents=True)
            todo = project / "tasks" / "backlog.md"
            todo.write_text(SAMPLE, encoding="utf-8")
            msg = mod.build_message(project, todo)
            self.assertIn("tasks/backlog.md", msg)
            self.assertIn("ralphex-adopt tasks/backlog.md", msg)
            self.assertNotIn("docs/TODO.md", msg)
            url_line = next(ln for ln in msg.splitlines() if "claude-code://" in ln)
            self.assertIn("tasks%2Fbacklog.md", url_line)


class RunTests(unittest.TestCase):
    def _project(self, tmp, todo_text):
        project = Path(tmp) / "proj"
        (project / "docs").mkdir(parents=True)
        (project / "docs" / "TODO.md").write_text(todo_text, encoding="utf-8")
        return project

    def _config(self, project, tmp, **over):
        cfg = {
            "todo_path": "docs/TODO.md",
            "project_dir": str(project),
            "min_tasks": 3,
            "state_dir": str(Path(tmp) / "state"),
            "agent": "codex",
            "launch_agent": False,
        }
        cfg.update(over)
        return cfg

    def test_injected_sender_receives_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, SAMPLE)
            captured = {}

            def sender(msg):
                captured["msg"] = msg
                return True

            result = mod.run(self._config(project, tmp), sender=sender)
            self.assertTrue(result["ready"])
            self.assertTrue(result["notified"])
            self.assertIn("docs/TODO.md", captured["msg"])

    def test_not_ready_does_not_notify(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, "# T\n- [ ] only one\n")
            calls = []
            result = mod.run(
                self._config(project, tmp), sender=lambda m: calls.append(m) or True
            )
            self.assertFalse(result["ready"])
            self.assertFalse(result["notified"])
            self.assertEqual(calls, [])

    def test_missing_todo(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "empty"
            (project / "docs").mkdir(parents=True)
            result = mod.run(self._config(project, tmp), sender=lambda m: True)
            self.assertEqual(result["reason"], "todo-missing")

    def test_debounce_second_run_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, SAMPLE)
            cfg = self._config(project, tmp)
            first = mod.run(cfg, sender=lambda m: True)
            self.assertTrue(first["notified"])
            second = mod.run(cfg, sender=lambda m: True)
            self.assertFalse(second["notified"])
            self.assertEqual(second["reason"], "unchanged")

    def test_dry_run_produces_message_without_sending(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, SAMPLE)
            calls = []
            cfg = self._config(project, tmp, dry_run=True)
            result = mod.run(cfg, sender=lambda m: calls.append(m) or True)
            self.assertEqual(result["reason"], "dry-run")
            self.assertFalse(result["notified"])
            self.assertIsNotNone(result["message"])
            self.assertEqual(calls, [])

    def test_send_failure_does_not_save_state(self):
        # A failed send must not persist state, so the next run retries.
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, SAMPLE)
            cfg = self._config(project, tmp)
            result = mod.run(cfg, sender=lambda m: False)
            self.assertTrue(result["ready"])
            self.assertFalse(result["notified"])
            self.assertEqual(result["reason"], "send-failed")
            self.assertFalse(mod.state_path(Path(cfg["state_dir"]), project).exists())

    def test_plan_exists_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp, SAMPLE)
            (project / "docs" / "plans").mkdir()
            (project / "docs" / "plans" / "x.md").write_text("plan", encoding="utf-8")
            result = mod.run(self._config(project, tmp), sender=lambda m: True)
            self.assertTrue(result["ready"])
            self.assertEqual(result["reason"], "plan-exists")


class EnsureTelegramSendTests(unittest.TestCase):
    def test_prefers_path_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            onpath = bin_dir / "telegram-send"
            onpath.write_text("#!/bin/sh\n", encoding="utf-8")
            onpath.chmod(0o755)
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{old_path}"
            try:
                resolved = mod.ensure_telegram_send(local_bin=Path(tmp) / "local")
            finally:
                os.environ["PATH"] = old_path
            self.assertEqual(resolved, str(onpath))
            # Nothing was linked into local_bin since PATH already had it.
            self.assertFalse((Path(tmp) / "local" / "telegram-send").exists())

    def test_symlinks_bundled_into_local_bin_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            local_bin = Path(tmp) / "local" / "bin"
            empty = Path(tmp) / "empty"
            empty.mkdir()
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = str(empty)  # ensure telegram-send is NOT on PATH
            try:
                resolved = mod.ensure_telegram_send(local_bin=local_bin)
            finally:
                os.environ["PATH"] = old_path
            link = local_bin / "telegram-send"
            self.assertEqual(resolved, str(link))
            self.assertTrue(link.is_symlink())
            self.assertEqual(
                link.resolve(), mod.bundled_telegram_send().resolve()
            )
            self.assertTrue(os.access(str(link), os.X_OK))


if __name__ == "__main__":
    unittest.main()
