"""Validate the plugin manifests that ship the do skill to Claude Code, Codex, and Cursor.

The version and description live in six files. These tests are the drift guard: a partial
release (one manifest bumped, the rest stale) must fail here rather than ship.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL = REPO_ROOT / "skills" / "do" / "SKILL.md"

PLUGIN_MANIFESTS = [
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
]
# One marketplace manifest serves both Claude Code and Codex: `codex plugin marketplace add`
# reads .claude-plugin/marketplace.json (verified against `codex plugin list`).
MARKETPLACE_MANIFESTS = [
    ".claude-plugin/marketplace.json",
]
# Manifests that declare where the skills live. Claude Code discovers skills/ on its own.
SKILLS_FIELD_MANIFESTS = [
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
]


def load(rel: str) -> dict:
    return json.loads((REPO_ROOT / rel).read_text(encoding="utf-8"))


def skill_description() -> str:
    for line in SKILL.read_text(encoding="utf-8").splitlines():
        if line.startswith("description:"):
            return line.partition(":")[2].strip()
    raise AssertionError("SKILL.md has no description in its frontmatter")


class TestPluginManifests(unittest.TestCase):
    def test_all_manifests_parse(self):
        for rel in PLUGIN_MANIFESTS + MARKETPLACE_MANIFESTS + ["package.json"]:
            with self.subTest(manifest=rel):
                self.assertTrue((REPO_ROOT / rel).is_file(), f"{rel} is missing")
                load(rel)

    def test_plugin_name_is_do(self):
        for rel in PLUGIN_MANIFESTS:
            with self.subTest(manifest=rel):
                self.assertEqual(load(rel)["name"], "do")

    def test_marketplaces_offer_the_do_plugin(self):
        for rel in MARKETPLACE_MANIFESTS:
            with self.subTest(manifest=rel):
                data = load(rel)
                self.assertEqual(data["name"], "skill-do")
                names = [p["name"] for p in data["plugins"]]
                self.assertEqual(names, ["do"])
                self.assertEqual(data["plugins"][0]["source"], "./")

    def test_every_manifest_agrees_on_version(self):
        versions = {}
        for rel in PLUGIN_MANIFESTS + ["package.json"]:
            versions[rel] = load(rel)["version"]
        for rel in MARKETPLACE_MANIFESTS:
            data = load(rel)
            versions[f"{rel}:metadata"] = data["metadata"]["version"]
            versions[f"{rel}:plugins[0]"] = data["plugins"][0]["version"]

        distinct = set(versions.values())
        self.assertEqual(
            len(distinct), 1, f"manifests disagree on version: {versions}"
        )
        self.assertRegex(distinct.pop(), r"^\d+\.\d+\.\d+$")

    def test_description_matches_the_skill(self):
        expected = skill_description()
        for rel in PLUGIN_MANIFESTS:
            with self.subTest(manifest=rel):
                self.assertEqual(load(rel)["description"], expected)
        for rel in MARKETPLACE_MANIFESTS:
            with self.subTest(manifest=rel):
                self.assertEqual(load(rel)["plugins"][0]["description"], expected)

    def test_skills_field_points_at_the_skill(self):
        for rel in SKILLS_FIELD_MANIFESTS:
            with self.subTest(manifest=rel):
                skills_dir = REPO_ROOT / load(rel)["skills"]
                self.assertTrue((skills_dir / "do" / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
