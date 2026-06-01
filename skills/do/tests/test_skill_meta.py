"""Validate skills/do/SKILL.md frontmatter."""
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"


def parse_frontmatter(content: str) -> dict:
    """Parse a leading ``---``-delimited YAML-ish frontmatter block (flat keys)."""
    m = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


class TestSkillMeta(unittest.TestCase):
    def setUp(self):
        self.content = SKILL.read_text(encoding="utf-8")
        self.fields = parse_frontmatter(self.content)

    def test_has_frontmatter(self):
        self.assertTrue(self.content.startswith("---\n"))
        self.assertTrue(self.fields, "frontmatter should parse to non-empty fields")

    def test_name_is_do(self):
        self.assertEqual(self.fields.get("name"), "do")

    def test_description_non_empty(self):
        self.assertTrue(self.fields.get("description"))

    def test_body_documents_key_behaviors(self):
        body = self.content
        self.assertIn("task:", body)  # commit prefix
        self.assertNotIn("todo:", body)  # stale prefix must not reappear
        self.assertIn("/ralphex:ralphex-adopt docs/TODO.md", body)
        self.assertIn("telegram-send", body)  # standalone/cron branch
        self.assertIn("DO_MIN_TASKS", body)  # cron env docs


if __name__ == "__main__":
    unittest.main()
