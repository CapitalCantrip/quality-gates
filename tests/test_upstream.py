import contextlib
import datetime
import io
import json
import tempfile
import os
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from quality_gates import manifest, upstream

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
        self.record = Path(tempfile.mkdtemp()) / "record.json"
        self.record.write_text(json.dumps({"sources": [{
            "repo": "someone/skills", "commit": OLD, "copied": "verbatim",
            "files": {"skills/domain.md": "src/domain.md", "skills/labels.md": "src/labels.md"},
        }]}))

    def check(self, github):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            upstream.main([], self.record, github)
        return stop.exception.code, out.getvalue() + err.getvalue()

    def test_a_missing_record_exits_3_with_one_plain_line_naming_the_file(self):
        self.record.unlink()
        self.assertEqual(self.check(FakeGitHub(OLD, {})), (3, f"qg-upstream: {self.record}: not found\n"))

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
        for source in manifest.load_sources():
            for local in source.files.values():
                self.assertTrue((repo / local).is_file(), local)


TODAY = datetime.date(2026, 11, 1)


def admission(name, **fields):
    return dict({"name": name, "kind": "dependency", "licence": "MIT", "practice": "Maintained by one person."}, **fields)


class Upkeep(unittest.TestCase):
    def setUp(self):
        self.components = Path(tempfile.mkdtemp()) / "outside-sources.json"

    def check(self, *admissions):
        self.components.write_text(json.dumps({"format_version": 2, "admissions": list(admissions), "components": []}))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            upstream.main(["--upkeep"], components_path=self.components, today=TODAY)
        return stop.exception.code, out.getvalue() + err.getvalue()

    def test_a_source_whose_last_release_is_13_months_old_and_not_stable_is_reported_with_how_to_renew_it(self):
        code, out = self.check(admission("radon", last_release="2025-10-01"))
        self.assertEqual(code, 1)
        self.assertIn("radon: no release recorded since 2025-10-01 (13 months)", out)
        self.assertIn("mark it stable with the reason", out)

    def test_the_upkeep_report_says_it_read_the_recorded_date_and_not_the_source(self):
        _, out = self.check(admission("radon", last_release="2025-10-01"))
        self.assertIn("This check reads the `last_release` recorded in `components.json`; it does not ask the source.", out)

    def test_a_source_marked_stable_is_not_reported(self):
        code, out = self.check(admission("radon", stable="A finished algorithm."))
        self.assertEqual((code, out), (0, "No outside source has gone quiet.\n"))

    def test_a_source_released_11_months_ago_is_not_reported(self):
        code, _ = self.check(admission("radon", last_release="2025-12-01"))
        self.assertEqual(code, 0)

    def test_only_the_quiet_sources_among_several_are_reported(self):
        code, out = self.check(admission("radon", last_release="2025-10-01"), admission("lizard", last_release="2026-10-24"))
        self.assertEqual(code, 1)
        self.assertIn("radon", out)
        self.assertNotIn("lizard", out)

    def test_a_malformed_manifest_exits_3_with_one_plain_line_naming_the_file(self):
        self.components.write_text("{")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as stop:
            upstream.main(["--upkeep"], components_path=self.components, today=TODAY)
        self.assertEqual(stop.exception.code, 3)
        self.assertTrue(err.getvalue().startswith(f"qg-upstream: {self.components}: not valid JSON"))


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
