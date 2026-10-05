import contextlib
import io
import json
import tempfile
import os
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from quality_gates import upstream

OLD, NEW = "a" * 40, "b" * 40


class FakeGitHub:
    def __init__(self, head, files, fail=False):
        self.head, self.files, self.fail = head, files, fail

    def __call__(self, url, accept=None):
        if self.fail:
            raise upstream.FetchError("network down")
        if url.endswith("/commits/HEAD"):
            return self.head
        for (ref, path), text in self.files.items():
            if url.endswith(f"/{ref}/{path}"):
                return text
        return None


class Upstream(unittest.TestCase):
    def setUp(self):
        self.record = Path(tempfile.mkdtemp()) / "upstream.json"
        self.record.write_text(json.dumps({"sources": [{
            "repo": "someone/skills", "commit": OLD, "copied": "verbatim",
            "files": {"skills/domain.md": "src/domain.md", "skills/labels.md": "src/labels.md"},
        }]}))

    def check(self, github):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            upstream.main([], self.record, github)
        return stop.exception.code, out.getvalue() + err.getvalue()

    def test_an_upstream_at_the_recorded_commit_reports_nothing(self):
        code, out = self.check(FakeGitHub(OLD, {}))
        self.assertEqual((code, out), (0, "No watched upstream file has changed.\n"))

    def test_upstream_commits_that_leave_our_files_alone_report_nothing(self):
        same = {(OLD, "skills/domain.md"): "d", (NEW, "skills/domain.md"): "d",
                (OLD, "skills/labels.md"): "l", (NEW, "skills/labels.md"): "l"}
        self.assertEqual(self.check(FakeGitHub(NEW, same))[0], 0)

    def test_a_changed_file_is_reported_with_its_diff_and_how_to_adopt_it(self):
        files = {(OLD, "skills/domain.md"): "one\n", (NEW, "skills/domain.md"): "one\ntwo\n",
                 (OLD, "skills/labels.md"): "l", (NEW, "skills/labels.md"): "l"}
        code, out = self.check(FakeGitHub(NEW, files))
        self.assertEqual(code, 1)
        self.assertIn("## someone/skills: 1 watched file(s) changed, aaaaaaa → bbbbbbb", out)
        self.assertIn("### `skills/domain.md` → `src/domain.md`", out)
        self.assertIn("+two", out)
        self.assertNotIn("labels.md", out)
        self.assertIn("set `commit` for that source", out)

    def test_a_file_deleted_upstream_is_reported_as_removed(self):
        files = {(OLD, "skills/domain.md"): "d", (OLD, "skills/labels.md"): "l", (NEW, "skills/labels.md"): "l"}
        code, out = self.check(FakeGitHub(NEW, files))
        self.assertEqual(code, 1)
        self.assertIn("removed upstream", out)

    def test_github_unreachable_exits_2_rather_than_reporting_no_change(self):
        code, out = self.check(FakeGitHub(NEW, {}, fail=True))
        self.assertEqual(code, 2)
        self.assertIn("network down", out)

    def test_the_shipped_record_names_only_files_that_exist_here(self):
        repo = Path(__file__).resolve().parents[1]
        record = json.loads(upstream.RECORD.read_text())
        for source in record["sources"]:
            for local in source["files"].values():
                self.assertTrue((repo / local).is_file(), local)


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class GitHubFetch(unittest.TestCase):
    def fetch(self, outcome, url="https://api.github.com/repos/a/b/commits/HEAD", token=None):
        seen = []

        def urlopen(request, timeout):
            seen.append(request)
            if isinstance(outcome, Exception):
                raise outcome
            return Reply(outcome)

        env = {"GITHUB_TOKEN": token} if token else {}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("urllib.request.urlopen", urlopen):
            return upstream.github_fetch(url), seen[0]

    def test_a_reply_is_returned_as_text(self):
        self.assertEqual(self.fetch(b"abc\n")[0], "abc\n")

    def test_a_token_is_sent_to_the_api_only(self):
        api = self.fetch(b"", token="t")[1]
        raw = self.fetch(b"", url="https://raw.githubusercontent.com/a/b/c/f", token="t")[1]
        self.assertEqual(api.get_header("Authorization"), "Bearer t")
        self.assertIsNone(raw.get_header("Authorization"))

    def test_a_missing_file_is_none(self):
        error = urllib.error.HTTPError("u", upstream.NOT_FOUND, "Not Found", {}, None)
        self.assertIsNone(self.fetch(error)[0])

    def test_any_other_http_error_is_a_fetch_error(self):
        error = urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
        with self.assertRaisesRegex(upstream.FetchError, "HTTP 403"):
            self.fetch(error)

    def test_no_network_is_a_fetch_error(self):
        with self.assertRaisesRegex(upstream.FetchError, "offline"):
            self.fetch(urllib.error.URLError("offline"))


if __name__ == "__main__":
    unittest.main()
