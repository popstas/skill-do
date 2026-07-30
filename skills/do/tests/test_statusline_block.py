"""Validate skills/do/statusline-block.sh — the ccstatusline tasks-block port."""
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "statusline-block.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def run(todo_text: str | None, env: dict | None = None) -> str:
    """Run the script with a temp cwd holding docs/TODO.md; return ANSI-stripped stdout."""
    with tempfile.TemporaryDirectory() as d:
        if todo_text is not None:
            docs = Path(d) / "docs"
            docs.mkdir()
            (docs / "TODO.md").write_text(todo_text, encoding="utf-8")
        stdin = json.dumps({"workspace": {"current_dir": d}})
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            input=stdin,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
        )
        return ANSI.sub("", proc.stdout)


class TestStatuslineBlock(unittest.TestCase):
    def test_plain(self):
        todo = "- [x] a\n- [x] b\n- [x] c\n- [ ] d\n- [ ] e\n- [ ] f\n- [ ] g\n- [ ] h\n"
        self.assertEqual(run(todo), "☑ 3/8")

    def test_no_percentage(self):
        self.assertNotIn("%", run("- [x] a\n- [ ] b\n"))

    def test_missing_file_is_empty(self):
        self.assertEqual(run(None), "")

    def test_no_checkboxes_is_empty(self):
        self.assertEqual(run("# Heading\nplain prose, no checkboxes\n"), "")

    def test_split_on_by_default(self):
        todo = "- [x] a\n- [x] b\n# Week\n- [ ] w1\n- [ ] w2\n- [x] w3\n# Week+\n- [ ] p1\n"
        self.assertEqual(run(todo), "☑ 2/2 │ 2 week │ 1 week+")

    def test_split_disabled(self):
        todo = "- [x] a\n- [x] b\n# Week\n- [ ] w1\n- [ ] w2\n- [x] w3\n# Week+\n- [ ] p1\n"
        self.assertEqual(run(todo, {"STATUSLINE_TODO_SPLIT": "off"}), "☑ 3/6")

    def test_split_needs_two_sections(self):
        # A single section falls back to the plain render even with split on.
        self.assertEqual(run("- [x] a\n- [ ] b\n"), "☑ 1/2")

    def test_toplevel_ignores_indented_by_default(self):
        todo = "- [ ] top1\n  - [ ] sub1\n  - [x] sub2\n- [x] top2\n"
        self.assertEqual(run(todo), "☑ 1/2")

    def test_toplevel_disabled_counts_all(self):
        todo = "- [ ] top1\n  - [ ] sub1\n  - [x] sub2\n- [x] top2\n"
        self.assertEqual(run(todo, {"STATUSLINE_TODO_TOPLEVEL": "false"}), "☑ 2/4")

    def test_custom_todo_path(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "TASKS.md").write_text("- [x] a\n- [ ] b\n- [ ] c\n", encoding="utf-8")
            stdin = json.dumps({"workspace": {"current_dir": d}})
            proc = subprocess.run(
                ["bash", str(SCRIPT)],
                input=stdin,
                capture_output=True,
                text=True,
                env={**os.environ, "STATUSLINE_TODO": "TASKS.md"},
            )
            self.assertEqual(ANSI.sub("", proc.stdout), "☑ 1/3")

    def test_no_ansi_colors(self):
        # Output is plain text — no ANSI escape codes, even in the split render.
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs"
            docs.mkdir()
            todo = "- [x] a\n- [x] b\n# Week\n- [ ] w1\n- [ ] w2\n# Week+\n- [ ] p1\n"
            (docs / "TODO.md").write_text(todo, encoding="utf-8")
            stdin = json.dumps({"workspace": {"current_dir": d}})
            proc = subprocess.run(
                ["bash", str(SCRIPT)], input=stdin, capture_output=True, text=True
            )
            self.assertNotIn("\x1b", proc.stdout)
            self.assertEqual(proc.stdout, "☑ 2/2 │ 2 week │ 1 week+")

    def test_runs_as_a_bare_command(self):
        # ccstatusline executes the configured path directly, not through `bash`. Without the
        # executable bit that is an exit 126 — which every other test here misses, because they
        # all invoke `bash SCRIPT`.
        self.assertTrue(os.access(SCRIPT, os.X_OK), "statusline-block.sh must be executable")
        with tempfile.TemporaryDirectory() as d:
            docs = Path(d) / "docs"
            docs.mkdir()
            (docs / "TODO.md").write_text("- [x] a\n- [ ] b\n", encoding="utf-8")
            proc = subprocess.run(
                [str(SCRIPT)],
                input=json.dumps({"workspace": {"current_dir": d}}),
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "☑ 1/2")


if __name__ == "__main__":
    unittest.main()
