import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from quality_gates import skills_sync


def run(argv, source):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), self_exit() as code:
        skills_sync.main(argv, source)
    return code[0], out.getvalue()


@contextlib.contextmanager
def self_exit():
    code = [None]
    try:
        yield code
    except SystemExit as stop:
        code[0] = stop.code


class SkillsSync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.source = self.tmp / "shipped"
        self.dest = self.tmp / "repo" / ".claude" / "skills"
        self.write(self.source / "cc-python" / "SKILL.md", "cc python v1")
        self.write(self.source / "crap" / "SKILL.md", "crap v1")
        self.write(self.source / "crap" / "reference.md", "crap ref")

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def sync(self):
        return run(["--dest", str(self.dest)], self.source)

    def check(self):
        return run(["--dest", str(self.dest), "--check"], self.source)

    def test_sync_copies_every_shipped_skill_with_its_files(self):
        code, _ = self.sync()
        self.assertEqual(code, 0)
        self.assertEqual((self.dest / "crap" / "reference.md").read_text(), "crap ref")
        self.assertEqual((self.dest / "cc-python" / "SKILL.md").read_text(), "cc python v1")

    def test_check_passes_right_after_a_sync(self):
        self.sync()
        self.assertEqual(self.check()[0], 0)

    def test_check_fails_when_a_skill_has_not_been_copied(self):
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("cc-python/SKILL.md: missing", out)

    def test_check_fails_when_a_copy_was_edited_by_hand(self):
        self.sync()
        self.write(self.dest / "crap" / "SKILL.md", "crap edited")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("crap/SKILL.md: differs", out)

    def test_check_fails_when_the_pinned_version_ships_a_newer_skill(self):
        self.sync()
        self.write(self.source / "crap" / "SKILL.md", "crap v2")
        self.assertEqual(self.check()[0], 1)

    def test_a_file_the_new_version_dropped_fails_the_check_and_sync_removes_it(self):
        self.sync()
        (self.source / "crap" / "reference.md").unlink()
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("crap/reference.md: not shipped", out)
        self.sync()
        self.assertFalse((self.dest / "crap" / "reference.md").exists())

    def test_sync_leaves_the_repos_own_skills_alone(self):
        self.write(self.dest / "cos" / "SKILL.md", "the repo's own skill")
        self.sync()
        self.assertEqual((self.dest / "cos" / "SKILL.md").read_text(), "the repo's own skill")
        self.assertEqual(self.check()[0], 0)

    def test_the_package_ships_every_skill_the_plugin_lists(self):
        names = skills_sync.skill_names(skills_sync.SHIPPED)
        self.assertEqual(names, ["cc-python", "cc-rust", "cc-swift", "crap", "no-comments"])


if __name__ == "__main__":
    unittest.main()
