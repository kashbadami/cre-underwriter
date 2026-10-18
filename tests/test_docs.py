"""
Checks on the documentation, because the documentation is the deliverable.

Two classes of mistake here are mechanically detectable, so they are detected
rather than promised against: marketing register, and links that point at
nothing.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ["README.md", "SKILL.md", "examples/edgemont-vs-published.md"]

# Vocabulary this repo does not use. Not a style preference: the audience is a
# practitioner who said publicly that he is tired of this category's noise.
BANNED = [
    "transform", "unlock", "powerful", "revolutioni", "seamless", "leverage",
    "cutting-edge", "game-chang", "effortless", "supercharge", "turbocharge",
    "elevate", "empower", "harness", "unleash", "best-in-class", "world-class",
    "state-of-the-art", "next-generation", "AI-powered", "delightful",
    "blazing", "magic", "simply put", "in today's", "look no further",
]

EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF⬀-⯿️]"
)
BADGE = re.compile(r"!\[[^\]]*\]\((https?://(img\.shields\.io|badge)[^)]*)\)")
LINK = re.compile(r"\[[^\]]*\]\(([^)#][^)]*)\)")


def read(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


class TestRegister(unittest.TestCase):
    def test_no_hype_vocabulary(self):
        for rel in DOCS:
            low = read(rel).lower()
            for word in BANNED:
                self.assertNotIn(word.lower(), low, f"{rel} contains {word!r}")

    def test_no_emoji(self):
        for rel in DOCS:
            found = EMOJI.findall(read(rel))
            self.assertEqual(found, [], f"{rel} contains emoji: {found}")

    def test_no_badges(self):
        for rel in DOCS:
            self.assertEqual(BADGE.findall(read(rel)), [], f"{rel} has a badge")


class TestLinks(unittest.TestCase):
    def test_every_relative_link_resolves(self):
        for rel in DOCS:
            base = os.path.dirname(os.path.join(ROOT, rel))
            for target in LINK.findall(read(rel)):
                if target.startswith(("http://", "https://", "mailto:", "<")):
                    continue
                path = os.path.normpath(os.path.join(base, target.split("#")[0]))
                self.assertTrue(os.path.exists(path), f"{rel} links to missing {target}")


class TestSkillFrontmatter(unittest.TestCase):
    def test_skill_md_has_name_and_description(self):
        text = read("SKILL.md")
        self.assertTrue(text.startswith("---\n"), "SKILL.md needs YAML frontmatter")
        block = text.split("---", 2)[1]
        self.assertIn("name:", block)
        self.assertIn("description:", block)

    def test_frontmatter_name_matches_the_directory_convention(self):
        block = read("SKILL.md").split("---", 2)[1]
        name = re.search(r"^name:\s*(\S+)", block, re.M).group(1)
        self.assertEqual(name, "cre-underwriter")


class TestNoSecrets(unittest.TestCase):
    """Nothing in this repo should ever hold a credential."""

    PATTERNS = [
        re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{8,}"),
        re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{20,}"),
    ]

    def test_no_credential_shaped_strings_anywhere(self):
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".venv")]
            for fn in filenames:
                if not fn.endswith((".py", ".md", ".yaml", ".yml", ".json", ".txt")):
                    continue
                path = os.path.join(dirpath, fn)
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
                for pat in self.PATTERNS:
                    self.assertIsNone(
                        pat.search(text),
                        f"{os.path.relpath(path, ROOT)} looks like it contains a credential",
                    )


if __name__ == "__main__":
    unittest.main()
